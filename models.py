"""
EZID plugin models module
"""

from django.db import models
from journal.models import Journal
from submission.models import Article
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
    PENDING = 1, "Pending"
    IN_PROGRESS = 2, "In Progress"
    SUCCESS = 3, "Success"
    FAILURE = 4, "Failure"

class IssueDoiRefreshHistory(models.Model):
    id = models.BigAutoField(primary_key=True)
    date_refresh = models.DateTimeField(auto_now_add=True)
    date_completed = models.DateTimeField(null=True)
    issue = models.ForeignKey('journal.Issue', on_delete=models.CASCADE)

    result = models.TextField(null=True, blank=True)

    status = models.IntegerField(
        choices=TaskStatus.choices,
        default=TaskStatus.PENDING,
    )
    def result_text(self):
        if self.status != TaskStatus.PENDING or self.status != TaskStatus.IN_PROGRESS:
            total_success = self.ArticleDoiRefreshHistory_set.filter(status=TaskStatus.SUCCESS).count()
            total = self.ArticleDoiRefreshHistory_set.all().count()
            return f"Successfully refreshed doi for {total_success} of {total} articles"

        return "Doi refresh in process"

    def __str__(self):
        success = self.get_status_display() # "successful" if self.success else "failed"
        s = f"{self.issue} doi refresh {success} on {self.date_refresh}"
        if self.issue_pub:
            s += f" with {self.issue_pub.issue}"
        return s

    class Meta:
        ordering = ['-date_refresh']

class ArticleDoiRefreshHistory(models.Model):
    id = models.BigAutoField(primary_key=True)
    article = models.ForeignKey('submission.Article', on_delete=models.CASCADE)
    date_refresh = models.DateTimeField(auto_now_add=True)
    date_completed = models.DateTimeField(null=True)
    result = models.TextField(null=True, blank=True)

    status = models.IntegerField(
        choices=TaskStatus.choices,
        default=TaskStatus.PENDING,
    )
    issue_pub = models.ForeignKey('IssueDoiRefreshHistory',
                                  blank=True,
                                  null=True,
                                  on_delete=models.CASCADE)

    def __str__(self):
        success = self.get_status_display() #"successful" if self.success else "failed"
        s = f"{self.article} doi refresh {success} on {self.date_refresh}"
        if self.issue_pub:
            s += f" with {self.issue_pub.issue}"
        return s

    class Meta:
        ordering = ['-date_refresh']
