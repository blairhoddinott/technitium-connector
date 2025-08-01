import argparse
import logging
import requests
import structlog
import os
import sys
import time

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
    validate_environment()

    dns = TechnitiumDNS(API_URL, API_TOKEN, REDIS_HOST)
    while True:
        records = dns.get_from_redis()
        if records:
            log.debug("Record found in redis", records=records["records"])
            for record in records["records"]:
                if dns.check_for_dns_record(
                    args.domain,
                    record["name"],
                    record["type"],
                    record["value"]
                ):
                    log.info("DNS record found, Running validation check")
                    if dns.check_for_validation_complete():
                        log.info(
                            "Validation complete, removing TXT record from DNS",
                            record=record
                        )
                        if dns.delete_dns_record(args.domain, record["name"], record["type"],
                                                record["value"]):
                            log.info("Removing record from redis")
                            if dns.remove_records_from_redis():
                                log.info("Records removed, validation loop completed.")
                        else:
                            log.warn("error removing DNS record")
                    else:
                        log.debug(
                            "Validation in progress or otherwise not ready to clean out records"
                        )
                else:
                    log.info("Adding record from redis", records=records["records"])
                    for record in records["records"]:
                        dns.add_dns_record(
                            args.domain,
                            record["name"],
                            record["type"],
                            record["value"]
                        )

        time.sleep(300)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="A service that monitors for required changes to DNS"
    )
    parser.add_argument(
        "-d",
        "--domain",
        action="store",
        required=True,
        help="The domain you wish to query within Namecheap"
    )
    parser.add_argument(
        "-v",
        "--debug",
        action="store_true",
        help="Turns on debug logging"
    )
    args = parser.parse_args()
    if args.debug:
        structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),)
    else:
        structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),)

    run()
