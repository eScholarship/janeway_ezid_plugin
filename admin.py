from django.contrib import admin
from plugins.ezid.models import RepoEZIDSettings

class RepoEZIDSettingsAdmin(admin.ModelAdmin):
    pass

admin.site.register(RepoEZIDSettings, RepoEZIDSettingsAdmin)
