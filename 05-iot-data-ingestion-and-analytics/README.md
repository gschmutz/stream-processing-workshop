# Ingest IoT Vehicle Data

In this workshop we will be ingesting IoT data into a Kafka topic from which it will later be use to do analytics using various Stream Analytics components. To make it a bit more realistic, the data is not directly sent to Kafka from the IoT devices (vehicles) but first sent through an MQTT broker (IoT gateway). 

The following diagram shows the setup of the data flow we will be implementing. 
We will be using a fictitious Trucking company with a fleet of trucks constantly providing some data about the moving vehicles. Of course we will not be using real-life data, but have a program simulating trucks and their driving behaviour.

For simulating truck data, we are going to use a Java program (adapted from Hortonworks) and maintained in this [GitHub project](https://github.com/TrivadisBDS/various-bigdata-prototypes/tree/master/streaming-sources/iot-truck-simulator/impl). It can be started either using Maven or Docker. We will be using it as a Docker container.

The simulator can produce data to various data sinks, such as **File**, **MQTT** or event **Kafka**. For our workshop here, we will be using **File** and **MQTT** as the target, but first let's use it in **File** mode. 

![Alt Image Text](./images/iot-ingestion-overview.png "Schema Registry UI")

We will implement this end-to-end demo case step by step using different technologies. The links to the separate documents can be found as follows:

1. [Ingesting simulated IoT from System A into MQTT](../05a-iot-data-ingestion-sys-a-into-mqtt/README.md)
2. [Ingesting simulated IoT from System B into Kafka](../05b-iot-data-ingestion-sys-b-into-kafak/README.md)
2. [Moving Data from MQTT into Kafka using Kafka Connect](../05b-iot-data-ingestion-mqtt-to-kafka-with-connect/README.md)
3. [Moving Data from MQTT into Kafka using Apache NiFi](../05b-iot-data-ingestion-mqtt-to-kafka-with-nifi/README.md)
3. [Moving Data from MQTT into Kafka using Apache NiFi](../05b-iot-data-ingestion-mqtt-to-kafka-with-nifi/README.md)

3. [Stream Transformation using ksqlDB](../05c-stream-processing-using-ksql/README.md)

3. [Stream Processing using Faust](../05d-stream-processing-using-faust/README.md)
4. [Ingesting and Joining Static Data to Stream](../05e-static-data-ingestion/README.md)
5. [Moving Data from Kafka to Object Storage](../05f-stream-data-integration-with-s3/README.md)