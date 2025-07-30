import requests
import json


from urllib3.exceptions import InsecureRequestWarning

# Suppress only InsecureRequestWarning
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)


# Your Technitium DNS server details
API_URL = "https://dns.weepynet.com/api"
API_TOKEN = "4b12168172073ff8b7c75df6b711d15bdcb34910c5a582ca8914068a108ae065"

# Common headers
headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

# Zone and record details
zone_name = "weepynet.com."
record_name = "gaaaayyyyyy.weepynet.com"
record_ip = "192.168.1.50"
ttl = 3600  # 1 hour TTL


def add_dns_record(zone, record, ip, ttl):
    payload = {
        "zone": zone,
        "name": record,
        "type": "A",
        "ttl": ttl,
        "overwrite": True,  # overwrite existing record if exists
        "rdata": [ip]
    }

    response = requests.post(f"{API_URL}/zones/records/add", headers=headers, json=payload)
    print("Add Record Response:", response.json())


def delete_dns_record(zone, record, ip):
    payload = {
        "zone": zone,
        "name": record,
        "type": "A",
        "rdata": [ip]
    }

    response = requests.post(f"{API_URL}/zones/records/delete", headers=headers, json=payload)
    print("Delete Record Response:", response.json())


def list_zone_records(zone):
    response = requests.get(
        f"{API_URL}/zones/records/get?domain={zone}&zone={zone}&token={API_TOKEN}&listZone=true",
        verify=False
    )
    data = response.json()

    if data.get("status") == "ok":
        records = data.get("response", {}).get("records", [])
        # print(json.dumps(records, indent=4))
        # print(data)
        print(f"Records for {zone}:")
        for record in records:
            print(
                f"{record['name']} - "
                f"{record['type']} - "
                f"{record['rData']}"
            )
    else:
        print("Failed to fetch records:", data)


if __name__ == "__main__":
    # Add a new DNS record
    # add_dns_record(zone_name, record_name, record_ip, ttl)

    # List all DNS records in the zone
    list_zone_records(zone_name)

    # Delete the DNS record
    # delete_dns_record(zone_name, record_name, record_ip)