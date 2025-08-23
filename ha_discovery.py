import json
from dataclasses import dataclass
from decimal import Decimal

from config import get_first_config


@dataclass(frozen=True, slots=True)
class SensorDef:
    name: str
    state_topic: str | None = None
    platform: str = 'sensor'
    device_class: str | None = None
    unit: str | None = None
    state_class: str | None = None
    payload_on: str | None = None
    payload_off: str | None = None
    entity_category: str | None = None
    precision: int | None = None
    command_topic: bool | None = None
    options: list[str] | None = None
    value_min: int | None = None
    value_max: int | None = None
    value_step: float | None = None


def generate_ha_discovery_payload(sensors: list[SensorDef], dev_id: str, dev_name: str, o_name: str, o_url: str,
                                  av_topic: str, topic_prefix: str) -> str:
    payload: dict[str, dict[str, str | dict]] = {
        'dev': {  # device
            'ids': dev_id,  # identifiers
            'name': dev_name,
        },
        'o': {  # origin
            'name': o_name,
            'sw': '1.0',  # sw_version
            'url': o_url,  # support_url
        },
        'avty_t': av_topic,  # availability_topic
        'cmps': {}  # components
    }
    for sensor in sensors:
        component: dict[str, str | int | float | list[str]] = {
            'p': sensor.platform,  # platform
            'name': sensor.name,
            'uniq_id': f"{payload['dev']['ids']}_{sensor.name}",  # unique_id
            'stat_t': f'{topic_prefix}{sensor.state_topic or sensor.name}',  # state_topic
        }
        if sensor.device_class: component['dev_cla'] = sensor.device_class  # device_class
        if sensor.unit: component['unit_of_meas'] = sensor.unit  # unit_of_measurement
        if sensor.state_class: component['stat_cla'] = sensor.state_class  # state_class
        if sensor.payload_on: component['pl_on'] = sensor.payload_on  # payload_on
        if sensor.payload_off: component['pl_off'] = sensor.payload_off  # payload_off
        if sensor.entity_category: component['ent_cat'] = sensor.entity_category  # entity_category
        if sensor.precision: component['sug_dsp_prc'] = sensor.precision  # suggested_display_precision
        if sensor.command_topic: component['cmd_t'] = f"{component['stat_t']}/set"  # command_topic
        if sensor.options: component['ops'] = sensor.options  # options
        if sensor.value_min: component['min'] = sensor.value_min  # min
        if sensor.value_max: component['max'] = sensor.value_max  # max
        if sensor.value_step: component['step'] = sensor.value_step  # step
        payload['cmps'][sensor.name] = component
    return json.dumps(payload)


def unit_to_device_class(unit: str | None) -> str | None:
    if not unit:
        return None
    unit_table = {
        '°c': 'temperature',
        'a': 'current',
        'kw': 'power',
        'kwh': 'energy',
        'hz': 'frequency',
        'v': 'voltage',
        'var': 'reactive_power',
        'w': 'power',
    }
    return unit_table.get(unit.lower())


def get_decimals(value: float | None) -> int | None:
    if not value:
        return None
    value_s = format(value, f'.6g')
    value_d = Decimal(value_s).normalize()
    return max(0, -value_d.as_tuple().exponent)


def get_unique_dict_values(data: dict) -> list[str] | None:
    if not data:
        return None
    seen, out = set(), []
    for v in data.values():
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def send_ha_discovery(config: dict, topic_prefix: str, publish):
    if 'ha_device_id' not in config:
        return
    # register_attrs = set()
    # register_classes = set()
    # register_types = set()
    # register_units = set()
    # register_sensor_types = set()
    # for register_type in ['registers', 'input', 'holding']:
    #     for register in config.get(register_type, []):
    #         for register_attr in register:
    #             register_attrs.add(register_attr)
    #         if 'type' in register:
    #             register_types.add(register['type'])
    #         if 'class' in register:
    #             register_classes.add(register['class'])
    #         if 'sensor_type' in register:
    #             register_sensor_types.add(register['sensor_type'])
    #         if 'unit' in register:
    #             register_units.add(register['unit'])
    # print('attrs', sorted(register_attrs))
    # print('classes', sorted(register_classes))
    # print('types', sorted(register_types))
    # print('units', sorted(register_units))
    # print('sensor_types', sorted(register_sensor_types))
    sensors: list[SensorDef] = []
    for register_type in ['registers', 'input', 'holding']:
        for register in config.get(register_type, []):
            sensor_name = register['pub_topic']
            platform_select = 'select' if register_type == 'holding' and 'value_map' in register else None
            platform_number = 'number' if register_type == 'holding' and 'value_min' in register and 'value_max' in register else None
            platform_binary = 'binary_sensor' if 'binary' == register.get('sensor_type') else None
            platform: str = platform_select or platform_number or platform_binary or 'sensor'
            unit = register.get('unit')
            device_class = register.get('class') or unit_to_device_class(unit)
            state_class = ('total_increasing' if device_class == 'energy' else None) or (
                'measurement' if unit else None)
            payload_on = '1' if platform == 'binary_sensor' else None
            payload_off = '0' if platform == 'binary_sensor' else None
            entity_category = 'diagnostic' if register_type == 'holding' else None
            precision = get_decimals(register.get('scale'))
            command_topic = True if platform_select or platform_number else False
            options = get_unique_dict_values(register.get('value_map')) if platform_select else None
            value_min = register.get('value_min') if platform_number else None
            value_max = register.get('value_max') if platform_number else None
            value_step = round(register.get('scale', 1), 3) if platform_number else None
            sensors.append(
                SensorDef(sensor_name, platform=platform, device_class=device_class, unit=unit, state_class=state_class,
                          payload_on=payload_on, payload_off=payload_off, entity_category=entity_category,
                          precision=precision, command_topic=command_topic, options=options, value_min=value_min,
                          value_max=value_max, value_step=value_step))
    payload = generate_ha_discovery_payload(sensors, config['ha_device_id'], config['ha_device_name'],
                                            'sungrowmodbus2mqtt', 'https://github.com/jesseklm/sungrowmodbus2mqtt',
                                            f'{topic_prefix}available', topic_prefix)
    publish(f"homeassistant/device/{config['ha_device_id']}/config", payload, retain=True)


if __name__ == "__main__":
    c = get_first_config()


    def publish_print(topic, payload, retain):
        print(f'publish {topic}: {payload}, retain={retain}')


    send_ha_discovery(c, 'sungrow/', publish_print)
