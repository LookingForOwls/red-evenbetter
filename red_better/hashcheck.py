from pathlib import Path
import subprocess


def run_hashcheck(torrent_file_path: Path, data_dir: Path):
    command = f'imdl -t torrent verify --input \"{torrent_file_path}\" --content \"{data_dir}\"'
    try:
        subprocess.check_output(
            command,
            stderr=subprocess.STDOUT,
            shell=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(e.output.decode('utf-8'))
        return False