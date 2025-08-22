import asyncio
import logging
from typing import Literal

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusIOException
from pymodbus.pdu import ModbusPDU


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
        self.word_order: Literal["big", "little"] = 'big' if config.get('word_order', 'little') == 'big' else 'little'
        self.modbus_client: AsyncModbusTcpClient = AsyncModbusTcpClient(host=self.host, port=self.port, timeout=10,
                                                                        retries=1)

    async def reconnect(self, first_connect=False) -> None:
        while True:
            try:
                if await self.modbus_client.connect():
                    logging.info('modbus connected.' if first_connect else 'modbus reconnected.')
                    break
            except (ConnectionResetError, ConnectionException) as e:
                logging.error('modbus connect to %s:%s failed: %s.', self.host, self.port, e)
            await asyncio.sleep(1)

    async def read(self, table: str, address: int, count: int) -> list[int] | None:
        while True:
            try:
                if table == 'holding':
                    result: ModbusPDU = await self.modbus_client.read_holding_registers(address, count=count,
                                                                                        slave=self.slave_id)
                elif table == 'input':
                    result: ModbusPDU = await self.modbus_client.read_input_registers(address, count=count,
                                                                                      slave=self.slave_id)
                else:
                    raise Exception('Invalid table')
            except (ConnectionResetError, ConnectionException) as e:
                logging.error('modbus read failed: %s.', e)
                await self.reconnect()
                continue
            except ModbusIOException as e:
                logging.error('modbus read failed: %s.', e)
                continue
            if result.isError():
                logging.error('modbus read failed: %s, table=%s, address=%s, count=%s.', result, table, address, count)
                if not self.modbus_client.connected:
                    await self.reconnect()
                continue
            return result.registers

    async def write(self, table: str, address: int, value: int, datatype: str) -> bool:
        logging.debug('write address: %s, value: %s', address, value)
        encoded_value: list[int] = self.encode(value, datatype)
        if encoded_value:
            return await self.write_registers(table, address, encoded_value)
        else:
            return False

    async def write_registers(self, table: str, address: int, values: list[int]) -> bool:
        logging.debug('write_registers address: %s, values: %s', address, values)
        try:
            if not self.modbus_client.connected:
                await self.reconnect()
            if table == 'holding':
                result = await self.modbus_client.write_registers(address, values, slave=self.slave_id)
            else:
                logging.error('writing to %s not supported.', table)
                return False
            return not result.isError()
        except Exception as e:
            logging.error('modbus write failed: %s, table=%s, address=%s, values=%s. Exception: %s', table, address,
                          values, e)
            return False

    def close(self) -> None:
        self.modbus_client.close()
        logging.info('modbus closed.')

    def encode(self, value: int, datatype: str) -> list[int]:
        try:
            enum_datatype = getattr(AsyncModbusTcpClient.DATATYPE, datatype.upper())
            return AsyncModbusTcpClient.convert_to_registers(value, enum_datatype, self.word_order)
        except AttributeError:
            logging.warning('unknown datatype %s %s.', datatype, value)
            return []

    def decode(self, registers: list[int], datatype: str) -> int | str:
        try:
            enum_datatype = getattr(AsyncModbusTcpClient.DATATYPE, datatype.upper())
            return AsyncModbusTcpClient.convert_from_registers(registers, enum_datatype, self.word_order)
        except AttributeError:
            logging.warning('unknown datatype %s %s.', datatype, registers)
