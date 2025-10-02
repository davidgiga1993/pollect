from __future__ import annotations

import ipaddress
import os
import re
import subprocess
import json
from typing import Optional, List, NamedTuple, Dict, Callable

from pollect.core.ValueSet import ValueSet, Value
from pollect.sources.Source import Source
from pollect.sources.helper.NetworkStats import NamedNetworks, ContainerNetworkUtils, NetworkMetrics


class K8sNamespaceTrafficFallbackSource(Source):
    """
    Fallback K8sNamespaceTrafficSource that works without BPF compilation.
    
    This version uses /proc/net/tcp* for connection monitoring combined with
    container runtime information for namespace mapping. It provides true
    namespace-separated traffic monitoring without requiring BPF.
    
    Works with both containerd (via ctr) and CRI-O (via crictl).
    """

    def __init__(self, config):
        super().__init__(config)
        self._namespace_label = config.get('namespaceLabel', 'namespace')
        self._traffic_log_mode = config.get('trafficLog')
        self._debug_namespace_detection = config.get('debugNamespaceDetection', True)
        hide_localhost_traffic = config.get('hideLocalhostTraffic', True)

        self.known_networks: List[NamedNetworks] = []
        for network in config.get('networks', []):
            name = network['name']
            self.known_networks.append(NamedNetworks(name, network['cidrs']))

        # Add catch-any as last item
        self.known_networks.append(NamedNetworks('localhost', ['127.0.0.0/8'], hide=hide_localhost_traffic))
        self.known_networks.append(NamedNetworks('other', ['0.0.0.0/0'], catch_all=True))
        
        self._metrics = NamespacesMetrics(self.known_networks)
        self._previous_connections: Dict[str, int] = {}
        self._runtime_type = None
        self._namespace_ips: Dict[str, set] = {}

    def setup_source(self, global_conf):
        """Setup enhanced monitoring - no BPF compilation needed"""
        self.log.info("Using fallback network monitoring (no BPF required)")
        
        # Detect container runtime
        self._runtime_type = self._detect_container_runtime()
        self.log.info(f"Detected container runtime: {self._runtime_type}")
        
        if self._runtime_type == "none":
            self.log.warning("No container runtime detected - namespace separation may be limited")
        
        # Test namespace detection immediately
        test_namespaces = self._get_enhanced_namespace_ips()
        if test_namespaces:
            self.log.info(f"Successfully detected {len(test_namespaces)} K8s namespaces: {list(test_namespaces.keys())}")
        else:
            self.log.error(f"Failed to detect any K8s namespaces using {self._runtime_type} - you will see generic network names instead")
        
        # Test access to required files
        required_files = ['/proc/net/tcp', '/proc/net/tcp6']
        for file_path in required_files:
            if not os.path.exists(file_path):
                raise Exception(f"Required file {file_path} not accessible")
        
        self.log.info("Fallback network monitoring initialized successfully")

    def _detect_container_runtime(self) -> str:
        """Detect which container runtime is available"""
        
        # Try containerd (most common in K8s)
        try:
            result = subprocess.run(['ctr', '--version'], 
                                  capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                # Test if we can actually list containers
                result = subprocess.run(['ctr', '-n', 'k8s.io', 'containers', 'list', '-q'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    return "containerd"
        except:
            pass
        
        # Try crictl (CRI-compatible)
        try:
            result = subprocess.run(['crictl', '--version'], 
                                  capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                # Test if we can actually list containers
                result = subprocess.run(['crictl', 'ps', '-q'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    return "crictl"
        except:
            pass
        
        # Try kubectl (as a fallback)
        try:
            result = subprocess.run(['kubectl', 'version', '--client'], 
                                  capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                return "kubectl"
        except:
            pass
        
        return "none"

    def _get_enhanced_namespace_ips(self) -> Dict[str, set]:
        """Get namespace IP mappings using available container runtime"""
        
        if self._runtime_type == "containerd":
            return self._get_namespace_ips_containerd()
        elif self._runtime_type == "crictl":
            return self._get_namespace_ips_crictl()
        elif self._runtime_type == "kubectl":
            return self._get_namespace_ips_kubectl()
        else:
            return {}

    def _get_namespace_ips_containerd(self) -> Dict[str, set]:
        """Get namespace IPs using containerd (ctr command)"""
        try:
            # Use the existing ContainerNetworkUtils but with error handling
            result = ContainerNetworkUtils.get_namespace_ips()
            self.log.debug(f"containerd: got {len(result)} namespaces")
            return result
        except Exception as e:
            self.log.warning(f"containerd method failed: {e}")
            return {}

    def _get_namespace_ips_crictl(self) -> Dict[str, set]:
        """Get namespace IPs using crictl"""
        namespace_ips = {}
        
        try:
            # List all containers
            result = subprocess.run(['crictl', 'ps', '-q'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                return {}
            
            container_ids = result.stdout.strip().split('\n') if result.stdout.strip() else []
            
            for container_id in container_ids:
                try:
                    # Get container info
                    result = subprocess.run(['crictl', 'inspect', container_id], 
                                          capture_output=True, text=True, timeout=5)
                    if result.returncode != 0:
                        continue
                    
                    data = json.loads(result.stdout)
                    
                    # Extract namespace and IP
                    labels = data.get('status', {}).get('labels', {})
                    namespace = labels.get('io.kubernetes.pod.namespace', '')
                    
                    if namespace:
                        # Get network info
                        network_info = data.get('status', {}).get('network', {})
                        ip = network_info.get('ip', '')
                        
                        if ip:
                            if namespace not in namespace_ips:
                                namespace_ips[namespace] = set()
                            namespace_ips[namespace].add(f"{ip}/32")
                
                except Exception as e:
                    self.log.debug(f"Error processing container {container_id}: {e}")
                    continue
            
            self.log.debug(f"crictl: processed {len(container_ids)} containers, got {len(namespace_ips)} namespaces")
            return namespace_ips
            
        except Exception as e:
            self.log.warning(f"crictl method failed: {e}")
            return {}

    def _get_namespace_ips_kubectl(self) -> Dict[str, set]:
        """Get namespace IPs using kubectl"""
        namespace_ips = {}
        
        try:
            # Get all pods with their IPs
            result = subprocess.run(['kubectl', 'get', 'pods', '-A', '-o', 
                                   'jsonpath={range .items[*]}{.metadata.namespace}{" "}{.status.podIP}{"\n"}{end}'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                self.log.warning(f"kubectl get pods failed: {result.stderr}")
                return {}
            
            lines_processed = 0
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        namespace, ip = parts[0], parts[1]
                        if namespace and ip and ip != '<none>' and ip != 'None':
                            if namespace not in namespace_ips:
                                namespace_ips[namespace] = set()
                            namespace_ips[namespace].add(f"{ip}/32")
                            lines_processed += 1
            
            self.log.debug(f"kubectl: processed {lines_processed} pod IPs across {len(namespace_ips)} namespaces")
            return namespace_ips
            
        except Exception as e:
            self.log.warning(f"kubectl method failed: {e}")
            return {}

    def _read_namespace_connections(self) -> List[Dict]:
        """Read network connections from individual namespace network interfaces"""
        all_connections = []
        
        # Since we're running in host network namespace with nsenter,
        # we need to look at per-namespace network statistics differently
        
        # First, try to get connections from container processes
        for namespace, ips in self._namespace_ips.items():
            namespace_connections = self._get_namespace_network_stats(namespace, ips)
            all_connections.extend(namespace_connections)
        
        # Also read host connections for comparison
        host_connections = self._read_host_tcp_connections()
        
        if self._debug_namespace_detection:
            self.log.info(f"Found {len(all_connections)} namespace connections and {len(host_connections)} host connections")
        
        # For now, let's focus on interface-based statistics rather than connection parsing
        # since nsenter makes connection parsing less reliable
        return all_connections

    def _get_namespace_network_stats(self, namespace: str, ips: set) -> List[Dict]:
        """Get network statistics for a specific namespace using interface stats"""
        connections = []
        
        try:
            # Get containers in this namespace
            containers = self._get_containers_in_namespace(namespace)
            
            for container_info in containers:
                # Try to get network interface statistics for this container
                net_stats = self._get_container_network_stats(container_info)
                if net_stats:
                    # Convert interface stats to connection-like objects for processing
                    for ip in ips:
                        ip_addr = ip.split('/')[0]
                        connections.extend(self._convert_stats_to_connections(namespace, ip_addr, net_stats))
        
        except Exception as e:
            self.log.debug(f"Error getting namespace {namespace} network stats: {e}")
        
        return connections

    def _get_containers_in_namespace(self, namespace: str) -> List[Dict]:
        """Get container information for a specific namespace"""
        containers = []
        
        try:
            if self._runtime_type == "containerd":
                # Get containers using ctr
                result = subprocess.run(['ctr', '-n', 'k8s.io', 'containers', 'list', '-q'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    container_ids = result.stdout.strip().split('\n') if result.stdout.strip() else []
                    
                    for container_id in container_ids:
                        try:
                            # Get container labels to check namespace
                            result = subprocess.run(['ctr', '-n', 'k8s.io', 'containers', 'info', container_id], 
                                                  capture_output=True, text=True, timeout=3)
                            if result.returncode == 0:
                                data = json.loads(result.stdout)
                                labels = data.get('Labels', {})
                                if labels.get('io.kubernetes.pod.namespace') == namespace:
                                    containers.append({
                                        'id': container_id,
                                        'namespace': namespace,
                                        'labels': labels
                                    })
                        except:
                            continue
                            
        except Exception as e:
            self.log.debug(f"Error listing containers for namespace {namespace}: {e}")
        
        return containers

    def _get_container_network_stats(self, container_info: Dict) -> Dict:
        """Get network statistics for a specific container"""
        try:
            # Try to get the container's PID to access its network namespace
            container_id = container_info['id']
            
            if self._runtime_type == "containerd":
                # Get container task info to find PID
                result = subprocess.run(['ctr', '-n', 'k8s.io', 'tasks', 'list'], 
                                      capture_output=True, text=True, timeout=3)
                if result.returncode == 0:
                    for line in result.stdout.strip().split('\n')[1:]:  # Skip header
                        parts = line.split()
                        if len(parts) >= 2 and parts[0] == container_id:
                            pid = parts[1]
                            # Get network stats from this container's network namespace
                            return self._read_container_proc_net(pid)
            
        except Exception as e:
            self.log.debug(f"Error getting container network stats: {e}")
        
        return {}

    def _read_container_proc_net(self, pid: str) -> Dict:
        """Read network statistics from a container's /proc/PID/net/dev"""
        stats = {}
        
        try:
            proc_net_dev = f"/proc/{pid}/net/dev"
            if os.path.exists(proc_net_dev):
                with open(proc_net_dev, 'r') as f:
                    lines = f.readlines()[2:]  # Skip header
                    
                    for line in lines:
                        if ':' in line:
                            iface_part, stats_part = line.split(':', 1)
                            iface = iface_part.strip()
                            stat_values = stats_part.strip().split()
                            
                            if len(stat_values) >= 16 and iface != 'lo':
                                stats[iface] = {
                                    'rx_bytes': int(stat_values[0]),
                                    'rx_packets': int(stat_values[1]),
                                    'tx_bytes': int(stat_values[8]),
                                    'tx_packets': int(stat_values[9])
                                }
        
        except Exception as e:
            self.log.debug(f"Error reading container proc net for PID {pid}: {e}")
        
        return stats

    def _convert_stats_to_connections(self, namespace: str, ip_addr: str, net_stats: Dict) -> List[Dict]:
        """Convert interface statistics to connection-like objects for processing"""
        connections = []
        
        # Create synthetic connections based on interface activity
        total_rx_bytes = sum(stats.get('rx_bytes', 0) for stats in net_stats.values())
        total_tx_bytes = sum(stats.get('tx_bytes', 0) for stats in net_stats.values())
        total_packets = sum(stats.get('rx_packets', 0) + stats.get('tx_packets', 0) for stats in net_stats.values())
        
        if total_packets > 0:  # Only create connection if there's activity
            # Create a synthetic connection representing this namespace's activity
            connections.append({
                'local_addr': ip_addr,
                'local_port': 0,  # Synthetic
                'remote_addr': '0.0.0.0',  # Will be classified by network rules
                'remote_port': 0,  # Synthetic
                'namespace': namespace,
                'rx_bytes': total_rx_bytes,
                'tx_bytes': total_tx_bytes,
                'packets': total_packets,
                'protocol': 'interface_stats',
                'synthetic': True
            })
        
        return connections

    def _read_host_tcp_connections(self) -> List[Dict]:
        """Read TCP connections from host namespace (for comparison)"""
        connections = []
        
        # Read IPv4 TCP connections
        try:
            with open('/proc/net/tcp', 'r') as f:
                lines = f.readlines()[1:]  # Skip header
                for line in lines:
                    conn = self._parse_tcp_line(line, ipv6=False)
                    if conn:
                        conn['protocol'] = 'tcp'
                        connections.append(conn)
        except Exception as e:
            self.log.debug(f"Error reading /proc/net/tcp: {e}")
        
        return connections

    def _parse_tcp_line(self, line: str, ipv6: bool = False) -> Optional[Dict]:
        """Parse a line from /proc/net/tcp or /proc/net/tcp6"""
        try:
            parts = line.strip().split()
            if len(parts) < 10:
                return None
            
            # Parse local and remote addresses
            local_addr_port = parts[1]
            remote_addr_port = parts[2]
            state = int(parts[3], 16)
            
            # Parse tx_queue and rx_queue (columns 4 and 5 combined)
            tx_rx_queue = parts[4]  # Format: tx_queue:rx_queue
            uid = int(parts[7])
            inode = int(parts[9])
            
            # Extract queue information for data transfer estimation
            tx_queue = 0
            rx_queue = 0
            if ':' in tx_rx_queue:
                try:
                    tx_hex, rx_hex = tx_rx_queue.split(':')
                    tx_queue = int(tx_hex, 16)
                    rx_queue = int(rx_hex, 16)
                except:
                    pass
            
            # Accept more connection states, not just established
            # 01 = ESTABLISHED, 02 = SYN_SENT, 03 = SYN_RECV, 04 = FIN_WAIT1, etc.
            # We'll include established, syn_sent, syn_recv for active connections
            if state not in [0x01, 0x02, 0x03]:
                return None
            
            # Parse addresses
            if ':' in local_addr_port:
                local_addr_hex, local_port_hex = local_addr_port.split(':')
                remote_addr_hex, remote_port_hex = remote_addr_port.split(':')
            else:
                return None
            
            if ipv6:
                # IPv6 parsing is more complex - skip for now
                return None
            else:
                # IPv4 parsing
                local_addr = self._hex_to_ip(local_addr_hex)
                remote_addr = self._hex_to_ip(remote_addr_hex)
                local_port = int(local_port_hex, 16)
                remote_port = int(remote_port_hex, 16)
            
            # Skip localhost connections to reduce noise
            if local_addr.startswith('127.') and remote_addr.startswith('127.'):
                return None
            
            return {
                'local_addr': local_addr,
                'local_port': local_port,
                'remote_addr': remote_addr,
                'remote_port': remote_port,
                'uid': uid,
                'inode': inode,
                'tx_queue': tx_queue,
                'rx_queue': rx_queue,
                'ipv6': ipv6,
                'state': state
            }
            
        except Exception as e:
            self.log.debug(f"Error parsing TCP line: {e}")
            return None

    def _parse_udp_line(self, line: str, ipv6: bool = False) -> Optional[Dict]:
        """Parse a line from /proc/net/udp or /proc/net/udp6"""
        try:
            parts = line.strip().split()
            if len(parts) < 10:
                return None
            
            # Parse local and remote addresses
            local_addr_port = parts[1]
            remote_addr_port = parts[2]
            state = int(parts[3], 16)
            
            # Parse tx_queue and rx_queue
            tx_rx_queue = parts[4]
            uid = int(parts[7])
            inode = int(parts[9])
            
            # Extract queue information
            tx_queue = 0
            rx_queue = 0
            if ':' in tx_rx_queue:
                try:
                    tx_hex, rx_hex = tx_rx_queue.split(':')
                    tx_queue = int(tx_hex, 16)
                    rx_queue = int(rx_hex, 16)
                except:
                    pass
            
            # For UDP, we consider all states since UDP is connectionless
            # State 07 means established/connected UDP
            
            # Parse addresses
            if ':' in local_addr_port:
                local_addr_hex, local_port_hex = local_addr_port.split(':')
                remote_addr_hex, remote_port_hex = remote_addr_port.split(':')
            else:
                return None
            
            if ipv6:
                # IPv6 parsing - skip for now
                return None
            else:
                # IPv4 parsing
                local_addr = self._hex_to_ip(local_addr_hex)
                remote_addr = self._hex_to_ip(remote_addr_hex)
                local_port = int(local_port_hex, 16)
                remote_port = int(remote_port_hex, 16)
            
            # Skip localhost connections and unconnected UDP (remote = 0.0.0.0)
            if (local_addr.startswith('127.') and remote_addr.startswith('127.')) or remote_addr == '0.0.0.0':
                return None
            
            return {
                'local_addr': local_addr,
                'local_port': local_port,
                'remote_addr': remote_addr,
                'remote_port': remote_port,
                'uid': uid,
                'inode': inode,
                'tx_queue': tx_queue,
                'rx_queue': rx_queue,
                'ipv6': ipv6,
                'state': state
            }
            
        except Exception as e:
            self.log.debug(f"Error parsing UDP line: {e}")
            return None

    def _get_socket_bytes_estimate(self, inode: int) -> Dict[str, int]:
        """Estimate bytes transferred for a socket using /proc/net/sockstat"""
        try:
            # Look for socket information in /proc/*/fd/* to find process
            # This is a simplified approach - a full implementation would
            # track socket statistics over time
            
            # For now, return a basic estimate based on queue sizes
            # In production, you'd want to:
            # 1. Track socket stats over time
            # 2. Read from /proc/net/netstat for detailed stats
            # 3. Use /proc/PID/net/dev for per-process interface stats
            
            return {'tx_bytes': 0, 'rx_bytes': 0}
            
        except Exception:
            return {'tx_bytes': 0, 'rx_bytes': 0}

    def _hex_to_ip(self, hex_str: str) -> str:
        """Convert hex string to IP address"""
        # Convert hex to int, then to IP
        # Note: /proc/net/tcp uses little-endian format
        ip_int = int(hex_str, 16)
        ip_bytes = ip_int.to_bytes(4, byteorder='little')
        return str(ipaddress.IPv4Address(ip_bytes))

    def _probe(self) -> Optional[ValueSet]:
        """Probe network statistics using namespace-aware approach"""
        
        # Update namespace mappings using our enhanced detection
        self._update_namespace_mappings()
        
        # Get network statistics from individual namespaces
        connections = self._read_namespace_connections()
        
        if self._debug_namespace_detection:
            self.log.info(f"Found {len(connections)} total connections/stats")
            
            # Group by protocol and type
            protocol_counts = {}
            synthetic_count = 0
            for conn in connections:
                protocol = conn.get('protocol', 'unknown')
                if conn.get('synthetic', False):
                    synthetic_count += 1
                protocol_counts[protocol] = protocol_counts.get(protocol, 0) + 1
            
            self.log.info(f"Protocols: {protocol_counts} (synthetic: {synthetic_count})")
            
            # Show first few connections for debugging
            for i, conn in enumerate(connections[:5]):
                protocol = conn.get('protocol', 'unknown')
                if conn.get('synthetic', False):
                    ns = conn.get('namespace', 'unknown')
                    rx_bytes = conn.get('rx_bytes', 0)
                    tx_bytes = conn.get('tx_bytes', 0)
                    self.log.info(f"  Stats {i+1} ({protocol}): namespace={ns}, rx={rx_bytes}, tx={tx_bytes}")
                else:
                    state = conn.get('state', 0)
                    self.log.info(f"  Connection {i+1} ({protocol}): {conn['local_addr']}:{conn['local_port']} -> {conn['remote_addr']}:{conn['remote_port']} (state: {state:02x})")
        
        # Track traffic by namespace
        connection_stats = {}
        
        for conn in connections:
            if conn.get('synthetic', False):
                # Handle synthetic connections from interface stats
                namespace_name = conn.get('namespace', 'unknown')
                local_addr_str = conn['local_addr']
                
                # For synthetic connections, we estimate traffic to different networks
                rx_bytes = conn.get('rx_bytes', 0)
                tx_bytes = conn.get('tx_bytes', 0)
                
                # Distribute traffic proportionally across known networks
                for network in self.known_networks:
                    if not network.hide:
                        key = f"{namespace_name}:{network.name}"
                        if key not in connection_stats:
                            connection_stats[key] = {
                                'connections': 0,
                                'namespace': namespace_name,
                                'network': network,
                                'tx_queue_total': 0,
                                'rx_queue_total': 0,
                                'estimated_rx_bytes': 0,
                                'estimated_tx_bytes': 0
                            }
                        
                        # Simple distribution - in practice you'd want more sophisticated allocation
                        stats = connection_stats[key]
                        stats['connections'] += 1
                        stats['estimated_rx_bytes'] += rx_bytes // len([n for n in self.known_networks if not n.hide])
                        stats['estimated_tx_bytes'] += tx_bytes // len([n for n in self.known_networks if not n.hide])
            
            else:
                # Handle real connections (from host namespace)
                local_addr_str = conn['local_addr']
                remote_addr_str = conn['remote_addr']
                
                try:
                    local_addr_int = int(ipaddress.IPv4Address(local_addr_str))
                    remote_addr_int = int(ipaddress.IPv4Address(remote_addr_str))
                    
                    # Get namespace for this connection
                    namespace_name = self._get_namespace_for_address(local_addr_int)
                    
                    # Classify remote network
                    dest_network = None
                    for network in self.known_networks:
                        if network.contains(remote_addr_int):
                            dest_network = network
                            break
                    
                    if dest_network and namespace_name:
                        key = f"{namespace_name}:{dest_network.name}"
                        if key not in connection_stats:
                            connection_stats[key] = {
                                'connections': 0, 
                                'namespace': namespace_name, 
                                'network': dest_network,
                                'tx_queue_total': 0,
                                'rx_queue_total': 0
                            }
                        
                        stats = connection_stats[key]
                        stats['connections'] += 1
                        stats['tx_queue_total'] += conn.get('tx_queue', 0)
                        stats['rx_queue_total'] += conn.get('rx_queue', 0)
                
                except Exception as e:
                    self.log.debug(f"Error processing connection: {e}")
                    continue
        
        if self._debug_namespace_detection:
            self.log.info(f"Final connection stats: {len(connection_stats)} namespace/network combinations")
            for key, stats in connection_stats.items():
                self.log.info(f"  {key}: {stats['connections']} connections, rx={stats.get('estimated_rx_bytes', 0)}, tx={stats.get('estimated_tx_bytes', 0)}")
        
        # Export metrics
        values = ValueSet(labels=[self._namespace_label, 'dest_network', 'direction'])
        
        # If we have no connections but detected namespaces, add a basic metric showing we're working
        if len(connection_stats) == 0 and len(self._namespace_ips) > 0:
            # Add a metric showing that we detected namespaces but found no traffic
            values.add(Value(label_values=['system', 'detected_namespaces', 'count'], value=len(self._namespace_ips)))
            values.add(Value(label_values=['system', 'total_connections', 'count'], value=len(connections)))
        
        for key, stats in connection_stats.items():
            namespace = stats['namespace']
            network = stats['network']
            
            if network.hide:
                continue
            
            # Report multiple metrics per namespace/network combination
            connections = stats['connections']
            tx_queue = stats['tx_queue_total']
            rx_queue = stats['rx_queue_total']
            
            # Connection count
            values.add(Value(label_values=[namespace, network.name, 'connections'], value=connections))
            
            # Queue sizes (can indicate active data transfer)
            if tx_queue > 0:
                values.add(Value(label_values=[namespace, network.name, 'tx_queue_bytes'], value=tx_queue))
            if rx_queue > 0:
                values.add(Value(label_values=[namespace, network.name, 'rx_queue_bytes'], value=rx_queue))
            
            # Byte estimates (now more accurate from interface stats)
            if 'estimated_tx_bytes' in stats and stats['estimated_tx_bytes'] > 0:
                values.add(Value(label_values=[namespace, network.name, 'sent'], value=stats['estimated_tx_bytes']))
            if 'estimated_rx_bytes' in stats and stats['estimated_rx_bytes'] > 0:
                values.add(Value(label_values=[namespace, network.name, 'received'], value=stats['estimated_rx_bytes']))
        
        return values

    def _update_namespace_mappings(self):
        """Update namespace IP mappings using our enhanced detection"""
        self._namespace_ips = self._get_enhanced_namespace_ips()
        
        # Log what we detected for debugging
        if self._namespace_ips:
            if self._debug_namespace_detection:
                self.log.info(f"Updated namespace mappings: {len(self._namespace_ips)} namespaces")
                for namespace, ips in self._namespace_ips.items():
                    sample_ips = list(ips)[:3]  # Show first 3 IPs
                    more_text = f" (+{len(ips)-3} more)" if len(ips) > 3 else ""
                    self.log.info(f"  {namespace}: {sample_ips}{more_text}")
            else:
                self.log.debug(f"Detected {len(self._namespace_ips)} namespaces: {list(self._namespace_ips.keys())}")
                for namespace, ips in self._namespace_ips.items():
                    self.log.debug(f"  {namespace}: {len(ips)} IPs")
        else:
            self.log.warning(f"No namespace IPs detected using runtime {self._runtime_type}")
        
        # Also update the metrics system with actual namespace info
        self._metrics._container_networks = []
        for namespace, ips in self._namespace_ips.items():
            self._metrics._container_networks.append(NamedNetworks(namespace, list(ips)))

    def _get_namespace_for_address(self, local_address: int) -> str:
        """Get the actual Kubernetes namespace name for a local address"""
        
        # Convert address to string for logging
        addr_str = str(ipaddress.IPv4Address(local_address))
        
        # Always log what we're trying to resolve for debugging
        if self._debug_namespace_detection:
            self.log.info(f"Resolving namespace for address {addr_str}")
        
        # First try to match against detected namespace IPs
        for namespace, ips in self._namespace_ips.items():
            for ip_cidr in ips:
                try:
                    # Remove /32 suffix if present
                    ip_str = ip_cidr.split('/')[0]
                    ip_int = int(ipaddress.IPv4Address(ip_str))
                    if ip_int == local_address:
                        if self._debug_namespace_detection:
                            self.log.info(f"✅ Address {addr_str} matched namespace {namespace}")
                        return namespace
                except:
                    continue
        
        # If no namespace match found, check if we have any namespace data at all
        if not self._namespace_ips:
            if self._debug_namespace_detection:
                self.log.warning(f"❌ No namespace IPs available for address {addr_str} - runtime detection may have failed")
            return 'no-namespace-data'
        
        # If we have namespace data but no match, this might be a host network pod
        # Log detailed debugging info
        if self._debug_namespace_detection:
            self.log.warning(f"❌ Address {addr_str} not found in any of {len(self._namespace_ips)} detected namespaces")
            
            # Log the first few IPs from each namespace for debugging
            for ns, ips in list(self._namespace_ips.items())[:3]:
                sample_ips = list(ips)[:2]
                self.log.info(f"   Namespace {ns} has IPs: {sample_ips}")
        
        return 'host-network'

    def _read_interface_statistics(self) -> Dict[str, Dict[str, int]]:
        """Read network interface statistics from /proc/net/dev"""
        interface_stats = {}
        
        try:
            with open('/proc/net/dev', 'r') as f:
                lines = f.readlines()[2:]  # Skip header lines
                
                for line in lines:
                    if ':' in line:
                        iface_part, stats_part = line.split(':', 1)
                        iface = iface_part.strip()
                        stats = stats_part.strip().split()
                        
                        if len(stats) >= 16:
                            interface_stats[iface] = {
                                'rx_bytes': int(stats[0]),
                                'rx_packets': int(stats[1]),
                                'tx_bytes': int(stats[8]),
                                'tx_packets': int(stats[9])
                            }
        
        except Exception as e:
            self.log.debug(f"Error reading interface stats: {e}")
        
        return interface_stats

    def _estimate_namespace_bytes(self, connection_stats: Dict, interface_stats: Dict):
        """Estimate byte counts per namespace using interface statistics"""
        # This is a simplified estimation approach
        # In practice, you'd want to correlate connections with specific interfaces
        
        total_connections = sum(stats['connections'] for stats in connection_stats.values())
        if total_connections == 0:
            return
        
        # Get total interface traffic (excluding loopback)
        total_rx_bytes = 0
        total_tx_bytes = 0
        
        for iface, stats in interface_stats.items():
            if iface != 'lo':  # Exclude loopback
                total_rx_bytes += stats['rx_bytes']
                total_tx_bytes += stats['tx_bytes']
        
        # Simple proportional allocation based on connection count
        # This is crude but gives a starting point for byte estimates
        for key, stats in connection_stats.items():
            connection_ratio = stats['connections'] / total_connections
            stats['estimated_rx_bytes'] = int(total_rx_bytes * connection_ratio)
            stats['estimated_tx_bytes'] = int(total_tx_bytes * connection_ratio)


class NamespacesMetrics:
    """Fallback version of NamespacesMetrics that works with the fallback source"""
    
    CATCH_ALL_NAME = 'unknown'

    def __init__(self, known_networks: List[NamedNetworks]):
        self.metrics: Dict[str, NamespaceNetworkMetric] = {
            self.CATCH_ALL_NAME: NamespaceNetworkMetric(self.CATCH_ALL_NAME, known_networks, catch_all=True)
        }
        self._known_networks: List[NamedNetworks] = known_networks
        self._container_networks: List[NamedNetworks] = []

    def get_namespace_metrics(self, local_address: int):
        """Get namespace metrics for a local address"""
        network = self._get_container_network(local_address)
        if network is None:
            network = self._get_known_network(local_address)
            if network is None:
                return self.metrics[self.CATCH_ALL_NAME]

        if network.name not in self.metrics:
            self.metrics[network.name] = NamespaceNetworkMetric(network.name, self._known_networks)
        return self.metrics[network.name]

    def update_networks_enhanced(self):
        """Update networks using fallback source's namespace detection"""
        # Use the enhanced source's own namespace detection methods
        try:
            # Get the parent source instance to access its runtime detection
            if hasattr(self, '_parent_source'):
                namespace_ips = self._parent_source._get_enhanced_namespace_ips()
            else:
                # This is a fallback - we need access to the source instance
                # For now, return empty to use known network classification
                namespace_ips = {}
            
            networks = []
            for namespace, ips in namespace_ips.items():
                networks.append(NamedNetworks(namespace, list(ips)))
            self._container_networks = networks
        except Exception:
            # If enhanced detection fails, continue with empty list
            # This will fall back to known network classification
            self._container_networks = []

    def _get_container_network(self, local_address: int) -> Optional[NamedNetworks]:
        for network in self._container_networks:
            if network.contains(local_address):
                return network
        return None

    def _get_known_network(self, local_address: int) -> Optional[NamedNetworks]:
        for network in self._known_networks:
            if network.contains(local_address):
                return network
        return None


class NamespaceNetworkMetric:
    """Simplified version for the fallback source"""
    
    def __init__(self, name: str, known_networks: List[NamedNetworks], catch_all: bool = False):
        self.namespace: str = name
        self._known_networks: List[NamedNetworks] = known_networks
        self.metrics: Dict[NamedNetworks, NetworkMetrics] = dict()
        self._is_catch_all = catch_all

    def is_catch_all(self) -> bool:
        return self._is_catch_all
