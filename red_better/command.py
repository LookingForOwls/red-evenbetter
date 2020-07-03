import subprocess
from pathlib import Path
from typing import Optional


def run_command(command: str, directory: Optional[Path] = None) -> Optional[str]:
    if directory is not None:
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