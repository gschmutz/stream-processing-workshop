# Moving Data from Kafka to Object Storage

In this workshop we will see how we can use Kafka Connect to move data from a Kafka topic to Object Storage. A similar approach would also work for moving data to HDFS. 

We will work with [MinIO](https://min.io/) as the Object Storage solution, but [Amazon S3](https://aws.amazon.com/s3/) or any other cloud Object Storage solution would work as well.

MinIO is available as part of the streaming platform. 

## Configure a Kafka Connector

The connector in Kafka Connect to work with S3 compliant object storage is the [Confluent Kafka Connect S3](https://docs.confluent.io/current/connect/kafka-connect-s3/index.html). 

It is part of the Confluent Platform and pre-loaded with the Kafka cluster. We can easily test that using the REST API 

```
curl -X "GET" "$DOCKER_HOST_IP:8083/connectors" -H "Content-Type: application/json" -H "Accept: application/json"
```

or use the [Kafka Connect UI](http://streamingplatform:28001/#/cluster/kafka-connect-1). If you click on **New** then on the page you should see the 

![Alt Image Text](./images/kafka-connect-ui-new-connector.png "Minio list objects") 

You can see the **Amazon S3 connector** ready to be used. 

So all we have to do is create a script with the REST call to setup the connector. 

In the `scripts` folder, create a file `start-s3.sh` and add the code below.  

```
#!/bin/bash

echo "removing MQTT Source Connector"

curl -X "DELETE" "$DOCKER_HOST_IP:8083/connectors/s3-confluent-sink"

echo "creating Confluent S3 Sink Connector"

curl -X "POST" "$DOCKER_HOST_IP:8083/connectors" \
     -H "Content-Type: application/json" \
     --data '{
  "name": "s3-confluent-sink",
  "config": {
      "connector.class": "io.confluent.connect.s3.S3SinkConnector",
      "partition.duration.ms": "3600000",
      "flush.size": "100",
      "topics": "truck_position",
      "tasks.max": "1",
      "timezone": "UTC",
      "locale": "en",
      "partitioner.class": "io.confluent.connect.storage.partitioner.DefaultPartitioner",
      "schema.generator.class": "io.confluent.connect.storage.hive.schema.DefaultSchemaGenerator",
      "storage.class": "io.confluent.connect.s3.storage.S3Storage",
      "format.class": "io.confluent.connect.s3.format.json.JsonFormat",
      "s3.region": "us-east-1",
      "s3.bucket.name": "kafka-logistics",
      "s3.part.size": "5242880",
      "store.url": "http://minio:9000",
      "key.converter": "org.apache.kafka.connect.storage.StringConverter",
      "value.converter": "org.apache.kafka.connect.storage.StringConverter"
  }
}'
```

We configure the connector to read the topic `truck_position` and write messages to the bucket named `kafka-logistics `. 

Also create a separate script `stop-s3.sh` for just stopping the connector and add the following code:

```
#!/bin/bash

echo "removing MQTT Source Connector"

curl -X "DELETE" "$DOCKER_HOST_IP:8083/connectors/s3-confluent-sink"
```

Make sure that the both scripts are executable

```
sudo chmod +x start-s3.sh
sudo chmod +x stop-s3.sh
```

## Create the Bucket in Object Storage

Before we can start the script, we have to make sure that the bucket `kafka-logistics` exists in Object Storage. 

In a browser window, navigate to <http://streamingplatform:9000> and you should see login screen. Enter `V42FCGRVMK24JJ8DHUYG` into the **Access Key** and  `bKhWxVF3kQoLY9kFmt91l+tDrEoZjqnWXzY9Eza ` into the **Secret Key** field and click on the connect button.  

The MinIO homepage should now appear. Click on the **+** button on the lower right corner and create the bucket.

![Alt Image Text](./images/minio-create-bucket.png "Minio create bucket") 

## Start the S3 connector

Finally let's start the connector by running the `start-s3` script.

```
./scripts/start-mqtt.sh
```

You have to make sure that either the ingestion into `truck_position` over MQTT is still working or that you have existing messages in the topic `truck_position`. You can also run the simulator to by-track the MQTT ingestion pipeline and produce directly to the Kafka topic instead:

```
docker run trivadis/iot-truck-simulator '-s' 'KAFKA' '-h' $PUBLIC_IP '-p' '9092' '-f' 'CSV' "-t" "sec"
```

As soon as the connector picks up messages, they should start to appear in the `kafka-logistics` bucket in MiniIO. 

You should see a new folder `topics` with a sub-folder `truck_position` representing the topic and inside this folder there is another folder per partition. 

![Alt Image Text](./images/minio-folders.png "Minio create bucket")

In each folder you will find multiple files, all with some messages from Kafka. 

![Alt Image Text](./images/minio-objects.png "Minio create bucket")

Download one of the files and check the messages it contains.
