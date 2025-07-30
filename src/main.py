import argparse
import logging
import requests
import structlog
import os
import sys

from urllib3.exceptions import InsecureRequestWarning
from dotenv import load_dotenv
from structlog import get_logger
from technitium import TechnitiumDNS


requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso", utc=False),
        structlog.processors.add_log_level,
        structlog.dev.ConsoleRenderer(),
    ]
)
log = get_logger()
load_dotenv()

API_URL = os.getenv("API_URL")
API_TOKEN = os.getenv("API_TOKEN")
REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")
REDIS_KEY = os.getenv("REDIS_KEY", "dns_update")
REDIS_PORT = os.getenv("REDIS_PORT", 6379)
REDIS_DB = os.getenv("REDIS_DB", 4)
VALID_RECORD_TYPES = [
    "A",
    "AAAA",
    "CNAME",
    "MX",
    "TXT"
]


def validate_environment():
    if API_URL is None or API_TOKEN is None:
        log.critical(
            "Confirm the .env file has been populated.",
            API_URL=API_URL,
            API_TOKEN=API_TOKEN,
            REDIS_HOST=REDIS_HOST,
            REDIS_PORT=REDIS_PORT
        )
        sys.exit(1)


def run():
    dns = TechnitiumDNS(API_URL, API_TOKEN, REDIS_HOST)
    if args.list_zone:
        dns.list_zone_records(args.domain)

    if args.use_redis:
        records = dns.get_from_redis()

    if args.add_record:
        if args.use_redis:
            log.info("Adding record from redis", records=records["records"])
            for record in records["records"]:
                dns.add_dns_record(
                    args.domain,
                    record["name"],
                    record["type"],
                    record["value"]
                )
        else:
            log.info("adding record manually")
            log.debug("", record_type=args.record_type)
            dns.add_dns_record(
                args.domain,
                args.name,
                args.record_type,
                args.value
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="A utility for interacting with the Technitium DNS server API"
    )
    parser.add_argument(
        "-d",
        "--domain",
        action="store",
        required=True,
        help="The domain you wish to query within Namecheap"
    )
    parser.add_argument(
        "-a",
        "--add_record",
        action="store_true",
        help="Add a record to the specified zone"
    )
    parser.add_argument(
        "-g",
        "--get_record_type",
        action="store",
        help=f"Get records of specified type. Valid types are {VALID_RECORD_TYPES}"
    )
    parser.add_argument(
        "-l",
        "--list_zone",
        action="store_true",
        help="Lists all records from the specified zone"
    )
    parser.add_argument(
        "-n",
        "--name",
        action="store",
        help="Name for the record you wish to create"
    )
    parser.add_argument(
        "-r",
        "--use_redis",
        action="store_true",
        help="If you wish to store the results of a query in Redis, use this flag. "
             "Redis info is populated from the .env file"
    )
    parser.add_argument(
        "-t",
        "--record_type",
        action="store",
        help="Type of record to query the zone for. "
             "If this is not set, all record types will be returned"
    )
    parser.add_argument(
        "-v",
        "--debug",
        action="store_true",
        help="Turns on debug logging"
    )
    parser.add_argument(
        "--value",
        action="store",
        help="Value for the record you are trying to create"
    )
    args = parser.parse_args()
    if args.debug:
        structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),)
    else:
        structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),)

    if args.add_record:
        if args.use_redis:
            log.debug("Loading records from Redis to be added")
        else:
            if args.record_type is None:
                log.critical(
                    "You must specify a record type if you are using the -a flag to add a record"
                )
                sys.exit(1)
            else:
                args.record_type = args.record_type.upper()
                if args.name is None:
                    log.critical(
                        "You must specify a name for the new record if you are using the "
                        "-a flag to add a record"
                    )
                    sys.exit(1)
                else:
                    if args.value is None:
                        log.critical(
                            "You must specify a record value for the new recored if you are "
                            "using the -a flag to add a record"
                        )
                        sys.exit(1)
    run()
