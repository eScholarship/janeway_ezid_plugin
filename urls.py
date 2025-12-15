"""
EZID plugin urls module (not sure this is necessary now but perhaps for future use)
"""
from django.urls import re_path

from plugins.ezid import views


urlpatterns = [
    re_path(r'^manager/$', views.ezid_manager, name='ezid_manager'),
]
