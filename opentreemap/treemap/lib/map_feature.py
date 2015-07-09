# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import datetime

from django.conf import settings
from django.core.urlresolvers import reverse
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.utils.formats import number_format
from django.utils.translation import ugettext as _
from django.db.models import Q

from treemap.audit import Audit
from treemap.ecobackend import ECOBENEFIT_ERRORS
from treemap.lib import execute_sql
from treemap.models import Tree, MapFeature, User, Favorite

from treemap.lib import format_benefits
from treemap.lib.photo import context_dict_for_photo
from treemap.util import leaf_subclasses


def _photo_upload_share_text(feature, has_tree=False):
    return _("I added a photo of this %s!") % feature.display_name.lower()


def _map_feature_audits(user, instance, feature, filters=None,
                        cudf_filters=None):
    if filters is None:
        filters = []
    if cudf_filters is None:
        cudf_filters = []

    readable_plot_fields = feature.visible_fields(user)

    feature_filter = Q(model=feature.feature_type, model_id=feature.pk,
                       field__in=readable_plot_fields)
    filters.append(feature_filter)

    feature_collection_udfs_filter = Q(
        model__in=feature.visible_collection_udfs_audit_names(user),
        model_id__in=feature.collection_udfs_audit_ids())
    cudf_filters.append(feature_collection_udfs_filter)

    # Seems to be much faster to do three smaller
    # queries here instead of ORing them together
    # (about a 50% inprovement!)
    # TODO: Verify this is still the case now that we are also getting
    # collection udf audits
    iaudit = Audit.objects\
        .filter(instance=instance)\
        .exclude(user=User.system_user())

    audits = []
    for afilter in filters:
        audits += list(iaudit.filter(afilter).order_by('-created')[:5])

    # UDF collection audits have some fields which aren't very useful to show
    udf_collection_exclude_filter = Q(
        field__in=['model_id', 'field_definition'])

    for afilter in cudf_filters:
        audits += list(iaudit.filter(afilter)
                             .exclude(udf_collection_exclude_filter)
                             .order_by('-created')[:5])

    audits = sorted(audits, key=lambda audit: audit.updated, reverse=True)[:5]

    return audits


def _add_eco_benefits_to_context_dict(instance, feature, context):
    FeatureClass = feature.__class__

    if not hasattr(FeatureClass, 'benefits'):
        return

    benefits, basis, error = FeatureClass.benefits\
                                         .benefits_for_object(
                                             instance, feature)

    if error in ECOBENEFIT_ERRORS:
        context[error] = True
    elif benefits:
        context.update(format_benefits(instance, benefits, basis))


def _plot_audits(user, instance, plot):
    fake_tree = Tree(instance=instance)
    tree_visible_fields = fake_tree.visible_fields(user)

    # Get a history of trees that were on this plot
    tree_history = plot.get_tree_history()

    tree_filter = Q(model='Tree',
                    field__in=tree_visible_fields,
                    model_id__in=tree_history)

    tree_delete_filter = Q(model='Tree',
                           action=Audit.Type.Delete,
                           model_id__in=tree_history)

    tree_collection_udfs_audit_names =\
        fake_tree.visible_collection_udfs_audit_names(user)

    tree_collection_udfs_filter = Q(
        model__in=tree_collection_udfs_audit_names,
        model_id__in=Tree.static_collection_udfs_audit_ids(
            (instance,), tree_history, tree_collection_udfs_audit_names))

    filters = [tree_filter, tree_delete_filter]
    cudf_filters = [tree_collection_udfs_filter]

    audits = _map_feature_audits(user, instance, plot, filters, cudf_filters)

    return audits


def _add_audits_to_context(audits, context):
    def _audits_are_in_different_groups(prev_audit, audit):
        if prev_audit is None:
            return True
        elif prev_audit.user_id != audit.user_id:
            return True
        else:
            time_difference = last_audit.created - audit.created
            return time_difference > datetime.timedelta(days=1)

    audit_groups = []
    current_audit_group = None
    last_audit = None

    for audit in audits:
        if _audits_are_in_different_groups(last_audit, audit):
            current_audit_group = {
                'created': audit.created,
                'user': audit.user,
                'audits': []}
            audit_groups.append(current_audit_group)
        current_audit_group['audits'].append(audit)
        last_audit = audit
    # Converting the audit groups to tuples makes the template code cleaner
    context['recent_activity'] = [
        (ag['user'], ag['created'], ag['audits']) for ag in audit_groups]

    if len(audits) > 0:
        context['latest_update'] = audits[0]
    else:
        context['latest_update'] = None


def get_map_feature_or_404(feature_id, instance, type=None):
    if type:
        MapFeatureSubclass = MapFeature.get_subclass(type)
        InstanceMapFeature = instance.scope_model(MapFeatureSubclass)
        return get_object_or_404(InstanceMapFeature, pk=feature_id)

    else:
        InstanceMapFeature = instance.scope_model(MapFeature)
        feature = get_object_or_404(InstanceMapFeature, pk=feature_id)

        # Return the concrete subtype (e.g. Plot), not a general MapFeature
        return feature.cast_to_subtype()


def context_dict_for_plot(request, plot, tree_id=None, **kwargs):
    context = context_dict_for_map_feature(request, plot, **kwargs)

    instance = request.instance
    user = request.user

    if tree_id:
        tree = get_object_or_404(Tree,
                                 instance=instance,
                                 plot=plot,
                                 pk=tree_id)
    else:
        tree = plot.current_tree()

    if tree:
        tree.convert_to_display_units()

    if tree is not None:
        photos = tree.photos()
        # can't send a regular photo qs because the API will
        # serialize this to JSON, which is not supported for qs
        context['photos'] = [context_dict_for_photo(request, photo)
                             for photo in photos]
    else:
        photos = []

    has_tree_diameter = tree is not None and tree.diameter is not None
    has_tree_species_with_code = tree is not None \
        and tree.species is not None and tree.species.otm_code is not None
    has_photo = tree is not None and len(photos) > 0

    total_progress_items = 4
    completed_progress_items = 1  # there is always a plot

    if has_tree_diameter:
        completed_progress_items += 1
    if has_tree_species_with_code:
        completed_progress_items += 1
    if has_photo:
        completed_progress_items += 1

    context['progress_percent'] = int(100 * (
        completed_progress_items / total_progress_items))

    context['progress_messages'] = []
    if not tree:
        context['progress_messages'].append(_('Add a tree'))
    if not has_tree_diameter:
        context['progress_messages'].append(_('Add the diameter'))
    if not has_tree_species_with_code:
        context['progress_messages'].append(_('Add the species'))
    if not has_photo:
        context['progress_messages'].append(_('Add a photo'))

    url_kwargs = {'instance_url_name': instance.url_name,
                  'feature_id': plot.pk}
    if tree:
        url_name = 'add_photo_to_tree'
        url_kwargs = dict(url_kwargs.items() + [('tree_id', tree.pk)])
    else:
        url_name = 'add_photo_to_plot'

    context['upload_photo_endpoint'] = reverse(url_name, kwargs=url_kwargs)

    context['plot'] = plot
    context['has_tree'] = tree is not None
    # Give an empty tree when there is none in order to show tree fields easily
    context['tree'] = tree or Tree(plot=plot, instance=instance)

    context['photo_upload_share_text'] = _photo_upload_share_text(
        plot, tree is not None)

    audits = _plot_audits(user, instance, plot)

    _add_audits_to_context(audits, context)

    _add_share_context(context, request, photos)

    return context


def context_dict_for_resource(request, resource, **kwargs):
    context = context_dict_for_map_feature(request, resource, **kwargs)
    instance = request.instance

    # Give them 2 for adding the resource and answering its questions
    total_progress_items = 3
    completed_progress_items = 2

    photos = resource.photos()
    context['photos'] = [context_dict_for_photo(request, photo)
                         for photo in photos]

    has_photos = len(photos) > 0

    if has_photos:
        completed_progress_items += 1

    context['upload_photo_endpoint'] = reverse(
        'add_photo_to_map_feature',
        kwargs={'instance_url_name': instance.url_name,
                'feature_id': resource.pk})

    context['progress_percent'] = int(100 * (
        completed_progress_items / total_progress_items) + .5)

    context['progress_messages'] = []
    if not has_photos:
        context['progress_messages'].append(_('Add a photo'))

    audits = _map_feature_audits(request.user, request.instance, resource)

    _add_audits_to_context(audits, context)

    _add_share_context(context, request, photos)

    return context


def title_for_map_feature(feature):
    # Cast allows the map feature subclass to handle generating
    # the display name
    feature = feature.cast_to_subtype()

    if feature.is_plot:
        tree = feature.current_tree()
        if tree:
            if tree.species:
                title = tree.species.common_name
            else:
                title = _("Missing Species")
        else:
            title = _("Empty Planting Site")
    else:
        title = feature.display_name

    return title


def context_dict_for_map_feature(request, feature, edit=False):
    context = {}

    if edit:
        if feature.is_plot or getattr(feature, 'is_editable', False):
            context['editmode'] = edit
        else:
            raise PermissionDenied("Cannot edit '%s' objects"
                                   % feature.feature_type)

    instance = request.instance
    if instance.pk != feature.instance_id:
        raise Exception("Invalid instance, does not match map feature")

    feature.instance = instance  # save a DB lookup

    user = request.user
    if user and user.is_authenticated():
        feature.mask_unauthorized_fields(user)
        favorited = Favorite.objects \
            .filter(map_feature=feature, user=user).exists()
    else:
        favorited = False

    feature.convert_to_display_units()

    context.update({
        'feature': feature,
        'feature_type': feature.feature_type,
        'title': title_for_map_feature(feature),
        'address_full': feature.address_full,
        'upload_photo_endpoint': None,
        'photos': None,
        'share': None,
        'favorited': favorited,
        'photo_upload_share_text': _photo_upload_share_text(feature),
    })

    _add_eco_benefits_to_context_dict(instance, feature, context)

    return context


def _add_share_context(context, request, photos):
    if len(photos) > 0:
        photo_url = photos[0].thumbnail.url
    elif context.get('has_tree'):
        photo_url = settings.STATIC_URL + "img/tree.png"
    else:
        photo_url = settings.STATIC_URL + "img/otmLogo126.png"
    photo_url = request.build_absolute_uri(photo_url)

    title = _("%(feature)s on %(treemap)s") % {
        'feature': context['title'],
        'treemap': request.instance.name
    }

    if context.get('benefits_total_currency', 0) > 0:
        description = \
            _("This %(feature)s saves %(currency)s%(amount)s per year.") \
            % {
                'feature': context['title'],
                'currency': context['currency_symbol'],
                'amount': number_format(context['benefits_total_currency'],
                                        decimal_pos=0)
            }
    else:
        description = _("This %(feature)s is mapped on %(treemap)s") % {
            'feature': context['title'],
            'treemap': request.instance.name
        }

    url = reverse('map_feature_detail',
                  kwargs={'instance_url_name': request.instance.url_name,
                          'feature_id': context['feature'].pk})

    context['share'] = {
        'url': request.build_absolute_uri(url),
        'title': title,
        'description': description,
        'image': photo_url,
    }


def set_map_feature_updated_at():
    models = [Model.map_feature_type for Model in
              leaf_subclasses(MapFeature)]
    if not models:
        raise Exception("Could not find any map_feature subclasses")

    models_in = "('%s')" % "','".join(models)

    # For a baseline, pull the most recent change to the MapFeature itself.
    # This depends on the fact that all the MapFeature subclasses share the
    # same id pool and ids do not overlap.
    # NOTE: This MUST be run first. Additional update queries compare
    # dates against the updated_at values set by this statement.
    execute_sql("""
UPDATE treemap_mapfeature
SET updated_at = a.updated_at
FROM (
  SELECT model_id as id, MAX(created) AS updated_at
  FROM treemap_audit
  WHERE treemap_audit.model IN %s
  GROUP BY model_id
) a
    WHERE a.id = treemap_mapfeature.id;""" % models_in)

    # If the tree associated with a MapFeature has been updated more
    # recently than the MapFeature, copy the tree's most recent
    # update date to the MapFeature
    execute_sql("""
UPDATE treemap_mapfeature
SET updated_at = GREATEST(treemap_mapfeature.updated_at, b.updated_at)
FROM (
  SELECT plot_id as id, a.updated_at
  FROM treemap_tree
  JOIN (
    SELECT model_id as tree_id, MAX(created) AS updated_at
    FROM treemap_audit
    WHERE treemap_audit.model = 'Tree'
    GROUP BY model_id
  ) a
  ON a.tree_id = treemap_tree.id
) b
WHERE b.id = treemap_mapfeature.id;""")

    # If a photo associated with a Tree or MapFeature has been updated more
    # recently than the MapFeature, copy the photo's most recent
    # update date to the MapFeature. TreePhoto is a subclass of
    # MapFeaturePhoto so they share the same id range.
    execute_sql("""
UPDATE treemap_mapfeature
SET updated_at = GREATEST(treemap_mapfeature.updated_at, b.updated_at)
FROM (
  SELECT map_feature_id as id, a.updated_at
  FROM treemap_mapfeaturephoto
  JOIN (
    SELECT model_id as photo_id, MAX(created) AS updated_at
    FROM treemap_audit
    WHERE treemap_audit.model in ('TreePhoto', 'MapFeaturePhoto')
    GROUP BY model_id
  ) a
  ON a.photo_id = treemap_mapfeaturephoto.id
) b
WHERE b.id = treemap_mapfeature.id;
""")
