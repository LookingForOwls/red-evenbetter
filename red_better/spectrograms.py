from pathlib import Path
import mutagen.flac
from functools import partial
from multiprocessing import Pool
import subprocess

class SoxError(Exception):
    pass

def runSox(spectrogram_dir, flac_dir, flac_file):
    full_sox_command = "-n remix 1 spectrogram -x 3000 -y 513 -z 120 -w Kaiser"
    zoom_sox_command = "-n remix 1 spectrogram -x 500 -y 1025 -z 120 -w Kaiser"
    zoom_start = 3
    zoom_total = 2
    
    if flac_file.parent.name == flac_dir.name:
        out_file = spectrogram_dir.joinpath(flac_file.name)
    else:
        out_file = spectrogram_dir.joinpath(f"{flac_file.parent.name} - {flac_file.name}")
    # Handle long names for zoom
    name = flac_file
    if len(str(flac_file)) > 85:
        name = flac_file.name
    flac = mutagen.flac.FLAC(flac_file)
    # Calc start position for for zoomed spectrals
    start_zoom = round(flac.info.length / zoom_start)
    comment = f"{flac.info.bits_per_sample} bit  |  {flac.info.sample_rate} Hz"
    full = f"sox '{flac_file}' {full_sox_command} -t '{name}' -c '{comment}' -o '{out_file}-full.png'"
    zoom = f"sox '{flac_file}' {zoom_sox_command} -S 0:{start_zoom} -d 0:{zoom_total} -t '{name}' -c '{comment}   |  {zoom_total} sec  |  starting @ {start_zoom} sec' -o '{out_file}-zoom.png'"
    command = f"{full}; {zoom}"
    try:
        output = subprocess.check_output(
            command,
            stderr=subprocess.STDOUT,
            shell=True,
        )
        if 'FAIL' in output.decode('utf-8'):
            raise SoxError
    except subprocess.CalledProcessError as e:
        print(e)
    except Exception as e:
        print(output.decode('utf-8'))


def make_spectrograms(flac_dir, spectral_dir_str, max_threads = 4):
    files = list(Path(flac_dir).rglob("*.flac"))
    with Pool(max_threads) as pool:
        try:
            func = partial(runSox, spectral_dir_str, flac_dir)
            output = pool.map(func, files)
        except Exception as e:
            return False
        return True
