# Janeway EZID Plugin

A plugin for [Janeway](https://janeway.systems/), enables minting of DOIs (via [EZID](https://ezid.cdlib.org/)) upon preprint acceptance to a Janeway repository.

The plugin is triggered by the `preprint_publication` event. This event happens immediately after the button to send an acceptance e-mail is clicked.

See also: [janeway_cdl_utils](https://github.com/eScholarship/janeway_cdl_utils)

## Installation

1. Clone this repo into /path/to/janeway/src/plugins/
2. run `pip install xmltodict`
3. run `python src/manage.py install_plugins`
4. Restart your server (Apache, Passenger, etc).
5. configure the plugin (see below)

## Configuration

Configuration for preprints and journals is slightly different because preprints don't support the internal settings
substructure that allows for press-wide defaults.

### Preprints

Each preprint repository needs to have an associated EZID Repo Settings object.

1. Navigate to admin and find the "EZID" section
1. Click "Add" Repo EZID settings
1. Select the appropriate repository and fill in the shoulder, owner, username, password, and endpoint url
1. Save

### Journals

Upon creation of a new press you should setup default values for EZID settings.

1. Go to press manager https://your-domain/manager
1. Click "Edit Journal Default Settings"
1. Search for "ezid"
1. EZID is enabled by default but may be changed press-wide or overriden per journal
1. Fill in valid endpoint_url, username and password

The EZID plugin also uses 3 values from the crossref settings and 1 other DOI-related setting you may choose to set press defaults for these
or set them only on a per journal basis.

1. Crossref depositor name
1. Crossref depositor email
1. Crossref registrant name
1. Article DOI Pattern

To override EZID settings for a particular journal:

1. Go to journal dashboard > "Manager" > "All Settings"
1. Search for "ezid"
1. Create an override for each setting you want to override from the default


## Usage

### Preprints 

When installed and configured, the plugin will mint DOIs and add them to the system-created `preprint_doi` field for each newly-accepted preprint. Errors are logged.

* `register_ezid_doi` *`short_name`* *`preprint_id`* - Mint a new DOI for the given article.  Preprint.preprint_doi should not be set.
* `update_ezid_doi` *`short_name`* *`preprint_id`* - Send and update request for the DOI in Preprint.preprint_doi.

### Journals

When an article is pushed to eScholarship with the janeway to escholarship plugin if the ezid plugin is installed and configured a doi is registered. DOIs are generated based on the Article DOI Pattern setting which is in line with Janeway functionality with Crossref.  There are also management commands that allow you to manually register or update a DOI associated with an article.

* `register_journal_ezid_doi` *`article_id`* - Article should already have an Identifier of type "DOI" assigned to it.  Register it.
* `update_journal_ezid_doi` *`article_id`* - Send an update request for an already registered DOI.  The caller is expected to track the status of the DOI.

## Tests

The test suite can be run in the context of a janeway development environment.  The general command (assuming the plugin is installed in a directory called 'ezid'):

```
python src/manage.py test ezid
```

If you are using a lando development environment:
```
lando manage test ezid
```

Tests cannot be run on stg/prd servers because it requires creating a new database in order to test in a known environment. It can run on dev server and other custom installations. 

## Contributing

1. Fork it!
2. Create your feature branch: `git checkout -b my-new-feature`
3. Commit your changes: `git commit -am 'Add some feature'`
4. Push to the branch: `git push origin my-new-feature`
5. Submit a pull request :D

## License

[BSD 3-Clause](LICENSE)
