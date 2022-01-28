# IoT Data Ingestion - Moving Data from Kafka to Hadoop HDFS

In this workshop we will see how we can use Kafka Connect to move data from the Kafka topic with the driver data (`truck_driver`) to HDFS.  

![Alt Image Text](./images/kafka-connect-s3-overview.png "Minio list objects")

A similar approach would also work for moving data to HDFS.

## Configure a Kafka Connector

The connector in Kafka Connect to work with Hadoop HDFS is the [Confluent HDFS 3 Sink Connector](https://docs.confluent.io/kafka-connect-hdfs3-sink/current/index.html). 

It is part of the Confluent Platform and pre-loaded with the Kafka cluster. We can easily test that using the REST API 

```
curl -X "GET" "$DOCKER_HOST_IP:8083/connectors" -H "Content-Type: application/json" -H "Accept: application/json"
```

or use the [Kafka Connect UI](http://dataplatform:28103/#/cluster/kafka-connect-1). If you click on **New** then on the page you should see the 

![Alt Image Text](./images/kafka-connect-ui-new-connector.png "Minio list objects") 

You can see the **Hdfs3SinkConnector** ready to be used. 

So all we have to do is create a script with the REST call to setup the connector. 

In the `scripts` folder, create a file `start-hdfs.sh` and add the code below.  

```
#!/bin/bash

echo "removing MQTT Source Connector"

curl -X "DELETE" "$DOCKER_HOST_IP:8083/connectors/hdfs3-parquet-sink"

echo "creating Confluent S3 Sink Connector"

curl -X "POST" http://dataplatform:8083/connectors \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "hdfs3-parquet-sink",
    "config": {
        "connector.class": "io.confluent.connect.hdfs3.Hdfs3SinkConnector",
        "tasks.max": "1",
        "topics": "truck_driver",
        "hdfs.url": "hdfs://namenode:9000",
        "flush.size": "3",
        "key.converter": "org.apache.kafka.connect.converters.LongConverter",
        "value.converter": "io.confluent.connect.avro.AvroConverter",
        "value.converter.schema.registry.url":"http://schema-registry-1:8081",
        "confluent.topic.bootstrap.servers": "kafka-1:19092",
        "confluent.topic.replication.factor": "1",
        "format.class":"io.confluent.connect.hdfs3.parquet.ParquetFormat",
        "partitioner.class":"io.confluent.connect.storage.partitioner.FieldPartitioner"
    }
}'
```

We configure the connector to read the topic `truck_driver` and write messages to the namenode on `hdfs://namenode:9000`. 

Also create a separate script `stop-s3.sh` for just stopping the connector and add the following code:

```
#!/bin/bash

echo "removing MQTT Source Connector"

curl -X "DELETE" "$DOCKER_HOST_IP:8083/connectors/hdfs3-parquet-sink"
```

Make sure that the both scripts are executable

```
sudo chmod +x start-hdfs.sh
sudo chmod +x stop-hdfs.sh
```

## Start the HDFS connector

Finally let's start the connector by running the `start-hdfs` script.

```
./scripts/start-hdfs.sh
```

You have to make sure that either the ingestion into `truck_position` over MQTT is still working or that you have existing messages in the topic `truck_position`. 

You can also run the simulator to sidetrack the MQTT ingestion pipeline and produce directly to the Kafka topic instead:

```
docker run trivadis/iot-truck-simulator '-s' 'KAFKA' '-h' $PUBLIC_IP '-p' '9092' '-f' 'CSV' "-t" "sec"
```

As soon as the connector picks up messages, they should start to appear in the `topics` folder in HDFS. Within that folder you should see a sub-folder `truck_driver` holding the files.

```
docker exec -ti namenode bash

hadoop fs -ls /topics/truck_driver
```

```
root@namenode:/# hadoop fs -ls /topics/truck_driver
Found 6 items
-rw-r--r--   3 appuser supergroup       2009 2021-07-05 10:03 /topics/truck_driver/truck_driver+0+0000000000+0000000002.parquet
-rw-r--r--   3 appuser supergroup       2005 2021-07-05 10:03 /topics/truck_driver/truck_driver+2+0000000000+0000000002.parquet
-rw-r--r--   3 appuser supergroup       1996 2021-07-05 10:03 /topics/truck_driver/truck_driver+3+0000000000+0000000002.parquet
-rw-r--r--   3 appuser supergroup       2011 2021-07-05 10:03 /topics/truck_driver/truck_driver+3+0000000003+0000000005.parquet
-rw-r--r--   3 appuser supergroup       1996 2021-07-05 10:03 /topics/truck_driver/truck_driver+5+0000000000+0000000002.parquet
-rw-r--r--   3 appuser supergroup       2001 2021-07-05 10:03 /topics/truck_driver/truck_driver+7+0000000000+0000000002.parquet
...
```

```
curl -X "POST" http://dataplatform:8083/connectors \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "hdfs3-parquet-sink",
    "config": {
        "connector.class": "io.confluent.connect.hdfs3.Hdfs3SinkConnector",
        "tasks.max": "1",
        "topics": "truck_driver",
        "hdfs.url": "hdfs://namenode:9000",
        "flush.size": "3",
        "key.converter": "org.apache.kafka.connect.converters.LongConverter",
        "value.converter": "io.confluent.connect.avro.AvroConverter",
        "value.converter.schema.registry.url":"http://schema-registry-1:8081",
        "confluent.topic.bootstrap.servers": "kafka-1:19092",
        "confluent.topic.replication.factor": "1",
        "format.class":"io.confluent.connect.hdfs3.parquet.ParquetFormat",
        "hive.integration":"true",
        "hive.metastore.uris":"thrift://hive-metastore:9083",
        "schema.compatibility":"BACKWARD"
    }
}'
```

----

[previous part](../05d-static-data-ingestion/README.md)	| 	[top](../05-iot-data-ingestion-and-analytics/README.md) 	