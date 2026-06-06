# Getting started with Apache Kafka

In this workshop we will learn the basics of working with Apache Kafka. Make sure that you have created the environment as described in [Preparing the Environment](../00-environment/README.md).

The main units of interest in Kafka are topics and messages. A topic is simply what you publish a message to; topics are a stream of messages.

## Table of Contents

- [What you will learn](#what-you-will-learn)
- [Prerequisites](#prerequisites)
- [Using built-in Command Line Utilities](#using-built-in-command-line-utilities)
- [Working with Consumer Groups](#working-with-consumer-groups)
- [Using `kcat`](#using-kcat)
- [Publishing a "real" data stream to Kafka](#publishing-a-real-data-stream-to-kafka)
- [Retention and Log Compaction](#retention-and-log-compaction)
- [Using AKHQ](#using-akhq)

## What you will learn

- How to connect to a Kafka broker using the built-in command line utilities
- How to create, describe, and delete Kafka topics
- How to produce and consume messages using `kafka-console-producer` and `kafka-console-consumer`
- How to work with keyed messages in Kafka
- How consumer groups distribute partitions across multiple consumers and how to monitor lag
- How to use `kcat` as a powerful alternative CLI for producing and consuming messages
- How to stream realistic test data into Kafka using a sales data simulator
- How topic retention controls how long data is kept, and how log compaction keeps only the latest value per key
- How to inspect and manage your Kafka cluster using the AKHQ and CMAK web UIs

## Prerequisites

- The **Data Platform** described [here](../00-environment/README.md) is running and accessible
- Basic familiarity with the Linux command line

## Using built-in Command Line Utilities

### Connect to a Kafka Broker

The environment contains a Kafka cluster with 3 brokers, all running on the Docker host. It is not designed for production fault tolerance, but it gives you a realistic multi-broker environment to work with.

The command line utilities are available on each broker. The `kafka-topics` utility is used to create, alter, describe, and delete topics. `kafka-console-producer` and `kafka-console-consumer` are used to produce and consume messages.

Connect to one of the Kafka brokers. In the terminal window, run a `docker exec` command to open a shell in the `kafka-1` container:

```bash
docker exec -ti kafka-1 bash
```

Running `kafka-topics` without any options prints the help page:

```bash
root@kafka-1:/# kafka-topics
Create, delete, describe, or change a topic.
Option                                   Description
------                                   -----------
--alter                                  Alter the number of partitions,
                                           replica assignment, and/or
                                           configuration for the topic.
--at-min-isr-partitions                  if set when describing topics, only
                                           show partitions whose isr count is
                                           equal to the configured minimum.
--bootstrap-server <String: server to    REQUIRED: The Kafka server to connect
  connect to>                              to.
--create                                 Create a new topic.
--delete                                 Delete a topic
--describe                               List details for the given topics.
--list                                   List all available topics.
--partitions <Integer: # of partitions>  The number of partitions for the topic
                                           being created or altered.
--replication-factor <Integer:           The replication factor for each
  replication factor>                      partition in the topic being created.
--topic <String: topic>                  The topic to create, alter, describe
                                           or delete.
--version                                Display Kafka version.
```

### List topics in Kafka

List the topics currently on the cluster using the `--list` option:

```bash
kafka-topics --list --bootstrap-server kafka-1:19092,kafka-2:19093
```

> **What you should see:** A list of topic names. Even on a fresh cluster you will see at least one internal topic — `_schemas` — which is where the Confluent Schema Registry stores its schemas. Later you will see `__consumer_offsets` appear once consumers start committing offsets.

> **What just happened?** `kafka-topics --list` sends a metadata request to the broker and returns the names of all topics known to the cluster. The `--bootstrap-server` flag is the initial contact point — Kafka uses it to discover the full cluster and route the request to the appropriate controller.

### Creating a topic in Kafka

Create a new topic using the `--create` option. We will create a test topic with 6 partitions and a replication factor of 2. The `--if-not-exists` option suppresses errors if the topic already exists.

```bash
kafka-topics --create \
             --if-not-exists \
             --bootstrap-server kafka-1:19092,kafka-2:19093 \
             --topic test-topic \
             --partitions 6 \
             --replication-factor 2
```

> **What you should see:** The command completes silently (no output means success). Re-run `kafka-topics --list` and you will see `test-topic` alongside the internal topics.

> **What just happened?** Kafka registered the new topic in its internal metadata log and instructed the brokers to create the required partition replicas. With 6 partitions and a replication factor of 2, Kafka created 12 replica logs spread across the 3 brokers (4 per broker). One replica per partition is elected **Leader** and handles all reads and writes; the others are **Followers** that stay in sync.

### Describe a Topic

Use `--describe` to see the details of a topic:

```bash
kafka-topics --describe --bootstrap-server kafka-1:19092,kafka-2:19093 --topic test-topic
```

```
Topic: test-topic   PartitionCount: 6   ReplicationFactor: 2   Configs:
    Topic: test-topic   Partition: 0    Leader: 3   Replicas: 3,2   Isr: 3,2
    Topic: test-topic   Partition: 1    Leader: 1   Replicas: 1,3   Isr: 1,3
    Topic: test-topic   Partition: 2    Leader: 2   Replicas: 2,1   Isr: 2,1
    Topic: test-topic   Partition: 3    Leader: 3   Replicas: 3,1   Isr: 3,1
    Topic: test-topic   Partition: 4    Leader: 1   Replicas: 1,2   Isr: 1,2
    Topic: test-topic   Partition: 5    Leader: 2   Replicas: 2,3   Isr: 2,3
```

> **What you should see:** Six rows, one per partition. Each row shows which broker is the current **Leader**, which brokers hold **Replicas**, and which replicas are in the **In-Sync Replica (ISR)** set — the replicas that are fully caught up with the leader.

> **What just happened?** Kafka distributed the 6 partition leaders evenly across the 3 brokers. If a leader broker goes down, Kafka automatically elects a new leader from the ISR set — this is how the cluster stays available without losing data.

### Producing and Consuming Messages

Kafka provides two command line utilities for testing: `kafka-console-producer` and `kafka-console-consumer`.

In a new terminal window, start the consumer on `test-topic`:

```bash
kafka-console-consumer --bootstrap-server kafka-1:19092,kafka-2:19093 \
                       --topic test-topic
```

Once started, the consumer waits for incoming messages.

In another terminal, connect to `kafka-1`:

```bash
docker exec -ti kafka-1 bash
```

Then start the producer:

```bash
kafka-console-producer --bootstrap-server kafka-1:19092,kafka-2:19093 --topic test-topic
```

By default, the console producer batches messages for up to **1,000 ms** or until the batch reaches **16,384 bytes**. These limits are controlled by the `--timeout` and `--max-partition-memory-bytes` options respectively.

> **Note:** Even if you specify `linger.ms` and `batch.size` via `--producer-property` or `--producer.config`, they will always be overridden by the above options.

At the `>` prompt, type a few messages and press **Enter** after each one:

```
>aaa
>bbb
>ccc
>ddd
>eee
```

> **What you should see:** The messages appear in the consumer terminal in the same order they were typed.

```
aaa
bbb
ccc
ddd
eee
```

> **What just happened?** The producer wrote each message to one of the 6 partitions (chosen by the default round-robin partitioner). The consumer subscribed to all 6 partitions and displayed messages as they arrived. Because you typed slowly enough that each message was sent and consumed before the next, they appear in order — but this ordering is only guaranteed *within a single partition*, not across partitions.

You can stop the consumer with **Ctrl-C**. To replay all messages from the beginning, use the `--from-beginning` option.

You can also pipe a message directly into the producer:

```bash
echo "This is my first message!" | kafka-console-producer \
                         --bootstrap-server kafka-1:19092,kafka-2:19093 \
                         --topic test-topic
```

Or send multiple messages using a bash for loop:

```bash
for i in 1 2 3 4 5 6 7 8 9 10
do
   echo "This is message $i" | kafka-console-producer \
          --bootstrap-server kafka-1:19092,kafka-2:19093 \
          --topic test-topic \
          --batch-size 1 &
done
```

The trailing `&` runs each producer in the background in parallel.

> **What you should see:** The messages arrive at the consumer out of order, because they are published in parallel to multiple partitions.

> **What just happened?** Each of the 10 producer processes ran independently and wrote its message to a different partition. Because messages in different partitions are consumed independently, the consumer sees them interleaved in delivery order — not the order they were sent.

### Working with Keyed Messages

A Kafka message consists of a key and a value. The value carries the event payload; the key is optional but controls which partition the message is routed to. When no key is provided, Kafka sets it to `null` and distributes messages across partitions using round-robin.

We can verify this by consuming with `--from-beginning` and enabling key display. Stop the existing consumer and restart it:

```bash
kafka-console-consumer --bootstrap-server kafka-1:19092,kafka-2:19093 \
                      --topic test-topic \
                      --property print.key=true \
                      --property key.separator=, \
                      --from-beginning
```

> **What you should see:** Every message is printed as `null,aaa` — the `null` key followed by the comma separator and the value. This confirms that all messages produced so far had no key.

> **What just happened?** Kafka stores a key field alongside every message. When the producer sends no key, it stores `null`. The consumer's `print.key=true` property makes this visible at consumption time.

To produce messages with a key, add the `parse.key` and `key.separator` properties:

```bash
kafka-console-producer  --bootstrap-server kafka-1:19092,kafka-2:19093 \
                        --topic test-topic \
                        --property parse.key=true \
                        --property key.separator=,
```

Type a few messages in `key,value` format, e.g. `key1,value1`, and verify they appear in the consumer window with both key and value printed.

> **What you should see:** The consumer now displays `key1,value1` — the key and value separated by the configured comma. Produce multiple messages with the same key and they will always land on the same partition.

> **What just happened?** Kafka hashes the key using the murmur2 algorithm and maps the result to a partition number. Any two messages with the same key always hash to the same partition, guaranteeing that a consumer reading that partition sees those messages in the exact order they were written.

### Deleting a Kafka topic

Delete a topic using the `--delete` option:

```bash
kafka-topics  --bootstrap-server kafka-1:19092,kafka-2:19093 --delete --topic test-topic
```

> **What you should see:** The command completes silently. Re-run `kafka-topics --list` and `test-topic` will no longer appear.

> **What just happened?** Kafka queued the topic for deletion. With `delete.topic.enable=true` (configured in the platform), the broker asynchronously removes the underlying partition log files. The topic disappears from the metadata immediately, even before the file cleanup completes.

## Working with Consumer Groups

A **consumer group** is a set of consumers that cooperate to consume messages from a set of topics. Kafka automatically assigns each partition to exactly one consumer within the group, so messages within a partition are processed in order, while different partitions can be processed in parallel.

When consumers join or leave a group, Kafka triggers a **rebalance** to redistribute partitions evenly. This is the mechanism that lets you scale consumption horizontally by simply starting additional consumers.

### Create a topic for the consumer group demo

Create a fresh topic with 6 partitions for this section:

```bash
kafka-topics --create \
             --if-not-exists \
             --bootstrap-server kafka-1:19092 \
             --topic cg-test-topic \
             --partitions 6 \
             --replication-factor 3
```

### Start consumers in the same group

Open **three separate terminal windows** and connect to `kafka-1` in each one:

```bash
docker exec -ti kafka-1 bash
```

In each terminal, start a consumer that joins the **same consumer group** `my-consumer-group`:

```bash
kafka-console-consumer --bootstrap-server kafka-1:19092 \
                       --topic cg-test-topic \
                       --group my-consumer-group
```

> **What you should see:** Each consumer starts and waits for messages. With 6 partitions and 3 consumers, each consumer is assigned 2 partitions. Each terminal prints a log line showing its assigned partitions, such as `Assigned partitions: [cg-test-topic-0, cg-test-topic-1]`.

> **What just happened?** When the first consumer joined the group, it was assigned all 6 partitions. When the second joined, Kafka triggered a **rebalance** and redistributed the partitions — 3 to each consumer. When the third joined, another rebalance gave each consumer exactly 2 partitions. The **group coordinator** broker manages this process using the consumers' heartbeats to track who is alive in the group.

### Produce messages and observe distribution

Open a **fourth terminal**, connect to `kafka-1`, and produce 30 messages in a loop:

```bash
docker exec -ti kafka-1 bash
```

```bash
for i in $(seq 1 30)
do
   echo "message-$i" | kafka-console-producer \
          --bootstrap-server kafka-1:19092 \
          --topic cg-test-topic \
          --batch-size 1
done
```

> **What you should see:** The 30 messages are spread across the three consumer terminals. Each consumer only receives messages from the partitions it owns — the same message will never appear in two consumers.

> **What just happened?** Kafka used the default round-robin partitioner (no key was set) to distribute messages across the 6 partitions. Since each consumer owns 2 partitions, each received roughly 10 of the 30 messages. The fundamental guarantee is **exclusive partition ownership**: within a consumer group, each partition is consumed by exactly one consumer at a time.

### Observe a rebalance

Stop one of the three consumers with **Ctrl-C**. After a few seconds the two surviving consumers will each take on 3 partitions instead of 2.

Restart the stopped consumer. A second rebalance fires and all three consumers return to 2 partitions each.

> **What you should see:** When you stop a consumer, the other two each print a new partition assignment showing they now own 3 partitions. When you restart, a third rebalance returns all three consumers to 2 partitions each.

> **What just happened?** Each consumer sends periodic **heartbeats** to the group coordinator. When a consumer stops, its heartbeats cease. After `session.timeout.ms` (default 45 seconds for the console consumer), the coordinator declares it dead and triggers a rebalance. The surviving consumers re-join the group and the coordinator uses the configured assignment strategy (range or round-robin) to redistribute all partitions evenly.

### List and describe consumer groups

The `kafka-consumer-groups` utility lets you inspect all active consumer groups and see how far behind each consumer is.

List all consumer groups:

```bash
kafka-consumer-groups --bootstrap-server kafka-1:19092 --list
```

Describe the group to see partition assignments and **lag** (the number of messages produced but not yet consumed):

```bash
kafka-consumer-groups --bootstrap-server kafka-1:19092 \
                      --describe \
                      --group my-consumer-group
```

```
GROUP              TOPIC          PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG  CONSUMER-ID                          HOST
my-consumer-group  cg-test-topic  0          5               5               0    consumer-1-...                       /172.x.x.x
my-consumer-group  cg-test-topic  1          5               5               0    consumer-1-...                       /172.x.x.x
my-consumer-group  cg-test-topic  2          5               5               0    consumer-2-...                       /172.x.x.x
my-consumer-group  cg-test-topic  3          5               5               0    consumer-2-...                       /172.x.x.x
my-consumer-group  cg-test-topic  4          5               5               0    consumer-3-...                       /172.x.x.x
my-consumer-group  cg-test-topic  5          5               5               0    consumer-3-...                       /172.x.x.x
```

Stop all three consumers and produce a few more messages — then re-run `--describe` to see the lag grow.

> **What you should see:** Six rows, one per partition. Each row shows the consumer's ID, its `CURRENT-OFFSET` (the last committed offset), the `LOG-END-OFFSET` (the highest offset written to that partition), and the `LAG` (the difference). When all consumers are running and caught up, lag is 0. After stopping all consumers and producing more messages, the lag will grow to match the number of new unread messages.

> **What just happened?** Consumers periodically **commit** their current offset back to Kafka (stored in the internal `__consumer_offsets` topic). `CURRENT-OFFSET` is the last committed position — the offset the consumer will resume from on restart. `LOG-END-OFFSET` is the next offset the broker will assign to an incoming message. The difference between the two is the **consumer lag**, which is the primary operational metric for knowing whether your consumers are keeping up with producers.

### Reset consumer group offsets

To re-process messages from the beginning, reset the group's offsets. All consumers in the group must be stopped first:

```bash
kafka-consumer-groups --bootstrap-server kafka-1:19092 \
                      --group my-consumer-group \
                      --topic cg-test-topic \
                      --reset-offsets \
                      --to-earliest \
                      --execute
```

Restart the consumers and they will replay all messages from the start of each partition.

> **What you should see:** Each partition's `CURRENT-OFFSET` is reset to 0. When you restart the consumers, the lag briefly spikes to the total message count before dropping back to 0 as they catch up.

> **What just happened?** `--reset-offsets --to-earliest` overwrote the committed offsets in `__consumer_offsets` for every partition in the group. The next time a consumer starts, it reads this stored offset and resumes from that position — in this case, offset 0 (the beginning of each partition).

## Using `kcat`

[kcat](https://github.com/edenhill/kcat) is a command line utility for testing and debugging Apache Kafka. Described as "netcat for Kafka", it is a swiss-army knife for inspecting and creating data in Kafka, and a powerful alternative to `kafka-console-producer` and `kafka-console-consumer`.

`kcat` is available as a container in the Data Platform (enabled via `KCAT_enable: true`). You can also install it locally on any **Linux** or **Mac** computer to connect to a remote Kafka cluster.

### Installing `kcat` locally

In all workshops we assume that `kcat` is installed locally on the Docker host and that the `dataplatform` alias has been added to `/etc/hosts`.

> **Note:** `kcat` used to be `kafkacat` before version 1.7. If you have an older installation, replace `kcat` with `kafkacat` in the commands below, or define an alias: `alias kcat=kafkacat`.

#### Ubuntu > 23.04

```bash
sudo apt-get install kcat
```

Verify the installation:

```bash
$ kcat -V
kcat - Apache Kafka producer and consumer tool
https://github.com/edenhill/kcat
Copyright (c) 2014-2021, Magnus Edenhill
Version 1.7.1 (JSON, Transactions, IncrementalAssign, librdkafka 2.0.2 builtin.features=gzip,snappy,ssl,sasl,regex,lz4,sasl_gssapi,sasl_plain,sasl_scram,plugins,zstd,sasl_oauthbearer)
```

#### Mac OS-X

```bash
brew install kcat
```

Verify the installation:

```bash
% kcat -V
kcat - Apache Kafka producer and consumer tool
https://github.com/edenhill/kcat
Copyright (c) 2014-2021, Magnus Edenhill
Version 1.7.0 (JSON, Avro, Transactions, IncrementalAssign, librdkafka 2.0.2 builtin.features=gzip,snappy,ssl,sasl,regex,lz4,sasl_gssapi,sasl_plain,sasl_scram,plugins,zstd,sasl_oauthbearer,http,oidc)
```

#### Docker Container

You can also run `kcat` as a Docker container:

```bash
docker run --tty --network kafka-workshop edenhill/kcat:1.7.1 kcat
```

Set an alias to use the containerised version transparently:

```bash
alias kcat='docker run --tty --network host --add-host dataplatform:127.0.0.1 edenhill/kcat:1.7.1 kcat'
```

See [Running in Docker](https://github.com/edenhill/kcat#running-in-docker) for more options.

#### Windows

There is no official Windows build. You can try the unofficial build at <https://ci.appveyor.com/project/edenhill/kafkacat/builds/23675338/artifacts>, or run `kcat` as a Docker container as shown above.

### Display `kcat` options

Running `kcat` without arguments prints the full option list:

```bash
> kcat
Error: -b <broker,..> missing

Usage: kcat <options> [file1 file2 .. | topic1 topic2 ..]]
kcat - Apache Kafka producer and consumer tool
https://github.com/edenhill/kcat
Copyright (c) 2014-2021, Magnus Edenhill
Version 1.7.1 (JSON, Transactions, IncrementalAssign, librdkafka 2.3.0 builtin.features=gzip,snappy,ssl,sasl,regex,lz4,sasl_gssapi,sasl_plain,sasl_scram,plugins,zstd,sasl_oauthbearer)


General options:
  -C | -P | -L | -Q  Mode: Consume, Produce, Metadata List, Query mode
  -G <group-id>      Mode: High-level KafkaConsumer (Kafka >=0.9 balanced consumer groups)
                     Expects a list of topics to subscribe to
  -t <topic>         Topic to consume from, produce to, or list
  -p <partition>     Partition
  -b <brokers,..>    Bootstrap broker(s) (host[:port])
  -D <delim>         Message delimiter string:
                     a-z | \r | \n | \t | \xNN ..
                     Default: \n
  -K <delim>         Key delimiter (same format as -D)
  -c <cnt>           Limit message count
  -m <seconds>       Metadata (et.al.) request timeout.
                     This limits how long kcat will block
                     while waiting for initial metadata to be
                     retrieved from the Kafka cluster.
                     It also sets the timeout for the producer's
                     transaction commits, init, aborts, etc.
                     Default: 5 seconds.
  -F <config-file>   Read configuration properties from file,
                     file format is "property=value".
                     The KCAT_CONFIG=path environment can also be used, but -F takes precedence.
                     The default configuration file is $HOME/.config/kcat.conf
  -X list            List available librdkafka configuration properties
  -X prop=val        Set librdkafka configuration property.
                     Properties prefixed with "topic." are
                     applied as topic properties.
  -X dump            Dump configuration and exit.
  -d <dbg1,...>      Enable librdkafka debugging:
                     all,generic,broker,topic,metadata,feature,queue,msg,protocol,cgrp,security,fetch,interceptor,plugin,consumer,admin,eos,mock,assignor,conf
  -q                 Be quiet (verbosity set to 0)
  -v                 Increase verbosity
  -E                 Do not exit on non-fatal error
  -V                 Print version
  -h                 Print usage help

Producer options:
  -z snappy|gzip|lz4 Message compression. Default: none
  -p -1              Use random partitioner
  -D <delim>         Delimiter to split input into messages
  -K <delim>         Delimiter to split input key and message
  -k <str>           Use a fixed key for all messages.
                     If combined with -K, per-message keys
                     takes precendence.
  -H <header=value>  Add Message Headers (may be specified multiple times)
  -l                 Send messages from a file separated by
                     delimiter, as with stdin.
                     (only one file allowed)
  -T                 Output sent messages to stdout, acting like tee.
  -c <cnt>           Exit after producing this number of messages
  -Z                 Send empty messages as NULL messages
  file1 file2..      Read messages from files.
                     With -l, only one file permitted.
                     Otherwise, the entire file contents will
                     be sent as one single message.
  -X transactional.id=.. Enable transactions and send all
                     messages in a single transaction which
                     is committed when stdin is closed or the
                     input file(s) are fully read.
                     If kcat is terminated through Ctrl-C
                     (et.al) the transaction will be aborted.

Consumer options:
  -o <offset>        Offset to start consuming from:
                     beginning | end | stored |
                     <value>  (absolute offset) |
                     -<value> (relative offset from end)
                     s@<value> (timestamp in ms to start at)
                     e@<value> (timestamp in ms to stop at (not included))
  -e                 Exit successfully when last message received
  -f <fmt..>         Output formatting string, see below.
                     Takes precedence over -D and -K.
  -J                 Output with JSON envelope
  -s key=<serdes>    Deserialize non-NULL keys using <serdes>.
  -s value=<serdes>  Deserialize non-NULL values using <serdes>.
  -s <serdes>        Deserialize non-NULL keys and values using <serdes>.
                     Available deserializers (<serdes>):
                       <pack-str> - A combination of:
                                    <: little-endian,
                                    >: big-endian (recommended),
                                    b: signed 8-bit integer
                                    B: unsigned 8-bit integer
                                    h: signed 16-bit integer
                                    H: unsigned 16-bit integer
                                    i: signed 32-bit integer
                                    I: unsigned 32-bit integer
                                    q: signed 64-bit integer
                                    Q: unsigned 64-bit integer
                                    c: ASCII character
                                    s: remaining data is string
                                    $: match end-of-input (no more bytes remaining or a parse error is raised).
                                       Not including this token skips any
                                       remaining data after the pack-str is
                                       exhausted.
  -D <delim>         Delimiter to separate messages on output
  -K <delim>         Print message keys prefixing the message
                     with specified delimiter.
  -O                 Print message offset using -K delimiter
  -c <cnt>           Exit after consuming this number of messages
  -Z                 Print NULL values and keys as "NULL" instead of empty.
                     For JSON (-J) the nullstr is always null.
  -u                 Unbuffered output

Metadata options (-L):
  -t <topic>         Topic to query (optional)

Query options (-Q):
  -t <t>:<p>:<ts>    Get offset for topic <t>,
                     partition <p>, timestamp <ts>.
                     Timestamp is the number of milliseconds
                     since epoch UTC.
                     Requires broker >= 0.10.0.0 and librdkafka >= 0.9.3.
                     Multiple -t .. are allowed but a partition
                     must only occur once.

Format string tokens:
  %s                 Message payload
  %S                 Message payload length (or -1 for NULL)
  %R                 Message payload length (or -1 for NULL) serialized
                     as a binary big endian 32-bit signed integer
  %k                 Message key
  %K                 Message key length (or -1 for NULL)
  %T                 Message timestamp (milliseconds since epoch UTC)
  %h                 Message headers (n=v CSV)
  %t                 Topic
  %p                 Partition
  %o                 Message offset
  \n \r \t           Newlines, tab
  \xXX \xNNN         Any ASCII character
 Example:
  -f 'Topic %t [%p] at offset %o: key %k: %s\n'

JSON message envelope (on one line) when consuming with -J:
 { "topic": str, "partition": int, "offset": int,
   "tstype": "create|logappend|unknown", "ts": int, // timestamp in milliseconds since epoch
   "broker": int,
   "headers": { "<name>": str, .. }, // optional
   "key": str|json, "payload": str|json,
   "key_error": str, "payload_error": str, //optional
   "key_schema_id": int, "value_schema_id": int //optional
 }
 notes:
   - key_error and payload_error are only included if deserialization fails.
   - key_schema_id and value_schema_id are included for successfully deserialized Avro messages.

Consumer mode (writes messages to stdout):
  kcat -b <broker> -t <topic> -p <partition>
 or:
  kcat -C -b ...

High-level KafkaConsumer mode:
  kcat -b <broker> -G <group-id> topic1 top2 ^aregex\d+

Producer mode (reads messages from stdin):
  ... | kcat -b <broker> -t <topic> -p <partition>
 or:
  kcat -P -b ...

Metadata listing:
  kcat -L -b <broker> [-t <topic>]

Query offset by timestamp:
  kcat -Q -b broker -t <topic>:<partition>:<timestamp>
```

### Consuming messages using `kcat`

All examples below use `kcat`. Replace with `kafkacat` if you are on a pre-1.7 installation.

The simplest invocation consumes all messages from the beginning of the topic:

```bash
kcat -b dataplatform:9092 -t test-topic
```

To start at the end of the topic and only receive new messages, use the `-o end` option:

```bash
kcat -b dataplatform:9092 -t test-topic -o end
```

To show only the last message per partition, set `-o -1`. `-o -2` would show the last two per partition:

```bash
kcat -b dataplatform:9092 -t test-topic -o -1
```

To show only the last message from a single partition, add the `-p` option:

```bash
kcat -b dataplatform:9092 -t test-topic -p1 -o -1
```

Use the `-f` format string to print the partition, key, and value alongside each message:

```bash
kcat -b dataplatform:9092 -t test-topic -f 'Part-%p => %k:%s\n'
```

> **What you should see:** Each message printed as `Part-3 => :aaa`, showing the source partition. Messages from the same partition appear in offset order; messages from different partitions are interleaved in the order they were fetched.

> **What just happened?** Unlike `kafka-console-consumer`, `kcat` is a lightweight native client that connects directly to the broker without Java consumer group overhead. The `-f` format string is evaluated per message and gives you full control over what metadata is printed — useful for debugging partition routing and key distribution.

To display `null` keys explicitly, add the `-Z` flag:

```bash
kcat -b dataplatform:9092 -t test-topic -f 'Part-%p => %k:%s\n' -Z
```

To emit each message as a JSON envelope, use `-J`:

```bash
kcat -b dataplatform:9092 -t test-topic -J
```

### Producing messages using `kcat`

Switch to producer mode with the `-P` flag:

```bash
kcat -b dataplatform:9092 -t test-topic -P
```

To produce messages with a key, use `-K` to specify the key/value delimiter:

```bash
kcat -b dataplatform:9092 -t test-topic -P -K , -X topic.partitioner=murmur2_random
```

Find more examples on the [kcat GitHub project](https://github.com/edenhill/kcat) or in the [Confluent Documentation](https://docs.confluent.io/current/app-development/kafkacat-usage.html).

### Send realistic test messages to Kafka using Mockaroo and `kcat`

In his [blog article](https://rmoff.net/2018/05/10/quick-n-easy-population-of-realistic-test-data-into-kafka-with-mockaroo-and-kafkacat/) Robin Moffatt demonstrates how to combine [Mockaroo](https://mockaroo.com/) — a free test data generator — with `kcat` to produce realistic mock messages with a single command.

The following example sends 20 simulated orders to `test-topic`. This requires a locally installed `kcat`; the containerised version will not work here because it cannot reach the Mockaroo API from inside Docker.

```bash
curl -s "https://api.mockaroo.com/api/d5a195e0?count=20&key=ff7856d0" | kcat -b dataplatform:9092 -t test-topic -P
```

## Publishing a "real" data stream to Kafka

Next we will see a more realistic example using the [Streaming Synthetic Sales Data Simulator](https://github.com/TrivadisPF/various-bigdata-prototypes/tree/master/streaming-sources/sales-simulator), available as a [Docker image](https://hub.docker.com/repository/docker/trivadis/sales-simulator).

This moves us beyond manually typed messages and lets us see how Kafka handles a continuous, unbounded stream of data.

First, create the three topics the simulator will publish to:

```bash
docker exec -ti kafka-1 kafka-topics --create \
    --bootstrap-server kafka-1:19092 \
    --topic demo.products \
    --replication-factor 3 --partitions 6 \
    --config cleanup.policy=compact \
    --config segment.ms=100 \
    --config delete.retention.ms=100 \
    --config min.cleanable.dirty.ratio=0.001 \
    --if-not-exists

docker exec -ti kafka-1 kafka-topics --create \
    --bootstrap-server kafka-1:19092 \
    --topic demo.purchases \
    --replication-factor 3 --partitions 6 \
    --if-not-exists

docker exec -ti kafka-1 kafka-topics --create \
    --bootstrap-server kafka-1:19092 \
    --topic demo.inventories \
    --replication-factor 3 --partitions 6 \
    --if-not-exists
```

`demo.purchases` and `demo.inventories` use the default 7-day time-based retention. `demo.products` uses log compaction with aggressive settings (`segment.ms=100`, `min.cleanable.dirty.ratio=0.001`) to compact quickly for demo purposes — see the [Retention and Log Compaction](#retention-and-log-compaction) section for details.

The simulator container must join the same Docker network as the Kafka cluster. List available networks with:

```bash
docker network list
```

For this workshop environment the network is `kafka-workshop`. Start the simulator with:

```bash
docker run -ti --rm --network kafka-workshop \
    -e KAFKA_BOOTSTRAP_SERVERS=kafka-1:19092,kafka-2:19093 \
    trivadis/sales-simulator:latest
```

Because the container joins the broker's network, it can address brokers by service name (`kafka-1`) and internal port (`19092`).

Alternatively, if you want to run the simulator locally against a remote Docker stack, use the `dataplatform` alias and the external ports:

```bash
docker run -ti --rm \
    -e KAFKA_BOOTSTRAP_SERVERS=dataplatform:9092,dataplatform:9093 \
    trivadis/sales-simulator:latest
```

Use `kcat` to watch data streaming into the `demo.purchases` topic:

```bash
kcat -b dataplatform:9092 -t demo.purchases -q -f 'Part-%p => %k:%s\n'
```

You can also use the **Live Tail** option of **AKHQ** (see the [Using AKHQ](#using-akhq) section below).

## Retention and Log Compaction

Kafka provides two strategies for controlling how long data is kept in a topic:

- **Time-based / size-based retention** (default) — messages are deleted after a configurable time period (default: 7 days) or when the total log size exceeds a limit. This is the right model for event streams where you only need a recent window.
- **Log compaction** — Kafka keeps only the **latest message per key**, discarding older records with the same key. The compacted topic always contains a full snapshot of the current state for every key. This is the right model for change-log or lookup data (e.g., a product catalogue).

### Viewing and changing retention on a topic

Use `kafka-configs` to inspect the current configuration of a topic:

```bash
kafka-configs --bootstrap-server kafka-1:19092 \
              --entity-type topics \
              --entity-name test-topic \
              --describe
```

> **What you should see:** All topic-level configuration overrides. On a freshly created topic with no overrides, the output will read `Default configs for topic test-topic are:` followed by an empty list, meaning all values inherit the broker defaults.

> **What just happened?** `kafka-configs --describe` reads the dynamic configuration entries stored in Kafka's internal metadata for the given topic. These overrides take precedence over the broker-wide defaults in `server.properties`, letting you tune individual topics without restarting or touching the broker configuration.

To change the retention time to 1 hour (3,600,000 ms) on an existing topic:

```bash
kafka-configs --bootstrap-server kafka-1:19092 \
              --entity-type topics \
              --entity-name test-topic \
              --alter \
              --add-config retention.ms=3600000
```

> **What just happened?** Kafka wrote the `retention.ms=3600000` override into its internal configuration store. The change takes effect immediately — the log cleaner enforces the new limit on the next cleanup cycle. No broker restart is required.

To remove the override and fall back to the broker default:

```bash
kafka-configs --bootstrap-server kafka-1:19092 \
              --entity-type topics \
              --entity-name test-topic \
              --alter \
              --delete-config retention.ms
```

### Demonstrating log compaction

Create a dedicated topic with log compaction enabled and aggressive settings so the effect is visible within seconds:

```bash
kafka-topics --create \
             --if-not-exists \
             --bootstrap-server kafka-1:19092 \
             --topic compaction-test \
             --partitions 1 \
             --replication-factor 1 \
             --config cleanup.policy=compact \
             --config segment.ms=100 \
             --config delete.retention.ms=100 \
             --config min.cleanable.dirty.ratio=0.001
```

Start the producer with key parsing enabled:

```bash
kafka-console-producer --bootstrap-server kafka-1:19092 \
                       --topic compaction-test \
                       --property parse.key=true \
                       --property key.separator=:
```

Enter the following messages one by one, pressing **Enter** after each line. Notice that `user-1` is updated three times and `user-2` is updated twice:

```
user-1:{"name":"Alice","city":"Zurich"}
user-2:{"name":"Bob","city":"London"}
user-1:{"name":"Alice","city":"Bern"}
user-3:{"name":"Charlie","city":"Paris"}
user-2:{"name":"Bob","city":"Amsterdam"}
user-1:{"name":"Alice","city":"Basel"}
```

Stop the producer with **Ctrl-C**.

Consume all messages immediately — compaction has not run yet, so all 6 records are visible:

```bash
kafka-console-consumer --bootstrap-server kafka-1:19092 \
                       --topic compaction-test \
                       --property print.key=true \
                       --property key.separator=: \
                       --from-beginning \
                       --timeout-ms 5000
```

> **What you should see:** All 6 messages in the order they were written, including the intermediate values for `user-1` (Zurich, Bern) and `user-2` (London).

> **What just happened?** Compaction has not run yet. The log still contains all original segments, so consuming `--from-beginning` returns every offset in order.

Wait a few seconds, then consume again:

```bash
kafka-console-consumer --bootstrap-server kafka-1:19092 \
                       --topic compaction-test \
                       --property print.key=true \
                       --property key.separator=: \
                       --from-beginning \
                       --timeout-ms 5000
```

> **What you should see:** Only the latest value for each key — one record each for `user-1` (Basel), `user-2` (Amsterdam), and `user-3` (Paris). The earlier values for `user-1` and `user-2` have been removed by the compactor.

> **What just happened?** Kafka's **log cleaner** thread scanned the log segments and built an offset map of the highest offset seen for each key. It then rewrote the segments, keeping only the message at the highest offset per key and discarding all earlier duplicates. The aggressive settings (`segment.ms=100`, `min.cleanable.dirty.ratio=0.001`) forced this to happen within a few seconds rather than the hours it would take with production defaults.

This is exactly the behaviour used by the `demo.products` topic created in the previous section — it stores the current state of every product, and compaction ensures the topic never grows unboundedly even though products are updated continuously.

## Using AKHQ

[AKHQ](https://akhq.io/) is an open-source web UI for managing Kafka topics, consumer groups, the schema registry, connectors, and more. It runs as part of the **Data Platform** and is accessible at <http://dataplatform:28107/>.

By default you will land on the topics overview page.

![Alt Image Text](./images/akhq-homepage.png "AKHQ Homepage")

Navigate to **Nodes** in the left menu to see the Kafka cluster and its 3 brokers.

![Alt Image Text](./images/akhq-nodes.png "AKHQ Nodes")

Click on **Topics** in the menu to return to the topics view.

By default only user-created topics are shown. Select **Show all topics** from the dropdown to also display internal topics such as `__consumer_offsets`.

![Alt Image Text](./images/akhq-topics-all.png "AKHQ All Topics")

To browse the messages stored in a topic, click the **magnifying glass** icon on the right side of any topic row.

![Alt Image Text](./images/akhq-topics-details.png "AKHQ Topic Details")

> **What you should see:** The first page of messages for that topic, displayed in a table with offset, partition, timestamp, key, and value columns.

![Alt Image Text](./images/akhq-topics-details1.png "AKHQ Topic Messages")

To watch live data arriving in a topic, navigate to **Live Tail** in the left menu. If the sales simulator is no longer running, restart it first.

Select one or more topics to tail:

![Alt Image Text](./images/akhq-live-tail.png "AKHQ Live Tail")

Click the **magnifying glass** icon to start the live tail — messages will appear as they arrive.

![Alt Image Text](./images/akhq-live-tail2.png "AKHQ Live Tail Running")

To empty a topic, click its **magnifying glass** icon on the Topics page and then click **Empty Topic**.

![Alt Image Text](./images/akhq-empty-topic.png "AKHQ Empty Topic")

AKHQ also supports copying data between topics (**Copy Topic**) and producing individual test messages (**Produce to topic**). The left menu provides access to the **Schema Registry**, Kafka Connect clusters, and ksqlDB clusters.
