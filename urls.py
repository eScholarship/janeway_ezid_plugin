from django.urls import re_path

from plugins.ezid import views


urlpatterns = [
    re_path(r'^manager/$', views.ezid_manager, name='ezid_manager'),
]
