"""
Tasks for refreshing DOIs via Django‑Q.

This module defines asynchronous task functions used to update
journal and article DOIs and record their refresh history.
"""
from django.utils import timezone
from utils.logger import get_logger
from .models import (
    IssueDoiRefreshHistory,
    ArticleDoiRefreshHistory,
    TaskStatus,
)
from .logic import update_journal_doi

logger = get_logger(__name__)

def is_refresh_okay(article):
    """
    Determines whether it is okay refresh DOI.
    """
    if article.stage != "Published":
        return False, f'Skipping. Expected stage Published, actual {article.stage}'
    # TBD waiting for more input on date updated check
    return True, "Okay to proceed"

def refresh_article_doi(article, issueh):
    """
    Refreshes one article DOI.
    """
    # create article history object
    history = ArticleDoiRefreshHistory.objects.create(
        article=article,
        issue_hist=issueh,
        date_refresh=timezone.now(),
    )
    history.save()
    success = True # The article skipped are not counted towards failures
    is_okay, message = is_refresh_okay(article)
    if is_okay:
        # skip if the article is not published or updated after publishing
        logger.info(f"Working on article {article}")

        # do work for each article
        is_done, is_doi, message = update_journal_doi(article)
        logger.info(f"result is is_done={is_done} and is_doi={is_doi}")

        success = is_done and is_doi

        history.status = (
            TaskStatus.SUCCESS if success else TaskStatus.FAILURE
        )
    else:
        history.status = TaskStatus.ABORTED

    history.result = message
    history.date_completed = timezone.now()
    history.save()
    return success

def refresh_issue_doi(issueh_id):
    """
    Task function that Django-Q runs asynchronously to refresh DOIs.
    """
    logger.info(f"Running refresh_issue_doi with issueh_id={issueh_id}")

    try:
        issueh = IssueDoiRefreshHistory.objects.get(id=issueh_id)
    except IssueDoiRefreshHistory.DoesNotExist:
        return f"Issuehistory {issueh_id} not found"

    num_failed = 0

    success = TRUE # if no eligible article to publish
    # get the list of articles
    for article in issueh.issue.get_sorted_articles():
        success = refresh_article_doi(article, issueh)
        num_failed += int(not success)

        # if failed three times then stop
        if num_failed > 3:
            break

    issueh.status = TaskStatus.SUCCESS if success else TaskStatus.FAILURE
    issueh.date_completed = timezone.now()
    issueh.save()

    logger.info(
        f"Completed Running refresh_issue_doi with issue_id={issueh_id}"
    )
    return f"DOI refresh complete for Issue {issueh_id}"
