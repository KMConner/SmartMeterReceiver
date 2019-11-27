import logging
import time
from typing import Optional, Tuple

from serial import Serial


class SmartMeterConnection:
    def __init__(self, dev: str, rb_id: str, key: str):
        self.__dev = dev
        self.__id = rb_id
        self.__key = key
        self.__serial_logger = logging.getLogger('connection')
        self.__logger = logging.getLogger(__name__)

    def run(self):
        with Serial(self.__dev, 115200) as connection:
            version = self.__check_version(connection)
            self.__logger.info(f'Version: {version}')
            self.__set_password(connection, self.__key)
            self.__set_id(connection, self.__id)
            channel, pan_id, addr = self.__scan(connection)
            self.__logger.info(f'Channel: {channel}, Pan ID: {pan_id}, Addr; {addr}')
            self.__set_reg(connection, 'S2', channel)
            self.__set_reg(connection, 'S3', pan_id)
            link_local_addr = self.__get_ip_from_mac(connection, addr)
            self.__logger.info(f'IPv6 Link Local: {link_local_addr}')
            self.__connect(connection, link_local_addr)
            self.__logger.info(f'Connected to {link_local_addr} !')
            connection.timeout = 2
            while True:
                data = self.__get_data(connection, link_local_addr)
                self.__logger.info(f'Current power consumption: {data} W')
                time.sleep(3)

    def __write_line_serial(self, connection: Serial, line: str) -> None:
        if line.startswith('SKSETPWD'):
            parts = line.split(' ', 3)
            parts[2] = '*' * len(parts[2])
            self.__serial_logger.debug(f'Send: {parts[0]} {parts[1]} {parts[2]}')
        else:
            self.__serial_logger.debug(f'Send: {line}')
        connection.write((line + '\r\n').encode('utf-8'))
        self.__serial_logger.debug('Echo back: ' + str(connection.readline()))

    def __send_udp_serial(self, connection: Serial, addr: str, data: bytes) -> None:
        head = f'SKSENDTO 1 {addr} 0E1A 1 {len(data):04X} '
        data = head.encode('ascii') + data
        self.__serial_logger.debug(b'Send: ' + data)
        connection.write(data)
        echo_back = connection.readline()
        while echo_back != head.encode('ascii') + b'\r\n':
            self.__serial_logger.info('Received Different: ' + str(echo_back))
            echo_back = connection.readline()
        self.__serial_logger.debug('Echo back: ' + str(echo_back))

    def __read_line_serial(self, connection: Serial) -> str:
        text = connection.readline().decode('utf-8')[:-2]
        if text.startswith('SKSETPWD'):
            parts = text.split(' ', 3)
            parts[2] = '*' * len(parts[2])
            self.__serial_logger.debug(f'Receive: {parts[0]} {parts[1]} {parts[2]}')
        else:
            self.__serial_logger.debug(f'Receive: {text}')
        return text

    def __check_version(self, conn: Serial) -> str:
        self.__write_line_serial(conn, 'SKVER')
        ever = self.__read_line_serial(conn)
        self.__read_line_serial(conn)
        ret = ever.split(' ', 2)
        return ret[1]

    def __set_password(self, conn: Serial, key: str):
        self.__write_line_serial(conn, f'SKSETPWD C {key}')
        assert self.__read_line_serial(conn) == 'OK'

    def __set_id(self, conn: Serial, rb_id: str):
        self.__write_line_serial(conn, f'SKSETRBID {rb_id}')
        assert self.__read_line_serial(conn) == 'OK'

    def __scan(self, conn: Serial) -> Tuple[str, str, str]:
        for duration in range(4, 10):
            self.__logger.debug(f'Start scanning with duration {duration}')
            self.__write_line_serial(conn, f'SKSCAN 2 FFFFFFFF {duration}')
            scan_res = {}
            while True:
                line = self.__read_line_serial(conn)
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

    def __set_reg(self, conn: Serial, reg_name: str, value: str) -> None:
        self.__write_line_serial(conn, f'SKSREG {reg_name} {value}')
        assert self.__read_line_serial(conn) == 'OK'

    def __get_ip_from_mac(self, conn: Serial, addr: str) -> str:
        self.__write_line_serial(conn, f'SKLL64 {addr}')
        return self.__read_line_serial(conn)

    def __connect(self, conn: Serial, addr: str) -> None:
        self.__write_line_serial(conn, f'SKJOIN {addr}')
        while True:
            line = self.__read_line_serial(conn)
            if line.startswith('EVENT 24'):
                raise RuntimeError('Failed to connect !')
            elif line.startswith('EVENT 25'):
                self.__read_line_serial(conn)
                return

    def __get_data(self, conn: Serial, addr: str) -> Optional[int]:
        request_str = b'\x10\x81\x00\x01\x05\xFF\x01\x02\x88\x01\x62\x01\xE7\x00'
        self.__send_udp_serial(conn, addr, request_str)
        assert self.__read_line_serial(conn).startswith('EVENT 21')
        assert self.__read_line_serial(conn) == 'OK'
        event = self.__read_line_serial(conn)

        if event.startswith('ERXUDP'):
            parts = event.split(' ')
            assert len(parts) == 9
            packet = parts[8]
            e_data = packet[8:]
            seoj = e_data[0:6]
            esv = e_data[12:14]
            epc = e_data[16:18]
            if seoj == '028801' and esv == '72' and epc == 'E7':
                return int(e_data[-8:], 16)
        return None
