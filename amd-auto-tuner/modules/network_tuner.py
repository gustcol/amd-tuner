#!/usr/bin/env python3
"""
Network Tuner Module
Optimizes network interface performance (ring buffers, offloads, sysctl)

Supports high-speed NICs:
- 25 Gbps, 50 Gbps, 100 Gbps, 200 Gbps, 400 Gbps
- Intel: ice, i40e, ixgbe, igb, e1000e
- Mellanox/NVIDIA: mlx5_core, mlx4_en
- Broadcom: bnxt_en
- AMD/Pensando: ionic

Features:
- Ring buffer optimization
- Hardware offloads (TSO, GSO, GRO, LRO)
- Interrupt coalescing and moderation
- RDMA/RoCE configuration
- DCB (Data Center Bridging)
- PFC (Priority Flow Control)
- Jumbo frames
- RSS (Receive Side Scaling)
- IRQ affinity optimization
"""

import json
import subprocess
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import logging


class NetworkTuner:
    """Handles network interface performance tuning for high-speed NICs."""

    # Speed tiers in Mbps
    SPEED_TIERS = {
        '1G': 1000,
        '10G': 10000,
        '25G': 25000,
        '40G': 40000,
        '50G': 50000,
        '100G': 100000,
        '200G': 200000,
        '400G': 400000
    }

    # Driver classifications
    INTEL_DRIVERS = ['ice', 'i40e', 'ixgbe', 'igb', 'e1000e', 'iavf', 'i40evf']
    MELLANOX_DRIVERS = ['mlx5_core', 'mlx4_en', 'mlx5_en']
    BROADCOM_DRIVERS = ['bnxt_en', 'bnx2x', 'tg3']
    AMD_DRIVERS = ['ionic', 'atlantic']

    # Mellanox ConnectX generations with capabilities
    MELLANOX_CONNECTX = {
        'connectx-4': {'max_speed': '100G', 'rdma': True, 'roce_v2': True},
        'connectx-5': {'max_speed': '100G', 'rdma': True, 'roce_v2': True, 'nvme_of': True},
        'connectx-6': {'max_speed': '200G', 'rdma': True, 'roce_v2': True, 'nvme_of': True, 'dpdk': True},
        'connectx-6dx': {'max_speed': '200G', 'rdma': True, 'roce_v2': True, 'ipsec': True, 'crypto': True},
        'connectx-6lx': {'max_speed': '25G', 'rdma': True, 'roce_v2': True, 'crypto': True},
        'connectx-7': {'max_speed': '400G', 'rdma': True, 'roce_v2': True, 'nvme_of': True, 'dpdk': True, 'crypto': True}
    }

    # Intel high-speed NIC models
    INTEL_NICS = {
        'e810': {'driver': 'ice', 'max_speed': '100G', 'rdma': True},
        'e800': {'driver': 'ice', 'max_speed': '100G', 'rdma': True},
        'xl710': {'driver': 'i40e', 'max_speed': '40G'},
        'x710': {'driver': 'i40e', 'max_speed': '10G'},
        'xxv710': {'driver': 'i40e', 'max_speed': '25G'}
    }

    def __init__(self, backup_dir: Path):
        """
        Initialize the network tuner.

        Args:
            backup_dir: Directory to store configuration backups
        """
        self.logger = logging.getLogger('AMDAutoTuner.NetworkTuner')
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)

        self.net_path = Path('/sys/class/net')
        self.sysctl_path = Path('/proc/sys/net')

    def get_current_settings(self) -> Dict[str, Any]:
        """
        Get current network settings for all interfaces.

        Returns:
            Dictionary containing current network configuration
        """
        settings = {
            'interfaces': {},
            'sysctl': self._get_sysctl_settings()
        }

        for iface_path in self.net_path.iterdir():
            name = iface_path.name
            if name == 'lo':
                continue

            settings['interfaces'][name] = self._get_interface_settings(name)

        return settings

    def _get_interface_settings(self, interface: str) -> Dict[str, Any]:
        """Get settings for a specific interface."""
        settings = {
            'mtu': 0,
            'txqueuelen': 0,
            'ring_buffer_rx': 0,
            'ring_buffer_tx': 0,
            'ring_buffer_rx_max': 0,
            'ring_buffer_tx_max': 0,
            'offloads': {},
            'coalesce': {}
        }

        iface_path = self.net_path / interface

        try:
            # MTU
            mtu_path = iface_path / 'mtu'
            if mtu_path.exists():
                settings['mtu'] = int(mtu_path.read_text().strip())

            # TX queue length
            txqueuelen_path = iface_path / 'tx_queue_len'
            if txqueuelen_path.exists():
                settings['txqueuelen'] = int(txqueuelen_path.read_text().strip())

            # Ring buffer info (via ethtool)
            ring_info = self._get_ring_buffer_info(interface)
            settings.update(ring_info)

            # Offload features
            settings['offloads'] = self._get_offload_features(interface)

            # Coalesce settings
            settings['coalesce'] = self._get_coalesce_settings(interface)

        except Exception as e:
            self.logger.debug(f"Could not get settings for {interface}: {e}")

        return settings

    def _get_ring_buffer_info(self, interface: str) -> Dict[str, int]:
        """Get ring buffer information using ethtool."""
        info = {
            'ring_buffer_rx': 0,
            'ring_buffer_tx': 0,
            'ring_buffer_rx_max': 0,
            'ring_buffer_tx_max': 0
        }

        try:
            result = subprocess.run(
                ['ethtool', '-g', interface],
                capture_output=True, text=True, timeout=5
            )

            if result.returncode == 0:
                output = result.stdout
                in_current = False
                in_max = False

                for line in output.split('\n'):
                    if 'Pre-set maximums' in line:
                        in_max = True
                        in_current = False
                    elif 'Current hardware settings' in line:
                        in_current = True
                        in_max = False
                    elif 'RX:' in line:
                        try:
                            value = int(line.split(':')[1].strip())
                            if in_max:
                                info['ring_buffer_rx_max'] = value
                            elif in_current:
                                info['ring_buffer_rx'] = value
                        except (ValueError, IndexError):
                            pass
                    elif 'TX:' in line:
                        try:
                            value = int(line.split(':')[1].strip())
                            if in_max:
                                info['ring_buffer_tx_max'] = value
                            elif in_current:
                                info['ring_buffer_tx'] = value
                        except (ValueError, IndexError):
                            pass
        except Exception as e:
            self.logger.debug(f"Could not get ring buffer info for {interface}: {e}")

        return info

    def _get_offload_features(self, interface: str) -> Dict[str, bool]:
        """Get network offload features using ethtool."""
        features = {}

        try:
            result = subprocess.run(
                ['ethtool', '-k', interface],
                capture_output=True, text=True, timeout=5
            )

            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if ':' in line:
                        parts = line.split(':')
                        if len(parts) >= 2:
                            key = parts[0].strip()
                            value = parts[1].strip().lower()
                            # Only include main offload features
                            if any(x in key.lower() for x in ['offload', 'scatter', 'checksum', 'segmentation', 'gro', 'gso', 'tso', 'lro']):
                                features[key] = 'on' in value
        except Exception as e:
            self.logger.debug(f"Could not get offload features for {interface}: {e}")

        return features

    def _get_coalesce_settings(self, interface: str) -> Dict[str, int]:
        """Get interrupt coalescing settings using ethtool."""
        coalesce = {}

        try:
            result = subprocess.run(
                ['ethtool', '-c', interface],
                capture_output=True, text=True, timeout=5
            )

            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if ':' in line:
                        parts = line.split(':')
                        if len(parts) >= 2:
                            key = parts[0].strip()
                            try:
                                value = int(parts[1].strip())
                                coalesce[key] = value
                            except ValueError:
                                pass
        except Exception as e:
            self.logger.debug(f"Could not get coalesce settings for {interface}: {e}")

        return coalesce

    def _get_sysctl_settings(self) -> Dict[str, Any]:
        """Get network-related sysctl settings."""
        settings = {}

        sysctl_keys = [
            'net.core.rmem_max',
            'net.core.wmem_max',
            'net.core.rmem_default',
            'net.core.wmem_default',
            'net.core.netdev_max_backlog',
            'net.core.somaxconn',
            'net.ipv4.tcp_rmem',
            'net.ipv4.tcp_wmem',
            'net.ipv4.tcp_max_syn_backlog',
            'net.ipv4.tcp_congestion_control',
            'net.ipv4.tcp_fastopen',
            'net.ipv4.tcp_slow_start_after_idle',
            'net.ipv4.tcp_mtu_probing'
        ]

        try:
            result = subprocess.run(
                ['sysctl'] + sysctl_keys,
                capture_output=True, text=True, timeout=5
            )

            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        settings[key.strip()] = value.strip()
        except Exception as e:
            self.logger.debug(f"Could not get sysctl settings: {e}")

        return settings

    def create_backup(self) -> str:
        """
        Create a backup of current network settings.

        Returns:
            Path to backup file
        """
        settings = self.get_current_settings()
        settings['timestamp'] = datetime.now().isoformat()

        backup_file = self.backup_dir / f"network_backup_{datetime.now():%Y%m%d_%H%M%S}.json"

        with open(backup_file, 'w') as f:
            json.dump(settings, f, indent=2)

        self.logger.info(f"Network backup created: {backup_file}")
        return str(backup_file)

    def restore_backup(self, backup_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Restore network settings from backup.

        Args:
            backup_file: Path to specific backup file. If None, uses latest backup.

        Returns:
            Dictionary containing restoration status
        """
        if backup_file is None:
            backups = list(self.backup_dir.glob('network_backup_*.json'))
            if not backups:
                return {'success': False, 'error': 'No backup found'}
            backup_file = str(max(backups, key=lambda x: x.stat().st_mtime))

        try:
            with open(backup_file) as f:
                settings = json.load(f)

            results = {'success': True, 'interfaces': {}, 'sysctl': []}

            # Restore interface settings
            for interface, iface_settings in settings.get('interfaces', {}).items():
                iface_results = []

                # Restore ring buffers
                if iface_settings.get('ring_buffer_rx'):
                    if self._set_ring_buffer(interface, iface_settings['ring_buffer_rx'], 'rx'):
                        iface_results.append(f"Ring buffer RX: {iface_settings['ring_buffer_rx']}")

                if iface_settings.get('ring_buffer_tx'):
                    if self._set_ring_buffer(interface, iface_settings['ring_buffer_tx'], 'tx'):
                        iface_results.append(f"Ring buffer TX: {iface_settings['ring_buffer_tx']}")

                results['interfaces'][interface] = iface_results

            # Restore sysctl settings
            for key, value in settings.get('sysctl', {}).items():
                if self._set_sysctl(key, value):
                    results['sysctl'].append(f"{key}={value}")

            self.logger.info(f"Restored network settings from {backup_file}")
            return results
        except Exception as e:
            self.logger.error(f"Failed to restore backup: {e}")
            return {'success': False, 'error': str(e)}

    def apply_profile(self, settings: Dict[str, Any], interfaces: List[Dict[str, Any]],
                      dry_run: bool = False) -> Dict[str, Any]:
        """
        Apply network tuning settings.

        Args:
            settings: Network settings to apply
            interfaces: List of network interface information
            dry_run: If True, only simulate changes

        Returns:
            Dictionary containing applied changes
        """
        changes = {
            'interfaces': {},
            'sysctl': {
                'applied': [],
                'skipped': [],
                'errors': []
            }
        }

        # Create backup first (unless dry run)
        if not dry_run:
            try:
                self.create_backup()
            except Exception as e:
                self.logger.warning(f"Could not create backup: {e}")

        # Apply interface-specific settings
        for iface in interfaces:
            name = iface['name']

            # Skip virtual and wireless interfaces for some optimizations
            if iface.get('is_virtual', False):
                continue

            changes['interfaces'][name] = {
                'applied': [],
                'skipped': [],
                'errors': []
            }

            # Ring buffer optimization
            if settings.get('ring_buffer_max', False):
                max_rx = iface.get('ring_buffer_max_rx', 0)
                max_tx = iface.get('ring_buffer_max_tx', 0)

                if max_rx > 0:
                    if dry_run:
                        changes['interfaces'][name]['applied'].append(f"Would set ring buffer RX: {max_rx}")
                    else:
                        if self._set_ring_buffer(name, max_rx, 'rx'):
                            changes['interfaces'][name]['applied'].append(f"Set ring buffer RX: {max_rx}")
                        else:
                            changes['interfaces'][name]['errors'].append(f"Failed to set ring buffer RX")

                if max_tx > 0:
                    if dry_run:
                        changes['interfaces'][name]['applied'].append(f"Would set ring buffer TX: {max_tx}")
                    else:
                        if self._set_ring_buffer(name, max_tx, 'tx'):
                            changes['interfaces'][name]['applied'].append(f"Set ring buffer TX: {max_tx}")
                        else:
                            changes['interfaces'][name]['errors'].append(f"Failed to set ring buffer TX")

            # Offload optimization
            if settings.get('offloads', False):
                offload_features = ['gro', 'gso', 'tso', 'tx-checksum-ipv4', 'tx-checksum-ipv6', 'rx-checksum']
                for feature in offload_features:
                    if dry_run:
                        changes['interfaces'][name]['applied'].append(f"Would enable {feature}")
                    else:
                        if self._set_offload(name, feature, True):
                            changes['interfaces'][name]['applied'].append(f"Enabled {feature}")
                        else:
                            changes['interfaces'][name]['skipped'].append(f"{feature} not available")

            # Interrupt coalescing
            if settings.get('interrupt_coalescing', False):
                if dry_run:
                    changes['interfaces'][name]['applied'].append("Would enable adaptive interrupt coalescing")
                else:
                    if self._set_adaptive_coalescing(name, True):
                        changes['interfaces'][name]['applied'].append("Enabled adaptive interrupt coalescing")
                    else:
                        changes['interfaces'][name]['skipped'].append("Interrupt coalescing not supported")

            # Driver-specific optimizations
            driver = iface.get('driver', '')
            if driver:
                driver_optimizations = self._get_driver_optimizations(driver)
                for opt_name, opt_cmd in driver_optimizations.items():
                    if dry_run:
                        changes['interfaces'][name]['applied'].append(f"Would apply {opt_name}")
                    else:
                        if self._apply_driver_optimization(name, opt_cmd):
                            changes['interfaces'][name]['applied'].append(f"Applied {opt_name}")
                        else:
                            changes['interfaces'][name]['skipped'].append(f"{opt_name} failed")

        # Apply sysctl settings
        if settings.get('optimize_sysctl', False):
            sysctl_optimizations = self._get_sysctl_optimizations()

            for key, value in sysctl_optimizations.items():
                if dry_run:
                    changes['sysctl']['applied'].append(f"Would set {key}={value}")
                else:
                    if self._set_sysctl(key, value):
                        changes['sysctl']['applied'].append(f"Set {key}={value}")
                    else:
                        changes['sysctl']['errors'].append(f"Failed to set {key}")

        # Congestion control
        if 'congestion_control' in settings:
            cc = settings['congestion_control']
            if dry_run:
                changes['sysctl']['applied'].append(f"Would set congestion control: {cc}")
            else:
                if self._set_congestion_control(cc):
                    changes['sysctl']['applied'].append(f"Set congestion control: {cc}")
                else:
                    changes['sysctl']['errors'].append(f"Failed to set congestion control: {cc}")

        return changes

    def _set_ring_buffer(self, interface: str, size: int, direction: str) -> bool:
        """Set ring buffer size for an interface."""
        try:
            result = subprocess.run(
                ['ethtool', '-G', interface, direction, str(size)],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                self.logger.debug(f"Set {interface} ring buffer {direction} to {size}")
                return True
            else:
                self.logger.debug(f"Failed to set ring buffer: {result.stderr}")
                return False
        except Exception as e:
            self.logger.debug(f"Ring buffer setting failed: {e}")
            return False

    def _set_offload(self, interface: str, feature: str, enabled: bool) -> bool:
        """Set offload feature for an interface."""
        try:
            state = 'on' if enabled else 'off'
            result = subprocess.run(
                ['ethtool', '-K', interface, feature, state],
                capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def _set_adaptive_coalescing(self, interface: str, enabled: bool) -> bool:
        """Set adaptive interrupt coalescing."""
        try:
            state = 'on' if enabled else 'off'
            result = subprocess.run(
                ['ethtool', '-C', interface, 'adaptive-rx', state, 'adaptive-tx', state],
                capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def _set_sysctl(self, key: str, value: str) -> bool:
        """Set a sysctl value."""
        try:
            result = subprocess.run(
                ['sysctl', '-w', f'{key}={value}'],
                capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def _set_congestion_control(self, algorithm: str) -> bool:
        """Set TCP congestion control algorithm."""
        return self._set_sysctl('net.ipv4.tcp_congestion_control', algorithm)

    def _get_driver_optimizations(self, driver: str) -> Dict[str, List[str]]:
        """Get driver-specific optimizations."""
        optimizations = {}

        driver_lower = driver.lower()

        # Intel drivers (1G-100G+)
        if driver_lower in self.INTEL_DRIVERS:
            optimizations['intel_flow_director'] = ['ethtool', '-K', '{iface}', 'ntuple', 'on']
            if driver_lower in ['ice', 'i40e', 'ixgbe']:
                # High-speed Intel NICs
                optimizations['intel_lro'] = ['ethtool', '-K', '{iface}', 'lro', 'on']
                optimizations['intel_rss'] = ['ethtool', '-K', '{iface}', 'rxhash', 'on']

        # Mellanox/NVIDIA drivers (10G-400G)
        if driver_lower in self.MELLANOX_DRIVERS:
            optimizations['mellanox_adaptive_moderation'] = ['ethtool', '-C', '{iface}', 'adaptive-rx', 'on', 'adaptive-tx', 'on']
            optimizations['mellanox_lro'] = ['ethtool', '-K', '{iface}', 'lro', 'on']
            optimizations['mellanox_rss'] = ['ethtool', '-K', '{iface}', 'rxhash', 'on']

        # Broadcom drivers (1G-100G)
        if driver_lower in self.BROADCOM_DRIVERS:
            optimizations['broadcom_lro'] = ['ethtool', '-K', '{iface}', 'lro', 'on']
            if driver_lower == 'bnxt_en':
                optimizations['broadcom_adaptive'] = ['ethtool', '-C', '{iface}', 'adaptive-rx', 'on']

        # AMD/Pensando drivers (25G-200G)
        if driver_lower in self.AMD_DRIVERS:
            optimizations['amd_lro'] = ['ethtool', '-K', '{iface}', 'lro', 'on']
            optimizations['amd_adaptive'] = ['ethtool', '-C', '{iface}', 'adaptive-rx', 'on']

        # Realtek drivers (1G)
        if driver_lower in ['r8169', 'r8168']:
            optimizations['realtek_eee_disable'] = ['ethtool', '--set-eee', '{iface}', 'eee', 'off']

        return optimizations

    def detect_nic_speed(self, interface: str) -> Tuple[int, str]:
        """
        Detect NIC speed and classify it.

        Args:
            interface: Network interface name

        Returns:
            Tuple of (speed_mbps, speed_tier)
        """
        speed_mbps = 0
        speed_tier = 'unknown'

        try:
            # Try getting speed from sysfs
            speed_path = self.net_path / interface / 'speed'
            if speed_path.exists():
                speed_mbps = int(speed_path.read_text().strip())
        except (ValueError, FileNotFoundError, PermissionError):
            pass

        if speed_mbps <= 0:
            # Try ethtool
            try:
                result = subprocess.run(
                    ['ethtool', interface],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if 'Speed:' in line:
                            match = re.search(r'(\d+)\s*(Mb/s|Gb/s)', line)
                            if match:
                                value = int(match.group(1))
                                unit = match.group(2)
                                speed_mbps = value * 1000 if 'Gb/s' in unit else value
                                break
            except Exception:
                pass

        # Classify speed tier
        for tier, threshold in sorted(self.SPEED_TIERS.items(), key=lambda x: x[1], reverse=True):
            if speed_mbps >= threshold:
                speed_tier = tier
                break

        return speed_mbps, speed_tier

    def detect_nic_capabilities(self, interface: str) -> Dict[str, Any]:
        """
        Detect advanced NIC capabilities.

        Args:
            interface: Network interface name

        Returns:
            Dictionary of capabilities
        """
        capabilities = {
            'rdma': False,
            'roce': False,
            'dcb': False,
            'pfc': False,
            'sriov': False,
            'jumbo_frames': False,
            'rss': False,
            'rfs': False,
            'xdp': False,
            'timestamping': False
        }

        # Check for RDMA/RoCE
        try:
            rdma_path = Path('/sys/class/infiniband')
            if rdma_path.exists():
                for dev in rdma_path.iterdir():
                    netdev_path = dev / 'device' / 'net'
                    if netdev_path.exists():
                        for netdev in netdev_path.iterdir():
                            if netdev.name == interface:
                                capabilities['rdma'] = True
                                capabilities['roce'] = True
                                break
        except Exception:
            pass

        # Check for SR-IOV
        try:
            sriov_path = self.net_path / interface / 'device' / 'sriov_numvfs'
            if sriov_path.exists():
                capabilities['sriov'] = True
        except Exception:
            pass

        # Check for jumbo frames support
        try:
            result = subprocess.run(
                ['ip', 'link', 'show', interface],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                match = re.search(r'mtu\s+(\d+)', result.stdout)
                if match:
                    mtu = int(match.group(1))
                    # Check if we can set MTU to 9000
                    capabilities['jumbo_frames'] = mtu <= 9000
        except Exception:
            pass

        # Check for RSS support
        try:
            result = subprocess.run(
                ['ethtool', '-l', interface],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and 'Combined:' in result.stdout:
                capabilities['rss'] = True
        except Exception:
            pass

        # Check for timestamping support
        try:
            result = subprocess.run(
                ['ethtool', '-T', interface],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and 'hardware-transmit' in result.stdout:
                capabilities['timestamping'] = True
        except Exception:
            pass

        return capabilities

    def get_high_speed_optimizations(self, speed_tier: str, driver: str) -> Dict[str, Any]:
        """
        Get optimizations for high-speed NICs based on speed tier.

        Args:
            speed_tier: Speed tier (25G, 50G, 100G, 200G, 400G)
            driver: NIC driver name

        Returns:
            Dictionary of optimization settings
        """
        # Base settings that scale with speed
        base_settings = {
            'ring_buffer_max': True,
            'offloads': True,
            'interrupt_coalescing': True,
            'congestion_control': 'bbr',
            'optimize_sysctl': True
        }

        # Speed-specific settings
        speed_settings = {
            '25G': {
                'mtu': 9000,
                'rx_usecs': 50,
                'tx_usecs': 50,
                'rx_frames': 128,
                'tx_frames': 128,
                'netdev_budget': 600,
                'netdev_budget_usecs': 4000
            },
            '50G': {
                'mtu': 9000,
                'rx_usecs': 25,
                'tx_usecs': 25,
                'rx_frames': 256,
                'tx_frames': 256,
                'netdev_budget': 1200,
                'netdev_budget_usecs': 4000
            },
            '100G': {
                'mtu': 9000,
                'rx_usecs': 10,
                'tx_usecs': 10,
                'rx_frames': 512,
                'tx_frames': 512,
                'netdev_budget': 2400,
                'netdev_budget_usecs': 4000
            },
            '200G': {
                'mtu': 9000,
                'rx_usecs': 5,
                'tx_usecs': 5,
                'rx_frames': 1024,
                'tx_frames': 1024,
                'netdev_budget': 4800,
                'netdev_budget_usecs': 4000
            },
            '400G': {
                'mtu': 9000,
                'rx_usecs': 2,
                'tx_usecs': 2,
                'rx_frames': 2048,
                'tx_frames': 2048,
                'netdev_budget': 9600,
                'netdev_budget_usecs': 4000
            }
        }

        settings = base_settings.copy()
        if speed_tier in speed_settings:
            settings['speed_specific'] = speed_settings[speed_tier]

        # Driver-specific tuning
        driver_lower = driver.lower()

        if driver_lower in self.INTEL_DRIVERS:
            settings['driver_type'] = 'intel'
            settings['intel'] = {
                'itr': 'dynamic',
                'flow_director': True,
                'rss': True
            }

        elif driver_lower in self.MELLANOX_DRIVERS:
            settings['driver_type'] = 'mellanox'
            settings['mellanox'] = {
                'cq_moderation': 'auto',
                'adaptive_rx': True,
                'adaptive_tx': True,
                'rss': True,
                'roce_priority': 3
            }

        elif driver_lower in self.BROADCOM_DRIVERS:
            settings['driver_type'] = 'broadcom'
            settings['broadcom'] = {
                'rss': True,
                'adaptive_rx': True
            }

        elif driver_lower in self.AMD_DRIVERS:
            settings['driver_type'] = 'amd'
            settings['amd'] = {
                'adaptive_rx': True,
                'rss': True
            }

        return settings

    def apply_high_speed_tuning(self, interface: str, settings: Dict[str, Any],
                                 dry_run: bool = False) -> Dict[str, Any]:
        """
        Apply high-speed NIC optimizations.

        Args:
            interface: Network interface name
            settings: High-speed optimization settings
            dry_run: If True, only simulate changes

        Returns:
            Dictionary of applied changes
        """
        changes = {
            'applied': [],
            'skipped': [],
            'errors': []
        }

        speed_specific = settings.get('speed_specific', {})

        # Set MTU for jumbo frames
        if 'mtu' in speed_specific:
            mtu = speed_specific['mtu']
            if dry_run:
                changes['applied'].append(f"Would set MTU to {mtu}")
            else:
                if self._set_mtu(interface, mtu):
                    changes['applied'].append(f"Set MTU to {mtu}")
                else:
                    changes['skipped'].append(f"Could not set MTU to {mtu}")

        # Set interrupt coalescing
        if 'rx_usecs' in speed_specific:
            rx_usecs = speed_specific['rx_usecs']
            tx_usecs = speed_specific.get('tx_usecs', rx_usecs)
            if dry_run:
                changes['applied'].append(f"Would set rx-usecs={rx_usecs}, tx-usecs={tx_usecs}")
            else:
                if self._set_coalesce_usecs(interface, rx_usecs, tx_usecs):
                    changes['applied'].append(f"Set rx-usecs={rx_usecs}, tx-usecs={tx_usecs}")
                else:
                    changes['skipped'].append("Coalescing usecs not supported")

        # Set frame coalescing
        if 'rx_frames' in speed_specific:
            rx_frames = speed_specific['rx_frames']
            tx_frames = speed_specific.get('tx_frames', rx_frames)
            if dry_run:
                changes['applied'].append(f"Would set rx-frames={rx_frames}, tx-frames={tx_frames}")
            else:
                if self._set_coalesce_frames(interface, rx_frames, tx_frames):
                    changes['applied'].append(f"Set rx-frames={rx_frames}, tx-frames={tx_frames}")
                else:
                    changes['skipped'].append("Coalescing frames not supported")

        # Apply driver-specific optimizations
        driver_type = settings.get('driver_type')

        if driver_type == 'intel' and 'intel' in settings:
            intel_changes = self._apply_intel_optimizations(interface, settings['intel'], dry_run)
            changes['applied'].extend(intel_changes.get('applied', []))
            changes['skipped'].extend(intel_changes.get('skipped', []))

        elif driver_type == 'mellanox' and 'mellanox' in settings:
            mlx_changes = self._apply_mellanox_optimizations(interface, settings['mellanox'], dry_run)
            changes['applied'].extend(mlx_changes.get('applied', []))
            changes['skipped'].extend(mlx_changes.get('skipped', []))

        elif driver_type == 'broadcom' and 'broadcom' in settings:
            bcm_changes = self._apply_broadcom_optimizations(interface, settings['broadcom'], dry_run)
            changes['applied'].extend(bcm_changes.get('applied', []))
            changes['skipped'].extend(bcm_changes.get('skipped', []))

        elif driver_type == 'amd' and 'amd' in settings:
            amd_changes = self._apply_amd_optimizations(interface, settings['amd'], dry_run)
            changes['applied'].extend(amd_changes.get('applied', []))
            changes['skipped'].extend(amd_changes.get('skipped', []))

        return changes

    def _set_mtu(self, interface: str, mtu: int) -> bool:
        """Set MTU for an interface."""
        try:
            result = subprocess.run(
                ['ip', 'link', 'set', interface, 'mtu', str(mtu)],
                capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def _set_coalesce_usecs(self, interface: str, rx_usecs: int, tx_usecs: int) -> bool:
        """Set interrupt coalescing in microseconds."""
        try:
            result = subprocess.run(
                ['ethtool', '-C', interface, 'rx-usecs', str(rx_usecs), 'tx-usecs', str(tx_usecs)],
                capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def _set_coalesce_frames(self, interface: str, rx_frames: int, tx_frames: int) -> bool:
        """Set interrupt coalescing frame count."""
        try:
            result = subprocess.run(
                ['ethtool', '-C', interface, 'rx-frames', str(rx_frames), 'tx-frames', str(tx_frames)],
                capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def _apply_intel_optimizations(self, interface: str, settings: Dict[str, Any],
                                    dry_run: bool) -> Dict[str, Any]:
        """Apply Intel NIC specific optimizations."""
        changes = {'applied': [], 'skipped': []}

        if settings.get('flow_director'):
            if dry_run:
                changes['applied'].append("Would enable Intel Flow Director")
            else:
                try:
                    result = subprocess.run(
                        ['ethtool', '-K', interface, 'ntuple', 'on'],
                        capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0:
                        changes['applied'].append("Enabled Intel Flow Director")
                    else:
                        changes['skipped'].append("Flow Director not supported")
                except Exception:
                    changes['skipped'].append("Flow Director failed")

        if settings.get('rss'):
            if dry_run:
                changes['applied'].append("Would enable Intel RSS")
            else:
                try:
                    result = subprocess.run(
                        ['ethtool', '-K', interface, 'rxhash', 'on'],
                        capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0:
                        changes['applied'].append("Enabled Intel RSS")
                    else:
                        changes['skipped'].append("RSS not supported")
                except Exception:
                    changes['skipped'].append("RSS failed")

        return changes

    def detect_mellanox_generation(self, interface: str) -> Optional[str]:
        """
        Detect Mellanox ConnectX generation.

        Args:
            interface: Network interface name

        Returns:
            ConnectX generation string or None
        """
        try:
            # Try to get device info from lspci
            result = subprocess.run(
                ['lspci', '-v'],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                output = result.stdout.lower()
                for gen, caps in self.MELLANOX_CONNECTX.items():
                    if gen.replace('-', '') in output or gen in output:
                        return gen

            # Also check sysfs
            device_path = self.net_path / interface / 'device' / 'device'
            if device_path.exists():
                device_id = device_path.read_text().strip()
                # ConnectX device ID mapping
                connectx_ids = {
                    '0x1015': 'connectx-4',
                    '0x1017': 'connectx-5',
                    '0x101b': 'connectx-6',
                    '0x101d': 'connectx-6dx',
                    '0x101f': 'connectx-6lx',
                    '0x1021': 'connectx-7'
                }
                if device_id in connectx_ids:
                    return connectx_ids[device_id]

        except Exception:
            pass

        return None

    def _apply_mellanox_optimizations(self, interface: str, settings: Dict[str, Any],
                                       dry_run: bool) -> Dict[str, Any]:
        """Apply Mellanox/NVIDIA NIC specific optimizations."""
        changes = {'applied': [], 'skipped': []}

        # Detect ConnectX generation for specific optimizations
        connectx_gen = self.detect_mellanox_generation(interface)
        if connectx_gen:
            self.logger.info(f"Detected Mellanox {connectx_gen.upper()} on {interface}")
            changes['applied'].append(f"Detected {connectx_gen.upper()}")

        if settings.get('adaptive_rx') or settings.get('adaptive_tx'):
            if dry_run:
                changes['applied'].append("Would enable Mellanox adaptive moderation")
            else:
                try:
                    result = subprocess.run(
                        ['ethtool', '-C', interface, 'adaptive-rx', 'on', 'adaptive-tx', 'on'],
                        capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0:
                        changes['applied'].append("Enabled Mellanox adaptive moderation")
                    else:
                        changes['skipped'].append("Adaptive moderation not supported")
                except Exception:
                    changes['skipped'].append("Adaptive moderation failed")

        if settings.get('rss'):
            if dry_run:
                changes['applied'].append("Would enable Mellanox RSS")
            else:
                try:
                    result = subprocess.run(
                        ['ethtool', '-K', interface, 'rxhash', 'on'],
                        capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0:
                        changes['applied'].append("Enabled Mellanox RSS")
                    else:
                        changes['skipped'].append("RSS not supported")
                except Exception:
                    changes['skipped'].append("RSS failed")

        # ConnectX-6/7 specific optimizations
        if connectx_gen in ['connectx-6', 'connectx-6dx', 'connectx-6lx', 'connectx-7']:
            # Enable enhanced features
            enhanced_features = ['lro', 'tx-nocache-copy']

            for feature in enhanced_features:
                if dry_run:
                    changes['applied'].append(f"Would enable {feature}")
                else:
                    try:
                        result = subprocess.run(
                            ['ethtool', '-K', interface, feature, 'on'],
                            capture_output=True, text=True, timeout=5
                        )
                        if result.returncode == 0:
                            changes['applied'].append(f"Enabled {feature}")
                        else:
                            changes['skipped'].append(f"{feature} not supported")
                    except Exception:
                        changes['skipped'].append(f"{feature} failed")

            # Set optimal queue count for high-core systems
            try:
                import os
                cpu_count = os.cpu_count() or 8
                # Use at most CPU count or 64 queues, whichever is smaller
                queue_count = min(cpu_count, 64)

                if dry_run:
                    changes['applied'].append(f"Would set {queue_count} combined queues")
                else:
                    result = subprocess.run(
                        ['ethtool', '-L', interface, 'combined', str(queue_count)],
                        capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0:
                        changes['applied'].append(f"Set {queue_count} combined queues")
                    else:
                        changes['skipped'].append("Queue count adjustment not supported")
            except Exception:
                changes['skipped'].append("Queue optimization failed")

        return changes

    def _apply_broadcom_optimizations(self, interface: str, settings: Dict[str, Any],
                                       dry_run: bool) -> Dict[str, Any]:
        """Apply Broadcom NIC specific optimizations."""
        changes = {'applied': [], 'skipped': []}

        if settings.get('adaptive_rx'):
            if dry_run:
                changes['applied'].append("Would enable Broadcom adaptive RX")
            else:
                try:
                    result = subprocess.run(
                        ['ethtool', '-C', interface, 'adaptive-rx', 'on'],
                        capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0:
                        changes['applied'].append("Enabled Broadcom adaptive RX")
                    else:
                        changes['skipped'].append("Adaptive RX not supported")
                except Exception:
                    changes['skipped'].append("Adaptive RX failed")

        return changes

    def _apply_amd_optimizations(self, interface: str, settings: Dict[str, Any],
                                  dry_run: bool) -> Dict[str, Any]:
        """Apply AMD/Pensando NIC specific optimizations."""
        changes = {'applied': [], 'skipped': []}

        if settings.get('adaptive_rx'):
            if dry_run:
                changes['applied'].append("Would enable AMD adaptive RX")
            else:
                try:
                    result = subprocess.run(
                        ['ethtool', '-C', interface, 'adaptive-rx', 'on'],
                        capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0:
                        changes['applied'].append("Enabled AMD adaptive RX")
                    else:
                        changes['skipped'].append("Adaptive RX not supported")
                except Exception:
                    changes['skipped'].append("Adaptive RX failed")

        return changes

    def get_high_speed_sysctl(self, speed_tier: str) -> Dict[str, str]:
        """
        Get sysctl optimizations for high-speed networking.

        Args:
            speed_tier: Speed tier (25G, 50G, 100G, 200G, 400G)

        Returns:
            Dictionary of sysctl settings
        """
        # Base high-speed settings
        settings = {
            # Increase socket buffer sizes significantly
            'net.core.rmem_max': '67108864',  # 64MB
            'net.core.wmem_max': '67108864',
            'net.core.rmem_default': '16777216',  # 16MB
            'net.core.wmem_default': '16777216',

            # Increase network device backlog
            'net.core.netdev_max_backlog': '250000',
            'net.core.netdev_budget': '600',
            'net.core.netdev_budget_usecs': '4000',

            # Increase connection queue
            'net.core.somaxconn': '65535',

            # TCP buffer sizes
            'net.ipv4.tcp_rmem': '4096 16777216 67108864',
            'net.ipv4.tcp_wmem': '4096 16777216 67108864',

            # TCP optimizations
            'net.ipv4.tcp_max_syn_backlog': '65535',
            'net.ipv4.tcp_slow_start_after_idle': '0',
            'net.ipv4.tcp_tw_reuse': '1',
            'net.ipv4.tcp_fastopen': '3',
            'net.ipv4.tcp_mtu_probing': '1',
            'net.ipv4.tcp_timestamps': '1',
            'net.ipv4.tcp_sack': '1',
            'net.ipv4.tcp_window_scaling': '1',
            'net.ipv4.tcp_no_metrics_save': '1',

            # Increase port range
            'net.ipv4.ip_local_port_range': '1024 65535',

            # Enable BPF JIT
            'net.core.bpf_jit_enable': '1'
        }

        # Speed-specific adjustments
        if speed_tier in ['100G', '200G', '400G']:
            settings.update({
                'net.core.rmem_max': '134217728',  # 128MB
                'net.core.wmem_max': '134217728',
                'net.ipv4.tcp_rmem': '4096 33554432 134217728',
                'net.ipv4.tcp_wmem': '4096 33554432 134217728',
                'net.core.netdev_max_backlog': '500000'
            })

        if speed_tier in ['200G', '400G']:
            settings.update({
                'net.core.netdev_budget': '1200',
                'net.core.netdev_budget_usecs': '8000'
            })

        return settings

    def _apply_driver_optimization(self, interface: str, cmd_template: List[str]) -> bool:
        """Apply a driver-specific optimization."""
        try:
            cmd = [c.replace('{iface}', interface) for c in cmd_template]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except Exception:
            return False

    def _get_sysctl_optimizations(self) -> Dict[str, str]:
        """Get optimized sysctl settings for network performance."""
        return {
            # Socket buffer sizes
            'net.core.rmem_max': '16777216',
            'net.core.wmem_max': '16777216',
            'net.core.rmem_default': '1048576',
            'net.core.wmem_default': '1048576',

            # Network device backlog
            'net.core.netdev_max_backlog': '50000',
            'net.core.somaxconn': '4096',

            # TCP buffer sizes
            'net.ipv4.tcp_rmem': '4096 1048576 16777216',
            'net.ipv4.tcp_wmem': '4096 1048576 16777216',

            # TCP optimizations
            'net.ipv4.tcp_max_syn_backlog': '8192',
            'net.ipv4.tcp_slow_start_after_idle': '0',
            'net.ipv4.tcp_tw_reuse': '1',
            'net.ipv4.tcp_fastopen': '3',
            'net.ipv4.tcp_mtu_probing': '1',

            # Increase the maximum number of connections
            'net.ipv4.ip_local_port_range': '1024 65535',

            # Enable TCP window scaling
            'net.ipv4.tcp_window_scaling': '1',

            # Enable timestamps
            'net.ipv4.tcp_timestamps': '1',

            # Enable selective acknowledgments
            'net.ipv4.tcp_sack': '1',

            # Disable SYN cookies (for high-performance servers)
            # 'net.ipv4.tcp_syncookies': '0',
        }

    def optimize_for_workload(self, workload: str, interfaces: List[Dict[str, Any]],
                              dry_run: bool = False) -> Dict[str, Any]:
        """
        Optimize network for specific workload.

        Args:
            workload: Type of workload ('latency', 'throughput', 'balanced', 'server')
            interfaces: List of network interface information
            dry_run: If True, only simulate changes

        Returns:
            Dictionary containing applied changes
        """
        workload_profiles = {
            'latency': {
                'ring_buffer_max': False,
                'offloads': True,
                'interrupt_coalescing': False,
                'congestion_control': 'bbr',
                'optimize_sysctl': True
            },
            'throughput': {
                'ring_buffer_max': True,
                'offloads': True,
                'interrupt_coalescing': True,
                'congestion_control': 'bbr',
                'optimize_sysctl': True
            },
            'balanced': {
                'ring_buffer_max': False,
                'offloads': True,
                'interrupt_coalescing': True,
                'congestion_control': 'bbr',
                'optimize_sysctl': True
            },
            'server': {
                'ring_buffer_max': True,
                'offloads': True,
                'interrupt_coalescing': True,
                'congestion_control': 'bbr',
                'optimize_sysctl': True
            }
        }

        if workload not in workload_profiles:
            raise ValueError(f"Unknown workload: {workload}. Options: {list(workload_profiles.keys())}")

        return self.apply_profile(workload_profiles[workload], interfaces, dry_run)


if __name__ == '__main__':
    import json

    logging.basicConfig(level=logging.DEBUG)
    tuner = NetworkTuner(Path('/tmp/network_backup'))

    print("=== Network Settings ===")
    settings = tuner.get_current_settings()
    print(json.dumps(settings, indent=2))
