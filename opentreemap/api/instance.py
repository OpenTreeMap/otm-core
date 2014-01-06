def instance_info(request, instance):
    """
    Get all the info we need about a given instance

    If also includes info about the fields available for the
    instance. If a user has been specified the field info
    will be tailored to that user
    """
    user = request.user
    center = instance.center
    center.transform(4326)

    role = instance.default_role
    if user and not user.is_anonymous():
        instance_user = user.get_instance_user(instance)
        if instance_user:
            role = instance_user.role

    perms = {}

    for fp in role.fieldpermission_set.all():
        model = fp.model_name.lower()
        if fp.allows_reads:
            if model not in perms:
                perms[model] = []

            perms[model].append({
                'can_write': fp.allows_writes,
                'display_name': fp.display_field_name,
                'field_name': fp.field_name
            })

    return {'geoRev': instance.geo_rev_hash,
            'id': instance.pk,
            'url': instance.url_name,
            'name': instance.name,
            'center': {'lat': center.y,
                       'lng': center.x},
            'fields': perms}
