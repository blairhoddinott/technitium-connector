FROM ghcr.io/astral-sh/uv:bookworm-slim
COPY . .
ENTRYPOINT [ "/bin/bash", "-c", "uv run src/service.py -d ${DOMAIN}" ]