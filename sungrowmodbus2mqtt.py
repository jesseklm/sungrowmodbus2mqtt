import logging
import signal
import sys
from time import sleep, time

from config import get_first_config
from modbus_handler import ModbusHandler
from mqtt_handler import MqttHandler

__version__ = '1.0.19'


class SungrowModbus2Mqtt:
    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_handler)
        signal.signal(signal.SIGTERM, self.exit_handler)
        config = get_first_config()
        if 'logging' in config:
            logging_level_name = config['logging'].upper()
            logging_level = logging.getLevelNamesMapping().get(logging_level_name, logging.NOTSET)
            if logging_level != logging.NOTSET:
                logging.getLogger().setLevel(logging_level)
            else:
                logging.warning(f'unknown logging level: %s.', logging_level)
        self.mqtt_handler = MqttHandler(config)
        self.modbus_handler = ModbusHandler(config)
        self.modbus_handler.reconnect(first_connect=True)
        self.address_offset: int = config.get('address_offset', 0)
        self.old_value_map: bool = config.get('old_value_map', False)
        self.scan_batching: int = config.get('scan_batching', 100)
        self.update_rate: int = config.get('update_rate', 2)
        self.registers = {
            'holding': {},
            'input': {},
        }
        self.init_registers(config)

    def loop(self):
        while True:
            start_time = time()
            self.read(start_time)
            self.publish()
            time_taken = time() - start_time
            time_to_sleep = self.update_rate - time_taken
            logging.debug('looped in %.2fms, sleeping %.2fs.', time_taken * 1000, time_to_sleep)
            if time_to_sleep > 0:
                sleep(time_to_sleep)

    def exit_handler(self, signum, frame):
        self.modbus_handler.close()
        sys.exit(0)

    def add_dummy_register(self, register_table: str, address: int):
        self.registers[register_table][address] = {'type': 'dummy'}

    def create_register(self, register_table: str, config_register: dict) -> dict:
        register = {'topic': config_register['pub_topic']}
        if 'type' in config_register:
            register['type'] = config_register['type'].strip().lower()
        else:
            register['type'] = 'uint16'
        if 'value_map' in config_register:
            value_map = config_register['value_map']
            if self.old_value_map:
                value_map = dict((v, k) for k, v in value_map.items())
            register['map'] = value_map
        if 'scale' in config_register:
            register['scale'] = config_register['scale']
        if 'mask' in config_register:
            register['mask'] = config_register['mask']
        if 'shift' in config_register:
            register['shift'] = config_register['shift']
        if 'retain' in config_register:
            register['retain'] = config_register['retain']
        word_count = ModbusHandler.WORD_COUNT.get(register['type'], 1)
        for i in range(1, word_count):
            self.add_dummy_register(register_table, config_register['address'] + self.address_offset + i)
        return register

    def init_register(self, register_table: str, register: dict):
        new_register = self.create_register(register_table, register)
        register_address: int = register['address'] + self.address_offset
        if register_address in self.registers[register_table]:
            if 'multi' not in self.registers[register_table][register_address]:
                self.registers[register_table][register_address]['multi'] = []
            self.registers[register_table][register_address]['multi'].append(new_register)
            return
        self.registers[register_table][register_address] = new_register

    def init_registers(self, config: dict):
        for register in config.get('registers', []):
            register_table: str = register.get('table', 'holding')
            self.init_register(register_table, register)
        for register in config.get('input', []):
            self.init_register('input', register)
        for register in config.get('holding', []):
            self.init_register('holding', register)
        for table in self.registers:
            self.registers[table] = dict(sorted(self.registers[table].items()))

    def read(self, start_time: float):
        for table in self.registers:
            for address in list(self.registers[table].keys()):
                if start_time - self.registers[table][address].get('last_fetch', 0) < self.update_rate - 0.001:
                    continue

                if 'read_count' in self.registers[table][address]:
                    count: int = self.registers[table][address]['read_count']
                else:
                    count = self.scan_batching
                    for i in range(count - 1, -1, -1):
                        if address + i in self.registers[table]:
                            count = i + 1
                            self.registers[table][address]['read_count'] = count
                            break

                logging.debug(f'read: table:%s address:%s count:%s.', table, address, count)
                result = self.modbus_handler.read(table, address, count)

                for loop_address, register in enumerate(result, start=address):
                    if loop_address not in self.registers[table]:
                        continue
                    self.registers[table][loop_address]['last_fetch'] = start_time
                    if ('value' in self.registers[table][loop_address]
                            and self.registers[table][loop_address]['value'] == register):
                        self.registers[table][loop_address]['new'] = False
                        continue
                    self.registers[table][loop_address]['value'] = register
                    self.registers[table][loop_address]['new'] = True

    @staticmethod
    def prepare_value(register: dict, value: int) -> str | int | float:
        if 'map' in register:
            return register['map'].get(value, f'{value:#x} not mapped!')
        if 'mask' in register:
            value &= register['mask']
        if 'shift' in register:
            value >>= register['shift']
        if 'scale' in register:
            value *= register['scale']
            value = round(value, 10)
        return value

    def publish(self):
        for table in self.registers:
            for address in self.registers[table]:
                register: dict = self.registers[table][address]
                register_type: str = register['type']
                if register_type == 'dummy':
                    continue
                word_count = ModbusHandler.WORD_COUNT.get(register_type, 1)
                new = any(self.registers[table][address + i].get('new', False) for i in range(word_count))
                if not new:
                    continue
                values: list[int] = [self.registers[table][address + i]['value'] for i in range(word_count)]
                value = self.modbus_handler.decode(values, register_type)
                for subregister in register.get('multi', []):
                    self.mqtt_handler.publish(subregister['topic'], self.prepare_value(subregister, value),
                                              subregister.get('retain', False))
                self.mqtt_handler.publish(register['topic'], self.prepare_value(register, value),
                                          register.get('retain', False))


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.getLogger('pymodbus').setLevel(logging.INFO)
    logging.info(f'starting SungrowModbus2Mqtt v%s.', __version__)
    app = SungrowModbus2Mqtt()
    app.loop()
