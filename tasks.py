from django.utils import timezone
from utils.logger import get_logger
from .models import (
    IssueDoiRefreshHistory,
    ArticleDoiRefreshHistory,
    TaskStatus,
)
from .logic import update_journal_doi

logger = get_logger(__name__)
def refresh_issue_doi(issueh_id):
    """
    Task function that Django-Q runs asynchronously to refresh DOIs.
    """
    logger.info(f"Running refresh_issue_doi with issueh_id={issueh_id}")

    try:
        issueh = IssueDoiRefreshHistory.objects.get(id=issueh_id)
    except IssueDoiRefreshHistory.DoesNotExist:
        return f"Issuehistory {issueh_id} not found"

    success = False

    # get the list of articles
    for article in issueh.issue.get_sorted_articles():
        # create article history object
        history = ArticleDoiRefreshHistory.objects.create(
            article=article,
            issue_hist=issueh,
            date_refresh=timezone.now(),
        )
        history.save()

        logger.info(f"Working on article {article}")

        # do work for each article
        is_done, is_doi, message = update_journal_doi(article)
        logger.info(f"result is is_done={is_done} and is_doi={is_doi}")

        success = is_done and is_doi

        history.result = message
        history.status = (
            TaskStatus.SUCCESS if success else TaskStatus.FAILURE
        )
        history.date_completed = timezone.now()
        history.save()

        # if failed then stop
        if not success:
            break

    issueh.status = TaskStatus.SUCCESS if success else TaskStatus.FAILURE
    issueh.date_completed = timezone.now()
    issueh.save()

    logger.info(
        f"Completed Running refresh_issue_doi with issue_id={issueh_id}"
    )
    return f"DOI refresh complete for Issue {issueh_id}"

