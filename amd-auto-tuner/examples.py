#!/usr/bin/env python3
"""
AMD Auto Tuner - Usage Examples
================================
This file contains examples of how to use the AMD Auto Tuner
programmatically in your own Python scripts.
"""

import json
import sys
from pathlib import Path

# Add the project root to path
sys.path.insert(0, str(Path(__file__).parent))

from main import AMDAutoTuner


def example_basic_detection():
    """Example: Basic hardware detection."""
    print("=" * 60)
    print("Example 1: Basic Hardware Detection")
    print("=" * 60)

    tuner = AMDAutoTuner(verbose=True)

    # Detect all hardware
    hardware = tuner.detect_hardware()

    # Print CPU information
    cpu = hardware.get('cpu', {})
    print(f"\nCPU: {cpu.get('model', 'Unknown')}")
    print(f"  Cores: {cpu.get('cores', 0)}")
    print(f"  Threads: {cpu.get('threads', 0)}")
    print(f"  Governor: {cpu.get('governor', 'Unknown')}")
    print(f"  Zen Generation: {cpu.get('zen_generation', 'Unknown')}")

    # Print storage devices
    print("\nStorage Devices:")
    for device in hardware.get('storage', []):
        print(f"  {device['name']}: {device['type']} - {device['size_human']}")

    # Print network interfaces
    print("\nNetwork Interfaces:")
    for iface in hardware.get('network', []):
        print(f"  {iface['name']}: {iface.get('speed', 0)} Mbps ({iface.get('state', 'unknown')})")


def example_apply_profile():
    """Example: Apply a performance profile."""
    print("\n" + "=" * 60)
    print("Example 2: Apply Performance Profile")
    print("=" * 60)

    tuner = AMDAutoTuner(verbose=True)

    # Dry run first to see what would change
    print("\nSimulating 'performance' profile (dry run):")
    changes = tuner.apply_profile('performance', dry_run=True)

    print("\nCPU changes:")
    for change in changes.get('cpu', {}).get('applied', []):
        print(f"  - {change}")

    print("\nStorage changes:")
    for device, device_changes in changes.get('storage', {}).items():
        if device_changes.get('applied'):
            print(f"  {device}:")
            for change in device_changes['applied']:
                print(f"    - {change}")

    print("\nNetwork changes:")
    for iface, iface_changes in changes.get('network', {}).get('interfaces', {}).items():
        if iface_changes.get('applied'):
            print(f"  {iface}:")
            for change in iface_changes['applied']:
                print(f"    - {change}")


def example_custom_tuning():
    """Example: Apply custom tuning settings."""
    print("\n" + "=" * 60)
    print("Example 3: Custom CPU Tuning")
    print("=" * 60)

    tuner = AMDAutoTuner(verbose=True)

    # Custom CPU settings
    custom_cpu_settings = {
        'governor': 'schedutil',
        'boost': True,
        'min_freq_percent': 50,
        'max_freq_percent': 100,
        'energy_performance': 'balance_performance'
    }

    print("\nApplying custom CPU settings (dry run):")
    changes = tuner.tune_cpu(settings=custom_cpu_settings, dry_run=True)

    for change in changes.get('applied', []):
        print(f"  - {change}")


def example_benchmarking():
    """Example: Run benchmarks."""
    print("\n" + "=" * 60)
    print("Example 4: Running Benchmarks")
    print("=" * 60)

    tuner = AMDAutoTuner(verbose=True)

    # Run only CPU benchmarks (faster)
    print("\nRunning CPU benchmark (5 seconds)...")
    results = tuner.run_benchmarks(categories=['cpu'])

    cpu_results = results.get('cpu', {})
    if cpu_results.get('single_thread'):
        st = cpu_results['single_thread']
        print(f"\nSingle-thread performance:")
        print(f"  Events/sec: {st.get('events_per_second', 0):.2f}")

    if cpu_results.get('multi_thread'):
        mt = cpu_results['multi_thread']
        print(f"\nMulti-thread performance ({mt.get('threads', 0)} threads):")
        print(f"  Events/sec: {mt.get('events_per_second', 0):.2f}")


def example_generate_report():
    """Example: Generate a system report."""
    print("\n" + "=" * 60)
    print("Example 5: Generate System Report")
    print("=" * 60)

    tuner = AMDAutoTuner(verbose=True)

    report = tuner.generate_report()

    print(f"\nReport generated at: {report['timestamp']}")
    print(f"AMD Auto Tuner version: {report['version']}")

    # Current CPU settings
    cpu_settings = report.get('current_settings', {}).get('cpu', {})
    print(f"\nCurrent CPU Settings:")
    print(f"  Governor: {cpu_settings.get('governor', 'Unknown')}")
    print(f"  Boost: {cpu_settings.get('boost_enabled', 'Unknown')}")
    print(f"  Driver: {cpu_settings.get('driver', 'Unknown')}")


def example_workload_optimization():
    """Example: Optimize for specific workloads."""
    print("\n" + "=" * 60)
    print("Example 6: Workload-Specific Optimization")
    print("=" * 60)

    tuner = AMDAutoTuner(verbose=True)

    # Different profile examples
    profiles = {
        'gaming': {
            'description': 'Optimized for gaming (low latency, high performance)',
            'profile': 'gaming'
        },
        'server': {
            'description': 'Optimized for server workloads (throughput, stability)',
            'profile': 'server'
        },
        'powersave': {
            'description': 'Optimized for battery/power saving',
            'profile': 'powersave'
        }
    }

    for name, config in profiles.items():
        print(f"\n{name.upper()}: {config['description']}")
        changes = tuner.apply_profile(config['profile'], dry_run=True)
        cpu_changes = changes.get('cpu', {}).get('applied', [])
        if cpu_changes:
            print(f"  CPU: {', '.join(cpu_changes[:3])}")


def example_programmatic_usage():
    """Example: Full programmatic workflow."""
    print("\n" + "=" * 60)
    print("Example 7: Full Programmatic Workflow")
    print("=" * 60)

    from modules.hardware_detector import HardwareDetector
    from modules.cpu_tuner import CPUTuner
    from modules.storage_tuner import StorageTuner
    from modules.network_tuner import NetworkTuner

    backup_dir = Path('/tmp/amd_tuner_backups')
    backup_dir.mkdir(exist_ok=True)

    # Use individual components directly
    print("\n1. Detecting hardware...")
    detector = HardwareDetector()
    cpu_info = detector.detect_cpu()
    print(f"   CPU: {cpu_info.get('model', 'Unknown')}")

    print("\n2. Initializing tuners...")
    cpu_tuner = CPUTuner(backup_dir)
    storage_tuner = StorageTuner(backup_dir)
    network_tuner = NetworkTuner(backup_dir)

    print("\n3. Getting current settings...")
    current_cpu = cpu_tuner.get_current_settings()
    print(f"   Current governor: {current_cpu.get('governor', 'Unknown')}")

    print("\n4. Simulating changes...")
    settings = {
        'governor': 'performance',
        'boost': True
    }
    changes = cpu_tuner.apply_profile(settings, cpu_info, dry_run=True)
    print(f"   Would apply: {changes.get('applied', [])}")


def example_before_after_comparison():
    """Example: Before/After benchmark comparison."""
    print("\n" + "=" * 60)
    print("Example 8: Before/After Comparison")
    print("=" * 60)

    from modules.benchmarker import Benchmarker

    benchmarker = Benchmarker(Path('/tmp/benchmarks'))

    # Simulate before/after results
    before = {
        'cpu': {
            'single_thread': {'events_per_second': 1000},
            'multi_thread': {'events_per_second': 8000}
        }
    }

    after = {
        'cpu': {
            'single_thread': {'events_per_second': 1100},
            'multi_thread': {'events_per_second': 9200}
        }
    }

    comparison = benchmarker.compare_results(before, after)

    print("\nPerformance Improvements:")
    if 'cpu' in comparison:
        if 'single_thread_improvement_percent' in comparison['cpu']:
            print(f"  Single-thread: +{comparison['cpu']['single_thread_improvement_percent']}%")
        if 'multi_thread_improvement_percent' in comparison['cpu']:
            print(f"  Multi-thread: +{comparison['cpu']['multi_thread_improvement_percent']}%")


def main():
    """Run all examples."""
    print("\n" + "#" * 60)
    print("# AMD Auto Tuner - Usage Examples")
    print("#" * 60)

    examples = [
        ("Hardware Detection", example_basic_detection),
        ("Apply Profile", example_apply_profile),
        ("Custom Tuning", example_custom_tuning),
        ("Workload Optimization", example_workload_optimization),
        ("Generate Report", example_generate_report),
        ("Programmatic Usage", example_programmatic_usage),
        ("Before/After Comparison", example_before_after_comparison),
    ]

    # Quick examples that don't require benchmarking
    for name, func in examples:
        try:
            func()
        except Exception as e:
            print(f"\n[SKIP] {name}: {e}")

    print("\n" + "=" * 60)
    print("Examples completed!")
    print("=" * 60)

    # Optional: Run benchmarks (can take time)
    run_bench = input("\nRun benchmark example? (requires ~10 seconds) [y/N]: ").strip().lower()
    if run_bench == 'y':
        try:
            example_benchmarking()
        except Exception as e:
            print(f"Benchmark error: {e}")


if __name__ == '__main__':
    main()
