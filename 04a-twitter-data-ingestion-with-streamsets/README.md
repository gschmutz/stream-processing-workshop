# Ingesting Tweets into Kafka using StreamSets Data Collector

In this part of the workshop we are going to implement the ingestion of live twitter data into a topic in Apache Kafka using StreamSets Data Collector. 

StreamSets is part of the Data Platform.

## Log into StreamSets

Firs lets log into StreamSets. In a browser window, navigate to <http://dataplatform:18630>. The **StreamSets Data Collector** authentication page should be shown.

![Alt Image Text](./images/streamsets-login.png "Schema Registry UI")

Enter **admin** for username and also for the password.

## Create a new pipeline

On the **Get Started** screen, click on **Create New Pipeline**.

![Alt Image Text](./images/streamsets-create-new-pipeline.png "Schema Registry UI")

On the **New Pipeline** pop up, enter `Tweet_to_Kafka` for the **Title** field and a Description about the purpose of the new pipeline.

![Alt Image Text](./images/streamsets-new-pipeline-details.png "Schema Registry UI")

An empty canvas for the new pipeline is shown. 

![Alt Image Text](./images/streamsets-empty-pipeline.png "Schema Registry UI")

## Designing the pipeline

Select **HTTP Client - Basic** from the **Select Origin...** drop-down. 

![Alt Image Text](./images/streamsets-select-http-client.png "Schema Registry UI")

Select **Kafka Producer - Apache Kafka 1.0.0** from the **Select Desitination to connect...** drop-down. 

![Alt Image Text](./images/streamsets-select-kafka.png "Schema Registry UI")

The pipeline will be displayed with the Origin and Destination being connected. 

![Alt Image Text](./images/streamsets-pipeline-flow.png "Schema Registry UI")

You can see by the red explanation icons, that the pipeline has errors. They first have to be fixed, otherwise we cannot run the pipeline. 

Click on the red icon on the lower left corner and select **Discard (Library: Basic)** for the **Error Records** drop-down.

![Alt Image Text](./images/streamsets-fix-pipeline-error.png "Schema Registry UI")

## Configure the HTTP Client
Now let's configure the HTTP Client first. Click on the **HTTP Client 1** component on the canvas, it will change to blue. 

Click on the **HTTP** tab and enter `https://stream.twitter.com/1.1/statuses/filter.json?track=trump` into the **Resource URL** edit field. Also change the **Authentication Type** to `OAuth`. 

![Alt Image Text](./images/streamsets-http-client-config-http1.png "Schema Registry UI")

Now click on **Credentials** tab and enter the values for the Twitter application into the **Consumer Key**, **Consumer Secret**, **Token** and **Token Secret**. You can find the steps for creating a new Twitter Application [here](../99-misc/99-twitter-app/README.md). 

![Alt Image Text](./images/streamsets-http-client-config-http2.png "Schema Registry UI")

Click on the **Data Format** tab and make sure `JSON` is selected for the **Data Format** drop down. 

Increase the value of **Max Object Length (chars)** to `409600`.

![Alt Image Text](./images/streamsets-http-client-config-http3.png "Schema Registry UI")

### Configure the Kafka Producer
Now let's configure the Kafka Producer. Click on the **Kafka Producer 1** component on the canvas and select the **Kafka** tab. 

Enter `kafka-1:19092,kafka-2:19093` into the **Broker URI** edit field and `tweet-json` into the **Topic** field.

![Alt Image Text](./images/streamsets-kafka-producer-config-kafka.png "Schema Registry UI")
Click on the **Data Format** tab and make sure `JSON` is selected for the **Data Format**. 

### Create the topic in Kafka

Create the topic using the `kafka-topics` command. 

```
kafka-topics --create \
			--if-not-exists \
			--bootstrap-server kafka-1:19092 \
			--topic tweet-json \
			--partitions 6 \
			--replication-factor 2
```

Now let's start a `kafkacat` consumer on the new topic:

```
kafkacat -b dataplatform:9092 -t tweet-json
```
Now let's run the pipeline. There are two ways you can run a pipeline in StreamSets, either in **Preview** mode with no/minimal side-effects or in **Execution** mode, where the pipeline runs until stopped. 
 
### Preview the pipeline
The Preview mode allows you to check your pipeline before executing it. 

Click on the **Preview** icon on the menu-bar, as shown on the following screenshot:
 
![Alt Image Text](./images/streamsets-preview-pipeline.png "Schema Registry UI")

On the **Preview Configuration** pop-up window you can configure how side-effect free your preview should be (option **Write to Destinations and Executors** and **Execute pipeline lifecycle events**). 

Additionally you define from where the source should read the events for the preview. From **Configured Source** will use "live" data but you could also take data from a snapshot captured in an earlier run. 

Click on **Run Preview**.

![Alt Image Text](./images/streamsets-preview-pipeline-options.png "Schema Registry UI")

The Preview mode will get the configured number of events (**Preview Batch Size** setting on previous screen) from the source or stop after the timeout (**Preview Timeout** setting on previous screen). 

You can see that the component **HTTP Client 1** is selected and you can see both the input and the output of that component below. 

![Alt Image Text](./images/streamsets-previewing-pipeline-1.png "Schema Registry UI")

You can drill-down into each record as shown below.

![Alt Image Text](./images/streamsets-previewing-pipeline-2.png "Schema Registry UI")

Preview mode will be even more helpful if a Processor component is used between an Origin and a Destination, and you will be able to view the change between the Input Data and the Output Data done by the Processor.

### Run the pipeline 
Now let's run the pipeline. Click on the Start icon in the menu bar in the top right corner. 

![Alt Image Text](./images/streamsets-start-pipeline.png "Schema Registry UI")

The pipeline should change in the **RUNNING** state and the tweets should start to show up on the kafkacat terminal. 

![Alt Image Text](./images/terminal-kafkacat-output.png "Schema Registry UI")

You can see the that StreamSets also switches into the monitoring view, where you can find statistics about the data flow you run (such as number of rows processed, bot successfully and error as well as throughput). 

![Alt Image Text](./images/streamsets-running-pipeline.png "Schema Registry UI")

You can drill down to each component, by just selecting one of the components. 

### Stop the pipeline 

To stop a running pipeline, click on the stop button on the top right. 