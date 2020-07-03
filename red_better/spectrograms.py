import shutil
import subprocess
from pathlib import Path
from typing import Optional


def run(command: str, directory: Path) -> Optional[str]:
    command = f'cd \"{directory}\" && {command}'
    try:
        output = subprocess.check_output(
            command,
            stderr=subprocess.STDOUT,
            shell=True
        )
    except subprocess.CalledProcessError as e:
        print(e)
        return None
    return output.decode('utf-8')


def make_spectrograms(
        flac_dir: Path,
        spectrogram_dir: Path,
        threads: int
) -> bool:
    command = f'bash {Path(__file__).parent}/run_sox.sh --threads {threads} .'
    temp_spectrogram_dir = flac_dir / 'Spectrograms'
    if temp_spectrogram_dir.exists():
        print(f'Temp spectrogram dir {temp_spectrogram_dir} already exists.'
              f'Skipping since unable to validate.')
        return False
    if run(command, flac_dir) is None:
        return False
    if not temp_spectrogram_dir.exists():
        print(f'Temp spectrogram dir {temp_spectrogram_dir} was not created'
              f'for some reason. Skipping.')
        return False
    shutil.copytree(str(temp_spectrogram_dir), str(spectrogram_dir), dirs_exist_ok=True)
    shutil.rmtree(temp_spectrogram_dir)
    return True
