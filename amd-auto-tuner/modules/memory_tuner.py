#!/usr/bin/env python3
"""
Memory Tuner Module
Optimizes memory subsystem including HBM3, NUMA, DDR5, and memory bandwidth
Designed for AMD EPYC and Threadripper with advanced memory configurations
"""

import json
import os
import subprocess
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import logging


class MemoryTuner:
    """Handles memory subsystem optimization including HBM3 and DDR5."""

    def __init__(self, backup_dir: Path):
        """
        Initialize the memory tuner.

        Args:
            backup_dir: Directory to store configuration backups
        """
        self.logger = logging.getLogger('AMDAutoTuner.MemoryTuner')
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)

    def get_current_settings(self) -> Dict[str, Any]:
        """
        Get current memory subsystem settings.

        Returns:
            Dictionary containing current memory configuration
        """
        settings = {
            'memory_info': self._get_memory_info(),
            'numa_topology': self._get_numa_topology(),
            'hbm_info': self._get_hbm_info(),
            'memory_bandwidth': self._estimate_memory_bandwidth(),
            'cache_info': self._get_cache_info(),
            'vm_settings': self._get_vm_settings(),
            'memory_controllers': self._get_memory_controller_info()
        }
        return settings

    def _get_memory_info(self) -> Dict[str, Any]:
        """Get detailed memory information."""
        info = {
            'total_kb': 0,
            'available_kb': 0,
            'cached_kb': 0,
            'buffers_kb': 0,
            'swap_total_kb': 0,
            'swap_free_kb': 0,
            'huge_pages_total': 0,
            'huge_pages_free': 0,
            'huge_page_size_kb': 0,
            'direct_map_4k': 0,
            'direct_map_2m': 0,
            'direct_map_1g': 0
        }

        try:
            meminfo = Path('/proc/meminfo').read_text()
            for line in meminfo.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip()
                    value = value.strip().split()[0] if value.strip() else '0'

                    if key == 'MemTotal':
                        info['total_kb'] = int(value)
                    elif key == 'MemAvailable':
                        info['available_kb'] = int(value)
                    elif key == 'Cached':
                        info['cached_kb'] = int(value)
                    elif key == 'Buffers':
                        info['buffers_kb'] = int(value)
                    elif key == 'SwapTotal':
                        info['swap_total_kb'] = int(value)
                    elif key == 'SwapFree':
                        info['swap_free_kb'] = int(value)
                    elif key == 'HugePages_Total':
                        info['huge_pages_total'] = int(value)
                    elif key == 'HugePages_Free':
                        info['huge_pages_free'] = int(value)
                    elif key == 'Hugepagesize':
                        info['huge_page_size_kb'] = int(value)
                    elif key == 'DirectMap4k':
                        info['direct_map_4k'] = int(value)
                    elif key == 'DirectMap2M':
                        info['direct_map_2m'] = int(value)
                    elif key == 'DirectMap1G':
                        info['direct_map_1g'] = int(value)
        except Exception as e:
            self.logger.debug(f"Could not read meminfo: {e}")

        return info

    def _get_numa_topology(self) -> Dict[str, Any]:
        """Get NUMA memory topology."""
        info = {
            'available': False,
            'nodes': [],
            'interleaving': False,
            'memory_mode': 'unknown'
        }

        try:
            numa_path = Path('/sys/devices/system/node')
            if numa_path.exists():
                nodes = sorted([d for d in numa_path.iterdir() if d.name.startswith('node')])
                info['available'] = len(nodes) > 0

                for node in nodes:
                    node_id = int(node.name.replace('node', ''))
                    node_info = {
                        'id': node_id,
                        'cpus': '',
                        'memory_total_kb': 0,
                        'memory_free_kb': 0,
                        'distance': []
                    }

                    # CPUs
                    cpulist_path = node / 'cpulist'
                    if cpulist_path.exists():
                        node_info['cpus'] = cpulist_path.read_text().strip()

                    # Memory
                    meminfo_path = node / 'meminfo'
                    if meminfo_path.exists():
                        for line in meminfo_path.read_text().split('\n'):
                            if 'MemTotal' in line:
                                match = re.search(r'(\d+)', line)
                                if match:
                                    node_info['memory_total_kb'] = int(match.group(1))
                            elif 'MemFree' in line:
                                match = re.search(r'(\d+)', line)
                                if match:
                                    node_info['memory_free_kb'] = int(match.group(1))

                    # Distance
                    distance_path = node / 'distance'
                    if distance_path.exists():
                        node_info['distance'] = [int(x) for x in distance_path.read_text().strip().split()]

                    info['nodes'].append(node_info)

            # Check memory interleaving
            result = subprocess.run(
                ['numactl', '--show'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                if 'interleave' in result.stdout.lower():
                    info['interleaving'] = True

        except Exception as e:
            self.logger.debug(f"Could not get NUMA topology: {e}")

        return info

    def _get_hbm_info(self) -> Dict[str, Any]:
        """
        Get High Bandwidth Memory (HBM3) information.
        HBM appears as special NUMA nodes on AMD MI300A and similar accelerators.
        """
        info = {
            'available': False,
            'type': 'unknown',
            'nodes': [],
            'total_capacity_gb': 0,
            'bandwidth_gbps': 0
        }

        try:
            # Check for AMD MI300A or similar with HBM
            lspci_result = subprocess.run(
                ['lspci', '-v'],
                capture_output=True, text=True, timeout=10
            )

            if lspci_result.returncode == 0:
                output = lspci_result.stdout.lower()
                if 'mi300' in output or 'mi250' in output or 'hbm' in output:
                    info['available'] = True
                    if 'mi300a' in output:
                        info['type'] = 'HBM3'
                        info['bandwidth_gbps'] = 5300  # MI300A HBM3 theoretical
                    elif 'mi250' in output:
                        info['type'] = 'HBM2e'
                        info['bandwidth_gbps'] = 3200

            # Check NUMA nodes for HBM (typically high-bandwidth, separate nodes)
            numa_path = Path('/sys/devices/system/node')
            if numa_path.exists():
                nodes = [d for d in numa_path.iterdir() if d.name.startswith('node')]

                # HBM nodes typically have much higher bandwidth and specific patterns
                for node in nodes:
                    meminfo_path = node / 'meminfo'
                    if meminfo_path.exists():
                        content = meminfo_path.read_text()
                        # Large memory capacity with specific patterns might indicate HBM
                        # This is a heuristic - actual detection depends on system

            # Check for CXL memory devices (may include HBM-like devices)
            cxl_path = Path('/sys/bus/cxl/devices')
            if cxl_path.exists():
                for device in cxl_path.iterdir():
                    if device.is_dir():
                        info['cxl_devices'] = True

        except Exception as e:
            self.logger.debug(f"Could not detect HBM: {e}")

        return info

    def _estimate_memory_bandwidth(self) -> Dict[str, Any]:
        """Estimate memory bandwidth capabilities."""
        info = {
            'estimated_bandwidth_gbps': 0,
            'channels': 0,
            'type': 'unknown',
            'speed_mts': 0
        }

        try:
            # Try to get memory info from dmidecode
            result = subprocess.run(
                ['dmidecode', '-t', 'memory'],
                capture_output=True, text=True, timeout=10
            )

            if result.returncode == 0:
                output = result.stdout
                speed_matches = re.findall(r'Speed:\s*(\d+)\s*MT/s', output)
                type_match = re.search(r'Type:\s*(DDR\d+|HBM\d*)', output)
                channel_count = output.count('Locator:')

                if speed_matches:
                    info['speed_mts'] = max(int(s) for s in speed_matches)

                if type_match:
                    info['type'] = type_match.group(1)

                info['channels'] = channel_count

                # Estimate bandwidth: channels * speed * 8 bytes / 1000 (for GB/s)
                if info['speed_mts'] > 0 and info['channels'] > 0:
                    # Assuming 64-bit channels
                    info['estimated_bandwidth_gbps'] = (
                        info['channels'] * info['speed_mts'] * 8 / 1000
                    )

        except Exception as e:
            self.logger.debug(f"Could not estimate bandwidth: {e}")

        return info

    def _get_cache_info(self) -> Dict[str, Any]:
        """Get CPU cache information."""
        info = {
            'l1d_size': '',
            'l1i_size': '',
            'l2_size': '',
            'l3_size': '',
            'l3_per_ccx': ''
        }

        try:
            result = subprocess.run(['lscpu'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'L1d cache:' in line:
                        info['l1d_size'] = line.split(':')[1].strip()
                    elif 'L1i cache:' in line:
                        info['l1i_size'] = line.split(':')[1].strip()
                    elif 'L2 cache:' in line:
                        info['l2_size'] = line.split(':')[1].strip()
                    elif 'L3 cache:' in line:
                        info['l3_size'] = line.split(':')[1].strip()
        except Exception as e:
            self.logger.debug(f"Could not get cache info: {e}")

        return info

    def _get_vm_settings(self) -> Dict[str, Any]:
        """Get virtual memory settings."""
        settings = {}

        vm_params = [
            'swappiness', 'dirty_ratio', 'dirty_background_ratio',
            'dirty_expire_centisecs', 'dirty_writeback_centisecs',
            'vfs_cache_pressure', 'min_free_kbytes', 'zone_reclaim_mode',
            'overcommit_memory', 'overcommit_ratio', 'page-cluster',
            'compact_memory', 'drop_caches'
        ]

        for param in vm_params:
            path = Path(f'/proc/sys/vm/{param}')
            if path.exists():
                try:
                    settings[param] = path.read_text().strip()
                except Exception:
                    pass

        return settings

    def _get_memory_controller_info(self) -> Dict[str, Any]:
        """Get memory controller information from EDAC."""
        info = {
            'controllers': [],
            'errors_corrected': 0,
            'errors_uncorrected': 0
        }

        try:
            edac_path = Path('/sys/devices/system/edac/mc')
            if edac_path.exists():
                for mc in edac_path.iterdir():
                    if mc.is_dir() and mc.name.startswith('mc'):
                        mc_info = {
                            'name': mc.name,
                            'size_mb': 0,
                            'ce_count': 0,
                            'ue_count': 0
                        }

                        size_path = mc / 'size_mb'
                        if size_path.exists():
                            mc_info['size_mb'] = int(size_path.read_text().strip())

                        ce_path = mc / 'ce_count'
                        if ce_path.exists():
                            mc_info['ce_count'] = int(ce_path.read_text().strip())
                            info['errors_corrected'] += mc_info['ce_count']

                        ue_path = mc / 'ue_count'
                        if ue_path.exists():
                            mc_info['ue_count'] = int(ue_path.read_text().strip())
                            info['errors_uncorrected'] += mc_info['ue_count']

                        info['controllers'].append(mc_info)

        except Exception as e:
            self.logger.debug(f"Could not get memory controller info: {e}")

        return info

    def create_backup(self) -> str:
        """Create a backup of current memory settings."""
        settings = self._get_vm_settings()
        settings['timestamp'] = datetime.now().isoformat()

        backup_file = self.backup_dir / f"memory_backup_{datetime.now():%Y%m%d_%H%M%S}.json"

        with open(backup_file, 'w') as f:
            json.dump(settings, f, indent=2)

        self.logger.info(f"Memory backup created: {backup_file}")
        return str(backup_file)

    def restore_backup(self, backup_file: Optional[str] = None) -> Dict[str, Any]:
        """Restore memory settings from backup."""
        if backup_file is None:
            backups = list(self.backup_dir.glob('memory_backup_*.json'))
            if not backups:
                return {'success': False, 'error': 'No backup found'}
            backup_file = str(max(backups, key=lambda x: x.stat().st_mtime))

        try:
            with open(backup_file) as f:
                settings = json.load(f)

            results = {'success': True, 'changes': []}

            # Restore VM settings
            vm_params = ['swappiness', 'dirty_ratio', 'dirty_background_ratio',
                        'vfs_cache_pressure', 'min_free_kbytes']

            for param in vm_params:
                if param in settings:
                    if self._set_vm_param(param, settings[param]):
                        results['changes'].append(f"Restored vm.{param}: {settings[param]}")

            self.logger.info(f"Restored memory settings from {backup_file}")
            return results
        except Exception as e:
            self.logger.error(f"Failed to restore backup: {e}")
            return {'success': False, 'error': str(e)}

    def apply_profile(self, settings: Dict[str, Any], hardware_info: Dict[str, Any],
                      dry_run: bool = False) -> Dict[str, Any]:
        """
        Apply memory tuning settings.

        Args:
            settings: Memory settings to apply
            hardware_info: Current hardware information
            dry_run: If True, only simulate changes

        Returns:
            Dictionary containing applied changes
        """
        changes = {
            'applied': [],
            'skipped': [],
            'errors': []
        }

        if not dry_run:
            try:
                self.create_backup()
            except Exception as e:
                self.logger.warning(f"Could not create backup: {e}")

        # VM settings
        vm_params = {
            'swappiness': settings.get('vm_swappiness'),
            'dirty_ratio': settings.get('vm_dirty_ratio'),
            'dirty_background_ratio': settings.get('vm_dirty_background_ratio'),
            'vfs_cache_pressure': settings.get('vm_vfs_cache_pressure'),
            'min_free_kbytes': settings.get('vm_min_free_kbytes'),
            'zone_reclaim_mode': settings.get('zone_reclaim_mode')
        }

        for param, value in vm_params.items():
            if value is not None:
                if dry_run:
                    changes['applied'].append(f"Would set vm.{param}: {value}")
                else:
                    if self._set_vm_param(param, str(value)):
                        changes['applied'].append(f"Set vm.{param}: {value}")
                    else:
                        changes['errors'].append(f"Failed to set vm.{param}")

        # NUMA settings
        if 'numa_balancing' in settings:
            val = '1' if settings['numa_balancing'] else '0'
            if dry_run:
                changes['applied'].append(f"Would set numa_balancing: {val}")
            else:
                if self._set_sysctl('kernel.numa_balancing', val):
                    changes['applied'].append(f"Set numa_balancing: {val}")
                else:
                    changes['errors'].append("Failed to set numa_balancing")

        # Memory compaction
        if settings.get('compact_memory', False):
            if dry_run:
                changes['applied'].append("Would trigger memory compaction")
            else:
                if self._trigger_memory_compaction():
                    changes['applied'].append("Triggered memory compaction")
                else:
                    changes['skipped'].append("Memory compaction not available")

        # Drop caches
        if settings.get('drop_caches'):
            level = settings['drop_caches']
            if dry_run:
                changes['applied'].append(f"Would drop caches (level {level})")
            else:
                if self._drop_caches(level):
                    changes['applied'].append(f"Dropped caches (level {level})")
                else:
                    changes['errors'].append("Failed to drop caches")

        return changes

    def _set_vm_param(self, param: str, value: str) -> bool:
        """Set a VM parameter."""
        try:
            path = Path(f'/proc/sys/vm/{param}')
            if path.exists():
                path.write_text(value)
                return True
        except Exception as e:
            self.logger.error(f"Failed to set vm.{param}: {e}")
        return False

    def _set_sysctl(self, key: str, value: str) -> bool:
        """Set a sysctl value."""
        try:
            result = subprocess.run(
                ['sysctl', '-w', f'{key}={value}'],
                capture_output=True, timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def _trigger_memory_compaction(self) -> bool:
        """Trigger memory compaction."""
        try:
            path = Path('/proc/sys/vm/compact_memory')
            if path.exists():
                path.write_text('1')
                return True
        except Exception:
            pass
        return False

    def _drop_caches(self, level: int = 3) -> bool:
        """
        Drop page caches.

        Args:
            level: 1=page cache, 2=dentries/inodes, 3=all
        """
        try:
            # Sync first
            subprocess.run(['sync'], timeout=30)
            path = Path('/proc/sys/vm/drop_caches')
            if path.exists():
                path.write_text(str(level))
                return True
        except Exception:
            pass
        return False

    def optimize_for_workload(self, workload: str, dry_run: bool = False) -> Dict[str, Any]:
        """
        Optimize memory for specific workload.

        Args:
            workload: 'hpc', 'database', 'virtualization', 'streaming', 'desktop'
            dry_run: If True, only simulate changes

        Returns:
            Dictionary containing applied changes
        """
        profiles = {
            'hpc': {
                'vm_swappiness': 1,
                'vm_dirty_ratio': 40,
                'vm_dirty_background_ratio': 10,
                'vm_vfs_cache_pressure': 50,
                'zone_reclaim_mode': 0,
                'numa_balancing': False  # For consistent performance
            },
            'database': {
                'vm_swappiness': 10,
                'vm_dirty_ratio': 15,
                'vm_dirty_background_ratio': 5,
                'vm_vfs_cache_pressure': 50,
                'zone_reclaim_mode': 0
            },
            'virtualization': {
                'vm_swappiness': 10,
                'vm_dirty_ratio': 20,
                'vm_dirty_background_ratio': 5,
                'vm_vfs_cache_pressure': 100,
                'zone_reclaim_mode': 0
            },
            'streaming': {
                'vm_swappiness': 10,
                'vm_dirty_ratio': 80,
                'vm_dirty_background_ratio': 50,
                'vm_vfs_cache_pressure': 100
            },
            'desktop': {
                'vm_swappiness': 60,
                'vm_dirty_ratio': 20,
                'vm_dirty_background_ratio': 10,
                'vm_vfs_cache_pressure': 100
            }
        }

        if workload not in profiles:
            raise ValueError(f"Unknown workload: {workload}. Options: {list(profiles.keys())}")

        return self.apply_profile(profiles[workload], {}, dry_run=dry_run)

    def get_optimization_recommendations(self) -> List[Dict[str, str]]:
        """
        Get memory optimization recommendations based on current state.

        Returns:
            List of recommendation dictionaries
        """
        recommendations = []
        settings = self.get_current_settings()
        mem_info = settings['memory_info']
        vm_settings = settings['vm_settings']
        numa_topo = settings['numa_topology']

        # Check swap usage
        if mem_info['swap_total_kb'] > 0:
            swap_used = mem_info['swap_total_kb'] - mem_info.get('swap_free_kb', 0)
            if swap_used > mem_info['swap_total_kb'] * 0.5:
                recommendations.append({
                    'area': 'swap',
                    'issue': 'High swap usage detected',
                    'recommendation': 'Consider adding more RAM or reducing vm.swappiness',
                    'command': 'sysctl vm.swappiness=10'
                })

        # Check huge pages
        if mem_info['huge_pages_total'] == 0:
            recommendations.append({
                'area': 'huge_pages',
                'issue': 'No huge pages configured',
                'recommendation': 'Enable huge pages for large memory workloads',
                'command': 'echo 1024 > /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages'
            })

        # Check NUMA configuration
        if numa_topo['available'] and len(numa_topo['nodes']) > 1:
            recommendations.append({
                'area': 'numa',
                'issue': 'Multi-NUMA system detected',
                'recommendation': 'Use numactl for NUMA-aware process placement',
                'command': 'numactl --interleave=all <command> OR numactl --cpunodebind=0 --membind=0 <command>'
            })

        # Check memory bandwidth utilization hints
        bandwidth_info = settings['memory_bandwidth']
        if bandwidth_info.get('type') == 'DDR5' and bandwidth_info.get('channels', 0) < 4:
            recommendations.append({
                'area': 'bandwidth',
                'issue': 'Limited memory channels',
                'recommendation': 'Consider populating more DIMM slots for higher bandwidth'
            })

        return recommendations


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    tuner = MemoryTuner(Path('/tmp/memory_backup'))

    print("=== Memory Settings ===")
    settings = tuner.get_current_settings()
    print(json.dumps(settings, indent=2))

    print("\n=== Recommendations ===")
    for rec in tuner.get_optimization_recommendations():
        print(f"\n[{rec['area']}]")
        print(f"  Issue: {rec['issue']}")
        print(f"  Recommendation: {rec['recommendation']}")
        if 'command' in rec:
            print(f"  Command: {rec['command']}")
