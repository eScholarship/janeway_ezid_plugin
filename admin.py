"""
EZID plugin admin module
"""
from django.contrib import admin
from plugins.ezid.models import RepoEZIDSettings

admin.site.register(RepoEZIDSettings)
