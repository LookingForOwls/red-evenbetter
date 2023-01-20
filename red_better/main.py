from configparser import ConfigParser
import argparse
from pathlib import Path
from typing import List, Optional

import os
import shutil
import sys
import tempfile
from urllib import parse as urlparse
from multiprocessing import cpu_count

from red_better import transcode, tagging, redactedapi
from red_better.cache import Cache
from red_better.spectrograms import make_spectrograms
from red_better.hashcheck import run_hashcheck


def create_description(torrent, flac_dir, format, permalink) -> str:
    # Create an example command to document the transcode process.
    cmds = transcode.transcode_commands(format,
                                        transcode.needs_resampling(flac_dir),
                                        transcode.resample_rate(flac_dir),
            'input.flac', 'output' + transcode.encoders[format]['ext'])

    description = '\n'.join([
        f'Transcode of [url={permalink}]{permalink}[/url]\n',
        'Transcode process:',
        f'[code]{" | ".join(cmds)}[/code]\n'
        'Created using [url=https://gitlab.com/stormgit/red-better]REDBetter (glasslake fork)[/url]'
        ])
    return description


def formats_needed(group, torrent, supported_formats) -> List[str]:
    if torrent['format'] != 'FLAC':
        return []
    if torrent['reported']:
        print('Torrent has been reported. Skipping.')
        return []
    same_group = lambda t: t['media'] == torrent['media'] and\
                           t['remasterYear'] == torrent['remasterYear'] and\
                           t['remasterTitle'] == torrent['remasterTitle'] and\
                           t['remasterRecordLabel'] == torrent['remasterRecordLabel'] and\
                           t['remasterCatalogueNumber'] == torrent['remasterCatalogueNumber']

    others = list(filter(same_group, group['torrents']))
    current_formats = set((t['format'], t['encoding']) for t in others)
    missing_formats = [format for format, details in [(f, redactedapi.formats[f]) for f in supported_formats]\
                           if (details['format'], details['encoding']) not in current_formats]
    allowed_formats = redactedapi.allowed_transcodes(torrent)
    return [format for format in missing_formats if format in allowed_formats]


def border_msg(msg):
    width = 0
    for line in msg.splitlines():
        length = len(line)
        if length > width:
            width = length

    dash = "-" * (width - 1)
    return "+{dash}+\n{msg}\n+{dash}+".format(dash=dash,msg=msg)


def parse_config(config_path: Path) -> Optional[ConfigParser]:
    config = ConfigParser()
    if not config_path.is_file():
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config.add_section('redacted')
        config.set('redacted', 'username', '')
        config.set('redacted', 'password', '')
        config.set('redacted', 'session_cookie', '')
        config.set('redacted', 'api_key', '')
        config.set('redacted', 'data_dir', '')
        config.set('redacted', 'output_dir', '')
        config.set('redacted', 'torrent_dir', '')
        config.set('redacted', 'spectral_dir', '')
        config.set('redacted', 'formats', 'flac, v0, 320')
        config.set('redacted', 'media', ', '.join(redactedapi.lossless_media))
        config.set('redacted', '24bit_behaviour', 'yes')
        config.set('redacted', 'piece_length', '18')
        with open(str(config_path), 'w') as config_file:
            config.write(config_file)
        print(f'No config file found. Please edit the blank one created '
              f'at {config_path}')
        return None

    try:
        config.read(config_path)
    except Exception as e:
        print(f'Error reading config file from {config_path}')
        raise e

    return config


def validate_formats(formats: List[str]) -> None:
    allowed_formats = redactedapi.formats.keys()
    for format_name in formats:
        if format_name not in allowed_formats:
            raise ValueError(f'Format {format_name} is not one '
                             f'of {allowed_formats}')


def validate_spectrograms(flac_dir_str: str, spectral_dir_str: str, threads: int) -> bool:
    flac_dir = Path(flac_dir_str)
    spectrogram_dir = Path(spectral_dir_str)
    if spectrogram_dir.exists():
        shutil.rmtree(spectrogram_dir)
    spectrogram_dir.mkdir()
    if not make_spectrograms(flac_dir, spectrogram_dir, threads):
        return False
    print(f'Spectrograms written to {spectrogram_dir}. Are they acceptable?')
    response = get_input(['y', 'n'])
    if response == 'n':
        print(f'Spectrograms rejected. Skipping.')
        return False
    return True


def get_input(choices: List[str]) -> str:
    choice_set = set(choices)
    response = ''
    while response not in choice_set:
        response = input(f'Please enter one of {", ".join(choices)}: ').lower()
    return response


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        prog='redactedbetter'
    )
    parser.add_argument(
        'release_urls',
        nargs='*',
        help='the URL where the release is located'
    )
    parser.add_argument(
        '-s',
        '--single',
        action='store_true',
        help='only add one format per release (useful for getting unique groups)'
    )
    parser.add_argument(
        '-j',
        '--threads',
        type=int,
        help='number of threads to use when transcoding',
        default=max(cpu_count() - 1, 1)
    )
    parser.add_argument(
        '--config',
        help='the location of the configuration file',
        default=Path('./.redactedbetter/config').expanduser()
    )
    parser.add_argument(
        '--cache',
        help='the location of the cache',
        default=Path('./.redactedbetter/cache').expanduser()
    )
    parser.add_argument(
        '-p',
        '--page-size',
        type=int,
        help='Number of snatched results to fetch at once',
        default=2000
    )
    parser.add_argument(
        '--skip-missing',
        action='store_true',
        default=False,
        help='Skip snatches that have missing data directories'
    )
    parser.add_argument(
        '-r',
        '--retry',
        nargs='*',
        default=[],
        help='Retries certain classes of previous exit statuses'
    )
    parser.add_argument(
        '--skip-spectral',
        action='store_true',
        default=False,
        help='Skips spectrograph verification'
    )
    parser.add_argument(
        '--skip-hashcheck',
        action='store_true',
        default=False,
        help='Skip source file integrity verification'
    )

    args = parser.parse_args()

    config_path = Path(args.config)
    config = parse_config(config_path)
    if config is None:
        sys.exit(2)

    username = config.get('redacted', 'username', fallback=None)
    password = config.get('redacted', 'password', fallback=None)
    api_key = config.get('redacted', 'api_key', fallback=None)
    try:
        session_cookie = Path(config.get('redacted', 'session_cookie')).expanduser()
    except ConfigParser.NoOptionError:
        session_cookie = None
    data_dir = Path(config.get('redacted', 'data_dir')).expanduser()
    output_dir = Path(
        config.get('redacted', 'output_dir', fallback=data_dir)
    ).expanduser()
    torrent_dir = Path(config.get('redacted', 'torrent_dir')).expanduser()
    supported_formats = [format.strip().upper() for format in config.get('redacted', 'formats').split(',')]
    validate_formats(supported_formats)

    print('Logging in to RED...')
    api = redactedapi.RedactedAPI(
        args.page_size,
        username,
        password,
        session_cookie,
        api_key,
    )

    cache_path = Path(args.cache)
    cache = Cache.from_file(cache_path)
    spectral_dir = Path(config.get('redacted', 'spectral_dir', fallback='/tmp/spectrograms'))
    spectral_dir.mkdir(parents=True, exist_ok=True)

    print('Searching for transcode candidates...')
    if args.release_urls:
        print('You supplied one or more release URLs, ignoring your configuration\'s media types.')
        candidates = [(int(query['id']), int(query['torrentid'])) for query in\
                [dict(urlparse.parse_qsl(urlparse.urlparse(url).query)) for url in args.release_urls]]
    else:
        candidates = api.snatched()
    retry_modes = set(args.retry)

    for groupid, torrentid in candidates:
        if torrentid in cache.ids:
            retry = False
            if cache.ids[torrentid] in retry_modes:
                retry = True
            if not retry:
                print(f'Torrent ID {torrentid} present in cache. Skipping.')
                continue
        group = api.request('torrentgroup', id=groupid)
        if group != None:
            torrent = [t for t in group['torrents'] if t['id'] == torrentid][0]

            if len(group['group']['musicInfo']['artists']) > 1:
                artist = "Various Artists"
            else:
                artist = group['group']['musicInfo']['artists'][0]['name']

            year = str(torrent['remasterYear'])
            if year == "0":
                year = str(group['group']['year'])
            
            title = group['group']['name']
            print(f'\nTorrent ID: {torrentid} - {artist} - {title}')

            if not torrent['filePath']:
                flac_file = os.path.join(data_dir, redactedapi.unescape(torrent['fileList']).split('{{{')[0])
                if not Path(flac_file).exists():
                    print("Path not found - skipping: %s" % flac_file)
                    cache.add(torrentid, 'missing', cache_path)
                    continue
                flac_dir = os.path.join(data_dir, "%s (%s) [FLAC]" % (
                    redactedapi.unescape(group['group']['name']), group['group']['year']))
                if not os.path.exists(flac_dir):
                    os.makedirs(flac_dir)
                shutil.copy(flac_file, flac_dir)
            else:
                flac_dir = os.path.join(data_dir, redactedapi.unescape(torrent['filePath']))

            if transcode.is_multichannel(flac_dir):
                print("This is a multichannel release, which is unsupported - skipping")
                cache.add(torrentid, 'multichannel', cache_path)
                continue

            has_valid_dir = True
            while not Path(flac_dir).exists():
                if args.skip_missing:
                    print(f'Could not find flac dir {flac_dir}. Skipping.')
                    has_valid_dir = False
                    break
                else:
                    print(f'Could not find flac dir {flac_dir}')
                alternative_file_path_exists = ""
                while (alternative_file_path_exists.lower() != "y") and (alternative_file_path_exists.lower() != "n"):
                    alternative_file_path_exists = input("Do you wish to provide an alternative file path? (y/n): ")

                if alternative_file_path_exists.lower() == "y":
                    flac_dir = input("Alternative file path: ")
                else:
                    print("Skipping: %s" % flac_dir)
                    has_valid_dir = False
                    break

            if not has_valid_dir:
                cache.add(torrentid, 'missing', cache_path)
                continue

            needed = formats_needed(group, torrent, supported_formats)

            if len(needed) == 0:
                cache.add(torrentid, 'formats', cache_path)
                print(' -> No formats needed. Skipping.')
                continue
            else:
                print(" -> Formats needed: %s" % ', '.join(needed))

            # Before proceeding, do the basic tag checks on the source
            # files to ensure any uploads won't be reported, but punt
            # on the tracknumber formatting; problems with tracknumber
            # may be fixable when the tags are copied.
            broken_tags = False
            for flac_file in transcode.locate(flac_dir, transcode.ext_matcher('.flac')):
                (ok, msg) = tagging.check_tags(flac_file, check_tracknumber_format=False)
                if not ok:
                    print("A FLAC file in this release has unacceptable tags - skipping: %s" % msg)
                    print("You might be able to trump it.")
                    broken_tags = True
                    break
            if broken_tags:
                cache.add(torrentid, 'broken_tags', cache_path)
                continue

            # Manually validate spectrograms
            if not args.skip_spectral:
                print("\nGenerating Spectrograms...")
                spectrograms_ok = validate_spectrograms(flac_dir, spectral_dir, args.threads)
                if not spectrograms_ok:
                    cache.add(torrentid, 'spectrograms', cache_path)
                    continue

            if not args.skip_hashcheck:
                print("\nRunning Hashcheck...")
                file_path = Path(tempfile.mkstemp()[1])
                try:
                    api.save_torrent_file(torrentid, file_path)
                    hashcheck_passed = run_hashcheck(file_path, Path(flac_dir))
                finally:
                    file_path.unlink()
                if hashcheck_passed:
                    print('Hashcheck passed!')
                else:
                    cache.add(torrentid, 'hashcheck', cache_path)
                    print('Hashcheck failed, skipping...')
                    continue

            for format in needed:
                if Path(flac_dir).exists():
                    print('Adding format %s...' % format, end=' ')
                    tmpdir = tempfile.mkdtemp()
                    try:
                        if len(torrent['remasterTitle']) >= 1:
                            basename = artist + " - " + group['group']['name'] + " (" + torrent['remasterTitle'] + ") " + "[" + year + "] (" + torrent['media'] + " - "
                        else:
                            basename = artist + " - " + group['group']['name'] + " [" + year + "] (" + torrent['media'] + " - "

                        print(f'Transcoding...')
                        transcode_dir = transcode.transcode_release(flac_dir, output_dir, basename, format, max_threads=args.threads)
                        if not transcode_dir:
                            print("Skipping - some file(s) in this release were incorrectly marked as 24bit.")
                            cache.add(torrentid, '24bit', cache_path)
                            break

                        print('Creating torrent file...')
                        new_torrent = transcode.make_torrent(transcode_dir, tmpdir, api.tracker, api.passkey, config.get('redacted', 'piece_length'))

                        permalink = api.permalink(torrent)
                        print(f'\nTorrent ready for manual upload!')
                        print(f'Flac directory: {flac_dir}')
                        print(f'Transcode directory: {transcode_dir}')
                        print('Files:')
                        for file_name in Path(transcode_dir).glob('**/*'):
                            print(file_name)
                        print('Upload info:')
                        print(f'FLAC URL: {permalink}')
                        print(f'Edition: {year} - {torrent["remasterRecordLabel"]}')
                        print(f'Format: {format}')
                        description = create_description(torrent, flac_dir,
                                                         format, permalink)
                        print('Description:')
                        print(f'{description}\n')

                        shutil.copy(new_torrent, torrent_dir)
                        print("Done! Did you upload it?")
                        response = get_input(['y', 'n'])
                        if response == 'n':
                            print(f'Removing transcode output {transcode_dir}')
                            if Path(transcode_dir).is_dir():
                                Path(transcode_dir).rmdir()
                        if args.single:
                            break
                    except Exception as e:
                        print("Error adding format %s: %s" % (format, e))
                    finally:
                        shutil.rmtree(tmpdir)
            cache.add(torrentid, 'done', cache_path)


if __name__ == "__main__":
    main()
