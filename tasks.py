from .models import IssueDoiRefreshHistory, ArticleDoiRefreshHistory, TaskStatus
from django.utils import timezone
import time
from utils.logger import get_logger
from .logic import update_journal_doi

logger = get_logger(__name__)

def refresh_issue_doi(issueh_id):
    logger.info(f"Running refresh_issue_doi with issueh_id={issueh_id}")
    """
    Task function that Django-Q can run asynchronously.
    """
    try:
        issueh =  IssueDoiRefreshHistory.objects.get(id=issueh_id)
    except Issue.DoesNotExist:
        return f"Issueh {issueh_id} not found"

    success = False
    result_text = "Simulated DOI refresh result"

    # get the list of articles
    for a in issueh.issue.get_sorted_articles():
        # create article history objects
        x = ArticleDoiRefreshHistory.objects.create(
            article=a,
            issue_hist = issueh,
            date_refresh=timezone.now()
            )
        x.save()
        logger.info(f"Working on article {a}")
        # do work for each article
        isDone, isDoi, msg = update_journal_doi(a)
        logger.info(f"result is isDone={isDone} and isDoi={isDoi}")
        success = isDone and isDoi
        x.result = msg
        x.status = TaskStatus.SUCCESS if success else TaskStatus.FAILURE
        x.date_completed = timezone.now()
        x.save()

        # if failed then break the loop
        if not success:
            break


    issueh.status = TaskStatus.SUCCESS if success else TaskStatus.FAILURE
    issueh.date_completed = timezone.now()
    issueh.save()

    logger.info(f"Completed Running refresh_issue_doi with issue_id={issueh_id}")
    return f"DOI refresh complete for Issue {issueh_id}"
