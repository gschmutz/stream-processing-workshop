FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY flatten_plain.py .

ENV KAFKA_BROKER=kafka-1:19092
ENV SOURCE_TOPIC=energy-monitoring.raw
ENV SINK_TOPIC=energy-monitoring.avro
ENV SCHEMA_REGISTRY_URL=http://schema-registry-1:8081
ENV SCHEMA_SUBJECT=energy-monitoring.avro-value
ENV CONSUMER_GROUP=energy-flatten-plain-cg

CMD ["python", "flatten_plain.py"]
