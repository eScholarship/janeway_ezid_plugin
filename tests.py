from django.test import TestCase
from django.core.management import call_command
from django.utils import timezone
from django.template.loader import render_to_string

from utils.testing import helpers
from utils import setting_handler

from .logic import get_journal_metadata

class EZIDTest(TestCase):
    def setUp(self):
        call_command('install_plugins', 'ezid')
        #call_command('migrate', 'ezid')
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
        metadata['now'] = timezone.now()
        metadata['title'] = "This is the test title"

        cref_xml = render_to_string('ezid/journal_content.xml', metadata)
        print(cref_xml)
        self.assertIn(metadata['title'], cref_xml)
        self.assertNotIn(self.article.title, cref_xml)
        self.assertNotIn("abstract", cref_xml)


