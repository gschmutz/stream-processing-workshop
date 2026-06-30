# Real-Time Energy Grid Monitoring with RisingWave

In this workshop you will build a real-time energy grid monitoring system for 20 households. Synthetic energy consumption and solar production data streams flow through Apache Kafka, where RisingWave — a streaming database — ingests the streams, enriches them with customer reference data from PostgreSQL via change-data-capture (CDC), and maintains incrementally updated materialized views that track per-household energy balance and monthly bills in real time.

## Table of Contents

- [What you will learn](#what-you-will-learn)
- [Prerequisites](#prerequisites)
- [Architecture Overview](#architecture-overview)
- [Set Up Reference Data in PostgreSQL](#set-up-reference-data-in-postgresql)
- [Create Kafka Topics](#create-kafka-topics)
- [Start the Data Producers](#start-the-data-producers)
- [Verify Data is Arriving](#verify-data-is-arriving)
- [Connect RisingWave to Sources](#connect-risingwave-to-sources)
- [Create Materialized Views](#create-materialized-views)
- [Query the Results](#query-the-results)
- [Observe Live Updates](#observe-live-updates)
- [Visualize the RisingWave data in Grafana](#visualize-the-risingwave-data-in-grafana)
- [Clean up](#clean-up)

## What you will learn

- What a **streaming database** is and how RisingWave differs from a stream processor like Flink
- How to ingest JSON event streams from Kafka using `CREATE SOURCE`
- How to capture change-data-capture (CDC) updates from PostgreSQL using RisingWave's `postgres-cdc` connector
- How to define **materialized views** that join streaming Kafka data with a CDC-backed reference table
- How to use **tumbling windows** in RisingWave SQL to aggregate energy readings over 5-minute intervals
- How to implement **tiered pricing** and **time-of-use pricing** logic purely in SQL
- How to project a household's end-of-month bill from partial-month data using SQL extrapolation
- How live changes to the reference data (e.g., changing a customer's price plan) automatically propagate through all downstream materialized views

## Prerequisites

- The **Data Platform** (`docker-2`) described in [00-environment](../00-environment) is running and accessible, with Kafka (KRaft, 3 brokers), Schema Registry, Flink (JobManager + TaskManager + SQL Client), Kafka Connect, Spark, Hive Metastore, and S3-compatible object storage (RustFS/MinIO) all healthy
- Basic familiarity with SQL

## Architecture Overview

```
                                      ┌──────────────────────────────┐
 ┌──────────────┐  energy_consumed    │                              │
 │              ├───────────────────► │                              │
 │ Data         │  energy_produced    │         RisingWave           │
 │ Producers    ├───────────────────► │  (Streaming Database)        │
 │ (Python)     │                     │                              │
 └──────────────┘   Apache Kafka      │  ┌────────────────────────┐  │
                                      │  │  Materialized Views    │  │
 ┌──────────────┐                     │  │  ─ energy_per_house    │  │
 │  PostgreSQL  │  CDC (postgres-cdc) │  │  ─ energy_per_month    │  │
 │  customers   ├───────────────────► │  │  ─ current_bill_tiered │  │
 │  table       │                     │  │  ─ estimated_tier_cost │  │
 └──────────────┘                     │  │  ─ current_bill_tou    │  │
                                      │  │  ─ estimated_tou_cost  │  │
                                      │  └────────────────────────┘  │
                                      │                              │
                                      │  Queryable via standard SQL  │
                                      │  (PostgreSQL wire protocol)  │
                                      └──────────────────────────────┘
```

**How the simulator works:**

The two Python data producers simulate an energy grid with 20 metered households. Each producer advances a synthetic clock starting from 1997-05-01 at one simulated minute per 0.8 real seconds (after the first day, which runs at full speed to seed initial data). This means one simulated month passes in roughly 9 real minutes.

| Producer | Kafka topic | What it produces |
|---|---|---|
| `energy-consumed.py` | `energy_consumed` | Per-meter energy consumption (kWh), shaped by time-of-day: morning and evening peaks, lower overnight |
| `energy-produced.py` | `energy_produced` | Per-meter solar production (kWh), shaped by time-of-day (peaks at noon) and season |

Each record contains:

```json
// energy_consumed
{ "consumption_time": "1997-05-01T06:00:00Z", "meter_id": 7, "energy_consumed": 0.032 }

// energy_produced
{ "production_time": "1997-05-01T12:00:00Z", "meter_id": 7, "energy_produced": 0.041 }
```

**What makes RisingWave different from Apache Flink?**

Both RisingWave and Flink can process streaming data with SQL. The key difference is that RisingWave is a *streaming database* — it stores the materialized view results persistently and serves them via a standard PostgreSQL connection at any time, just like querying a table. You never need to write results to an external Kafka topic or storage system for the query layer. With Flink SQL, query results are either emitted to a sink connector or are ephemeral in the CLI session.

## Set Up Reference Data in PostgreSQL

The `customers` table holds static information about each household: their meter ID, address, and pricing plan. RisingWave will ingest this table via CDC and keep its internal copy up to date as rows change.

Connect to PostgreSQL:

```bash
docker exec -it postgresql psql -U postgres -d postgres
```

Create the customers table:

```sql
create table customers (
  "customer_id" SERIAL PRIMARY KEY,
  "meter_id" int,
  "address" varchar(200),
  "price_plan" varchar(200)
);
```

Change setting of table to `REPLICA IDENTITY`, which controls what PostgreSQL writes into its Write-Ahead Log (WAL) when a row is updated or deleted. Setting it to FULL tells PostgreSQL to log the entire old row for every UPDATE and DELETE:

```sql
ALTER TABLE
  public.customers REPLICA IDENTITY FULL;
```

Insert some customers

```sql
INSERT INTO customers (meter_id, address, price_plan)
VALUES
    (1, '123 Elm Street, Springfield, USA', 'tier'),
    (2, '456 Oak Avenue, Shelbyville, USA', 'time of use'),
    (3, '789 Pine Road, Ogdenville, USA', 'tier'),
    (4, '321 Maple Street, Capital City, USA', 'time of use'),
    (5, '654 Cedar Avenue, North Haverbrook, USA', 'tier'),
    (6, '987 Birch Lane, Springfield, USA', 'time of use'),
    (7, '432 Walnut Street, Shelbyville, USA', 'tier'),
    (8, '876 Chestnut Avenue, Ogdenville, USA', 'time of use'),
    (9, '543 Ash Road, Capital City, USA', 'tier'),
    (10, '109 Willow Street, North Haverbrook, USA', 'time of use'),
    (11, '222 Elm Street, Springfield, USA', 'tier'),
    (12, '333 Oak Avenue, Shelbyville, USA', 'time of use'),
    (13, '444 Pine Road, Ogdenville, USA', 'tier'),
    (14, '555 Maple Street, Capital City, USA', 'time of use'),
    (15, '666 Cedar Avenue, North Haverbrook, USA', 'tier'),
    (16, '912 Magnolia Plaza, North Haverbrook, USA', 'time of use'),
    (17, '777 Birch Lane, Springfield, USA', 'tier'),
    (18, '888 Walnut Street, Shelbyville, USA', 'time of use'),
    (19, '999 Chestnut Avenue, Ogdenville, USA', 'time of use'),
    (20, '101 Ash Road, Capital City, USA', 'tier');
```

Verify the data loaded:

```sql
SELECT customer_id, meter_id, price_plan FROM customers ORDER BY meter_id;
```

You should see 20 rows — 10 customers on the `tier` plan and 10 on `time of use`.

> **What just happened?** The script created a `customers` table, set `REPLICA IDENTITY FULL` (required so PostgreSQL's WAL includes the full row image for every change, not just the primary key), created a publication named `customers_pub` that RisingWave will subscribe to, and inserted 20 seed rows.

## Create Kafka Topics

The docker-2 platform has auto topic creation disabled. Create the two topics before starting the producers:

```bash
docker exec -it kafka-1 kafka-topics \
  --bootstrap-server kafka-1:19092 \
  --create --topic energy_consumed \
  --partitions 3 --replication-factor 3

docker exec -it kafka-1 kafka-topics \
  --bootstrap-server kafka-1:19092 \
  --create --topic energy_produced \
  --partitions 3 --replication-factor 3
```

Confirm both topics exist:

```bash
docker exec -it kafka-1 kafka-topics \
  --bootstrap-server kafka-1:19092 --list | grep energy
```

## Start the Data Producers

The data producers are Python scripts in `scripts/kafka-producer-app/`. You can run them as Docker containers on the same network as the Platys platform.

We will use a `docker-compose.override.yml` to create and start the docker container:

```yml
services:

  kafka-producer-app:
    build:
      context: .
      dockerfile: scripts/docker/kafka-producer-app/Dockerfile
    container_name: kafka-producer-app
    hostname: kafka-producer-app
    depends_on:
     - kafka-1
    environment:
      KAFKA_BOOTSTRAP_SERVERS: kafka-1:19092
    restart: always
```

Copy these artefacts into the dataplatform folder:

```bash
cp $DATAPLATFORM_HOME/../../09-streaming-db-with-risingwave/docker-compose.override.yml $DATAPLATFORM_HOME/

cp -R $DATAPLATFORM_HOME/../../09-streaming-db-with-risingwave/scripts/kafka-producer-app $DATAPLATFORM_HOME/scripts/docker/
```

Build the producer image and start the container:

```bash
cd $DATAPLATFORM_HOME
docker compose up -d --build
```

Check that the container is running:

```bash
docker logs kafka-producer-app --tail 20
```

## Verify Data is Arriving

Confirm records are landing in both topics:

```bash
docker exec -ti kcat kcat -b kafka-1:19092 -t energy_consumed -C -q -o end
```

```bash
docker exec -ti kcat kcat -b kafka-1:19092 -t energy_produced -C -q -o end
```

> **What you should see:** A continuous stream of JSON records, one per meter per simulated minute (20 meters, so ~20 records every 0.8 seconds). Press **Ctrl-C** to stop.

Count the messages already in each topic:

```bash
docker exec -ti kcat kcat -b kafka-1:19092 -t energy_consumed -C -e -q | wc -l
docker exec -ti kcat kcat -b kafka-1:19092 -t energy_produced -C -e -q | wc -l
```

## Connect RisingWave to Sources

RisingWave exposes a PostgreSQL-compatible SQL interface on port 4566. The `risingwave` container does not ship with `psql`, but the `postgresql` container on the same Docker network does. Connect via:

```bash
docker exec -it postgresql psql -h risingwave -p 4566 -d dev -U root
```

Or from the host if you have `psql` installed locally:

```bash
psql -h localhost -p 4566 -d dev -U root
```

### Create the Kafka sources

`CREATE SOURCE` tells RisingWave where to read streaming data from. Unlike a materialized view, a source by itself does not persist data — it describes the shape and location of the stream.

```sql
CREATE SOURCE IF NOT EXISTS energy_consume (
    consumption_time TIMESTAMPTZ,
    meter_id         INTEGER,
    energy_consumed  DOUBLE PRECISION
) WITH (
    connector                   = 'kafka',
    topic                       = 'energy_consumed',
    properties.bootstrap.server = 'kafka-1:19092',
    scan.startup.mode           = 'earliest'
) FORMAT PLAIN ENCODE JSON;

CREATE SOURCE IF NOT EXISTS energy_produce (
    production_time TIMESTAMPTZ,
    meter_id        INTEGER,
    energy_produced DOUBLE PRECISION
) WITH (
    connector                   = 'kafka',
    topic                       = 'energy_produced',
    properties.bootstrap.server = 'kafka-1:19092',
    scan.startup.mode           = 'earliest'
) FORMAT PLAIN ENCODE JSON;
```

Verify the sources were created:

```sql
SHOW SOURCES;
```

Sample a few records to confirm the schema:

```sql
SELECT * FROM energy_consume LIMIT 5;
SELECT * FROM energy_produce LIMIT 5;
```

### Create the PostgreSQL CDC source and table

RisingWave's `postgres-cdc` connector connects to PostgreSQL's logical replication stream and maintains an always-current internal copy of the specified table.

```sql
CREATE SOURCE IF NOT EXISTS pg_mydb WITH (
    connector        = 'postgres-cdc',
    hostname         = 'postgresql',
    port             = '5432',
    username         = 'postgres',
    password         = 'abc123!',
    database.name    = 'postgres',
    publication.name = 'customers_pub',
    slot.name        = 'risingwave_customers_slot'
);

CREATE TABLE IF NOT EXISTS customers (
    customer_id INT,
    meter_id    INT,
    address     VARCHAR,
    price_plan  VARCHAR,
    PRIMARY KEY (customer_id)
) FROM pg_mydb TABLE 'public.customers';
```

Verify the CDC table is populated:

```sql
SELECT * FROM customers ORDER BY meter_id;
```

> **What just happened?** RisingWave connected to PostgreSQL as a logical replication client, read the initial snapshot of the `customers` table, and is now tailing the WAL for any future inserts, updates, or deletes. Any change you make in PostgreSQL will automatically propagate into RisingWave's internal copy within milliseconds.

## Create Materialized Views

Materialized views in RisingWave are persistent, incrementally maintained query results. RisingWave updates them continuously as new events arrive — you never need to re-run a query or schedule a refresh job.

### Helper function

First create a helper SQL function that returns the number of days in a given month (used later for bill projection):

```sql
CREATE FUNCTION IF NOT EXISTS count_days(a TIMESTAMPTZ)
RETURNS NUMERIC LANGUAGE SQL AS
$$SELECT EXTRACT(DAY FROM (DATE_TRUNC('month', a) + INTERVAL '1 month' - INTERVAL '1 day'))$$;
```

### 1. Per-household energy balance (5-minute windows)

This view joins the consumption and production streams over 5-minute tumbling windows. The result is the net energy drawn from the grid (`total_energy = consumed − produced`) for each meter in each window.

```sql
CREATE MATERIALIZED VIEW IF NOT EXISTS energy_per_house AS
SELECT
    consumed.meter_id,
    energy_consumed,
    energy_produced,
    energy_consumed - energy_produced AS total_energy,
    consumed.window_end
FROM (
    SELECT
        meter_id,
        SUM(energy_consumed) AS energy_consumed,
        window_end
    FROM TUMBLE(energy_consume, consumption_time, INTERVAL '5' MINUTE)
    GROUP BY meter_id, window_end
) AS consumed
JOIN (
    SELECT
        meter_id,
        SUM(energy_produced) AS energy_produced,
        window_end
    FROM TUMBLE(energy_produce, production_time, INTERVAL '5' MINUTE)
    GROUP BY meter_id, window_end
) AS produced
    ON consumed.meter_id   = produced.meter_id
   AND consumed.window_end = produced.window_end;
```

Check it is already populated:

```sql
SELECT * FROM energy_per_house ORDER BY window_end DESC, meter_id LIMIT 20;
```

### 2. Monthly energy rollup per meter

Aggregates the 5-minute windows up to a monthly total:

```sql
CREATE MATERIALIZED VIEW IF NOT EXISTS energy_per_month AS
SELECT
    meter_id,
    SUM(total_energy)               AS total_energy,
    DATE_TRUNC('month', window_end) AS month,
    DATE_TRUNC('year',  window_end) AS year
FROM energy_per_house
GROUP BY meter_id,
         DATE_TRUNC('month', window_end),
         DATE_TRUNC('year',  window_end);
```

### 3. Split meters by price plan

Households have either a flat-tiered plan or a time-of-use plan. These views filter energy readings by joining against the CDC-backed `customers` table:

```sql
CREATE MATERIALIZED VIEW IF NOT EXISTS tiered_meters AS
SELECT customers.meter_id, total_energy, window_end
FROM energy_per_house
LEFT JOIN customers ON energy_per_house.meter_id = customers.meter_id
WHERE customers.price_plan = 'tier';

CREATE MATERIALIZED VIEW IF NOT EXISTS tou_meters AS
SELECT customers.meter_id, total_energy, window_end
FROM energy_per_house
LEFT JOIN customers ON energy_per_house.meter_id = customers.meter_id
WHERE customers.price_plan = 'time of use';
```

### 4. Current month bill — tiered plan

Tiered pricing: first 200 kWh at $0.20/kWh, anything above 200 kWh at $0.40/kWh:

```sql
CREATE MATERIALIZED VIEW IF NOT EXISTS current_bill_tiered AS
WITH monthly_consumption AS (
    SELECT
        meter_id,
        DATE_TRUNC('month', window_end) AS month,
        DATE_TRUNC('year',  window_end) AS year,
        SUM(total_energy)               AS total_monthly_energy
    FROM tiered_meters
    GROUP BY meter_id, DATE_TRUNC('month', window_end), DATE_TRUNC('year', window_end)
),
estimated_bills AS (
    SELECT
        meter_id, total_monthly_energy, month, year,
        CASE
            WHEN total_monthly_energy <= 200
                THEN total_monthly_energy * 0.2
            ELSE (200 * 0.20) + ((total_monthly_energy - 200) * 0.4)
        END AS estimated_bill_amount
    FROM monthly_consumption
)
SELECT meter_id, SUM(estimated_bill_amount) AS current_bill, month, year
FROM estimated_bills
GROUP BY meter_id, month, year;
```

### 5. Projected end-of-month bill — tiered plan

Extrapolates the current daily average to the full month:

```sql
CREATE MATERIALIZED VIEW IF NOT EXISTS estimated_tier_cost AS
WITH truncated_month AS (
    SELECT * FROM tiered_meters
    WHERE DATE_TRUNC('day', window_end) < (
        SELECT MAX(DATE_TRUNC('day', window_end)) FROM energy_per_house
    )
),
daily_consumption AS (
    SELECT meter_id, DATE_TRUNC('day', window_end) AS days, SUM(total_energy) AS daily_energy
    FROM truncated_month
    GROUP BY meter_id, DATE_TRUNC('day', window_end)
),
projected AS (
    SELECT
        meter_id,
        SUM(daily_energy) AS total_energy_so_far,
        (SUM(daily_energy) / DATE_PART('day', MAX(days)))
            * count_days(DATE_TRUNC('month', days)) AS estimated_monthly_energy,
        DATE_TRUNC('month', days) AS month,
        DATE_TRUNC('year',  days) AS year
    FROM daily_consumption
    GROUP BY meter_id, DATE_TRUNC('month', days), DATE_TRUNC('year', days)
),
estimated_bills AS (
    SELECT
        meter_id, estimated_monthly_energy, month, year,
        CASE
            WHEN estimated_monthly_energy <= 200
                THEN estimated_monthly_energy * 0.2
            ELSE (200 * 0.20) + ((estimated_monthly_energy - 200) * 0.4)
        END AS estimated_bill_amount
    FROM projected
)
SELECT
    meter_id,
    SUM(estimated_bill_amount)    AS estimated_total_bill,
    SUM(estimated_monthly_energy) AS estimated_total_energy,
    month
FROM estimated_bills
GROUP BY meter_id, month;
```

### 6. Current month bill — time-of-use plan

Peak hours (16:00–20:00): $0.40/kWh. Off-peak: $0.20/kWh:

```sql
CREATE MATERIALIZED VIEW IF NOT EXISTS current_bill_tou AS
WITH hourly_cost AS (
    SELECT
        meter_id,
        DATE_TRUNC('month', window_end) AS month,
        DATE_TRUNC('year',  window_end) AS year,
        CASE
            WHEN DATE_PART('hour', window_end) BETWEEN 16 AND 20 THEN total_energy * 0.4
            ELSE total_energy * 0.2
        END AS cost
    FROM tou_meters
),
month_cost AS (
    SELECT meter_id, month, year, SUM(cost) AS monthly_cost
    FROM hourly_cost
    GROUP BY meter_id, month, year
)
SELECT month_cost.meter_id, monthly_cost, month_cost.month, month_cost.year
FROM month_cost
LEFT JOIN energy_per_month
    ON month_cost.meter_id = energy_per_month.meter_id
   AND month_cost.month    = energy_per_month.month
   AND month_cost.year     = energy_per_month.year;
```

### 7. Projected end-of-month bill — time-of-use plan

```sql
CREATE MATERIALIZED VIEW IF NOT EXISTS estimated_tou_cost AS
WITH truncated_month AS (
    SELECT * FROM tou_meters
    WHERE DATE_TRUNC('day', window_end) < (
        SELECT MAX(DATE_TRUNC('day', window_end)) FROM energy_per_house
    )
),
hourly AS (
    SELECT
        meter_id,
        SUM(total_energy)               AS daily_energy,
        DATE_PART('hour', window_end)   AS hour,
        DATE_PART('day',  window_end)   AS day,
        DATE_TRUNC('month', window_end) AS month,
        DATE_TRUNC('year',  window_end) AS year
    FROM truncated_month
    GROUP BY meter_id,
             DATE_PART('hour', window_end), DATE_PART('day', window_end),
             DATE_TRUNC('month', window_end), DATE_TRUNC('year', window_end)
)
SELECT
    meter_id,
    (SUM(CASE WHEN hour BETWEEN 16 AND 20 THEN daily_energy * 0.4 ELSE daily_energy * 0.2 END)
        / MAX(day)) * count_days(month)   AS estimated_monthly_bill,
    (SUM(daily_energy) / MAX(day)) * count_days(month) AS estimated_total_energy,
    month
FROM hourly
GROUP BY meter_id, month;
```

Confirm all materialized views are active:

```sql
SHOW MATERIALIZED VIEWS;
```

> **What just happened?** RisingWave registered each materialized view as a continuous query. Unlike a traditional database view (which re-executes on every query), RisingWave maintains the result incrementally: as each new batch of Kafka records arrives, only the affected rows in the materialized view are updated. The billing views stay current without any scheduled jobs or manual refreshes.

## Query the Results

All queries below run instantly because RisingWave has pre-computed and continuously maintained the results.

### Real-time energy balance per household

Show the latest 5-minute net energy reading for each meter:

```sql
SELECT
    meter_id,
    ROUND(energy_consumed::NUMERIC, 4)  AS consumed_kwh,
    ROUND(energy_produced::NUMERIC, 4)  AS produced_kwh,
    ROUND(total_energy::NUMERIC, 4)     AS net_kwh,
    window_end
FROM energy_per_house
WHERE window_end = (SELECT MAX(window_end) FROM energy_per_house)
ORDER BY meter_id;
```

### Monthly energy consumption per meter

```sql
SELECT
    meter_id,
    ROUND(total_energy::NUMERIC, 2) AS total_kwh,
    TO_CHAR(month, 'YYYY-MM')       AS month
FROM energy_per_month
ORDER BY month, meter_id;
```

### Meters with the highest net energy draw (most dependent on the grid)

```sql
SELECT
    meter_id,
    ROUND(SUM(total_energy)::NUMERIC, 2) AS total_net_kwh
FROM energy_per_house
GROUP BY meter_id
ORDER BY total_net_kwh DESC
LIMIT 10;
```

### Current bills for tiered customers

```sql
SELECT
    c.address,
    b.meter_id,
    ROUND(b.current_bill::NUMERIC, 2) AS current_bill_usd,
    TO_CHAR(b.month, 'YYYY-MM')       AS month
FROM current_bill_tiered b
JOIN customers c ON b.meter_id = c.meter_id
ORDER BY b.month, b.meter_id;
```

### Projected end-of-month bills for tiered customers

```sql
SELECT
    c.address,
    e.meter_id,
    ROUND(e.estimated_total_energy::NUMERIC, 2) AS est_total_kwh,
    ROUND(e.estimated_total_bill::NUMERIC, 2)   AS est_total_bill_usd,
    TO_CHAR(e.month, 'YYYY-MM')                  AS month
FROM estimated_tier_cost e
JOIN customers c ON e.meter_id = c.meter_id
ORDER BY e.month, e.meter_id;
```

### Current bills for time-of-use customers

```sql
SELECT
    c.address,
    b.meter_id,
    ROUND(b.monthly_cost::NUMERIC, 2) AS current_bill_usd,
    TO_CHAR(b.month, 'YYYY-MM')        AS month
FROM current_bill_tou b
JOIN customers c ON b.meter_id = c.meter_id
ORDER BY b.month, b.meter_id;
```

### Households with the highest projected bill this month

```sql
SELECT
    c.address,
    c.price_plan,
    e.meter_id,
    ROUND(e.estimated_monthly_bill::NUMERIC, 2) AS projected_bill_usd,
    TO_CHAR(e.month, 'YYYY-MM')                  AS month
FROM estimated_tou_cost e
JOIN customers c ON e.meter_id = c.meter_id
ORDER BY projected_bill_usd DESC
LIMIT 5;
```

### Side-by-side bill comparison

Compare what each household is paying versus what they are projected to pay by month-end:

```sql
SELECT
    c.meter_id,
    c.price_plan,
    CASE
        WHEN c.price_plan = 'tier'        THEN ROUND(b.current_bill::NUMERIC, 2)
        WHEN c.price_plan = 'time of use' THEN ROUND(t.monthly_cost::NUMERIC, 2)
    END AS current_bill_usd,
    CASE
        WHEN c.price_plan = 'tier'        THEN ROUND(et.estimated_total_bill::NUMERIC, 2)
        WHEN c.price_plan = 'time of use' THEN ROUND(eu.estimated_monthly_bill::NUMERIC, 2)
    END AS projected_bill_usd
FROM customers c
LEFT JOIN current_bill_tiered  b  ON c.meter_id = b.meter_id
LEFT JOIN current_bill_tou     t  ON c.meter_id = t.meter_id
LEFT JOIN estimated_tier_cost  et ON c.meter_id = et.meter_id
LEFT JOIN estimated_tou_cost   eu ON c.meter_id = eu.meter_id
ORDER BY c.meter_id;
```

## Observe Live Updates

### Watch a view update in real time

Run the same query twice, a few seconds apart, to see the values change:

```sql
SELECT meter_id, ROUND(total_energy::NUMERIC, 3) AS net_kwh, window_end
FROM energy_per_house
WHERE window_end = (SELECT MAX(window_end) FROM energy_per_house)
ORDER BY meter_id;
```

### Change a customer's price plan and observe the effect

Open a second terminal, connect to PostgreSQL, and switch meter 1 from `tier` to `time of use`:

```bash
docker exec -it postgresql psql -U postgres -d postgres
```

```sql
UPDATE customers SET price_plan = 'time of use' WHERE meter_id = 1;
```

Return to the RisingWave session and re-query the billing views. Within a few seconds, meter 1 will have disappeared from the tiered views and appeared in the time-of-use views — without restarting any job or refreshing any query.

```sql
-- Meter 1 should no longer appear here
SELECT * FROM current_bill_tiered WHERE meter_id = 1;

-- Meter 1 should now appear here
SELECT * FROM current_bill_tou WHERE meter_id = 1;
```

> **What just happened?** RisingWave detected the CDC change from PostgreSQL's WAL, updated its internal `customers` table, and then re-evaluated all downstream materialized views that reference it. The pricing plan change propagated automatically through the entire chain — `tiered_meters` → `current_bill_tiered` and `tou_meters` → `current_bill_tou` — with no manual intervention required. This is the key advantage of a streaming database: the entire pipeline is a live, reactive graph.

### Check materialized view statistics

```sql
SELECT * FROM rw_materialized_views;
```

### Describe a view's definition

```sql
DESCRIBE energy_per_house;
```

## Visualize the RisingWave data in Grafana

[Grafana](https://grafana.com) is an open-source observability and dashboarding platform that can connect to a wide range of data sources — including PostgreSQL and TimescaleDB — and render time-series data as interactive charts, gauges, and tables. It runs as a web application and requires no client installation beyond a browser. In this workshop Grafana reads directly from TimescaleDB using standard SQL queries and displays the energy sensor readings as live time-series panels.

### Open Grafana

In a browser navigate to <http://dataplatform:3000>. Log in with:

- **User**: `admin`
- **Password**: `abc123!`

> **What you should see:** the Grafana home screen after a successful login.

### Check RisingWave data source

RisingWave as a PostgreSQL data source is already registered in Grafana as part of the dataplatform. You can check it by clicking **Connections** → **Data sources** in the left side bar and you should see the **risingwave** data source. Click on the datasource and at the bottom of the page click **Save & test**. 

> **What you should see:** a green **Database Connection OK** banner confirming Grafana can reach TimescaleDB.

### Import the Grid Monitoring dashboard

A pre-built dashboard is provided in the `grafana/` folder of this workshop.

1. In the left sidebar click **Dashboards** → **New** → **Import**.
2. Click **Upload dashboard JSON file** and select the file `grafana/energy-monitoring.json` from this workshop folder.
3. Click **Import**.

![Alt Image Text](./images/grafana-dashboard.png "Grafana Dashboard")

> **What you should see:** the **Energy Monitoring** dashboard opens with time-series panels showing sensor readings (heating, lighting, cooling, etc.) per factory, updating as new messages flow through the pipeline. Use the **Factory** drop-down at the top of the dashboard to filter the panels to a specific factory.


## Clean up

To drop all objects created in this workshop:

```sql
DROP MATERIALIZED VIEW IF EXISTS estimated_tou_cost;
DROP MATERIALIZED VIEW IF EXISTS current_bill_tou;
DROP MATERIALIZED VIEW IF EXISTS estimated_tier_cost;
DROP MATERIALIZED VIEW IF EXISTS current_bill_tiered;
DROP MATERIALIZED VIEW IF EXISTS tou_meters;
DROP MATERIALIZED VIEW IF EXISTS tiered_meters;
DROP MATERIALIZED VIEW IF EXISTS energy_per_month;
DROP MATERIALIZED VIEW IF EXISTS energy_per_house;
DROP TABLE IF EXISTS customers;
DROP SOURCE IF EXISTS pg_mydb;
DROP SOURCE IF EXISTS energy_produce;
DROP SOURCE IF EXISTS energy_consume;
DROP FUNCTION IF EXISTS count_days;
```

Stop the data producers:

```bash
cd scripts/data-producer && docker compose down
```
