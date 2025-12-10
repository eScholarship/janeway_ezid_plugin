import re
from datetime import datetime
from freezegun import freeze_time
import mock

from django.test import TestCase
from django.core.management import call_command
from django.template.loader import render_to_string
from django.utils import timezone
from django.core.cache import cache

from identifiers.models import Identifier
from repository.models import Repository, PreprintVersion
from submission.models import Licence
from utils.testing import helpers
from utils import setting_handler, logger

from plugins.ezid import logic
from plugins.ezid.models import RepoEZIDSettings

FROZEN_DATETIME = timezone.make_aware(timezone.datetime(2023, 1, 1, 0, 0, 0))

JOURNAL_XML = \
"""
<?xml version="1.0" encoding="UTF-8"?>
<doi_batch xmlns="http://www.crossref.org/schema/5.3.1"
           xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
           version="5.3.1"
           xsi:schemaLocation="http://www.crossref.org/schema/5.3.1
                               http://www.crossref.org/schemas/crossref5.3.1.xsd">
    <head>
        <doi_batch_id>JournalOne_20230101_{article_id}</doi_batch_id>
        <timestamp>1672531200</timestamp>
        <depositor>
            <depositor_name>crossref_test</depositor_name>
            <email_address>user1@test.edu</email_address>
        </depositor>
        <registrant>crossref_registrant</registrant>
    </head>
    <body>
        <journal>
            <journal_metadata>
                <full_title>Journal One</full_title>
                <abbrev_title>Journal One</abbrev_title>
                <issn media_type="electronic">1111-1111</issn>
            </journal_metadata>
            <journal_article publication_type="full_text">
                <titles>
                    <title>Test Article from Utils Testing Helpers</title>
                </titles>
                <contributors>
                    <person_name contributor_role="author" sequence="first">
                        <given_name>Author A</given_name>
                        <surname>User</surname>
                        <ORCID>https://orcid.org/1234-5678-9012-345X</ORCID>
                    </person_name>
                </contributors>
                {license_xml}
                <doi_data>
                    <doi>10.9999/TEST</doi>
                    <resource>{target_url}</resource>
                    {download_xml}
                </doi_data>
            </journal_article>
        </journal>
    </body>
</doi_batch>
"""

DOWNLOAD_XML = \
"""
<collection property="text-mining">
    <item>
        <resource mime_type="application/pdf">
            https://escholarship.org/content/qtqtXXXXXX/qtqtXXXXXX.pdf
        </resource>
    </item>
</collection>
"""

BOOK_XML = \
"""
<?xml version="1.0" encoding="UTF-8"?>
<doi_batch xmlns="http://www.crossref.org/schema/5.3.1"
           xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
           version="5.3.1"
           xsi:schemaLocation="http://www.crossref.org/schema/5.3.1
                               http://www.crossref.org/schemas/crossref5.3.1.xsd">
    <head>
        <doi_batch_id>JournalOne_20230101_{article_id}</doi_batch_id>
        <timestamp>1672531200</timestamp>
        <depositor>
            <depositor_name>crossref_test</depositor_name>
            <email_address>user1@test.edu</email_address>
        </depositor>
        <registrant>crossref_registrant</registrant>
    </head>
    <body>
        <book book_type="edited_book">
            <book_series_metadata language="en">
                <series_metadata>
                    <titles>
                        <title>Journal One</title>
                    </titles>
                    <issn>1111-1111</issn>
                </series_metadata>
                <titles>
                    <title>Journal One</title>
                </titles>
                <publication_date media_type="online"> 
                    <year></year>
                </publication_date>
                <noisbn reason="archive_volume"/>
                <publisher>
                    <publisher_name>eScholarship Publishing</publisher_name>
                    <publisher_place>Oakland,CA</publisher_place>
                </publisher>
            </book_series_metadata>
            <content_item component_type="chapter" publication_type="full_text" language="en">
                <contributors>
                    <person_name contributor_role="author" sequence="first">
                        <given_name>Author A</given_name>
                        <surname>User</surname>
                        <ORCID>https://orcid.org/1234-5678-9012-345X</ORCID>
                    </person_name>
                </contributors>
                <titles>
                    <title>Test Article from Utils Testing Helpers</title>
                </titles>
                <publication_date media_type="online">
                    <month></month>
                    <day></day>
                    <year></year>
                </publication_date>
                {license_xml}
                <doi_data>
                    <doi>10.9999/TEST</doi>
                    <resource>{target_url}</resource>
                    {download_xml}
                </doi_data>
            </content_item>
        </book>
    </body>
</doi_batch>
"""

PREPRINT_XML = """
<?xml version="1.0"?>
<posted_content xmlns="http://www.crossref.org/schema/4.4.0"
                xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                xmlns:jats="http://www.ncbi.nlm.nih.gov/JATS1"
                xsi:schemaLocation="http://www.crossref.org/schema/4.4.0 http://www.crossref.org/schema/deposit/crossref4.4.0.xsd"
                type="preprint"> 
    <group_title>Repo Subject</group_title>
    <contributors>
        <person_name contributor_role="author" sequence="first">
            <given_name>User</given_name>
            <surname>One</surname>
            <ORCID>https://orcid.org/0000-0001-2345-6789</ORCID>
        </person_name>
    </contributors>
    <titles>
        <title>This is a Test Preprint</title>
    </titles>
    <posted_date>
        <month>1</month>
        <day>1</day>
        <year>2023</year>
    </posted_date>
    <acceptance_date>
        <month>1</month>
        <day>1</day>
        <year>2023</year>
    </acceptance_date>
    <jats:abstract>
        <jats:p>This is a fake abstract.</jats:p>
    </jats:abstract>
    <!-- placeholder DOI, will be overwritten when DOI is minted -->
    <doi_data>
        <doi>10.50505/preprint_sample_doi_2</doi>
        <resource>https://escholarship.org/</resource>
        <collection property="text-mining">
            <item>
                <resource mime_type="application/pdf">
                    http://localhost/testrepo{}
                </resource>
            </item>
        </collection>
    </doi_data>
</posted_content>
"""

PAYLOAD = 'crossref: {}\n_crossref: yes\n_profile: crossref\n_target: {}\n_owner: {}'

EZID_PATH = 'id/doi:10.9999/TEST'
EZID_USERNAME = 'username'
EZID_ENDPOINT_URL = 'https://test.org/'
EZID_PASSWORD = 'password'

class EZIDJournalTest(TestCase):
    def setUp(self):
        call_command('install_plugins', 'ezid')
        self.user = helpers.create_user("user1@test.edu")
        self.press = helpers.create_press()
        self.journal, _ = helpers.create_journals()
        self.article = helpers.create_article(
            self.journal,
            with_author=True,
            remote_url="https://test.org/qtXXXXXX"
        )
        self.license = Licence(name="license_test", short_name="lt", url="https://test.cc.org")
        self.license.save()
        isettings = {"crossref_name": "crossref_test",
                     "crossref_email": "user1@test.edu",
                     "crossref_registrant": "crossref_registrant"}
        self.save_settings('Identifiers', self.journal, isettings)
        esettings = {
            "ezid_plugin_endpoint_url": "https://test.org/",
            "ezid_plugin_username":  "username",
            "ezid_plugin_password": "password"
        }
        self.save_settings('plugin:ezid', self.journal, esettings)

        setting_handler.save_setting('general', 'journal_issn', self.article.journal, "1111-1111")
        # if we don't clear the cache we get the old, invalid ISSN
        cache.clear()
        _doi = Identifier.objects.create(
            id_type="doi",
            identifier="10.9999/TEST",
            article=self.article
        )

    def save_settings(self, prefix, journal, settings_dict):
        for key, value in settings_dict.items():
            setting_handler.save_setting(prefix, key, journal, value)

    def test_journal_metadata(self):
        metadata = logic.get_journal_metadata(self.article)
        self.assertEqual(metadata["target_url"], "https://test.org/qtXXXXXX")
        self.assertEqual(metadata["title"], self.article.title)
        self.assertIsNone(metadata["abstract"])
        self.assertEqual(metadata["doi"], "10.9999/TEST")
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
        self.assertEqual(metadata["doi"], "10.9999/TEST")
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

    def strip_payload(self, s):
        return re.compile(r"\s+").sub(" ", s).strip()

    def get_payload(self, xml_tmpl, **kwargs):
        target_url = kwargs.pop("target_url", "https://test.org/qtXXXXXX")
        owner = kwargs.pop("owner", "crossref_registrant")
        args = {
            "article_id": self.article.pk,
            "license_xml": kwargs.pop("license_xml", ""),
            "target_url": target_url, 
            "download_xml": kwargs.pop("download_xml", DOWNLOAD_XML),           
        }
        return PAYLOAD.format(
            self.strip_payload(xml_tmpl.format(**args)),
            target_url,
            owner
        )

    @freeze_time(FROZEN_DATETIME)
    @mock.patch('plugins.ezid.logic.send_request',
                return_value="success: doi:10.9999/TEST | ark:/b9999/test")
    def test_register_doi(self, mock_send):
        payload = self.get_payload(JOURNAL_XML)

        enabled, success, msg = logic.register_journal_doi(self.article)

        mock_send.assert_called_once_with(
            "PUT",
            EZID_PATH,
            payload,
            EZID_USERNAME,
            EZID_PASSWORD,
            EZID_ENDPOINT_URL
        )

        self.assertTrue(enabled)
        self.assertTrue(success)
        self.assertEqual(msg, "success: doi:10.9999/TEST | ark:/b9999/test")

    @freeze_time(FROZEN_DATETIME)
    @mock.patch('plugins.ezid.logic.send_request',
                return_value="success: doi:10.9999/TEST | ark:/b9999/test")
    def test_update_doi(self, mock_send):
        payload = self.get_payload(JOURNAL_XML)

        enabled, success, msg = logic.update_journal_doi(self.article)

        mock_send.assert_called_once_with(
            "POST",
            EZID_PATH,
            payload,
            EZID_USERNAME,
            EZID_PASSWORD,
            EZID_ENDPOINT_URL
        )

        self.assertTrue(enabled)
        self.assertTrue(success)
        self.assertEqual(msg, "success: doi:10.9999/TEST | ark:/b9999/test")

    def test_no_issn(self):
        setting_handler.save_setting('general', 'journal_issn', self.article.journal, "")
        cache.clear()
        enabled, success, msg = logic.register_journal_doi(self.article)

        self.assertTrue(enabled)
        self.assertFalse(success)
        self.assertEqual(
            msg,
            f"Invalid ISSN {self.article.journal.issn} for {self.article.journal}"
        )

    def test_disabled(self):
        setting_handler.save_setting(
            'plugin:ezid',
            'ezid_plugin_enable',
            self.article.journal, False
        )
        enabled, _success, _msg = logic.register_journal_doi(self.article)

        self.assertFalse(enabled)

    @freeze_time(FROZEN_DATETIME)
    @mock.patch('plugins.ezid.logic.send_request',
                return_value="success: doi:10.9999/TEST | ark:/b9999/test")
    def test_register_bookchapter_doi(self, mock_send):
        setting_handler.save_setting('plugin:ezid', 'ezid_book_chapter', self.journal, "1")
        cache.clear()
        payload = self.get_payload(BOOK_XML)

        enabled, success, msg = logic.register_journal_doi(self.article)

        mock_send.assert_called_once_with(
            "PUT",
            EZID_PATH,
            payload,
            EZID_USERNAME,
            EZID_PASSWORD,
            EZID_ENDPOINT_URL
        )

        self.assertTrue(enabled)
        self.assertTrue(success)
        self.assertEqual(msg, "success: doi:10.9999/TEST | ark:/b9999/test")


    @freeze_time(FROZEN_DATETIME)
    @mock.patch('plugins.ezid.logic.send_request',
                return_value="success: doi:10.9999/TEST | ark:/b9999/test")
    def test_update_bookchapter_doi(self, mock_send):
        setting_handler.save_setting('plugin:ezid', 'ezid_book_chapter', self.journal, "1")
        cache.clear()
        payload = self.get_payload(BOOK_XML)

        enabled, success, msg = logic.update_journal_doi(self.article)

        mock_send.assert_called_once_with(
            "POST",
            EZID_PATH,
            payload,
            EZID_USERNAME,
            EZID_PASSWORD,
            EZID_ENDPOINT_URL
        )

        self.assertTrue(enabled)
        self.assertTrue(success)
        self.assertEqual(msg, "success: doi:10.9999/TEST | ark:/b9999/test")

    @freeze_time(FROZEN_DATETIME)
    @mock.patch('plugins.ezid.logic.send_request',
                return_value="success: doi:10.9999/TEST | ark:/b9999/test")
    def test_with_license_doi(self, mock_send):
        self.article.license = self.license
        self.article.save()
        license_xml = """<program xmlns="http://www.crossref.org/AccessIndicators.xsd">
                            <free_to_read/> <license_ref>https://test.cc.org</license_ref>
                        </program>"""
        payload = self.get_payload(JOURNAL_XML, license_xml=license_xml)

        enabled, success, msg = logic.update_journal_doi(self.article)

        mock_send.assert_called_once_with(
            "POST",
            EZID_PATH,
            payload,
            EZID_USERNAME,
            EZID_PASSWORD,
            EZID_ENDPOINT_URL
        )

        self.assertTrue(enabled)
        self.assertTrue(success)
        self.assertEqual(msg, "success: doi:10.9999/TEST | ark:/b9999/test")

    # test without remote url
    @freeze_time(FROZEN_DATETIME)
    @mock.patch('plugins.ezid.logic.send_request',
                return_value="success: doi:10.9999/TEST | ark:/b9999/test")
    def test_without_remoteurl_doi(self, mock_send):
        self.article.remote_url = None
        self.article.save()
        payload = self.get_payload(
            JOURNAL_XML,
            target_url=self.article.url,
            download_xml=""
        )

        enabled, success, msg = logic.update_journal_doi(self.article)

        mock_send.assert_called_once_with(
            "POST",
            EZID_PATH,
            payload,
            EZID_USERNAME,
            EZID_PASSWORD,
            EZID_ENDPOINT_URL
        )

        self.assertTrue(enabled)
        self.assertTrue(success)
        self.assertEqual(msg, "success: doi:10.9999/TEST | ark:/b9999/test")


    @freeze_time(FROZEN_DATETIME)
    @mock.patch('plugins.ezid.logic.send_request',
                return_value="success: doi:10.9999/TEST | ark:/b9999/test")
    def test_with_empty_license_doi(self, mock_send):
        self.license.url = '  '
        self.license.save()
        self.article.license = self.license
        self.article.save()
        payload = self.get_payload(JOURNAL_XML)

        enabled, success, msg = logic.update_journal_doi(self.article)

        mock_send.assert_called_once_with(
            "POST",
            EZID_PATH,
            payload,
            EZID_USERNAME,
            EZID_PASSWORD,
            EZID_ENDPOINT_URL
        )

        self.assertTrue(enabled)
        self.assertTrue(success)
        self.assertEqual(msg, "success: doi:10.9999/TEST | ark:/b9999/test")

    @freeze_time(FROZEN_DATETIME)
    @mock.patch('plugins.ezid.logic.send_request',
                return_value="success: doi:10.9999/TEST | ark:/b9999/test")
    def test_orcid_url(self, mock_send):
        author = self.article.authors.all()[0]
        author.orcid = "https://orcid.org/1234-5678-9012-345X"
        author.save()

        payload = self.get_payload(JOURNAL_XML)

        enabled, success, msg = logic.update_journal_doi(self.article)

        mock_send.assert_called_once_with(
            "POST",
            EZID_PATH,
            payload,
            EZID_USERNAME,
            EZID_PASSWORD,
            EZID_ENDPOINT_URL
        )

        self.assertTrue(enabled)
        self.assertTrue(success)
        self.assertEqual(msg, "success: doi:10.9999/TEST | ark:/b9999/test")


class EZIDPreprintTest(TestCase):
    def setUp(self):
        self.user = helpers.create_user(
            "user1@test.edu",
            first_name="User",
            last_name="One",
            orcid="0000-0001-2345-6789"
        )
        self.press = helpers.create_press()
        self.repo, self.subject = helpers.create_repository(
            self.press,
            [self.user],
            [self.user]
        )
        self.preprint = helpers.create_preprint(self.repo, self.user, self.subject)
        PreprintVersion.objects.create(preprint=self.preprint,
                                       version=1,
                                       file=self.preprint.submission_file)
        self.preprint.save()
        self.settings = RepoEZIDSettings.objects.create(
            repo=self.repo,
            ezid_shoulder="shoulder",
            ezid_owner="owner",
            ezid_username="username",
            ezid_password="password",
            ezid_endpoint_url="endpoint.org"
        )

    def strip_payload(self, s):
        return re.compile(r"\s+").sub(" ", s).strip()

    def get_payload(self, owner="owner"):
        xml = PREPRINT_XML.format(
            self.preprint.current_version.file.download_url()
        )
        return PAYLOAD.format(
            self.strip_payload(xml),
            self.preprint.url,
            owner
        )

    def test_preprint_metadata(self):
        metadata = logic.get_preprint_metadata(self.preprint)
        self.assertEqual(metadata["target_url"], self.preprint.url)
        self.assertEqual(metadata["title"], self.preprint.title)
        self.assertEqual(metadata["abstract"], self.preprint.abstract)
        self.assertFalse("published_doi" in metadata)
        self.assertEqual(metadata["group_title"], self.subject.name)
        self.assertEqual(len(metadata["contributors"]), 1)

    def test_preprint_percent(self):
        self.preprint.title = "This is the title with a %"
        self.preprint.save()
        metadata = logic.get_preprint_metadata(self.preprint)
        self.assertEqual(metadata["target_url"], self.preprint.url)
        self.assertEqual(metadata["title"], "This is the title with a %25")
        self.assertEqual(metadata["abstract"], self.preprint.abstract)
        self.assertFalse("published_doi" in metadata)
        self.assertEqual(metadata["group_title"], self.subject.name)
        self.assertEqual(len(metadata["contributors"]), 1)

    def test_published_doi(self):
        self.preprint.doi = "https://doi.org/10.15697/TEST"
        self.preprint.save()

        metadata = logic.get_preprint_metadata(self.preprint)
        self.assertEqual(metadata["target_url"], self.preprint.url)
        self.assertEqual(metadata["title"], self.preprint.title)
        self.assertEqual(metadata["abstract"], self.preprint.abstract)
        self.assertEqual(metadata["published_doi"], self.preprint.doi)
        self.assertEqual(metadata["group_title"], self.subject.name)
        self.assertEqual(len(metadata["contributors"]), 1)

    @mock.patch.object(logger.PrefixedLoggerAdapter, 'error')
    def test_bad_published_doi(self, error_mock):
        self.preprint.doi = "10.15697/TEST"
        self.preprint.save()
        metadata = logic.get_preprint_metadata(self.preprint)
        self.assertEqual(metadata["target_url"], self.preprint.url)
        self.assertEqual(metadata["title"], self.preprint.title)
        self.assertEqual(metadata["abstract"], self.preprint.abstract)
        self.assertFalse("published_doi" in metadata)
        self.assertEqual(metadata["group_title"], self.subject.name)
        self.assertEqual(len(metadata["contributors"]), 1)
        log_msg = f'{self.preprint} has an invalid Published DOI: {self.preprint.doi}'
        error_mock.assert_called_once_with(log_msg)

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

    def test_disabled(self):
        repo2 = Repository.objects.create(press=self.press,
                                          name='Test Repository 2',
                                          short_name='testrepo2',
                                          object_name='Preprint',
                                          object_name_plural='Preprints',
                                          publisher='Test Publisher',
                                          live=True,
                                          domain="repo2.domain.com",)

        preprint2 = helpers.create_preprint(repo2, self.user, self.subject)

        enabled, _success, _msg = logic.mint_preprint_doi(preprint2)

        self.assertFalse(enabled)

    @freeze_time(FROZEN_DATETIME)
    @mock.patch('plugins.ezid.logic.send_request',
                return_value="success: doi:10.9999/TEST | ark:/b9999/test")
    def test_preprint_update(self, mock_send):
        self.preprint.preprint_doi = "10.9999/TEST"
        path = "id/doi:10.9999/TEST"
        payload = self.get_payload()

        enabled, success, msg = logic.update_preprint_doi(self.preprint)

        mock_send.assert_called_once_with(
            "POST",
            path,
            payload,
            self.settings.ezid_username,
            self.settings.ezid_password,
            self.settings.ezid_endpoint_url
        )

        self.assertTrue(enabled)
        self.assertTrue(success)
        self.assertEqual(msg, "success: doi:10.9999/TEST | ark:/b9999/test")
        self.assertEqual(self.preprint.preprint_doi, "10.9999/TEST")

    @freeze_time(FROZEN_DATETIME)
    @mock.patch('plugins.ezid.logic.send_request',
                return_value="success: doi:10.9999/TEST | ark:/b9999/test")
    def test_preprint_mint(self, mock_send):
        path = "shoulder/shoulder"
        payload = self.get_payload()
        enabled, success, msg = logic.mint_preprint_doi(self.preprint)

        mock_send.assert_called_once_with(
            "POST",
            path,
            payload,
            self.settings.ezid_username,
            self.settings.ezid_password,
            self.settings.ezid_endpoint_url
        )

        self.assertTrue(enabled)
        self.assertTrue(success)
        self.assertEqual(msg, "success: doi:10.9999/TEST | ark:/b9999/test")
        self.assertEqual(self.preprint.preprint_doi, "10.9999/TEST")

    @freeze_time(FROZEN_DATETIME)
    @mock.patch('plugins.ezid.logic.send_request',
                return_value="success: doi:10.9999/TEST | ark:/b9999/test")
    def test_preprint_orcid_url(self, mock_send):
        self.user.orcid = "https://orcid.org/0000-0001-2345-6789"
        self.user.save()
        path = "shoulder/shoulder"
        payload = self.get_payload()
        enabled, success, msg = logic.mint_preprint_doi(self.preprint)

        mock_send.assert_called_once_with(
            "POST",
            path,
            payload,
            self.settings.ezid_username,
            self.settings.ezid_password,
            self.settings.ezid_endpoint_url
        )

        self.assertTrue(enabled)
        self.assertTrue(success)
        self.assertEqual(msg, "success: doi:10.9999/TEST | ark:/b9999/test")
        self.assertEqual(self.preprint.preprint_doi, "10.9999/TEST")
