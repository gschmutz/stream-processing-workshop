# Kafka Connect RSS 

Kafka Connect RSS and Atom Source Connector.

[![Build Status](https://travis-ci.com/kaliy/kafka-connect-rss.svg?branch=master)](https://travis-ci.com/kaliy/kafka-connect-rss)
[![codecov](https://codecov.io/gh/kaliy/kafka-connect-rss/branch/master/graph/badge.svg)](https://codecov.io/gh/kaliy/kafka-connect-rss)
[![Maven Central](https://maven-badges.herokuapp.com/maven-central/org.kaliy.kafka/kafka-connect-rss/badge.svg)](https://maven-badges.herokuapp.com/maven-central/org.kaliy.kafka/kafka-connect-rss)
[![Known Vulnerabilities](https://snyk.io/test/github/kaliy/daily-coding-problem/badge.svg?targetFile=pom.xml)](https://snyk.io/test/github/kaliy/kafka-connect-rss?targetFile=pom.xml)

## Configuration

Connector supports polling multiple URLs and sending output to a single topic. Sample configuration file can be found in the repository [here](https://github.com/kaliy/kafka-connect-rss/blob/master/config/rss-source-connector-sample.properties).

URLs should be percent encoded and separated by space. Tasks will be split evenly, e.g. for 5 URLs and 3 `tasks.max` there will be 3 tasks created with 2, 2 and 1 URLs each. 
If `tasks.max` is higher than provided number of URLs, only the necessary number of tasks will be created with 1 URL each.

Connector has following configuration options:

| Name            | Description                                                        | Type   | Default Value | Importance |
|-----------------|--------------------------------------------------------------------|--------|---------------|------------|
| `rss.urls`      | RSS or Atom feed URLs                                              | string |               | high       |
| `topic`         | Topic to write to                                                  | string |               | high       |
| `sleep.seconds` | Time in seconds that connector will wait until querying feed again | int    | 60            | medium     |

## Output

Message has the following schema:

```json
{
  "schema": {
    "type": "struct",
    "fields": [
      {
        "type": "struct",
        "fields": [
          {
            "type": "string",
            "optional": true,
            "field": "title"
          },
          {
            "type": "string",
            "optional": false,
            "field": "url"
          }
        ],
        "optional": false,
        "name": "org.kaliy.kafka.rss.Feed",
        "version": 1,
        "field": "feed"
      },
      {
        "type": "string",
        "optional": false,
        "field": "title"
      },
      {
        "type": "string",
        "optional": false,
        "field": "id"
      },
      {
        "type": "string",
        "optional": false,
        "field": "link"
      },
      {
        "type": "string",
        "optional": true,
        "field": "content"
      },
      {
        "type": "string",
        "optional": true,
        "field": "author"
      },
      {
        "type": "string",
        "optional": true,
        "field": "date"
      }
    ],
    "optional": false,
    "name": "org.kaliy.kafka.rss.Item",
    "version": 1
  }
}
```

Sample message with JSON converter without embedded schema:
```json
{
  "feed": {
    "title": "CNN.com - RSS Channel - App International Edition",
    "url": "http://rss.cnn.com/rss/edition.rss"
  },
  "title": "The 56,000-mile electric car journey",
  "id": "https://www.cnn.com/2019/03/22/motorsport/electric-car-around-the-world-wiebe-wakker-spt-intl/index.html",
  "link": "https://www.cnn.com/2019/03/22/motorsport/electric-car-around-the-world-wiebe-wakker-spt-intl/index.html",
  "content": "For three years and 90,000 kilometers and counting, he's traveled the world powered both by electricity and strangers' kindness.",
  "author": "CNN",
  "date": "2019-03-22T13:34:17Z"
}
```

## Changelog
* 0.1.0 (2019-03-24): Initial release
* 0.1.1 (2022-11-24):
  * Address known vulnerabilities by upgrading dependencies ([#6](https://github.com/kaliy/kafka-connect-rss/pull/6))
  * Handle Null Pointer Exception in the confluent control center ([#8](https://github.com/kaliy/kafka-connect-rss/pull/8))

## Development

Some development notes can be found [here](https://github.com/kaliy/kafka-connect-rss/blob/master/devnotes.md).

To compile and execute unit and integration tests `mvn verify` command can be used.
