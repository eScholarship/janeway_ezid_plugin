"""
EZID plugin models module
"""

from django.db import models
from repository.models import Repository

class RepoEZIDSettings(models.Model):
    """EZID settings for a repsitory"""
    repo = models.OneToOneField(Repository, on_delete=models.CASCADE)
    ezid_shoulder = models.CharField(max_length=50)
    ezid_owner = models.CharField(max_length=50)
    ezid_username = models.CharField(max_length=200)
    ezid_password = models.CharField(max_length=200)
    ezid_endpoint_url = models.URLField(max_length=300)

    def __str__(self):
        return f"EZID settings: {self.repo}"


class TaskStatus(models.IntegerChoices):
    """Task status enum for Bulk Doi updates"""
    PENDING = 1, "Pending"
    IN_PROGRESS = 2, "In Progress"
    SUCCESS = 3, "Success"
    FAILURE = 4, "Failure"
    ABORTED = 5, "Aborted"

class IssueDoiRefreshHistory(models.Model):
    """Issue level history of bulk DOI update"""
    id = models.BigAutoField(primary_key=True)
    date_refresh = models.DateTimeField(auto_now_add=True)
    date_completed = models.DateTimeField(null=True)
    issue = models.ForeignKey('journal.Issue', on_delete=models.CASCADE)

    result = models.TextField(null=True, blank=True)

    status = models.IntegerField(
        choices=TaskStatus.choices,
        default=TaskStatus.PENDING,
    )

    def is_complete(self):
        return self.status not in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS)

    def result_text(self):
        if self.is_complete():
            if self.articledoirefreshhistory_set:
                total_success = (
                    self.articledoirefreshhistory_set
                    .filter(status=TaskStatus.SUCCESS)
                    .count()
                )

                total = (
                    self.articledoirefreshhistory_set
                    .all()
                    .count()
                )

                return (
                    f"Refreshed doi for {total_success} of {total} articles"
                )

            return "No article processed"

        return "Doi refresh in process"

    def __str__(self):
        return self.result_text()

    class Meta:
        ordering = ['-date_refresh']
        verbose_name = "Issue DOI Refresh History"
        verbose_name_plural = "Issue DOI Refresh Histories"

class ArticleDoiRefreshHistory(models.Model):
    """Article level history for bulk DOI update"""
    id = models.BigAutoField(primary_key=True)
    article = models.ForeignKey('submission.Article', on_delete=models.CASCADE)
    date_refresh = models.DateTimeField(auto_now_add=True)
    date_completed = models.DateTimeField(null=True)
    result = models.TextField(null=True, blank=True)

    status = models.IntegerField(
        choices=TaskStatus.choices,
        default=TaskStatus.PENDING,
    )
    issue_hist = models.ForeignKey('IssueDoiRefreshHistory',
                                  blank=True,
                                  null=True,
                                  on_delete=models.CASCADE)

    def __str__(self):
        success = self.get_status_display()
        s = f"{self.article} doi refresh {success} on {self.date_refresh}"
        if self.issue_hist:
            s += f" with {self.issue_hist.issue}"
        return s

    class Meta:
        ordering = ['-date_refresh']
        verbose_name = "Article DOI Refresh History"
        verbose_name_plural = "Article DOI Refresh Histories"
