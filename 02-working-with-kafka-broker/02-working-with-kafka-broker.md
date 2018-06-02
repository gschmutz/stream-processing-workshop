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
First, let's list the topics availble on a given Kafka Cluster.
For that we use the `kafka-topics` utility with the `--list` option. 

```
kafka-topics --list --zookeeper zookeeper:2181
```
We can see that there are some techical topics, _schemas being the one, where the Confluent Schema Registry stores its schemas. 

### Creating a topic in Kafka

Now let's create a new topic. For that we again use the `kafka-topics` utility but this time with the `--create` option. 

```
kafka-topics --create --zookeeper zookeeper:2181 --partitions 3 --replication-factor 2 --topic test-topic
```
Re-Run the command to list the topics. You should see the new topic you have just created.  

### Produce and Consume from the command line
Now let's see the topic in use. The most basic way to test it is through the command line. Kafka comes with two handy utilities `kafka-console-consumer` and `kafka-console-producer` to consume and produce messages trought the command line. 

In a new terminal, connect into broker-1 and run the following command to start the producer.
 
```
kafka-console-producer --broker-list broker-1:9092,broker-2:9092 --topic test-topic
```
In another terminal window, run the consumer

```
kafka-console-consumer --zookeeper zookeeper:2181 --topic test-topic --from-beginning
```



