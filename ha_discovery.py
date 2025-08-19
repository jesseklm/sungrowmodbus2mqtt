import json

from config import get_first_config


def guess_component(register: dict) -> str:
    if register.get('sensor_type') == 'binary':
        return 'binary_sensor'
    return 'sensor'


def guess_device_class(pub_topic: str, unit: str | None, explicit_class: str | None) -> str | None:
    if explicit_class:
        return explicit_class
    if unit:
        m = {
            '°c': 'temperature',
            'c': 'temperature',
            'v': 'voltage',
            'a': 'current',
            'w': 'power',
            'kw': 'power',
            'kwh': 'energy',
            'hz': 'frequency',
            '%': 'battery' if ('battery' in pub_topic or 'soc' in pub_topic) else None,
        }
        key = unit.lower()
        return m.get(key)
    # topic-name based
    if 'temperature' in pub_topic:
        return 'temperature'
    if 'voltage' in pub_topic:
        return 'voltage'
    if 'current' in pub_topic:
        return 'current'
    if 'power' in pub_topic:
        return "power"
    if 'energy' in pub_topic:
        return 'energy'
    if 'frequency' in pub_topic:
        return 'frequency'
    if 'battery' in pub_topic or 'soc' in pub_topic:
        return 'battery'
    return None


def guess_state_class(pub_topic: str, unit: str | None, sensor_type: str | None) -> str | None:
    if sensor_type == 'binary':
        return None
    if unit and unit.lower() in {'w', 'kw', '°c', 'c', 'v', 'a', 'hz', '%'}:
        return 'measurement'
    if unit and unit.lower() == 'kwh':
        if 'total' in pub_topic:
            return 'total_increasing'
        return 'measurement'
    # fallback
    if sensor_type == 'measurement':
        return 'measurement'
    return None


def ha_discovery_from_register(register: dict, device_id: str, device_name: str, state_prefix: str,
                               discovery_prefix: str = 'homeassistant') -> tuple[str, str]:
    pub_topic = register['pub_topic']
    unit = register.get('unit')
    explicit_class = register.get('class')
    sensor_type = register.get('sensor_type')

    component = guess_component(register)
    object_id = pub_topic

    discovery_topic = f'{discovery_prefix}/{component}/{device_id}/{object_id}/config'

    payload: dict = {
        'name': pub_topic,
        'unique_id': f'{device_id}_{object_id}',
        'state_topic': f'{state_prefix}{pub_topic}',
        'device': {
            'identifiers': [device_id],
            'name': device_name,
        },
    }

    if unit:
        payload['unit_of_measurement'] = unit

    if device_class := guess_device_class(pub_topic, unit, explicit_class):
        payload['device_class'] = device_class

    if state_class := guess_state_class(pub_topic, unit, sensor_type):
        payload['state_class'] = state_class

    if component == 'binary_sensor':
        payload['payload_on'] = '1'
        payload['payload_off'] = '0'

    return discovery_topic, json.dumps(payload, ensure_ascii=False)


def send_ha_discovery(config: dict, topic_prefix: str, publish):
    if 'ha_device_id' not in config:
        return
    device_id = config['ha_device_id']
    device_name = config.get('ha_device_name', device_id)
    for register_type in ['registers', 'input', 'holding']:
        for register in config.get(register_type, []):
            topic, payload = ha_discovery_from_register(register, device_id, device_name, topic_prefix)
            publish(topic, payload, retain=True)


if __name__ == "__main__":
    def publish_print(topic, payload, retain):
        print(f'publish {topic}: {payload}, retain={retain}')


    send_ha_discovery(get_first_config(), 'sungrow/', publish_print)
