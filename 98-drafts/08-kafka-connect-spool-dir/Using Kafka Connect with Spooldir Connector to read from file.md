# Using Kafka Connect with Spooldir Connector to read from file

```
curl -s http://dataplatform:8083/connector-plugins|jq '.[].class'|egrep 'SpoolDir'
```

```bash
guido.schmutz@AMAXDKFVW0HYY ~/D/G/v/o/docker (main)> curl -s http://dataplatform:8083/connector-plugins|jq '.[].class'|egrep 'SpoolDir'

"com.github.jcustenborder.kafka.connect.spooldir.SpoolDirAvroSourceConnector"
"com.github.jcustenborder.kafka.connect.spooldir.SpoolDirBinaryFileSourceConnector"
"com.github.jcustenborder.kafka.connect.spooldir.SpoolDirCsvSourceConnector"
"com.github.jcustenborder.kafka.connect.spooldir.SpoolDirJsonSourceConnector"
"com.github.jcustenborder.kafka.connect.spooldir.SpoolDirLineDelimitedSourceConnector"
"com.github.jcustenborder.kafka.connect.spooldir.SpoolDirSchemaLessJsonSourceConnector"
"com.github.jcustenborder.kafka.connect.spooldir.elf.SpoolDirELFSourceConnector"
```

```bash
cd $DATAPLATFORM_HOME
mkdir -p data-transfer/file/unprocessed
mkdir -p data-transfer/file/processed
mkdir -p data-transfer/file/error
```

```bash
docker exec -ti kafka-1 kafka-topics --create --bootstrap-server kafka-1:19092 --topic sensor_spooldir_00 --partitions 3 --replication-factor 3
```

Start connector

```bash
curl -i -X PUT -H "Accept:application/json" \
    -H  "Content-Type:application/json" http://dataplatform:8083/connectors/source-csv-spooldir-00/config \
    -d '{
        "connector.class": "com.github.jcustenborder.kafka.connect.spooldir.SpoolDirCsvSourceConnector",
        "topic": "sensor_spooldir_00",
        "input.path": "/data-transfer/file/unprocessed",
        "finished.path": "/data-transfer/file/processed",
        "error.path": "/data-transfer/file/error",
        "input.file.pattern": ".*\\.csv",
        "schema.generation.enabled":"true",
        "csv.first.row.as.header":"true"
        }'
```

Now let's observe our data

```bash
docker exec kcat \
    kcat -b kafka-1:19092 -t orders_spooldir_00 \
             -C -o-1 -J \
             -s key=s -s value=avro -r http://schema-registry-1:8081 | \
             jq '.payload'
```

print Kafka Headers

```bash
docker exec kcat \
    kcat -b kafka-1:19092 -t orders_spooldir_00 \
             -C -o-1 -J \
             -s key=s -s value=avro -r http://schema-registry-1:8081 | \
             jq '.headers'
```

extract header into value field `filename`

```
      "transforms": "extractHeader",
      "transforms.extractHeader.type": "com.github.jcustenborder.kafka.connect.transform.common.HeaderToField$Value",
      "transforms.extractHeader.header.mappings": "file.name.without.extension:STRING:filename",  
```

use regexp extract SMT to extract part of the file name and store it into value field `key`

```
        "transforms.regexpextract.type": "com.github.cjmatta.kafka.connect.transform.RegexpExtract$Value",
        "transforms.regexpextract.source.field.name": "filename",
        "transforms.regexpextract.destination.field.name": "key",
        "transforms.regexpextract.pattern": "^(\\d+)",
        "transforms.regexpextract.occurrence": 1,
```

Use ValueToKey SMT to copy the `key` field into the key

```
        "transforms.toKey.type": "org.apache.kafka.connect.transforms.ValueToKey",
        "transforms.toKey.fields": "key",
```

Use ExtractField SMT to extract the value from the `key` struct

```
        "transforms.extractKeyFromStruct.type"  :"org.apache.kafka.connect.transforms.ExtractField$Key",
        "transforms.extractKeyFromStruct.field" :"key",
```        

Use the ReplaceField SMT to remove the `filename` and `key` fields from the value

```
        "transforms.dropFields.type": "org.apache.kafka.connect.transforms.ReplaceField$Value",
        "transforms.dropFields.blacklist": "filename,key"   
```        

All these together in the connector definition looks as follows

       
```bash       
curl -i -X PUT -H "Accept:application/json" \
    -H  "Content-Type:application/json" http://dataplatform:8083/connectors/source-csv-spooldir-00/config \
    -d '{
        "connector.class": "com.github.jcustenborder.kafka.connect.spooldir.SpoolDirCsvSourceConnector",
        "topic": "sensor_spooldir_00",
        "input.path": "/data-transfer/file/unprocessed",
        "finished.path": "/data-transfer/file/processed",
        "error.path": "/data-transfer/file/error",
        "input.file.pattern": ".*\\.csv",
        "schema.generation.enabled":"true",
        "csv.first.row.as.header":"true",
        "transforms": "extractHeader,regexpextract,toKey,extractKeyFromStruct,dropFields",
        "transforms.extractHeader.type": "com.github.jcustenborder.kafka.connect.transform.common.HeaderToField$Value",
        "transforms.extractHeader.header.mappings": "file.name.without.extension:STRING:filename",  
        "transforms.regexpextract.type": "com.github.cjmatta.kafka.connect.transform.RegexpExtract$Value",
        "transforms.regexpextract.source.field.name": "filename",
        "transforms.regexpextract.destination.field.name": "key",
        "transforms.regexpextract.pattern": "^(\\d+)",
        "transforms.regexpextract.occurrence": 1,
        "transforms.toKey.type": "org.apache.kafka.connect.transforms.ValueToKey",
        "transforms.toKey.fields": "key",
        "transforms.extractKeyFromStruct.type"  :"org.apache.kafka.connect.transforms.ExtractField$Key",
        "transforms.extractKeyFromStruct.field" :"key",
        "transforms.dropFields.type": "org.apache.kafka.connect.transforms.ReplaceField$Value",
        "transforms.dropFields.blacklist": "filename,key"                
        }'
 ```       
      