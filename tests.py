from django.test import TestCase
from django.core.management import call_command
from django.template.loader import render_to_string

from utils.testing import helpers
from utils import setting_handler

from .logic import get_journal_metadata, get_preprint_metadata
from plugins.ezid.models import RepoEZIDSettings

from datetime import datetime

class EZIDJournalTest(TestCase):
    def setUp(self):
        call_command('install_plugins', 'ezid')
        self.user = helpers.create_user("user1@test.edu")        
        self.press = helpers.create_press()
        self.journal, _ = helpers.create_journals()
        self.article = helpers.create_article(self.journal, remote_url="https://test.org/qtXXXXXX")
        setting_handler.save_setting('Identifiers', 'crossref_name', self.journal, "crossref_test")
        setting_handler.save_setting('Identifiers', 'crossref_email', self.journal, "user1@test.edu")
        setting_handler.save_setting('Identifiers', 'crossref_registrant', self.journal, "crossref_registrant")

    def test_journal_metadata(self):
        config, metadata = get_journal_metadata(self.article)
        self.assertEqual(metadata["target_url"], "https://test.org/qtXXXXXX")
        self.assertEqual(metadata["title"], self.article.title)
        self.assertIsNone(metadata["abstract"])
        self.assertIsNone(metadata["doi"])
        self.assertEqual(metadata["depositor_name"], "crossref_test")
        self.assertEqual(metadata["depositor_email"], "user1@test.edu")
        self.assertEqual(metadata["registrant"], "crossref_registrant")

    def test_journal_percent(self):
        self.article.title = "This is the title with a %"
        self.article.save()

        config, metadata = get_journal_metadata(self.article)
        self.assertEqual(metadata["target_url"], "https://test.org/qtXXXXXX")
        self.assertEqual(metadata["title"], "This is the title with a %25")
        self.assertIsNone(metadata["abstract"])
        self.assertIsNone(metadata["doi"])
        self.assertEqual(metadata["depositor_name"], "crossref_test")
        self.assertEqual(metadata["depositor_email"], "user1@test.edu")
        self.assertEqual(metadata["registrant"], "crossref_registrant")

    def test_journal_template(self):
        config, metadata = get_journal_metadata(self.article)
        metadata['now'] = datetime(2023, 1, 1)
        metadata['title'] = "This is the test title"

        cref_xml = render_to_string('ezid/journal_content.xml', metadata)
        self.assertIn(metadata['title'], cref_xml)
        self.assertNotIn(self.article.title, cref_xml)
        self.assertNotIn("abstract", cref_xml)

class EZIDPreprintTest(TestCase):
    def setUp(self):
        call_command('install_plugins', 'ezid')
        #call_command('migrate', 'ezid')
        self.user = helpers.create_user("user1@test.edu", first_name="User", last_name="One")
        self.press = helpers.create_press()
        self.repo, self.subject = helpers.create_repository(self.press, [self.user], [self.user])
        self.preprint = helpers.create_preprint(self.repo, self.user, self.subject)
        settings = RepoEZIDSettings.objects.create(repo=self.repo,
                                                   ezid_shoulder="shoulder",
                                                   ezid_owner="owner",
                                                   ezid_username="username",
                                                   ezid_password="password",
                                                   ezid_endpoint_url="endpoint.org")

    def test_preprint_metadata(self):
        config, metadata = get_preprint_metadata(self.preprint)
        self.assertEqual(metadata["target_url"], "http://localhost/testrepo/repository/view/1/")
        self.assertEqual(metadata["title"], self.preprint.title)
        self.assertEqual(metadata["abstract"], self.preprint.abstract)
        self.assertIsNone(metadata["published_doi"])
        self.assertEqual(metadata["group_title"], self.subject.name)
        self.assertEqual(len(metadata["contributors"]), 1)

    def test_preprint_percent(self):
        self.preprint.title = "This is the title with a %"
        self.preprint.save()
        config, metadata = get_preprint_metadata(self.preprint)
        self.assertEqual(metadata["target_url"], "http://localhost/testrepo/repository/view/2/")
        self.assertEqual(metadata["title"], "This is the title with a %25")
        self.assertEqual(metadata["abstract"], self.preprint.abstract)
        self.assertIsNone(metadata["published_doi"])
        self.assertEqual(metadata["group_title"], self.subject.name)
        self.assertEqual(len(metadata["contributors"]), 1)

    def test_preprint_template(self):
        config, metadata = get_preprint_metadata(self.preprint)
        metadata['now'] = datetime(2023, 1, 1)

        cref_xml = render_to_string('ezid/posted_content.xml', metadata)
        self.assertIn(self.preprint.title, cref_xml)
        self.assertIn(self.preprint.abstract, cref_xml)
        self.assertIn("10.50505/preprint_sample_doi_2", cref_xml)