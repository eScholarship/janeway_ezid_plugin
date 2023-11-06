from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from submission.models import Article
from plugins.ezid import logic

class Command(BaseCommand):
    """Takes a journal article ID and registers the DOI via EZID"""
    help = "Takes a journal article ID and registers the DOI via EZID"

    def add_arguments(self, parser):
        parser.add_argument(
            "article_id", help="`id` of article to register", type=int
        )

    def handle(self, *args, **options):
        article_id = options['article_id']

        if not Article.objects.filter(pk=article_id).exists():
            raise CommandError(f"Article {article_id} does not exist.")

        article = Article.objects.get(id=article_id)
        self.stdout.write(f"Attempting to register DOI for {article}")

        enabled, success, msg = logic.register_journal_doi(article)

        if not enabled:
            self.stdout.write(self.style.WARNING(msg))
        elif not success:
            self.stdout.write(self.style.ERROR(msg))
        else:
            self.stdout.write(self.style.SUCCESS(f'✅ DOI registered with EZID for {article}'))


