#!/usr/bin/env python3
"""
CPU Tuner Module
Optimizes AMD CPU performance through governors, frequencies, boost, and C-states
"""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging


class CPUTuner:
    """Handles CPU-specific performance tuning for AMD processors."""

    def __init__(self, backup_dir: Path):
        """
        Initialize the CPU tuner.

        Args:
            backup_dir: Directory to store configuration backups
        """
        self.logger = logging.getLogger('AMDAutoTuner.CPUTuner')
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)

        self.cpu_base_path = Path('/sys/devices/system/cpu')
        self.cpufreq_path = self.cpu_base_path / 'cpufreq'

    def get_current_settings(self) -> Dict[str, Any]:
        """
        Get current CPU settings.

        Returns:
            Dictionary containing current CPU configuration
        """
        settings = {
            'governor': self._get_current_governor(),
            'available_governors': self._get_available_governors(),
            'boost_enabled': self._get_boost_status(),
            'min_freq_mhz': self._get_min_freq(),
            'max_freq_mhz': self._get_max_freq(),
            'scaling_min_freq_mhz': self._get_scaling_min_freq(),
            'scaling_max_freq_mhz': self._get_scaling_max_freq(),
            'current_freq_mhz': self._get_current_freq(),
            'energy_performance_preference': self._get_epp(),
            'available_epp': self._get_available_epp(),
            'driver': self._get_scaling_driver(),
            'online_cpus': self._get_online_cpus(),
            'total_cpus': self._get_total_cpus()
        }
        return settings

    def _get_current_governor(self) -> str:
        """Get current CPU governor."""
        try:
            path = self.cpu_base_path / 'cpu0' / 'cpufreq' / 'scaling_governor'
            if path.exists():
                return path.read_text().strip()
        except Exception:
            pass
        return ''

    def _get_available_governors(self) -> List[str]:
        """Get list of available governors."""
        try:
            path = self.cpu_base_path / 'cpu0' / 'cpufreq' / 'scaling_available_governors'
            if path.exists():
                return path.read_text().strip().split()
        except Exception:
            pass
        return []

    def _get_boost_status(self) -> Optional[bool]:
        """Get CPU boost status."""
        try:
            path = self.cpufreq_path / 'boost'
            if path.exists():
                return path.read_text().strip() == '1'
        except Exception:
            pass
        return None

    def _get_min_freq(self) -> int:
        """Get hardware minimum frequency in MHz."""
        try:
            path = self.cpu_base_path / 'cpu0' / 'cpufreq' / 'cpuinfo_min_freq'
            if path.exists():
                return int(path.read_text().strip()) // 1000
        except Exception:
            pass
        return 0

    def _get_max_freq(self) -> int:
        """Get hardware maximum frequency in MHz."""
        try:
            path = self.cpu_base_path / 'cpu0' / 'cpufreq' / 'cpuinfo_max_freq'
            if path.exists():
                return int(path.read_text().strip()) // 1000
        except Exception:
            pass
        return 0

    def _get_scaling_min_freq(self) -> int:
        """Get scaling minimum frequency in MHz."""
        try:
            path = self.cpu_base_path / 'cpu0' / 'cpufreq' / 'scaling_min_freq'
            if path.exists():
                return int(path.read_text().strip()) // 1000
        except Exception:
            pass
        return 0

    def _get_scaling_max_freq(self) -> int:
        """Get scaling maximum frequency in MHz."""
        try:
            path = self.cpu_base_path / 'cpu0' / 'cpufreq' / 'scaling_max_freq'
            if path.exists():
                return int(path.read_text().strip()) // 1000
        except Exception:
            pass
        return 0

    def _get_current_freq(self) -> int:
        """Get current CPU frequency in MHz."""
        try:
            path = self.cpu_base_path / 'cpu0' / 'cpufreq' / 'scaling_cur_freq'
            if path.exists():
                return int(path.read_text().strip()) // 1000
        except Exception:
            pass
        return 0

    def _get_epp(self) -> str:
        """Get current energy performance preference."""
        try:
            path = self.cpu_base_path / 'cpu0' / 'cpufreq' / 'energy_performance_preference'
            if path.exists():
                return path.read_text().strip()
        except Exception:
            pass
        return ''

    def _get_available_epp(self) -> List[str]:
        """Get available energy performance preferences."""
        try:
            path = self.cpu_base_path / 'cpu0' / 'cpufreq' / 'energy_performance_available_preferences'
            if path.exists():
                return path.read_text().strip().split()
        except Exception:
            pass
        return []

    def _get_scaling_driver(self) -> str:
        """Get current scaling driver."""
        try:
            path = self.cpu_base_path / 'cpu0' / 'cpufreq' / 'scaling_driver'
            if path.exists():
                return path.read_text().strip()
        except Exception:
            pass
        return ''

    def _get_online_cpus(self) -> int:
        """Get number of online CPUs."""
        try:
            online_path = self.cpu_base_path / 'online'
            if online_path.exists():
                content = online_path.read_text().strip()
                # Parse format like "0-15" or "0-7,9-15"
                count = 0
                for part in content.split(','):
                    if '-' in part:
                        start, end = map(int, part.split('-'))
                        count += end - start + 1
                    else:
                        count += 1
                return count
        except Exception:
            pass
        return 0

    def _get_total_cpus(self) -> int:
        """Get total number of CPUs."""
        count = 0
        try:
            for item in self.cpu_base_path.iterdir():
                if item.name.startswith('cpu') and item.name[3:].isdigit():
                    count += 1
        except Exception:
            pass
        return count

    def create_backup(self) -> str:
        """
        Create a backup of current CPU settings.

        Returns:
            Path to backup file
        """
        settings = self.get_current_settings()
        settings['timestamp'] = datetime.now().isoformat()

        backup_file = self.backup_dir / f"cpu_backup_{datetime.now():%Y%m%d_%H%M%S}.json"

        with open(backup_file, 'w') as f:
            json.dump(settings, f, indent=2)

        self.logger.info(f"CPU backup created: {backup_file}")
        return str(backup_file)

    def restore_backup(self, backup_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Restore CPU settings from backup.

        Args:
            backup_file: Path to specific backup file. If None, uses latest backup.

        Returns:
            Dictionary containing restoration status
        """
        if backup_file is None:
            # Find latest backup
            backups = list(self.backup_dir.glob('cpu_backup_*.json'))
            if not backups:
                return {'success': False, 'error': 'No backup found'}
            backup_file = str(max(backups, key=lambda x: x.stat().st_mtime))

        try:
            with open(backup_file) as f:
                settings = json.load(f)

            results = {'success': True, 'changes': []}

            # Restore governor
            if settings.get('governor'):
                self._set_governor(settings['governor'])
                results['changes'].append(f"Governor: {settings['governor']}")

            # Restore boost
            if settings.get('boost_enabled') is not None:
                self._set_boost(settings['boost_enabled'])
                results['changes'].append(f"Boost: {settings['boost_enabled']}")

            # Restore frequencies
            if settings.get('scaling_min_freq_mhz'):
                self._set_min_freq(settings['scaling_min_freq_mhz'])
                results['changes'].append(f"Min freq: {settings['scaling_min_freq_mhz']} MHz")

            if settings.get('scaling_max_freq_mhz'):
                self._set_max_freq(settings['scaling_max_freq_mhz'])
                results['changes'].append(f"Max freq: {settings['scaling_max_freq_mhz']} MHz")

            self.logger.info(f"Restored CPU settings from {backup_file}")
            return results
        except Exception as e:
            self.logger.error(f"Failed to restore backup: {e}")
            return {'success': False, 'error': str(e)}

    def apply_profile(self, settings: Dict[str, Any], cpu_info: Dict[str, Any],
                      dry_run: bool = False) -> Dict[str, Any]:
        """
        Apply CPU tuning settings.

        Args:
            settings: CPU settings to apply
            cpu_info: Current CPU hardware information
            dry_run: If True, only simulate changes

        Returns:
            Dictionary containing applied changes
        """
        changes = {
            'applied': [],
            'skipped': [],
            'errors': []
        }

        # Create backup first (unless dry run)
        if not dry_run:
            try:
                self.create_backup()
            except Exception as e:
                self.logger.warning(f"Could not create backup: {e}")

        # Apply governor
        if 'governor' in settings:
            governor = settings['governor']
            available = cpu_info.get('available_governors', [])

            if governor in available or not available:
                if dry_run:
                    changes['applied'].append(f"Would set governor: {governor}")
                else:
                    if self._set_governor(governor):
                        changes['applied'].append(f"Set governor: {governor}")
                    else:
                        changes['errors'].append(f"Failed to set governor: {governor}")
            else:
                changes['skipped'].append(f"Governor '{governor}' not available")

        # Apply boost setting
        if 'boost' in settings:
            boost = settings['boost']
            if dry_run:
                changes['applied'].append(f"Would set boost: {boost}")
            else:
                if self._set_boost(boost):
                    changes['applied'].append(f"Set boost: {boost}")
                else:
                    changes['errors'].append(f"Failed to set boost: {boost}")

        # Apply frequency settings
        max_freq = cpu_info.get('max_freq_mhz', 0)
        min_freq = cpu_info.get('min_freq_mhz', 0)

        if 'min_freq_percent' in settings and max_freq > 0:
            target_min = int(min_freq + (max_freq - min_freq) * settings['min_freq_percent'] / 100)
            if dry_run:
                changes['applied'].append(f"Would set min freq: {target_min} MHz")
            else:
                if self._set_min_freq(target_min):
                    changes['applied'].append(f"Set min freq: {target_min} MHz")
                else:
                    changes['errors'].append(f"Failed to set min freq: {target_min} MHz")

        if 'max_freq_percent' in settings and max_freq > 0:
            target_max = int(min_freq + (max_freq - min_freq) * settings['max_freq_percent'] / 100)
            if dry_run:
                changes['applied'].append(f"Would set max freq: {target_max} MHz")
            else:
                if self._set_max_freq(target_max):
                    changes['applied'].append(f"Set max freq: {target_max} MHz")
                else:
                    changes['errors'].append(f"Failed to set max freq: {target_max} MHz")

        if 'min_freq_mhz' in settings:
            if dry_run:
                changes['applied'].append(f"Would set min freq: {settings['min_freq_mhz']} MHz")
            else:
                if self._set_min_freq(settings['min_freq_mhz']):
                    changes['applied'].append(f"Set min freq: {settings['min_freq_mhz']} MHz")
                else:
                    changes['errors'].append(f"Failed to set min freq: {settings['min_freq_mhz']} MHz")

        if 'max_freq_mhz' in settings:
            if dry_run:
                changes['applied'].append(f"Would set max freq: {settings['max_freq_mhz']} MHz")
            else:
                if self._set_max_freq(settings['max_freq_mhz']):
                    changes['applied'].append(f"Set max freq: {settings['max_freq_mhz']} MHz")
                else:
                    changes['errors'].append(f"Failed to set max freq: {settings['max_freq_mhz']} MHz")

        # Apply energy performance preference (for AMD P-State)
        if 'energy_performance' in settings:
            epp = settings['energy_performance']
            if dry_run:
                changes['applied'].append(f"Would set EPP: {epp}")
            else:
                if self._set_epp(epp):
                    changes['applied'].append(f"Set EPP: {epp}")
                else:
                    changes['skipped'].append(f"EPP not available or failed: {epp}")

        # Apply C-state settings (if ZenStates is available)
        if 'c6_disable' in settings:
            if dry_run:
                action = "disable" if settings['c6_disable'] else "enable"
                changes['applied'].append(f"Would {action} C6 state")
            else:
                if self._set_c6_state(not settings['c6_disable']):
                    action = "Disabled" if settings['c6_disable'] else "Enabled"
                    changes['applied'].append(f"{action} C6 state")
                else:
                    changes['skipped'].append("C6 state control not available")

        return changes

    def _set_governor(self, governor: str) -> bool:
        """Set CPU governor for all CPUs."""
        success = True

        for cpu_dir in self.cpu_base_path.iterdir():
            if cpu_dir.name.startswith('cpu') and cpu_dir.name[3:].isdigit():
                governor_path = cpu_dir / 'cpufreq' / 'scaling_governor'
                if governor_path.exists():
                    try:
                        governor_path.write_text(governor)
                        self.logger.debug(f"Set {cpu_dir.name} governor to {governor}")
                    except Exception as e:
                        self.logger.error(f"Failed to set governor for {cpu_dir.name}: {e}")
                        success = False

        return success

    def _set_boost(self, enabled: bool) -> bool:
        """Set CPU boost state."""
        boost_path = self.cpufreq_path / 'boost'

        if not boost_path.exists():
            self.logger.warning("Boost control not available")
            return False

        try:
            boost_path.write_text('1' if enabled else '0')
            self.logger.debug(f"Set boost to {enabled}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to set boost: {e}")
            return False

    def _set_min_freq(self, freq_mhz: int) -> bool:
        """Set minimum CPU frequency for all CPUs."""
        freq_khz = freq_mhz * 1000
        success = True

        for cpu_dir in self.cpu_base_path.iterdir():
            if cpu_dir.name.startswith('cpu') and cpu_dir.name[3:].isdigit():
                freq_path = cpu_dir / 'cpufreq' / 'scaling_min_freq'
                if freq_path.exists():
                    try:
                        freq_path.write_text(str(freq_khz))
                        self.logger.debug(f"Set {cpu_dir.name} min freq to {freq_mhz} MHz")
                    except Exception as e:
                        self.logger.error(f"Failed to set min freq for {cpu_dir.name}: {e}")
                        success = False

        return success

    def _set_max_freq(self, freq_mhz: int) -> bool:
        """Set maximum CPU frequency for all CPUs."""
        freq_khz = freq_mhz * 1000
        success = True

        for cpu_dir in self.cpu_base_path.iterdir():
            if cpu_dir.name.startswith('cpu') and cpu_dir.name[3:].isdigit():
                freq_path = cpu_dir / 'cpufreq' / 'scaling_max_freq'
                if freq_path.exists():
                    try:
                        freq_path.write_text(str(freq_khz))
                        self.logger.debug(f"Set {cpu_dir.name} max freq to {freq_mhz} MHz")
                    except Exception as e:
                        self.logger.error(f"Failed to set max freq for {cpu_dir.name}: {e}")
                        success = False

        return success

    def _set_epp(self, preference: str) -> bool:
        """Set energy performance preference for all CPUs."""
        success = True

        for cpu_dir in self.cpu_base_path.iterdir():
            if cpu_dir.name.startswith('cpu') and cpu_dir.name[3:].isdigit():
                epp_path = cpu_dir / 'cpufreq' / 'energy_performance_preference'
                if epp_path.exists():
                    try:
                        epp_path.write_text(preference)
                        self.logger.debug(f"Set {cpu_dir.name} EPP to {preference}")
                    except Exception as e:
                        self.logger.error(f"Failed to set EPP for {cpu_dir.name}: {e}")
                        success = False
                else:
                    success = False

        return success

    def _set_c6_state(self, enabled: bool) -> bool:
        """Set C6 state using ZenStates (if available)."""
        try:
            # Try using zenstates command
            action = '--c6-enable' if enabled else '--c6-disable'
            result = subprocess.run(
                ['zenstates', action],
                capture_output=True, text=True, timeout=10
            )

            if result.returncode == 0:
                self.logger.debug(f"C6 state {'enabled' if enabled else 'disabled'}")
                return True
            else:
                self.logger.debug(f"ZenStates failed: {result.stderr}")
                return False
        except FileNotFoundError:
            self.logger.debug("ZenStates not installed")
            return False
        except Exception as e:
            self.logger.debug(f"C6 state control failed: {e}")
            return False

    def set_cores_online(self, cores: List[int], online: bool = True) -> Dict[str, Any]:
        """
        Set CPU cores online/offline.

        Args:
            cores: List of core numbers to modify
            online: True to bring online, False to take offline

        Returns:
            Dictionary containing results
        """
        results = {'success': [], 'failed': []}

        for core in cores:
            if core == 0:
                results['failed'].append(f"Core 0 cannot be taken offline")
                continue

            online_path = self.cpu_base_path / f'cpu{core}' / 'online'

            if not online_path.exists():
                results['failed'].append(f"Core {core} does not exist")
                continue

            try:
                online_path.write_text('1' if online else '0')
                results['success'].append(f"Core {core} {'online' if online else 'offline'}")
            except Exception as e:
                results['failed'].append(f"Core {core}: {e}")

        return results


if __name__ == '__main__':
    import json

    logging.basicConfig(level=logging.DEBUG)
    tuner = CPUTuner(Path('/tmp/cpu_backup'))

    print("=== CPU Settings ===")
    settings = tuner.get_current_settings()
    print(json.dumps(settings, indent=2))
