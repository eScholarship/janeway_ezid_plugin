"""
EZID plugin views module (currently placeholder)
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.utils import timezone
from django_q.tasks import async_task

from journal.models import Issue
from utils.logger import get_logger

from .models import IssueDoiRefreshHistory, ArticleDoiRefreshHistory
from .plugin_settings import PLUGIN_NAME
from .tasks import refresh_issue_doi

logger = get_logger(__name__)

def ezid_manager(request):
    template = 'ezid/manager.html'
    if request.journal:
        issues = Issue.objects.filter(journal=request.journal)
    else:
        logger.error("NO JOURNAL IN REQ")
        issues = Issue.objects.all()

    issueshist = IssueDoiRefreshHistory.objects.filter(issue__in=issues)
    context = {
        'plugin_name': PLUGIN_NAME,
        'issues': issues,
        'issueshist': issueshist
    }
    return render(request, template, context)

@login_required
def trigger_issue_refresh(request, issue_id):
    x = IssueDoiRefreshHistory.objects.create(
        issue_id=issue_id,
        date_refresh=timezone.now()
    )
    async_task(refresh_issue_doi, x.id)
    return redirect("ezid_manager")

def issue_history(request, issuehist_id):
    template = 'ezid/issuehist_details.html'
    articlehist = ArticleDoiRefreshHistory.objects.filter(issue_hist_id=issuehist_id)

    context = {
        'plugin_name': PLUGIN_NAME,
        'ahistory': articlehist
    }
    return render(request, template, context)

@login_required
def trigger_all_refresh(request):
    logger.info("In TRIGGER All")
    issues = None
    if request.journal:
        issues = Issue.objects.filter(journal=request.journal)
    else:
        logger.error("NO JOURNAL IN REQ")

    # create task for all the issues
    for i in issues:
        x = IssueDoiRefreshHistory.objects.create(
            issue=i,
            date_refresh=timezone.now()
        )
        async_task(refresh_issue_doi, x.id)
    return redirect("ezid_manager")
