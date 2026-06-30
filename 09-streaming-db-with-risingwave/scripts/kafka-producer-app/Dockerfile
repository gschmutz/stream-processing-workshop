FROM python:3.11-slim

RUN pip install --no-cache-dir kafka-python==2.0.2

WORKDIR /app

COPY scripts/docker/kafka-producer-app/run-producers.py .
COPY scripts/docker/kafka-producer-app/energy-consumed.py .
COPY scripts/docker/kafka-producer-app/energy-produced.py .

CMD ["python3", "run-producers.py"]
