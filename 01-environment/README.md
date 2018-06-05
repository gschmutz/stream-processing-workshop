# Setup of the Streaming Platform
The environment for this course is completly based on docker containers. 

Either use the Virtual Machine image made available in the course, containing a docker installation or provisiong your own Docker environemnt including Docker Compose. Find the information for installing [Docker](https://docs.docker.com/install/#supported-platforms) and [Docker Compose](https://docs.docker.com/compose/install/).
 
[Here](../00-setup/README.md) you can find the installation of an Virtual Machine in Azure. 

In order to simplify the provisioning, a single docker-compose configuration is used. All the necessary software will be provisioned using Docker. 

## What is this Streaming Platform?

The following services are provisioned as part of the Streaming Platform: 

 * Apache Zookeeper
 * Kafka Broker 1-3
 * Confluent Schema Registry
 * kafka connect
 * kafka rest proxy
 * ksql server
 * ksql cli
 * Confluent control center
 * schema registry UI
 * kafka manager
 * apache zeppelin
 * Streamets Data Collector
 * Apache NiFi

For Kafka we will be using the Docker images provided by Confluent and available under the following GitHub project: <https://github.com/confluentinc/cp-docker-images>. In this project, there is an example folder with a few different docker compose configuration for various Confluent Platform configurations. 

## Prepare the Docker Compose configuration

On your Docker Machine, create a folder `streamingplatform`. 

```
mkdir streamingplaform
cd streamingplatform
```

Copy the following code fragment into a file named `docker-compose.yml`.

```
#
# Docker Compose with the following services:
#  zookeeper
#  kafka broker 1-3
#  schema registry
#  kafka connect
#  kafka rest proxy
#  ksql server
#  ksql cli
#  confluent control center
#  schema registry UI
#  kafka manager
#  apache zeppelin
#  streamsets
#  apache nifi
#

version: '2'
services:
  zookeeper:
    image: confluentinc/cp-zookeeper:5.0.0-beta1-1
    hostname: zookeeper
    ports:
      - "2181:2181"
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
      ZOOKEEPER_TICK_TIME: 2000

  broker-1:
    image: confluentinc/cp-enterprise-kafka:5.0.0-beta1-1
    hostname: broker-1
    depends_on:
      - zookeeper
    ports:
      - "9092:9092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_BROKER_RACK: 'r1'
      KAFKA_ZOOKEEPER_CONNECT: 'zookeeper:2181'
      KAFKA_ADVERTISED_LISTENERS: 'PLAINTEXT://${DOCKER_HOST_IP}:9092'
      KAFKA_METRIC_REPORTERS: io.confluent.metrics.reporter.ConfluentMetricsReporter
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS: 0
      KAFKA_DELETE_TOPIC_ENABLE: 'true'
      KAFKA_AUTO_CREATE_TOPICS_ENABLE: 'false'
      KAFKA_JMX_PORT: 9994
      CONFLUENT_METRICS_REPORTER_BOOTSTRAP_SERVERS: broker-1:9092
      CONFLUENT_METRICS_REPORTER_ZOOKEEPER_CONNECT: zookeeper:2181
      CONFLUENT_METRICS_REPORTER_TOPIC_REPLICAS: 1
      CONFLUENT_METRICS_ENABLE: 'true'
      CONFLUENT_SUPPORT_CUSTOMER_ID: 'anonymous'

  broker-2:
    image: confluentinc/cp-enterprise-kafka:5.0.0-beta1-1
    hostname: broker-2
    depends_on:
      - zookeeper
    ports:
      - "9093:9093"
    environment:
      KAFKA_BROKER_ID: 2
      KAFKA_BROKER_RACK: 'r1'
      KAFKA_ZOOKEEPER_CONNECT: 'zookeeper:2181'
      KAFKA_ADVERTISED_LISTENERS: 'PLAINTEXT://${DOCKER_HOST_IP}:9093'
      KAFKA_METRIC_REPORTERS: io.confluent.metrics.reporter.ConfluentMetricsReporter
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS: 0
      KAFKA_DELETE_TOPIC_ENABLE: 'true'
      KAFKA_AUTO_CREATE_TOPICS_ENABLE: 'false'
      KAFKA_JMX_PORT: 9993
      CONFLUENT_METRICS_REPORTER_BOOTSTRAP_SERVERS: broker-2:9093
      CONFLUENT_METRICS_REPORTER_ZOOKEEPER_CONNECT: zookeeper:2181
      CONFLUENT_METRICS_REPORTER_TOPIC_REPLICAS: 1
      CONFLUENT_METRICS_ENABLE: 'true'
      CONFLUENT_SUPPORT_CUSTOMER_ID: 'anonymous'

  broker-3:
    image: confluentinc/cp-enterprise-kafka:5.0.0-beta1-1
    hostname: broker-3
    depends_on:
      - zookeeper
    ports:
      - "9094:9094"
    environment:
      KAFKA_BROKER_ID: 3
      KAFKA_BROKER_RACK: 'r1'
      KAFKA_ZOOKEEPER_CONNECT: 'zookeeper:2181'
      KAFKA_ADVERTISED_LISTENERS: 'PLAINTEXT://${DOCKER_HOST_IP}:9094'
      KAFKA_METRIC_REPORTERS: io.confluent.metrics.reporter.ConfluentMetricsReporter
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS: 0
      KAFKA_DELETE_TOPIC_ENABLE: 'true'
      KAFKA_AUTO_CREATE_TOPICS_ENABLE: 'false'
      KAFKA_JMX_PORT: 9994
      CONFLUENT_METRICS_REPORTER_BOOTSTRAP_SERVERS: broker-3:9094
      CONFLUENT_METRICS_REPORTER_ZOOKEEPER_CONNECT: zookeeper:2181
      CONFLUENT_METRICS_REPORTER_TOPIC_REPLICAS: 1
      CONFLUENT_METRICS_ENABLE: 'true'
      CONFLUENT_SUPPORT_CUSTOMER_ID: 'anonymous'
      
  schema_registry:
    image: confluentinc/cp-schema-registry:5.0.0-beta1-1
    hostname: schema_registry
    depends_on:
      - zookeeper
      - broker-1
    ports:
      - "8081:8081"
    environment:
      SCHEMA_REGISTRY_HOST_NAME: schema_registry
      SCHEMA_REGISTRY_KAFKASTORE_CONNECTION_URL: 'zookeeper:2181'
      SCHEMA_REGISTRY_ACCESS_CONTROL_ALLOW_ORIGIN: '*'
      SCHEMA_REGISTRY_ACCESS_CONTROL_ALLOW_METHODS: 'GET,POST,PUT,OPTIONS'
      
  connect:
    image: confluentinc/cp-kafka-connect:5.0.0-beta1-1
    hostname: connect
    depends_on:
      - zookeeper
      - broker-1
      - schema_registry
    ports:
      - "8083:8083"
    environment:
      CONNECT_BOOTSTRAP_SERVERS: 'broker-1:9092'
      CONNECT_REST_ADVERTISED_HOST_NAME: connect
      CONNECT_REST_PORT: 8083
      CONNECT_GROUP_ID: compose-connect-group
      CONNECT_CONFIG_STORAGE_TOPIC: docker-connect-configs
      CONNECT_CONFIG_STORAGE_REPLICATION_FACTOR: 1
      CONNECT_OFFSET_FLUSH_INTERVAL_MS: 10000
      CONNECT_OFFSET_STORAGE_TOPIC: docker-connect-offsets
      CONNECT_OFFSET_STORAGE_REPLICATION_FACTOR: 1
      CONNECT_STATUS_STORAGE_TOPIC: docker-connect-status
      CONNECT_STATUS_STORAGE_REPLICATION_FACTOR: 1
      CONNECT_KEY_CONVERTER: io.confluent.connect.avro.AvroConverter
      CONNECT_KEY_CONVERTER_SCHEMA_REGISTRY_URL: 'http://schema_registry:8081'
      CONNECT_VALUE_CONVERTER: io.confluent.connect.avro.AvroConverter
      CONNECT_VALUE_CONVERTER_SCHEMA_REGISTRY_URL: 'http://schema_registry:8081'
      CONNECT_INTERNAL_KEY_CONVERTER: org.apache.kafka.connect.json.JsonConverter
      CONNECT_INTERNAL_VALUE_CONVERTER: org.apache.kafka.connect.json.JsonConverter
      CONNECT_ZOOKEEPER_CONNECT: 'zookeeper:2181'

  rest-proxy:
    image: confluentinc/cp-kafka-rest:5.0.0-beta1-1
    hostname: rest-proxy
    depends_on:
      - broker-1
      - schema_registry
    ports:
      - "8084:8084"
    environment:
      KAFKA_REST_ZOOKEEPER_CONNECT: '${DOCKER_HOST_IP}:2181'
      KAFKA_REST_LISTENERS: 'http://0.0.0.0:8084'
      KAFKA_REST_SCHEMA_REGISTRY_URL: 'http://schema_registry:8081'
      KAFKA_REST_HOST_NAME: 'rest-proxy'

  ksql-server:
    image: confluentinc/ksql-cli:5.0.0-beta1
    hostname: ksql-server
    ports:
      - '8088:8088'
    depends_on:
      - broker-1
      - schema_registry
    # Note: The container's `run` script will perform the same readiness checks
    # for Kafka and Confluent Schema Registry, but that's ok because they complete fast.
    # The reason we check for readiness here is that we can insert a sleep time
    # for topic creation before we start the application.
    command: "bash -c 'echo Waiting for Kafka to be ready... && \
                       cub kafka-ready -b broker-1:9092 1 20 && \
                       echo Waiting for Confluent Schema Registry to be ready... && \
                       cub sr-ready schema-registry 8081 20 && \
                       echo Waiting a few seconds for topic creation to finish... && \
                       sleep 2 && \
                       /usr/bin/ksql-server-start /etc/ksql/ksql-server.properties'"
    environment:
      KSQL_CONFIG_DIR: "/etc/ksql"
      KSQL_OPTS: "-Dbootstrap.servers=broker-1:9092 -Dksql.schema.registry.url=http://schema_registry:8081 -Dlisteners=http://0.0.0.0:8088"
      KSQL_LOG4J_OPTS: "-Dlog4j.configuration=file:/etc/ksql/log4j-rolling.properties"

  ksql-cli:
    image: confluentinc/ksql-cli:5.0.0-beta1
    hostname: ksql-cli
    depends_on:
      - broker-1
      - schema_registry
      - ksql-server
    command: "perl -e 'while(1){ sleep 99999 }'"
    environment:
      KSQL_CONFIG_DIR: "/etc/ksql"
      KSQL_LOG4J_OPTS: "-Dlog4j.configuration=file:/etc/ksql/log4j-rolling.properties"
      STREAMS_BOOTSTRAP_SERVERS: broker-1:9092
      STREAMS_SCHEMA_REGISTRY_HOST: schema_registry
      STREAMS_SCHEMA_REGISTRY_PORT: 8081

  control-center:
    image: confluentinc/cp-enterprise-control-center:5.0.0-beta1-1
    hostname: control-center
    depends_on:
      - zookeeper
      - broker-1
      - schema_registry
      - connect
    ports:
      - "9021:9021"
    environment:
      CONTROL_CENTER_BOOTSTRAP_SERVERS: 'broker-1:9092'
      CONTROL_CENTER_ZOOKEEPER_CONNECT: 'zookeeper:2181'
      CONTROL_CENTER_CONNECT_CLUSTER: 'connect:8083'
      CONTROL_CENTER_REPLICATION_FACTOR: 1
      CONTROL_CENTER_INTERNAL_TOPICS_PARTITIONS: 1
      CONTROL_CENTER_MONITORING_INTERCEPTOR_TOPIC_PARTITIONS: 1
      CONFLUENT_METRICS_TOPIC_REPLICATION: 1
      PORT: 9021

  schema-registry-ui:
    image: landoop/schema-registry-ui
    hostname: schema-registry-ui
    depends_on:
      - broker-1
      - schema_registry
    ports:
      - "8002:8000"
    environment:
      SCHEMAREGISTRY_URL: 'http://${PUBLIC_IP}:8081'

  kafka-manager:
    image: trivadisbds/kafka-manager
    hostname: kafka-manager
    depends_on:
      - zookeeper
    ports:
      - "39000:9000"
    environment:
      ZK_HOSTS: 'zookeeper:2181'
      APPLICATION_SECRET: 'letmein'
    restart: always

  streamsets:
    image: trivadisbds/streamsets-kafka-nosql
    hostname: streamsets
    ports:
      - "18630:18630"
    volumes:
      - ./streamsets/user-libs:/opt/streamsets-datacollector-user-libs
      - ./streamsets/data:/data      
    restart: always

  nifi:
    image: apache/nifi:1.6.0
    hostname: nifi
    ports:
      - "28080:8080"
    restart: always

  zeppelin:
    image: dylanmei/zeppelin
    container_name: zeppelin
    ports:
      - "38080:8080"
    environment:
      ZEPPELIN_PORT: 8080
      ZEPPELIN_JAVA_OPTS: >-
        -Dspark.driver.memory=1g
        -Dspark.executor.memory=2g
      MASTER: local[*]
    volumes:
      - ./data:/usr/zeppelin/data
      - ./  :/usr/zeppelin/notebook
    restart: always
```

## Start the environment

Before we can start the environment, we have to set the environment variable DOCKER_HOST_IP to contain the IP-address of the Docker Host and environment variable PUBLIC_IP to the public IP address (not the same if you are using Azure). 
You can find the IP-Address of the Docker host using the `ifconfig` config from the linux shell. The public IP address of the VM in Azure can be found in the Azure portal.

```
export PUBLIC_IP=40.91.195.92
export DOCKER_HOST_IP=10.0.1.4
```
Now let's run all the container specified by the Docker Compose configuration.

```
docker-compose up -d
```

The first time it will take a while, as it has to download many Docker images.

After it has started, you can get the log output of all services by executing
 
```
docker-compose logs -f
```

if you want to see the services running for our environment, perform the following command:

```
docker ps

CONTAINER ID        IMAGE                                            COMMAND                  CREATED             STATUS                           PORTS                                          NAMES
d01fb522accd        apache/nifi:1.6.0                                "/bin/sh -c ${NIFI_B…"   6 hours ago         Up 6 hours                       8443/tcp, 10000/tcp, 0.0.0.0:38080->8080/tcp   stream-processing_nifi_1
9ecf9a3ab42c        trivadisbds/streamsets-kafka-nosql               "/docker-entrypoint.…"   6 hours ago         Up 6 hours                       0.0.0.0:18630->18630/tcp                       stream-processing_streamsets_1
5e96deeff9cc        confluentinc/ksql-cli:5.0.0-beta1                "perl -e 'while(1){ …"   7 hours ago         Up 7 hours                                                                      stream-processing_ksql-cli_1
cf4893312d40        confluentinc/cp-kafka-rest:5.0.0-beta1-1         "/etc/confluent/dock…"   7 hours ago         Up 7 hours                       8082/tcp, 0.0.0.0:8084->8084/tcp               stream-processing_rest-proxy_1
a36ed06fa71f        landoop/schema-registry-ui                       "/run.sh"                7 hours ago         Up 7 hours                       0.0.0.0:8002->8000/tcp                         stream-processing_schema-registry-ui_1
382358f81cf8        confluentinc/cp-enterprise-kafka:5.0.0-beta1-1   "/etc/confluent/dock…"   7 hours ago         Up 7 hours                       9092/tcp, 0.0.0.0:9093->9093/tcp               stream-processing_broker-2_1
e813de06f7cd        confluentinc/cp-enterprise-kafka:5.0.0-beta1-1   "/etc/confluent/dock…"   7 hours ago         Up 7 hours                       0.0.0.0:9092->9092/tcp                         stream-processing_broker-1_1
c2210b42db6e        confluentinc/cp-enterprise-kafka:5.0.0-beta1-1   "/etc/confluent/dock…"   7 hours ago         Up 7 hours                       9092/tcp, 0.0.0.0:9094->9094/tcp               stream-processing_broker-3_1
db2033adfd2a        trivadisbds/kafka-manager                        "./km.sh"                7 hours ago         Restarting (255) 7 seconds ago                                                  stream-processing_kafka-manager_1
676e4f734b09        confluentinc/cp-zookeeper:5.0.0-beta1-1          "/etc/confluent/dock…"   7 hours ago         Up 7 hours                       2888/tcp, 0.0.0.0:2181->2181/tcp, 3888/tcp     stream-processing_zookeeper_1
```

### Add inbound rules for the follwing ports
If you are using a VM on Azure, make sure to add inbound rules for the following ports:

Service | Url
------- | -------------
StreamSets Data Collector | 18630
Apache NiFi | 28080
Apache Zepplin  | 38080
Schema Registry UI  | 8002
Schema Registry Rest API  | 8081
Kafka Manager  | 39000
Confluent Control Center | 9021


### Add entry to local /etc/hosts File
To simplify working with the Streaming Platform, add the following entry to your local `/etc/hosts` file. 

```
40.91.195.92	streamingplatform
```

## Services accessible on Streaming Platform
The following service are available as part of the platform:

Type | Service | Url
------|------- | -------------
Development | StreamSets Data Collector | <http://streamingplatform:18630>
Development | Apache NiFi | <http://streamingplatform:28080/nifi>
Development | Apache Zepplin  | <http://streamingplatform:38080>
Governance | Schema Registry UI  | <http://streamingplatform:8002>
Governance | Schema Registry Rest API  | <http://streamingplatform:8081>
Management | Kafka Manager  | <http://streamingplatform:39000>
Management | Confluent Control Center | <http://streamingplatform:9021>


## Stop the environment
To stop the environment, execute the following command:

```
docker-compose stop
```

after that it can be re-started using `docker-compose start`.

To stop and remove all running container, execute the following command:

```
docker-compose down
```

