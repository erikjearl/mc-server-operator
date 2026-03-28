FROM python:3.11-slim

LABEL org.opencontainers.image.source="https://github.com/erikjearl/mc-server-operator"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY helpers.py .
COPY main.py .

CMD ["kopf", "run", "main.py", "--all-namespaces", "--verbose"]