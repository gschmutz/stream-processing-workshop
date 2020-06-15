# IoT Data Ingestion - Ingesting and Joining Static Data to Stream

So far we have ingested the truck data from MQTT to Kafka and detected dangerous driving behaviour. But the information only holds the `driverId` but no other information about the driver. 

In this workshop we will ingest information about the drivers into another Kafka topic and then use that information and join it with the `dangerous_driving_s` stream using ksqlDB. 

![Alt Image Text](./images/joining-static-data-with-ksql-overview.png "Schema Registry UI")

## Create the `driver` table and load some data

The Data Platform contains PostgreSQL database service called `postgresql`, which we will use as the data store for the driver information.

Let's run a bash shell inside this docker container

```
docker exec -ti postgresql bash
```

and run the `psql` command line utility to connect to the Postgresql database as user `sample`.

```
psql -d sample -U sample
```

Now let's first create the table `driver`

```
DROP TABLE driver;

CREATE TABLE driver (id BIGINT, first_name CHARACTER VARYING(45), last_name CHARACTER VARYING(45), available CHARACTER VARYING(1), birthdate DATE, last_update TIMESTAMP);

ALTER TABLE driver ADD CONSTRAINT driver_pk PRIMARY KEY (id);
```

and then add some driver data to the newly created table. 

```
INSERT INTO "driver" ("id", "first_name", "last_name", "available", "birthdate", "last_update") VALUES (10,'Diann', 'Butler', 'Y', '10-JUN-68', CURRENT_TIMESTAMP);
INSERT INTO "driver" ("id", "first_name", "last_name", "available", "birthdate", "last_update") VALUES (11,'Micky', 'Isaacson', 'Y', '31-AUG-72' ,CURRENT_TIMESTAMP);
INSERT INTO "driver" ("id", "first_name", "last_name", "available", "birthdate", "last_update") VALUES (12,'Laurence', 'Lindsey', 'Y', '19-MAY-78' ,CURRENT_TIMESTAMP);
INSERT INTO "driver" ("id", "first_name", "last_name", "available", "birthdate", "last_update") VALUES (13,'Pam', 'Harrington', 'Y','10-JUN-68' ,CURRENT_TIMESTAMP);
INSERT INTO "driver" ("id", "first_name", "last_name", "available", "birthdate", "last_update") VALUES (14,'Brooke', 'Ferguson', 'Y','10-DEC-66' ,CURRENT_TIMESTAMP);
INSERT INTO "driver" ("id", "first_name", "last_name", "available", "birthdate", "last_update") VALUES (15,'Clint','Hudson', 'Y','5-JUN-75' ,CURRENT_TIMESTAMP);
INSERT INTO "driver" ("id", "first_name", "last_name", "available", "birthdate", "last_update") VALUES (16,'Ben','Simpson', 'Y','11-SEP-74' ,CURRENT_TIMESTAMP);
INSERT INTO "driver" ("id", "first_name", "last_name", "available", "birthdate", "last_update") VALUES (17,'Frank','Bishop', 'Y','3-OCT-60' ,CURRENT_TIMESTAMP);
INSERT INTO "driver" ("id", "first_name", "last_name", "available", "birthdate", "last_update") VALUES (18,'Trevor','Hines', 'Y','23-FEB-78' ,CURRENT_TIMESTAMP);
INSERT INTO "driver" ("id", "first_name", "last_name", "available", "birthdate", "last_update") VALUES (19,'Christy','Stephens', 'Y','11-JAN-73' ,CURRENT_TIMESTAMP);
INSERT INTO "driver" ("id", "first_name", "last_name", "available", "birthdate", "last_update") VALUES (20,'Clarence','Lamb', 'Y','15-NOV-77' ,CURRENT_TIMESTAMP);
```

Keep this window open and connected to the datase, we will need it again later.
 
## Create a new Kafka topic truck_driver

Let's create a new topic `truck_driver`, which will hold the latest information for all the drivers. It's a compacted topic, so that only one version (the latest) per key will be kept. 

Start a bash shell in one of the running Kafka broker docker containers

```
docker exec -ti kafka-1 bash
```

and then perform the `kafka-topics --create` command to create the topic `truck_driver` and configure it to be a **log compacted** topic:

```
kafka-topics --zookeeper zookeeper-1:2181 --create --topic truck_driver --partitions 8 --replication-factor 2 --config cleanup.policy=compact --config segment.ms=100 --config delete.retention.ms=100 --config min.cleanable.dirty.ratio=0.001
```

Still in the bash on the kafka borkerNow let's create a consumer wich reads the new topic from the beginning. There is nothing shown so far, as we don't yet have any data available. 

```
kafka-console-consumer --bootstrap-server kafka-1:9092 --topic truck_driver --from-beginning
```

Keep it running, we will come back to it in a minute!

## Create a Kafka JDBC Connector to pull the driver data from PostgreSQL

To populate the `truck_driver` Kafka topic with the driver data, we use a Kafka Connect JDBC connector with Kafka Connect. 

It can be configured to gets all the data from the `driver` table and to publish it to the `truck_driver` topic. It not only gets the complete driver data once, it also gets updates to the driver data, while the connnector is constantly running.

Unlike the MQTT Connector we have used in [IoT Data Ingestion through MQTT into Kafka](../08-iot-data-ingestion-over-mqtt/README.md), the [Kafka Connect JDBC Connector](https://docs.confluent.io/current/connect/kafka-connect-jdbc/index.html) is already part of the Confuent Community Platform and by that part of the Data Platform, so we don't have to provision additional software in order to use it. 

Similar to the way we have configured and created the MQTT or Twitter connector, create a new file `start-jdbc.sh` in the `scripts` folder.
 
```
cd scripts
nano start-jdbc.sh
```

Add the following script logic to the file. 

```
#!/bin/bash

echo "removing JDBC Source Connector"

curl -X "DELETE" "http://dataplatform:28013/connectors/jdbc-source"

echo "creating JDBC Source Connector"

curl -X PUT \
  http://dataplatform:28013/connectors/jdbc-source/config \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json' \
  -d '{
    "connector.class": "JdbcSourceConnector",
    "tasks.max": "1",
    "connection.url":"jdbc:postgresql://postgresql/sample?user=sample&password=sample",
    "mode": "timestamp",
    "timestamp.column.name":"last_update",
    "table.whitelist":"driver",
    "validate.non.null":"false",
    "topic.prefix":"truck_",
    "key.converter":"org.apache.kafka.connect.storage.StringConverter",
    "key.converter.schemas.enable": "false",
    "value.converter":"org.apache.kafka.connect.json.JsonConverter",
    "value.converter.schemas.enable": "false",
    "transforms":"createKey,extractInt",
    "transforms.createKey.type":"org.apache.kafka.connect.transforms.ValueToKey",
    "transforms.createKey.fields":"id",
    "transforms.extractInt.type":"org.apache.kafka.connect.transforms.ExtractField$Key",
    "transforms.extractInt.field":"id"
  }
}'
```

First make sure that the script is executable and then run it. 

```
sudo chmod +x configure-connect-jdbc.sh
./configure-connect-jdbc.sh
```

After a while you should see each record from the `driver` table appearing as a message on the `kafka-console-consumer` listening on the `truck_driver` topic. 

Go back to the PostgreSQL shell and some additional driver data:

```
INSERT INTO "driver" ("id", "first_name", "last_name", "available", "birthdate", "last_update") VALUES (21,'Lila', 'Page', 'Y', '5-APR-77', CURRENT_TIMESTAMP);
INSERT INTO "driver" ("id", "first_name", "last_name", "available", "birthdate", "last_update") VALUES (22,'Patricia', 'Coleman', 'Y', '11-AUG-80' ,CURRENT_TIMESTAMP);
INSERT INTO "driver" ("id", "first_name", "last_name", "available", "birthdate", "last_update") VALUES (23,'Jeremy', 'Olson', 'Y', '13-JUN-82', CURRENT_TIMESTAMP);
INSERT INTO "driver" ("id", "first_name", "last_name", "available", "birthdate", "last_update") VALUES (24,'Walter', 'Ward', 'Y', '24-JUL-85', CURRENT_TIMESTAMP);
INSERT INTO "driver" ("id", "first_name", "last_name", "available", "birthdate", "last_update") VALUES (25,'Kristen', ' Patterson', 'Y', '14-JUN-73', CURRENT_TIMESTAMP);
INSERT INTO "driver" ("id", "first_name", "last_name", "available", "birthdate", "last_update") VALUES (26,'Jacquelyn', 'Fletcher', 'Y', '24-AUG-85', CURRENT_TIMESTAMP);
INSERT INTO "driver" ("id", "first_name", "last_name", "available", "birthdate", "last_update") VALUES (27,'Walter', '  Leonard', 'Y', '12-SEP-88', CURRENT_TIMESTAMP);
INSERT INTO "driver" ("id", "first_name", "last_name", "available", "birthdate", "last_update") VALUES (28,'Della', ' Mcdonald', 'Y', '24-JUL-79', CURRENT_TIMESTAMP);
INSERT INTO "driver" ("id", "first_name", "last_name", "available", "birthdate", "last_update") VALUES (29,'Leah', 'Sutton', 'Y', '12-JUL-75', CURRENT_TIMESTAMP);
INSERT INTO "driver" ("id", "first_name", "last_name", "available", "birthdate", "last_update") VALUES (30,'Larry', 'Jensen', 'Y', '14-AUG-83', CURRENT_TIMESTAMP);
INSERT INTO "driver" ("id", "first_name", "last_name", "available", "birthdate", "last_update") VALUES (31,'Rosemarie', 'Ruiz', 'Y', '22-SEP-80', CURRENT_TIMESTAMP);
INSERT INTO "driver" ("id", "first_name", "last_name", "available", "birthdate", "last_update") VALUES (32,'Shaun', ' Marshall', 'Y', '22-JAN-85', CURRENT_TIMESTAMP);
```

The new records will also appear with almost no latency as messages in the `truck_driver` topic. 

Now let's see an update on some existing records: 

```
UPDATE "driver" SET "available" = 'N', "last_update" = CURRENT_TIMESTAMP  WHERE "id" = 21;
UPDATE "driver" SET "available" = 'N', "last_update" = CURRENT_TIMESTAMP  WHERE "id" = 14;
```

Again you should see the updates as new messages in the `truck_driver` topic. 

Now let's use the driver data to enrich the `dangerous_driving_s` stream from workshop [Stream Processing using KSQL](../09-stream-processing-using-ksql/README.md). For that we again have to provide some structure to the `truck_driver` topic, so that we can use it in a ksqlDB `SELECT ... JOIN ...` query.

## Create a ksqlDB table

Connect again to the ksqlDB CLI 

```
docker exec -it ksqldb-cli ksql http://ksqldb-server-1:8088
```

and create the table over the `truck_driver` topic. It will hold the latest state of all the drivers:

```
DROP TABLE driver_t;

CREATE TABLE driver_t  \
   (id BIGINT,  \
   first_name VARCHAR, \
   last_name VARCHAR, \
   available VARCHAR, \
   birthdate VARCHAR) \
  WITH (kafka_topic='truck_driver', \
        value_format='JSON', \
        KEY = 'id');
```

Let's see the data the table contains by using a SELECT on the table created above:

```
SELECT * FROM driver_t
EMIT CHANGES; 
```

This is also a continous query statement, but there is no data being shown. Why is that, shouldn't there be data in the `truck_topic`, as we have seen in the console consumer. The reason why we don't see any data is because the query starts at th end of the topic, waiting for new data to arrive. If we perform another update on the source (the PostgreSQL table), keeping the ksql select running

```
UPDATE "driver" SET "available" = 'N', "last_update" = CURRENT_TIMESTAMP  WHERE "id" = 27;
```

then after a short while we should see the change appear as a result of the SELECT on the table. The reason why there is some latency is the polling interval on the JDBC connector. 

There is also way to force reading from the beginning, by setting the following values before the SELECT itself. 

```
set 'commit.interval.ms'='5000';
set 'cache.max.bytes.buffering'='10000000';
set 'auto.offset.reset'='earliest';

SELECT * FROM driver_t
EMIT CHANGES;
```

The result of that table will only show each driver once, always with the latest information. Cross-check that the available flag is set to "N" for the driver with id 21 (because of the update we did above). 

if you perform another `UPDATE` on the table, setting the `available` flag back to `Y`

```
UPDATE "driver" SET "available" = 'Y', "last_update" = CURRENT_TIMESTAMP  WHERE "id" = 21;
```

then you will see a new message appearing in the result of the KSQL SELECT. This shows that a table contains the currrent view of information for all the drivers as well as it informs about changes on the driver while the statement is running. 

With that table at hand, let's join it to the data stream we get from the vehicles. 

## Join Stream with Table

Let's execute the `SELECT .. JOIN ...` statement in an ad-hoc manner, as we have seen in the previous workshop. That helps us developing the statment and we can easily see if the resulting data is correct. 

```
SELECT driverid, first_name, last_name, truckId, routeId, eventType, latitude, longitude
FROM dangerous_driving_s
LEFT JOIN driver_t
ON dangerous_driving_s.driverId = driver_t.id
EMIT CHANGES;
```

Make sure that the vehicle simulator is still running, otherwise you won't see any new results appearing. Because we join the table to the `dangerous_driving_s` stream, a new row is only shown when there is an abnormal driving beaviour.

We could also perform an outer-join, if we would like to see vehicles with a driver-id, where the driver is not really known or at least not stored in the `driver` database.

```
SELECT driverid, first_name, last_name, truckId, routeId, eventType, latitude, longitude 
FROM dangerous_driving_s 
LEFT OUTER JOIN driver_t 
ON dangerous_driving_s.driverId = driver_t.id
EMIT CHANGES;
```

Again, selecting and viewing the data in the ksqlDB CLI is very helpful while devloping and debugging a statement. Once you are happy with the result, you want to provide it to other potential subscribers, by creating a new stream.

Let's create the stream `dangerous_driving_and_driver` using the following KSQL statement. 

```
DROP STREAM dangerous_driving_and_driver_s;

CREATE STREAM dangerous_driving_and_driver_s 
  WITH (kafka_topic='dangerous_driving_and_driver', 
        value_format='JSON', partitions=8) 
AS SELECT driverid, first_name, last_name, truckId, routeId, eventType, latitude, longitude 
FROM dangerous_driving_s 
LEFT JOIN driver_t 
ON dangerous_driving_s.driverId = driver_t.id
EMIT CHANGES;
```

Now we can get the same data by just selecting from the new stream just created:

```
SELECT * FROM dangerous_driving_and_driver_s
EMIT CHANGES;
```

Of course we can also conditionally retrieve only the messages for driver 11:

```
SELECT * FROM dangerous_driving_and_driver_s 
WHERE driverid = 11
EMIT CHANGES;
```

While the KSQL statement is running, perform another update on the `first_name` of the `driver` table in PostgreSQL. Connecto to the PostgreSQL shell

```
docker exec -ti postgresql psql -d sample -U sample
```

perform the SQL UPDATE on the table

```
UPDATE "driver" SET "first_name" = 'Slow Down Mickey', "last_update" = CURRENT_TIMESTAMP  WHERE "id" = 11;
```

and check the live stream to see the change.

```
...
|1580431526616       |11                  |11                  |Micky               |Isaacson            |78                  |1325712174          |Unsafe tail distance|37.02               |-94.54              |
|1580431560114       |11                  |11                  |Micky               |Isaacson            |78                  |1325712174          |Lane Departure      |37.8                |-92.48              |
|1580431595643       |11                  |11                  |Micky               |Isaacson            |78                  |1325712174          |Overspeed           |38.46               |-90.86              |
|1580431630484       |11                  |11                  |Micky               |Isaacson            |78                  |1325712174          |Unsafe following dis|38.31               |-91.07              |
|1580431664922       |11                  |11                  |Micky               |Isaacson            |78                  |1325712174          |Overspeed           |37.7                |-92.61              |
|1580450850718       |11                  |11                  |Slow Down Mickey    |Isaacson            |101                 |1962261785          |Unsafe tail distance|41.48               |-88.07              |
|1580450886238       |11                  |11                  |Slow Down Mickey    |Isaacson            |101                 |1962261785          |Overspeed           |40.38               |-89.17              |
...
```
