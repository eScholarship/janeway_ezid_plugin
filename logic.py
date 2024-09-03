"""
This module contains the logic for the EZID plugin for Janeway
"""

__copyright__ = "Copyright (c) 2020, The Regents of the University of California"
__author__ = "Hardy Pottinger, Mahjabeen Yucekul & Esther Verreau"
__license__ = "BSD 3-Clause"
__maintainer__ = "California Digital Library"

import re
from urllib.parse import quote
import urllib.request as urlreq

from django.core.validators import URLValidator, ValidationError
from django.conf import settings
from django.utils import timezone
from django.template.loader import render_to_string
from utils.logger import get_logger
from utils import setting_handler
from identifiers import logic as id_logic

from django.contrib import messages

from plugins.ezid.models import RepoEZIDSettings

logger = get_logger(__name__)

def get_valid_orcid(orcid):
    ''' Determine whether the given input_string is a valid ORCID '''
    if not orcid:
        return None
    if not orcid.startswith('http'):
        orcid = f'https://orcid.org/{orcid}'

    regex = re.compile('https?://orcid.org/[0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9]{3}[X0-9]{1}$')
    match = regex.match(str(orcid))
    return orcid if bool(match) else None

def normalize_author_metadata(preprint_authors):
    ''' returns a list of authors in dictionary format using a list of author objects '''
    #example: {"given_name": "Hardy", "surname": "Pottinger", "ORCID": "https://orcid.org/0000-0001-8549-9354"},
    author_list = []
    for author in preprint_authors:
        new_author = dict()
        contributor = author.account
        if contributor is None:
            logger.warn('No preprint author account found')
        elif not contributor.first_name and not contributor.last_name:
            logger.warn('No names given for preprint author')
        else:
            if contributor.last_name:
                new_author['given_name'] = contributor.first_name
                new_author['surname'] = contributor.last_name
            else:
                new_author['surname'] = contributor.first_name
                logger.info(f'No last_name found for {contributor} using first_name')

            orcid = get_valid_orcid(contributor.orcid)
            if orcid:
                new_author['ORCID'] = orcid
            else:
                logger.warning(f'Invalid ORCID {contributor.orcid} for {contributor} omitted')

            author_list.append(new_author)
    return author_list

def escape_str(s):
    # To prevent percent-decode error from EZID
    return s.replace('%','%25') if s else s

def encode(txt):
    ''' encode a text string '''
    return quote(txt, ":/")

def get_date_dict(d):
    if d:
        return {'month': d.month, 'day': d.day, 'year': d.year}
    return None

def is_valid_issn(issn):
    if not issn or issn == "0000-0000":
        return False

    r = re.compile("^[0-9]{4}-[0-9]{3}[0-9X]$")

    return re.search(r, issn)

def is_valid_url(url):
    try:
        validator = URLValidator()
        validator(url)
        return True
    except ValidationError:
        return False

class EzidHTTPErrorProcessor(urlreq.HTTPErrorProcessor):
    ''' Error Processor, required to let 201 responses pass '''
    def http_response(self, request, response):
        if response.code == 201:
            my_return = response
        else:
            my_return = urlreq.HTTPErrorProcessor.http_response(self, request, response)
        return my_return
    https_response = http_response

def send_request(method, path, data, username, password, endpoint_url):
    ''' sends a request to EZID '''
    request_url = f"{endpoint_url}/{path}"

    opener = urlreq.build_opener(EzidHTTPErrorProcessor())
    ezid_handler = urlreq.HTTPBasicAuthHandler()
    ezid_handler.add_password("EZID", endpoint_url, username, password)
    opener.add_handler(ezid_handler)

    request = urlreq.Request(request_url)
    request.get_method = lambda: method
    request.add_header("Content-Type", "text/plain; charset=UTF-8")
    request.data = data.encode("UTF-8")

    try:
        connection = opener.open(request)
        response = connection.read()
        return response.decode("UTF-8")

    except urlreq.HTTPError as ezid_error:
        if ezid_error.fp is not None:
            response = ezid_error.fp.read().decode("utf-8")
            if not response.endswith("\n"):
                response += "\n"
        return response

def prepare_payload(ezid_metadata, template, target_url, owner):
    # normalize xml output by collapsing all whitespace to a single space
    _RE_COMBINE_WHITESPACE = re.compile(r"\s+")
    metadata = _RE_COMBINE_WHITESPACE.sub(" ", render_to_string(template, ezid_metadata)).strip()
    payload = f"crossref: {metadata}\n_crossref: yes\n_profile: crossref\n_target: {target_url}\n_owner: {owner}"
    return payload

def process_ezid_result(item, action, ezid_result, request):
    if isinstance(ezid_result, str):
        if ezid_result.startswith('success:'):
            doi = re.search("doi:([0-9A-Z./]+)", ezid_result).group(1)
            msg = f'DOI {action} success: {doi}'
            logger.debug(msg)
            if request: messages.success(request, msg)
            return doi
        else:
            msg = f'EZID DOI {action} failed for {item}: {ezid_result}'
            logger.error(msg)
            if request: messages.error(request, msg)
    else:
        logger.error(f'EZID DOI {action} failed for {item}')
        if ezid_result != None:
            logger.error(ezid_result.msg)

    return None

def get_preprint_metadata(preprint):
    ezid_metadata = {'now': timezone.now(),
                     'target_url': preprint.url,
                     'group_title': preprint.subject.values_list()[0][2],
                     'contributors': normalize_author_metadata(preprint.preprintauthor_set.all()),
                     'title': escape_str(preprint.title),
                     'published_date': get_date_dict(preprint.date_published),
                     'accepted_date': get_date_dict(preprint.date_accepted),
                     'abstract': escape_str(preprint.abstract),
                     'license': preprint.license.url if preprint.license else None}

    if preprint.doi:
        if is_valid_url(preprint.doi):
            ezid_metadata['published_doi'] = preprint.doi
        else:
            logger.error(f'{preprint} has an invalid Published DOI: {preprint.doi}')

    return ezid_metadata

def preprint_doi(preprint, action, request):
    if RepoEZIDSettings.objects.filter(repo=preprint.repository).exists():
        ezid_metadata = get_preprint_metadata(preprint)
        ezid_settings = RepoEZIDSettings.objects.get(repo=preprint.repository)

        shoulder = ezid_settings.ezid_shoulder
        username = ezid_settings.ezid_username
        password  = ezid_settings.ezid_password
        endpoint_url = ezid_settings.ezid_endpoint_url
        owner = ezid_settings.ezid_owner

        payload = prepare_payload(ezid_metadata, 'ezid/posted_content.xml', ezid_metadata['target_url'], owner)

        if action == "update":
            path = f'id/doi:{encode(preprint.preprint_doi)}'
        else:
            path = f'shoulder/{encode(shoulder)}'

        ezid_result = send_request("POST", path, payload, username, password, endpoint_url)
        doi = process_ezid_result(preprint, action, ezid_result, request)
        if doi:
            preprint.preprint_doi = doi
            preprint.save()
        return True, (doi != None), ezid_result
    else:
        return False, False, f"EZID not enabled for {preprint.repository}"

def update_preprint_doi(preprint, request=None):
    if not preprint.preprint_doi:
        msg = f'{preprint} does not have a DOI'
        logger.info(msg)
        return True, False, msg
    else:
        return preprint_doi(preprint, "update", request)

def mint_preprint_doi(preprint, request=None):
    if preprint.preprint_doi:
        msg = f'{preprint} already has a DOI: {preprint.preprint_doi}'
        logger.info(msg)
        return True, False, msg
    else:
        return preprint_doi(preprint, "mint", request)

def preprint_publication(**kwargs):
    ''' hook script for the preprint_publication event '''
    logger.debug('>>> preprint_publication called, mint an EZID DOI...')
    preprint = kwargs.get('preprint')
    request = kwargs.get('request')
    enabled, success, msg = mint_preprint_doi(preprint, request=request)

def get_setting(name, journal):
    return setting_handler.get_setting('plugin:ezid', name, journal).processed_value

def get_journal_metadata(article):
    # get remote_url from articles
    itemId = 'qt'+ article.remote_url[-8:]
    # build content download url
    download_url = f'https://escholarship.org/content/{itemId}/{itemId}.pdf'
    return {'now': timezone.now(),
            'target_url': article.remote_url,
            'article': article,
            'title': escape_str(article.title),
            'abstract': escape_str(article.abstract),
            'doi': article.get_doi(),
            'depositor_name': setting_handler.get_setting('Identifiers', 'crossref_name', article.journal).processed_value,
            'depositor_email': setting_handler.get_setting('Identifiers', 'crossref_email', article.journal).processed_value,
            'registrant': setting_handler.get_setting('Identifiers', 'crossref_registrant', article.journal).processed_value,
            'download_url': download_url,}

def get_journal_template(journal):
    return 'ezid/book_chapter.xml' if get_setting('ezid_book_chapter', journal) else 'ezid/journal_content.xml'

def journal_article_doi(article, action, request):
    if get_setting('ezid_plugin_enable', article.journal):
        if not is_valid_issn(article.journal.issn) and not is_valid_url(article.journal.issn):
            msg = f"Invalid ISSN {article.journal.issn} for {article.journal}"
            if request: messages.error(request, msg)
            return True, False, msg

        ezid_metadata = get_journal_metadata(article)
        if not ezid_metadata["doi"] and action != "mint":
            msg = f"{article} not assigned a DOI"
            if request: messages.error(request, msg)
            return True, False, msg
        template = get_journal_template(article.journal)

        if action == "update":
            ezid_metadata['update_id'] = ezid_metadata["doi"]
            method = "POST"
        else:
            method = "PUT"

        username = get_setting('ezid_plugin_username', article.journal)
        password = get_setting('ezid_plugin_password', article.journal)
        endpoint_url = get_setting('ezid_plugin_endpoint_url', article.journal)
        owner = setting_handler.get_setting('Identifiers', 'crossref_registrant', article.journal).processed_value

        if not username or not password or not endpoint_url or not owner:
            msg = f"EZID not fully configured for {article.journal}"
            if request: messages.error(request, msg)
            return True, False, msg

        path = f'id/doi:{encode(ezid_metadata["doi"])}'
        payload = prepare_payload(ezid_metadata, template, ezid_metadata["target_url"], owner)
        ezid_result = send_request(method, path, payload, username, password, endpoint_url)
        doi = process_ezid_result(article, action, ezid_result, request)
        return True, (doi != None), ezid_result
    else:
        msg = f"EZID not enabled for {article.journal}"
        if request: messages.warning(request, msg)
        return False, False, msg

def update_journal_doi(article, request=None):
    return journal_article_doi(article, "update", request)

def register_journal_doi(article, request=None):
    return journal_article_doi(article, "register", request)

def assign_article_doi(**kwargs):
    article = kwargs.get('article')
    if get_setting('ezid_plugin_enable', article.journal):
        if not article.get_doi():
            id = id_logic.generate_crossref_doi_with_pattern(article)
