import logging
import time
from typing import Callable

from pymodbus.client import ModbusTcpClient
from pymodbus.constants import Endian
from pymodbus.exceptions import ConnectionException
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.pdu import ModbusResponse
from SungrowModbusTcpClient.SungrowModbusTcpClient import SungrowModbusTcpClient


class ModbusHandler:
    WORD_COUNT: dict[str, int] = {
        'uint16': 1,
        'int16': 1,
        'uint32': 2,
        'int32': 2,
        'uint64': 4,
        'int64': 4,
    }

    def __init__(self, config: dict) -> None:
        self.host: str = config['ip']
        self.port: int = config.get('port', 502)
        self.slave_id: int = config.get('slave_id', 0x1)
        self.byte_order: Endian = Endian.BIG if config.get('byte_order', 'big') == 'big' else Endian.LITTLE
        self.word_order: Endian = Endian.BIG if config.get('word_order', 'little') == 'big' else Endian.LITTLE
        modbus_class: type[ModbusTcpClient] = SungrowModbusTcpClient if config.get('sungrow_encrypted',
                                                                                   False) else ModbusTcpClient
        self.modbus_client: ModbusTcpClient = modbus_class(host=self.host, port=self.port, timeout=10, retries=1)

    def reconnect(self, first_connect=False) -> None:
        while True:
            try:
                if self.modbus_client.connect():
                    logging.info('modbus connected.' if first_connect else 'modbus reconnected.')
                    break
            except (ConnectionResetError, ConnectionException) as e:
                logging.error(f'modbus connect to %s:%s failed: %s.', self.host, self.port, e)
            time.sleep(1)

    def read(self, table: str, address: int, count: int) -> list[int]:
        while True:
            try:
                if table == 'holding':
                    result: ModbusResponse = self.modbus_client.read_holding_registers(address, count, self.slave_id)
                elif table == 'input':
                    result: ModbusResponse = self.modbus_client.read_input_registers(address, count, self.slave_id)
                else:
                    raise Exception('Invalid table')
            except (ConnectionResetError, ConnectionException) as e:
                logging.error(f'modbus read failed: %s.', e)
                self.reconnect()
                continue
            if result.isError():
                logging.error(f'modbus read failed: %s, table=%s, address=%s, count=%s.', result, table, address, count)
                if not self.modbus_client.connected:
                    self.reconnect()
                continue
            return result.registers

    def close(self) -> None:
        self.modbus_client.close()
        logging.info('modbus closed.')

    def decode(self, registers: list[int], datatype: str) -> int:
        decoder: BinaryPayloadDecoder = BinaryPayloadDecoder.fromRegisters(registers, byteorder=self.byte_order,
                                                                           wordorder=self.word_order)
        decode_methods: dict[str, Callable[[], int]] = {
            'uint16': decoder.decode_16bit_uint,
            'int16': decoder.decode_16bit_int,
            'uint32': decoder.decode_32bit_uint,
            'int32': decoder.decode_32bit_int,
            'uint64': decoder.decode_64bit_uint,
            'int64': decoder.decode_64bit_int,
        }
        if decode_func := decode_methods.get(datatype):
            return decode_func()
        logging.warning(f'unknown datatype %s %s.', datatype, registers)
