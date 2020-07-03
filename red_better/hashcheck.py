from pathlib import Path
from typing import Tuple

from red_better.command import run_command


def run_hashcheck(torrent_file_path: Path, data_dir: Path) -> Tuple[bool, str]:
    command = f'hashcheck \"{torrent_file_path}\" \"{data_dir}\"'
    output = run_command(command)
    if output is None:
        return False, ''
    statuses = {line.split()[0] for line in output.splitlines()}
    return len(statuses) == 1 and list(statuses)[0] == 'INFO', output
