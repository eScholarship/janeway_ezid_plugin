from django.test import TestCase
from django.core.management import call_command
from django.template.loader import render_to_string

from utils.testing import helpers
from utils import setting_handler

import plugins.ezid.logic as logic

from plugins.ezid.models import RepoEZIDSettings

from datetime import datetime
from django.utils import timezone

import mock
from django.core.cache import cache
from freezegun import freeze_time

from identifiers.models import Identifier

FROZEN_DATETIME = timezone.make_aware(timezone.datetime(2023, 1, 1, 0, 0, 0))

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
        setting_handler.save_setting('plugin:ezid', 'ezid_plugin_endpoint_url', self.journal, "https://test.org/")
        setting_handler.save_setting('plugin:ezid', 'ezid_plugin_username', self.journal, "username")
        setting_handler.save_setting('plugin:ezid', 'ezid_plugin_password', self.journal, "password")

    def test_journal_metadata(self):
        metadata = logic.get_journal_metadata(self.article)
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

        metadata = logic.get_journal_metadata(self.article)
        self.assertEqual(metadata["target_url"], "https://test.org/qtXXXXXX")
        self.assertEqual(metadata["title"], "This is the title with a %25")
        self.assertIsNone(metadata["abstract"])
        self.assertIsNone(metadata["doi"])
        self.assertEqual(metadata["depositor_name"], "crossref_test")
        self.assertEqual(metadata["depositor_email"], "user1@test.edu")
        self.assertEqual(metadata["registrant"], "crossref_registrant")

    def test_journal_template(self):
        metadata = logic.get_journal_metadata(self.article)
        metadata['now'] = datetime(2023, 1, 1)
        metadata['title'] = "This is the test title"

        cref_xml = render_to_string('ezid/journal_content.xml', metadata)
        self.assertIn(metadata['title'], cref_xml)
        self.assertNotIn(self.article.title, cref_xml)
        self.assertNotIn("abstract", cref_xml)

    @freeze_time(FROZEN_DATETIME)
    @mock.patch('plugins.ezid.logic.send_request', return_value="success: doi:10.9999/TEST | ark:/b9999/test")
    def test_register_doi(self, mock_send):
        setting_handler.save_setting('general', 'journal_issn', self.article.journal, "1111-1111")
        # if we don't clear the cache we get the old, invalid ISSN
        cache.clear()
        doi = Identifier.objects.create(id_type="doi", identifier="10.9999/TEST", article=self.article)

        path = "id/doi:10.9999/TEST"
        payload = f'crossref: <?xml version="1.0" encoding="UTF-8"?><doi_batch xmlns="http://www.crossref.org/schema/5.3.1"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="5.3.1"    xsi:schemaLocation="http://www.crossref.org/schema/5.3.1 http://www.crossref.org/schemas/crossref5.3.1.xsd">    <head>        <doi_batch_id>JournalOne_20230101_{self.article.pk}</doi_batch_id>        <timestamp>1672531200</timestamp>        <depositor>            <depositor_name>crossref_test</depositor_name>            <email_address>user1@test.edu</email_address>        </depositor>        <registrant>crossref_registrant</registrant>    </head>    <body>        <journal>            <journal_metadata>                <full_title>Journal One</full_title>                <abbrev_title>Journal One</abbrev_title>                                                <issn media_type="electronic">1111-1111</issn>                            </journal_metadata>                        <journal_article publication_type="full_text">                <titles>                    <title>Test Article from Utils Testing Helpers</title>                </titles>                                                                  <doi_data>                                                                  <doi>10.9999/TEST</doi>                                                              <resource>https://test.org/qtXXXXXX</resource>                </doi_data>            </journal_article>        </journal>    </body></doi_batch>\n_crossref: yes\n_profile: crossref\n_target: https://test.org/qtXXXXXX\n_owner: crossref_registrant'
        username = logic.get_setting('ezid_plugin_username', self.article.journal)
        password = logic.get_setting('ezid_plugin_password', self.article.journal)
        endpoint_url = logic.get_setting('ezid_plugin_endpoint_url', self.article.journal)

        enabled, success, msg = logic.register_journal_doi(self.article)

        mock_send.assert_called_once_with("PUT", path, payload, username, password, endpoint_url)

        self.assertTrue(enabled)
        self.assertTrue(success)
        self.assertEqual(msg, "success: doi:10.9999/TEST | ark:/b9999/test")

    @freeze_time(FROZEN_DATETIME)
    @mock.patch('plugins.ezid.logic.send_request', return_value="success: doi:10.9999/TEST | ark:/b9999/test")
    def test_update_doi(self, mock_send):
        setting_handler.save_setting('general', 'journal_issn', self.article.journal, "1111-1111")
        # if we don't clear the cache we get the old, invalid ISSN
        cache.clear()
        doi = Identifier.objects.create(id_type="doi", identifier="10.9999/TEST", article=self.article)

        path = "id/doi:10.9999/TEST"
        payload = f'crossref: <?xml version="1.0" encoding="UTF-8"?><doi_batch xmlns="http://www.crossref.org/schema/5.3.1"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="5.3.1"    xsi:schemaLocation="http://www.crossref.org/schema/5.3.1 http://www.crossref.org/schemas/crossref5.3.1.xsd">    <head>        <doi_batch_id>JournalOne_20230101_{self.article.pk}</doi_batch_id>        <timestamp>1672531200</timestamp>        <depositor>            <depositor_name>crossref_test</depositor_name>            <email_address>user1@test.edu</email_address>        </depositor>        <registrant>crossref_registrant</registrant>    </head>    <body>        <journal>            <journal_metadata>                <full_title>Journal One</full_title>                <abbrev_title>Journal One</abbrev_title>                                                <issn media_type="electronic">1111-1111</issn>                            </journal_metadata>                        <journal_article publication_type="full_text">                <titles>                    <title>Test Article from Utils Testing Helpers</title>                </titles>                                                                  <doi_data>                                                                  <doi>10.9999/TEST</doi>                                                              <resource>https://test.org/qtXXXXXX</resource>                </doi_data>            </journal_article>        </journal>    </body></doi_batch>\n_crossref: yes\n_profile: crossref\n_target: https://test.org/qtXXXXXX\n_owner: crossref_registrant'
        username = logic.get_setting('ezid_plugin_username', self.article.journal)
        password = logic.get_setting('ezid_plugin_password', self.article.journal)
        endpoint_url = logic.get_setting('ezid_plugin_endpoint_url', self.article.journal)

        enabled, success, msg = logic.update_journal_doi(self.article)

        mock_send.assert_called_once_with("POST", path, payload, username, password, endpoint_url)

        self.assertTrue(enabled)
        self.assertTrue(success)
        self.assertEqual(msg, "success: doi:10.9999/TEST | ark:/b9999/test")

    def test_no_issn(self):
        enabled, success, msg = logic.register_journal_doi(self.article)

        self.assertTrue(enabled)
        self.assertFalse(success)
        self.assertEqual(msg, f"Invalid ISSN {self.article.journal.issn} for {self.article.journal}")

    def test_disabled(self):
        setting_handler.save_setting('plugin:ezid', 'ezid_plugin_enable', self.article.journal, False)
        enabled, success, msg = logic.register_journal_doi(self.article)

        self.assertFalse(enabled)

class EZIDPreprintTest(TestCase):
    def setUp(self):
        call_command('install_plugins', 'ezid')
        #call_command('migrate', 'ezid')
        self.user = helpers.create_user("user1@test.edu", first_name="User", last_name="One")
        self.press = helpers.create_press()
        self.repo, self.subject = helpers.create_repository(self.press, [self.user], [self.user])
        self.preprint = helpers.create_preprint(self.repo, self.user, self.subject)
        s = RepoEZIDSettings.objects.create(repo=self.repo,
                                            ezid_shoulder="shoulder",
                                            ezid_owner="owner",
                                            ezid_username="username",
                                            ezid_password="password",
                                            ezid_endpoint_url="endpoint.org")

    def test_preprint_metadata(self):
        metadata = logic.get_preprint_metadata(self.preprint)
        self.assertEqual(metadata["target_url"], f"http://localhost/testrepo/repository/view/{self.preprint.pk}/")
        self.assertEqual(metadata["title"], self.preprint.title)
        self.assertEqual(metadata["abstract"], self.preprint.abstract)
        self.assertFalse("published_doi" in metadata)
        self.assertEqual(metadata["group_title"], self.subject.name)
        self.assertEqual(len(metadata["contributors"]), 1)

    def test_preprint_percent(self):
        self.preprint.title = "This is the title with a %"
        self.preprint.save()
        metadata = logic.get_preprint_metadata(self.preprint)
        self.assertEqual(metadata["target_url"], f"http://localhost/testrepo/repository/view/{self.preprint.pk}/")
        self.assertEqual(metadata["title"], "This is the title with a %25")
        self.assertEqual(metadata["abstract"], self.preprint.abstract)
        self.assertFalse("published_doi" in metadata)
        self.assertEqual(metadata["group_title"], self.subject.name)
        self.assertEqual(len(metadata["contributors"]), 1)

    def test_preprint_template(self):
        metadata = logic.get_preprint_metadata(self.preprint)
        metadata['now'] = datetime(2023, 1, 1)

        cref_xml = render_to_string('ezid/posted_content.xml', metadata)
        self.assertIn(self.preprint.title, cref_xml)
        self.assertIn(self.preprint.abstract, cref_xml)
        self.assertIn("10.50505/preprint_sample_doi_2", cref_xml)

    def test_update_no_doi(self):
        enabled, success, msg = logic.update_preprint_doi(self.preprint)

        self.assertTrue(enabled)
        self.assertFalse(success)
        self.assertEqual(msg, f"{self.preprint} does not have a DOI")

    def test_mint_with_doi(self):
        self.preprint.preprint_doi = "10.9999/TEST"

        enabled, success, msg = logic.mint_preprint_doi(self.preprint)

        self.assertTrue(enabled)
        self.assertFalse(success)
        self.assertEqual(msg, f"{self.preprint} already has a DOI: {self.preprint.preprint_doi}")

    @freeze_time(FROZEN_DATETIME)
    @mock.patch('plugins.ezid.logic.send_request', return_value="success: doi:10.9999/TEST | ark:/b9999/test")
    def test_preprint_update(self, mock_send):
        self.preprint.preprint_doi = "10.9999/TEST"
        path = "id/doi:10.9999/TEST"
        payload = f'crossref: <?xml version="1.0"?><posted_content xmlns="http://www.crossref.org/schema/4.4.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:jats="http://www.ncbi.nlm.nih.gov/JATS1" xsi:schemaLocation="http://www.crossref.org/schema/4.4.0 http://www.crossref.org/schema/deposit/crossref4.4.0.xsd" type="preprint">  <group_title>Repo Subject</group_title>    <contributors>            <person_name contributor_role="author" sequence="first">          <given_name>User</given_name>          <surname>One</surname>                </person_name>        </contributors>    <titles>    <title>This is a Test Preprint</title>  </titles>  <posted_date>    <month>1</month>    <day>1</day>    <year>2023</year>  </posted_date>  <acceptance_date>    <month>1</month>    <day>1</day>    <year>2023</year>  </acceptance_date>    <jats:abstract>    <jats:p>This is a fake abstract.</jats:p>  </jats:abstract>        <!-- placeholder DOI, will be overwritten when DOI is minted -->  <doi_data>    <doi>10.50505/preprint_sample_doi_2</doi>    <resource>https://escholarship.org/</resource>  </doi_data>  </posted_content>\n_crossref: yes\n_profile: crossref\n_target: {self.preprint.url}\n_owner: owner'

        print(self.preprint.pk)

        enabled, success, msg = logic.update_preprint_doi(self.preprint)

        s = RepoEZIDSettings.objects.get(repo=self.repo)

        mock_send.assert_called_once_with("POST", path, payload, s.ezid_username, s.ezid_password, s.ezid_endpoint_url)

        self.assertTrue(enabled)
        self.assertTrue(success)
        self.assertEqual(msg, "success: doi:10.9999/TEST | ark:/b9999/test")

    @freeze_time(FROZEN_DATETIME)
    @mock.patch('plugins.ezid.logic.send_request', return_value="success: doi:10.9999/TEST | ark:/b9999/test")
    def test_preprint_mint(self, mock_send):
        path = "shoulder/shoulder"
        payload = f'crossref: <?xml version="1.0"?><posted_content xmlns="http://www.crossref.org/schema/4.4.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:jats="http://www.ncbi.nlm.nih.gov/JATS1" xsi:schemaLocation="http://www.crossref.org/schema/4.4.0 http://www.crossref.org/schema/deposit/crossref4.4.0.xsd" type="preprint">  <group_title>Repo Subject</group_title>    <contributors>            <person_name contributor_role="author" sequence="first">          <given_name>User</given_name>          <surname>One</surname>                </person_name>        </contributors>    <titles>    <title>This is a Test Preprint</title>  </titles>  <posted_date>    <month>1</month>    <day>1</day>    <year>2023</year>  </posted_date>  <acceptance_date>    <month>1</month>    <day>1</day>    <year>2023</year>  </acceptance_date>    <jats:abstract>    <jats:p>This is a fake abstract.</jats:p>  </jats:abstract>        <!-- placeholder DOI, will be overwritten when DOI is minted -->  <doi_data>    <doi>10.50505/preprint_sample_doi_2</doi>    <resource>https://escholarship.org/</resource>  </doi_data>  </posted_content>\n_crossref: yes\n_profile: crossref\n_target: {self.preprint.url}\n_owner: owner'

        enabled, success, msg = logic.mint_preprint_doi(self.preprint)

        s = RepoEZIDSettings.objects.get(repo=self.repo)

        mock_send.assert_called_once_with("POST", path, payload, s.ezid_username, s.ezid_password, s.ezid_endpoint_url)

        self.assertTrue(enabled)
        self.assertTrue(success)
        self.assertEqual(msg, "success: doi:10.9999/TEST | ark:/b9999/test")
