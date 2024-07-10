from pathlib import Path

import yaml


def get_config_local(filename: Path) -> dict:
    with open(filename, 'r') as file:
        try:
            return yaml.safe_load(file)
        except yaml.YAMLError as e:
            print(e)
            return {'error': str(e)}


try:
    config: dict = get_config_local(Path('/config/config.yaml'))
except FileNotFoundError:
    config = get_config_local(Path('config.yaml'))
