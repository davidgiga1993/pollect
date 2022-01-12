# pollect - python data collection daemon

pollect is a daemon for collecting system and application metrics in periodical intervals.
(similar to collectd). It's designed to require very little dependencies to run.


# Architecture

pollect uses `executors` which contain `sources` for probing the data. The data is exported using the `collection` name.

For persisting the data `writers` are used. They can be defined globally (for all executors)
or on a per executor level.

By default the tick time is defined globally, but can be changed on a executor level.

# Usage

```bash
pip install pollect
pollect --config config.json [--dry-run]
```

## Docker
Place your `config.json` and any custom `sources` into your working directory and run
```bash
docker run -v $(pwd):/pollect -p 8000:8000 davidgiga1993/pollect:latest
```


# Config

Here is an example for collecting the load average every 30 seconds as well as sampling the response time of google
every 2 min and exporting it as prometheus metrics

```json
{
  "tickTime": 30,
  "writer": {
	"type": "Prometheus",
	"port": 8000
  },
  "executors": [
	{
	  "collection": "pollect",
	  "sources": [
		{
		  "type": "LoadAvg"
		}
	  ]
	},
	{
	  "collection": "slowerMetrics",
	  "tickTime": 120,
	  "sources": [
		{
		  "type": "Http",
		  "url": "https://google.com"
		}
	  ]
	}
  ]
}
```

A more advanced configuration sample can be found in the `pollect.json` file.

# Sources

A source collects data in regular intervals. Depending on the source there are multiple configuration parameters
available.

Certain sources might need additional dependencies.

The following parameters are available for all sources:

| Param | Desc |
| --- | --- |
| name | Name of the metric (prefix) |

## Http response time `Http`

Measures the http response time

| Param | Desc |
| --- | --- |
| url | Url to the web service |
| timeout | Timeout in seconds (default 15) |

## Disk usage `DiskUsage`

Disk usage statistics. Requires `shutil` package

## Load average `LoadAvg`

System load average. Linux only

## Memory usage `MemoryUsage`

System memory usage. Requires `psutil` package

## Process stats `Process`

Information about one or more processes

| Param | Desc |
| --- | --- |
| name | Name of the metric |
| procRegex| Name of the process(es) - Regex |
| memory | True to enable memory metrics (default true) |
| load| True to enable cpu load metrics (default true)  |

## Interface `Interface`

Collects NIC statistics. Requires `psutil` package

| Param | Desc |
| --- | --- |
| includeTotal | Enables incremental counter data |
| include | Explicitly includes nics. Can be empty |
| exclude | Excludes nics. Can be empty |

## IO `IO`

Collects IO statistics. Requires `psutil` package

| Param | Desc |
| --- | --- |
| include | Explicitly includes disks. Can be empty |
| exclude | Excludes disks. Can be empty |

## HDD smart data `SmartCtl`

Wrapper for the linux `smartctl` tool. Collects SMART data

| Param | Desc |
| --- | --- |
| attributes | Name of smart attributes which should be included |
| devices | List of regex for matching disks which should be included |

## Sensors `Sensors`

Wrapper for the linux `sensors` utility. Collects sensor data such as temps and voltages

| Param | Desc |
| --- | --- |
| include | Name of chips which should be included. Can be empty |
| exclude | Name of chips which should be excluded. Can be empty |

## DNS server statistics `Bind`

Bind DNS server statistics.

| Param | Desc |
| --- | --- |
| url | URL to the bind statistics |
| views | Views which should be included |

## SNMP `SnmpGet`

Wrapper for the snmpget binary.

```
{
	"type": "SnmpGet",
	"name": "Procurve",
	// Host which should be contacted
	"host": "10.1.100.1",
	// Community string (public by default)
	"communityString": "public",
	// Metrics which should be collected
	// Each metric can query one or more oids
	"metrics": [{ 
		// If multiple oids are given they will be summed
		"oids": ["iso.3.6.1.2.1.16.1.1.1.4.1"] ,
		// Name of the metric
		"name": "throughput", 
		// Defines how the value should be processed: raw -> No further processing, rate -> change per second
		"mode": "rate"
	}]
}
```

## Plex server `Plex`

Collects plex mediaserver statistics. This requires local IP addresses to be allowed without authentication.

| Param | Desc |
| --- | --- |
| url | URL to plex. Use the IP of the NIC instead of `localhost` |

## Fritzbox WAN `Fritzbox`

Connects to the fritzbox api and collects WAN statistics. Requires
the [fritzconnection](https://pypi.org/project/fritzconnection) package.

## Viessmann API `Viessmann`

Collects sensor data from viessmann heatpumps

| Param | Desc |
| --- | --- |
| user | Username of viessmann account |
| password | Password of account |

These information are only required for the first data collection. Afterwards a `viessmann_token.json` file is created
to cache the oauth credentials.

## Homematic IP `HomematicIp`

Collects temperature and humidity data from homematic IP. Requires
the [homematicip](https://homematicip-rest-api.readthedocs.io/en/latest/gettingstarted.html#installation) package.

| Param | Desc |
| --- | --- |
| authToken | Auth token |
| accessPoint | Access point id |

## TP-LINK EAP `TpLinkEap`

Collects wifi statistics of the TP-LINK EAP series devices.
This uses the rest api of the device.
Note that the devices only support one session at a time, meaning you will be logged out from the
web UI in regular intervals.

| Param | Desc |
| --- | --- |
| url | URL to the admin UI |
| user | Username  |
| password | Password |


## Openhab `Openhab`

Collects the values of all channels of all items in openhab.
This contains more data than the original metrics exporter of openhab (since it doesn't include all items). 

| Param | Desc |
| --- | --- |
| url | URL to openhab |

## Audi MMI `MMI`

Connects to the audi MMI backend and collects data. Requires the [audi api](https://github.com/davidgiga1993/AudiAPI)
package. Note: This pacakge is currently broken due to API changes.

| Param | Desc |
| --- | --- |
| credentials | Path to the credentials.json |
| vin | VIN of the car that should be crawled |

## Google Play Developer Console `Gdc`

Provides app statistics from the google play developer console. Requires the google-cloud-storage package.

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

# Writers

A writer represents the destination where the collected data is written to.

## Dry run `DryRun`

Prints the collected data to the stdout

## Graphite `Graphite`

Sends data in the pickle format to graphite. Make sure to define the correct pickle port.

## Prometheus http exporter `Prometheus`

Exports the data via a prometheus endpoint. The port can be configured using
`port`as configuration:

```
"writer": {
    "type": "Prometheus",
    "port": 9001
}
```

# Extensions

This example shows how to add your own collectors

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

config.json:

```json
"sources": [
{
"type": "extensions.SingleRandom",
"max": 100
},
{
"type": "extensions.MultiRandom"
}
]
```

A similar principle is used for the writers. Take a look at the `sources`and `writers` folders for more examples.
