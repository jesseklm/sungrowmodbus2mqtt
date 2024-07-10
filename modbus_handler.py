import logging
from time import sleep

from pymodbus.exceptions import ConnectionException
from SungrowModbusTcpClient.SungrowModbusTcpClient import SungrowModbusTcpClient

from config import config


class ModbusHandler:
    def __init__(self):
        self.modbus_client = SungrowModbusTcpClient(host=config['ip'], port=config.get('port', 502), timeout=10,
                                                    retries=1)
        if self.modbus_client.connect():
            logging.info('modbus connected.')

    def reconnect(self):
        while True:
            try:
                connected = self.modbus_client.connect()
            except (ConnectionResetError, ConnectionException) as e:
                logging.error(f'connect failed: {e}.')
                connected = False
            if connected:
                break
            sleep(1)

    def read(self, table, address, count):
        while True:
            try:
                if table == 'holding':
                    result = self.modbus_client.read_holding_registers(address, count, unit=0x01)
                elif table == 'input':
                    result = self.modbus_client.read_input_registers(address, count, unit=0x01)
                else:
                    raise Exception('Invalid table')
            except (ConnectionResetError, ConnectionException) as e:
                logging.error(f'read failed: {e}.')
                self.reconnect()
                continue
            return result.registers

    def close(self):
        self.modbus_client.close()
        logging.info('modbus closed.')
