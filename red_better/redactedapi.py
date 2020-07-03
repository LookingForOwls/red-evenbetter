#!/usr/bin/env python
import re
import json
import time
import traceback

import requests
import html.parser

headers = {
    'Connection': 'keep-alive',
    'Cache-Control': 'max-age=0',
    'User-Agent': 'REDBetter API',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Encoding': 'gzip,deflate,sdch',
    'Accept-Language': 'en-US,en;q=0.8',
    'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3'}

# gazelle is picky about case in searches with &media=x
media_search_map = {
    'cd': 'CD',
    'dvd': 'DVD',
    'vinyl': 'Vinyl',
    'soundboard': 'Soundboard',
    'sacd': 'SACD',
    'dat': 'DAT',
    'web': 'WEB',
    'blu-ray': 'Blu-ray'
    }

lossless_media = set(media_search_map.keys())

formats = {
    'FLAC': {
        'format': 'FLAC',
        'encoding': 'Lossless'
    },
    'V0': {
        'format' : 'MP3',
        'encoding' : 'V0 (VBR)'
    },
    '320': {
        'format' : 'MP3',
        'encoding' : '320'
    },
    'V2': {
        'format' : 'MP3',
        'encoding' : 'V2 (VBR)'
    },
}


def allowed_transcodes(torrent):
    """Some torrent types have transcoding restrictions."""
    preemphasis = re.search(r"""pre[- ]?emphasi(s(ed)?|zed)""", torrent['remasterTitle'], flags=re.IGNORECASE)
    if preemphasis:
        return []
    else:
        return list(formats.keys())


class LoginException(Exception):
    pass


class RequestException(Exception):
    pass


class RedactedAPI:
    def __init__(
            self,
            page_size,
            username=None,
            password=None,
            session_cookie=None,
            api_key=None,
    ):
        self.session = requests.Session()
        self.session.headers.update(headers)
        self.page_size = page_size
        self.username = username
        self.password = password
        self.session_cookie = session_cookie
        self.api_key = api_key
        self.authkey = None
        self.passkey = None
        self.userid = None
        self.api_key_authenticated = False
        self.tracker = "https://flacsfor.me/"
        self.last_request = time.time()
        self.rate_limit = 2.0 # seconds between requests
        self._login()

    def _login(self):
        if self.api_key is not None and len(self.api_key) > 0:
            self._login_api_key()
        elif self.session_cookie is not None and len(str(self.session_cookie)) > 0:
            try:
                self._login_cookie()
            except:
                print("WARNING: session cookie attempted and failed")
                self._login_username_password()
        else:
            self._login_username_password()

    def _get_account_info(self):
        accountinfo = self.request('index')
        if accountinfo is None:
            raise LoginException
        self.authkey = accountinfo['authkey']
        self.passkey = accountinfo['passkey']
        self.userid = accountinfo['id']

    def _login_api_key(self):
        self.session.headers.update({'Authorization': self.api_key})
        self._get_account_info()
        self.api_key_authenticated = True

    def _login_cookie(self):
        mainpage = 'https://redacted.ch/';
        cookiedict = {"session": self.session_cookie}
        cookies = requests.utils.cookiejar_from_dict(cookiedict)

        self.session.cookies.update(cookies)
        r = self.session.get(mainpage)
        self._get_account_info()

    def _login_username_password(self):
        '''Logs in user and gets authkey from server'''

        if not self.username or self.username == "":
            print("WARNING: username authentication attempted, but username not set, skipping.")
            raise LoginException
        loginpage = 'https://redacted.ch/login.php'
        data = {'username': self.username,
                'password': self.password}
        r = self.session.post(loginpage, data=data)
        if r.status_code != 200:
            raise LoginException
        self._get_account_info()

    def logout(self):
        self.session.get("https://redacted.ch/logout.php?auth=%s" % self.authkey)

    def request(self, action, **kwargs):
        '''Makes an AJAX request at a given action page'''
        while time.time() - self.last_request < self.rate_limit:
            time.sleep(0.1)

        ajaxpage = 'https://redacted.ch/ajax.php'
        params = {'action': action}
        if not self.api_key_authenticated and self.authkey:
            params['auth'] = self.authkey
        params.update(kwargs)
        r = self.session.get(ajaxpage, params=params, allow_redirects=False)
        self.last_request = time.time()
        try:
            parsed = json.loads(r.content)
            if parsed['status'] != 'success':
                return None
            return parsed['response']
        except ValueError as e:
            raise RequestException(e)

    def get_artist(self, id=None, format='MP3', best_seeded=True):
        res = self.request('artist', id=id)
        torrentgroups = res['torrentgroup']
        keep_releases = []
        for release in torrentgroups:
            torrents = release['torrent']
            best_torrent = torrents[0]
            keeptorrents = []
            for t in torrents:
                if t['format'] == format:
                    if best_seeded:
                        if t['seeders'] > best_torrent['seeders']:
                            keeptorrents = [t]
                            best_torrent = t
                    else:
                        keeptorrents.append(t)
            release['torrent'] = list(keeptorrents)
            if len(release['torrent']):
                keep_releases.append(release)
        res['torrentgroup'] = keep_releases
        return res

    def snatched(self):
        page = 0
        while True:
            response = self.request(
                'user_torrents',
                id=self.userid,
                type='snatched',
                limit=self.page_size,
                offset=page * self.page_size
            )
            snatched = response['snatched']
            if len(snatched) == 0:
                break
            print(f'Fetched snatched results {page * self.page_size} to '
                  f'{(page + 1) * self.page_size - 1}')
            for entry in snatched:
                group_id = int(entry['groupId'])
                torrent_id = int(entry['torrentId'])
                yield group_id, torrent_id
            page += 1

    def release_url(self, group, torrent):
        return "https://redacted.ch/torrents.php?id=%s&torrentid=%s#torrent%s" % (group['group']['id'], torrent['id'], torrent['id'])

    def permalink(self, torrent):
        return "https://redacted.ch/torrents.php?torrentid=%s" % torrent['id']

    def get_better(self, search_type=3, tags=None):
        if tags is None:
            tags = []
        data = self.request('better', method='transcode', type=search_type, search=' '.join(tags))
        out = []
        for row in data:
            out.append({
                'permalink': 'torrents.php?id={}'.format(row['torrentId']),
                'id': row['torrentId'],
                'torrent': row['downloadUrl'],
            })
        return out

    def get_torrent(self, torrent_id):
        '''Downloads the torrent at torrent_id using the authkey and passkey'''
        while time.time() - self.last_request < self.rate_limit:
            time.sleep(0.1)

        torrentpage = 'https://redacted.ch/torrents.php'
        params = {'action': 'download', 'id': torrent_id}
        if self.authkey:
            params['authkey'] = self.authkey
            params['torrent_pass'] = self.passkey
        r = self.session.get(torrentpage, params=params, allow_redirects=False)

        self.last_request = time.time() + 2.0
        if r.status_code == 200 and 'application/x-bittorrent' in r.headers['content-type']:
            return r.content
        return None

    def get_torrent_info(self, id):
        return self.request('torrent', id=id)['torrent']


def unescape(text):
    return html.unescape(text)
