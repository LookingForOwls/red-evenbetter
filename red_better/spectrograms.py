import shutil
from pathlib import Path

from red_better.command import run_command


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
    if run_command(command, flac_dir) is None:
        return False
    if not temp_spectrogram_dir.exists():
        print(f'Temp spectrogram dir {temp_spectrogram_dir} was not created'
              f'for some reason. Skipping.')
        return False
    shutil.copytree(str(temp_spectrogram_dir), str(spectrogram_dir), dirs_exist_ok=True)
    shutil.rmtree(temp_spectrogram_dir)
    return True
