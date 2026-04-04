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
    
    IMPORTANT LIMITATION: This fallback cannot provide accurate byte counts
    like the original eBPF source. Instead, it provides estimated traffic 
    volumes based on connection patterns and port-based heuristics.
    
    This version uses /proc/net/tcp* for connection monitoring combined with
    container runtime information for namespace mapping. It provides true
    namespace-separated connection monitoring and estimated traffic volumes.
    
    Use this when eBPF is not available, but be aware that traffic volumes
    are estimates, not actual measured bytes.
    
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
        self.log.warning("FALLBACK MODE: Traffic volumes are estimates based on connection patterns, not actual measured bytes")
        
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
        """Probe network statistics using connection-based approach with estimated traffic"""
        
        # Update namespace mappings
        self._update_namespace_mappings()
        
        # Read actual TCP connections with real destinations
        connections = self._read_all_tcp_connections()
        
        if self._debug_namespace_detection:
            self.log.info(f"Found {len(connections)} total connections")
        
        # Process connections and estimate traffic based on connection patterns
        for conn in connections:
            try:
                local_addr_int = int(ipaddress.IPv4Address(conn['local_addr']))
                remote_addr_int = int(ipaddress.IPv4Address(conn['remote_addr']))
                
                # Get namespace metrics for this local address
                namespace_metrics = self._metrics.get_namespace_metrics(local_addr_int)
                
                # Classify traffic by actual destination 
                dest_network = None
                for network in self.known_networks:
                    if network.contains(remote_addr_int):
                        dest_network = network
                        break
                
                if dest_network:
                    # Estimate traffic per connection based on connection type and ports
                    estimated_bytes = self._estimate_connection_traffic(conn)
                    
                    # Add traffic to the specific destination network only
                    if dest_network not in namespace_metrics.metrics:
                        namespace_metrics.metrics[dest_network] = NetworkMetrics()
                    
                    namespace_metrics.metrics[dest_network].add_transmitted(estimated_bytes['tx'])
                    namespace_metrics.metrics[dest_network].add_received(estimated_bytes['rx'])
                    
                    if self._debug_namespace_detection:
                        self.log.info(f"Connection traffic estimate: {namespace_metrics.namespace} -> {dest_network.name}, "
                                    f"tx={estimated_bytes['tx']}, rx={estimated_bytes['rx']}, "
                                    f"from {conn['local_addr']}:{conn['local_port']} to {conn['remote_addr']}:{conn['remote_port']}")
                else:
                    if self._debug_namespace_detection:
                        self.log.info(f"No network match for destination {conn['remote_addr']} from {conn['local_addr']}")
            
            except Exception as e:
                self.log.debug(f"Error processing connection: {e}")
                continue
        
        # Export metrics using the same logic as original source
        values = ValueSet(labels=[self._namespace_label, 'dest_network', 'direction'])
        for value in self._metrics.metrics.values():
            namespace = value.namespace
            for network, metrics in value.metrics.items():
                if network.hide:
                    continue

                net_name = network.name
                assert isinstance(metrics, NetworkMetrics)
                values.add(Value(label_values=[namespace, net_name, 'received'], value=metrics.received_bytes))
                values.add(Value(label_values=[namespace, net_name, 'sent'], value=metrics.transmitted_bytes))
        
        return values

    def _estimate_connection_traffic(self, conn: Dict) -> Dict[str, int]:
        """Estimate traffic for a connection based on connection characteristics"""
        
        # Start with queue sizes if available (these are real buffered bytes)
        base_tx = max(conn.get('tx_queue', 0), 0)
        base_rx = max(conn.get('rx_queue', 0), 0)
        
        # Estimate additional traffic based on port and connection type
        local_port = conn['local_port']
        remote_port = conn['remote_port']
        
        # Common service port patterns and their typical traffic volumes
        # These are rough estimates based on typical service behavior
        
        # Web traffic (HTTP/HTTPS)
        if remote_port in [80, 443, 8080, 8443, 9090]:
            # Web requests: typically 1-10KB request, 10-100KB response
            estimated_tx = max(base_tx, 5000)   # ~5KB request
            estimated_rx = max(base_rx, 50000)  # ~50KB response
        
        # Database traffic
        elif remote_port in [3306, 5432, 6379, 27017, 1433, 5984]:
            # Database queries: typically 1KB query, 1-10KB response
            estimated_tx = max(base_tx, 1000)   # ~1KB query
            estimated_rx = max(base_rx, 5000)   # ~5KB response
        
        # API/Service mesh traffic
        elif remote_port in [6443, 2379, 2380, 10250, 10255]:
            # K8s API calls: typically small requests and responses
            estimated_tx = max(base_tx, 500)    # ~500B request
            estimated_rx = max(base_rx, 2000)   # ~2KB response
        
        # Monitoring/metrics traffic
        elif remote_port in [9100, 9090, 3000, 8086, 9093]:
            # Metrics scraping: typically small requests, larger responses
            estimated_tx = max(base_tx, 200)    # ~200B request
            estimated_rx = max(base_rx, 10000)  # ~10KB metrics response
        
        # Message queues/streaming
        elif remote_port in [9092, 5672, 4222, 1883]:
            # Message traffic: variable, moderate estimate
            estimated_tx = max(base_tx, 2000)   # ~2KB message
            estimated_rx = max(base_rx, 2000)   # ~2KB message
        
        # DNS traffic
        elif remote_port == 53:
            # DNS queries: very small
            estimated_tx = max(base_tx, 100)    # ~100B query
            estimated_rx = max(base_rx, 200)    # ~200B response
        
        # SSH/administrative
        elif remote_port == 22:
            # SSH: typically small interactive traffic
            estimated_tx = max(base_tx, 500)    # ~500B command
            estimated_rx = max(base_rx, 1000)   # ~1KB response
        
        # Default for unknown ports
        else:
            # Conservative estimate for unknown traffic
            estimated_tx = max(base_tx, 1000)   # ~1KB
            estimated_rx = max(base_rx, 1000)   # ~1KB
        
        # If this is a server port (listening), reverse the traffic pattern
        # (more incoming than outgoing)
        if local_port < 1024 or local_port in [8080, 8443, 9090]:
            # This appears to be a server connection, swap tx/rx estimates
            estimated_tx, estimated_rx = estimated_rx, estimated_tx
        
        return {
            'tx': estimated_tx,
            'rx': estimated_rx
        }

    def _read_all_tcp_connections(self) -> List[Dict]:
        """Read TCP connections from all accessible namespaces"""
        all_connections = []
        
        # Read from host namespace first
        host_connections = self._read_host_tcp_connections()
        all_connections.extend(host_connections)
        
        # Read from individual container namespaces
        for namespace, ips in self._namespace_ips.items():
            try:
                containers = self._get_containers_in_namespace(namespace)
                for container_info in containers:
                    container_connections = self._read_container_tcp_connections(container_info)
                    all_connections.extend(container_connections)
            except Exception as e:
                self.log.debug(f"Could not read connections from namespace {namespace}: {e}")
        
        # Remove duplicates and filter for meaningful connections
        unique_connections = []
        seen_connections = set()
        
        for conn in all_connections:
            # Create a unique key for this connection
            conn_key = f"{conn['local_addr']}:{conn['local_port']}->{conn['remote_addr']}:{conn['remote_port']}"
            if conn_key not in seen_connections:
                seen_connections.add(conn_key)
                # Only include connections with meaningful destinations (not 0.0.0.0)
                if conn['remote_addr'] != '0.0.0.0':
                    unique_connections.append(conn)
        
        if self._debug_namespace_detection:
            self.log.info(f"Found {len(unique_connections)} unique TCP connections from {len(all_connections)} total")
            # Show sample connections with destinations
            for i, conn in enumerate(unique_connections[:5]):
                self.log.info(f"  Connection {i+1}: {conn['local_addr']}:{conn['local_port']} -> {conn['remote_addr']}:{conn['remote_port']}")
        
        return unique_connections

    def _read_container_tcp_connections(self, container_info: Dict) -> List[Dict]:
        """Read TCP connections from a specific container's network namespace"""
        connections = []
        
        try:
            container_id = container_info['id']
            
            if self._runtime_type == "containerd":
                # Get container PID
                result = subprocess.run(['ctr', '-n', 'k8s.io', 'tasks', 'list'], 
                                      capture_output=True, text=True, timeout=3)
                if result.returncode == 0:
                    for line in result.stdout.strip().split('\n')[1:]:
                        parts = line.split()
                        if len(parts) >= 2 and parts[0] == container_id:
                            pid = parts[1]
                            # Read TCP connections from this container's namespace
                            connections = self._read_tcp_from_pid_namespace(pid)
                            break
        
        except Exception as e:
            self.log.debug(f"Error reading container TCP connections: {e}")
        
        return connections

    def _read_tcp_from_pid_namespace(self, pid: str) -> List[Dict]:
        """Read TCP connections from a specific PID's network namespace"""
        connections = []
        
        try:
            proc_net_tcp = f"/proc/{pid}/net/tcp"
            if os.path.exists(proc_net_tcp):
                with open(proc_net_tcp, 'r') as f:
                    lines = f.readlines()[1:]  # Skip header
                    for line in lines:
                        conn = self._parse_tcp_line(line, ipv6=False)
                        if conn:
                            conn['protocol'] = 'tcp'
                            conn['pid_namespace'] = pid
                            connections.append(conn)
        
        except Exception as e:
            self.log.debug(f"Error reading TCP from PID {pid}: {e}")
        
        return connections

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
