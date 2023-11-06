"""
Janeway Management command for updating metadata for existing DOIs for the EZID plugin
"""

import re
from urllib.parse import urlparse
from django.core.management.base import BaseCommand, CommandError
from plugins.ezid.logic import update_preprint_doi
from repository.models import Repository, Preprint

class Command(BaseCommand):
    """ Takes a preprint ID or DOI URL and updates the associated DOI metadata via EZID, if the preprint has a DOI, AND if the preprint is accepted """
    help = "Updates the DOI metadata for the provided preprint ID."

    def add_arguments(self, parser):
        parser.add_argument(
            "short_name", help="`short_name` for the repository containing the preprint for which we need to mint a DOI", type=str)
        parser.add_argument(
            "preprint_id", help="`id` of preprint needing a DOI to be minted, OR a complete DOI URL", type=str
        )

    def handle(self, *args, **options):
        short_name = options.get('short_name')
        preprint_id = options.get('preprint_id')

        try:
            repo = Repository.objects.get(short_name=short_name)
        except Repository.DoesNotExist:
            raise CommandError('No repository found.')

        # determine whether we've been given a DOI, and if so, find the matching preprint
        if preprint_id.startswith('http'):
            try:
                # get the preprint that matches the provided preprint_doi(in the preprint_id param)
                doiURL = urlparse(preprint_id)
                # grab just the path from the provided URL, and chop off the first character, BOOM, there's your DOI
                preprint_doi = doiURL.path[1:]
                preprint = Preprint.objects.get(repository=repo, preprint_doi=preprint_doi)
            except Preprint.DoesNotExist:
                raise CommandError('No preprint found with preprint_doi=' + preprint_id)
        else:
            try:
                # get the preprint that matches the provided preprint_id
                preprint = Preprint.objects.get(repository=repo, pk=preprint_id)
            except Preprint.DoesNotExist:
                raise CommandError(f'No preprint found with preprint_id={preprint_id}')

        if not preprint.is_published():
            raise CommandError(f"{preprint} is not yet published, cannot update a DOI for an unpublished preprint.")

        self.stdout.write(f"Attempting to update DOI metadata for preprint {preprint_id}")

        enabled, success, msg = update_preprint_doi(preprint)

        if not enabled:
            self.stdout.write(self.style.WARNING(msg))
        elif not success:
            self.stdout.write(self.style.ERROR(msg))
        else:
            self.stdout.write(self.style.SUCCESS(f'✅ DOI updated with EZID for {preprint}'))
