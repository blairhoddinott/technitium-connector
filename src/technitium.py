import json
import redis
import requests

from urllib3.exceptions import InsecureRequestWarning
from structlog import get_logger


requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
log = get_logger()


class TechnitiumDNS():
    VALID_RECORD_TYPES = [
        "A",
        "AAAA",
        "CNAME",
        "MX",
        "TXT"
    ]

    def __init__(self, api_url, api_token, redis_host, redis_port=6379, redis_key="dns_update",
                 redis_db=4):
        self.API_URL = api_url
        self.API_TOKEN = api_token
        self.REDIS_HOST = redis_host
        self.REDIS_PORT = redis_port
        self.REDIS_KEY = redis_key
        self.REDIS_DB = redis_db

    def add_dns_record(self, zone, record_name, record_type, value, ttl=60):
        if value is None:
            log.critical(
                "Must provide an IP address for this record type",
                record_type=record_type
            )
            raise ValueError

        if record_type == "A" or record_type == "AAAA":
            payload = f"{self.API_URL}/zones/records/add" \
                      f"?token={self.API_TOKEN}" \
                      f"&domain={record_name}.{zone}" \
                      f"&zone={zone}" \
                      f"&type={record_type}" \
                      f"&ipAddress={value}"

        if record_type == "CNAME":
            payload = f"{self.API_URL}/zones/records/add" \
                      f"?token={self.API_TOKEN}" \
                      f"&domain={record_name}.{zone}" \
                      f"&zone={zone}" \
                      f"&type={record_type}" \
                      f"&cname={value}"

        if record_type == "TXT":
            payload = f"{self.API_URL}/zones/records/add" \
                      f"?token={self.API_TOKEN}" \
                      f"&domain={record_name}.{zone}" \
                      f"&zone={zone}" \
                      f"&type={record_type}" \
                      f"&text={value}"

        if record_type not in self.VALID_RECORD_TYPES:
            log.critical(
                "Must select a valid record type",
                valid_records=self.VALID_RECORD_TYPES
            )
            raise ValueError

        log.info("Adding record to Technitium", payload=payload)
        response = requests.post(payload, verify=False)
        if response.json()["status"] != "ok":
            log.info("Error adding record:", response=response.json())
        else:
            log.info("Added record", added_record=response.json()["response"]["addedRecord"])

    # TODO:
    # def delete_dns_record(self, zone, record, ip):
    #     payload = {
    #         "zone": zone,
    #         "name": record,
    #         "type": "A",
    #         "rdata": [ip]
    #     }
    #     log.info("", payload=payload)

    #     response = requests.post(f"{self.API_URL}/zones/records/delete", verify=False)
    #     log.info("Delete Record Response:", response.json())

    def list_zone_records(self, zone):
        response = requests.get(
            f"{self.API_URL}/zones/records/get"
            f"?domain={zone}"
            f"&zone={zone}"
            f"&token={self.API_TOKEN}"
            f"&listZone=true",
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

    def get_from_redis(self):
        r = redis.Redis(host=self.REDIS_HOST, port=self.REDIS_PORT, db=self.REDIS_DB)
        if r.exists(self.REDIS_KEY):
            record_dict = json.loads(r.get(self.REDIS_KEY))
            record_dict["records"] = list(sum(record_dict["records"], []))
            log.debug("specific info", received_records=record_dict["records"])
            for entry in record_dict["records"]:
                log.debug("", record=entry)
            return record_dict
        else:
            log.warn("Key not found in Redis", key=self.REDIS_KEY)
