# Stream Processing using KSQL
With the truck data continously ingested into the truck_movemnt topic, let's perform some stream processing on the information. There are many possible solutions for performing analytics directly on the event stream. In the Kafka project, we can either use Kafka Streams or KSQL, a SQL abstraction on top of Kafka Streams. For this workshop we will be using KSQL. 

### Analyze abnormal driver behaviour

First let's find out abnormal driver behaviour by selecting all the events where the event type is not `Normal`.

In order to use KSQL, we need to connect to the KSQL engine using the KSQL CLI. One instance of a KSQL server has been started with our Streaming Plaform can can be reached on port 8088.

```
docker-compose exec ksql-cli ksql http://ksql-server:8088
```

We can use the show command to show topics as well as streams and tables. We have not yet created streams and tables, therefore we won't see anything. 

```
show topics;
show streams;
show tables;
```

Before we can use a KSQL SELECT statement, we have to describe the structure of our event in the `truck_position` topic. 

```
DROP STREAM truck_position_s;

CREATE STREAM truck_position_s \
  (ts VARCHAR, \
   truckId VARCHAR, \
   driverId BIGINT, \
   routeId BIGINT, \
   eventType VARCHAR, \
   latitude DOUBLE, \
   longitude DOUBLE, \
   correlationId VARCHAR) \
  WITH (kafka_topic='truck_position', \
        value_format='DELIMITED');
```

Now with the `truck_position_s` in place, let's use the SELECT statement to query live messages arriving on the stream. 
        
```
SELECT * FROM truck_position_s;
```

This is not really different to using the `kafka-console-consumer` or `kafkacat`. But of course with KSQL you can do much more. You have the power of SQL-like language at hand. 

So let's use a WHERE clause to only view the events where the event type is not `Normal`. 

```
SELECT * FROM truck_position_s WHERE eventType != 'Normal';
```

```
docker exec -ti docker_broker-1_1 bash
```

```
kafka-topics --zookeeper zookeeper:2181 --create --topic dangerous_driving_ksql --partitions 8 --replication-factor 2
```


```
DROP STREAM dangerous_driving_s;
CREATE STREAM dangerous_driving_s \
  WITH (kafka_topic='dangerous_driving_ksql', \
        value_format='DELIMITED', \
        partitions=8) \
AS SELECT * FROM truck_position_s \
WHERE eventtype != 'Normal';
```

```
DESCRIBE dangerous_driving_s;        
```

```
SELECT * FROM dangerous_driving_s;
```

```
docker exec -ti docker_broker-1_1 bash
```

```
kafka-console-consumer --bootstrap-server broker-1:9092 --topic dangerous_driving_ksql
```
        

### Create the driver table and load some data

```
SELECT eventType, count(*) FROM dangerous_driving_s 
WINDOW TUMBLING (size 20 seconds) 
GROUP BY eventType;
```

```
SELECT first_name, last_name, eventType, count(*) 
FROM dangerous_driving_and_driver_s 
WINDOW TUMBLING (size 20 seconds) 
GROUP BY first_name, last_name, eventType;
```
