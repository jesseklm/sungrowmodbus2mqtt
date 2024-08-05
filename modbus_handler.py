import logging
from time import sleep

from pymodbus.exceptions import ConnectionException
from SungrowModbusTcpClient.SungrowModbusTcpClient import SungrowModbusTcpClient

from config import config


class ModbusHandler:
    def __init__(self):
        self.host = config['ip']
        self.port = config.get('port', 502)
        self.slave_id = config.get('slave_id', 0x1)
        self.modbus_client = SungrowModbusTcpClient(host=self.host, port=self.port, timeout=10, retries=1)
        self.reconnect(first_connect=True)

    def reconnect(self, first_connect=False):
        while True:
            try:
                connected = self.modbus_client.connect()
            except (ConnectionResetError, ConnectionException) as e:
                logging.error(f'modbus connect to {self.host}:{self.port} failed: {e}.')
                connected = False
            if connected:
                logging.info('modbus connected.' if first_connect else 'modbus reconnected.')
                break
            sleep(1)

    def read(self, table, address, count):
        while True:
            try:
                if table == 'holding':
                    result = self.modbus_client.read_holding_registers(address, count, self.slave_id)
                elif table == 'input':
                    result = self.modbus_client.read_input_registers(address, count, self.slave_id)
                else:
                    raise Exception('Invalid table')
            except (ConnectionResetError, ConnectionException) as e:
                logging.error(f'modbus read failed: {e}.')
                self.reconnect()
                continue
            return result.registers

    def close(self):
        self.modbus_client.close()
        logging.info('modbus closed.')
