# IoT Data Ingestion through MQTT into Kafka
In this workshop we will be ingesting data not directly into Kafka but rather through MQTT first. We will be using a fictious Trucking company with a fleet of trucks constantly providing some data about the moving vehicles. 

The following diagram shows the setup of the data flow we will be implementing. Of course we will not be using any real-life data, but have a program simulating some drivers and their trucks.

![Alt Image Text](./images/iot-ingestion-overview.png "Schema Registry UI")

### Adding a MQTT broker
Our streaming platform does not yet contain an MQTT broker. 

So let's add a new serice to the docker-compose.yml file we have created in [Setup of the Streaming Platform](../01-environment/README.md).

[Mosquitto](https://mosquitto.org/) is an easy to use MQTT broker, belonging to the Eclipse project. The is a docker images available for us on Docker Hub. Just add the following section at the end of the `docker-compose.yml`, right below the zeppelin service. 

```
  mosquitto-1:
    image: eclipse-mosquitto:latest
    hostname: mosquitto-1
    ports: 
      - "1883:1883"
      - "9001:9001"
    volumes:
      - ./mosquitto/mosquitto-1.conf:/mosquitto/config/mosquitto.conf
```

Mosquitto needs some configurations, which we can pass from outside in a file. First create a folder `mosquitto` and inside this folder create the `mosquitto-1.conf` file. Add the following configurations to this file:

```
persistence true
persistence_location /mosquitto/data/
log_dest file /mosquitto/log/mosquitto.log
```

With Docker Compose, you can easily later add some new services, even if the platfrom is currently running. If you redo a `docker-compose up -d`, Docker Compose will check if there is a delta between what is currently running and what the `docker-compose.yml` file tells. 

If there is a new service added, such as here with Mosquitto, Docker Compose will start the service, leaving the other, already running services untouched. 

If you change configuration on an already running service, then Docker will recreate that service applying the new settings. 

However, removing a service from the `docker-compose.yml` will not cause a running service to be stopped and removed. You have to do that manually. 

### Installing MQTT Client
In order to be able to see what we are producing into MQTT, we need something similar to the `kafkacat` and `kafka-console-consumer` utilities. 

There are multiple tools available, some with a Web-UI and some with Rich-Client UI. 

TODO

### Running the Truck Simulator

Now with the MQTT broker and the MQTT client in place, let's produce some messages to the MQTT topics. 
TODO

```
docker run -E gschmutz/truck-simulator:1.0.0

mvn exec:java -Dexec.args="-s MQTT -f CSV -p 1883"
```

### Adding Kafka Connect to bridge between MQTT and Kafka

In order to get the messages from MQTT into Kafka, we will be using Kafka Connect. Luckily, there are multiple Kafka Connectors available for MQTT. We will be using the one availble from Landoop. (TODO)

Kafka Connect is already started as a service of the Streaming Platform and it exposes a REST API on Port 8083. 

For invoking the API, you can either use a REST client or the Linux `curl` command line utility, which should be available on the Docker host. Curl is what we are going to use here. Create a script `configure-mqtt.sh` and copy/paste the code below.  

```
#!/bin/bash

echo "removing MQTT Source Connector"

curl -X "DELETE" "$DOCKER_HOST_IP:8083/connectors/mqtt-source"

echo "creating MQTT Source Connector"

curl -X "POST" "$DOCKER_HOST_IP:8083/connectors" \
     -H "Content-Type: application/json" \
     -d $'{
  "name": "mqtt-source",
  "config": {
  	"connector.class": "com.datamountaineer.streamreactor.connect.mqtt.source.MqttSourceConnector",
  	"connect.mqtt.connection.timeout": "1000",
  	"tasks.max": "1",
  	"connect.mqtt.kcql": "INSERT INTO truck_position SELECT * FROM truck/+/position",
  	"name": "mqtt-source",
  	"connect.mqtt.connection.clean": "true",
  	"connect.mqtt.service.quality": "0",
  	"connect.mqtt.connection.keep.alive": "1000",
  	"connect.mqtt.client.id": "tm-mqtt-connect-01",
  	"connect.mqtt.converter.throw.on.error": "true",
  	"connect.mqtt.hosts": "tcp://mosquitto:1883"
	}
  }'
```

Make sure it is executable by running `sudo chmod +X configure-mqtt.sh` and then run it. It will first remove the MQTT connector, if it already exists and then create it (again). 

### Create necessary Kafka Topic

```
docker exec -ti streamingplatform_broker-1_1 bash
```

```
kafka-topics --zookeeper zookeeper:2181 --create --topic truck_position --partitions 8 --replication-factor 2
```


```
kafka-console-consumer --bootstrap-server broker-1:9092 --topic truck_position
```




