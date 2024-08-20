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
    options_files = [
        Path('/data/options.json'),
        Path('/data/options.yaml'),
    ]
    for options_file in options_files:
        if options_file.exists():
            if options_file.suffix == '.json':
                with open(options_file) as file:
                    options: dict = json.load(file)
            else:
                options = get_config_local(options_file)
            for key, option in options.items():
                if isinstance(option, str) and option:
                    loaded_config[key] = option
                elif isinstance(option, int) or isinstance(option, bool):
                    loaded_config[key] = option
            break
    return loaded_config
