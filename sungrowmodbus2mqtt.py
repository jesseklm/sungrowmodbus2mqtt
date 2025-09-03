import asyncio
import logging
import signal
import time
from typing import Any

from config import get_first_config
from modbus_handler import ModbusHandler
from mqtt_handler import MqttHandler

__version__ = '1.0.28'


class SungrowModbus2Mqtt:
    def __init__(self) -> None:
        config: dict = get_first_config()
        if 'logging' in config:
            logging_level_name: str = config['logging'].upper()
            logging_level: int = logging.getLevelNamesMapping().get(logging_level_name, logging.NOTSET)
            if logging_level != logging.NOTSET:
                logging.getLogger().setLevel(logging_level)
            else:
                logging.warning('unknown logging level: %s.', logging_level)
        self.address_offset: int = config.get('address_offset', 0)
        self.old_value_map: bool = config.get('old_value_map', False)
        self.scan_batching: int = config.get('scan_batching', 100)
        self.update_rate: int = config.get('update_rate', 2)
        self.registers: dict[str, dict[int, dict[str, Any]]] = {
            'holding': {},
            'input': {},
        }
        self.init_registers(config)
        sub_topics = []
        for address, register in self.registers['holding'].items():
            if register['topic'] == 'dummy':
                continue
            sub_topics.append(register['topic'])
        self.mqtt_handler: MqttHandler = MqttHandler(config, sub_topics, self.handle_mqtt_message)
        self.modbus_handler: ModbusHandler = ModbusHandler(config)

    async def loop(self) -> None:
        try:
            await self.modbus_handler.reconnect(first_connect=True)
            while True:
                start_time: float = time.perf_counter()
                await self.read(start_time)
                await self.publish()
                time_taken: float = time.perf_counter() - start_time
                time_to_sleep: float = self.update_rate - time_taken
                logging.debug('looped in %.2fms, sleeping %.2fs.', time_taken * 1000, time_to_sleep)
                if time_to_sleep > 0:
                    await asyncio.sleep(time_to_sleep)
        except KeyboardInterrupt:
            await self.mqtt_handler.mqttc.disconnect()

    async def exit(self) -> None:
        self.modbus_handler.close()
        await self.mqtt_handler.disconnect()

    async def handle_mqtt_message(self, topic: str, payload: str):
        logging.debug('handle topic: %s, payload: %s', topic, payload)
        for address, register in self.registers['holding'].items():
            if register['topic'] == topic:
                new_value: int = self.prepare_write_value(register, payload, )
                await self.modbus_handler.write('holding', address, new_value, register['type'])
                return

    def add_dummy_register(self, register_table: str, address: int) -> None:
        self.registers[register_table][address] = {'type': 'dummy'}

    def create_register(self, register_table: str, config_register: dict) -> dict[str, Any]:
        register: dict[str, Any] = {
            'topic': config_register['pub_topic'],
            'type': config_register.get('type', 'uint16').strip().lower(),
        }
        if 'value_map' in config_register:
            value_map: dict = config_register['value_map']
            if self.old_value_map:
                value_map = {v: k for k, v in value_map.items()}
            register['map'] = value_map
        for option in ['scale', 'mask', 'shift', 'retain', 'word_count', 'word_order']:
            if option in config_register:
                register[option] = config_register[option]
        if 'word_count' in register:
            word_count: int = register['word_count']
        else:
            word_count: int = ModbusHandler.WORD_COUNT.get(register['type'], 1)
        for i in range(1, word_count):
            self.add_dummy_register(register_table, config_register['address'] + self.address_offset + i)
        return register

    def init_register(self, register_table: str, register: dict) -> None:
        new_register: dict[str, Any] = self.create_register(register_table, register)
        register_address: int = register['address'] + self.address_offset
        existing_register: dict[str, Any] = self.registers[register_table].setdefault(register_address, new_register)
        if existing_register is not new_register:
            existing_register.setdefault('multi', []).append(new_register)

    def init_registers(self, config: dict) -> None:
        for register_type in ['registers', 'input', 'holding']:
            for register in config.get(register_type, []):
                register_table: str = register.get('table',
                                                   'holding') if register_type == 'registers' else register_type
                self.init_register(register_table, register)
        self.registers = {table: dict(sorted(register.items())) for table, register in self.registers.items()}

    async def read(self, start_time: float) -> None:
        for table, table_registers in self.registers.items():
            for address, register in list(table_registers.items()):
                if start_time - register.get('last_fetch', 0) < self.update_rate - 0.001:
                    continue

                count: int = register.get('read_count', self.scan_batching)
                if 'read_count' not in register:
                    count = next((i + 1 for i in range(count - 1, -1, -1) if address + i in table_registers))
                    register['read_count'] = count

                logging.debug('read: table:%s address:%s count:%s.', table, address, count)
                result: list[int] = await self.modbus_handler.read(table, address, count)

                for result_address, result_register in enumerate(result, start=address):
                    if result_address not in table_registers:
                        continue
                    table_register: dict[str, Any] = table_registers[result_address]
                    table_register['last_fetch'] = start_time
                    if table_register.get('value') == result_register:
                        table_register['new'] = False
                    else:
                        table_register['value'] = result_register
                        table_register['new'] = True

    @staticmethod
    def prepare_value(register: dict[str, Any], value: int | str) -> str | int | float:
        if value_map := register.get('map'):
            return value_map.get(value, f'{value:#x} not mapped!')
        if mask := register.get('mask'):
            value &= mask
        if shift := register.get('shift'):
            value >>= shift
        if scale := register.get('scale'):
            value: int | float = round(value * scale, 10)
        return value

    @staticmethod
    def prepare_write_value(register: dict[str, Any], value: str | int | float) -> int:
        if value_map := register.get('map'):
            try:
                return {v: k for k, v in value_map.items()}[value]
            except KeyError:
                logging.error('value: %s of topic: %s not mapped!', value, register['topic'])
        try:
            value = float(value)
        except ValueError:
            pass
        if scale := register.get('scale'):
            value = round(value / scale, 0)
        try:
            value = int(value)
        except ValueError:
            logging.error('value: %s of topic: %s failed to prepare!', value, register['topic'])
        return value

    async def publish(self) -> None:
        for table, table_registers in self.registers.items():
            for address, register in table_registers.items():
                if (register_type := register['type']) == 'dummy':
                    continue
                if 'word_count' in register:
                    word_count: int = register['word_count']
                else:
                    word_count: int = ModbusHandler.WORD_COUNT.get(register_type, 1)
                if not any(table_registers[address + i].get('new', False) for i in range(word_count)):
                    continue
                values: list[int] = [table_registers[address + i]['value'] for i in range(word_count)]
                try:
                    value: int | str = self.modbus_handler.decode(values, register_type, register.get('word_order'))
                except UnicodeDecodeError as e:
                    logging.error('values: %s of topic: %s failed to decode: %s', values, register['topic'], e)
                    continue
                for subregister in register.get('multi', []):
                    self.mqtt_handler.publish(subregister['topic'], self.prepare_value(subregister, value),
                                              subregister.get('retain', False))
                self.mqtt_handler.publish(register['topic'], self.prepare_value(register, value),
                                          register.get('retain', False))


async def main():
    app = SungrowModbus2Mqtt()
    loop = asyncio.get_running_loop()
    main_task = asyncio.current_task()

    def shutdown_handler():
        if not main_task.done():
            main_task.cancel()

    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, shutdown_handler)
    except NotImplementedError:
        pass
    try:
        await app.loop()
    except asyncio.CancelledError:
        logging.info('exiting.')
    finally:
        await app.exit()
        logging.info('exited.')


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.getLogger('pymodbus').setLevel(logging.INFO)
    logging.getLogger('gmqtt').setLevel(logging.ERROR)
    logging.info('starting SungrowModbus2Mqtt v%s.', __version__)
    asyncio.run(main())
