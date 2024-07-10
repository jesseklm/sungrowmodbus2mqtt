import json
from pathlib import Path

import yaml


def get_config_local(filename: Path) -> dict:
    with open(filename) as file:
        try:
            return yaml.safe_load(file)
        except yaml.YAMLError as e:
            print(e)
            return {'error': str(e)}


def get_first_config() -> dict:
    files = [
        Path('/config/config.yaml'),
        Path('config.yaml'),
        Path('config.sh10rt.example.yaml')
    ]
    for file in files:
        if file.exists():
            loaded_config = get_config_local(file)
            break
    else:
        raise FileNotFoundError
    options_file = Path('/data/options.json')
    if options_file.exists():
        with open(options_file) as file:
            options = json.load(file)
        for key in options:
            if isinstance(options[key], str):
                if len(options[key]) > 0:
                    loaded_config[key] = options[key]
            elif isinstance(options[key], int):
                loaded_config[key] = options[key]
    return loaded_config


config: dict = get_first_config()
