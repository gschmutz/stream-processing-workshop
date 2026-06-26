# Stream Processing and Analytics with Flink SQL, Iceberg, and Spark

In this workshop you will build a streaming fraud detection pipeline for credit card transactions. Synthetic transaction and cardholder data flows through Apache Kafka, where Apache Flink SQL performs real-time stream processing — joining against a merchant blacklist, enriching with reference data, and flagging suspicious transactions. The flagged records are then persisted as Apache Iceberg tables in S3-compatible object storage via Kafka Connect, and the resulting tables are curated and queried analytically using Apache Spark SQL.

## Table of Contents

- [What you will learn](#what-you-will-learn)
- [Prerequisites](#prerequisites)
- [Additional Services](#additional-services)
- [Kafka Topic Setup with Jikkou](#kafka-topic-setup-with-jikkou)
- [Simulator Setup](#simulator-setup)
- [Exploring Streams with the Default In-Memory Catalog](#exploring-streams-with-the-default-in-memory-catalog)
- [Making Definitions Durable with the Hive Metastore Catalog](#making-definitions-durable-with-the-hive-metastore-catalog)
- [Fraud Detection: Blacklist Flagging and Merchant Enrichment](#fraud-detection-blacklist-flagging-and-merchant-enrichment)
- [Advanced Fraud Detection Patterns](#advanced-fraud-detection-patterns)
- [Persisting to Iceberg with Kafka Connect](#persisting-to-iceberg-with-kafka-connect)
- [Validating and Querying with Spark SQL](#validating-and-querying-with-spark-sql)
- [Curating Data with Spark](#curating-data-with-spark)

## What you will learn

- How to declare Kafka topics as code using Jikkou's `KafkaTopicList` resource and apply them idempotently with a single command
- How to configure and start the ShadowTraffic simulator to generate synthetic credit card transaction data
- How to create Flink SQL tables over Kafka topics using the Kafka and upsert-kafka connectors
- How to join a transaction stream against a blacklist table to flag suspicious transactions
- How to enrich a Kafka stream with merchant reference data using a stream-table join
- How to materialize enriched Flink SQL queries into new Kafka topics with `INSERT INTO`
- How to use tumbling window aggregations in Flink SQL to detect unusual transaction patterns
- How to deploy the Iceberg Sink Connector to persist Avro records as Parquet files in S3
- How to create Iceberg tables using Spark SQL
- How to validate data arrival by querying Iceberg tables with Spark SQL
- How to curate raw data by joining Iceberg tables in Spark and writing the result back as a new Iceberg table

## Prerequisites

- The **Data Platform** described in [00-environment](../00-environment) is running and accessible, with Kafka (KRaft, 3 brokers), Schema Registry, Flink (JobManager + TaskManager + SQL Client), Kafka Connect, Spark, Hive Metastore, and S3-compatible object storage (RustFS/MinIO) all healthy
- A [ShadowTraffic](https://shadowtraffic.io/) license — a free trial is available on their website
- Basic familiarity with SQL

## Additional Services

The base Platys platform covers the core infrastructure (Kafka, Schema Registry, Flink, etc.). This workshop adds two more service definitions in `docker-compose.override.yml` that Docker Compose automatically merges with the base stack when you run `docker compose up`.

### lhbank-cardholder-app

```yaml
lhbank-cardholder-app:
  image: ghcr.io/gschmutz/lhbank-cardholder:main
  environment:
    SERVER_PORT: 8082
    SPRING_DATASOURCE_URL: jdbc:postgresql://postgresql:5432/customer_db
    SPRING_DATASOURCE_USERNAME: customer
    SPRING_DATASOURCE_PASSWORD: abc123!
    SPRING_KAFKA_PROPERTIES_SCHEMA_REGISTRY_URL: http://schema-registry-1:8081
  ports:
    - "29000:8082"
```

This is a Spring Boot microservice that implements the **transactional outbox pattern** for cardholder data. ShadowTraffic does not write cardholders directly to Kafka — instead it calls this service's REST endpoint (acting as a webhook target). The service then:

1. Persists the cardholder record to the `customer_db` PostgreSQL database
2. Publishes the same record to the `pub.cus.cardHolder.state.v1` Kafka topic as an Avro event, using the Schema Registry for schema management

Writing to the database and publishing to Kafka inside the same transactional boundary ensures cardholder state in PostgreSQL and in Kafka is always consistent. The service waits for both PostgreSQL and Schema Registry to be healthy before starting (`depends_on` with health checks).

### trino-1 (override)

```yaml
trino-1:
  environment:
    POSTGRESQL_DATABASE: customer_db
    POSTGRESQL_USER: customer
    POSTGRESQL_PASSWORD: abc123!
```

This is not a new container — it extends the `trino-1` service already defined by Platys, injecting the credentials for the `customer_db` database into Trino's PostgreSQL connector. This makes the cardholder reference data queryable from Trino without modifying the base platform config.

### Start the extended stack

Start the platform including these two extensions:

```bash
export DATAPLATFORM_IP=localhost
docker compose up -d
```

Docker Compose automatically reads `docker-compose.override.yml` from the same directory and merges it with the base `docker-compose.yml`, so no extra flags are needed.

Confirm the cardholder service is healthy:

```bash
docker logs lhbank-cardholder-app --tail 20
```

> **What you should see:** Spring Boot startup log lines ending with `Started LhbankCardholderApplication`, indicating the service is ready to receive webhook calls from ShadowTraffic.

## Kafka Topic Setup with Jikkou

[Jikkou](https://www.jikkou.io/) is a GitOps-style command-line tool for managing Kafka resources — topics, ACLs, schema subjects, consumer groups — as versioned, declarative YAML files. Instead of running `kafka-topics.sh` commands by hand, you describe the desired state once in a spec file and let Jikkou reconcile the cluster to match it. Jikkou only changes what differs from the spec, so re-applying the same file is always safe (idempotent).

In this platform Kafka is configured with `auto.create.topics.enable = false`, which means every topic the ShadowTraffic simulator writes to must exist before the simulator starts. Jikkou is the right tool for this: it lets you keep the topic definitions in source control alongside the rest of the workshop and recreate them reliably in any environment.

### The topic spec file

The file `card-topic-specs.yml` in this workshop directory defines all five topics needed by the pipeline as a single `KafkaTopicList` resource:

```yaml
apiVersion: "kafka.jikkou.io/v1beta2"
kind: "KafkaTopicList"
metadata: {}
items:
  - metadata:
      name: 'priv.pay.transaction.delta.v1'
    spec:
      partitions: 2
      replicas: 3
      configs:
        cleanup.policy: delete
        segment.bytes: 104857600

  - metadata:
      name: 'priv.pay.blacklist.state.v1'
    spec:
      partitions: 2
      replicas: 3
      configs:
        cleanup.policy: compact
        segment.ms: 100
        delete.retention.ms: 100
        min.cleanable.dirty.ratio: 0.001

  - metadata:
      name: 'pub.cus.cardHolder.state.v1'
    spec:
      partitions: 2
      replicas: 3
      configs:
        cleanup.policy: compact
        segment.ms: 100
        delete.retention.ms: 100
        min.cleanable.dirty.ratio: 0.001

  - metadata:
      name: 'pub.ref.merchant.state.v1'
    spec:
      partitions: 2
      replicas: 3
      configs:
        cleanup.policy: compact
        segment.ms: 100
        delete.retention.ms: 100
        min.cleanable.dirty.ratio: 0.001

  - metadata:
      name: 'pub.ref.geonames.state.v1'
    spec:
      partitions: 1
      replicas: 3
      configs:
        cleanup.policy: compact
        segment.ms: 100
        delete.retention.ms: 100
        min.cleanable.dirty.ratio: 0.001
```

What each topic is for and why the settings differ:

| Topic | `cleanup.policy` | Purpose |
|---|---|---|
| `priv.pay.transaction.delta.v1` | `delete` | Append-only transaction event stream. Records can expire after the retention window — old events do not need to be replayed forever. |
| `priv.pay.blacklist.state.v1` | `compact` | Keyed blacklist state. Log compaction ensures the latest value for every merchant key is always available, regardless of how old it is. |
| `pub.cus.cardHolder.state.v1` | `compact` | Keyed cardholder reference state. Same reasoning as the blacklist — lookups must always return the current record. |
| `pub.ref.merchant.state.v1` | `compact` | Keyed merchant reference state. Flink's upsert-kafka connector reads this as a changelog table. |
| `pub.ref.geonames.state.v1` | `compact` | Keyed geo-name lookup state. Single partition because it is a small, infrequently updated reference dataset. |

The aggressive compaction settings (`segment.ms: 100`, `delete.retention.ms: 100`, `min.cleanable.dirty.ratio: 0.001`) on the compacted topics cause the log cleaner to run almost immediately, so tombstone records are removed quickly and the topic stays lean.

Make the topic spec file available to the dataplatform:

```bash
cp card-topic-specs.yml $DATAPLATFORM_HOME/scripts/jikkou
```

### Preview the changes before applying

Use `jikkou diff` to see exactly what Jikkou would create or modify without touching the cluster:

```bash
docker compose run jikkou diff --files=/jikkou/card-topic-specs.yml
```

> **What you should see:** Five entries, each marked `+` (create), because the topics do not exist yet. After the first apply, running `diff` again will show no changes — confirming that the cluster already matches the spec.

### Apply the spec

```bash
docker compose run jikkou apply --files=/jikkou/card-topic-specs.yml
```

Jikkou reads the spec, compares it to the live cluster, creates the missing topics, and prints a summary of what was changed.

### Verify the topics exist

```bash
docker exec jikkou jikkou get kafkatopics --default-configs=false --navigation=false
```

You should see all five topic names in the output. Alternatively, use kcat:

```bash
docker exec -ti kcat kcat -b kafka-1:19092 -L | grep "priv\.\|pub\."
```

> **What just happened?** Jikkou connected to the Kafka cluster, compared the `KafkaTopicList` spec to the current topic inventory, and created each topic with the exact partition count, replication factor, and configuration properties specified. Because the spec file is checked in alongside the workshop code, anyone starting this workshop from scratch can recreate the identical topic layout with a single command — no tribal knowledge of `kafka-topics.sh` flags required.

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
export PLATYS_SHADOW_TRAFFIC_LICENSE_ID="02d79a76-6830-4e08-b700-5487eced158b"
export PLATYS_SHADOW_TRAFFIC_LICENSE_EMAIL="michael+examples@shadowtraffic.io"
export PLATYS_SHADOW_TRAFFIC_LICENSE_ORGANIZATION="ShadowTraffic"
export PLATYS_SHADOW_TRAFFIC_LICENSE_EDITION="ShadowTraffic Free Trial"
export PLATYS_SHADOW_TRAFFIC_LICENSE_EXPIRATION="2026-07-22"
export PLATYS_SHADOW_TRAFFIC_LICENSE_SIGNATURE="KjPD4Ox+rAuLmvANNXT/ZTYgcWpyddXaicZ3rNLDgdZ5/rpBD/Rj9x+3FCDrxAh5FtIs4yegxBM3WM08+RT4AkAf54HQYfLV/vs4//A0cs4/+wmTRndpIzQ1GQ4ETbTw7sDoMt6mmI2/7MDF6NikKmzlYqhizivuiFbhcWZ3Rg4efZLGa9aQqTuEuAsW6KSIQJxTzObVEwI9+I/c3ofGAXT+muJ1Ew7Q9C6S2CUdhNKTCSBx27oy1vwvg+ABkCirOP91RAZxqT6CdVUgXI+zUUpJiSnw2Jz7C7xIIpsjCDwbXIcAd3Qcy1xrBQt/2VzyUWVYzPBs3ATPFTKhlhB4aw=="
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

## Exploring Streams using Flink SQL with the Default In-Memory Catalog

[Apache Flink](https://flink.apache.org/) is a distributed stream-processing engine. Its SQL interface lets you write standard SQL queries that run continuously over unbounded data streams. In Flink SQL, **every object is a `TABLE`**; whether it behaves as an append-only stream or a keyed lookup depends on the connector and the presence of a primary key:

- **Kafka connector** (`connector = 'kafka'`) — append-only source or sink; models an unbounded event stream
- **Upsert-Kafka connector** (`connector = 'upsert-kafka'`) — changelog source or sink; holds the latest value per key and is suitable for lookups

Connect to the Flink SQL CLI and set a clean display mode:

```bash
docker exec -it flink-sql-client sql-client.sh
```

```sql
SET 'sql-client.execution.result-mode' = 'tableau';
```

Out of the box, Flink uses the **`default_catalog`** — an in-memory catalog that is session-scoped. Table definitions stored here are available immediately but exist only for the lifetime of the current SQL client session. This makes the default catalog ideal for ad-hoc exploration.

Create a table over the raw transaction topic and run a few exploratory queries:

```sql
CREATE TABLE pay_transaction_s (
    transaction_id   STRING,
    card_number      STRING,
    merchant_id      STRING,
    amount           DOUBLE,
    currency         STRING,
    channel          STRING,
    transaction_date TIMESTAMP_LTZ(3),
    WATERMARK FOR transaction_date AS transaction_date - INTERVAL '5' SECOND
) WITH (
    'connector'                    = 'kafka',
    'topic'                        = 'priv.pay.transaction.delta.v1',
    'properties.bootstrap.servers' = 'kafka-1:19092',
    'properties.group.id'          = 'flink-pay-transaction',
    'scan.startup.mode'            = 'earliest-offset',
    'value.format'                 = 'avro-confluent',
    'value.avro-confluent.url'     = 'http://schema-registry-1:8081'
);
```

Confirm the table appears in the catalog:

```sql
SHOW TABLES;
```

Query it to see live records arriving:

```sql
SELECT * FROM pay_transaction_s;
```

Press **Q** or **Ctrl-C** to stop any running query.

Count transactions per card number:

```sql
SELECT card_number, COUNT(*) AS nof
FROM pay_transaction_s
GROUP BY card_number;
```

Use a one-minute tumbling window to detect bursts of activity:

```sql
SELECT
    window_start,
    window_end,
    card_number,
    COUNT(*)    AS nof,
    SUM(amount) AS total_amount
FROM TABLE(
    TUMBLE(TABLE pay_transaction_s, DESCRIPTOR(transaction_date), INTERVAL '1' MINUTE)
)
GROUP BY window_start, window_end, card_number;
```

Narrow to cards with more than one transaction per minute:

```sql
SELECT
    window_start,
    window_end,
    card_number,
    COUNT(*)    AS nof,
    SUM(amount) AS total_amount
FROM TABLE(
    TUMBLE(TABLE pay_transaction_s, DESCRIPTOR(transaction_date), INTERVAL '1' MINUTE)
)
GROUP BY window_start, window_end, card_number
HAVING COUNT(*) > 1;
```

Press **Ctrl-C** to stop any running query. Now demonstrate what in-memory actually means — exit the session and immediately reconnect:

```sql
EXIT;
```

```bash
docker exec -it flink-sql-client sql-client.sh
```

```sql
SHOW TABLES;
```

> **What you should see:** An empty result — no tables. The `pay_transaction_s` definition is gone. The in-memory catalog is session-scoped: every new SQL client session starts with a blank `default_catalog`. The underlying Kafka topic and its data are completely untouched, but Flink has no record of how to read them.

This is a fundamental limitation of the default catalog for anything beyond one-off exploration. Flink ships with [three catalog types](https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/table/catalogs/#catalog-types):

| Catalog type | Persistence | Can create new objects? | Best for |
|---|---|---|---|
| **In-memory** (`default_catalog`) | Session only | Yes | Ad-hoc exploration |
| **Hive Metastore** | Permanent — stored in the Metastore DB | Yes | Production pipelines |
| **JDBC** | Permanent — but read-only view of an existing DB | No | Querying existing tables |

## Making Definitions Durable with the Hive Metastore Catalog

The Hive Metastore stores table DDL — schema, connector properties, partition metadata — in a relational database (PostgreSQL in this platform). Any Flink SQL client that connects to the same Metastore sees the same catalog, so a table defined in one session is immediately available in a fresh session, after a cluster restart, or from a different machine entirely.

Connect and register the Hive catalog:

```bash
docker exec -it flink-sql-client sql-client.sh
```

```sql
CREATE CATALOG hive_catalog WITH (
    'type'          = 'hive',
    'hive-conf-dir' = '/opt/hive-conf'
);
```

> **Note on catalog persistence:** This platform is configured with `table.catalog-store.kind: file` (stored in `./conf/catalogs`). When you run `CREATE CATALOG`, Flink writes the catalog definition to that directory, so the catalog registration itself survives session restarts — you only need to run `CREATE CATALOG hive_catalog ...` **once**. On reconnect, Flink loads the definition automatically and the catalog is immediately available. The TABLE definitions inside the catalog are separately stored in the Hive Metastore database, which is also permanent. Both layers of metadata persist independently of the SQL client session.

Switch to it and create a dedicated database for this workshop:

```sql
USE CATALOG hive_catalog;

SHOW DATABASES;

CREATE DATABASE IF NOT EXISTS fraud_detection;

USE fraud_detection;
```

Verify the active context:

```sql
SHOW CURRENT CATALOG;
SHOW CURRENT DATABASE;
```

> **What you should see:** `hive_catalog` and `fraud_detection`.

### Register all source and sink tables

With the Hive catalog active, every `CREATE TABLE` statement is written to the Metastore and survives session restarts. Define all five tables the pipeline needs:

```sql
-- Raw transaction stream (Kafka source, append-only)
CREATE TABLE IF NOT EXISTS pay_transaction_s (
    transaction_id   STRING,
    card_number      STRING,
    merchant_id      STRING,
    amount           DOUBLE,
    currency         STRING,
    channel          STRING,
    transaction_date TIMESTAMP_LTZ(3),
    WATERMARK FOR transaction_date AS transaction_date - INTERVAL '5' SECOND
) WITH (
    'connector'                    = 'kafka',
    'topic'                        = 'priv.pay.transaction.delta.v1',
    'properties.bootstrap.servers' = 'kafka-1:19092',
    'properties.group.id'          = 'flink-pay-transaction',
    'scan.startup.mode'            = 'earliest-offset',
    'value.format'                 = 'avro-confluent',
    'value.avro-confluent.url'     = 'http://schema-registry-1:8081'
);

-- Merchant blacklist (upsert-kafka: latest value per key)
CREATE TABLE IF NOT EXISTS pay_blacklist_t (
    `key`       STRING,
    merchant_id STRING,
    PRIMARY KEY (`key`) NOT ENFORCED
) WITH (
    'connector'                    = 'upsert-kafka',
    'topic'                        = 'priv.pay.blacklist.state.v1',
    'properties.bootstrap.servers' = 'kafka-1:19092',
    'key.format'                   = 'avro-confluent',
    'key.avro-confluent.url'       = 'http://schema-registry-1:8081',
    'value.format'                 = 'avro-confluent',
    'value.avro-confluent.url'     = 'http://schema-registry-1:8081'
);

-- Merchant reference data (upsert-kafka: latest value per key)
CREATE TABLE IF NOT EXISTS ref_merchant_t (
    `key`         STRING,
    name          STRING,
    country       STRING,
    city          STRING,
    category_name STRING,
    PRIMARY KEY (`key`) NOT ENFORCED
) WITH (
    'connector'                    = 'upsert-kafka',
    'topic'                        = 'pub.ref.merchant.state.v1',
    'properties.bootstrap.servers' = 'kafka-1:19092',
    'key.format'                   = 'avro-confluent',
    'key.avro-confluent.url'       = 'http://schema-registry-1:8081',
    'value.format'                 = 'avro-confluent',
    'value.avro-confluent.url'     = 'http://schema-registry-1:8081'
);

-- Sink: blacklist-flagged transactions (upsert-kafka: keyed by transaction_id)
CREATE TABLE IF NOT EXISTS pay_transaction_flagged_s (
    transaction_id   STRING,
    card_number      STRING,
    currency         STRING,
    amount           DOUBLE,
    merchant_id      STRING,
    channel          STRING,
    transaction_date TIMESTAMP_LTZ(3),
    is_flagged       INT,
    flagged_reason   STRING,
    PRIMARY KEY (transaction_id) NOT ENFORCED
) WITH (
    'connector'                    = 'upsert-kafka',
    'topic'                        = 'priv.pay.transaction-flagged.delta.v1',
    'properties.bootstrap.servers' = 'kafka-1:19092',
    'key.format'                   = 'avro-confluent',
    'key.avro-confluent.url'       = 'http://schema-registry-1:8081',
    'value.format'                 = 'avro-confluent',
    'value.avro-confluent.url'     = 'http://schema-registry-1:8081'
);

-- Sink: flagged transactions enriched with merchant details (upsert-kafka)
CREATE TABLE IF NOT EXISTS pay_transaction_flagged_enriched_s (
    transaction_id   STRING,
    card_number      STRING,
    currency         STRING,
    amount           DOUBLE,
    channel          STRING,
    transaction_date TIMESTAMP_LTZ(3),
    is_flagged       INT,
    flagged_reason   STRING,
    merchant_id      STRING,
    merchant_name    STRING,
    country          STRING,
    city             STRING,
    category_name    STRING,
    PRIMARY KEY (transaction_id) NOT ENFORCED
) WITH (
    'connector'                    = 'upsert-kafka',
    'topic'                        = 'priv.pay.transaction-flagged-enriched.delta.v1',
    'properties.bootstrap.servers' = 'kafka-1:19092',
    'key.format'                   = 'avro-confluent',
    'key.avro-confluent.url'       = 'http://schema-registry-1:8081',
    'value.format'                 = 'avro-confluent',
    'value.avro-confluent.url'     = 'http://schema-registry-1:8081'
);
```

Verify all five tables are registered:

```sql
SHOW TABLES;
```

Now prove the definitions persist across sessions:

```sql
EXIT;
```

```bash
docker exec -it flink-sql-client sql-client.sh
```

```sql
USE CATALOG hive_catalog;
USE fraud_detection;
SHOW TABLES;
```

> **What you should see:** All five table names — no `CREATE TABLE` statements needed, and no `CREATE CATALOG` either. Because this platform uses a file-based catalog store, both the catalog registration and the table DDL survived the session restart intact. From this point on, every SQL statement in this workshop assumes the Hive catalog and `fraud_detection` database are active.

---

## Fraud Detection: Blacklist Flagging and Merchant Enrichment

With all table definitions persisted in the Hive catalog, we can now build the two-stage pipeline. Make sure your SQL client session has the Hive catalog active:

```sql
USE CATALOG hive_catalog;
USE fraud_detection;
```

### Flag transactions against the merchant blacklist

Join the transaction stream with the blacklist table to see which transactions involve blacklisted merchants:

```sql
SELECT t.*
     , CASE WHEN bl.`key` IS NOT NULL THEN 1 ELSE 0 END           AS is_flagged
     , CASE WHEN bl.`key` IS NOT NULL THEN 'blacklist' ELSE '' END AS flagged_reason
FROM pay_transaction_s t
LEFT JOIN pay_blacklist_t bl ON t.merchant_id = bl.`key`;
```

Because the blacklist is currently empty, no transaction is flagged. Open a second terminal, connect a second SQL client session, and add a merchant:

```bash
docker exec -it flink-sql-client sql-client.sh
```

```sql
USE CATALOG hive_catalog;
USE fraud_detection;
INSERT INTO pay_blacklist_t VALUES ('merchant-199', 'merchant-199');
```

> **What you should see:** Transactions from `merchant-199` now appear with `is_flagged=1` and `flagged_reason='blacklist'` in the first terminal window.

Stop the ad-hoc query (**Ctrl-C**) and materialize the join as a persistent Flink job:

```sql
INSERT INTO pay_transaction_flagged_s
SELECT
    t.transaction_id
  , t.card_number
  , t.currency
  , t.amount
  , t.merchant_id
  , t.channel
  , t.transaction_date
  , CASE WHEN bl.`key` IS NOT NULL THEN 1 ELSE 0 END           AS is_flagged
  , CASE WHEN bl.`key` IS NOT NULL THEN 'blacklist' ELSE '' END AS flagged_reason
FROM pay_transaction_s t
LEFT JOIN pay_blacklist_t bl ON t.merchant_id = bl.`key`;
```

Verify flagged transactions are flowing:

```sql
SELECT * FROM pay_transaction_flagged_s WHERE is_flagged = 1;
```

> **What just happened?** Flink submitted a persistent streaming job that runs on the cluster independently of the SQL client session. Every new record on `priv.pay.transaction.delta.v1` is joined against the current blacklist state and the result is written to `priv.pay.transaction-flagged.delta.v1`. Because `pay_blacklist_t` uses the upsert-kafka connector, Flink maintains an in-memory state of the latest value per merchant key — adding a merchant to the blacklist after the job starts immediately affects subsequent transactions.

### Enrich flagged transactions with merchant details

The merchant reference topic contains name, city, country, and category for each merchant. Preview the join:

```sql
SELECT t.*
     , m.name          AS merchant_name
     , m.country
     , m.city
     , m.category_name
FROM pay_transaction_flagged_s t
LEFT JOIN ref_merchant_t m ON t.merchant_id = m.`key`;
```

Materialize as a second persistent job:

```sql
INSERT INTO pay_transaction_flagged_enriched_s
SELECT
    t.transaction_id
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
LEFT JOIN ref_merchant_t m ON t.merchant_id = m.`key`;
```

Query the enriched flagged transactions:

```sql
SELECT * FROM pay_transaction_flagged_enriched_s WHERE is_flagged = 1;
```

> **What just happened?** Two persistent streaming jobs now run on the Flink cluster in sequence. The first joins raw transactions against the blacklist; the second reads that output and joins with the merchant reference table. Each job writes to its own Kafka topic, forming a pipeline. New merchant records appearing in `pub.ref.merchant.state.v1` are automatically picked up by the upsert-kafka state and applied to subsequent joins.

---

## Advanced Fraud Detection Patterns

The blacklist join in the previous section flags known-bad merchants. This section adds three complementary fraud signals that do not require an external reference list — they derive suspicion entirely from patterns within the transaction stream itself. Each pattern uses a different Flink SQL capability.

| Pattern | Flink SQL feature | Requires previous records? |
|---|---|---|
| Velocity — too many transactions per window | `TUMBLE` window + `HAVING` | No (aggregated per window) |
| Amount anomaly — spike above card's own rolling average | `OVER` window aggregation | **Yes — reads back 24 h of history per card** |
| Card-testing sequence — small probe followed by large transaction | `MATCH_RECOGNIZE` | **Yes — scans across rows of same card** |

Make sure the Hive catalog and database are active in your SQL client session:

```sql
USE CATALOG hive_catalog;
USE fraud_detection;
```

First add the two new output topics to the Jikkou spec and apply:

```yaml
# append to card-topic-specs.yml
  - metadata:
      name: 'priv.pay.fraud.velocity.delta.v1'
    spec:
      partitions: 2
      replicas: 3
      configs:
        cleanup.policy: delete
        segment.bytes: 104857600

  - metadata:
      name: 'priv.pay.fraud.amount-anomaly.delta.v1'
    spec:
      partitions: 2
      replicas: 3
      configs:
        cleanup.policy: delete
        segment.bytes: 104857600
```

```bash
docker cp card-topic-specs.yml jikkou:/tmp/card-topic-specs.yml
docker exec jikkou jikkou apply --files /tmp/card-topic-specs.yml
```

---

### Pattern 1 — Velocity detection

**Signal:** A legitimate cardholder rarely makes more than a handful of purchases within a few minutes. A burst of transactions in a short window is a strong indicator of card abuse or automated fraud.

**How it works:** Group transactions into 10-minute tumbling windows per card. Emit a fraud alert row for every window where the count exceeds the threshold.

Explore first:

```sql
SELECT
    window_start,
    window_end,
    card_number,
    COUNT(*)    AS tx_count,
    SUM(amount) AS total_amount
FROM TABLE(
    TUMBLE(TABLE pay_transaction_s, DESCRIPTOR(transaction_date), INTERVAL '10' MINUTE)
)
GROUP BY window_start, window_end, card_number
HAVING COUNT(*) > 3;
```

Materialize as a persistent fraud alert stream:

```sql
CREATE TABLE IF NOT EXISTS pay_fraud_velocity_s (
    window_start  TIMESTAMP_LTZ(3),
    window_end    TIMESTAMP_LTZ(3),
    card_number   STRING,
    tx_count      BIGINT,
    total_amount  DOUBLE,
    flagged_reason STRING
) WITH (
    'connector'                    = 'kafka',
    'topic'                        = 'priv.pay.fraud.velocity.delta.v1',
    'properties.bootstrap.servers' = 'kafka-1:19092',
    'value.format'                 = 'avro-confluent',
    'value.avro-confluent.url'     = 'http://schema-registry-1:8081'
);

INSERT INTO pay_fraud_velocity_s
SELECT
    window_start,
    window_end,
    card_number,
    COUNT(*)    AS tx_count,
    SUM(amount) AS total_amount,
    'velocity'  AS flagged_reason
FROM TABLE(
    TUMBLE(TABLE pay_transaction_s, DESCRIPTOR(transaction_date), INTERVAL '10' MINUTE)
)
GROUP BY window_start, window_end, card_number
HAVING COUNT(*) > 3;
```

> **What you should see:** Because ShadowTraffic generates one transaction per card every ~50–500 ms of simulated time, most cards will breach the threshold quickly. This demonstrates the pattern; in production you would tune the window size and threshold to your expected legitimate traffic volume.

---

### Pattern 2 — Amount anomaly (OVER window)

**Signal:** Each cardholder has their own spending profile. A transaction that is three or more times larger than that card's own recent average — not an absolute dollar threshold — is suspicious regardless of the amount. This avoids the false positive problem of a flat global threshold: a $2 000 transaction is normal for a corporate card but alarming for a card that averages $20.

**Why this requires previous records:** The comparison baseline is the card's own rolling 24-hour average. Flink must keep the history of all amounts seen for each card within the last 24 hours in memory (`OVER` window state) to compute that average for each new incoming transaction.

Explore first — the inner subquery computes the rolling stats, the outer query applies the flag:

```sql
SELECT
    transaction_id,
    card_number,
    merchant_id,
    amount,
    transaction_date,
    ROUND(rolling_avg_24h, 2)               AS rolling_avg_24h,
    ROUND(amount / rolling_avg_24h, 1)      AS amount_ratio,
    tx_count_24h,
    CASE
        WHEN tx_count_24h >= 3
         AND amount > 3.0 * rolling_avg_24h THEN 1
        ELSE 0
    END AS is_flagged
FROM (
    SELECT
        transaction_id,
        card_number,
        merchant_id,
        amount,
        transaction_date,
        AVG(amount) OVER (
            PARTITION BY card_number
            ORDER BY transaction_date
            RANGE BETWEEN INTERVAL '24' HOUR PRECEDING AND CURRENT ROW
        ) AS rolling_avg_24h,
        COUNT(*) OVER (
            PARTITION BY card_number
            ORDER BY transaction_date
            RANGE BETWEEN INTERVAL '24' HOUR PRECEDING AND CURRENT ROW
        ) AS tx_count_24h
    FROM pay_transaction_s
);
```

The `tx_count_24h >= 3` guard prevents the first one or two transactions on a card — where there is not yet enough history to establish a baseline — from being flagged spuriously.

Materialize only the flagged rows as a persistent alert stream:

```sql
CREATE TABLE IF NOT EXISTS pay_fraud_amount_anomaly_s (
    transaction_id  STRING,
    card_number     STRING,
    merchant_id     STRING,
    amount          DOUBLE,
    transaction_date TIMESTAMP_LTZ(3),
    rolling_avg_24h DOUBLE,
    amount_ratio    DOUBLE,
    flagged_reason  STRING
) WITH (
    'connector'                    = 'kafka',
    'topic'                        = 'priv.pay.fraud.amount-anomaly.delta.v1',
    'properties.bootstrap.servers' = 'kafka-1:19092',
    'value.format'                 = 'avro-confluent',
    'value.avro-confluent.url'     = 'http://schema-registry-1:8081'
);

INSERT INTO pay_fraud_amount_anomaly_s
SELECT
    transaction_id,
    card_number,
    merchant_id,
    amount,
    transaction_date,
    ROUND(rolling_avg_24h, 2)          AS rolling_avg_24h,
    ROUND(amount / rolling_avg_24h, 1) AS amount_ratio,
    'amount_anomaly'                   AS flagged_reason
FROM (
    SELECT
        transaction_id,
        card_number,
        merchant_id,
        amount,
        transaction_date,
        AVG(amount) OVER (
            PARTITION BY card_number
            ORDER BY transaction_date
            RANGE BETWEEN INTERVAL '24' HOUR PRECEDING AND CURRENT ROW
        ) AS rolling_avg_24h,
        COUNT(*) OVER (
            PARTITION BY card_number
            ORDER BY transaction_date
            RANGE BETWEEN INTERVAL '24' HOUR PRECEDING AND CURRENT ROW
        ) AS tx_count_24h
    FROM pay_transaction_s
)
WHERE tx_count_24h >= 3
  AND amount > 3.0 * rolling_avg_24h;
```

Query the anomalies as they arrive:

```sql
SELECT * FROM pay_fraud_amount_anomaly_s;
```

> **What just happened?** Flink maintains per-card state for every transaction seen in the last 24 hours. For each new transaction it recomputes the rolling average and count over that state, then emits a row only if the threshold is exceeded. The `OVER` window is evaluated row-by-row in event-time order, so the comparison is always against the card's history **up to the moment that transaction occurred** — not including future transactions.

---

### Pattern 3 — Card-testing sequence (`MATCH_RECOGNIZE`)

**Signal:** A common attack pattern is to first make a tiny "probe" transaction (under $5) to verify a stolen card is still active, then immediately follow up with a large purchase (over $200) on the same card. The two events are consecutive on the same card and happen within minutes of each other.

**Why this requires previous records:** `MATCH_RECOGNIZE` scans an ordered sequence of rows partitioned by card number, looking for a specific pattern across consecutive events. Flink buffers all unmatched rows for each card in state until the pattern either completes or the match window expires.

This is an ad-hoc exploratory query — run it in the SQL Client to watch matches appear in real time:

```sql
SELECT
    card_number,
    test_tx_id,
    ROUND(test_amount, 2)  AS test_amount,
    large_tx_id,
    ROUND(large_amount, 2) AS large_amount,
    test_time,
    large_time,
    TIMESTAMPDIFF(SECOND, test_time, large_time) AS seconds_between
FROM pay_transaction_s
MATCH_RECOGNIZE (
    PARTITION BY card_number
    ORDER BY transaction_date
    MEASURES
        TEST.transaction_id    AS test_tx_id,
        TEST.amount            AS test_amount,
        LARGE.transaction_id   AS large_tx_id,
        LARGE.amount           AS large_amount,
        TEST.transaction_date  AS test_time,
        LARGE.transaction_date AS large_time
    ONE ROW PER MATCH
    AFTER MATCH SKIP TO NEXT ROW
    PATTERN (TEST LARGE)
    WITHIN INTERVAL '5' MINUTE
    DEFINE
        TEST  AS amount < 5.0,
        LARGE AS amount > 200.0
) AS M;
```

> **What you should see:** Whenever ShadowTraffic happens to generate a low-amount transaction immediately followed by a high-amount transaction for the same card within 5 simulated minutes, a match row appears. Because the amount distribution is skewed (5 % of transactions are high-value outliers), matches will occur occasionally but not constantly.

You can tighten or relax the pattern by adjusting the thresholds in `DEFINE` or the `WITHIN` interval. You can also extend the pattern — for example `(TEST+ LARGE)` would match one or more probe transactions before the large one.

> **`MATCH_RECOGNIZE` vs `OVER` window:** `OVER` aggregates a metric over a time range and emits one output per input row. `MATCH_RECOGNIZE` looks for a specific multi-row sequence of event types and emits one output per completed match. Use `OVER` when you want a continuously updated statistic; use `MATCH_RECOGNIZE` when you want to detect a specific temporal narrative.

---

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
