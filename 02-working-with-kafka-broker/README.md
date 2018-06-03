# Getting started with Apache Kafka
In this workshop we will learn the basics of working with Apache Kafka. Make sure that you have created the environment as described in [Preparing the Environment](../01-environment/01-environment.md).
## Using the Command Line Utilities 

### Connect to a Kafka Broker 
The environment contains of a Kafka cluster with 3 brokers, all running on the Docker host of course. So it's of course not meant to really fault-tolerant but to demonstrate how to work with a Kafka cluster. 

To work with Kafka you need the command line utilities. The are available on each broker. So let's connect into one of the broker through a terminal window. 

1. open a terminal window on the Docker Host
2. run a `docker exec` command to run a shell in the docker container of broker-1

	```
	docker exec -ti streamingplatform_broker-1_1 bash
	```

### List topics in Kafka
The main units of interest in Kafka are topics and messages. A topic is simply what you publish a message to, topics are a stream of messages.

First, let's list the topics availble on a given Kafka Cluster.
For that we use the `kafka-topics` utility with the `--list` option. 

```
kafka-topics --list --zookeeper zookeeper:2181
```
We can see that there are some techical topics, _schemas being the one, where the Confluent Schema Registry stores its schemas. 

### Creating a topic in Kafka

Now let's create a new topic. For that we again use the `kafka-topics` utility but this time with the `--create` option. We will create a test topic with 6 partitions and replicated 2 times. 

```
kafka-topics --create \
			--zookeeper zookeeper:2181 \
			--partitions 6  \
			--replication-factor 2 \ 
			--topic test-topic
```
Re-Run the command to list the topics. You should see the new topic you have just created. 

### Produce and Consume from the command line
Now let's see the topic in use. The most basic way to test it is through the command line. Kafka comes with two handy utilities `kafka-console-consumer` and `kafka-console-producer` to consume and produce messages trought the command line. 

In a new terminal window, first let's run the consumer

```
kafka-console-consumer --bootstrap-server broker-1:9092,broker-2:9093 \
				--topic test-topic
```

In a another terminal, connect into broker-1 and run the following command to start the producer.
 
```
kafka-console-producer --broker-list broker-1:9092,broker-2:9093 \
				--topic test-topic
```

On the `>` prompt enter a few messages, separate each message by a new line

```
>aaa
>bbb
>ccc
>ddd
```

You should see the messages being consumed by the consumer. 

```
root@broker-1:/# kafka-console-consumer --bootstrap-server broker-1:9092,broker-2:9093 --topic test-topic --from-beginning
bbb
aaa
ccc
ddd
```

Stop the consumer with ctrl-C. 

```
echo "This is my first message!" | kafka-console-producer \
                  --broker-list broker-1:9092,broker-2:9093 \
                  --topic test-topic
echo "This is my second message!" | kafka-console-producer \
                  --broker-list broker-1:9092,broker-2:9093 \
                  --topic test-topic
echo "This is my third message!" | kafka-console-producer \
                  --broker-list broker-1:9092,broker-2:9093 \
                  --topic test-topic 
```

They are not in the same order, because of the different partitions, and the messages being published in multiple partitions. We can force order, by using a key when publishing the messages and always using the same value for the key. 

### Working with Keyed Messages
A message produced to Kafka always consists of a key and a value, the value being necessary and representing the message/event payload. If a key is not specified, such as we did so far, then it is passed as a null value and Kafka distributes such messages in a round-robin fashion over the different partitions. 

We can check that by just listing the messages we have so far specifying the properties `print.key` `key.separator` together with the `--from-beginning` in the console consumer. 

```
kafka-console-consumer --bootstrap-server broker-1:9092,broker-2:9093 \
							--topic test-topic \
							--property print.key=true \
							--property key.separator=, \
							--from-beginning
```

```
kafka-console-producer --broker-list broker-1:9092,broker-2:9093 \
							--topic test-topic \
							--property parse.key=true \
							--property key.separator=,
```

### Dropping a Kafka topic
A Kafka topic can be droped using the `kafka-topics` utility with the `--delete` option. 

```
kafka-topics --zookeeper zookeeper:2181 --delete --topic test-topic
```


### Creating Kafka Topics upon startup 

```
  kafka-client:
    image: confluentinc/cp-enterprise-kafka:4.1.0
    hostname: kafka-client
    container_name: kafka-client
    depends_on:
      - kafka1
    volumes:
      - $PWD/scripts/security:/etc/kafka/secrets
    # We defined a dependency on "kafka", but `depends_on` will NOT wait for the
    # dependencies to be "ready" before starting the "kafka-client"
    # container;  it waits only until the dependencies have started.  Hence we
    # must control startup order more explicitly.
    # See https://docs.docker.com/compose/startup-order/
    command: "bash -c -a 'echo Waiting for Kafka to be ready... && \
                       /etc/confluent/docker/configure && \
                       cub kafka-ready -b kafka1:9091 1 60 --config /etc/kafka/kafka.properties && \
                       sleep 5 && \
                       kafka-topics --zookeeper zookeeper:2181 --topic users --create --replication-factor 2 --partitions 2 && \
                       kafka-topics --zookeeper zookeeper:2181 --topic wikipedia.parsed --create --replication-factor 2 --partitions 2 && \
                       kafka-topics --zookeeper zookeeper:2181 --topic wikipedia.failed --create --replication-factor 2 --partitions 2 && \
                       kafka-topics --zookeeper zookeeper:2181 --topic WIKIPEDIABOT --create --replication-factor 2 --partitions 2 && \
                       kafka-topics --zookeeper zookeeper:2181 --topic WIKIPEDIANOBOT --create --replication-factor 2 --partitions 2 && \
                       kafka-topics --zookeeper zookeeper:2181 --topic EN_WIKIPEDIA_GT_1 --create --replication-factor 2 --partitions 2 && \
                       kafka-topics --zookeeper zookeeper:2181 --topic EN_WIKIPEDIA_GT_1_COUNTS --create --replication-factor 2 --partitions 2'"
    environment:
      # The following settings are listed here only to satisfy the image's requirements.
      # We override the image's `command` anyways, hence this container will not start a broker.
      KAFKA_BROKER_ID: ignored
      KAFKA_ZOOKEEPER_CONNECT: ignored
      KAFKA_ADVERTISED_LISTENERS: ignored
      KAFKA_SECURITY_PROTOCOL: SASL_SSL
      KAFKA_SASL_JAAS_CONFIG: "org.apache.kafka.common.security.plain.PlainLoginModule required \
        username=\"client\" \
        password=\"client-secret\";"
      KAFKA_SASL_MECHANISM: PLAIN
      KAFKA_SSL_TRUSTSTORE_LOCATION: /etc/kafka/secrets/kafka.client.truststore.jks
      KAFKA_SSL_TRUSTSTORE_PASSWORD: confluent
      KAFKA_SSL_KEYSTORE_LOCATION: /etc/kafka/secrets/kafka.client.keystore.jks
      KAFKA_SSL_KEYSTORE_PASSWORD: confluent
      KAFKA_SSL_KEY_PASSWORD: confluent
      KAFKA_ZOOKEEPER_SET_ACL: "true"
      KAFKA_OPTS: -Djava.security.auth.login.config=/etc/kafka/secrets/broker_jaas.conf
    ports:
- "7073:7073"
```