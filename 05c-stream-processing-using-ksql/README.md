# IoT Data Ingestion - Stream Processing using ksqlDB

With the truck data continuously ingested into the `truck_movement` topic, let's now perform some stream processing on the data.
 
There are many possible solutions for performing analytics directly on the event stream. From the Kafka ecosystem, we can either use Kafka Streams or ksqlDB, a SQL abstraction on top of Kafka Streams. For this workshop we will be using KSQL. 

![Alt Image Text](./images/stream-processing-with-ksql-overview.png "Schema Registry UI")

## Connect to ksqlDB engine
 
An instance of a ksqlDB server is part of the Data Platform and started as service `ksqldb-server-1`. It can be reached on port 8088. Additionally the ksqlDB CLI is also running as service `ksqldb-cli`. 

Let's use the CLI by doing an `docker exec` into the running docker container

```
docker exec -it ksqldb-cli ksql http://ksqldb-server-1:8088
```

and you should see the ksqlDB "welcome page":

```
                  ===========================================
                  =       _              _ ____  ____       =
                  =      | | _____  __ _| |  _ \| __ )      =
                  =      | |/ / __|/ _` | | | | |  _ \      =
                  =      |   <\__ \ (_| | | |_| | |_) |     =
                  =      |_|\_\___/\__, |_|____/|____/      =
                  =                   |_|                   =
                  =  Event Streaming Database purpose-built =
                  =        for stream processing apps       =
                  ===========================================

Copyright 2017-2020 Confluent Inc.

CLI v0.9.0, Server v0.9.0 located at http://ksqldb-server-1:8088

Having trouble? Type 'help' (case-insensitive) for a rundown of how things work!
```

We can use the show command to show topics as well as streams and tables. We have not yet created streams and tables, therefore we won't see anything (except of the internal `ksql_processing_log` stream):

```
show topics;
show streams;
show tables;
```

Let's bring ksqlDB to action. 

## Working with KSQL in an ad-hoc fashion

KSQL is a SQL like dialect, but instead of reading from static tables, as you know from using it with databases, in KSQL we mostly read from data streams. In the Kafka world, a data stream is available through a Kafka topic. 

ksqlDB can be used for doing ad-hoc queries as well as running continuous queries in the background. Let's first doing some ad-hoc queries to familiarise ourselves with the data on the `truck_position` topic. 

### Give the truck_position topic a structure

Before we can use a KSQL SELECT statement and consume data from a data stream, we have to give the data in the `truck_position` topic a "face", by defining the structure of the data. We do that using the `CREATE STREAM ...` command, as shown below: 

```
DROP STREAM truck_position_s;

CREATE STREAM truck_position_s
  (ts VARCHAR,
   truckId VARCHAR,
   driverId BIGINT,
   routeId BIGINT, 
   eventType VARCHAR,
   latitude DOUBLE,
   longitude DOUBLE,
   correlationId VARCHAR)
  WITH (kafka_topic='truck_position',
        value_format='DELIMITED');
```

With the `truck_position_s` Stream in place, we can use the `SELECT` statement to query live messages while they are being sent to the Kafka topic. 

### Using KSQL to find abnormal driver behaviour

First let's find out abnormal driver behaviour by selecting all the events where the event type is not `Normal`.
        
```
SELECT * FROM truck_position_s EMIT CHANGES;
```

This is not that much different from using the `kafka-console-consumer` or `kafkacat`. But of course with KSQL you can do much more. You have the power of SQL-like language at hand. Stop the statement with `Ctl-C`. 

So let's start using the WHERE clause, so that we only view the events where the event type is not `Normal`. 

```
SELECT * FROM truck_position_s 
WHERE eventType != 'Normal'
EMIT CHANGES;
```

It  will now take much longer until we see a result, as the non-normal behaviour is not occurring so often. So be patient!

This is interesting data, but just seeing it in the KSQL terminal is of limited value. We would like to have that information available as a new Kafka topic, so we can further process it using KSQL or allow other subscriber to work with that information.  

## Using ksqlDB to constantly publish results to a new topic 

For publishing the resulting data to a new Kafka topic, we first have to create the Kafka topic. 

As we have learnt before, connect to one of the broker container instances

```
docker exec -ti kafka-1 bash
```

and perform the following command to create the `dangerous_driving_ksql` topic in Kafka.

```
kafka-topics --zookeeper zookeeper-1:2181 --create --topic dangerous_driving_ksql --partitions 8 --replication-factor 3
```

Now let's publish to that topic from KSQL. For that we can create a new Stream. Instead of creating it on an existing topic as we have done before, we use the `CREATE STREAM ... AS SELECT ...` variant. 

```
DROP STREAM dangerous_driving_s;

CREATE STREAM dangerous_driving_s
  WITH (kafka_topic='dangerous_driving_ksql',
        value_format='DELIMITED', 
        partitions=8)
AS 
SELECT * 
FROM truck_position_s
WHERE eventtype != 'Normal'
EMIT CHANGES;
```

The `SELECT` statement inside is basically the statement we have tested before and we know it will create the right information. 

We can use a `DESCRIBE` command to see metadata of any stream: 

```
DESCRIBE dangerous_driving_s;        
```

which should return an output similar to the one shown below:

```
ksql> DESCRIBE dangerous_driving_s;
Name                 : DANGEROUS_DRIVING_S
 Field         | Type
-------------------------------------------
 ROWTIME       | BIGINT           (system)
 ROWKEY        | VARCHAR(STRING)  (system)
 TS            | VARCHAR(STRING)
 TRUCKID       | VARCHAR(STRING)
 DRIVERID      | BIGINT
 ROUTEID       | BIGINT
 EVENTTYPE     | VARCHAR(STRING)
 LATITUDE      | DOUBLE
 LONGITUDE     | DOUBLE
 CORRELATIONID | VARCHAR(STRING)
-------------------------------------------
For runtime statistics and query details run: DESCRIBE EXTENDED <Stream,Table>;
```

Now it's much easier to get the abnormal behaviour. All we have to do is selecting that new stream `truck_position_s`. 

```
SELECT * FROM dangerous_driving_s
EMIT CHANGES;
```

This stream is backed by the Kafka topic `dangerous_driving_ksql` so we can also use any Kafka consumer to directly get the data from there. Let's see it by either using `kafka-console-consumer` 

```
docker exec -ti kafka-1 bash
```

```
kafka-console-consumer --bootstrap-server broker-1:9092 \
     --topic dangerous_driving_ksql
```

or `kafkacat`

```
docker exec -ti kafkacat kafkacat -b kafka-1 -t dangerous_driving_ksql
```

You should see the same abnormal driving behaviour data as before in the ksqlDB shell.        

## Perform some more advanced analytics on the stream


Let's see how many abnormal events do we get per 20 seconds tumbling window

```
SELECT eventType, count(*) 
FROM dangerous_driving_s 
WINDOW TUMBLING (size 20 seconds)
GROUP BY eventType
EMIT CHANGES;
```

----

[previous part](../05b-iot-data-ingestion-mqtt-to-kafka/README.md)	| 	[top](../05-iot-data-ingestion-and-analytics/README.md) 	| 	[next part](../05d-static-data-ingestion/README.md)
