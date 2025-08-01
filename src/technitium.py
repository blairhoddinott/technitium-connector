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
        self.REDIS_VALIDATION_KEY = "validation_complete"

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

    def check_for_dns_record(self, zone, record_name, record_type, value):
        response = requests.get(
            f"{self.API_URL}/zones/records/get"
            f"?domain={record_name}.{zone}"
            f"&zone={zone}"
            f"&token={self.API_TOKEN}",
            verify=False
        )
        try:
            data = response.json()
        except Exception as e:
            log.critical("Unable to process response", exception=e, response=response)
            return False

        if data.get("status") == "ok":
            records = data.get("response", {}).get("records", [])
            log.debug("Raw data", records=data)
            if not records:
                log.debug("DNS record not found")
                return False
            else:
                log.debug("", records=records)
                for record in records:
                    log.info("Record found", name=record["name"], type=record["type"],
                        data=record["rData"])
                return True
        else:
            log.warn(
                "Failed to fetch records:",
                status_code=response.status_code,
                error_message=data["errorMessage"]
            )
            return False

    def delete_dns_record(self, zone, record_name, record_type, value):
        if record_type == "A" or record_type == "AAAA":
            payload = f"{self.API_URL}/zones/records/delete" \
                      f"?token={self.API_TOKEN}" \
                      f"&domain={record_name}.{zone}" \
                      f"&zone={zone}" \
                      f"&type={record_type}" \
                      f"&ipAddress={value}"

        if record_type == "CNAME":
            payload = f"{self.API_URL}/zones/records/delete" \
                      f"?token={self.API_TOKEN}" \
                      f"&domain={record_name}.{zone}" \
                      f"&zone={zone}" \
                      f"&type={record_type}" \
                      f"&cname={value}"

        if record_type == "TXT":
            payload = f"{self.API_URL}/zones/records/delete" \
                      f"?token={self.API_TOKEN}" \
                      f"&domain={record_name}.{zone}" \
                      f"&zone={zone}" \
                      f"&type={record_type}" \
                      f"&text={value}"

        log.debug("", payload=payload)

        response = requests.post(payload, verify=False)
        if response.json()["status"] != "ok":
            log.info("Error deleting record:", response=response.json())
            return False
        else:
            log.info("Removed record")
            return True

    def list_zone_records(self, zone):
        response = requests.get(
            f"{self.API_URL}/zones/records/get"
            f"?domain={zone}"
            f"&zone={zone}"
            f"&token={self.API_TOKEN}"
            f"&listZone=true",
            verify=False
        )
        try:
            data = response.json()
        except Exception as e:
            log.critical("Unable to process response", exception=e, response=response)

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

        return None

    def check_for_validation_complete(self):
        """
        This function checks the redis key for validation completion.
        If this is set to true, it will delete the record in DNS and then unset the redis keys.
        This is part of my split-brain DNS validation issue, not likely to be of use to others
        """
        r = redis.Redis(host=self.REDIS_HOST, port=self.REDIS_PORT, db=self.REDIS_DB)
        if r.exists(self.REDIS_VALIDATION_KEY):
            validation_complete = bool(int(r.get(self.REDIS_VALIDATION_KEY)))
            log.debug("validation status", is_validation_complete=validation_complete)
            if validation_complete:
                return True
        else:
            log.debug("validation key is not set")
        return False

    def remove_records_from_redis(self):
        r = redis.Redis(host=self.REDIS_HOST, port=self.REDIS_PORT, db=self.REDIS_DB)
        if r.exists(self.REDIS_KEY):
            try:
                r.delete(self.REDIS_KEY)
            except Exception as e:
                log.critical("Error removing redis key", exception=e, key=self.REDIS_KEY)
                return False
        else:
            log.debug("Redis key is not set", key=self.REDIS_KEY)

        if r.exists(self.REDIS_VALIDATION_KEY):
            try:
                r.delete(self.REDIS_VALIDATION_KEY)
            except Exception as e:
                log.critical(
                    "Error removing redis key",
                    excpetion=e,
                    key=self.REDIS_VALIDATION_KEY
                )
                return False
        else:
            log.debug("Redis key is not set", key=self.REDIS_VALIDATION_KEY)

        return True
