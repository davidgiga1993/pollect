# pollect - python data collection daemon

pollect is a daemon for collecting system and application metrics in periodical intervals.
(similar to collectd). It's designed to require very little dependencies and to be easily customizable.

# Architecture

```
 ------------                           ----------
 | executor |  -- result of sources --> | writer |
 ------------                           ----------
       1
       | Calls sources to probe data
       n
 ---------------                                   
 |   source    |   
 ---------------
```

pollect uses `executors` which contain `sources` for probing the data. The data is exported using the `collection` name.

For persisting the data `writers` are used. They can be defined globally (for all executors)
or on a per executor level.

By default, the tick time is defined globally, but can be changed on a executor level.

# Usage

```bash
pip install pollect
pollect --config config.yml [--dry-run]
```

Note: You can use either `json` or `yml` files for configuration.

## Docker

Place your `config.[json|yml]` and any custom `sources` into your working directory and run

```bash
docker run -v $(pwd):/pollect -p 8000:8000 davidgiga1993/pollect:latest
```

# Config

Here is an example for collecting the load average every 30 seconds as well as sampling the response time of google
every 2 min and exporting it as prometheus metrics

```yml
---
tickTime: 30
threads: 4
writers:
  - type: Prometheus
    port: 8000
executors:
  - collection: pollect
    # An executor can als have its own writer
    # writer: ...
    sources:
      - type: LoadAvg
    
  - collection: slowerMetrics
    tickTime: 120
    sources:
      - type: Http # See Http below for more details
        url: https://google.com
        labels: # Additional labels/tags for the metrics
          # It is also possible to access env variables anywhere
          # in the config
          system: prod
          home: ${HOME}
```

A more advanced configuration sample can be found in the `pollect.[json|yml]` file.

# Metric names

The metric names are automatically build out of the collection, source and value name. Example:

Pattern: `${collection}_${sourceType}[_${sourceName}][_$valueName}]`

| Collection | Source type | Source name (optional) | Resulting metric name                                            |
|------------|-------------|------------------------|------------------------------------------------------------------|
| pollect    | Http        |                        | pollect_Http                                                     |
| pollect    | Http        | test                   | pollect_Http_test                                                |
| pollect    | Process     |                        | pollect_Process_load_percent <br> pollect_Process_virtual_memory |

# Sources

A source collects data in regular intervals. Depending on the source there are multiple configuration parameters
available.

Certain sources might need additional dependencies.

The following parameters are available for all sources:

| Param  | Desc                        |
|--------|-----------------------------|
| name   | Name of the metric (prefix) |
| labels | Dict of static labels       |

## Http response time `Http`

Measures the http response time in milliseconds

| Param      | Desc                                                                                                                                     |
|------------|------------------------------------------------------------------------------------------------------------------------------------------|
| url        | Url to the web service. Can be a list of strings as well (the url will be added as label)                                                |
| timeout    | Timeout in seconds (default 15)                                                                                                          |
| statusCode | The expected status code (default any non error)                                                                                         |
| proxy      | Http proxy which should be used (defaults to none respecting environment variables. Set to '' to use no proxy regardless of environment) |

## Disk usage `DiskUsage`

Disk usage statistics.

## Load average `LoadAvg`

System load average. Linux only

## Memory usage `MemoryUsage`

System memory usage

## Process stats `Process`

Information about one or more processes

| Param     | Desc                                           |
|-----------|------------------------------------------------|
| name      | Name of the metric                             |
| procRegex | Name of the process(es) - Regex                |
| memory    | True to enable memory metrics (default true)   |
| load      | True to enable cpu load metrics (default true) |

## Interface `Interface`

Collects NIC statistics.

| Param        | Desc                                   |
|--------------|----------------------------------------|
| includeTotal | Enables incremental counter data       |
| include      | Explicitly includes nics. Can be empty |
| exclude      | Excludes nics. Can be empty            |

## IO `IO`

Collects IO statistics.

| Param   | Desc                                    |
|---------|-----------------------------------------|
| include | Explicitly includes disks. Can be empty |
| exclude | Excludes disks. Can be empty            |

## HDD smart data `SmartCtl`

Wrapper for the linux `smartctl` tool. Collects SMART data

| Param      | Desc                                                      |
|------------|-----------------------------------------------------------|
| attributes | Name of smart attributes which should be included         |
| devices    | List of regex for matching disks which should be included |

## Sensors `Sensors`

Wrapper for the linux `sensors` utility. Collects sensor data such as temps and voltages

| Param        | Desc                                                                                         |
|--------------|----------------------------------------------------------------------------------------------|
| include      | Name of chips which should be included. Can be empty                                         |
| exclude      | Name of chips which should be excluded. Can be empty                                         |
| useBaseUnits | Set to `False` to report the raw values in their reported unit (for example mV instead of V) |

## Kubernetes Network Traffic `K8sNamespaceTraffic`

Monitors the per-namespace traffic.

See [Kubernetes Network Insights](docs/K8sNetwork.md) for more details.


## DNS server statistics `Bind`

Bind DNS server statistics.

| Param | Desc                           |
|-------|--------------------------------|
| url   | URL to the bind statistics     |
| views | Views which should be included |

## SNMP `SnmpGet`

Wrapper for the snmpget binary, supports snmp v1 and v3

```yaml
type: SnmpGet
name: Procurve
# Host which should be contacted
host: 10.1.100.1

# v1 only: Community string (public by default)
communityString: public
# v3 section:
snmpVersion: 3 # 1 by default
username: test # Security name
authPassPhrase: ${AUTH_PASS} # authentication protocol pass phrase
authProtocol: SHA # Can be MD5 or SHA (default)
privacyPassPhrase: ${PRIV_PASS} # privacy protocol pass phrase
privacyProtocol: SHA # Can be MD5 or SHA (default)

# Metrics which should be collected
# Each metric can query one or more oids
metrics:
  # Name of the metric
  - name: throughput
    # Processing mode:
    # - undefined (default): No processing
    # - rate: Computes the change per second, compensating for value overflows
    mode: rate
    # OID which should be probed
    oid: iso.3.6.1.2.1.16.1.1.1.4.1

  # It is also possible to define ranges
  - name: interface_link_state
    # The parameter in the oid will be replaced with the range number
    oid: iso.3.6.1.2.1.2.2.1.5.${if}
    range:
      from: 1
      to: 10 # From and to are inclusive
      label: "if" # The label will be attached to the metric

```

## Plex server `Plex`

Collects plex mediaserver statistics. This requires local IP addresses to be allowed without authentication.

| Param | Desc                                                      |
|-------|-----------------------------------------------------------|
| url   | URL to plex. Use the IP of the NIC instead of `localhost` |

## Plex server `Zfs`

Provides simple ZFS pool sizing and performance metrics.

## Fritzbox WAN `Fritzbox`

Connects to the fritzbox api and collects WAN statistics.

## Viessmann API `Viessmann`

Collects sensor data from viessmann heatpumps

| Param    | Desc                          |
|----------|-------------------------------|
| user     | Username of viessmann account |
| password | Password of account           |

These information are only required for the first data collection. Afterwards a `viessmann_token.json` file is created
to cache the oauth credentials.

## Homematic IP `HomematicIp`

Collects temperature and humidity data from homematic IP.

| Param       | Desc            |
|-------------|-----------------|
| authToken   | Auth token      |
| accessPoint | Access point id |

## SMA Energy Meter `SmaEnergyMeter`

Collects data from the SMA Home Manager 2.0. The data is received via multicast from the meter. If this doesn't work for
you, there is also a possibility to configure the meter to unicast the values directly to your machine.

| Param  | Desc                                                                            |
|--------|---------------------------------------------------------------------------------|
| hostIp | The primary IP address of the host running pollect. <br/>Required for multicast |

## SMA PV Modbus `SmaPvModbus`

Collects data from SMA Photovoltaik inverters. Requires tcp modbus to be enabled on the inverted.

Requires the `pymodbus` dependency.

| Param | Desc                                  |
|-------|---------------------------------------|
| host  | IP or hostname of the inverted        |
| port  | Optional: modbus port, 502 by default |

## TP-LINK EAP `TpLinkEap`

Collects wifi statistics of the TP-LINK EAP series devices. This uses the rest api of the device. Note that the devices
only support one session at a time, meaning you will be logged out from the web UI in regular intervals.

| Param    | Desc                |
|----------|---------------------|
| url      | URL to the admin UI |
| user     | Username            |
| password | Password            |

## Openhab `Openhab`

Collects the values of all channels of all items in openhab. This contains more data than the original metrics exporter
of openhab (since it doesn't include all items).

| Param | Desc           |
|-------|----------------|
| url   | URL to openhab |

## Zodiac Pool Cleaner `ZodiacPool`
Provides metrics about the current state and remaining duration of the cleaning
cycle. This source has been tested with the Zodiac Alpha 63 IQ and might 
also work with other Zodiac devices.

| Param    | Desc                |
|----------|---------------------|
| user     | Username            |
| password | Password            |

## Audi MMI `MMI`

Connects to the audi MMI backend and collects data. Note: This pacakge is currently broken due to API changes.

| Param       | Desc                                  |
|-------------|---------------------------------------|
| credentials | Path to the credentials.json          |
| vin         | VIN of the car that should be crawled |

## Google Play Developer Console `Gdc`

Provides app statistics from the google play developer console.

**Important** each fetch will call the google cloud storage api to check for updates so make sure to call is less
frequent (every 30min or so).

Sample config:

```
{
  "type": "Gdc",
  // Name of the bucket - this can be found at the bottom of the bulk export page in the GDC
  "bucketName": "pubsite_prod_rev_1234",
  "apps": [
	{ // All apps for which the statistics should be crawled
	  "package": "my.app.package",
	  "name": "My App"
	}
  ],
  // Key file for the service account which has read access to the GDC
  "keyFile": "api-project-1234.json",
  // Name of the folder where the crawled files should be stored
  "dbDir": "db"
}
```

## Apple appstore connect `AppStoreConnect`

Collects download statistics from apple

```json
{
  "type": "AppStoreConnect",
  "keyId": "ASDH123123",
  "keyFile": "my_api_key.p8",
  "issuerId": "asdasd-123123asd-asd12312-asd",
  "vendorNumber": "882223",
  "dbDir": "db"
}
```

## Http Ingress source `HttpIngress`

This source starts a simple http webserver and where you can post metrics to.
It's intended if you want to push metrics to pollect, instead of using the default pull probes.

```yml
- type: HttpIngress
  name: Ingress
  port: 9005 # Listener port
  metrics: # You can define multiple metrics
    sample_metric: # Name of the metric
      type: counter # Optional, gauge by default, counter will cause the value to increment by X every time
      labels: # Labels for this metric
        - host
```

You can update the metrics using a simple http json post:

```bash
curl -X POST http://pollect:9005 \
-H 'Content-Type: application/json' \
--data-binary @- << EOF
{
    "metrics": {
      "sample_metric": {
        "value": 124
        "labels": {
          "host": "my-hostname"
        }
      }
    }
}
EOF
```

## Certificate source `Certificate`

Returns the expiry date of a https certificate. Requires `openssl` binary and `pyOpenSSL`.

```yml
- type: Certificate
  name: cert
  url: https://google.com
```

## EVCC `Evcc`

Exposes the values shown in the EVCC web-ui as metrics.

| Param |     | Desc                                                       |
|-------|:----|------------------------------------------------------------|
| host  |     | Host and port of the EVCC instance (e.g. `localhost:7070`) |


## PMCC source `Pmcc`

Exports metrics of the "Porsche Mobile Charge Connect" device such as state of charge and charge rate.

```yml
- type: Pmcc
  host: "iccpd-..."
```

# Writers

A writer represents the destination where the collected data is written to.

## Dry run `DryRun`

Prints the collected data to the stdout

## Prometheus http exporter `Prometheus`

Exports the data via a prometheus endpoint. The port can be configured using
`port`as configuration:

```yaml
writers:
  - type: Prometheus
    port: 9001
```

### Https support `PrometheusSsl`

Pollect has a custom prometheus exporter which supports https.

```yaml
writers:
  - type: PrometheusSsl
    port: 8000
    key: key.key
    cert: cert.pem
```

## Otel http exporter `Otel`

Exports/Sends the data via OTLP (OpenTelemetry Protocol) over HTTP to a collector.

```yaml
writers:
  - type: Otel
```

You can use the common otel environment variables to configure the exporter.

```bash
export OTEL_EXPORTER_OTLP_HEADERS='Authorization=Basic xxx=='
export OTEL_EXPORTER_OTLP_METRICS_ENDPOINT='http://localhost:4318/v1/metrics'
```

## MQTT `Mqtt`

Exports metrics to an MQTT broker:

```yaml
writers:
  - type: Mqtt
    host: 127.0.0.1
    port: 1883
    user: mqtt
    password: password
    # Define which metrics should be sent via mqtt
    # If no patterns are defined, all metrics will be sent
    includePattern:
      - "pollect\\.esphome/temperature.+"
      - "pollect\\.smaenergymeter/wirkleistung_.+/phase/0"
      - "pollect\\.smapvmodbus/.+"
```

# Dependency Management

By default pollect requires minimal dependencies to keep the package lightweight.
Certain sources require additional packages to be installed to work correctly.

For this pollect provides a command to print all required additional dependencies for a given configuration:

```bash
pollect --config config.yml --dependencies
```
This will print the dependencies in the `requirements.txt` format.

# Multithreading

By default, pollect executes all sources of a collection in parallel with 5 threads.
Different collections are executed in separate threads as well, meaning that multiple long-running probes in one
collection can't block another collection.
If the writer supports partial writes (for example `prometheus`) the result of each source will be immediately
available.
Writers which do not support partial writes will receive the data once all probes have completed.

# Extensions

This example shows how to add your own sources to pollect

## Source

extensions/SingleRandom.py:

```python
# Single random value with parameter
class SingleRandomSource(Source):
    def __init__(self, data):
        super().__init__(data)
        self.max = data.get('max')

    def _probe(self):
        return random() * self.max

```

extensions/MultiRandomSource.py:

```python
# Multiple random values
class MultiRandomSource(Source):
    def _probe(self):
        return {'a': random(), 'b': random()}
```

config.yml:

```yaml
tickTime: 30
threads: 4
writers:
  - type: Prometheus
    port: 8000
executors:
  - collection: example
    sources:
      - type: "extensions.SingleRandom",
        max: 100
      - type: "extensions.MultiRandom"
}
```

A similar principle is used for the writers. Take a look at the `sources`and `writers` folders for more examples.