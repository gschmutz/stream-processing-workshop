#!/usr/bin/env python3
"""
Reads raw JSON energy-monitoring messages from Kafka, flattens the nested
'values' object using plain Python dict manipulation, and produces
Avro-serialised records to the energy-monitoring topic via the Confluent
Schema Registry.

Usage:
    pip install -r requirements.txt
    python flatten_plain.py
"""

import json

from confluent_kafka import Consumer, KafkaException, Producer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer
from confluent_kafka.serialization import MessageField, SerializationContext

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

KAFKA_BROKER = "kafka-1:19092"
SOURCE_TOPIC = "energy-monitoring-raw"
SINK_TOPIC = "energy-monitoring"
SCHEMA_REGISTRY_URL = "http://dataplatform:8081"
SCHEMA_SUBJECT = "energy-monitoring-value"
CONSUMER_GROUP = "energy-flatten-plain-cg"

# ---------------------------------------------------------------------------
# Transformation
# ---------------------------------------------------------------------------

def flatten(raw: dict) -> dict:
    """Promote every key inside 'values' to the top level and drop the wrapper."""
    result = {k: v for k, v in raw.items() if k != "values"}
    result.update(raw.get("values", {}))
    return result

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    schema_registry = SchemaRegistryClient({"url": SCHEMA_REGISTRY_URL})
    schema_str = schema_registry.get_latest_version(SCHEMA_SUBJECT).schema.schema_str
    print(f"Fetched schema '{SCHEMA_SUBJECT}' from registry.")
    avro_serializer = AvroSerializer(schema_registry, schema_str)

    consumer = Consumer({
        "bootstrap.servers": KAFKA_BROKER,
        "group.id": CONSUMER_GROUP,
        "auto.offset.reset": "earliest",
    })
    consumer.subscribe([SOURCE_TOPIC])

    producer = Producer({"bootstrap.servers": KAFKA_BROKER})

    print(f"Consuming '{SOURCE_TOPIC}' → producing Avro to '{SINK_TOPIC}' ...")
    print("Press Ctrl-C to stop.\n")

    try:
        while True:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue
            if msg.error():
                raise KafkaException(msg.error())

            raw = json.loads(msg.value())
            flat = flatten(raw)

            avro_bytes = avro_serializer(
                flat,
                SerializationContext(SINK_TOPIC, MessageField.VALUE),
            )
            producer.produce(
                SINK_TOPIC,
                key=str(flat.get("factory_id", "")),
                value=avro_bytes,
                on_delivery=lambda err, m: print(f"  ERROR: {err}") if err else None,
            )
            producer.poll(0)
            print(f"  factory_id={flat['factory_id']}  ts={flat['timestamp']}  "
                  f"heating={flat.get('heating_equipment')} kWh")

    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        consumer.close()
        producer.flush()


if __name__ == "__main__":
    main()
