#!/usr/bin/env python3
"""
Config Manager Module
Handles loading, saving, and managing configuration files
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
import logging


class ConfigManager:
    """Handles configuration file management."""

    DEFAULT_CONFIG: Dict[str, Any] = {
        'version': '1.0.0',
        'logging': {
            'level': 'INFO',
            'file_logging': True,
            'console_logging': True
        },
        'backup': {
            'enabled': True,
            'max_backups': 10,
            'auto_restore_on_failure': False
        },
        'profiles': {
            'default': 'balanced'
        },
        'cpu': {
            'enabled': True,
            'auto_detect_workload': False,
            'safe_mode': True,
            'max_temperature_celsius': 85
        },
        'storage': {
            'enabled': True,
            'auto_trim': False,
            'trim_schedule': 'weekly'
        },
        'network': {
            'enabled': True,
            'optimize_sysctl': True,
            'preserve_custom_sysctl': True
        },
        'benchmarks': {
            'cpu_duration_seconds': 10,
            'storage_test_size': '1G',
            'network_ping_count': 10
        }
    }

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize the config manager.

        Args:
            config_path: Path to configuration file
        """
        self.logger = logging.getLogger('AMDAutoTuner.ConfigManager')
        self.config_path = Path(config_path) if config_path else None
        self._config: Optional[Dict[str, Any]] = None

    def load(self) -> Dict[str, Any]:
        """
        Load configuration from file.

        Returns:
            Configuration dictionary
        """
        if self._config is not None:
            return self._config

        config = self.DEFAULT_CONFIG.copy()

        if self.config_path and self.config_path.exists():
            try:
                file_config = self._load_yaml(self.config_path)
                config = self._merge_configs(config, file_config)
                self.logger.info(f"Loaded configuration from {self.config_path}")
            except Exception as e:
                self.logger.warning(f"Could not load config file: {e}. Using defaults.")

        self._config = config
        return config

    def _load_yaml(self, path: Path) -> Dict[str, Any]:
        """Load YAML configuration file."""
        try:
            import yaml
            with open(path) as f:
                return yaml.safe_load(f) or {}
        except ImportError:
            self.logger.warning("PyYAML not installed. Trying JSON fallback.")
            return self._load_json_fallback(path)

    def _load_json_fallback(self, path: Path) -> Dict[str, Any]:
        """Load configuration as JSON if YAML fails."""
        import json

        # Try to parse YAML-like content as JSON
        # This is a simple fallback that works for basic configs
        json_path = path.with_suffix('.json')
        if json_path.exists():
            with open(json_path) as f:
                return json.load(f)

        return {}

    def save(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """
        Save configuration to file.

        Args:
            config: Configuration to save (uses current if None)

        Returns:
            True if successful
        """
        if config is None:
            config = self._config or self.DEFAULT_CONFIG

        if not self.config_path:
            self.logger.error("No config path specified")
            return False

        try:
            # Ensure directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            try:
                import yaml
                with open(self.config_path, 'w') as f:
                    yaml.dump(config, f, default_flow_style=False, sort_keys=False)
            except ImportError:
                # Fallback to JSON
                import json
                json_path = self.config_path.with_suffix('.json')
                with open(json_path, 'w') as f:
                    json.dump(config, f, indent=2)
                self.logger.info(f"Saved as JSON (PyYAML not installed): {json_path}")
                return True

            self.logger.info(f"Configuration saved to {self.config_path}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to save configuration: {e}")
            return False

    def _merge_configs(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deep merge two configuration dictionaries.

        Args:
            base: Base configuration
            override: Configuration to override with

        Returns:
            Merged configuration
        """
        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value

        return result

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value by dot-separated key.

        Args:
            key: Dot-separated key (e.g., 'cpu.enabled')
            default: Default value if key not found

        Returns:
            Configuration value
        """
        config = self.load()
        keys = key.split('.')

        value = config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any) -> bool:
        """
        Set a configuration value by dot-separated key.

        Args:
            key: Dot-separated key (e.g., 'cpu.enabled')
            value: Value to set

        Returns:
            True if successful
        """
        config = self.load()
        keys = key.split('.')

        # Navigate to parent
        current = config
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]

        # Set value
        current[keys[-1]] = value
        self._config = config

        return True

    def reset(self) -> Dict[str, Any]:
        """
        Reset configuration to defaults.

        Returns:
            Default configuration
        """
        self._config = self.DEFAULT_CONFIG.copy()
        return self._config

    def validate(self, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Validate configuration.

        Args:
            config: Configuration to validate (uses current if None)

        Returns:
            Dictionary with 'valid' boolean and 'errors' list
        """
        if config is None:
            config = self.load()

        errors = []

        # Validate required sections
        required_sections = ['cpu', 'storage', 'network']
        for section in required_sections:
            if section not in config:
                errors.append(f"Missing required section: {section}")

        # Validate CPU settings
        if 'cpu' in config:
            cpu = config['cpu']
            if 'max_temperature_celsius' in cpu:
                temp = cpu['max_temperature_celsius']
                if not isinstance(temp, (int, float)) or temp < 50 or temp > 105:
                    errors.append(f"Invalid max_temperature_celsius: {temp} (must be 50-105)")

        # Validate benchmark settings
        if 'benchmarks' in config:
            bench = config['benchmarks']
            if 'cpu_duration_seconds' in bench:
                duration = bench['cpu_duration_seconds']
                if not isinstance(duration, int) or duration < 1 or duration > 3600:
                    errors.append(f"Invalid cpu_duration_seconds: {duration} (must be 1-3600)")

        return {
            'valid': len(errors) == 0,
            'errors': errors
        }

    def create_default_config(self) -> bool:
        """
        Create a default configuration file.

        Returns:
            True if successful
        """
        if not self.config_path:
            self.logger.error("No config path specified")
            return False

        return self.save(self.DEFAULT_CONFIG)


if __name__ == '__main__':
    import json

    logging.basicConfig(level=logging.DEBUG)

    # Test config manager
    config_path = Path('/tmp/test_config.yaml')
    manager = ConfigManager(config_path)

    print("=== Default Configuration ===")
    config = manager.load()
    print(json.dumps(config, indent=2))

    print("\n=== Get specific value ===")
    print(f"cpu.enabled: {manager.get('cpu.enabled')}")
    print(f"benchmarks.cpu_duration_seconds: {manager.get('benchmarks.cpu_duration_seconds')}")

    print("\n=== Validation ===")
    validation = manager.validate()
    print(json.dumps(validation, indent=2))
