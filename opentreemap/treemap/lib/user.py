# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import urllib

from django.db.models import Q

from treemap.audit import Audit, Authorizable, get_auditable_class
from treemap.models import Plot, Tree, Instance, MapFeature, InstanceUser
from treemap.util import get_filterable_audit_models


def get_audits(logged_in_user, instance, query_vars, user, models,
               model_id, page=0, page_size=20, exclude_pending=True,
               should_count=False):
    start_pos = page * page_size
    end_pos = start_pos + page_size

    if instance:
        if instance.is_accessible_by(logged_in_user):
            instances = Instance.objects.filter(pk=instance.pk)
        else:
            instances = []
    # If we didn't specify an instance we only want to
    # show audits where the user has permission
    else:
        instances = Instance.objects.filter(
            user_accessible_instance_filter(logged_in_user))

    if len(instances) == 0:
        # Force no results
        return {'audits': [],
                'total_count': 0,
                'next_page': None,
                'prev_page': None}

    map_feature_models = set(MapFeature.subclass_dict().keys())
    model_filter = Q()
    # We only want to show the TreePhoto's image, not other fields
    # and we want to do it automatically if 'Tree' was specified as
    # a model.  The same goes for MapFeature(s) <-> MapFeaturePhoto
    # There is no need to check permissions, because photos are always visible
    if 'Tree' in models:
        model_filter = model_filter | Q(model='TreePhoto', field='image')
    if map_feature_models.intersection(models):
        model_filter = model_filter | Q(model='MapFeaturePhoto', field='image')

    if logged_in_user == user:
        # The logged-in user can see all their own edits
        model_filter = model_filter | \
            Q(model__in=models) | Q(model__startswith='udf:')
    else:
        # Filter other users' edits by their visibility to the logged-in user
        for inst in instances:
            for model in models:
                ModelClass = get_auditable_class(model)
                if issubclass(ModelClass, Authorizable):
                    fake_model = ModelClass(instance=inst)
                    visible_fields = fake_model.visible_fields(logged_in_user)
                    model_filter = model_filter |\
                        Q(model=model, field__in=visible_fields, instance=inst)
                else:
                    model_filter = model_filter | Q(model=model, instance=inst)

                # Add UDF collections related to model
                if model == 'Tree':
                    fake_model = Tree(instance=inst)
                elif model == 'Plot':
                    fake_model = Plot(instance=inst)
                else:
                    continue

                model_collection_udfs_audit_names =\
                    fake_model.visible_collection_udfs_audit_names(
                        logged_in_user)

                model_filter = model_filter |\
                    Q(model__in=model_collection_udfs_audit_names)

    udf_bookkeeping_fields = Q(
        model__startswith='udf:',
        field__in=('id', 'model_id', 'field_definition'))

    audits = Audit.objects \
        .filter(model_filter) \
        .filter(instance__in=instances) \
        .exclude(udf_bookkeeping_fields) \
        .order_by('-created', 'id')

    if user:
        audits = audits.filter(user=user)
    if model_id:
        audits = audits.filter(model_id=model_id)
    if exclude_pending:
        audits = audits.exclude(requires_auth=True, ref__isnull=True)

    total_count = audits.count() if should_count else 0
    audits = audits[start_pos:end_pos]

    query_vars = {k: v for (k, v) in query_vars.iteritems() if k != 'page'}
    next_page = None
    prev_page = None
    if len(audits) == page_size:
        query_vars['page'] = page + 1
        next_page = "?" + urllib.urlencode(query_vars)
    if page > 0:
        query_vars['page'] = page - 1
        prev_page = "?" + urllib.urlencode(query_vars)

    return {'audits': audits,
            'total_count': total_count,
            'next_page': next_page,
            'prev_page': prev_page}


def get_audits_params(request):
    PAGE_MAX = 100
    PAGE_DEFAULT = 20

    r = request.REQUEST

    page_size = min(int(r.get('page_size', PAGE_DEFAULT)), PAGE_MAX)
    page = int(r.get('page', 0))

    models = []

    allowed_models = get_filterable_audit_models()
    models_param = r.get('models', None)

    if models_param:
        for model in models_param.split(','):
            if model.lower() in allowed_models:
                models.append(allowed_models[model.lower()])
            else:
                raise Exception("Invalid model: %s" % model)
    else:
        models = allowed_models.values()

    model_id = r.get('model_id', None)

    if model_id is not None and len(models) != 1:
        raise Exception("You must specific one and only model "
                        "when looking up by id")

    exclude_pending = r.get('exclude_pending', "false") == "true"

    return (page, page_size, models, model_id, exclude_pending)


def user_accessible_instance_filter(logged_in_user):
    public = Q(is_public=True)
    if logged_in_user is not None and not logged_in_user.is_anonymous():
        private_with_access = Q(instanceuser__user=logged_in_user)

        instance_filter = public | private_with_access
    else:
        instance_filter = public
    return instance_filter


def get_user_instances(logged_in_user, user, current_instance=None):
    # Which instances can the user being inspected see?
    user_instances = {iu.instance for iu in InstanceUser.objects
                        .filter(user=user)
                        .select_related('instance')}

    # Which instances can the logged-in user see?
    accessible_filter = user_accessible_instance_filter(logged_in_user)
    accessible_instances = set(Instance.objects.filter(accessible_filter))

    instances = user_instances.intersection(accessible_instances)

    # The logged-in user should see the current instance in their own list
    if current_instance and logged_in_user == user:
        instances = instances.union({current_instance})

    instances = sorted(instances, cmp=lambda x, y: cmp(x.name, y.name))
    return instances
