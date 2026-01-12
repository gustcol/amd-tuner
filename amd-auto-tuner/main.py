#!/usr/bin/env python3
"""
AMD Auto Tuner - Main Orchestrator
Automated performance tuning for AMD Ryzen/EPYC systems on Linux

This script orchestrates the detection, benchmarking, and tuning of:
- AMD CPU (governors, frequencies, boost, C-states, P-states)
- Storage devices (NVMe, SSD, HDD schedulers and parameters)
- Network interfaces (ring buffers, offloads, sysctl tuning)
- HPC workloads (NUMA, huge pages, MPI, SLURM integration)
- Memory subsystem (HBM3, DDR5, NUMA topology optimization)
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

# Add modules directory to path
sys.path.insert(0, str(Path(__file__).parent / 'modules'))

from hardware_detector import HardwareDetector
from cpu_tuner import CPUTuner
from storage_tuner import StorageTuner
from network_tuner import NetworkTuner
from benchmarker import Benchmarker
from config_manager import ConfigManager
from hpc_tuner import HPCTuner
from memory_tuner import MemoryTuner


class AMDAutoTuner:
    """Main orchestrator for AMD system performance tuning."""

    VERSION = "1.0.0"

    def __init__(self, config_path: Optional[str] = None, verbose: bool = False):
        """
        Initialize the AMD Auto Tuner.

        Args:
            config_path: Path to custom configuration file
            verbose: Enable verbose output
        """
        self.base_dir = Path(__file__).parent
        self.logs_dir = self.base_dir / 'logs'
        self.backups_dir = self.base_dir / 'backups'
        self.benchmarks_dir = self.base_dir / 'benchmarks'
        self.reports_dir = self.base_dir / 'reports'

        # Ensure directories exist
        for directory in [self.logs_dir, self.backups_dir,
                         self.benchmarks_dir, self.reports_dir]:
            directory.mkdir(exist_ok=True)

        # Setup logging
        self._setup_logging(verbose)

        # Load configuration
        self.config_manager = ConfigManager(config_path or self.base_dir / 'config' / 'config.yaml')
        self.config = self.config_manager.load()

        # Initialize components
        self.detector = HardwareDetector()
        self.cpu_tuner = CPUTuner(self.backups_dir)
        self.storage_tuner = StorageTuner(self.backups_dir)
        self.network_tuner = NetworkTuner(self.backups_dir)
        self.benchmarker = Benchmarker(self.benchmarks_dir)
        self.hpc_tuner = HPCTuner(self.backups_dir)
        self.memory_tuner = MemoryTuner(self.backups_dir)

        # Hardware info cache
        self._hardware_info: Optional[Dict[str, Any]] = None

        self.logger.info(f"AMD Auto Tuner v{self.VERSION} initialized")

    def _setup_logging(self, verbose: bool):
        """Configure logging with file and console handlers."""
        self.logger = logging.getLogger('AMDAutoTuner')
        self.logger.setLevel(logging.DEBUG if verbose else logging.INFO)

        # Clear existing handlers
        self.logger.handlers.clear()

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
        console_format = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_format)
        self.logger.addHandler(console_handler)

        # File handler
        log_file = self.logs_dir / f"amd_tuner_{datetime.now():%Y%m%d_%H%M%S}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_format)
        self.logger.addHandler(file_handler)

    @property
    def hardware_info(self) -> Dict[str, Any]:
        """Get cached hardware information or detect if not available."""
        if self._hardware_info is None:
            self._hardware_info = self.detector.detect_all()
        return self._hardware_info

    def detect_hardware(self) -> Dict[str, Any]:
        """
        Detect all system hardware.

        Returns:
            Dictionary containing CPU, storage, and network information
        """
        self.logger.info("Detecting system hardware...")
        self._hardware_info = self.detector.detect_all()

        # Log summary
        cpu = self._hardware_info.get('cpu', {})
        storage = self._hardware_info.get('storage', [])
        network = self._hardware_info.get('network', [])

        self.logger.info(f"CPU: {cpu.get('model', 'Unknown')} "
                        f"({cpu.get('cores', 0)} cores, {cpu.get('threads', 0)} threads)")
        self.logger.info(f"Storage devices: {len(storage)}")
        self.logger.info(f"Network interfaces: {len(network)}")

        return self._hardware_info

    def run_benchmarks(self, categories: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Run performance benchmarks.

        Args:
            categories: List of categories to benchmark ('cpu', 'storage', 'network')
                       If None, runs all benchmarks

        Returns:
            Dictionary containing benchmark results
        """
        if categories is None:
            categories = ['cpu', 'storage', 'network']

        self.logger.info(f"Running benchmarks: {', '.join(categories)}")

        results = {}

        if 'cpu' in categories:
            self.logger.info("Running CPU benchmarks...")
            results['cpu'] = self.benchmarker.benchmark_cpu()

        if 'storage' in categories:
            self.logger.info("Running storage benchmarks...")
            storage_devices = self.hardware_info.get('storage', [])
            results['storage'] = self.benchmarker.benchmark_storage(storage_devices)

        if 'network' in categories:
            self.logger.info("Running network benchmarks...")
            results['network'] = self.benchmarker.benchmark_network()

        # Save results
        results['timestamp'] = datetime.now().isoformat()
        self.benchmarker.save_results(results)

        return results

    def apply_profile(self, profile: str, dry_run: bool = False) -> Dict[str, Any]:
        """
        Apply a performance profile.

        Args:
            profile: Profile name ('performance', 'balanced', 'powersave', 'gaming', 'server', 'hpc')
            dry_run: If True, only show what would be changed without applying

        Returns:
            Dictionary containing applied changes
        """
        valid_profiles = ['performance', 'balanced', 'powersave', 'gaming', 'server', 'hpc']
        if profile not in valid_profiles:
            raise ValueError(f"Invalid profile: {profile}. Valid options: {valid_profiles}")

        self.logger.info(f"{'Simulating' if dry_run else 'Applying'} profile: {profile}")

        changes = {
            'profile': profile,
            'dry_run': dry_run,
            'timestamp': datetime.now().isoformat(),
            'cpu': {},
            'storage': {},
            'network': {},
            'hpc': {},
            'memory': {}
        }

        # Get profile configuration
        profile_config = self._get_profile_config(profile)

        # Apply CPU tuning
        if profile_config.get('cpu', {}).get('enabled', True):
            self.logger.info("Applying CPU tuning...")
            changes['cpu'] = self.cpu_tuner.apply_profile(
                profile_config['cpu'],
                self.hardware_info.get('cpu', {}),
                dry_run=dry_run
            )

        # Apply storage tuning
        if profile_config.get('storage', {}).get('enabled', True):
            self.logger.info("Applying storage tuning...")
            changes['storage'] = self.storage_tuner.apply_profile(
                profile_config['storage'],
                self.hardware_info.get('storage', []),
                dry_run=dry_run
            )

        # Apply network tuning
        if profile_config.get('network', {}).get('enabled', True):
            self.logger.info("Applying network tuning...")
            changes['network'] = self.network_tuner.apply_profile(
                profile_config['network'],
                self.hardware_info.get('network', []),
                dry_run=dry_run
            )

        # Apply HPC tuning (for hpc and server profiles)
        if profile_config.get('hpc', {}).get('enabled', False):
            self.logger.info("Applying HPC tuning...")
            changes['hpc'] = self.hpc_tuner.apply_profile(
                profile_config['hpc'],
                self.hardware_info,
                dry_run=dry_run
            )

        # Apply memory tuning
        if profile_config.get('memory', {}).get('enabled', False):
            self.logger.info("Applying memory tuning...")
            changes['memory'] = self.memory_tuner.apply_profile(
                profile_config['memory'],
                self.hardware_info,
                dry_run=dry_run
            )

        # Save report
        self._save_report(changes)

        return changes

    def _get_profile_config(self, profile: str) -> Dict[str, Any]:
        """Get configuration for a specific profile."""
        profiles = {
            'performance': {
                'cpu': {
                    'enabled': True,
                    'governor': 'performance',
                    'boost': True,
                    'min_freq_percent': 80,
                    'max_freq_percent': 100,
                    'c6_disable': True,
                    'energy_performance': 'performance'
                },
                'storage': {
                    'enabled': True,
                    'nvme_scheduler': 'none',
                    'ssd_scheduler': 'mq-deadline',
                    'hdd_scheduler': 'bfq',
                    'read_ahead_kb': 256,
                    'nr_requests': 256
                },
                'network': {
                    'enabled': True,
                    'ring_buffer_max': True,
                    'offloads': True,
                    'interrupt_coalescing': True,
                    'congestion_control': 'bbr',
                    'optimize_sysctl': True
                }
            },
            'balanced': {
                'cpu': {
                    'enabled': True,
                    'governor': 'schedutil',
                    'boost': True,
                    'min_freq_percent': 40,
                    'max_freq_percent': 100,
                    'c6_disable': False,
                    'energy_performance': 'balance_performance'
                },
                'storage': {
                    'enabled': True,
                    'nvme_scheduler': 'none',
                    'ssd_scheduler': 'mq-deadline',
                    'hdd_scheduler': 'bfq',
                    'read_ahead_kb': 128,
                    'nr_requests': 128
                },
                'network': {
                    'enabled': True,
                    'ring_buffer_max': False,
                    'offloads': True,
                    'interrupt_coalescing': True,
                    'congestion_control': 'bbr',
                    'optimize_sysctl': True
                }
            },
            'powersave': {
                'cpu': {
                    'enabled': True,
                    'governor': 'powersave',
                    'boost': False,
                    'min_freq_percent': 20,
                    'max_freq_percent': 70,
                    'c6_disable': False,
                    'energy_performance': 'power'
                },
                'storage': {
                    'enabled': True,
                    'nvme_scheduler': 'none',
                    'ssd_scheduler': 'mq-deadline',
                    'hdd_scheduler': 'bfq',
                    'read_ahead_kb': 64,
                    'nr_requests': 64
                },
                'network': {
                    'enabled': True,
                    'ring_buffer_max': False,
                    'offloads': True,
                    'interrupt_coalescing': True,
                    'congestion_control': 'cubic',
                    'optimize_sysctl': False
                }
            },
            'gaming': {
                'cpu': {
                    'enabled': True,
                    'governor': 'performance',
                    'boost': True,
                    'min_freq_percent': 70,
                    'max_freq_percent': 100,
                    'c6_disable': True,
                    'energy_performance': 'performance'
                },
                'storage': {
                    'enabled': True,
                    'nvme_scheduler': 'none',
                    'ssd_scheduler': 'none',
                    'hdd_scheduler': 'mq-deadline',
                    'read_ahead_kb': 512,
                    'nr_requests': 512
                },
                'network': {
                    'enabled': True,
                    'ring_buffer_max': True,
                    'offloads': True,
                    'interrupt_coalescing': False,
                    'congestion_control': 'bbr',
                    'optimize_sysctl': True
                }
            },
            'server': {
                'cpu': {
                    'enabled': True,
                    'governor': 'schedutil',
                    'boost': True,
                    'min_freq_percent': 50,
                    'max_freq_percent': 100,
                    'c6_disable': False,
                    'energy_performance': 'balance_performance'
                },
                'storage': {
                    'enabled': True,
                    'nvme_scheduler': 'none',
                    'ssd_scheduler': 'mq-deadline',
                    'hdd_scheduler': 'bfq',
                    'read_ahead_kb': 256,
                    'nr_requests': 256
                },
                'network': {
                    'enabled': True,
                    'ring_buffer_max': True,
                    'offloads': True,
                    'interrupt_coalescing': True,
                    'congestion_control': 'bbr',
                    'optimize_sysctl': True,
                    'high_speed': True
                },
                'hpc': {'enabled': False},
                'memory': {'enabled': False}
            },
            'hpc': {
                'cpu': {
                    'enabled': True,
                    'governor': 'performance',
                    'boost': True,
                    'min_freq_percent': 100,
                    'max_freq_percent': 100,
                    'c6_disable': True,
                    'energy_performance': 'performance'
                },
                'storage': {
                    'enabled': True,
                    'nvme_scheduler': 'none',
                    'ssd_scheduler': 'none',
                    'hdd_scheduler': 'mq-deadline',
                    'read_ahead_kb': 4096,
                    'nr_requests': 1024
                },
                'network': {
                    'enabled': True,
                    'ring_buffer_max': True,
                    'offloads': True,
                    'interrupt_coalescing': False,
                    'congestion_control': 'bbr',
                    'optimize_sysctl': True,
                    'high_speed': True,
                    'rdma': True
                },
                'hpc': {
                    'enabled': True,
                    'numa_aware': True,
                    'huge_pages': True,
                    'huge_pages_size': '2M',
                    'huge_pages_count': 'auto',
                    'irq_affinity': True,
                    'process_affinity': True,
                    'memory_policy': 'interleave',
                    'kernel_optimizations': True
                },
                'memory': {
                    'enabled': True,
                    'numa_balancing': False,
                    'thp': 'always',
                    'zone_reclaim': True,
                    'swappiness': 1,
                    'dirty_ratio': 40,
                    'dirty_background_ratio': 10
                }
            }
        }

        return profiles.get(profile, profiles['balanced'])

    def tune_cpu(self, settings: Optional[Dict[str, Any]] = None,
                 dry_run: bool = False) -> Dict[str, Any]:
        """
        Apply CPU-specific tuning.

        Args:
            settings: Custom CPU settings (uses balanced defaults if None)
            dry_run: If True, only show what would be changed

        Returns:
            Dictionary containing applied changes
        """
        if settings is None:
            settings = self._get_profile_config('balanced')['cpu']

        self.logger.info(f"{'Simulating' if dry_run else 'Applying'} CPU tuning...")
        return self.cpu_tuner.apply_profile(
            settings,
            self.hardware_info.get('cpu', {}),
            dry_run=dry_run
        )

    def tune_storage(self, settings: Optional[Dict[str, Any]] = None,
                     dry_run: bool = False) -> Dict[str, Any]:
        """
        Apply storage-specific tuning.

        Args:
            settings: Custom storage settings (uses balanced defaults if None)
            dry_run: If True, only show what would be changed

        Returns:
            Dictionary containing applied changes
        """
        if settings is None:
            settings = self._get_profile_config('balanced')['storage']

        self.logger.info(f"{'Simulating' if dry_run else 'Applying'} storage tuning...")
        return self.storage_tuner.apply_profile(
            settings,
            self.hardware_info.get('storage', []),
            dry_run=dry_run
        )

    def tune_network(self, settings: Optional[Dict[str, Any]] = None,
                     dry_run: bool = False) -> Dict[str, Any]:
        """
        Apply network-specific tuning.

        Args:
            settings: Custom network settings (uses balanced defaults if None)
            dry_run: If True, only show what would be changed

        Returns:
            Dictionary containing applied changes
        """
        if settings is None:
            settings = self._get_profile_config('balanced')['network']

        self.logger.info(f"{'Simulating' if dry_run else 'Applying'} network tuning...")
        return self.network_tuner.apply_profile(
            settings,
            self.hardware_info.get('network', []),
            dry_run=dry_run
        )

    def tune_hpc(self, settings: Optional[Dict[str, Any]] = None,
                 dry_run: bool = False) -> Dict[str, Any]:
        """
        Apply HPC-specific tuning.

        Args:
            settings: Custom HPC settings (uses hpc profile defaults if None)
            dry_run: If True, only show what would be changed

        Returns:
            Dictionary containing applied changes
        """
        if settings is None:
            settings = self._get_profile_config('hpc')['hpc']

        self.logger.info(f"{'Simulating' if dry_run else 'Applying'} HPC tuning...")
        return self.hpc_tuner.apply_profile(
            settings,
            self.hardware_info,
            dry_run=dry_run
        )

    def tune_memory(self, settings: Optional[Dict[str, Any]] = None,
                    dry_run: bool = False) -> Dict[str, Any]:
        """
        Apply memory-specific tuning.

        Args:
            settings: Custom memory settings (uses hpc profile defaults if None)
            dry_run: If True, only show what would be changed

        Returns:
            Dictionary containing applied changes
        """
        if settings is None:
            settings = self._get_profile_config('hpc')['memory']

        self.logger.info(f"{'Simulating' if dry_run else 'Applying'} memory tuning...")
        return self.memory_tuner.apply_profile(
            settings,
            self.hardware_info,
            dry_run=dry_run
        )

    def auto_detect_profile(self) -> str:
        """
        Automatically detect the best profile based on hardware and workload.

        Returns:
            Recommended profile name
        """
        self.logger.info("Auto-detecting optimal profile...")

        cpu_info = self.hardware_info.get('cpu', {})
        model = cpu_info.get('model', '').lower()
        cores = cpu_info.get('cores', 0)
        threads = cpu_info.get('threads', 0)

        # Check for EPYC/Threadripper (HPC/Server)
        if 'epyc' in model or 'threadripper' in model:
            if cores >= 32:
                self.logger.info("Detected EPYC/Threadripper with 32+ cores - recommending HPC profile")
                return 'hpc'
            else:
                self.logger.info("Detected EPYC/Threadripper - recommending server profile")
                return 'server'

        # Check for high core count workstation
        if cores >= 16:
            self.logger.info("Detected high core count - recommending performance profile")
            return 'performance'

        # Check for laptop/mobile (look for power management)
        try:
            with open('/sys/class/power_supply/BAT0/status', 'r') as f:
                self.logger.info("Detected laptop with battery - recommending balanced profile")
                return 'balanced'
        except (FileNotFoundError, PermissionError):
            pass

        # Default to balanced
        self.logger.info("Using balanced profile as default")
        return 'balanced'

    def restore_defaults(self) -> Dict[str, Any]:
        """
        Restore system to default/backed up settings.

        Returns:
            Dictionary containing restoration status
        """
        self.logger.info("Restoring system defaults...")

        results = {
            'timestamp': datetime.now().isoformat(),
            'cpu': self.cpu_tuner.restore_backup(),
            'storage': self.storage_tuner.restore_backup(),
            'network': self.network_tuner.restore_backup()
        }

        return results

    def generate_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive system report.

        Returns:
            Dictionary containing full system report
        """
        self.logger.info("Generating system report...")

        report = {
            'version': self.VERSION,
            'timestamp': datetime.now().isoformat(),
            'hardware': self.hardware_info,
            'current_settings': {
                'cpu': self.cpu_tuner.get_current_settings(),
                'storage': self.storage_tuner.get_current_settings(),
                'network': self.network_tuner.get_current_settings()
            }
        }

        self._save_report(report, 'system_report')
        return report

    def _save_report(self, data: Dict[str, Any], prefix: str = 'changes'):
        """Save report to reports directory."""
        filename = f"{prefix}_{datetime.now():%Y%m%d_%H%M%S}.json"
        report_path = self.reports_dir / filename

        with open(report_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)

        self.logger.debug(f"Report saved: {report_path}")

    def interactive_mode(self):
        """Run in interactive mode with menu-driven interface."""
        while True:
            print("\n" + "=" * 60)
            print(f"AMD Auto Tuner v{self.VERSION}")
            print("=" * 60)
            print("\n--- Detection & Analysis ---")
            print("1.  Detect Hardware")
            print("2.  Run Benchmarks")
            print("3.  Generate Report")
            print("4.  Auto-Detect Best Profile")
            print("\n--- Performance Profiles ---")
            print("5.  Apply Performance Profile")
            print("6.  Apply Balanced Profile")
            print("7.  Apply Power Saving Profile")
            print("8.  Apply Gaming Profile")
            print("9.  Apply Server Profile")
            print("10. Apply HPC Profile")
            print("\n--- Advanced Tuning ---")
            print("11. Tune CPU Only")
            print("12. Tune Storage Only")
            print("13. Tune Network Only")
            print("14. Tune HPC/NUMA")
            print("15. Tune Memory")
            print("\n--- Maintenance ---")
            print("16. Restore Defaults")
            print("0.  Exit")

            try:
                choice = input("\nSelect option: ").strip()

                if choice == '1':
                    info = self.detect_hardware()
                    print(json.dumps(info, indent=2, default=str))
                elif choice == '2':
                    results = self.run_benchmarks()
                    print(json.dumps(results, indent=2, default=str))
                elif choice == '3':
                    report = self.generate_report()
                    print(json.dumps(report, indent=2, default=str))
                elif choice == '4':
                    profile = self.auto_detect_profile()
                    print(f"\nRecommended profile: {profile}")
                    apply = input("Apply this profile? (y/n): ").strip().lower()
                    if apply == 'y':
                        self.apply_profile(profile)
                elif choice == '5':
                    self.apply_profile('performance')
                elif choice == '6':
                    self.apply_profile('balanced')
                elif choice == '7':
                    self.apply_profile('powersave')
                elif choice == '8':
                    self.apply_profile('gaming')
                elif choice == '9':
                    self.apply_profile('server')
                elif choice == '10':
                    self.apply_profile('hpc')
                elif choice == '11':
                    changes = self.tune_cpu()
                    print(json.dumps(changes, indent=2, default=str))
                elif choice == '12':
                    changes = self.tune_storage()
                    print(json.dumps(changes, indent=2, default=str))
                elif choice == '13':
                    changes = self.tune_network()
                    print(json.dumps(changes, indent=2, default=str))
                elif choice == '14':
                    changes = self.tune_hpc()
                    print(json.dumps(changes, indent=2, default=str))
                elif choice == '15':
                    changes = self.tune_memory()
                    print(json.dumps(changes, indent=2, default=str))
                elif choice == '16':
                    self.restore_defaults()
                elif choice == '0':
                    print("Exiting...")
                    break
                else:
                    print("Invalid option")

            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                self.logger.error(f"Error: {e}")


def main():
    """Main entry point for CLI usage."""
    parser = argparse.ArgumentParser(
        description='AMD Auto Tuner - Automated performance tuning for AMD systems',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s detect                    Detect system hardware
  %(prog)s auto                      Auto-detect and apply best profile
  %(prog)s benchmark                 Run all benchmarks
  %(prog)s benchmark --cpu           Run CPU benchmarks only
  %(prog)s profile performance       Apply performance profile
  %(prog)s profile hpc               Apply HPC profile (NUMA, huge pages)
  %(prog)s profile balanced --dry-run  Simulate balanced profile
  %(prog)s tune-cpu --governor performance
  %(prog)s tune-hpc --huge-pages     Apply HPC tuning with huge pages
  %(prog)s tune-memory               Apply memory optimization
  %(prog)s restore                   Restore default settings
  %(prog)s report                    Generate system report
  %(prog)s interactive               Run interactive mode
        """
    )

    parser.add_argument('--version', action='version', version=f'%(prog)s {AMDAutoTuner.VERSION}')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')
    parser.add_argument('-c', '--config', type=str, help='Path to custom config file')
    parser.add_argument('--dry-run', action='store_true', help='Simulate changes without applying')

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Detect command
    subparsers.add_parser('detect', help='Detect system hardware')

    # Auto-detect command
    auto_parser = subparsers.add_parser('auto', help='Auto-detect and apply best profile')
    auto_parser.add_argument('--apply', action='store_true', help='Apply the detected profile automatically')

    # Benchmark command
    bench_parser = subparsers.add_parser('benchmark', help='Run performance benchmarks')
    bench_parser.add_argument('--cpu', action='store_true', help='Benchmark CPU only')
    bench_parser.add_argument('--storage', action='store_true', help='Benchmark storage only')
    bench_parser.add_argument('--network', action='store_true', help='Benchmark network only')

    # Profile command
    profile_parser = subparsers.add_parser('profile', help='Apply a performance profile')
    profile_parser.add_argument('name', choices=['performance', 'balanced', 'powersave', 'gaming', 'server', 'hpc'],
                               help='Profile to apply')

    # Tune CPU command
    cpu_parser = subparsers.add_parser('tune-cpu', help='Apply CPU-specific tuning')
    cpu_parser.add_argument('--governor', choices=['performance', 'powersave', 'schedutil', 'ondemand', 'conservative'])
    cpu_parser.add_argument('--boost', type=bool, help='Enable/disable boost')
    cpu_parser.add_argument('--min-freq', type=int, help='Minimum frequency in MHz')
    cpu_parser.add_argument('--max-freq', type=int, help='Maximum frequency in MHz')

    # Tune Storage command
    storage_parser = subparsers.add_parser('tune-storage', help='Apply storage-specific tuning')
    storage_parser.add_argument('--scheduler', choices=['none', 'mq-deadline', 'bfq', 'kyber'])
    storage_parser.add_argument('--read-ahead', type=int, help='Read-ahead in KB')

    # Tune Network command
    network_parser = subparsers.add_parser('tune-network', help='Apply network-specific tuning')
    network_parser.add_argument('--congestion', choices=['bbr', 'cubic', 'reno'])
    network_parser.add_argument('--ring-buffer-max', action='store_true')
    network_parser.add_argument('--high-speed', action='store_true', help='Optimize for 25G/40G/100G/200G/400G NICs')

    # Tune HPC command
    hpc_parser = subparsers.add_parser('tune-hpc', help='Apply HPC-specific tuning')
    hpc_parser.add_argument('--huge-pages', action='store_true', help='Enable huge pages')
    hpc_parser.add_argument('--huge-pages-size', choices=['2M', '1G'], default='2M', help='Huge page size')
    hpc_parser.add_argument('--numa-aware', action='store_true', help='Enable NUMA-aware tuning')
    hpc_parser.add_argument('--irq-affinity', action='store_true', help='Optimize IRQ affinity')

    # Tune Memory command
    memory_parser = subparsers.add_parser('tune-memory', help='Apply memory-specific tuning')
    memory_parser.add_argument('--swappiness', type=int, help='Set swappiness (0-100)')
    memory_parser.add_argument('--thp', choices=['always', 'madvise', 'never'], help='Transparent Huge Pages policy')
    memory_parser.add_argument('--numa-balancing', type=bool, help='Enable/disable NUMA balancing')

    # Restore command
    subparsers.add_parser('restore', help='Restore default settings')

    # Report command
    subparsers.add_parser('report', help='Generate system report')

    # Interactive command
    subparsers.add_parser('interactive', help='Run interactive mode')

    args = parser.parse_args()

    # Check for root privileges for most operations
    if args.command and args.command not in ['detect', 'report', 'interactive'] and not args.dry_run:
        if os.geteuid() != 0:
            print("Error: This operation requires root privileges.")
            print("Please run with sudo or as root.")
            sys.exit(1)

    try:
        tuner = AMDAutoTuner(config_path=args.config, verbose=args.verbose)

        if args.command == 'detect':
            info = tuner.detect_hardware()
            print(json.dumps(info, indent=2, default=str))

        elif args.command == 'auto':
            profile = tuner.auto_detect_profile()
            print(f"Recommended profile: {profile}")
            if args.apply:
                print(f"Applying {profile} profile...")
                changes = tuner.apply_profile(profile, dry_run=args.dry_run)
                print(json.dumps(changes, indent=2, default=str))

        elif args.command == 'benchmark':
            categories = []
            if args.cpu:
                categories.append('cpu')
            if args.storage:
                categories.append('storage')
            if args.network:
                categories.append('network')
            if not categories:
                categories = None  # Run all

            results = tuner.run_benchmarks(categories)
            print(json.dumps(results, indent=2, default=str))

        elif args.command == 'profile':
            changes = tuner.apply_profile(args.name, dry_run=args.dry_run)
            print(json.dumps(changes, indent=2, default=str))

        elif args.command == 'tune-cpu':
            settings = {}
            if args.governor:
                settings['governor'] = args.governor
            if args.boost is not None:
                settings['boost'] = args.boost
            if args.min_freq:
                settings['min_freq_mhz'] = args.min_freq
            if args.max_freq:
                settings['max_freq_mhz'] = args.max_freq

            changes = tuner.tune_cpu(settings if settings else None, dry_run=args.dry_run)
            print(json.dumps(changes, indent=2, default=str))

        elif args.command == 'tune-storage':
            settings = {}
            if args.scheduler:
                settings['scheduler'] = args.scheduler
            if args.read_ahead:
                settings['read_ahead_kb'] = args.read_ahead

            changes = tuner.tune_storage(settings if settings else None, dry_run=args.dry_run)
            print(json.dumps(changes, indent=2, default=str))

        elif args.command == 'tune-network':
            settings = {}
            if args.congestion:
                settings['congestion_control'] = args.congestion
            if args.ring_buffer_max:
                settings['ring_buffer_max'] = True
            if hasattr(args, 'high_speed') and args.high_speed:
                settings['high_speed'] = True

            changes = tuner.tune_network(settings if settings else None, dry_run=args.dry_run)
            print(json.dumps(changes, indent=2, default=str))

        elif args.command == 'tune-hpc':
            settings = {'enabled': True}
            if args.huge_pages:
                settings['huge_pages'] = True
                settings['huge_pages_size'] = args.huge_pages_size
            if args.numa_aware:
                settings['numa_aware'] = True
            if args.irq_affinity:
                settings['irq_affinity'] = True

            changes = tuner.tune_hpc(settings, dry_run=args.dry_run)
            print(json.dumps(changes, indent=2, default=str))

        elif args.command == 'tune-memory':
            settings = {'enabled': True}
            if args.swappiness is not None:
                settings['swappiness'] = args.swappiness
            if args.thp:
                settings['thp'] = args.thp
            if args.numa_balancing is not None:
                settings['numa_balancing'] = args.numa_balancing

            changes = tuner.tune_memory(settings, dry_run=args.dry_run)
            print(json.dumps(changes, indent=2, default=str))

        elif args.command == 'restore':
            results = tuner.restore_defaults()
            print(json.dumps(results, indent=2, default=str))

        elif args.command == 'report':
            report = tuner.generate_report()
            print(json.dumps(report, indent=2, default=str))

        elif args.command == 'interactive':
            tuner.interactive_mode()

        else:
            parser.print_help()

    except KeyboardInterrupt:
        print("\nOperation cancelled.")
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
