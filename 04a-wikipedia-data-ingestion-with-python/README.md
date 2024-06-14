# Wikipedia Data Ingestion with Python

In this workshop we will be using Python to get the data from the [Wikipedia Recent Changes stream](https://wikitech.wikimedia.org/wiki/Event_Platform/EventStreams) into Kafka. Wikipedia EventStreams is a web service that exposes continuous streams of structured event data. It does so over HTTP using chunked transfer encoding following the Server-Sent Events protocol (SSE). 

## Create the topic in Kafka

Create the topic in Kafka, if it does not yet exist, using the `kafka-topics` command. 

```bash
docker exec -ti kafka-1 kafka-topics --create --if-not-exists --bootstrap-server kafka-1:19092 --topic wikipedia-recent-changes-python-v1 --partitions 8 --replication-factor 3
```

Alternatively you can also use AKHQ to create a topic.

## Implement the Wikipedia Consumer using Python

Navigate to Jupyter: <http://dataplatform:28888>

In the first cell, install the SSE 

```bash
pip install sseclient
```

and a second cell, install the Kafka client

```
pip install kafka-python
``` 

In the next cell, execute the following python script

```python
import json

from kafka import KafkaProducer
from sseclient import SSEClient as EventSource


def produce_events_from_url(url: str, topic: str) -> None:
    for event in EventSource(url):
        if event.event == "message":
            try:
                parsed_event = json.loads(event.data)
            except ValueError:
                pass
            else:
                key = parsed_event["server_name"]
                # Partiton by server_name
                producer.send(topic, value=json.dumps(parsed_event).encode("utf-8"), key=key.encode("utf-8"))


if __name__ == "__main__":
    producer = KafkaProducer(
        bootstrap_servers="kafka-1:19092", client_id="wikidata-producer"
    )
    produce_events_from_url(
        url="https://stream.wikimedia.org/v2/stream/recentchange", topic="wikipedia-recent-changes-python-v1"
    )
```

## Use `kcat` to show the messages on the console

Now let's start a `kcat` consumer on the new topic:

```bash
docker exec -ti kcat kcat -b kafka-1:19092 -t wikipedia-recent-changes-python-v1
```