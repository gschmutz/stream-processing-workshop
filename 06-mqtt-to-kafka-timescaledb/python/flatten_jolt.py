#!/usr/bin/env python3
"""
Reads raw JSON energy-monitoring messages from Kafka, flattens the nested
'values' object by interpreting a JOLT 'shift' specification, and produces
Avro-serialised records to the energy-monitoring topic via the Confluent
Schema Registry.

The JOLT spec is defined as a plain Python list of dicts — identical in
structure to what you would paste into the NiFi JoltTransformRecord processor.
A minimal shift-spec interpreter is included so no external JOLT library is
required; it handles direct field mappings and the wildcard '*' → '&' pattern.

Usage:
    pip install -r requirements.txt
    python flatten_jolt.py
"""

import json
from typing import Any

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
CONSUMER_GROUP = "energy-flatten-jolt-cg"

# ---------------------------------------------------------------------------
# JOLT spec
#
# This is the exact same spec used in the NiFi JoltTransformRecord processor.
# The 'shift' operation picks fields from the input and writes them to the
# named output paths.  The nested "values": {"*": "&"} rule lifts every key
# inside 'values' to the top level of the output (& means "use the matched
# key name as-is").
# ---------------------------------------------------------------------------

JOLT_SPEC = [
    {
        "operation": "shift",
        "spec": {
            "factory_id": "factory_id",
            "factory":    "factory",
            "timestamp":  "timestamp",
            "values": {
                "*": "&"   # promote every sensor field to the root level
            },
        },
    }
]

# ---------------------------------------------------------------------------
# Minimal JOLT shift interpreter
#
# Supports the two patterns used in the spec above:
#   "field_name": "output_name"   — copy a top-level field
#   "parent": {"*": "&"}          — promote all children of a nested object
# ---------------------------------------------------------------------------

def _apply_shift(spec: dict, data: dict) -> dict:
    output: dict[str, Any] = {}
    for input_key, rule in spec.items():
        if input_key not in data:
            continue
        value = data[input_key]
        if isinstance(rule, str):
            output[rule] = value
        elif isinstance(rule, dict) and isinstance(value, dict):
            for child_key, child_rule in rule.items():
                if child_key == "*":
                    # wildcard: iterate all children
                    for k, v in value.items():
                        dest = k if child_rule == "&" else child_rule
                        output[dest] = v
                elif child_key in value:
                    dest = child_rule if isinstance(child_rule, str) else child_key
                    output[dest] = value[child_key]
    return output


def apply_jolt(spec: list, data: dict) -> dict:
    """Apply a list of JOLT operation steps sequentially."""
    result = data
    for step in spec:
        operation = step.get("operation")
        if operation == "shift":
            result = _apply_shift(step["spec"], result)
        else:
            raise NotImplementedError(
                f"JOLT operation '{operation}' is not implemented in this interpreter. "
                "Supported operations: shift"
            )
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

    print(f"Consuming '{SOURCE_TOPIC}' → producing Avro to '{SINK_TOPIC}' (JOLT mode) ...")
    print("Press Ctrl-C to stop.\n")

    try:
        while True:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue
            if msg.error():
                raise KafkaException(msg.error())

            raw = json.loads(msg.value())
            flat = apply_jolt(JOLT_SPEC, raw)

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
