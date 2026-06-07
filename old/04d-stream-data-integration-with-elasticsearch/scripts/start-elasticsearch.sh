#!/bin/bash

echo "removing Elasticsarch Sink Connectors"

curl -X "DELETE" "$DOCKER_HOST_IP:28013/connectors/sink-es-tweets"

echo "creating Elasticsearch Sink Connector"

curl -X "POST" "$DOCKER_HOST_IP:28013/connectors" \
     -H "Content-Type: application/json" \
     --data '{
  "name": "sink-es-tweets",
  "config": {
    "connector.class" : "io.confluent.connect.elasticsearch.ElasticsearchSinkConnector",
    "tasks.max": "1",
    "topics" : "tweet-json-topic",
    "topic.index.map" : "tweet-json-topic:tweet-index",
    "connection.url" : "http://elasticsearch:9200",
    "key.ignore" : "true",
    "type.name" : "tweets",
    "schema.ignore" : "true",
    "key.converter" : "org.apache.kafka.connect.storage.StringConverter",
    "value.converter" : "org.apache.kafka.connect.json.JsonConverter",
    "value.converter.schemas.enable": "false"
    }
  }'



curl -X "POST" "$DOCKER_HOST_IP:28013/connectors" \
     -H "Content-Type: application/json" \
     --data '{
  "name": "sink-es-tweets",
  "config": {
    "connector.class" : "io.confluent.connect.elasticsearch.ElasticsearchSinkConnector",
    "tasks.max": "1",
    "topics" : "tweet-raw-v1",
    "topic.index.map" : "tweet-raw-v1:tweet-raw-v1-index",
    "connection.url" : "http://elasticsearch:9200",
    "key.ignore" : "true",
    "type.name" : "_doc",
    "schema.ignore" : "false",
    "key.converter" : "org.apache.kafka.connect.storage.StringConverter"
    }
  }'

