"""
Janeway Management command for registering DOIs for the EZID plugin
"""

import re
from django.core.management.base import BaseCommand, CommandError
from plugins.ezid.logic import mint_preprint_doi
from repository.models import Repository, Preprint

class Command(BaseCommand):
    """ Takes a preprint ID and mints a DOI via EZID, if the DOI is not yet minted, AND if the preprint is accepted """
    help = "Mints a DOI for the provided preprint ID."

    def add_arguments(self, parser):
        parser.add_argument(
            "short_name", help="`short_name` for the repository containing the preprint for which we need to mint a DOI", type=str)
        parser.add_argument(
            "preprint_id", help="`id` of preprint needing a DOI to be minted", type=str
        )

    def handle(self, *args, **options):

        short_name = options.get('short_name')
        preprint_id = options['preprint_id']

        try:
            repo = Repository.objects.get(short_name=short_name,)
        except Repository.DoesNotExist:
            raise CommandError('No repository found.')

        try:
            preprint = Preprint.objects.get(repository=repo, pk=preprint_id)
        except Preprint.DoesNotExist:
            raise CommandError(f'No preprint found with preprint_id={preprint_id}')

        if preprint.preprint_doi:
            raise CommandError(f"{preprint} already has a DOI, if you wish to update the DOI metadata for this preprint, try the update_ezid_doi command instead.")
        if not preprint.is_published():
            raise CommandError(f"{preprint} is not yet published, cannot mint a DOI for an unpublished preprint.")

        self.stdout.write(f"Attempting to mint a DOI for {preprint}")

        enabled, success, msg = mint_preprint_doi(preprint)

        if not enabled:
            self.stdout.write(self.style.WARNING(msg))
        elif not success:
            self.stdout.write(self.style.ERROR(msg))
        else:
            self.stdout.write(self.style.SUCCESS(f'✅ DOI minted with EZID for {preprint}'))
