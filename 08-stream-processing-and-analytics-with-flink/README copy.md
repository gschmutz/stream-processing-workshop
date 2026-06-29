# Stream Processing and Analytics with ksqlDB, Iceberg, and Spark

In this workshop you will build a streaming fraud detection pipeline for credit card transactions. Synthetic transaction and cardholder data flows through Apache Kafka, where ksqlDB performs real-time stream processing — joining against a merchant blacklist, enriching with reference data, and flagging suspicious transactions. The flagged records are then persisted as Apache Iceberg tables in S3-compatible object storage via Kafka Connect, and the resulting tables are curated and queried analytically using Apache Spark SQL and Trino.

## Table of Contents

- [What you will learn](#what-you-will-learn)
- [Prerequisites](#prerequisites)
- [Simulator Setup](#simulator-setup)
- [Stream Processing with ksqlDB](#stream-processing-with-ksqldb)
- [Persisting to Iceberg with Kafka Connect](#persisting-to-iceberg-with-kafka-connect)
- [Validating and Querying with Spark SQL](#validating-and-querying-with-spark-sql)
- [Curating Data with Spark](#curating-data-with-spark)

## What you will learn

- How to configure and start the ShadowTraffic simulator to generate synthetic credit card transaction data
- How to create ksqlDB streams and tables over Kafka topics
- How to join a transaction stream against a blacklist table to flag suspicious transactions
- How to enrich a Kafka stream with merchant reference data using a stream-table join
- How to materialize enriched ksqlDB streams into new Kafka topics
- How to use windowed aggregations in ksqlDB to detect unusual transaction patterns
- How to deploy the Iceberg Sink Connector to persist Avro records as Parquet files in S3
- How to create Iceberg tables using Spark SQL
- How to validate data arrival by querying Iceberg tables with Spark SQL
- How to curate raw data by joining Iceberg tables in Spark and writing the result back as a new Iceberg table

## Prerequisites

- The **Data Platform** described in [00-environment](../00-environment) is running and accessible, with Kafka (KRaft, 3 brokers), Schema Registry, ksqlDB, Kafka Connect, Spark, Hive Metastore, and S3-compatible object storage (RustFS/MinIO) all healthy
- A [ShadowTraffic](https://shadowtraffic.io/) license — a free trial is available on their website
- Basic familiarity with SQL

## Simulator Setup

This workshop uses [ShadowTraffic](https://shadowtraffic.io/) to generate realistic synthetic credit card transaction data without requiring a live payment system. ShadowTraffic reads a declarative JSON configuration file and continuously produces records to Kafka topics according to the data shapes and timing rules you define.

### How the simulator works

The configuration file `scripts/shadowtraffic/card-fraud.json` (from the [demo repository](https://github.com/gschmutz/credit-card-fraud-detection-demo)) defines three generators that run in two sequential stages:

**Stage 1 — seed reference data (runs once at startup):**

| Generator | Output topic | What it produces |
|---|---|---|
| `genMerchants` | `pub.ref.merchant.state.v1` | Up to 200 merchants, each with a sequential `merchant-NNN` ID, company name, country code, city, and retail category |
| `genCardHolders` | *(via webhook)* | 300 cardholder records sent to the `lhbank-cardholder` service, which writes them to Kafka via the transactional outbox pattern |

**Stage 2 — continuous transaction stream (runs indefinitely after stage 1):**

| Generator | Output topic | What it produces |
|---|---|---|
| `genCardTransactions` | `priv.pay.transaction.delta.v1` | One transaction every 50–500 ms (random), each referencing an existing card number and a randomly picked merchant |

Each transaction record contains:

```json
{
  "transaction_id": "<uuid>",
  "card_number":    "<card number from an existing cardholder>",
  "merchant_id":    "<merchant-NNN, picked from existing merchants>",
  "amount":         "<90% between 1–300, 10% between 1000–5000 (high-value outliers)>",
  "currency":       "USD",
  "channel":        "<online | in-store | mobile>",
  "transaction_date": "<current timestamp>"
}
```

The amount distribution is intentionally skewed: 95 % of transactions fall in the 1–300 range and 5 % are high-value outliers (mean ~3 000). This means a simple high-amount threshold will produce a low false-positive rate — which makes the blacklist-based and cardholder-average-based flagging in ksqlDB more interesting to observe.

All records are serialized as Avro and the schemas are registered automatically in the Confluent Schema Registry on first produce.

### Configure the ShadowTraffic license

ShadowTraffic requires a license to run. Export the license fields as environment variables before starting the simulator. You receive all six values when you sign up for the free trial at [shadowtraffic.io](https://shadowtraffic.io/).

```bash
export PLATYS_SHADOW_TRAFFIC_LICENSE_ID=
export PLATYS_SHADOW_TRAFFIC_LICENSE_EMAIL=
export PLATYS_SHADOW_TRAFFIC_LICENSE_ORGANIZATION=
export PLATYS_SHADOW_TRAFFIC_LICENSE_EDITION=
export PLATYS_SHADOW_TRAFFIC_LICENSE_EXPIRATION=
export PLATYS_SHADOW_TRAFFIC_LICENSE_SIGNATURE=
```

### Start the simulator

The simulator runs as a Docker container defined in the `test` Compose profile. Start it after the base platform is healthy:

```bash
export DATAPLATFORM_IP=localhost
docker compose --profile test up -d
```

> **What you should see:** The `shadowtraffic` container starts and immediately begins producing records. Check its logs to confirm:

```bash
docker logs shadowtraffic --tail 20
```

You should see lines indicating that merchants and cardholders were seeded in stage 1, followed by continuous transaction output in stage 2.

### Verify data is arriving in Kafka

Confirm the merchant reference topic is populated (merchants are produced only once at startup):

```bash
docker exec -ti kcat kcat -b kafka-1:19092 -t pub.ref.merchant.state.v1 -C -e -q | head -5
```

Confirm transactions are arriving continuously:

```bash
docker exec -ti kcat kcat -b kafka-1:19092 -t priv.pay.transaction.delta.v1 -C -q -o end
```

> **What you should see:** A stream of single-line JSON records appearing every fraction of a second, each representing one credit card transaction. Press **Ctrl-C** to stop.

> **What just happened?** ShadowTraffic read `card-fraud.json`, registered the Avro schemas with the Schema Registry, and entered stage 1 — producing all merchant records to `pub.ref.merchant.state.v1` (bounded at 200 records) and all cardholder records (bounded at 300). Once stage 1 is complete it entered stage 2 and began the open-ended transaction loop, looking up existing card numbers and merchant IDs to produce referentially consistent transaction records.

## Stream Processing with ksqlDB

[ksqlDB](https://ksqldb.io/) is a streaming SQL engine built on top of Kafka Streams. It lets you write SQL-like statements that run continuously — producing new records to output topics as input records arrive — without writing any Java or Python code. The two fundamental abstractions are:

- **Stream** — an unbounded, append-only sequence of records, backed by a Kafka topic
- **Table** — the latest value per key, backed by a compacted Kafka topic; suitable for lookups

Connect to the ksqlDB CLI:

```bash
docker exec -it ksqldb-cli ksql http://ksqldb-server-1:8088
```

### Create the raw transaction stream

Create a stream that reads from the raw transaction topic. Transactions are serialized as Avro and the schema is managed by the Schema Registry.

```sql
CREATE STREAM IF NOT EXISTS pay_transaction_s
  WITH (kafka_topic='priv.pay.transaction.delta.v1',
        value_format='AVRO');
```

Query the stream to see live records arriving:

```sql
SELECT * FROM pay_transaction_s EMIT CHANGES;
```

Count transactions per card number:

```sql
SELECT card_number, COUNT(*) AS nof
FROM pay_transaction_s
GROUP BY card_number
EMIT CHANGES;
```

Use a one-minute tumbling window to detect bursts of activity:

```sql
SELECT
  TIMESTAMPTOSTRING(WINDOWSTART, 'yyyy-MM-dd HH:mm:ss', 'UTC') AS window_start,
  TIMESTAMPTOSTRING(WINDOWEND,   'yyyy-MM-dd HH:mm:ss', 'UTC') AS window_end,
  card_number,
  COUNT(*)    AS nof,
  SUM(amount) AS sum
FROM pay_transaction_s
WINDOW TUMBLING (SIZE 1 MINUTE)
GROUP BY card_number
EMIT CHANGES;
```

Add a `HAVING` clause to surface only cards with more than one transaction per minute:

```sql
SELECT
  TIMESTAMPTOSTRING(WINDOWSTART, 'yyyy-MM-dd HH:mm:ss', 'UTC') AS window_start,
  TIMESTAMPTOSTRING(WINDOWEND,   'yyyy-MM-dd HH:mm:ss', 'UTC') AS window_end,
  card_number,
  COUNT(*)    AS nof,
  SUM(amount) AS sum
FROM pay_transaction_s
WINDOW TUMBLING (SIZE 1 MINUTE)
GROUP BY card_number
HAVING COUNT(*) > 1
EMIT CHANGES;
```

Press **Ctrl-C** to stop any running query before moving on.

### Create the blacklist table and flag suspicious transactions

The blacklist is a ksqlDB table backed by the compacted topic `priv.pay.blacklist.state.v1`. A ksqlDB table holds the latest value per key, making it ideal for point-in-time lookups during stream-table joins.

```sql
CREATE TABLE IF NOT EXISTS pay_blacklist_t
  (key VARCHAR PRIMARY KEY, merchant_id VARCHAR)
  WITH (kafka_topic='priv.pay.blacklist.state.v1',
        value_format='AVRO', key_format='AVRO');
```

Join the transaction stream with the blacklist table to see which transactions involve blacklisted merchants:

```sql
SELECT t.*
    , CASE WHEN bl.key IS NOT NULL THEN 1 ELSE 0 END AS is_flagged
    , CASE WHEN bl.key IS NOT NULL THEN 'blacklist' ELSE '' END AS flagged_reason
FROM pay_transaction_s t
LEFT JOIN pay_blacklist_t bl ON (t.merchant_id = bl.key)
EMIT CHANGES;
```

Because the blacklist is currently empty, no transaction is flagged. Open a second terminal and add a merchant to the blacklist:

```bash
docker exec -it ksqldb-cli ksql http://ksqldb-server-1:8088
```

```sql
INSERT INTO pay_blacklist_t (key, merchant_id)
VALUES ('merchant-199', 'merchant-199');
```

> **What you should see:** Transactions from `merchant-199` now appear with `is_flagged=1` and `flagged_reason='blacklist'` in the first terminal window.

Stop the ad-hoc query and materialize the join into a persistent stream backed by a new Kafka topic:

```sql
DROP STREAM IF EXISTS pay_transaction_flagged_enriched_s;
DROP STREAM IF EXISTS pay_transaction_flagged_s;

CREATE STREAM pay_transaction_flagged_s
  WITH (kafka_topic='priv.pay.transaction-flagged.delta.v1',
        value_format='AVRO', key_format='AVRO', partitions=2)
AS
  SELECT t.transaction_id
      , t.card_number
      , t.currency
      , t.amount
      , t.merchant_id
      , t.channel
      , t.transaction_date
      , CASE WHEN bl.key IS NOT NULL THEN 1 ELSE 0 END AS is_flagged
      , CASE WHEN bl.key IS NOT NULL THEN 'blacklist' ELSE '' END AS flagged_reason
  FROM pay_transaction_s t
  LEFT JOIN pay_blacklist_t bl ON (t.merchant_id = bl.key)
  EMIT CHANGES;
```

Verify that flagged transactions are flowing:

```sql
SELECT * FROM pay_transaction_flagged_s WHERE is_flagged = 1 EMIT CHANGES;
```

> **What just happened?** ksqlDB created a persistent query that runs continuously in the background. Every new record on `priv.pay.transaction.delta.v1` is joined against the current state of the blacklist table and the result is appended to `priv.pay.transaction-flagged.delta.v1`. Because the blacklist is a table, the join uses the latest value for each merchant ID — if a merchant is added to the blacklist after the stream starts, subsequent transactions involving that merchant are immediately flagged.

### Enrich flagged transactions with merchant details

The merchant reference data flowing through `pub.ref.merchant.state.v1` contains name, city, country, and category for each merchant. Create a table over this topic and join it to the flagged stream.

```sql
CREATE TABLE IF NOT EXISTS ref_merchant_t (key STRING PRIMARY KEY)
  WITH (kafka_topic='pub.ref.merchant.state.v1',
        value_format='AVRO', key_format='AVRO');
```

Preview the enriched join:

```sql
SELECT t.*
    , m.name          AS merchant_name
    , m.country
    , m.city
    , m.category_name
FROM pay_transaction_flagged_s t
LEFT JOIN ref_merchant_t m ON (t.merchant_id = m.key)
EMIT CHANGES;
```

Materialize it:

```sql
DROP STREAM IF EXISTS pay_transaction_flagged_enriched_s;

CREATE STREAM pay_transaction_flagged_enriched_s
  WITH (kafka_topic='priv.pay.transaction-flagged-enriched.delta.v1',
        value_format='AVRO', key_format='AVRO', partitions=2)
AS
  SELECT t.transaction_id
      , t.card_number
      , t.currency
      , t.amount
      , t.channel
      , t.transaction_date
      , t.is_flagged
      , t.flagged_reason
      , t.merchant_id
      , m.name          AS merchant_name
      , m.country
      , m.city
      , m.category_name
  FROM pay_transaction_flagged_s t
  LEFT JOIN ref_merchant_t m ON (t.merchant_id = m.key)
  EMIT CHANGES;
```

Query the enriched flagged transactions:

```sql
SELECT * FROM pay_transaction_flagged_enriched_s WHERE is_flagged = 1 EMIT CHANGES;
```

> **What just happened?** ksqlDB now runs two continuous queries in the background in sequence: the first joins raw transactions against the blacklist, the second joins the flagged output against the merchant reference table. Each query writes its output to its own Kafka topic, forming a pipeline of enriched, growing datasets. New merchant records appearing in `pub.ref.merchant.state.v1` are automatically picked up by the table and applied to subsequent joins.

## Persisting to Iceberg with Kafka Connect

[Apache Iceberg](https://iceberg.apache.org/) is an open table format that adds ACID transactions, schema evolution, and time-travel queries on top of ordinary Parquet files in object storage. The [Iceberg Kafka Connect Sink Connector](https://iceberg.apache.org/docs/nightly/kafka-connect/) reads records from Kafka topics and writes them as Iceberg-managed Parquet files, committing snapshots at a configurable interval.

### Create the Iceberg tables using Spark SQL

Open a Spark SQL shell:

```bash
docker exec -ti spark-master spark-sql
```

Create the `payment_db` database and the raw transactions table, partitioned by hour:

```sql
USE hiverest;

CREATE DATABASE IF NOT EXISTS payment_db
LOCATION 's3a://iceberg-bucket/payment_db';

CREATE TABLE payment_db.raw_transaction_t (
    transaction_id   STRING,
    card_number      STRING,
    currency         STRING,
    amount           DOUBLE,
    merchant_id      STRING,
    channel          STRING,
    transaction_date TIMESTAMP
)
PARTITIONED BY (hours(transaction_date));
```

Create the flagged transactions table:

```sql
DROP TABLE IF EXISTS payment_db.raw_transaction_flagged_t;

CREATE TABLE payment_db.raw_transaction_flagged_t (
    transaction_id   STRING,
    card_number      STRING,
    currency         STRING,
    amount           DOUBLE,
    merchant_id      STRING,
    channel          STRING,
    transaction_date TIMESTAMP,
    is_flagged       INTEGER,
    flagged_reason   STRING
)
PARTITIONED BY (hours(transaction_date));
```

Type `exit` to leave the Spark SQL shell.

### Create the connector control topic

The Iceberg Sink Connector requires an internal control topic to coordinate commits across tasks. Create it before deploying any connectors:

```bash
docker exec -it kafka-1 kafka-topics \
  --bootstrap-server kafka-1:19092 \
  --create \
  --topic control-iceberg \
  --partitions 1 \
  --replication-factor 3
```

### Deploy the raw transactions connector

This connector reads from `priv.pay.transaction.delta.v1` and writes to `payment_db.raw_transaction_t`. Commits are batched every 60 seconds.

```bash
curl -X PUT \
  http://$DATAPLATFORM_IP:8083/connectors/pay-transaction-kafka-to-s3/config \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json' \
  -d '{
    "connector.class": "org.apache.iceberg.connect.IcebergSinkConnector",
    "tasks.max": "1",
    "topics": "priv.pay.transaction.delta.v1",
    "iceberg.tables": "payment_db.raw_transaction_t",
    "iceberg.tables.dynamic-enabled": "false",
    "write.upsert.enabled": "false",
    "iceberg.control.commit.interval-ms": "60000",
    "consumer.max.poll.records": "5000",
    "iceberg.catalog.type": "rest",
    "iceberg.catalog.uri": "http://hive-metastore:9084/iceberg",
    "iceberg.catalog.warehouse": "s3a://iceberg-bucket/payment_db",
    "iceberg.catalog.client.region": "us-east-1",
    "iceberg.catalog.s3.endpoint": "http://rustfs-1:9000",
    "iceberg.catalog.s3.path-style-access": "true",
    "iceberg.catalog.s3.access-key-id": "admin",
    "iceberg.catalog.s3.secret-access-key": "abc123abc123!",
    "value.converter": "io.confluent.connect.avro.AvroConverter",
    "value.converter.schema.registry.url": "http://schema-registry-1:8081",
    "key.converter": "org.apache.kafka.connect.storage.StringConverter"
  }'
```

### Deploy the flagged transactions connector

This connector reads from `priv.pay.transaction-flagged.delta.v1` and writes to `payment_db.raw_transaction_flagged_t`:

```bash
curl -X PUT \
  http://$DATAPLATFORM_IP:8083/connectors/pay-transaction-flagged-kafka-to-s3/config \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json' \
  -d '{
    "connector.class": "org.apache.iceberg.connect.IcebergSinkConnector",
    "tasks.max": "1",
    "topics": "priv.pay.transaction-flagged.delta.v1",
    "iceberg.tables": "payment_db.raw_transaction_flagged_t",
    "iceberg.tables.dynamic-enabled": "false",
    "write.upsert.enabled": "false",
    "iceberg.control.commit.interval-ms": "60000",
    "consumer.max.poll.records": "5000",
    "iceberg.catalog.type": "rest",
    "iceberg.catalog.uri": "http://hive-metastore:9084/iceberg",
    "iceberg.catalog.warehouse": "s3a://iceberg-bucket/payment_db",
    "iceberg.catalog.client.region": "us-east-1",
    "iceberg.catalog.s3.endpoint": "http://rustfs-1:9000",
    "iceberg.catalog.s3.path-style-access": "true",
    "iceberg.catalog.s3.access-key-id": "admin",
    "iceberg.catalog.s3.secret-access-key": "abc123abc123!",
    "value.converter": "io.confluent.connect.avro.AvroConverter",
    "value.converter.schema.registry.url": "http://schema-registry-1:8081",
    "key.converter": "org.apache.kafka.connect.storage.StringConverter"
  }'
```

> **What just happened?** Each connector starts a Kafka consumer that reads records from the configured topic, deserializes them using the Schema Registry, and writes the data as Parquet files to S3. Every 60 seconds (one commit interval) the connector flushes buffered records, writes new Parquet data files, and commits a new Iceberg snapshot to the metadata layer via the Hive Metastore REST API. The result is a durable, queryable table that any Iceberg-compatible engine (Spark, Trino, Flink) can read with full snapshot isolation.

## Validating and Querying with Spark SQL

Once the connectors have been running for at least one commit interval (60 seconds), data starts appearing in the Iceberg tables. Use Spark SQL to verify the data and run exploratory queries.

Open a Spark SQL shell:

```bash
docker exec -ti spark-master spark-sql
```

Switch to the Iceberg catalog:

```sql
USE hiverest;
```

Query the raw transactions table:

```sql
SELECT * FROM payment_db.raw_transaction_t LIMIT 10;
```

Query the flagged transactions table:

```sql
SELECT * FROM payment_db.raw_transaction_flagged_t WHERE is_flagged = 1 LIMIT 10;
```

Count flagged transactions per merchant:

```sql
SELECT merchant_id, COUNT(*) AS flagged_count
FROM payment_db.raw_transaction_flagged_t
WHERE is_flagged = 1
GROUP BY merchant_id
ORDER BY flagged_count DESC;
```

Inspect the Iceberg table history (time travel):

```sql
SELECT * FROM payment_db.raw_transaction_t.history;
```

Query a specific historical snapshot:

```sql
SELECT COUNT(*) FROM payment_db.raw_transaction_t
FOR VERSION AS OF <snapshot_id>;
```

Replace `<snapshot_id>` with one of the snapshot IDs returned by the `history` query above.

Type `exit` to leave the Spark SQL shell.

> **What just happened?** Spark connects to the Iceberg REST catalog (Hive Metastore), which returns the current snapshot metadata for each table. The metadata lists the Parquet data files that make up the table and their partition layout. Spark reads only the relevant files — partition pruning on `transaction_date` means queries for a narrow time window skip files from other hours entirely, which is why analytic queries remain fast even as the table grows.

## Curating Data with Spark

The raw transaction table contains only a `merchant_id` foreign key. This curation step joins it with the merchant reference table to produce a denormalized view that is more useful for reporting and analytics.

First, write the merchant reference data to its own Iceberg table. Open a Spark SQL shell and create the database and table:

```bash
docker exec -ti spark-master spark-sql
```

```sql
USE hiverest;

CREATE DATABASE IF NOT EXISTS refdata_db
LOCATION 's3a://iceberg-bucket/refdata_db';

CREATE TABLE refdata_db.raw_merchant_t (
    merchant_id   STRING,
    name          STRING,
    country       STRING,
    city          STRING,
    category_name STRING
);
```

Type `exit`, then deploy a Kafka Connect connector to populate the merchant table from the `pub.ref.merchant.state.v1` topic:

```bash
curl -X PUT \
  http://$DATAPLATFORM_IP:8083/connectors/ref-merchant-kafka-to-s3/config \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json' \
  -d '{
    "connector.class": "org.apache.iceberg.connect.IcebergSinkConnector",
    "tasks.max": "1",
    "topics": "pub.ref.merchant.state.v1",
    "iceberg.tables": "refdata_db.raw_merchant_t",
    "iceberg.tables.dynamic-enabled": "false",
    "write.upsert.enabled": "false",
    "iceberg.control.commit.interval-ms": "60000",
    "consumer.max.poll.records": "5000",
    "iceberg.catalog.type": "rest",
    "iceberg.catalog.uri": "http://hive-metastore:9084/iceberg",
    "iceberg.catalog.warehouse": "s3a://iceberg-bucket/refdata_db",
    "iceberg.catalog.client.region": "us-east-1",
    "iceberg.catalog.s3.endpoint": "http://rustfs-1:9000",
    "iceberg.catalog.s3.path-style-access": "true",
    "iceberg.catalog.s3.access-key-id": "admin",
    "iceberg.catalog.s3.secret-access-key": "abc123abc123!",
    "value.converter": "io.confluent.connect.avro.AvroConverter",
    "value.converter.schema.registry.url": "http://schema-registry-1:8081",
    "key.converter": "org.apache.kafka.connect.storage.StringConverter"
  }'
```

Wait one commit interval (60 seconds), then run the curation job. Open a Spark SQL shell and create the curated table by joining transactions with merchants:

```bash
docker exec -ti spark-master spark-sql
```

```sql
USE hiverest;

DROP TABLE IF EXISTS payment_db.cur_transaction_with_merchant_t;

CREATE TABLE payment_db.cur_transaction_with_merchant_t
PARTITIONED BY (hours(transaction_date))
AS
SELECT t.transaction_id
    , t.card_number
    , t.currency
    , t.amount
    , t.channel
    , t.transaction_date
    , t.is_flagged
    , t.flagged_reason
    , m.merchant_id
    , m.name          AS merchant_name
    , m.country
    , m.city
    , m.category_name
    , CONCAT(m.name, ' / ', m.city, ' (', m.category_name, ')') AS booking_text
FROM payment_db.raw_transaction_flagged_t t
LEFT JOIN refdata_db.raw_merchant_t m
    ON t.merchant_id = m.merchant_id;
```

Query the curated table:

```sql
SELECT merchant_name, country, category_name, COUNT(*) AS flagged_count, ROUND(SUM(amount), 2) AS total_amount
FROM payment_db.cur_transaction_with_merchant_t
WHERE is_flagged = 1
GROUP BY merchant_name, country, category_name
ORDER BY flagged_count DESC
LIMIT 20;
```

> **What you should see:** A ranked list of merchants whose transactions were flagged, with their country, category, total flagged transaction count, and total value — giving a quick picture of where fraud risk is concentrated.

Type `exit` to leave the Spark SQL shell.

> **What just happened?** Spark executed a distributed join across two Iceberg tables stored as Parquet files in S3, applied the filter and aggregation, and wrote the result back as a new Iceberg table — also partitioned by hour so future queries can prune efficiently. Because all three tables are managed by the same Iceberg catalog, the result table is immediately visible to any other catalog-aware engine (Trino, Flink, another Spark session) without any additional registration step.
