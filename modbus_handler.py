import logging
from asyncio import sleep

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ConnectionException

from config import config


class ModbusHandler:
    def __init__(self):
        self.host = config['ip']
        self.port = config.get('port', 502)
        self.slave_id = config.get('slave_id', 0x1)
        self.modbus_client = AsyncModbusTcpClient(host=self.host, port=self.port, timeout=10, retries=1)

    async def reconnect(self, first_connect=False):
        while True:
            try:
                connected = await self.modbus_client.connect()
            except (ConnectionResetError, ConnectionException) as e:
                logging.error(f'modbus connect to {self.host}:{self.port} failed: {e}.')
                connected = False
            if connected:
                logging.info('modbus connected.' if first_connect else 'modbus reconnected.')
                break
            await sleep(1)

    async def read(self, table, address, count):
        while True:
            try:
                if table == 'holding':
                    result = await self.modbus_client.read_holding_registers(address, count, self.slave_id)
                elif table == 'input':
                    result = await self.modbus_client.read_input_registers(address, count, self.slave_id)
                else:
                    raise Exception('Invalid table')
            except (ConnectionResetError, ConnectionException) as e:
                logging.error(f'modbus read failed: {e}.')
                await self.reconnect()
                continue
            return result.registers

    def close(self):
        self.modbus_client.close()
        logging.info('modbus closed.')
