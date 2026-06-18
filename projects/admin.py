from django.contrib import admin
from .models import ProfileLog, ProjectProfile

admin.site.register(ProjectProfile)
admin.site.register(ProfileLog)