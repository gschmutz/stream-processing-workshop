"""
PyFlink pipeline: blacklist-flag transactions and enrich with merchant details.

Reads from:
  - pay_transaction_t    (raw transaction stream)
  - pay_blacklist_t      (compacted blacklist of merchant IDs)
  - ref_merchant_t       (compacted merchant reference data)

Writes to:
  - pay_transaction_flagged_enriched_t  (blacklist flag + merchant name/country/city/category)

"""

from pyflink.datastream import StreamExecutionEnvironment
from pyflink.table import StreamTableEnvironment, EnvironmentSettings
from pyflink.table.catalog import HiveCatalog
from pyflink.table.expressions import col, lit, if_then_else


BOOTSTRAP_SERVERS = "kafka-1:19092"
SCHEMA_REGISTRY_URL = "http://schema-registry-1:8081"


def register_tables(t_env: StreamTableEnvironment) -> None:
    # CREATE TABLE DDL must stay as SQL — there is no programmatic API for connector properties

    t_env.execute_sql(f"""
        CREATE TABLE IF NOT EXISTS pay_transaction_t (
            transaction_id   STRING,
            card_number      STRING,
            merchant_id      STRING,
            amount           DOUBLE,
            currency         STRING,
            channel          STRING,
            transaction_date TIMESTAMP(3),
            WATERMARK FOR transaction_date AS transaction_date - INTERVAL '5' SECOND
        ) WITH (
            'connector'                                = 'kafka',
            'topic'                                    = 'priv.pay.transaction.delta.v1',
            'properties.bootstrap.servers'             = '{BOOTSTRAP_SERVERS}',
            'properties.group.id'                      = 'flink-pay-transaction',
            'scan.startup.mode'                        = 'earliest-offset',
            'properties.fetch.max.bytes'               = '1048576',
            'properties.max.partition.fetch.bytes'     = '1048576',
            'value.format'                             = 'avro-confluent',
            'value.avro-confluent.url'                 = '{SCHEMA_REGISTRY_URL}'
        )
    """)

    t_env.execute_sql(f"""
        CREATE TABLE IF NOT EXISTS pay_blacklist_t (
            `key`       STRING,
            merchant_id STRING,
            PRIMARY KEY (`key`) NOT ENFORCED
        ) WITH (
            'connector'                    = 'upsert-kafka',
            'topic'                        = 'priv.pay.blacklist.state.v1',
            'properties.bootstrap.servers' = '{BOOTSTRAP_SERVERS}',
            'key.format'                   = 'avro-confluent',
            'key.avro-confluent.url'       = '{SCHEMA_REGISTRY_URL}',
            'value.format'                 = 'avro-confluent',
            'value.avro-confluent.url'     = '{SCHEMA_REGISTRY_URL}'
        )
    """)

    t_env.execute_sql(f"""
        CREATE TABLE IF NOT EXISTS ref_merchant_t (
            merchant_id   STRING,
            name          STRING,
            country       STRING,
            city          STRING,
            category_name STRING,
            PRIMARY KEY (merchant_id) NOT ENFORCED
        ) WITH (
            'connector'                    = 'upsert-kafka',
            'topic'                        = 'pub.ref.merchant.state.v1',
            'properties.bootstrap.servers' = '{BOOTSTRAP_SERVERS}',
            'key.format'                   = 'raw',
            'value.format'                 = 'avro-confluent',
            'value.avro-confluent.url'     = '{SCHEMA_REGISTRY_URL}'
        )
    """)

    t_env.execute_sql(f"""
        CREATE TABLE IF NOT EXISTS pay_transaction_flagged_enriched_py_t (
            transaction_id   STRING,
            card_number      STRING,
            currency         STRING,
            amount           DOUBLE,
            channel          STRING,
            transaction_date TIMESTAMP(3),
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
            'topic'                        = 'priv.pay.transaction-flagged-enriched-py.delta.v1',
            'properties.bootstrap.servers' = '{BOOTSTRAP_SERVERS}',
            'key.format'                   = 'avro-confluent',
            'key.avro-confluent.url'       = '{SCHEMA_REGISTRY_URL}',
            'value.format'                 = 'avro-confluent',
            'value.avro-confluent.url'     = '{SCHEMA_REGISTRY_URL}'
        )
    """)


def build_pipeline(t_env: StreamTableEnvironment) -> None:
    transactions = t_env.from_path("pay_transaction_t")

    # Pre-project blacklist to a single column to avoid merchant_id ambiguity after join
    blacklist = (
        t_env.from_path("pay_blacklist_t")
        .select(col("key").alias("bl_key"))
    )

    # Pre-project merchant reference to rename merchant_id and name, avoiding post-join conflicts
    merchants = (
        t_env.from_path("ref_merchant_t")
        .select(
            col("merchant_id").alias("ref_merchant_id"),
            col("name").alias("merchant_name"),
            col("country"),
            col("city"),
            col("category_name"),
        )
    )

    # Step 1 — left join with blacklist; set flag and reason
    flagged = (
        transactions
        .left_outer_join(blacklist, col("merchant_id") == col("bl_key"))
        .select(
            col("transaction_id"),
            col("card_number"),
            col("currency"),
            col("amount"),
            col("channel"),
            col("transaction_date"),
            col("merchant_id"),
            if_then_else(col("bl_key").is_not_null, lit(1), lit(0))
                .alias("is_flagged"),
            if_then_else(col("bl_key").is_not_null, lit("blacklist"), lit(""))
                .alias("flagged_reason"),
        )
    )

    # Step 2 — left join with merchant reference; add name / location / category
    result = (
        flagged
        .left_outer_join(merchants, col("merchant_id") == col("ref_merchant_id"))
        .select(
            col("transaction_id"),
            col("card_number"),
            col("currency"),
            col("amount"),
            col("channel"),
            col("transaction_date"),
            col("is_flagged"),
            col("flagged_reason"),
            col("merchant_id"),
            col("merchant_name"),
            col("country"),
            col("city"),
            col("category_name"),
        )
    )

    result.execute_insert("pay_transaction_flagged_enriched_py_t").wait()


HIVE_CONF_DIR = "/opt/hive-conf"
CATALOG_NAME  = "hive_catalog"
DATABASE_NAME = "fraud_detection"


def main() -> None:
    env = StreamExecutionEnvironment.get_execution_environment()
    t_env = StreamTableEnvironment.create(
        env,
        EnvironmentSettings.in_streaming_mode(),
    )

    catalog = HiveCatalog(CATALOG_NAME, DATABASE_NAME, HIVE_CONF_DIR)
    t_env.register_catalog(CATALOG_NAME, catalog)
    t_env.use_catalog(CATALOG_NAME)
    t_env.use_database(DATABASE_NAME)

    register_tables(t_env)
    build_pipeline(t_env)


if __name__ == "__main__":
    main()
