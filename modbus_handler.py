from time import sleep

from pymodbus.exceptions import ConnectionException
from SungrowModbusTcpClient.SungrowModbusTcpClient import SungrowModbusTcpClient

from config import config


class ModbusHandler:
    def __init__(self):
        self.modbus_client = SungrowModbusTcpClient(host=config['ip'], port=config['port'], timeout=10, retries=1)
        if self.modbus_client.connect():
            print('modbus connected.')

    def reconnect(self):
        while True:
            try:
                connected = self.modbus_client.connect()
            except (ConnectionResetError, ConnectionException) as e:
                print(e)
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
            except ConnectionResetError as e:
                print(e)
                self.reconnect()
                continue
            return result.registers

    def close(self):
        self.modbus_client.close()
        print('modbus closed.')
