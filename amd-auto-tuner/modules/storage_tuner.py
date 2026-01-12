#!/usr/bin/env python3
"""
Storage Tuner Module
Optimizes storage device performance (NVMe, SSD, HDD)
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging


class StorageTuner:
    """Handles storage device performance tuning."""

    def __init__(self, backup_dir: Path):
        """
        Initialize the storage tuner.

        Args:
            backup_dir: Directory to store configuration backups
        """
        self.logger = logging.getLogger('AMDAutoTuner.StorageTuner')
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)

        self.block_path = Path('/sys/block')

    def get_current_settings(self) -> Dict[str, Any]:
        """
        Get current storage settings for all devices.

        Returns:
            Dictionary containing current storage configuration
        """
        settings = {}

        for device_path in self.block_path.iterdir():
            name = device_path.name

            # Skip virtual devices
            if name.startswith(('loop', 'ram', 'dm-', 'sr', 'fd')):
                continue

            settings[name] = self._get_device_settings(name)

        return settings

    def _get_device_settings(self, device: str) -> Dict[str, Any]:
        """Get settings for a specific device."""
        device_path = self.block_path / device
        queue_path = device_path / 'queue'

        settings = {
            'scheduler': '',
            'available_schedulers': [],
            'read_ahead_kb': 0,
            'nr_requests': 0,
            'rotational': True,
            'max_sectors_kb': 0,
            'nomerges': 0,
            'rq_affinity': 0,
            'add_random': 0
        }

        try:
            # Scheduler
            scheduler_path = queue_path / 'scheduler'
            if scheduler_path.exists():
                content = scheduler_path.read_text().strip()
                import re
                match = re.search(r'\[(\w+)\]', content)
                if match:
                    settings['scheduler'] = match.group(1)
                settings['available_schedulers'] = re.findall(r'[\w-]+', content)

            # Read-ahead
            read_ahead_path = queue_path / 'read_ahead_kb'
            if read_ahead_path.exists():
                settings['read_ahead_kb'] = int(read_ahead_path.read_text().strip())

            # Number of requests
            nr_requests_path = queue_path / 'nr_requests'
            if nr_requests_path.exists():
                settings['nr_requests'] = int(nr_requests_path.read_text().strip())

            # Rotational
            rotational_path = queue_path / 'rotational'
            if rotational_path.exists():
                settings['rotational'] = rotational_path.read_text().strip() == '1'

            # Max sectors
            max_sectors_path = queue_path / 'max_sectors_kb'
            if max_sectors_path.exists():
                settings['max_sectors_kb'] = int(max_sectors_path.read_text().strip())

            # No merges
            nomerges_path = queue_path / 'nomerges'
            if nomerges_path.exists():
                settings['nomerges'] = int(nomerges_path.read_text().strip())

            # RQ affinity
            rq_affinity_path = queue_path / 'rq_affinity'
            if rq_affinity_path.exists():
                settings['rq_affinity'] = int(rq_affinity_path.read_text().strip())

            # Add random
            add_random_path = queue_path / 'add_random'
            if add_random_path.exists():
                settings['add_random'] = int(add_random_path.read_text().strip())

        except Exception as e:
            self.logger.debug(f"Could not get settings for {device}: {e}")

        return settings

    def create_backup(self) -> str:
        """
        Create a backup of current storage settings.

        Returns:
            Path to backup file
        """
        settings = self.get_current_settings()
        settings['timestamp'] = datetime.now().isoformat()

        backup_file = self.backup_dir / f"storage_backup_{datetime.now():%Y%m%d_%H%M%S}.json"

        with open(backup_file, 'w') as f:
            json.dump(settings, f, indent=2)

        self.logger.info(f"Storage backup created: {backup_file}")
        return str(backup_file)

    def restore_backup(self, backup_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Restore storage settings from backup.

        Args:
            backup_file: Path to specific backup file. If None, uses latest backup.

        Returns:
            Dictionary containing restoration status
        """
        if backup_file is None:
            backups = list(self.backup_dir.glob('storage_backup_*.json'))
            if not backups:
                return {'success': False, 'error': 'No backup found'}
            backup_file = str(max(backups, key=lambda x: x.stat().st_mtime))

        try:
            with open(backup_file) as f:
                settings = json.load(f)

            results = {'success': True, 'devices': {}}

            for device, device_settings in settings.items():
                if device == 'timestamp':
                    continue

                device_results = []

                if device_settings.get('scheduler'):
                    if self._set_scheduler(device, device_settings['scheduler']):
                        device_results.append(f"Scheduler: {device_settings['scheduler']}")

                if device_settings.get('read_ahead_kb'):
                    if self._set_read_ahead(device, device_settings['read_ahead_kb']):
                        device_results.append(f"Read-ahead: {device_settings['read_ahead_kb']} KB")

                if device_settings.get('nr_requests'):
                    if self._set_nr_requests(device, device_settings['nr_requests']):
                        device_results.append(f"NR requests: {device_settings['nr_requests']}")

                results['devices'][device] = device_results

            self.logger.info(f"Restored storage settings from {backup_file}")
            return results
        except Exception as e:
            self.logger.error(f"Failed to restore backup: {e}")
            return {'success': False, 'error': str(e)}

    def apply_profile(self, settings: Dict[str, Any], devices: List[Dict[str, Any]],
                      dry_run: bool = False) -> Dict[str, Any]:
        """
        Apply storage tuning settings.

        Args:
            settings: Storage settings to apply
            devices: List of storage device information
            dry_run: If True, only simulate changes

        Returns:
            Dictionary containing applied changes per device
        """
        changes = {}

        # Create backup first (unless dry run)
        if not dry_run:
            try:
                self.create_backup()
            except Exception as e:
                self.logger.warning(f"Could not create backup: {e}")

        for device in devices:
            name = device['name']
            device_type = device.get('type', 'unknown')

            changes[name] = {
                'applied': [],
                'skipped': [],
                'errors': []
            }

            # Determine scheduler based on device type
            scheduler = None
            if device_type == 'nvme' and 'nvme_scheduler' in settings:
                scheduler = settings['nvme_scheduler']
            elif device_type == 'ssd' and 'ssd_scheduler' in settings:
                scheduler = settings['ssd_scheduler']
            elif device_type == 'hdd' and 'hdd_scheduler' in settings:
                scheduler = settings['hdd_scheduler']
            elif 'scheduler' in settings:
                scheduler = settings['scheduler']

            # Apply scheduler
            if scheduler:
                if dry_run:
                    changes[name]['applied'].append(f"Would set scheduler: {scheduler}")
                else:
                    if self._set_scheduler(name, scheduler):
                        changes[name]['applied'].append(f"Set scheduler: {scheduler}")
                    else:
                        changes[name]['errors'].append(f"Failed to set scheduler: {scheduler}")

            # Apply read-ahead
            if 'read_ahead_kb' in settings:
                read_ahead = settings['read_ahead_kb']
                if dry_run:
                    changes[name]['applied'].append(f"Would set read-ahead: {read_ahead} KB")
                else:
                    if self._set_read_ahead(name, read_ahead):
                        changes[name]['applied'].append(f"Set read-ahead: {read_ahead} KB")
                    else:
                        changes[name]['errors'].append(f"Failed to set read-ahead: {read_ahead} KB")

            # Apply nr_requests
            if 'nr_requests' in settings:
                nr_requests = settings['nr_requests']
                if dry_run:
                    changes[name]['applied'].append(f"Would set nr_requests: {nr_requests}")
                else:
                    if self._set_nr_requests(name, nr_requests):
                        changes[name]['applied'].append(f"Set nr_requests: {nr_requests}")
                    else:
                        changes[name]['errors'].append(f"Failed to set nr_requests: {nr_requests}")

            # Apply max_sectors_kb
            if 'max_sectors_kb' in settings:
                max_sectors = settings['max_sectors_kb']
                if dry_run:
                    changes[name]['applied'].append(f"Would set max_sectors_kb: {max_sectors}")
                else:
                    if self._set_max_sectors(name, max_sectors):
                        changes[name]['applied'].append(f"Set max_sectors_kb: {max_sectors}")
                    else:
                        changes[name]['errors'].append(f"Failed to set max_sectors_kb: {max_sectors}")

            # Apply nomerges
            if 'nomerges' in settings:
                nomerges = settings['nomerges']
                if dry_run:
                    changes[name]['applied'].append(f"Would set nomerges: {nomerges}")
                else:
                    if self._set_nomerges(name, nomerges):
                        changes[name]['applied'].append(f"Set nomerges: {nomerges}")
                    else:
                        changes[name]['errors'].append(f"Failed to set nomerges: {nomerges}")

            # Apply rq_affinity
            if 'rq_affinity' in settings:
                rq_affinity = settings['rq_affinity']
                if dry_run:
                    changes[name]['applied'].append(f"Would set rq_affinity: {rq_affinity}")
                else:
                    if self._set_rq_affinity(name, rq_affinity):
                        changes[name]['applied'].append(f"Set rq_affinity: {rq_affinity}")
                    else:
                        changes[name]['errors'].append(f"Failed to set rq_affinity: {rq_affinity}")

            # Enable TRIM for SSDs and NVMe
            if device_type in ('ssd', 'nvme') and settings.get('enable_trim', True):
                if dry_run:
                    changes[name]['applied'].append("Would enable TRIM")
                else:
                    changes[name]['skipped'].append("TRIM requires fstab configuration")

        return changes

    def _set_scheduler(self, device: str, scheduler: str) -> bool:
        """Set I/O scheduler for a device."""
        scheduler_path = self.block_path / device / 'queue' / 'scheduler'

        if not scheduler_path.exists():
            self.logger.warning(f"Scheduler path not found for {device}")
            return False

        try:
            scheduler_path.write_text(scheduler)
            self.logger.debug(f"Set {device} scheduler to {scheduler}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to set scheduler for {device}: {e}")
            return False

    def _set_read_ahead(self, device: str, value: int) -> bool:
        """Set read-ahead value for a device."""
        path = self.block_path / device / 'queue' / 'read_ahead_kb'

        if not path.exists():
            return False

        try:
            path.write_text(str(value))
            self.logger.debug(f"Set {device} read-ahead to {value} KB")
            return True
        except Exception as e:
            self.logger.error(f"Failed to set read-ahead for {device}: {e}")
            return False

    def _set_nr_requests(self, device: str, value: int) -> bool:
        """Set number of requests for a device."""
        path = self.block_path / device / 'queue' / 'nr_requests'

        if not path.exists():
            return False

        try:
            path.write_text(str(value))
            self.logger.debug(f"Set {device} nr_requests to {value}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to set nr_requests for {device}: {e}")
            return False

    def _set_max_sectors(self, device: str, value: int) -> bool:
        """Set max sectors for a device."""
        path = self.block_path / device / 'queue' / 'max_sectors_kb'

        if not path.exists():
            return False

        try:
            path.write_text(str(value))
            self.logger.debug(f"Set {device} max_sectors_kb to {value}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to set max_sectors_kb for {device}: {e}")
            return False

    def _set_nomerges(self, device: str, value: int) -> bool:
        """Set nomerges value for a device."""
        path = self.block_path / device / 'queue' / 'nomerges'

        if not path.exists():
            return False

        try:
            path.write_text(str(value))
            self.logger.debug(f"Set {device} nomerges to {value}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to set nomerges for {device}: {e}")
            return False

    def _set_rq_affinity(self, device: str, value: int) -> bool:
        """Set rq_affinity value for a device."""
        path = self.block_path / device / 'queue' / 'rq_affinity'

        if not path.exists():
            return False

        try:
            path.write_text(str(value))
            self.logger.debug(f"Set {device} rq_affinity to {value}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to set rq_affinity for {device}: {e}")
            return False

    def optimize_for_workload(self, workload: str, devices: List[Dict[str, Any]],
                              dry_run: bool = False) -> Dict[str, Any]:
        """
        Optimize storage for specific workload.

        Args:
            workload: Type of workload ('database', 'webserver', 'desktop', 'throughput', 'latency')
            devices: List of storage device information
            dry_run: If True, only simulate changes

        Returns:
            Dictionary containing applied changes
        """
        workload_profiles = {
            'database': {
                'nvme_scheduler': 'none',
                'ssd_scheduler': 'mq-deadline',
                'hdd_scheduler': 'mq-deadline',
                'read_ahead_kb': 16,
                'nr_requests': 256,
                'nomerges': 2
            },
            'webserver': {
                'nvme_scheduler': 'none',
                'ssd_scheduler': 'mq-deadline',
                'hdd_scheduler': 'bfq',
                'read_ahead_kb': 256,
                'nr_requests': 128
            },
            'desktop': {
                'nvme_scheduler': 'none',
                'ssd_scheduler': 'bfq',
                'hdd_scheduler': 'bfq',
                'read_ahead_kb': 128,
                'nr_requests': 64
            },
            'throughput': {
                'nvme_scheduler': 'none',
                'ssd_scheduler': 'mq-deadline',
                'hdd_scheduler': 'mq-deadline',
                'read_ahead_kb': 512,
                'nr_requests': 512
            },
            'latency': {
                'nvme_scheduler': 'none',
                'ssd_scheduler': 'none',
                'hdd_scheduler': 'mq-deadline',
                'read_ahead_kb': 32,
                'nr_requests': 64,
                'nomerges': 1
            }
        }

        if workload not in workload_profiles:
            raise ValueError(f"Unknown workload: {workload}. Options: {list(workload_profiles.keys())}")

        return self.apply_profile(workload_profiles[workload], devices, dry_run)

    def run_trim(self, device: str) -> Dict[str, Any]:
        """
        Run TRIM/discard on a device.

        Args:
            device: Device name (e.g., 'sda', 'nvme0n1')

        Returns:
            Dictionary containing TRIM results
        """
        try:
            result = subprocess.run(
                ['fstrim', '-v', f'/dev/{device}'],
                capture_output=True, text=True, timeout=300
            )

            if result.returncode == 0:
                return {'success': True, 'output': result.stdout.strip()}
            else:
                return {'success': False, 'error': result.stderr.strip()}
        except FileNotFoundError:
            return {'success': False, 'error': 'fstrim command not found'}
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'TRIM operation timed out'}
        except Exception as e:
            return {'success': False, 'error': str(e)}


if __name__ == '__main__':
    import json

    logging.basicConfig(level=logging.DEBUG)
    tuner = StorageTuner(Path('/tmp/storage_backup'))

    print("=== Storage Settings ===")
    settings = tuner.get_current_settings()
    print(json.dumps(settings, indent=2))
