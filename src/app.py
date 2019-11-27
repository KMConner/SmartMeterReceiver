import logging
from argparse import ArgumentParser

from smart_meter_connection import SmartMeterConnection


def main():
    logging.basicConfig(level=logging.INFO)
    parser: ArgumentParser = ArgumentParser()
    parser.add_argument("--id", dest='id', type=str, required=True)
    parser.add_argument("--key", dest='key', type=str, required=True)
    parser.add_argument("--dev", dest='dev', type=str, required=False, default='/dev/ttyS0')
    args = parser.parse_args()
    conn = SmartMeterConnection(args.dev, args.id, args.key)
    conn.run()


if __name__ == '__main__':
    main()
