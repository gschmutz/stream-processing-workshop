# Producing and Consuming Kafka Messages with Python

In this workshop we will learn how to use the [Confluent Python client for Apache Kafka](https://github.com/confluentinc/confluent-kafka-python) to produce and consume messages from Kafka, including both plain text and Avro-serialised messages.

## Table of Contents

- [What you will learn](#what-you-will-learn)
- [Prerequisites](#prerequisites)
- [Installing the Confluent Python Client](#installing-the-confluent-python-client)
- [Working with Text Messages](#working-with-text-messages)
- [Working with Avro Messages](#working-with-avro-messages)

## What you will learn

- How to install and configure the Confluent Python client for Apache Kafka
- How to produce messages without a key and with a key from Python
- How to consume messages from a Kafka topic using a Python consumer
- How to produce Avro-serialised messages using the Schema Registry
- How to inspect registered schemas via the Schema Registry REST API and UI
- How to consume Avro messages using `kcat`, `kafka-avro-console-consumer`, and Python

## Prerequisites

- The **Data Platform** described [here](../00-environment/README.md) is running and accessible
- Workshop 1 ([Getting started with Apache Kafka](../01-working-with-kafka-broker/README.md)) completed
- Basic familiarity with Python

## Installing the Confluent Python Client

You can run the code in this workshop in two ways:

- **Locally on the Docker host** — install Python and the client library on your machine
- **Inside the Jupyter container** — the container is already running as part of the Data Platform and Python is pre-installed; navigate to <http://dataplatform:28888> (token `abc123!`)

> **Note:** The code examples below use the internal broker address `kafka-1:19092`. If you run them from outside the Docker network (e.g., directly on the Docker host), replace `kafka-1:19092` with `dataplatform:9092` and `kafka-2:19093` with `dataplatform:9093`.

Install the Confluent Python client:

```bash
pip install confluent-kafka
```

You can run each code block as a standalone script (`python script.py`) or paste it into a Jupyter notebook cell and execute it there.

## Working with Text Messages

### Create the topic

Create the topic we will use throughout this section:

```bash
docker exec -ti kafka-1 kafka-topics --create \
    --if-not-exists \
    --bootstrap-server kafka-1:19092 \
    --topic test-python-topic \
    --replication-factor 3 \
    --partitions 6
```

### Monitor the topic with `kcat`

Open a separate terminal and start `kcat` to watch messages arrive in real time. The `-f` format string prints the partition, key, and value of each message:

```bash
kcat -b dataplatform -t test-python-topic -f "P-%p: %k=%s\n" -Z
```

If you are using the `kcat` container that ships with the Data Platform, use:

```bash
docker exec -ti kcat kcat -b kafka-1:19092 -t test-python-topic -f "P-%p: %k=%s\n" -Z
```

Leave this running in the background as you work through the sections below.

### Producing messages without a key

The following script produces three messages with a `null` key. With no key, the producer distributes messages across partitions using round-robin:

```python
from confluent_kafka import Producer

topic_name = "test-python-topic"

p = Producer({'bootstrap.servers': 'kafka-1:19092,kafka-2:19093'})

def delivery_report(err, msg):
    if err is not None:
        print('Message delivery failed: {}'.format(err))
    else:
        print('Message delivered to {} [{}]'.format(msg.topic(), msg.partition()))

for data in ["message1", "message2", "message3"]:
    p.poll(0)
    p.produce(topic_name, data.encode('utf-8'), callback=delivery_report)

p.flush()
```

> **What you should see:** Three delivery confirmation lines from the `delivery_report` callback, and three new messages in the `kcat` terminal with `NULL` as the key:

```
P-3: NULL=message1
P-3: NULL=message3
P-4: NULL=message2
```

> **What just happened?** `p.produce()` enqueues the message in the internal librdkafka buffer. `p.poll(0)` gives the library a chance to trigger delivery callbacks for previously sent messages. `p.flush()` blocks until all enqueued messages have been delivered and all callbacks have fired. Because no key was specified, the producer used round-robin partitioning, so the messages landed on different partitions.

### Producing messages with a key

To route all messages for the same entity to the same partition, pass a `key` to `produce()`:

```python
from confluent_kafka import Producer

topic_name = "test-python-topic"

p = Producer({'bootstrap.servers': 'kafka-1:19092,kafka-2:19093'})

def delivery_report(err, msg):
    if err is not None:
        print('Message delivery failed: {}'.format(err))
    else:
        print('Message delivered to {} [{}]'.format(msg.topic(), msg.partition()))

for data in ["message1", "message2", "message3"]:
    p.poll(0)
    p.produce(topic_name, key='1', value=data.encode('utf-8'), callback=delivery_report)

p.flush()
```

> **What you should see:** Three more messages in the `kcat` terminal, all in the same partition and all carrying the key `1`:

```
P-5: 1=message1
P-5: 1=message2
P-5: 1=message3
```

> **What just happened?** The producer hashed the key `'1'` using the murmur2 algorithm and mapped it deterministically to a single partition. Every future message with key `'1'` will always land on partition 5 (the exact number depends on the cluster state), guaranteeing that a consumer of that partition sees all three messages in the order they were sent.

### Consuming messages

The following script subscribes to the topic and prints each message it receives. It exits cleanly when it receives a message with the value `STOP`:

```python
from confluent_kafka import Consumer, KafkaError

topic_name = "test-python-topic"

c = Consumer({
    'bootstrap.servers': 'kafka-1:19092,kafka-2:19093',
    'group.id': 'test-consumer-group',
    'auto.offset.reset': 'earliest'
})

c.subscribe([topic_name])

go_on = True
while go_on:
    msg = c.poll(1.0)

    if msg is None:
        continue
    if msg.error():
        if msg.error().code() == KafkaError._PARTITION_EOF:
            continue
        else:
            print(msg.error())
            break

    print('Received message: {}'.format(msg.value().decode('utf-8')))
    if msg.value().decode('utf-8') == 'STOP':
        go_on = False

c.close()
```

> **What you should see:** The consumer starts and immediately replays all messages already in the topic (because `auto.offset.reset` is set to `earliest`), then waits for new ones.

```
Received message: message1
Received message: message2
Received message: message3
...
```

> **What just happened?** `c.subscribe()` registers the consumer with the group coordinator broker, which assigns partitions to it. `c.poll(1.0)` fetches the next batch of messages, blocking for up to 1 second if no messages are available. `auto.offset.reset = earliest` tells Kafka to start from the beginning of each partition the first time this `group.id` subscribes — subsequent runs will resume from the last committed offset.

To send a new message while the consumer is running, open a second terminal and use `kcat` as a producer:

```bash
docker exec -ti kcat kcat -P -b kafka-1:19092 -t test-python-topic
```

Type a few messages and press **Ctrl-D** to send them. Send a final message with the value `STOP` to terminate the consumer.

![](./images/python-consumer.png)

### Producer reliability settings

By default the producer uses `acks=1` (the leader broker acknowledges the write) and will not retry on transient errors. For production workloads you generally want stronger guarantees:

| Config key | Recommended value | What it does |
|---|---|---|
| `acks` | `all` (or `-1`) | The leader waits for all in-sync replicas to acknowledge before responding — prevents data loss if the leader crashes immediately after the write |
| `retries` | `5` (or higher) | Automatically retry on retriable errors (network glitches, leader elections) |
| `enable.idempotence` | `true` | Guarantees exactly-once delivery to the broker even when retries cause duplicate network requests — requires `acks=all` |

```python
from confluent_kafka import Producer

topic_name = "test-python-topic"

p = Producer({
    'bootstrap.servers': 'kafka-1:19092,kafka-2:19093',
    'acks': 'all',
    'retries': 5,
    'enable.idempotence': True,
})

def delivery_report(err, msg):
    if err is not None:
        print('Message delivery failed: {}'.format(err))
    else:
        print('Message delivered to {} [{}] at offset {}'.format(
            msg.topic(), msg.partition(), msg.offset()))

for data in ["message1", "message2", "message3"]:
    p.poll(0)
    p.produce(topic_name, key='1', value=data.encode('utf-8'), callback=delivery_report)

p.flush()
```

> **What just happened?** With `acks=all` the broker only acknowledges once every in-sync replica has written the message to its log, so a broker crash immediately after the write cannot cause loss. `enable.idempotence=True` assigns each message a sequence number; if a retry re-sends a message the broker silently discards the duplicate, giving you exactly-once producer semantics without any code changes. `p.flush()` still blocks until the delivery callback has fired for every enqueued message, so any delivery failure surfaces as an error in `delivery_report`.

### Manual offset commits

By default the consumer auto-commits the offset every 5 seconds (`enable.auto.commit=True`). This means Kafka can mark a message as processed before your code has actually finished handling it — if the process crashes between the auto-commit and the end of your processing logic, that message is lost.

Disabling auto-commit and committing manually after successful processing gives you **at-least-once** delivery: in the worst case you reprocess a message, but you never silently skip one.

```python
from confluent_kafka import Consumer, KafkaError

topic_name = "test-python-topic"

c = Consumer({
    'bootstrap.servers': 'kafka-1:19092,kafka-2:19093',
    'group.id': 'test-consumer-group-manual',
    'auto.offset.reset': 'earliest',
    'enable.auto.commit': False,
})

c.subscribe([topic_name])

try:
    while True:
        msg = c.poll(1.0)

        if msg is None:
            continue
        if msg.error():
            print('Consumer error: {}'.format(msg.error()))
            continue

        value = msg.value().decode('utf-8')
        print('Received message: {}'.format(value))

        # commit only after successful processing
        c.commit(msg)

        if value == 'STOP':
            break
finally:
    c.close()
```

> **What just happened?** `enable.auto.commit=False` tells the client library never to commit on its own. After each message is processed, `c.commit(msg)` synchronously commits that message's offset back to Kafka. If the process crashes before `commit()` is called, the broker has no record of the offset advance — the next consumer in the group will re-read from the last committed position and reprocess the message. `c.close()` in the `finally` block commits any pending offsets and sends a leave-group request so the rebalance happens immediately rather than waiting for a session timeout.

> **Tip:** `c.commit(msg)` performs a synchronous commit, which adds a small round-trip per message. For high-throughput consumers, call `c.commit(asynchronous=True)` to fire-and-forget, or batch messages and commit once per batch.

## Working with Avro Messages

The Confluent Python client supports Avro-serialised messages via the [Confluent Schema Registry](https://docs.confluent.io/current/schema-registry/docs/index.html). The Schema Registry manages Avro schemas centrally and enforces schema compatibility rules so producers and consumers stay in sync.

Install the Avro extras:

```bash
pip install confluent-kafka[avro]
```

### Create the topic

Create a dedicated topic for the Avro examples:

```bash
docker exec -ti kafka-1 kafka-topics --create \
    --if-not-exists \
    --bootstrap-server kafka-1:19092 \
    --topic test-python-avro-topic \
    --partitions 8 \
    --replication-factor 3
```

Monitor the new topic with `kcat` in a separate terminal:

```bash
kcat -b dataplatform -t test-python-avro-topic -f "P-%p: %k=%s\n" -Z
```

### Producing Avro messages

The following script defines a `Person` Avro schema, registers it with the Schema Registry, and produces one message:

```python
from confluent_kafka import Producer
from confluent_kafka.serialization import StringSerializer, SerializationContext, MessageField
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer

topic_name = "test-python-avro-topic"

value_schema_str = """
{
   "namespace": "my.test",
   "name": "Person",
   "type": "record",
   "fields": [
     {"name": "id",        "type": "string"},
     {"name": "firstName", "type": "string"},
     {"name": "lastName",  "type": "string"}
   ]
}
"""

class Person(object):
    def __init__(self, id, firstName, lastName):
        self.id = id
        self.firstName = firstName
        self.lastName = lastName

def person_to_dict(person, ctx):
    return dict(id=person.id, firstName=person.firstName, lastName=person.lastName)

def delivery_report(err, msg):
    if err is not None:
        print("Delivery failed for record {}: {}".format(msg.key(), err))
        return
    print('Record {} successfully produced to {} [{}] at offset {}'.format(
        msg.key(), msg.topic(), msg.partition(), msg.offset()))

schema_registry_client = SchemaRegistryClient({'url': 'http://schema-registry-1:8081'})

avro_serializer = AvroSerializer(schema_registry_client, value_schema_str, person_to_dict)
string_serializer = StringSerializer('utf_8')

person = Person(id='1001', firstName='Peter', lastName='Muster')

producer = Producer({'bootstrap.servers': 'kafka-1:19092'})
producer.produce(
    topic=topic_name,
    key=string_serializer(str(person.id)),
    value=avro_serializer(person, SerializationContext(topic_name, MessageField.VALUE)),
    on_delivery=delivery_report
)
producer.flush()
```

> **What you should see:** A delivery confirmation line confirming the message was produced:

```
Record b'1001' successfully produced to test-python-avro-topic [1] at offset 0
```

> **What just happened?** On the first run, the `AvroSerializer` checked whether the `Person` schema already exists in the Schema Registry. Since it did not, it registered it automatically. It then serialised the `Person` object into Avro binary format, prefixed with a 5-byte magic byte + schema ID (the Confluent wire format), and handed the payload to the producer. The Schema Registry enforces the configured compatibility level on subsequent schema changes — by default `BACKWARD`, meaning new schemas must be able to read data written with the previous schema.

### Viewing schemas via the REST API

The Schema Registry exposes a REST API documented in the [Confluent documentation](https://docs.confluent.io/current/schema-registry/develop/api.html).

List all registered subjects:

```bash
curl http://dataplatform:8081/subjects
```

> **What you should see:** The subject created by the Avro producer:

```json
["test-python-avro-topic-value"]
```

List the available versions for the subject:

```bash
curl http://dataplatform:8081/subjects/test-python-avro-topic-value/versions
```

> **What you should see:** A single version, since we have only registered the schema once:

```json
[1]
```

Retrieve the full schema definition:

```bash
curl http://dataplatform:8081/subjects/test-python-avro-topic-value/versions/1
```

> **What you should see:** The schema object containing the subject name, version number, schema ID, and the Avro schema JSON:

```json
{"subject":"test-python-avro-topic-value","version":1,"id":1,"schema":"{\"type\":\"record\",\"name\":\"Person\",\"namespace\":\"my.test\",\"fields\":[{\"name\":\"id\",\"type\":\"string\"},{\"name\":\"firstName\",\"type\":\"string\"},{\"name\":\"lastName\",\"type\":\"string\"}]}"}
```

> **What just happened?** The Schema Registry stored the schema under the subject name `<topic>-value` (the default naming strategy). The REST API lets you inspect, compare, and manage versions without any Kafka tooling — useful for auditing schema evolution in a pipeline.

### Viewing schemas in the Schema Registry UI

Navigate to the Schema Registry UI at <http://dataplatform:28102>.

> **What you should see:** The `test-python-avro-topic-value` subject listed. Clicking on it displays the full Avro schema on the right side.

![Alt Image Text](./images/schema-registry-ui-1.png "Schema Registry UI")

### Consuming Avro messages with `kcat`

Consuming Avro messages with `kcat` without extra flags shows the raw binary payload, which is not human-readable:

```bash
docker exec -ti kcat kcat -b kafka-1:19092 -t test-python-avro-topic -f "P-%p: %k=%s\n" -Z
```

```
P-5: 10011001
Peter
     Muster
```

To have `kcat` decode the Avro payload using the Schema Registry, add the `-s value=avro` and `-r` flags:

```bash
docker exec -ti kcat kcat -b kafka-1:19092 -t test-python-avro-topic \
    -f "P-%p: %k=%s\n" -Z \
    -s value=avro \
    -r http://schema-registry-1:8081
```

> **What you should see:** The Avro payload decoded and displayed as a JSON string:

```
P-1: 1001={"id": "1001", "firstName": "Peter", "lastName": "Muster"}
```

> **What just happened?** `kcat` read the 5-byte Confluent wire format prefix from each message, extracted the schema ID, fetched the corresponding Avro schema from the Schema Registry at `-r`, and used it to deserialise the binary payload into a human-readable JSON representation.

### Consuming Avro messages with `kafka-avro-console-consumer`

The `kafka-avro-console-consumer` tool is included in the Schema Registry container and provides a quick way to inspect Avro topics from the command line.

Connect to the Schema Registry container:

```bash
docker exec -ti schema-registry-1 bash
```

Then run the consumer:

```bash
kafka-avro-console-consumer \
    --bootstrap-server kafka-1:19092,kafka-2:19093 \
    --topic test-python-avro-topic
```

> **What you should see:** Each Avro message printed as a readable JSON document:

```json
{"id":"1001","firstName":"Peter","lastName":"Muster"}
```

> **What just happened?** `kafka-avro-console-consumer` automatically fetches the schema from the Schema Registry and deserialises the Avro binary payload to JSON before printing it, in the same way `kcat` does with the `-s avro` flag — but it is pre-configured to talk to the Schema Registry running alongside it in the container.

### Consuming Avro messages from Python

The following script consumes Avro messages and deserialises each one into a `Person` object:

```python
from confluent_kafka import Consumer
from confluent_kafka.serialization import SerializationContext, MessageField
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroDeserializer

topic_name = "test-python-avro-topic"

value_schema_str = """
{
   "namespace": "my.test",
   "name": "Person",
   "type": "record",
   "fields": [
     {"name": "id",        "type": "string"},
     {"name": "firstName", "type": "string"},
     {"name": "lastName",  "type": "string"}
   ]
}
"""

class Person(object):
    def __init__(self, id, firstName, lastName):
        self.id = id
        self.firstName = firstName
        self.lastName = lastName

def dict_to_person(obj, ctx):
    if obj is None:
        return None
    return Person(id=obj['id'], firstName=obj['firstName'], lastName=obj['lastName'])

schema_registry_client = SchemaRegistryClient({'url': 'http://schema-registry-1:8081'})
avro_deserializer = AvroDeserializer(schema_registry_client, value_schema_str, dict_to_person)

consumer = Consumer({
    'bootstrap.servers': 'kafka-1:19092',
    'group.id': 'test-python-avro-topic-cg',
    'auto.offset.reset': 'earliest'
})
consumer.subscribe([topic_name])

try:
    while True:
        msg = consumer.poll(1.0)
        if msg is None:
            continue

        person = avro_deserializer(msg.value(), SerializationContext(msg.topic(), MessageField.VALUE))
        if person is not None:
            print("Person record {}: id: {}\n"
                  "\tfirstName: {}\n"
                  "\tlastName: {}\n"
                  .format(msg.key(), person.id, person.firstName, person.lastName))
except KeyboardInterrupt:
    pass
finally:
    consumer.close()
```

> **What you should see:** Each consumed Avro message deserialised and printed as a `Person` record:

```
Person record b'1001': id: 1001
	firstName: Peter
	lastName: Muster
```

> **What just happened?** The `AvroDeserializer` reads the 5-byte schema ID prefix from each message, fetches the schema from the Registry, and deserialises the Avro bytes into a Python dict. The `dict_to_person` callback then converts that dict into a `Person` instance. The consumer loop runs until interrupted with **Ctrl-C**, at which point the `finally` block calls `consumer.close()` to commit offsets and cleanly leave the consumer group.
