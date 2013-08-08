from django.contrib import admin
from django.contrib.auth import models as auth_models
from django.contrib.auth.signals import user_logged_in

import models
import udf

user_logged_in.disconnect(auth_models.update_last_login)

admin.site.register(models.Instance)
admin.site.register(models.FieldPermission)
admin.site.register(models.Role)
admin.site.register(models.BenefitCurrencyConversion)
admin.site.register(models.Species)
admin.site.register(models.Tree)
admin.site.register(models.User)

admin.site.register(udf.UserDefinedFieldDefinition)
