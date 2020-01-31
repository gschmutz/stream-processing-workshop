# Streaming Data Platform in Docker

The environment for this course is completely based on docker containers. 

In order to simplify the provisioning, a single docker-compose configuration is used. All the necessary software will be provisioned using Docker.  

For Kafka we will be using the Docker images provided by Confluent and available under the following GitHub project: <https://github.com/confluentinc/cp-docker-images>. In this project, there is an example folder with a few different docker compose configuration for various Confluent Platform configurations.

You have the following options to start the environment:

 * [**Local Virtual Machine Environment**](./LocalVirtualMachine.md) - a Virtual Machine with Docker and Docker Compose pre-installed will be distributed at by the course infrastructure. You will need 50 GB free disk space.
 * [**Local Docker Environment**](./LocalDocker.md) - you have a local Docker and Docker Compose setup in place which you want to use
 * [**AWS Lightsail Environment**](./Lightsail.md) - AWS Lightsail is a service in Amazon Web Services (AWS) with which we can easily startup an environment and provide all the necessary bootstrapping as a script.

## Post Provisioning

These steps are necessary after the starting the docker environment. 

### Add entry to local `/etc/hosts` File

To simplify working with the Data Platform and for the links below to work, add the following entry to your local `/etc/hosts` file. 

```
40.91.195.92		dataplaform	streamingplatform
```

Replace the IP address by the public IP address of the docker host. 

## Services accessible on Data Platform

The following service are available as part of the platform:

Type | Service | Url
------|------- | -------------
Development | StreamSets Data Collector | <http://dataplatform:28029>
Development | Apache NiFi | <http://dataplatform:28054/nifi>
Development | Apache Zeppelin | <http://dataplatform:28055>
Development | Jupyter | <http://dataplatform:38888>
Development | Kibana | <http://dataplatform:28006>
Development | InfluxDB UI | <http://dataplatform:28151>
Development | InfluxDB Chronograf UI | <http://dataplatform:28152>
Datastore | Neo4J | <http://dataplatform:28080>
Datastore | InfluxDB REST API | <http://dataplatform:28083>
Datastore | Minio | <http://dataplatform:28150>
Governance | Schema Registry UI  | <http://dataplatform:28039>
Governance | Schema Registry Rest API  | <http://dataplatform:18081>
Management | Kafka Connect UI | <http://dataplatform:28038>
Management | Kafka Manager  | <http://dataplatform:28044>
Management | Kafkahq  | <http://dataplatform:28042>
Management | Mino | <http://dataplatform:9000>
Management | Kafka Rest Service | <http://dataplatform:8086>
Management | Kafka Connect Rest Service | <http://dataplatform:8083>
Management | ksqlDB Rest Service | <http://dataplatform:28034>
Management | Elasticsearch Rest Service | <http://dataplatform:9200>
Management | Elasticsearch Dejavu UI | <http://dataplatform:28000>
Management | Elasticsearch Cerebro UI | <http://dataplatform:28061>
Management | Elasticsearch HQ | <http://dataplatform:28052>
Management | Adminer RDBMS UI | <http://dataplatform:28041>
Management | MQTT UI | <http://dataplatform:28082>
Monitoring | Grafana | <http://dataplatform:28099>
Monitoring | CAdvisor	 | <http://dataplatform:28160>

