# technitium-connector

## Overview

This is a python utility to connect to Technitium DNS server and manage DNS records. 

This is the other side of the [namecheap-connector](https://github.com/blairhoddinott/namecheap-connector)

## Using this tool

### Docker

I have created a Docker implementation. This make deploying this easier. 

I have attached a docker-compose.yaml file. The environment variables must be set prior to launching. You will need the following information:

- DOMAIN
This is the top level domain you are looking for in namecheap (e.g. weepynet.com). This is the domain name you are looking to generate LetsEncrypt certs for
- DOMAIN=DOMAIN.COM
- API_URL
This is the URL to your technitium DNS server. Replace the address portion, but make sure it ends with /api as this is needed to hit the API correctly
- API_TOKEN
This is the API token you make for your user in Technitium
- REDIS_HOST
This is the address for the Redis host you are using as part of this implementation

Once this has been filled out, you should be able to just `docker compose up -d` the file. You can check the logs with `docker logs technitium-connector` to make sure there are no errors.