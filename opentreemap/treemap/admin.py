from django.contrib import admin
from django.contrib.auth import models as auth_models
from django.contrib.auth.signals import user_logged_in

import models


user_logged_in.disconnect(auth_models.update_last_login)

admin.site.register(models.Instance)
admin.site.register(models.Species)
admin.site.register(models.Tree)
