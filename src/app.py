import logging
import time
from argparse import ArgumentParser

import prometheus_client

from smart_meter_connection import SmartMeterConnection


def main():
    logging.basicConfig(level=logging.INFO)
    parser: ArgumentParser = ArgumentParser()
    parser.add_argument("--id", dest='id', type=str, required=True)
    parser.add_argument("--key", dest='key', type=str, required=True)
    parser.add_argument("--dev", dest='dev', type=str, required=False, default='/dev/ttyS0')
    args = parser.parse_args()
    with SmartMeterConnection(args.dev, args.id, args.key) as conn:
        conn.initialize_params()
        while True:
            data = conn.get_data()
            print(f'Current power consumption: {data} W')
            time.sleep(3)


if __name__ == '__main__':
    prometheus_client.start_http_server(12345)
    main()
