

def export_enabled_for(instance, user):
    if instance.feature_enabled('exports'):
        if instance.non_admins_can_export:
            return True
        else:
            if user.is_authenticated:
                iuser = user.get_instance_user(instance)
                return iuser is not None and iuser.admin
            else:
                # AnonymousUser can not export
                # if non_admins_can_export is False
                return False
    else:
        # No one can export if the feature is not enabled
        return False
