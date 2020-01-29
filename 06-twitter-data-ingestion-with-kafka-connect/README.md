# Data Ingestion with Kafka Connect

In this workshop we will be using Kafka Connect to get the messages from Twitter into Kafka. 

Luckily, there is a [Kafka Connector](https://github.com/jcustenborder/kafka-connect-twitter) available for retrieving live Tweets. So all we have to do here is configure it and bring it to action!

## Adding the Kafka Connect service 

There are two instances of the Kafka Connect service instance running as part of the Modern Data Platform, `kafka-connect-1` and `kafka-connect-2`. 

To add the connector implementations, without having to copy them into the docker container (or even create a dedicated docker image holding the jar), both connect services are configured to use additional implementations from the local folder `/etc/kafka-connect/custom-plugins` inside the docker container. This folder is mapped as a volume to the `plugins/kafka-connect` folder outside of the container on the docker host. 

Into this folder we have to copy the artefacts of the Kafka connectors we want to use. 

### Download and deploy the kafka-connect-mqtt artefact

Navigate into the `plugins/kafka-connect` folder 

```
cd plugins/kafka-connect
```

and download the `kafka-connect-twitter-0.2.26.tar.gz` file from the [kafka-connect-twitter](https://github.com/jcustenborder/kafka-connect-twitter) Github project.

```
wget https://github.com/jcustenborder/kafka-connect-twitter/releases/download/0.2.26/kafka-connect-twitter-0.2.26.tar.gz
```

Once it is successfully downloaded, uncompress it using this `tar` command and remove the file. 

```
mkdir kafka-connect-twitter-0.2.26 && tar -xvzf kafka-connect-twitter-0.2.26.tar.gz -C kafka-connect-twitter-0.2.26 
rm kafka-connect-twitter-0.2.26.tar.gz 
```

Now we have to restart both connect service instances in order to pick up the new connector. 

```
docker-compose restart kafka-connect-1 kafka-connect-2
```

The connector should now get registered to the Kafka connect cluster. You can confirm that by checking the log file of the two containers

```
docker-compose logs -f kafka-connect-1 kafka-connect-2
```

After a while you should see an output similar to the one below with a message that the Twitter connector was added and later that the connector finished starting ...

```
kafka-connect-1       | [2020-01-28 21:35:38,777] INFO Added plugin 'io.confluent.connect.security.ConnectSecurityExtension' (org.apache.kafka.connect.runtime.isolation.DelegatingClassLoader)
kafka-connect-1       | [2020-01-28 21:35:38,777] INFO Loading plugin from: /usr/share/java/acl (org.apache.kafka.connect.runtime.isolation.DelegatingClassLoader)
kafka-connect-1       | [2020-01-28 21:35:42,923] INFO Registered loader: PluginClassLoader{pluginLocation=file:/usr/share/java/acl/} (org.apache.kafka.connect.runtime.isolation.DelegatingClassLoader)
kafka-connect-1       | [2020-01-28 21:35:42,923] INFO Loading plugin from: /usr/share/java/rest-utils (org.apache.kafka.connect.runtime.isolation.DelegatingClassLoader)
kafka-connect-1       | [2020-01-28 21:35:43,582] INFO Registered loader: PluginClassLoader{pluginLocation=file:/usr/share/java/rest-utils/} (org.apache.kafka.connect.runtime.isolation.DelegatingClassLoader)
kafka-connect-1       | [2020-01-28 21:35:43,583] INFO Loading plugin from: /etc/kafka-connect/custom-plugins/kafka-connect-twitter-0.2.26 (org.apache.kafka.connect.runtime.isolation.DelegatingClassLoader)
kafka-connect-1       | [2020-01-28 21:35:44,028] INFO Registered loader: PluginClassLoader{pluginLocation=file:/etc/kafka-connect/custom-plugins/kafka-connect-twitter-0.2.26/} (org.apache.kafka.connect.runtime.isolation.DelegatingClassLoader)
kafka-connect-1       | [2020-01-28 21:35:44,028] INFO Added plugin 'com.github.jcustenborder.kafka.connect.twitter.TwitterSourceConnector' (org.apache.kafka.connect.runtime.isolation.DelegatingClassLoader)
kafka-connect-1       | [2020-01-28 21:35:49,958] INFO Registered loader: sun.misc.Launcher$AppClassLoader@764c12b6 (org.apache.kafka.connect.runtime.isolation.DelegatingClassLoader)

...
```

## Configure the Twitter Connector

For creating an instance of the Twitter connector you can either use a REST client or the Linux `curl` command line utility, which should be available on the Docker host. Curl is what we are going to use here. 

Create a folder `scripts` if it does not yet exists and navigate into the folder. 

```
mkdir scripts
cd scripts
```

In the `scripts` folder, create a file `start-twitter.sh` and add the code below.  

```
#!/bin/bash

echo "removing Twitter Source Connector"

curl -X "DELETE" http://dataplatform:28013/connectors/tweet-source"

echo "creating Twitter Source Connector"

curl -X "POST" http://dataplatform:28013/connectors \
  -H 'Content-Type: application/json' \
  -d '{
  "name": "tweet-source",
  "config": {
    "connector.class": "com.github.jcustenborder.kafka.connect.twitter.TwitterSourceConnector",
    "process.deletes": "false",
    "filter.keywords": "trump",
    "kafka.status.topic": "tweet-avro-v1",
    "tasks.max": "1",
    "twitter.oauth.consumerKey": "XXXXXX",
    "twitter.oauth.consumerSecret": "XXXXXX",
    "twitter.oauth.accessToken": "XXXXXX",
    "twitter.oauth.accessTokenSecret": "XXXXXXXX"
  }
}' 
```
Make sure that you replace the `oauth.xxxxx` settings with the value of your Twittter application (created [here](https://developer.twitter.com/en/apps)).

Also create a separate script `stop-twitter.sh` for just stopping the connector and add the following code:

```
#!/bin/bash

echo "removing Twitter Source Connector"

curl -X "DELETE" http://dataplatform:28013/connectors/tweet-source"
```

Make sure that the both scripts are executable

```
sudo chmod +x start-mqtt.sh
sudo chmod +x stop-mqtt.sh
```

Before we can run the pipeline, we have to create the Kafka topic.

## Create the topic in Kafka

Create the topic in Kafka, if it does not yet exist, using the `kafka-topics` command. 
```
kafka-topics --create \
			--if-not-exists \
			--zookeeper zookeeper:2181 \
			--topic tweet-avro-v1 \
			--partitions 8 \
			--replication-factor 3
```

Alternatively you can also use KafkaHQ or Conduktor to create a topic. 

Now we are ready to run the Twitter Connector. 


## Start the Twitter connector

Finally let's start the connector by running the `start-twitter` script.

```
./scripts/start-twitter.sh
```

You can use [Kafka Connect UI](http://dataplatform:28038/) to check if the connector runs sucessfully.

![Alt Image Text](./images/kafka-connect-ui.png "Kafka Connect UI") 

The connector uses Avro for the serialization of the messages. The necessary Avro schemas (for key and for the value) are registered in the Schema Registry When starting the connector for the first time. Navigte to the [Schema Registry UI](http://dataplatform:28039/) to see these Avro schemas. 

![Alt Image Text](./images/schema-registry-ui.png "Schema Registry UI") 

## Use kafkacat to see the mssage on the console

Now let's start a `kafkacat` consumer on the new topic:

```
kafkacat -b dataplatform:9092 -t tweet-avro-v1
```

This is not very readable, as the Twitter Connector is using Avro for the serializer. But we can tell `kafkacat` to do the same for serialization, using the `-s` together with the `-r` option:

```
kafkacat -b dataplatform:9092 -t tweet-avro-v1 -s avro -r http://dataplatform:28030
```

