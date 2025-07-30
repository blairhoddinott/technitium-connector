import argparse
import json
import logging
import redis
import requests
import structlog
import os
import sys

from urllib3.exceptions import InsecureRequestWarning
from dotenv import load_dotenv
from structlog import get_logger


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


def add_dns_record(zone, record_name, record_type, value=None, ip=None, ttl=60):
    if record_type == "A" or record_type == "AAAA":
        if ip is None:
            log.critical(
                "Must provide an IP address for this record type",
                record_type=record_type
            )
            sys.exit(1)

        payload = {
            "zone": zone,
            "name": record_name,
            "type": record_type,
            "ttl": ttl,
            "overwrite": True,
            "rdata": [ip]
        }

    if record_type == "CNAME":
        payload = {
            "zone": zone,
            "name": record_name,
            "type": record_type,
            "ttl": ttl,
            "overwrite": True,
            "rdata": value
        }

    if record_type.upper() == "TXT":
        payload = f"{API_URL}/zones/records/add?" \
                  f"token={API_TOKEN}" \
                  f"&domain={record_name}.{zone}" \
                  f"&zone={zone}" \
                  f"&type={record_type}" \
                  f"&text={value}"

    if record_type not in VALID_RECORD_TYPES:
        log.critical(
            "Must select a valid record type",
            valid_records=VALID_RECORD_TYPES
        )
        sys.exit(1)

    log.info("Adding record to Technitium", payload=payload)
    log.info("", payload=payload)
    response = requests.post(payload, verify=False)
    log.info("Add Record Response:", response=response.json())


def delete_dns_record(zone, record, ip):
    payload = {
        "zone": zone,
        "name": record,
        "type": "A",
        "rdata": [ip]
    }
    log.info("", payload=payload)

    response = requests.post(f"{API_URL}/zones/records/delete", verify=False)
    print("Delete Record Response:", response.json())


def list_zone_records(zone):
    response = requests.get(
        f"{API_URL}/zones/records/get?domain={zone}&zone={zone}&token={API_TOKEN}&listZone=true",
        verify=False
    )
    data = response.json()

    if data.get("status") == "ok":
        records = data.get("response", {}).get("records", [])
        log.debug("Raw data", records=data)
        log.info(f"Records for {zone}:")
        for record in records:
            log.info("Record: ", name=record["name"], type=record["type"],
                data=record["rData"])
    else:
        log.warn(
            "Failed to fetch records:",
            status_code=response.status_code,
            error_message=data["errorMessage"]
        )


def get_from_redis():
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=4)
    if r.exists(REDIS_KEY):
        record_dict = json.loads(r.get(REDIS_KEY))
        record_dict["records"] = list(sum(record_dict["records"], []))
        log.debug("specific info", received_records=record_dict["records"])
        for entry in record_dict["records"]:
            log.debug("", record=entry)
        # r.delete(REDIS_KEY)
        return record_dict
    else:
        log.warn("Key not found in Redis", key=REDIS_KEY)


def run():
    if args.list_zone:
        list_zone_records(args.domain)

    if args.use_redis:
        records = get_from_redis()

    if args.add_record:
        if args.use_redis:
            log.info("Adding record from redis", records=records["records"])
            for record in records["records"]:
                if record["type"] == "TXT" or record["type"] == "CNAME":
                    add_dns_record(
                        args.domain,
                        record["name"],
                        record["type"],
                        value=record["value"]
                    )
                elif record["type"] == "A" or record["type"] == "AAAA":
                    add_dns_record(args.domain, record["name"], record["type"], ip=record["value"])
        else:
            log.info("adding record manually")

    # Delete the DNS record
    # delete_dns_record(zone_name, record_name, record_ip)


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
