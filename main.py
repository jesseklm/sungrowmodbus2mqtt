import logging
import signal
import sys
from time import sleep, time

from config import config
from modbus_handler import ModbusHandler
from mqtt_handler import MqttHandler

__version__ = '1.0.1'


def convert_to_type(value: int, datatype: str) -> int:
    if datatype == 'uint16':
        return value
    elif datatype == 'int16':
        value = value.to_bytes(length=2, byteorder='big', signed=False)
        return int.from_bytes(value, byteorder='big', signed=True)
    elif datatype == 'uint32':
        return value
    elif datatype == 'int32':
        value = value.to_bytes(length=4, byteorder='big', signed=False)
        return int.from_bytes(value, byteorder='big', signed=True)
    logging.warning(f'unknown datatype {datatype} {value}.')


class SungrowModbus2Mqtt:
    def __init__(self):
        self.mqtt_handler = MqttHandler()
        self.modbus_handler = ModbusHandler()
        signal.signal(signal.SIGINT, self.exit_handler)
        signal.signal(signal.SIGTERM, self.exit_handler)
        self.address_offset = config.get('address_offset', 0)
        self.scan_batching = config.get('scan_batching', 100)
        self.registers: dict = {
            'holding': {},
            'input': {},
        }
        self.init_registers()

    def loop(self):
        while True:
            start_time = time()
            self.read()
            self.publish()
            time_taken = time() - start_time
            time_to_sleep = config['update_rate'] - time_taken
            if time_to_sleep > 0:
                sleep(time_to_sleep)

    def exit_handler(self, signum, frame):
        self.modbus_handler.close()
        sys.exit(0)

    def create_register(self, register_table, config_register):
        register = {'topic': config_register['pub_topic']}
        if 'type' in config_register:
            register['type'] = config_register['type'].strip().lower()
        else:
            register['type'] = 'uint16'
        if 'value_map' in config_register:
            value_map = config_register['value_map']
            register['map'] = dict((v, k) for k, v in value_map.items())
        if 'scale' in config_register:
            register['scale'] = config_register['scale']
        if 'mask' in config_register:
            register['mask'] = config_register['mask']
        if 'shift' in config_register:
            register['shift'] = config_register['shift']
        if register['type'].endswith('32'):
            self.registers[register_table][
                config_register['address'] + self.address_offset + 1] = {'type': f'{register["type"]}_2'}
        return register

    def init_register(self, register_table, register):
        new_register = self.create_register(register_table, register)
        register_address = register['address'] + self.address_offset
        if register_address in self.registers[register_table]:
            if 'multi' not in self.registers[register_table][register_address]:
                self.registers[register_table][register_address]['multi'] = []
            self.registers[register_table][register_address]['multi'].append(new_register)
            return
        self.registers[register_table][register_address] = new_register

    def init_registers(self):
        if 'registers' in config:
            for register in config['registers']:
                register_table = register.get('table', 'holding')
                self.init_register(register_table, register)
        if 'input' in config:
            for register in config['input']:
                self.init_register('input', register)
        if 'holding' in config:
            for register in config['holding']:
                self.init_register('holding', register)

    def read(self):
        for table in self.registers:
            for address in list(self.registers[table].keys()):
                if time() - self.registers[table][address].get('last_fetch', 0) < config['update_rate']:
                    continue

                if 'read_count' in self.registers[table][address]:
                    count = self.registers[table][address]['read_count']
                else:
                    count = self.scan_batching
                    for i in range(count - 1, -1, -1):
                        if address + i in self.registers[table]:
                            count = i + 1
                            self.registers[table][address]['read_count'] = count
                            break

                logging.debug(f'read: table:{table} address:{address} count:{count}.')
                result = self.modbus_handler.read(table, address, count)

                for i, register in enumerate(result):
                    loop_address = address + i
                    if loop_address not in self.registers[table]:
                        continue
                    self.registers[table][loop_address]['last_fetch'] = time()
                    if ('value' in self.registers[table][loop_address]
                            and self.registers[table][loop_address]['value'] == register):
                        self.registers[table][loop_address]['new'] = False
                        continue
                    self.registers[table][loop_address]['value'] = register
                    self.registers[table][loop_address]['new'] = True

    @staticmethod
    def prepare_value(register, value):
        if 'map' in register:
            value = register['map'].get(value, f'{value} not mapped!')
        else:
            value = convert_to_type(value, register['type'])
        if 'mask' in register:
            value &= register['mask']
        if 'shift' in register:
            value >>= register['shift']
        if 'scale' in register:
            value = value * register['scale']
            value = round(value, 10)
        return value

    def publish(self):
        for table in self.registers:
            for address in self.registers[table]:
                register = self.registers[table][address]
                register_type = register['type']
                if register_type in ['int32_2', 'uint32_2']:
                    continue
                if register_type in ['int32', 'uint32']:
                    new = register.get('new', False) or self.registers[table][address + 1].get('new', False)
                else:
                    new = register.get('new', False)
                if not new:
                    continue
                value = register['value']
                if register_type in ['int32', 'uint32']:
                    value_2 = self.registers[table][address + 1]['value']
                    value = (value_2.to_bytes(length=2, byteorder='big', signed=False)
                             + value.to_bytes(length=2, byteorder='big', signed=False))
                    value = int.from_bytes(value, byteorder='big', signed=False)
                if 'multi' in register:
                    for subregister in register['multi']:
                        self.mqtt_handler.publish(subregister['topic'], self.prepare_value(subregister, value))
                self.mqtt_handler.publish(register['topic'], self.prepare_value(register, value))


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.info(f'starting SungrowModbus2Mqtt v{__version__}.')
    app = SungrowModbus2Mqtt()
    app.loop()
