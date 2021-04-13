# -*- coding: utf-8 -*-


from django.db.models import Q

from treemap.audit import Audit, Authorizable, get_auditable_class
from treemap.models import Instance, MapFeature, InstanceUser, User
from treemap.util import get_filterable_audit_models
from treemap.lib.object_caches import udf_defs
from treemap.udf import UDFModel


def _instance_ids_edited_by(user):
    return Audit.objects.filter(user=user)\
                        .values_list('instance_id', flat=True)\
                        .exclude(instance_id=None)\
                        .distinct()


PAGE_DEFAULT = 20
ALLOWED_MODELS = get_filterable_audit_models()


def get_audits(logged_in_user, instance, query_vars, user=None,
               models=ALLOWED_MODELS, model_id=None, start_id=None,
               prev_start_ids=[], page_size=PAGE_DEFAULT, exclude_pending=True,
               should_count=False):
    if instance:
        if instance.is_accessible_by(logged_in_user):
            instances = Instance.objects.filter(pk=instance.pk)
        else:
            instances = Instance.objects.none()
    # If we didn't specify an instance we only want to
    # show audits where the user has permission
    else:
        instances = Instance.objects\
            .filter(user_accessible_instance_filter(logged_in_user))
        if user:
            instances = instances.filter(pk__in=_instance_ids_edited_by(user))
        instances = instances.distinct()

    if not instances.exists():
        # Force no results
        return {'audits': Audit.objects.none(),
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

    for inst in instances:
        eligible_models = ({'Tree', 'TreePhoto', 'MapFeaturePhoto'} |
                           set(inst.map_feature_types)) & set(models)

        if logged_in_user == user:
            eligible_udfs = {'udf:%s' % udf.id for udf in udf_defs(inst)
                             if udf.model_type in eligible_models
                             and udf.iscollection}

            # The logged-in user can see all their own edits
            model_filter = model_filter | Q(
                instance=inst, model__in=(eligible_models | eligible_udfs))

        else:
            # Filter other users' edits by their visibility to the
            # logged-in user
            for model in eligible_models:
                ModelClass = get_auditable_class(model)
                fake_model = ModelClass(instance=inst)
                if issubclass(ModelClass, Authorizable):
                    visible_fields = fake_model.visible_fields(logged_in_user)
                    model_filter = model_filter |\
                        Q(model=model, field__in=visible_fields, instance=inst)
                else:
                    model_filter = model_filter | Q(model=model, instance=inst)

                if issubclass(ModelClass, UDFModel):
                    model_collection_udfs_audit_names = (
                        fake_model.visible_collection_udfs_audit_names(
                            logged_in_user))

                    model_filter = model_filter | (
                        Q(model__in=model_collection_udfs_audit_names))

    udf_bookkeeping_fields = Q(
        model__startswith='udf:',
        field__in=('id', 'model_id', 'field_definition'))

    audits = (Audit.objects
              .filter(model_filter)
              .filter(instance__in=instances)
              .select_related('instance')
              .exclude(udf_bookkeeping_fields)
              .exclude(user=User.system_user())
              .order_by('-pk'))

    if user:
        audits = audits.filter(user=user)
    if model_id:
        audits = audits.filter(model_id=model_id)
    if exclude_pending:
        audits = audits.exclude(requires_auth=True, ref__isnull=True)

    # Slicing the QuerySet uses a SQL Limit, which has proven to be quite slow.
    # By relying on the fact the our list is ordered by primary key from newest
    # to oldest, we can rely on the index on the primary key, which is faster.
    if start_id is not None:
        audits = audits.filter(pk__lte=start_id)

    total_count = audits.count() if should_count else 0
    audits = audits[:page_size]

    # Coerce the queryset into a list so we can get the last audit row on the
    # current page
    audits = list(audits)

    # We are using len(audits) instead of audits.count() because we
    # have already realized the queryset at this point
    if len(audits) == page_size:
        query_vars.setlist('prev', prev_start_ids + [audits[0].pk])
        query_vars['start'] = audits[-1].pk - 1
        next_page = "?" + query_vars.urlencode()
    else:
        next_page = None

    if prev_start_ids:
        if len(prev_start_ids) == 1:
            del query_vars['prev']
            del query_vars['start']
        else:
            prev_start_id = prev_start_ids.pop()
            query_vars.setlist('prev', prev_start_ids)
            query_vars['start'] = prev_start_id
        prev_page = "?" + query_vars.urlencode()
    else:
        prev_page = None

    return {'audits': audits,
            'total_count': total_count,
            'next_page': next_page,
            'prev_page': prev_page}


def get_audits_params(request):
    PAGE_MAX = 100

    r = request.GET

    page_size = min(int(r.get('page_size', PAGE_DEFAULT)), PAGE_MAX)
    start_id = r.get('start', None)
    if start_id is not None:
        start_id = int(start_id)

    prev_start_ids = [int(pk) for pk in r.getlist('prev')]

    models = r.getlist('models', default=ALLOWED_MODELS)

    if models:
        for model in models:
            if model not in ALLOWED_MODELS:
                raise Exception("Invalid model: %s" % model)

    model_id = r.get('model_id', None)

    if model_id is not None and len(models) != 1:
        raise Exception("You must specific one and only model "
                        "when looking up by id")

    exclude_pending = r.get('exclude_pending', "false") == "true"

    return {'start_id': start_id, 'prev_start_ids': prev_start_ids,
            'page_size': page_size, 'models': models, 'model_id': model_id,
            'exclude_pending': exclude_pending}


def user_accessible_instance_filter(logged_in_user):
    public = Q(is_public=True)
    if logged_in_user is not None and not logged_in_user.is_anonymous:
        private_with_access = Q(instanceuser__user=logged_in_user)

        instance_filter = public | private_with_access
    else:
        instance_filter = public
    return instance_filter


def get_user_instances(logged_in_user, user, current_instance=None):

    # Which instances can the logged-in user see?
    instance_filter = (user_accessible_instance_filter(logged_in_user))

    user_instance_ids = (InstanceUser.objects
                         .filter(user_id=user.pk)
                         .values_list('instance_id', flat=True))

    instance_filter = Q(instance_filter, Q(pk__in=user_instance_ids))

    # The logged-in user should see the current instance in their own list
    if current_instance and logged_in_user == user:
        instance_filter = instance_filter | Q(pk=current_instance.id)

    return (Instance.objects
            .filter(instance_filter)
            .distinct()
            .order_by('name'))
