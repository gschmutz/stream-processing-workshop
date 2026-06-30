# Stream Processing Workshop

Hands-on tutorials for building real-time data pipelines with Apache Kafka and the broader streaming ecosystem — producers, consumers, Kafka Connect, Change Data Capture, MQTT, NiFi, Python, and time-series storage.

This workshop is part of the Trivadis course [Introduction to Stream Processing](https://www.trivadis.com/en/training/introduction-stream-processing-bd-stream) as well as the [Stream Processing module of the Data Engineering CAS](https://www.bfh.ch/de/weiterbildung/cas/data-engineering/) at the Berner Fachhochschule.

## Workshops

| # | Workshop | Description |
| --- | --- | --- |
| 1 | [Working with Apache Kafka](01-working-with-kafka-broker/README.md) | Explore the core concepts of Apache Kafka — topics, partitions, producers, consumers, and consumer groups — using the command-line tools bundled with Apache Kafka. |
| 2 | [Understanding Kafka Scalability and Failover](02-scalability-and-failover/README.md) | Understand how Kafka scales horizontally by multiplying producers and grouping consumers, and observe how partition replication keeps the cluster running when a broker fails. |
| 3 | [Producing and Consuming Kafka Messages with Python](03-producing-consuming-kafka-with-python/README.md) | Use the Confluent Python client to build a producer and consumer application, covering consumer groups, Avro serialization with the Schema Registry, and real-world usage patterns. |
| 4 | [Producing and Consuming Kafka Messages with Apache NiFi](04-producing-consuming-kafka-with-nifi/README.md) | Use Apache NiFi's visual canvas to build producer and consumer data flows — generating synthetic FlowFiles, publishing them to Kafka, and reading them back — with and without Avro serialization via the Schema Registry. |
| 5 | [Bluesky Data Ingestion](05-bluesky-data-intestion/README.md) | Build a streaming pipeline that ingests live posts from the Bluesky social network via its Firehose API, routes them through Apache Kafka, and delivers them to Elasticsearch for search and visualization. |
| 6 | [IoT Industrial Energy Monitoring — MQTT → Kafka → Iceberg/S3 → TimescaleDB → Grafana](06-mqtt-to-kafka-s3-timescaledb/README.md) | Build a complete IoT data pipeline that ingests simulated factory energy data via MQTT, bridges it to Kafka with Kafka Connect, flattens and serializes it as Avro with NiFi or Python, persists it in TimescaleDB, and visualizes it in Grafana. |
| 7 | [Working with Kafka Connect and Change Data Capture (CDC)](07-working-with-kafka-connect-and-cdc/README.md) | Explore three CDC strategies on PostgreSQL — query-based polling, log-based capture with Debezium, and the transactional outbox pattern — using Kafka Connect to stream database changes into downstream topics. |
| 8 | [Stream Processing and Analytics with Flink SQL](08-stream-processing-and-analytics-with-flink/README.md) | Build the same streaming credit card fraud detection pipeline using Apache Flink SQL — blacklist flagging, merchant enrichment, cardholder-average scoring, and card-testing pattern detection — then implement the enrichment pipeline programmatically with PyFlink's Table API and DataStream API. |
| 9 | [Real-Time Energy Grid Monitoring with RisingWave](09-streaming-db-with-risingwave/README.md) | Build a real-time energy grid monitoring system using RisingWave — a streaming database — ingesting synthetic consumption and solar production data from Kafka, enriching with PostgreSQL customer reference data via CDC, and maintaining incrementally updated materialized views for per-household energy balance and billing. |
