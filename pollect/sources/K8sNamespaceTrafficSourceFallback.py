from __future__ import annotations

import os
import re
import time
import subprocess
from typing import Optional, List, Dict

from pollect.core.ValueSet import ValueSet, Value
from pollect.sources.Source import Source
from pollect.sources.helper.NetworkStats import NamedNetworks, ContainerNetworkUtils, NetworkMetrics


class K8sNamespaceTrafficSourceFallback(Source):
    """
    Fallback implementation for K8sNamespaceTrafficSource that works without BPF.
    Uses /proc/net/dev and container network namespaces for monitoring.
    
    This is a simplified version that provides basic network traffic monitoring
    without the detailed per-process tracking that BPF provides.
    """

    def __init__(self, config):
        super().__init__(config)
        self._namespace_label = config.get('namespaceLabel', 'namespace')
        self._traffic_log_mode = config.get('trafficLog')
        hide_localhost_traffic = config.get('hideLocalhostTraffic', True)

        self.known_networks: List[NamedNetworks] = []
        for network in config.get('networks', []):
            name = network['name']
            self.known_networks.append(NamedNetworks(name, network['cidrs']))

        # Add catch-any as last item
        self.known_networks.append(NamedNetworks('localhost', ['127.0.0.0/8'], hide=hide_localhost_traffic))
        self.known_networks.append(NamedNetworks('other', ['0.0.0.0/0'], catch_all=True))
        
        self._previous_stats: Dict[str, Dict[str, int]] = {}
        self._namespace_interfaces: Dict[str, List[str]] = {}

    def setup_source(self, global_conf):
        """Setup the fallback monitoring - no BPF compilation needed"""
        self.log.info("Using fallback network monitoring (no BPF)")
        self.log.info("This provides interface-level statistics instead of per-process tracking")
        
        # Test if we can access network namespaces
        try:
            self._update_namespace_interfaces()
            self.log.info(f"Found {len(self._namespace_interfaces)} network namespaces")
        except Exception as e:
            self.log.warning(f"Limited namespace access: {e}")

    def _update_namespace_interfaces(self):
        """Update the mapping of namespaces to their network interfaces"""
        self._namespace_interfaces.clear()
        
        try:
            # Try to get container network information using a safe method
            # that doesn't require containerd
            namespaces = self._get_namespace_ips_fallback()
            
            for namespace, ips in namespaces.items():
                # Find interfaces for this namespace
                interfaces = self._find_interfaces_for_namespace(namespace, ips)
                if interfaces:
                    self._namespace_interfaces[namespace] = interfaces
                    
        except Exception as e:
            # This is expected in non-container environments
            self.log.debug(f"Container namespace detection not available: {e}")
            # Continue with fallback approach

    def _get_namespace_ips_fallback(self):
        """
        Fallback method to detect namespace IPs without requiring containerd.
        This method tries to parse network information from /proc and other sources.
        """
        namespace_ips = {}
        
        # Try to read from /proc/net/route to find container networks
        try:
            with open('/proc/net/route', 'r') as f:
                lines = f.readlines()
            
            # Parse routing table to find container networks
            # This is a simplified approach that may not catch all cases
            for line in lines[1:]:  # Skip header
                parts = line.split()
                if len(parts) >= 8:
                    iface = parts[0]
                    # Look for interfaces that might be container interfaces
                    if iface.startswith(('veth', 'eth', 'docker', 'cni')):
                        # Try to get the IP of this interface
                        ip = self._get_interface_ip(iface)
                        if ip:
                            # Use a generic namespace name
                            if 'containers' not in namespace_ips:
                                namespace_ips['containers'] = set()
                            namespace_ips['containers'].add(ip)
        except:
            pass
        
        return namespace_ips

    def _get_interface_ip(self, interface: str) -> Optional[str]:
        """Get the IP address of a network interface"""
        try:
            result = subprocess.run(['ip', 'addr', 'show', interface], 
                                  capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                import re
                # Look for IPv4 addresses
                ip_pattern = r'inet (\d+\.\d+\.\d+\.\d+)'
                matches = re.findall(ip_pattern, result.stdout)
                if matches:
                    return matches[0]  # Return first IP found
        except:
            pass
        return None

    def _find_interfaces_for_namespace(self, namespace: str, ips: List[str]) -> List[str]:
        """Find network interfaces that belong to a specific namespace"""
        interfaces = []
        
        try:
            # Read /proc/net/dev to get all interfaces
            with open('/proc/net/dev', 'r') as f:
                lines = f.readlines()
            
            # Parse interface names
            for line in lines[2:]:  # Skip header lines
                if ':' in line:
                    iface = line.split(':')[0].strip()
                    
                    # Try to get IP of this interface
                    try:
                        result = subprocess.run(['ip', 'addr', 'show', iface], 
                                              capture_output=True, text=True, timeout=1)
                        if result.returncode == 0:
                            # Check if any of the namespace IPs are on this interface
                            for ip in ips:
                                if ip in result.stdout:
                                    interfaces.append(iface)
                                    break
                    except:
                        continue
                        
        except Exception as e:
            self.log.debug(f"Error finding interfaces for {namespace}: {e}")
            
        return interfaces

    def _read_interface_stats(self, interface: str) -> Optional[Dict[str, int]]:
        """Read network statistics for a specific interface"""
        try:
            with open('/proc/net/dev', 'r') as f:
                lines = f.readlines()
            
            for line in lines[2:]:  # Skip header lines
                if line.strip().startswith(interface + ':'):
                    parts = line.split()
                    if len(parts) >= 17:
                        return {
                            'rx_bytes': int(parts[1]),
                            'rx_packets': int(parts[2]),
                            'tx_bytes': int(parts[9]),
                            'tx_packets': int(parts[10])
                        }
        except Exception as e:
            self.log.debug(f"Error reading stats for {interface}: {e}")
            
        return None

    def _get_network_for_interface(self, interface: str) -> NamedNetworks:
        """Determine which network category an interface belongs to"""
        
        # Try to get the IP address of the interface
        try:
            result = subprocess.run(['ip', 'addr', 'show', interface], 
                                  capture_output=True, text=True, timeout=1)
            if result.returncode == 0:
                # Extract IP addresses from output
                import re
                ip_pattern = r'inet (\d+\.\d+\.\d+\.\d+)'
                ips = re.findall(ip_pattern, result.stdout)
                
                for ip_str in ips:
                    # Convert to int for network matching
                    import ipaddress
                    try:
                        ip = ipaddress.IPv4Address(ip_str)
                        ip_int = int(ip)
                        
                        # Check against known networks
                        for network in self.known_networks:
                            if network.contains(ip_int):
                                return network
                    except:
                        continue
        except:
            pass
            
        # Default to 'other' network
        return self.known_networks[-1]  # Last one should be 'other'

    def _probe(self) -> Optional[ValueSet]:
        """Probe network statistics using /proc/net/dev approach"""
        
        # Update namespace information
        try:
            self._update_namespace_interfaces()
        except Exception as e:
            self.log.debug(f"Could not update namespace info: {e}")
        
        values = ValueSet(labels=[self._namespace_label, 'dest_network', 'direction'])
        current_time = time.time()
        
        # If we have namespace information, use it
        if self._namespace_interfaces:
            for namespace, interfaces in self._namespace_interfaces.items():
                rx_bytes = 0
                tx_bytes = 0
                
                for interface in interfaces:
                    stats = self._read_interface_stats(interface)
                    if stats:
                        # Calculate deltas if we have previous stats
                        prev_key = f"{namespace}:{interface}"
                        if prev_key in self._previous_stats:
                            prev = self._previous_stats[prev_key]
                            rx_delta = max(0, stats['rx_bytes'] - prev['rx_bytes'])
                            tx_delta = max(0, stats['tx_bytes'] - prev['tx_bytes'])
                        else:
                            rx_delta = 0
                            tx_delta = 0
                        
                        rx_bytes += rx_delta
                        tx_bytes += tx_delta
                        
                        # Store current stats for next iteration
                        self._previous_stats[prev_key] = stats
                
                # Determine network category (simplified - use 'other' for now)
                network_name = 'other'
                
                # Add values for this namespace
                values.add(Value(label_values=[namespace, network_name, 'received'], value=rx_bytes))
                values.add(Value(label_values=[namespace, network_name, 'sent'], value=tx_bytes))
        
        else:
            # Fallback: monitor all interfaces and categorize as 'unknown'
            try:
                with open('/proc/net/dev', 'r') as f:
                    lines = f.readlines()
                
                total_rx = 0
                total_tx = 0
                
                for line in lines[2:]:  # Skip header lines
                    if ':' in line:
                        parts = line.split()
                        if len(parts) >= 17:
                            interface = parts[0].split(':')[0]
                            
                            # Skip loopback
                            if interface == 'lo':
                                continue
                            
                            stats = {
                                'rx_bytes': int(parts[1]),
                                'tx_bytes': int(parts[9])
                            }
                            
                            # Calculate deltas
                            if interface in self._previous_stats:
                                prev = self._previous_stats[interface]
                                rx_delta = max(0, stats['rx_bytes'] - prev['rx_bytes'])
                                tx_delta = max(0, stats['tx_bytes'] - prev['tx_bytes'])
                            else:
                                rx_delta = 0
                                tx_delta = 0
                            
                            total_rx += rx_delta
                            total_tx += tx_delta
                            
                            self._previous_stats[interface] = stats
                
                # Add aggregated stats as 'unknown' namespace
                values.add(Value(label_values=['unknown', 'other', 'received'], value=total_rx))
                values.add(Value(label_values=['unknown', 'other', 'sent'], value=total_tx))
                
            except Exception as e:
                self.log.error(f"Error reading network statistics: {e}")
                return None
        
        return values
