# Kubernetes Network Insights

This source uses the eBPF kernel module to collect network traffic statistics and
groups the traffic by kubernetes namespace and known destination networks.

## Requirements

Requires the following packages:

- `bcc` or `amazon-linux-extras install BCC` for AWS EC2 instances.

Additional requirements:
- containerd

## Example
The following configuration groups the traffic by kubernetes namespace
 and separates the traffic by "local" and "other" traffic. 
```yaml
type: K8sNamespaceTraffic
name: host
networks: # List of known destination networks to which to group the traffic by (in addition to the namespace names)
  - name: "local"
    cidrs: [ "192.168.1.0/24" ]
# All traffic not matching any network will be labeled with "other"

# Optional: Defines the label name to use for the exported metrics k8s namespaces
# namespaceLabel: 'namespace'

# Optional: When true logs all packets which do not match any of the known networks
# logUnknownTraffic: False
```

Example output:
```
{dest_network="local", direction="sent", namespace="kube-system"} 10
{dest_network="local", direction="received", namespace="kube-system"} 10
{dest_network="other", direction="received", namespace="kube-system"} 3254
{dest_network="other", direction="sent", namespace="kube-system"} 951
```


The metric unit is in bytes.

## Setup
As this module uses eBPF it requires elevated privileges.
When running from a container make sure to run the process in the host namespace,
for example using 
```
nsenter --target 1 --uts --ipc --pid --mount -- python3 /app/pollect/pollect.py --config /etc/pollect/config.yml`
```