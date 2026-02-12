"""
EZID plugin urls module (not sure this is necessary now but perhaps for future use)
"""
from django.urls import re_path

from plugins.ezid import views


urlpatterns = [
    re_path(r'^manager/$', views.ezid_manager, name='ezid_manager'),
    re_path(r'^issues/(?P<issue_id>\d+)/refresh/$', views.trigger_issue_refresh, name='issue_refresh'),
    re_path(r'^refreshall/$', views.trigger_all_refresh, name='all_refresh'),
    re_path(r'^issuehist/(?P<issuehist_id>\d+)/$', views.issue_history, name='issue_history'),
]
