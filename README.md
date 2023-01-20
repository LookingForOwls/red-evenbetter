## Introduction

This is a quick fork of https://gitlab.com/stormgit/red-better to resolve some issues and make a few minor changes. 

The source of both forks is https://github.com/iw00t/REDBetter

* Now works with Python 3.9+
* Configs stored in `.redactedbetter` folder in code directory instead of `~/`  
* Changed hashcheck to use imdl (Intermodal)
* Fixed issues with script incorrectly exiting, multiprocess and spectral generation

Code is provided as-is, please be cautious when running it. 

---
REDBetter is a script which searches your torrent download directory for any FLAC torrents which do not have transcodes, then automatically transcodes and uploads the torrents to redacted.ch.

## Differences
This project differs from its parent fork because it allows the user to verify spectrals of source FLAC files before transcoding & uploading them. This is meant to reduce the number of lossy transcodes that inadvertently slip through (because some lossy files might be erroneously labeled as FLAC).

Additionally, this fork only uses the API for site access and so does not run afoul of the rule that states that HTML scraping is not allowed.

Finally, this fork performs automatic hashcheck verification on the source FLAC files before transcoding them in case files are missing/corrupted.

This fork effectively aims to make the process result in fewer errors but increases the amount of work the user must go through to upload transcodes.

## Dependencies

* Python 3.7 or newer
* `mktorrent>=1.1`
* `lame`, `sox` and `flac`
* [Poetry](https://python-poetry.org/)
* [Intermodal](https://github.com/casey/intermodal)

## Installation Instructions

#### 1. Install Python >= 3.7
* Can either install directly from [here](https://www.python.org/downloads/)
* Alternatively, install [PyEnv](https://github.com/pyenv/pyenv) and use that to install the desired version of Python (recommended, but may require more permissions)

#### 2. Install [Poetry](https://python-poetry.org/)
* Install instructions found at [this link](https://python-poetry.org/docs/)

#### 3. Install `mktorrent`

`mktorrent` version 1.1 or higher is needed. Both Brew and Ubuntu repositories include version 1.1 now.  If you need to build from source you can with the following steps for Linux systems:

~~~~
$> git clone git@github.com:Rudde/mktorrent.git
$> cd mktorrent
$> make && sudo make install
~~~~

If you are on a seedbox and you lack the privileges to install packages, you are best off contacting your seedbox provider and asking them to install the listed packages.

#### 4. Install REDBetter

* Use Poetry to install REDBetter by running
~~~~
git clone https://gitlab.com/stormgit/red-better
cd red-better
poetry install
~~~~


#### 5. Install `lame`, `sox` and `flac`

These should all be available on your package manager of choice:
  * Debian: `sudo apt-get install lame sox flac`
  * Ubuntu: `sudo apt install lame sox flac`
  * macOS: `brew install lame sox flac`


#### 6. (Optional) Install Intermodal (hashcheck)

This program requires the `idml` to be available on your path in order to run hash check verification. This verification can be skipped (not recommended) by providing the `--skip-hashcheck` option.
You can read the install instructions [here](https://github.com/casey/intermodal). 

Installing somewhere like `/usr/local/bin` ensures that it is in your path.
`curl --proto '=https' --tlsv1.2 -sSf https://imdl.io/install.sh | bash -s -- --to /usr/local/bin`

You can verify its working by simply running: `imdl`

## Configuration
Run REDBetter by running `poetry run better`

You will receive a notification stating that you should edit the configuration file located at:

    .redactedbetter/config

Open this file in your preferred text editor, and configure as desired. The options are as follows:
* `username`: Your redacted.ch username.
* `password`: Your redacted.ch password.
* `session_cookie`: Path to a valid session cookie
* `api_key`: API key that REDBetter can use
* `data_dir`: The directory where your torrent downloads are stored.
* `output_dir`: The directory where the transcoded torrent files will be stored. If left blank, it will use the value of `data_dir`.
* `torrent_dir`: The directory where the generated `.torrent` files are stored.
* `spectral_dir`: The directory where temporary spectral images will be written to for user verification
* `formats`: A comma space (`, `) separated list of formats you'd like to transcode to. By default, this will be `flac, v0, 320`. `flac` is included because REDBetter supports converting 24-bit FLAC to 16-bit FLAC. Note that `v2` is not included deliberately - v0 torrents trump v2 torrents per redacted rules.

It is required that you use the API key method of authentication unless you choose to skip hashcheck verification.

## Usage
~~~~
usage: redactedbetter [-h] [-s] [-j THREADS] [--config CONFIG] [--cache CACHE] [-p PAGE_SIZE]
                      [--skip-missing] [-r [RETRY [RETRY ...]]] [--skip-spectral] [--skip-hashcheck]
                      [release_urls [release_urls ...]]

positional arguments:
  release_urls          the URL where the release is located (default: None)

optional arguments:
  -h, --help            show this help message and exit
  -s, --single          only add one format per release (useful for getting unique groups) (default:
                        False)
  -j THREADS, --threads THREADS
                        number of threads to use when transcoding (default: 7)
  --config CONFIG       the location of the configuration file (default:
                        ~/.redactedbetter/config)
  --cache CACHE         the location of the cache (default: ~/.redactedbetter/cache)
  -p PAGE_SIZE, --page-size PAGE_SIZE
                        Number of snatched results to fetch at once (default: 2000)
  --skip-missing        Skip snatches that have missing data directories (default: False)
  -r [RETRY [RETRY ...]], --retry [RETRY [RETRY ...]]
                        Retries certain classes of previous exit statuses (default: [])
  --skip-spectral       Skips spectrograph verification (default: False)
  --skip-hashcheck      Skip source file integrity verification (default: False)

~~~~

### Examples

To transcode and upload everything you have in your download directory with manual spectral verification and hashcheck verification (recommended):

    $> poetry run better
    
To transcode and upload everything you have in your download directory with no verification (not recommended):

    $> poetry run better --skip-spectral --skip-hashcheck

To transcode and upload a specific release (provided you have already downloaded the FLAC and it is located in your `data_dir`):

    $> poetry run better http://redacted.ch/torrents.php?id=1000\&torrentid=1000000

REDBetter caches the results of your transcodes, and will skip any transcodes it believes it's already finished. This makes subsequent runs much faster than the first, especially with large download directories. However, if you do run into errors when running the script, sometimes you will find that the cache thinks the torrent it crashed on previously was uploaded - so it skips it. A solution would be to manually specify the release as mentioned above. If you have multiple issues like this, you can remove the cache:

    $> rm .redactedbetter/cache

Beware though, this will cause the script to re-check every download as it does on the first run.

Alternatively, the cache remembers the exit mode for each torrent that is added to it. If you want to re-run all torrents that failed the spectral or hashcheck tests, for example, you can run

    $> poetry run better --retry spectrograms hashcheck
    
The `--retry` flag accepts a space-delimited list of modes to retry. Acceptable modes are one of: `missing`, `multichannel`, `broken_tags`, `spectrograms`, `24bit`, `hashcheck`, `formats`, `done`.

## Bugs and feature requests

If you have any issues using the script, or would like to suggest a feature, please use the issue tracker but do not expect a quick response.
