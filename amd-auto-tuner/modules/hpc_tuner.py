#!/usr/bin/env python3
"""
HPC Tuner Module
Optimizes system for High Performance Computing workloads
Includes NUMA, huge pages, process affinity, and MPI optimizations
"""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import logging


class HPCTuner:
    """Handles High Performance Computing optimizations for AMD processors."""

    def __init__(self, backup_dir: Path):
        """
        Initialize the HPC tuner.

        Args:
            backup_dir: Directory to store configuration backups
        """
        self.logger = logging.getLogger('AMDAutoTuner.HPCTuner')
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)

        self.sys_path = Path('/sys')
        self.proc_path = Path('/proc')

    def get_current_settings(self) -> Dict[str, Any]:
        """
        Get current HPC-related settings.

        Returns:
            Dictionary containing current HPC configuration
        """
        settings = {
            'numa': self._get_numa_info(),
            'huge_pages': self._get_huge_pages_info(),
            'transparent_hugepages': self._get_thp_status(),
            'cpu_affinity': self._get_irq_affinity_info(),
            'scheduler': self._get_scheduler_info(),
            'memory': self._get_memory_info(),
            'kernel_params': self._get_kernel_params()
        }
        return settings

    def _get_numa_info(self) -> Dict[str, Any]:
        """Get NUMA topology information."""
        info = {
            'available': False,
            'nodes': 0,
            'node_cpus': {},
            'node_memory': {},
            'distances': []
        }

        numa_path = Path('/sys/devices/system/node')
        if not numa_path.exists():
            return info

        try:
            nodes = [d for d in numa_path.iterdir() if d.name.startswith('node')]
            info['available'] = len(nodes) > 0
            info['nodes'] = len(nodes)

            for node in nodes:
                node_id = node.name.replace('node', '')

                # CPUs in this node
                cpulist_path = node / 'cpulist'
                if cpulist_path.exists():
                    info['node_cpus'][node_id] = cpulist_path.read_text().strip()

                # Memory in this node
                meminfo_path = node / 'meminfo'
                if meminfo_path.exists():
                    meminfo = {}
                    for line in meminfo_path.read_text().split('\n'):
                        if ':' in line:
                            key, value = line.split(':', 1)
                            key = key.strip().replace(f'Node {node_id} ', '')
                            meminfo[key] = value.strip()
                    info['node_memory'][node_id] = meminfo

            # NUMA distances
            result = subprocess.run(
                ['numactl', '--hardware'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'node distances' in line.lower():
                        continue
                    if line.strip().startswith('node'):
                        continue
                    if line.strip() and ':' not in line:
                        info['distances'].append(line.strip().split())

        except Exception as e:
            self.logger.debug(f"Could not get NUMA info: {e}")

        return info

    def _get_huge_pages_info(self) -> Dict[str, Any]:
        """Get huge pages configuration."""
        info = {
            'total_2mb': 0,
            'free_2mb': 0,
            'total_1gb': 0,
            'free_1gb': 0,
            'reserved': 0
        }

        try:
            # 2MB huge pages
            hp_path = Path('/sys/kernel/mm/hugepages/hugepages-2048kB')
            if hp_path.exists():
                nr_path = hp_path / 'nr_hugepages'
                free_path = hp_path / 'free_hugepages'
                if nr_path.exists():
                    info['total_2mb'] = int(nr_path.read_text().strip())
                if free_path.exists():
                    info['free_2mb'] = int(free_path.read_text().strip())

            # 1GB huge pages
            hp_1g_path = Path('/sys/kernel/mm/hugepages/hugepages-1048576kB')
            if hp_1g_path.exists():
                nr_path = hp_1g_path / 'nr_hugepages'
                free_path = hp_1g_path / 'free_hugepages'
                if nr_path.exists():
                    info['total_1gb'] = int(nr_path.read_text().strip())
                if free_path.exists():
                    info['free_1gb'] = int(free_path.read_text().strip())

            # Reserved huge pages
            meminfo = Path('/proc/meminfo').read_text()
            for line in meminfo.split('\n'):
                if 'HugePages_Rsvd' in line:
                    info['reserved'] = int(line.split()[1])

        except Exception as e:
            self.logger.debug(f"Could not get huge pages info: {e}")

        return info

    def _get_thp_status(self) -> Dict[str, str]:
        """Get transparent huge pages status."""
        info = {
            'enabled': 'unknown',
            'defrag': 'unknown'
        }

        try:
            enabled_path = Path('/sys/kernel/mm/transparent_hugepage/enabled')
            if enabled_path.exists():
                content = enabled_path.read_text().strip()
                # Format: always [madvise] never - bracketed is current
                import re
                match = re.search(r'\[(\w+)\]', content)
                if match:
                    info['enabled'] = match.group(1)

            defrag_path = Path('/sys/kernel/mm/transparent_hugepage/defrag')
            if defrag_path.exists():
                content = defrag_path.read_text().strip()
                match = re.search(r'\[(\w+)\]', content)
                if match:
                    info['defrag'] = match.group(1)

        except Exception as e:
            self.logger.debug(f"Could not get THP status: {e}")

        return info

    def _get_irq_affinity_info(self) -> Dict[str, Any]:
        """Get IRQ affinity information."""
        info = {
            'irqbalance_running': False,
            'sample_irqs': {}
        }

        try:
            # Check if irqbalance is running
            result = subprocess.run(
                ['pgrep', 'irqbalance'],
                capture_output=True, timeout=5
            )
            info['irqbalance_running'] = result.returncode == 0

            # Sample a few IRQs
            irq_path = Path('/proc/irq')
            if irq_path.exists():
                irqs = list(irq_path.iterdir())[:10]  # Sample first 10
                for irq in irqs:
                    if irq.is_dir():
                        affinity_path = irq / 'smp_affinity_list'
                        if affinity_path.exists():
                            info['sample_irqs'][irq.name] = affinity_path.read_text().strip()

        except Exception as e:
            self.logger.debug(f"Could not get IRQ affinity info: {e}")

        return info

    def _get_scheduler_info(self) -> Dict[str, Any]:
        """Get scheduler-related information."""
        info = {
            'rt_runtime_us': 0,
            'rt_period_us': 0,
            'sched_rr_timeslice_ms': 0,
            'migration_cost_ns': 0
        }

        try:
            for key, path in [
                ('rt_runtime_us', '/proc/sys/kernel/sched_rt_runtime_us'),
                ('rt_period_us', '/proc/sys/kernel/sched_rt_period_us'),
                ('sched_rr_timeslice_ms', '/proc/sys/kernel/sched_rr_timeslice_ms'),
                ('migration_cost_ns', '/proc/sys/kernel/sched_migration_cost_ns')
            ]:
                p = Path(path)
                if p.exists():
                    info[key] = int(p.read_text().strip())
        except Exception as e:
            self.logger.debug(f"Could not get scheduler info: {e}")

        return info

    def _get_memory_info(self) -> Dict[str, Any]:
        """Get memory subsystem information."""
        info = {
            'vm_swappiness': 60,
            'vm_dirty_ratio': 20,
            'vm_dirty_background_ratio': 10,
            'vm_vfs_cache_pressure': 100,
            'zone_reclaim_mode': 0
        }

        try:
            for key, path in [
                ('vm_swappiness', '/proc/sys/vm/swappiness'),
                ('vm_dirty_ratio', '/proc/sys/vm/dirty_ratio'),
                ('vm_dirty_background_ratio', '/proc/sys/vm/dirty_background_ratio'),
                ('vm_vfs_cache_pressure', '/proc/sys/vm/vfs_cache_pressure'),
                ('zone_reclaim_mode', '/proc/sys/vm/zone_reclaim_mode')
            ]:
                p = Path(path)
                if p.exists():
                    info[key] = int(p.read_text().strip())
        except Exception as e:
            self.logger.debug(f"Could not get memory info: {e}")

        return info

    def _get_kernel_params(self) -> Dict[str, str]:
        """Get HPC-relevant kernel parameters."""
        params = {}

        try:
            cmdline = Path('/proc/cmdline').read_text().strip()
            for param in cmdline.split():
                if '=' in param:
                    key, value = param.split('=', 1)
                    if any(x in key for x in ['numa', 'hugepages', 'isolcpus', 'nohz', 'rcu']):
                        params[key] = value
                else:
                    if any(x in param for x in ['numa', 'nohz']):
                        params[param] = 'set'
        except Exception as e:
            self.logger.debug(f"Could not get kernel params: {e}")

        return params

    def create_backup(self) -> str:
        """Create a backup of current HPC settings."""
        settings = self.get_current_settings()
        settings['timestamp'] = datetime.now().isoformat()

        backup_file = self.backup_dir / f"hpc_backup_{datetime.now():%Y%m%d_%H%M%S}.json"

        with open(backup_file, 'w') as f:
            json.dump(settings, f, indent=2)

        self.logger.info(f"HPC backup created: {backup_file}")
        return str(backup_file)

    def restore_backup(self, backup_file: Optional[str] = None) -> Dict[str, Any]:
        """Restore HPC settings from backup."""
        if backup_file is None:
            backups = list(self.backup_dir.glob('hpc_backup_*.json'))
            if not backups:
                return {'success': False, 'error': 'No backup found'}
            backup_file = str(max(backups, key=lambda x: x.stat().st_mtime))

        try:
            with open(backup_file) as f:
                settings = json.load(f)

            results = {'success': True, 'changes': []}

            # Restore huge pages
            if 'huge_pages' in settings:
                hp = settings['huge_pages']
                if hp.get('total_2mb', 0) > 0:
                    self._set_huge_pages(hp['total_2mb'], '2M')
                    results['changes'].append(f"Restored 2MB huge pages: {hp['total_2mb']}")

            # Restore THP
            if 'transparent_hugepages' in settings:
                thp = settings['transparent_hugepages']
                if thp.get('enabled'):
                    self._set_transparent_hugepages(thp['enabled'])
                    results['changes'].append(f"Restored THP: {thp['enabled']}")

            # Restore memory settings
            if 'memory' in settings:
                mem = settings['memory']
                if 'vm_swappiness' in mem:
                    self._set_sysctl('vm.swappiness', str(mem['vm_swappiness']))

            self.logger.info(f"Restored HPC settings from {backup_file}")
            return results
        except Exception as e:
            self.logger.error(f"Failed to restore backup: {e}")
            return {'success': False, 'error': str(e)}

    def apply_profile(self, settings: Dict[str, Any], hardware_info: Dict[str, Any],
                      dry_run: bool = False) -> Dict[str, Any]:
        """
        Apply HPC tuning settings.

        Args:
            settings: HPC settings to apply
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

        # Configure NUMA
        if settings.get('numa_balancing') is not None:
            numa_val = '1' if settings['numa_balancing'] else '0'
            if dry_run:
                changes['applied'].append(f"Would set NUMA balancing: {numa_val}")
            else:
                if self._set_sysctl('kernel.numa_balancing', numa_val):
                    changes['applied'].append(f"Set NUMA balancing: {numa_val}")
                else:
                    changes['errors'].append("Failed to set NUMA balancing")

        # Configure huge pages
        if 'huge_pages_2mb' in settings:
            count = settings['huge_pages_2mb']
            if dry_run:
                changes['applied'].append(f"Would allocate {count} 2MB huge pages")
            else:
                if self._set_huge_pages(count, '2M'):
                    changes['applied'].append(f"Allocated {count} 2MB huge pages")
                else:
                    changes['errors'].append("Failed to allocate 2MB huge pages")

        if 'huge_pages_1gb' in settings:
            count = settings['huge_pages_1gb']
            if dry_run:
                changes['applied'].append(f"Would allocate {count} 1GB huge pages")
            else:
                if self._set_huge_pages(count, '1G'):
                    changes['applied'].append(f"Allocated {count} 1GB huge pages")
                else:
                    changes['skipped'].append("1GB huge pages may require boot-time allocation")

        # Configure THP
        if 'transparent_hugepages' in settings:
            thp = settings['transparent_hugepages']
            if dry_run:
                changes['applied'].append(f"Would set THP: {thp}")
            else:
                if self._set_transparent_hugepages(thp):
                    changes['applied'].append(f"Set THP: {thp}")
                else:
                    changes['errors'].append("Failed to set THP")

        # Configure memory settings
        if 'vm_swappiness' in settings:
            val = str(settings['vm_swappiness'])
            if dry_run:
                changes['applied'].append(f"Would set vm.swappiness: {val}")
            else:
                if self._set_sysctl('vm.swappiness', val):
                    changes['applied'].append(f"Set vm.swappiness: {val}")
                else:
                    changes['errors'].append("Failed to set vm.swappiness")

        if 'zone_reclaim_mode' in settings:
            val = str(settings['zone_reclaim_mode'])
            if dry_run:
                changes['applied'].append(f"Would set zone_reclaim_mode: {val}")
            else:
                if self._set_sysctl('vm.zone_reclaim_mode', val):
                    changes['applied'].append(f"Set zone_reclaim_mode: {val}")
                else:
                    changes['errors'].append("Failed to set zone_reclaim_mode")

        # Disable IRQ balance for dedicated HPC
        if settings.get('disable_irqbalance', False):
            if dry_run:
                changes['applied'].append("Would disable irqbalance service")
            else:
                if self._stop_service('irqbalance'):
                    changes['applied'].append("Disabled irqbalance service")
                else:
                    changes['skipped'].append("irqbalance service not running or not found")

        return changes

    def _set_huge_pages(self, count: int, size: str) -> bool:
        """Set number of huge pages."""
        try:
            if size == '2M':
                path = Path('/sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages')
            elif size == '1G':
                path = Path('/sys/kernel/mm/hugepages/hugepages-1048576kB/nr_hugepages')
            else:
                return False

            if path.exists():
                path.write_text(str(count))
                return True
        except Exception as e:
            self.logger.error(f"Failed to set huge pages: {e}")
        return False

    def _set_transparent_hugepages(self, mode: str) -> bool:
        """Set transparent huge pages mode."""
        try:
            path = Path('/sys/kernel/mm/transparent_hugepage/enabled')
            if path.exists() and mode in ['always', 'madvise', 'never']:
                path.write_text(mode)
                return True
        except Exception as e:
            self.logger.error(f"Failed to set THP: {e}")
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

    def _stop_service(self, service: str) -> bool:
        """Stop a systemd service."""
        try:
            result = subprocess.run(
                ['systemctl', 'stop', service],
                capture_output=True, timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False

    def optimize_for_mpi(self, num_ranks: int, dry_run: bool = False) -> Dict[str, Any]:
        """
        Optimize system for MPI workloads.

        Args:
            num_ranks: Number of MPI ranks
            dry_run: If True, only simulate changes

        Returns:
            Dictionary containing recommended settings and applied changes
        """
        numa_info = self._get_numa_info()
        cpu_info = self._get_cpu_count()

        recommendations = {
            'ranks_per_node': num_ranks,
            'cpus_per_rank': cpu_info // num_ranks if num_ranks > 0 else cpu_info,
            'numa_nodes': numa_info['nodes'],
            'settings': []
        }

        # NUMA binding recommendations
        if numa_info['nodes'] > 1:
            recommendations['settings'].append({
                'name': 'NUMA binding',
                'command': f'mpirun --bind-to core --map-by numa -np {num_ranks} <program>',
                'description': 'Bind MPI ranks to cores within NUMA domains'
            })

        # Memory settings for MPI
        hpc_settings = {
            'numa_balancing': False,  # Disable for predictable performance
            'vm_swappiness': 1,  # Minimal swapping
            'zone_reclaim_mode': 0,  # Allow remote NUMA access
            'transparent_hugepages': 'madvise'  # Application-controlled
        }

        changes = self.apply_profile(hpc_settings, {}, dry_run=dry_run)
        recommendations['changes'] = changes

        return recommendations

    def _get_cpu_count(self) -> int:
        """Get total CPU count."""
        try:
            return os.cpu_count() or 1
        except Exception:
            return 1

    def generate_slurm_config(self, node_name: str = 'node01') -> str:
        """
        Generate recommended SLURM configuration snippet.

        Returns:
            SLURM configuration string
        """
        numa_info = self._get_numa_info()
        cpu_count = self._get_cpu_count()
        mem_info = self._get_memory_info()

        # Get total memory from /proc/meminfo
        total_mem_kb = 0
        try:
            for line in Path('/proc/meminfo').read_text().split('\n'):
                if 'MemTotal' in line:
                    total_mem_kb = int(line.split()[1])
                    break
        except Exception:
            pass

        total_mem_mb = total_mem_kb // 1024

        config = f"""# SLURM Node Configuration for AMD System
# Generated by AMD Auto Tuner

NodeName={node_name} CPUs={cpu_count} Sockets={numa_info['nodes']} CoresPerSocket={cpu_count // max(1, numa_info['nodes'])} ThreadsPerCore=2 RealMemory={total_mem_mb} State=UNKNOWN

# Partition Configuration
PartitionName=compute Nodes={node_name} Default=YES MaxTime=INFINITE State=UP

# Optional: CPU binding settings
# TaskPluginParam=Cores
# SelectType=select/cons_tres
# SelectTypeParameters=CR_Core_Memory
"""
        return config


if __name__ == '__main__':
    import json as json_module

    logging.basicConfig(level=logging.DEBUG)
    tuner = HPCTuner(Path('/tmp/hpc_backup'))

    print("=== HPC Settings ===")
    settings = tuner.get_current_settings()
    print(json_module.dumps(settings, indent=2))

    print("\n=== SLURM Config ===")
    print(tuner.generate_slurm_config())
