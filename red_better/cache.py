from pathlib import Path

import jsonpickle


class Cache:

    def __init__(self):
        self.ids = {}

    @staticmethod
    def from_file(cache_path: Path):
        try:
            with open(str(cache_path), 'r') as cache_file:
                cache = jsonpickle.decode(cache_file.read())
                cache.ids = {int(key): cache.ids[key] for key in cache.ids}
                return cache
        except:
            return Cache()

    def add(self, torrent_id: str, reason: str, cache_path: Path):
        self.ids[torrent_id] = reason
        self.write(cache_path)

    def write(self, cache_path: Path):
        with open(str(cache_path), 'w') as cache_file:
            encoded = jsonpickle.encode(self)
            cache_file.write(encoded)
