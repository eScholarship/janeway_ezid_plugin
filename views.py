"""
EZID plugin views module (currently placeholder)
"""
from django.shortcuts import render, redirect
from django.utils import timezone
from .models import IssueDoiRefreshHistory, ArticleDoiRefreshHistory
from .plugin_settings import PLUGIN_NAME
from journal.models import Issue
from submission.models import Article
from utils.logger import get_logger
from django_q.tasks import async_task
from .tasks import refresh_issue_doi

logger = get_logger(__name__)

def ezid_manager(request):
    logger.info("In MANAGER")
    template = 'ezid/manager.html'
    if request.journal:
        logger.error("FOUND JOURNAL")
        issues = Issue.objects.filter(journal=request.journal)
    else:
        logger.error("NO JOURNAL IN REQ")
        issues = Issue.objects.all()
 
    logger.info("The issues are:")
    logger.info(issues)
    context = {
        'plugin_name': PLUGIN_NAME,
        'issues': issues
    }
    return render(request, template, context)

def trigger_issue_refresh(request, issue_id):
    logger.info("In TRIGGER")
    x = IssueDoiRefreshHistory.objects.create(
        issue_id=issue_id,
        date_refresh=timezone.now()
    )
    async_task(refresh_issue_doi, x.id)
    return redirect("ezid_manager")
