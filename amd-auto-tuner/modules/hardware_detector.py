#!/usr/bin/env python3
"""
Hardware Detector Module
Detects AMD CPU, storage devices, and network interfaces
"""

import os
import re
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging


class HardwareDetector:
    """Detects and gathers information about system hardware."""

    def __init__(self):
        self.logger = logging.getLogger('AMDAutoTuner.HardwareDetector')
        self._cpu_info: Optional[Dict[str, Any]] = None
        self._storage_info: Optional[List[Dict[str, Any]]] = None
        self._network_info: Optional[List[Dict[str, Any]]] = None

    def detect_all(self) -> Dict[str, Any]:
        """
        Detect all hardware components.

        Returns:
            Dictionary with 'cpu', 'storage', and 'network' keys
        """
        return {
            'cpu': self.detect_cpu(),
            'storage': self.detect_storage(),
            'network': self.detect_network()
        }

    def detect_cpu(self) -> Dict[str, Any]:
        """
        Detect AMD CPU information.

        Returns:
            Dictionary containing CPU details
        """
        self.logger.debug("Detecting CPU...")

        info = {
            'model': '',
            'vendor': '',
            'family': '',
            'architecture': '',
            'cores': 0,
            'threads': 0,
            'sockets': 1,
            'base_freq_mhz': 0,
            'max_freq_mhz': 0,
            'min_freq_mhz': 0,
            'current_freq_mhz': 0,
            'cache_l1d': '',
            'cache_l1i': '',
            'cache_l2': '',
            'cache_l3': '',
            'features': [],
            'governor': '',
            'available_governors': [],
            'boost_enabled': None,
            'is_amd': False,
            'zen_generation': None,
            'amd_pstate_available': False,
            'amd_pstate_mode': None
        }

        # Read /proc/cpuinfo
        try:
            with open('/proc/cpuinfo', 'r') as f:
                cpuinfo = f.read()

            # Parse CPU info
            for line in cpuinfo.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip()
                    value = value.strip()

                    if key == 'model name':
                        info['model'] = value
                    elif key == 'vendor_id':
                        info['vendor'] = value
                        info['is_amd'] = 'AMD' in value.upper()
                    elif key == 'cpu family':
                        info['family'] = value
                    elif key == 'cpu cores':
                        info['cores'] = int(value)
                    elif key == 'siblings':
                        info['threads'] = int(value)
                    elif key == 'flags':
                        info['features'] = value.split()
        except Exception as e:
            self.logger.warning(f"Could not read /proc/cpuinfo: {e}")

        # Detect Zen generation from model name
        info['zen_generation'] = self._detect_zen_generation(info['model'])

        # Get architecture
        try:
            result = subprocess.run(['uname', '-m'], capture_output=True, text=True)
            info['architecture'] = result.stdout.strip()
        except Exception:
            pass

        # Get frequency information
        info.update(self._get_frequency_info())

        # Get governor information
        info.update(self._get_governor_info())

        # Get boost status
        info['boost_enabled'] = self._get_boost_status()

        # Check AMD P-State driver
        info.update(self._check_amd_pstate())

        # Get cache information
        info.update(self._get_cache_info())

        # Get socket count
        info['sockets'] = self._get_socket_count()

        self._cpu_info = info
        return info

    def _detect_zen_generation(self, model: str) -> Optional[str]:
        """Detect AMD Zen generation from model name."""
        model_lower = model.lower()

        if 'ryzen' in model_lower or 'epyc' in model_lower or 'threadripper' in model_lower:
            # Zen 4 (Ryzen 7000 series, EPYC Genoa)
            if any(x in model_lower for x in ['7950', '7900', '7800', '7700', '7600', '9950', '9900', '9800', '9700', '9600']):
                return 'zen4'
            if 'genoa' in model_lower or '9004' in model_lower:
                return 'zen4'

            # Zen 3 (Ryzen 5000 series, EPYC Milan)
            if any(x in model_lower for x in ['5950', '5900', '5800', '5700', '5600', '5500']):
                return 'zen3'
            if 'milan' in model_lower or '7003' in model_lower:
                return 'zen3'

            # Zen 2 (Ryzen 3000 series, EPYC Rome)
            if any(x in model_lower for x in ['3950', '3900', '3800', '3700', '3600', '3500', '3400', '3300', '3200', '3100']):
                return 'zen2'
            if 'rome' in model_lower or '7002' in model_lower:
                return 'zen2'

            # Zen+ (Ryzen 2000 series)
            if any(x in model_lower for x in ['2700', '2600', '2500', '2400', '2300', '2200']):
                return 'zen+'

            # Zen 1 (Ryzen 1000 series, EPYC Naples)
            if any(x in model_lower for x in ['1800', '1700', '1600', '1500', '1400', '1300', '1200']):
                return 'zen1'
            if 'naples' in model_lower or '7001' in model_lower:
                return 'zen1'

        return None

    def _get_frequency_info(self) -> Dict[str, Any]:
        """Get CPU frequency information from sysfs."""
        info = {
            'base_freq_mhz': 0,
            'max_freq_mhz': 0,
            'min_freq_mhz': 0,
            'current_freq_mhz': 0
        }

        cpufreq_path = Path('/sys/devices/system/cpu/cpu0/cpufreq')

        try:
            # Maximum frequency
            max_freq_file = cpufreq_path / 'cpuinfo_max_freq'
            if max_freq_file.exists():
                with open(max_freq_file) as f:
                    info['max_freq_mhz'] = int(f.read().strip()) // 1000

            # Minimum frequency
            min_freq_file = cpufreq_path / 'cpuinfo_min_freq'
            if min_freq_file.exists():
                with open(min_freq_file) as f:
                    info['min_freq_mhz'] = int(f.read().strip()) // 1000

            # Base frequency (scaling_max_freq as fallback)
            base_freq_file = cpufreq_path / 'base_frequency'
            if base_freq_file.exists():
                with open(base_freq_file) as f:
                    info['base_freq_mhz'] = int(f.read().strip()) // 1000
            else:
                info['base_freq_mhz'] = info['max_freq_mhz']

            # Current frequency
            cur_freq_file = cpufreq_path / 'scaling_cur_freq'
            if cur_freq_file.exists():
                with open(cur_freq_file) as f:
                    info['current_freq_mhz'] = int(f.read().strip()) // 1000
        except Exception as e:
            self.logger.debug(f"Could not read frequency info: {e}")

        return info

    def _get_governor_info(self) -> Dict[str, Any]:
        """Get CPU governor information."""
        info = {
            'governor': '',
            'available_governors': []
        }

        cpufreq_path = Path('/sys/devices/system/cpu/cpu0/cpufreq')

        try:
            # Current governor
            governor_file = cpufreq_path / 'scaling_governor'
            if governor_file.exists():
                with open(governor_file) as f:
                    info['governor'] = f.read().strip()

            # Available governors
            available_file = cpufreq_path / 'scaling_available_governors'
            if available_file.exists():
                with open(available_file) as f:
                    info['available_governors'] = f.read().strip().split()
        except Exception as e:
            self.logger.debug(f"Could not read governor info: {e}")

        return info

    def _get_boost_status(self) -> Optional[bool]:
        """Get CPU boost status."""
        boost_path = Path('/sys/devices/system/cpu/cpufreq/boost')

        try:
            if boost_path.exists():
                with open(boost_path) as f:
                    return f.read().strip() == '1'
        except Exception as e:
            self.logger.debug(f"Could not read boost status: {e}")

        return None

    def _check_amd_pstate(self) -> Dict[str, Any]:
        """Check AMD P-State driver availability and status."""
        info = {
            'amd_pstate_available': False,
            'amd_pstate_mode': None
        }

        # Check if amd_pstate driver is in use
        driver_path = Path('/sys/devices/system/cpu/cpu0/cpufreq/scaling_driver')
        status_path = Path('/sys/devices/system/cpu/amd_pstate/status')

        try:
            if driver_path.exists():
                with open(driver_path) as f:
                    driver = f.read().strip()
                    if 'amd' in driver.lower() and 'pstate' in driver.lower():
                        info['amd_pstate_available'] = True

            if status_path.exists():
                info['amd_pstate_available'] = True
                with open(status_path) as f:
                    info['amd_pstate_mode'] = f.read().strip()
        except Exception as e:
            self.logger.debug(f"Could not check AMD P-State: {e}")

        return info

    def _get_cache_info(self) -> Dict[str, str]:
        """Get CPU cache information."""
        info = {
            'cache_l1d': '',
            'cache_l1i': '',
            'cache_l2': '',
            'cache_l3': ''
        }

        try:
            result = subprocess.run(['lscpu'], capture_output=True, text=True)
            output = result.stdout

            for line in output.split('\n'):
                if 'L1d cache:' in line:
                    info['cache_l1d'] = line.split(':')[1].strip()
                elif 'L1i cache:' in line:
                    info['cache_l1i'] = line.split(':')[1].strip()
                elif 'L2 cache:' in line:
                    info['cache_l2'] = line.split(':')[1].strip()
                elif 'L3 cache:' in line:
                    info['cache_l3'] = line.split(':')[1].strip()
        except Exception as e:
            self.logger.debug(f"Could not get cache info: {e}")

        return info

    def _get_socket_count(self) -> int:
        """Get number of CPU sockets."""
        try:
            result = subprocess.run(['lscpu'], capture_output=True, text=True)
            for line in result.stdout.split('\n'):
                if 'Socket(s):' in line:
                    return int(line.split(':')[1].strip())
        except Exception:
            pass
        return 1

    def detect_storage(self) -> List[Dict[str, Any]]:
        """
        Detect storage devices.

        Returns:
            List of dictionaries containing storage device information
        """
        self.logger.debug("Detecting storage devices...")

        devices = []
        block_path = Path('/sys/block')

        try:
            for device in block_path.iterdir():
                name = device.name

                # Skip loop devices, ram disks, etc.
                if name.startswith(('loop', 'ram', 'dm-', 'sr', 'fd')):
                    continue

                device_info = self._get_storage_device_info(name)
                if device_info:
                    devices.append(device_info)
        except Exception as e:
            self.logger.warning(f"Could not enumerate storage devices: {e}")

        # Sort by device name
        devices.sort(key=lambda x: x['name'])

        self._storage_info = devices
        return devices

    def _get_storage_device_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific storage device."""
        device_path = Path(f'/sys/block/{name}')

        if not device_path.exists():
            return None

        info = {
            'name': name,
            'path': f'/dev/{name}',
            'type': 'unknown',
            'model': '',
            'size_bytes': 0,
            'size_human': '',
            'rotational': True,
            'scheduler': '',
            'available_schedulers': [],
            'read_ahead_kb': 0,
            'nr_requests': 0,
            'queue_depth': 0,
            'is_nvme': name.startswith('nvme'),
            'is_ssd': False,
            'transport': 'unknown'
        }

        try:
            # Size
            size_file = device_path / 'size'
            if size_file.exists():
                with open(size_file) as f:
                    sectors = int(f.read().strip())
                    info['size_bytes'] = sectors * 512
                    info['size_human'] = self._format_size(info['size_bytes'])

            # Rotational (0 = SSD, 1 = HDD)
            rotational_file = device_path / 'queue' / 'rotational'
            if rotational_file.exists():
                with open(rotational_file) as f:
                    info['rotational'] = f.read().strip() == '1'
                    info['is_ssd'] = not info['rotational']

            # Device type
            if info['is_nvme']:
                info['type'] = 'nvme'
                info['transport'] = 'pcie'
            elif info['is_ssd']:
                info['type'] = 'ssd'
                info['transport'] = 'sata'
            else:
                info['type'] = 'hdd'
                info['transport'] = 'sata'

            # Model
            model_file = device_path / 'device' / 'model'
            if model_file.exists():
                with open(model_file) as f:
                    info['model'] = f.read().strip()

            # NVMe model
            if info['is_nvme']:
                nvme_model_file = device_path / 'device' / 'model'
                if nvme_model_file.exists():
                    with open(nvme_model_file) as f:
                        info['model'] = f.read().strip()

            # Scheduler
            scheduler_file = device_path / 'queue' / 'scheduler'
            if scheduler_file.exists():
                with open(scheduler_file) as f:
                    content = f.read().strip()
                    # Parse format: "mq-deadline [none] kyber bfq"
                    # Current scheduler is in brackets
                    match = re.search(r'\[(\w+)\]', content)
                    if match:
                        info['scheduler'] = match.group(1)
                    info['available_schedulers'] = re.findall(r'[\w-]+', content)

            # Read-ahead
            read_ahead_file = device_path / 'queue' / 'read_ahead_kb'
            if read_ahead_file.exists():
                with open(read_ahead_file) as f:
                    info['read_ahead_kb'] = int(f.read().strip())

            # Number of requests
            nr_requests_file = device_path / 'queue' / 'nr_requests'
            if nr_requests_file.exists():
                with open(nr_requests_file) as f:
                    info['nr_requests'] = int(f.read().strip())

            # Queue depth
            queue_depth_file = device_path / 'device' / 'queue_depth'
            if queue_depth_file.exists():
                with open(queue_depth_file) as f:
                    info['queue_depth'] = int(f.read().strip())

        except Exception as e:
            self.logger.debug(f"Could not get info for {name}: {e}")

        return info

    def _format_size(self, size_bytes: int) -> str:
        """Format size in bytes to human readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
            if size_bytes < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} EB"

    def detect_network(self) -> List[Dict[str, Any]]:
        """
        Detect network interfaces.

        Returns:
            List of dictionaries containing network interface information
        """
        self.logger.debug("Detecting network interfaces...")

        interfaces = []
        net_path = Path('/sys/class/net')

        try:
            for iface in net_path.iterdir():
                name = iface.name

                # Skip loopback
                if name == 'lo':
                    continue

                iface_info = self._get_network_interface_info(name)
                if iface_info:
                    interfaces.append(iface_info)
        except Exception as e:
            self.logger.warning(f"Could not enumerate network interfaces: {e}")

        # Sort by interface name
        interfaces.sort(key=lambda x: x['name'])

        self._network_info = interfaces
        return interfaces

    def _get_network_interface_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific network interface."""
        iface_path = Path(f'/sys/class/net/{name}')

        if not iface_path.exists():
            return None

        info = {
            'name': name,
            'type': 'unknown',
            'driver': '',
            'mac_address': '',
            'speed': 0,
            'mtu': 0,
            'state': 'unknown',
            'ip_addresses': [],
            'ring_buffer_current_rx': 0,
            'ring_buffer_max_rx': 0,
            'ring_buffer_current_tx': 0,
            'ring_buffer_max_tx': 0,
            'offload_features': {},
            'is_virtual': False,
            'is_wireless': False
        }

        try:
            # Interface type
            type_file = iface_path / 'type'
            if type_file.exists():
                with open(type_file) as f:
                    type_id = int(f.read().strip())
                    # 1 = Ethernet, 772 = loopback, 801 = wireless
                    if type_id == 1:
                        info['type'] = 'ethernet'
                    elif type_id == 801:
                        info['type'] = 'wireless'
                        info['is_wireless'] = True

            # Check if virtual
            if (iface_path / 'device').exists():
                info['is_virtual'] = False
            else:
                info['is_virtual'] = True

            # Driver
            driver_link = iface_path / 'device' / 'driver'
            if driver_link.exists():
                info['driver'] = driver_link.resolve().name

            # MAC address
            address_file = iface_path / 'address'
            if address_file.exists():
                with open(address_file) as f:
                    info['mac_address'] = f.read().strip()

            # Speed
            speed_file = iface_path / 'speed'
            if speed_file.exists():
                try:
                    with open(speed_file) as f:
                        info['speed'] = int(f.read().strip())
                except ValueError:
                    pass  # Speed might be -1 if link is down

            # MTU
            mtu_file = iface_path / 'mtu'
            if mtu_file.exists():
                with open(mtu_file) as f:
                    info['mtu'] = int(f.read().strip())

            # Operational state
            operstate_file = iface_path / 'operstate'
            if operstate_file.exists():
                with open(operstate_file) as f:
                    info['state'] = f.read().strip()

            # Get ring buffer info using ethtool
            info.update(self._get_ring_buffer_info(name))

            # Get offload features using ethtool
            info['offload_features'] = self._get_offload_features(name)

            # Get IP addresses
            info['ip_addresses'] = self._get_ip_addresses(name)

        except Exception as e:
            self.logger.debug(f"Could not get info for {name}: {e}")

        return info

    def _get_ring_buffer_info(self, interface: str) -> Dict[str, int]:
        """Get ring buffer information using ethtool."""
        info = {
            'ring_buffer_current_rx': 0,
            'ring_buffer_max_rx': 0,
            'ring_buffer_current_tx': 0,
            'ring_buffer_max_tx': 0
        }

        try:
            result = subprocess.run(
                ['ethtool', '-g', interface],
                capture_output=True, text=True, timeout=5
            )

            if result.returncode == 0:
                output = result.stdout
                lines = output.split('\n')

                in_current = False
                in_max = False

                for line in lines:
                    if 'Pre-set maximums' in line:
                        in_max = True
                        in_current = False
                    elif 'Current hardware settings' in line:
                        in_current = True
                        in_max = False
                    elif 'RX:' in line:
                        value = int(line.split(':')[1].strip())
                        if in_max:
                            info['ring_buffer_max_rx'] = value
                        elif in_current:
                            info['ring_buffer_current_rx'] = value
                    elif 'TX:' in line:
                        value = int(line.split(':')[1].strip())
                        if in_max:
                            info['ring_buffer_max_tx'] = value
                        elif in_current:
                            info['ring_buffer_current_tx'] = value
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
                            features[key] = value == 'on'
        except Exception as e:
            self.logger.debug(f"Could not get offload features for {interface}: {e}")

        return features

    def _get_ip_addresses(self, interface: str) -> List[str]:
        """Get IP addresses for an interface."""
        addresses = []

        try:
            result = subprocess.run(
                ['ip', 'addr', 'show', interface],
                capture_output=True, text=True, timeout=5
            )

            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'inet ' in line:
                        match = re.search(r'inet (\S+)', line)
                        if match:
                            addresses.append(match.group(1))
                    elif 'inet6 ' in line:
                        match = re.search(r'inet6 (\S+)', line)
                        if match:
                            addresses.append(match.group(1))
        except Exception as e:
            self.logger.debug(f"Could not get IP addresses for {interface}: {e}")

        return addresses

    def get_system_info(self) -> Dict[str, Any]:
        """
        Get general system information.

        Returns:
            Dictionary containing system information
        """
        info = {
            'hostname': '',
            'kernel': '',
            'distribution': '',
            'uptime': '',
            'memory_total': 0,
            'memory_available': 0,
            'swap_total': 0,
            'swap_used': 0
        }

        try:
            # Hostname
            with open('/etc/hostname') as f:
                info['hostname'] = f.read().strip()
        except Exception:
            pass

        try:
            # Kernel
            result = subprocess.run(['uname', '-r'], capture_output=True, text=True)
            info['kernel'] = result.stdout.strip()
        except Exception:
            pass

        try:
            # Distribution
            with open('/etc/os-release') as f:
                for line in f:
                    if line.startswith('PRETTY_NAME='):
                        info['distribution'] = line.split('=')[1].strip().strip('"')
                        break
        except Exception:
            pass

        try:
            # Memory
            with open('/proc/meminfo') as f:
                for line in f:
                    if 'MemTotal:' in line:
                        info['memory_total'] = int(line.split()[1]) * 1024
                    elif 'MemAvailable:' in line:
                        info['memory_available'] = int(line.split()[1]) * 1024
                    elif 'SwapTotal:' in line:
                        info['swap_total'] = int(line.split()[1]) * 1024
                    elif 'SwapFree:' in line:
                        swap_free = int(line.split()[1]) * 1024
                        info['swap_used'] = info['swap_total'] - swap_free
        except Exception:
            pass

        try:
            # Uptime
            with open('/proc/uptime') as f:
                uptime_seconds = float(f.read().split()[0])
                days = int(uptime_seconds // 86400)
                hours = int((uptime_seconds % 86400) // 3600)
                minutes = int((uptime_seconds % 3600) // 60)
                info['uptime'] = f"{days}d {hours}h {minutes}m"
        except Exception:
            pass

        return info


if __name__ == '__main__':
    # Test the detector
    import json

    logging.basicConfig(level=logging.DEBUG)
    detector = HardwareDetector()

    print("=== Hardware Detection ===\n")

    print("--- CPU ---")
    cpu = detector.detect_cpu()
    print(json.dumps(cpu, indent=2))

    print("\n--- Storage ---")
    storage = detector.detect_storage()
    print(json.dumps(storage, indent=2))

    print("\n--- Network ---")
    network = detector.detect_network()
    print(json.dumps(network, indent=2))

    print("\n--- System ---")
    system = detector.get_system_info()
    print(json.dumps(system, indent=2))
