import logging
from typing import Optional, Tuple

from serial import Serial


class SmartMeterConnection:
    def __init__(self, dev: str, rb_id: str, key: str):
        self.__dev = dev
        self.__id = rb_id
        self.__key = key
        self.__serial_logger = logging.getLogger('connection')
        self.__logger = logging.getLogger(__name__)
        self.__connection: Optional[Serial] = None
        self.__link_local_addr: Optional[str] = None

    def connect(self):
        self.__connection = Serial(self.__dev, 115200)

    def close(self):
        self.__connection.close()
        self.__connection = None

    def initialize_params(self):
        if not self.__connection:
            raise Exception('Connection is not initialized')
        version = self.__check_version()
        self.__logger.info(f'Version: {version}')
        self.__set_password(self.__key)
        self.__set_id(self.__id)
        channel, pan_id, addr = self.__scan()
        self.__logger.info(f'Channel: {channel}, Pan ID: {pan_id}, Addr; {addr}')
        self.__set_reg('S2', channel)
        self.__set_reg('S3', pan_id)
        link_local_addr = self.__get_ip_from_mac(addr)
        self.__logger.info(f'IPv6 Link Local: {link_local_addr}')
        self.__connect(link_local_addr)
        self.__logger.info(f'Connected to {link_local_addr} !')
        self.__link_local_addr = link_local_addr

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __write_line_serial(self, line: str) -> None:
        if line.startswith('SKSETPWD'):
            parts = line.split(' ', 3)
            parts[2] = '*' * len(parts[2])
            self.__serial_logger.debug(f'Send: {parts[0]} {parts[1]} {parts[2]}')
        else:
            self.__serial_logger.debug(f'Send: {line}')
        self.__connection.write((line + '\r\n').encode('utf-8'))
        self.__serial_logger.debug('Echo back: ' + str(self.__connection.readline()))

    def __send_udp_serial(self, addr: str, data: bytes) -> None:
        head = f'SKSENDTO 1 {addr} 0E1A 1 {len(data):04X} '
        data = head.encode('ascii') + data
        self.__serial_logger.debug(b'Send: ' + data)
        self.__connection.write(data)
        echo_back = self.__connection.readline()
        while echo_back != head.encode('ascii') + b'\r\n':
            self.__serial_logger.info('Received Different: ' + str(echo_back))
            echo_back = self.__connection.readline()
        self.__serial_logger.debug('Echo back: ' + str(echo_back))

    def __read_line_serial(self) -> str:
        text = self.__connection.readline().decode('utf-8')[:-2]
        if text.startswith('SKSETPWD'):
            parts = text.split(' ', 3)
            parts[2] = '*' * len(parts[2])
            self.__serial_logger.debug(f'Receive: {parts[0]} {parts[1]} {parts[2]}')
        else:
            self.__serial_logger.debug(f'Receive: {text}')
        return text

    def __check_version(self) -> str:
        self.__write_line_serial('SKVER')
        ever = self.__read_line_serial()
        self.__read_line_serial()
        ret = ever.split(' ', 2)
        return ret[1]

    def __set_password(self, key: str):
        self.__write_line_serial(f'SKSETPWD C {key}')
        assert self.__read_line_serial() == 'OK'

    def __set_id(self, rb_id: str):
        self.__write_line_serial(f'SKSETRBID {rb_id}')
        assert self.__read_line_serial() == 'OK'

    def __scan(self) -> Tuple[str, str, str]:
        for duration in range(4, 10):
            self.__logger.debug(f'Start scanning with duration {duration}')
            self.__write_line_serial(f'SKSCAN 2 FFFFFFFF {duration}')
            scan_res = {}
            while True:
                line = self.__read_line_serial()
                if line.startswith('EVENT 22'):
                    if 'Channel' not in scan_res or 'Pan ID' not in scan_res or 'Addr' not in scan_res:
                        break

                    channel = scan_res['Channel']
                    pan_id = scan_res['Pan ID']
                    addr = scan_res['Addr']
                    return channel, pan_id, addr
                elif line.startswith('  '):
                    cols = line.strip().split(':')
                    scan_res[cols[0]] = cols[1]
        raise Exception('Scan Failed')

    def __set_reg(self, reg_name: str, value: str) -> None:
        self.__write_line_serial(f'SKSREG {reg_name} {value}')
        assert self.__read_line_serial() == 'OK'

    def __get_ip_from_mac(self, addr: str) -> str:
        self.__write_line_serial(f'SKLL64 {addr}')
        return self.__read_line_serial()

    def __connect(self, addr: str) -> None:
        self.__write_line_serial(f'SKJOIN {addr}')
        while True:
            line = self.__read_line_serial()
            if line.startswith('EVENT 24'):
                raise RuntimeError('Failed to connect !')
            elif line.startswith('EVENT 25'):
                self.__read_line_serial()
                self.__connection.timeout = 1
                return

    def get_data(self) -> Optional[int]:
        if not self.__connection:
            raise Exception('Connection is not initialized')
        if not self.__link_local_addr:
            raise Exception('Destination address is not set')

        request_str = b'\x10\x81\x00\x01'
        request_str += b'\x05\xFF\x01'
        request_str += b'\x02\x88\x01'
        request_str += b'\x62'
        request_str += b'\x01'
        request_str += b'\xE7\x00'
        self.__send_udp_serial(self.__link_local_addr, request_str)
        assert self.__read_line_serial().startswith('EVENT 21')
        assert self.__read_line_serial() == 'OK'
        event = self.__read_line_serial()

        if event.startswith('ERXUDP'):
            parts = event.split(' ')
            assert len(parts) == 9
            length = int(parts[7], 16)
            assert length * 2 == len(parts[8])
            packet = parts[8]
            e_data = packet[8:]
            seoj = e_data[0:6]
            esv = e_data[12:14]
            epc = e_data[16:18]
            if seoj == '028801' and esv == '72' and epc == 'E7':
                return int(e_data[-8:], 16)
        return None
