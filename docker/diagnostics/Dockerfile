FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY src/clinique/prescreen/diagnostics.py /app/diagnostics.py

ENTRYPOINT ["python", "/app/diagnostics.py"]
