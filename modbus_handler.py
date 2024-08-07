import logging
from time import sleep

from pymodbus.client import ModbusTcpClient
from pymodbus.constants import Endian
from pymodbus.exceptions import ConnectionException
from pymodbus.payload import BinaryPayloadDecoder
from SungrowModbusTcpClient.SungrowModbusTcpClient import SungrowModbusTcpClient

from config import config


class ModbusHandler:
    def __init__(self):
        self.host = config['ip']
        self.port = config.get('port', 502)
        self.slave_id = config.get('slave_id', 0x1)
        self.byte_order = Endian.BIG if config.get('byte_order', 'big') == 'big' else Endian.LITTLE
        self.word_order = Endian.BIG if config.get('word_order', 'little') == 'big' else Endian.LITTLE
        if config.get('sungrow_encrypted', False):
            self.modbus_client = SungrowModbusTcpClient(host=self.host, port=self.port, timeout=10, retries=1)
        else:
            self.modbus_client = ModbusTcpClient(host=self.host, port=self.port, timeout=10, retries=1)
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

    def decode(self, registers: list[int], datatype: str):
        decoder = BinaryPayloadDecoder.fromRegisters(registers, byteorder=self.byte_order, wordorder=self.word_order)
        if datatype == 'uint16':
            return decoder.decode_16bit_uint()
        elif datatype == 'int16':
            return decoder.decode_16bit_int()
        elif datatype == 'uint32':
            return decoder.decode_32bit_uint()
        elif datatype == 'int32':
            return decoder.decode_32bit_int()
        logging.warning(f'unknown datatype {datatype} {registers}.')
