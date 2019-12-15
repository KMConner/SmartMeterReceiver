import logging
import time
from argparse import ArgumentParser

import prometheus_client
from prometheus_client import Gauge
from smart_meter_connection import SmartMeterConnection


def main():
    logging.basicConfig(level=logging.DEBUG)
    parser: ArgumentParser = ArgumentParser()
    parser.add_argument("--id", dest='id', type=str, required=True)
    parser.add_argument("--key", dest='key', type=str, required=True)
    parser.add_argument("--dev", dest='dev', type=str, required=False, default='/dev/ttyS0')
    args = parser.parse_args()
    gauge = None
    with SmartMeterConnection(args.dev, args.id, args.key) as conn:
        conn.initialize_params()
        while True:
            data = conn.get_data()
            if data is None:
                print('Failed to get data !')
                continue
            if not gauge:
                gauge = Gauge('power_consumption', 'Power consumption in W')
            gauge.set(data)
            print(f'Current power consumption: {data} W')
            time.sleep(7)


if __name__ == '__main__':
    prometheus_client.start_http_server(8000)
    main()
