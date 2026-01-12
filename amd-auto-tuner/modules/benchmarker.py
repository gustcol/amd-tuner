#!/usr/bin/env python3
"""
Benchmarker Module
System benchmarking for CPU, storage, and network performance
"""

import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging
import os


class Benchmarker:
    """Handles system performance benchmarking."""

    def __init__(self, results_dir: Path):
        """
        Initialize the benchmarker.

        Args:
            results_dir: Directory to store benchmark results
        """
        self.logger = logging.getLogger('AMDAutoTuner.Benchmarker')
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(exist_ok=True)

    def benchmark_cpu(self, duration: int = 10) -> Dict[str, Any]:
        """
        Run CPU benchmarks.

        Args:
            duration: Duration of benchmark in seconds

        Returns:
            Dictionary containing CPU benchmark results
        """
        self.logger.info(f"Running CPU benchmark (duration: {duration}s)...")

        results = {
            'timestamp': datetime.now().isoformat(),
            'duration_seconds': duration,
            'single_thread': None,
            'multi_thread': None,
            'sysbench_available': False
        }

        # Check if sysbench is available
        if not self._command_available('sysbench'):
            self.logger.warning("sysbench not installed. Using fallback benchmark.")
            results['single_thread'] = self._run_fallback_cpu_benchmark(1, duration)
            cpu_count = os.cpu_count() or 4
            results['multi_thread'] = self._run_fallback_cpu_benchmark(cpu_count, duration)
            return results

        results['sysbench_available'] = True

        # Single-threaded benchmark
        self.logger.debug("Running single-threaded CPU benchmark...")
        single_result = self._run_sysbench_cpu(threads=1, duration=duration)
        results['single_thread'] = single_result

        # Multi-threaded benchmark
        cpu_count = os.cpu_count() or 4
        self.logger.debug(f"Running multi-threaded CPU benchmark ({cpu_count} threads)...")
        multi_result = self._run_sysbench_cpu(threads=cpu_count, duration=duration)
        results['multi_thread'] = multi_result

        return results

    def _run_sysbench_cpu(self, threads: int, duration: int) -> Dict[str, Any]:
        """Run sysbench CPU benchmark."""
        result = {
            'threads': threads,
            'events_per_second': 0,
            'total_events': 0,
            'latency_avg_ms': 0,
            'latency_95th_ms': 0
        }

        try:
            proc = subprocess.run(
                ['sysbench', 'cpu', f'--threads={threads}', f'--time={duration}', 'run'],
                capture_output=True, text=True, timeout=duration + 30
            )

            if proc.returncode == 0:
                output = proc.stdout

                for line in output.split('\n'):
                    line = line.strip()
                    if 'events per second:' in line:
                        result['events_per_second'] = float(line.split(':')[1].strip())
                    elif 'total number of events:' in line:
                        result['total_events'] = int(line.split(':')[1].strip())
                    elif 'avg:' in line and 'latency' not in line.lower():
                        pass
                    elif line.startswith('avg:'):
                        result['latency_avg_ms'] = float(line.split(':')[1].strip().replace('ms', ''))
                    elif '95th percentile:' in line:
                        result['latency_95th_ms'] = float(line.split(':')[1].strip().replace('ms', ''))
        except subprocess.TimeoutExpired:
            self.logger.error("CPU benchmark timed out")
        except Exception as e:
            self.logger.error(f"CPU benchmark failed: {e}")

        return result

    def _run_fallback_cpu_benchmark(self, threads: int, duration: int) -> Dict[str, Any]:
        """Run a simple Python-based CPU benchmark as fallback."""
        result = {
            'threads': threads,
            'operations_per_second': 0,
            'total_operations': 0
        }

        import threading
        import math

        operations = [0] * threads
        stop_flag = threading.Event()

        def cpu_work(thread_id: int):
            count = 0
            while not stop_flag.is_set():
                # Simple CPU-intensive work
                for _ in range(1000):
                    math.sqrt(12345.6789)
                    math.sin(12345.6789)
                count += 1000
            operations[thread_id] = count

        # Start threads
        thread_list = []
        for i in range(threads):
            t = threading.Thread(target=cpu_work, args=(i,))
            t.start()
            thread_list.append(t)

        # Wait for duration
        time.sleep(duration)
        stop_flag.set()

        # Wait for threads to finish
        for t in thread_list:
            t.join()

        total_ops = sum(operations)
        result['total_operations'] = total_ops
        result['operations_per_second'] = total_ops / duration

        return result

    def benchmark_storage(self, devices: List[Dict[str, Any]],
                          test_size: str = '1G') -> Dict[str, Any]:
        """
        Run storage benchmarks.

        Args:
            devices: List of storage device information
            test_size: Size of test file

        Returns:
            Dictionary containing storage benchmark results
        """
        self.logger.info("Running storage benchmark...")

        results = {
            'timestamp': datetime.now().isoformat(),
            'test_size': test_size,
            'devices': {},
            'fio_available': False
        }

        # Check if fio is available
        if not self._command_available('fio'):
            self.logger.warning("fio not installed. Using fallback benchmark.")
            for device in devices:
                name = device['name']
                results['devices'][name] = self._run_fallback_storage_benchmark(device)
            return results

        results['fio_available'] = True

        for device in devices:
            name = device['name']
            self.logger.debug(f"Benchmarking {name}...")

            # Only benchmark if device is mounted and writable
            mount_point = self._get_mount_point(name)
            if mount_point:
                results['devices'][name] = self._run_fio_benchmark(mount_point, test_size)
            else:
                results['devices'][name] = {'error': 'Device not mounted or not accessible'}

        return results

    def _run_fio_benchmark(self, path: str, size: str) -> Dict[str, Any]:
        """Run fio benchmark on a path."""
        result = {
            'sequential_read_mbps': 0,
            'sequential_write_mbps': 0,
            'random_read_iops': 0,
            'random_write_iops': 0,
            'latency_read_us': 0,
            'latency_write_us': 0
        }

        test_file = Path(path) / '.amd_tuner_benchmark_test'

        try:
            # Sequential read
            seq_read = self._run_fio_test(test_file, 'read', 'seq', size)
            result['sequential_read_mbps'] = seq_read.get('bandwidth_mbps', 0)

            # Sequential write
            seq_write = self._run_fio_test(test_file, 'write', 'seq', size)
            result['sequential_write_mbps'] = seq_write.get('bandwidth_mbps', 0)

            # Random read
            rand_read = self._run_fio_test(test_file, 'randread', 'rand', '256M')
            result['random_read_iops'] = rand_read.get('iops', 0)
            result['latency_read_us'] = rand_read.get('latency_us', 0)

            # Random write
            rand_write = self._run_fio_test(test_file, 'randwrite', 'rand', '256M')
            result['random_write_iops'] = rand_write.get('iops', 0)
            result['latency_write_us'] = rand_write.get('latency_us', 0)

        except Exception as e:
            self.logger.error(f"FIO benchmark failed: {e}")
            result['error'] = str(e)
        finally:
            # Clean up test file
            if test_file.exists():
                test_file.unlink()

        return result

    def _run_fio_test(self, filename: Path, rw: str, pattern: str, size: str) -> Dict[str, Any]:
        """Run a single fio test."""
        result = {'bandwidth_mbps': 0, 'iops': 0, 'latency_us': 0}

        bs = '4k' if pattern == 'rand' else '1M'

        try:
            proc = subprocess.run(
                [
                    'fio',
                    f'--name={pattern}_{rw}',
                    f'--filename={filename}',
                    f'--rw={rw}',
                    f'--bs={bs}',
                    f'--size={size}',
                    '--ioengine=libaio',
                    '--direct=1',
                    '--runtime=10',
                    '--time_based',
                    '--group_reporting',
                    '--output-format=json'
                ],
                capture_output=True, text=True, timeout=60
            )

            if proc.returncode == 0:
                data = json.loads(proc.stdout)
                job = data['jobs'][0]

                if 'read' in rw:
                    result['bandwidth_mbps'] = job['read']['bw'] / 1024  # KB/s to MB/s
                    result['iops'] = job['read']['iops']
                    result['latency_us'] = job['read']['lat_ns']['mean'] / 1000  # ns to us
                else:
                    result['bandwidth_mbps'] = job['write']['bw'] / 1024
                    result['iops'] = job['write']['iops']
                    result['latency_us'] = job['write']['lat_ns']['mean'] / 1000

        except subprocess.TimeoutExpired:
            self.logger.error("FIO test timed out")
        except Exception as e:
            self.logger.debug(f"FIO test error: {e}")

        return result

    def _run_fallback_storage_benchmark(self, device: Dict[str, Any]) -> Dict[str, Any]:
        """Run a simple dd-based storage benchmark as fallback."""
        result = {
            'method': 'dd_fallback',
            'error': 'Device not benchmarked (fio not available)'
        }

        mount_point = self._get_mount_point(device['name'])
        if not mount_point:
            return result

        test_file = Path(mount_point) / '.amd_tuner_benchmark_test'

        try:
            # Write test
            start = time.time()
            proc = subprocess.run(
                ['dd', 'if=/dev/zero', f'of={test_file}', 'bs=1M', 'count=256', 'conv=fdatasync'],
                capture_output=True, text=True, timeout=60
            )
            write_time = time.time() - start

            if proc.returncode == 0:
                result['write_mbps'] = 256 / write_time

            # Read test
            subprocess.run(['sync'], timeout=5)
            subprocess.run(['echo', '3', '>', '/proc/sys/vm/drop_caches'],
                          shell=True, capture_output=True, timeout=5)

            start = time.time()
            proc = subprocess.run(
                ['dd', f'if={test_file}', 'of=/dev/null', 'bs=1M'],
                capture_output=True, text=True, timeout=60
            )
            read_time = time.time() - start

            if proc.returncode == 0:
                result['read_mbps'] = 256 / read_time

            del result['error']
        except Exception as e:
            result['error'] = str(e)
        finally:
            if test_file.exists():
                test_file.unlink()

        return result

    def _get_mount_point(self, device: str) -> Optional[str]:
        """Get mount point for a device."""
        try:
            proc = subprocess.run(
                ['lsblk', '-no', 'MOUNTPOINT', f'/dev/{device}'],
                capture_output=True, text=True, timeout=5
            )

            if proc.returncode == 0:
                mount_points = proc.stdout.strip().split('\n')
                for mp in mount_points:
                    if mp and mp != '' and os.access(mp, os.W_OK):
                        return mp

            # Check partitions
            proc = subprocess.run(
                ['lsblk', '-no', 'NAME,MOUNTPOINT', f'/dev/{device}'],
                capture_output=True, text=True, timeout=5
            )

            if proc.returncode == 0:
                for line in proc.stdout.strip().split('\n'):
                    parts = line.split()
                    if len(parts) >= 2:
                        mp = parts[-1]
                        if mp and mp != '' and os.access(mp, os.W_OK):
                            return mp

        except Exception:
            pass

        return None

    def benchmark_network(self, target: str = '8.8.8.8') -> Dict[str, Any]:
        """
        Run network benchmarks.

        Args:
            target: Target for latency test

        Returns:
            Dictionary containing network benchmark results
        """
        self.logger.info("Running network benchmark...")

        results = {
            'timestamp': datetime.now().isoformat(),
            'target': target,
            'latency': self._run_latency_test(target),
            'bandwidth': None  # Would require iperf3 server
        }

        return results

    def _run_latency_test(self, target: str, count: int = 10) -> Dict[str, Any]:
        """Run ping latency test."""
        result = {
            'min_ms': 0,
            'avg_ms': 0,
            'max_ms': 0,
            'packet_loss_percent': 100
        }

        try:
            proc = subprocess.run(
                ['ping', '-c', str(count), target],
                capture_output=True, text=True, timeout=count + 10
            )

            if proc.returncode == 0:
                output = proc.stdout

                # Parse packet loss
                for line in output.split('\n'):
                    if 'packet loss' in line:
                        # Format: "X packets transmitted, Y received, Z% packet loss"
                        import re
                        match = re.search(r'(\d+(?:\.\d+)?)%\s+packet loss', line)
                        if match:
                            result['packet_loss_percent'] = float(match.group(1))

                    # Parse latency stats
                    if 'min/avg/max' in line or 'rtt min/avg/max' in line:
                        # Format: "rtt min/avg/max/mdev = 1.234/5.678/9.012/1.234 ms"
                        match = re.search(r'([\d.]+)/([\d.]+)/([\d.]+)', line)
                        if match:
                            result['min_ms'] = float(match.group(1))
                            result['avg_ms'] = float(match.group(2))
                            result['max_ms'] = float(match.group(3))

        except subprocess.TimeoutExpired:
            self.logger.error("Ping test timed out")
        except Exception as e:
            self.logger.error(f"Ping test failed: {e}")
            result['error'] = str(e)

        return result

    def compare_results(self, before: Dict[str, Any],
                        after: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compare two benchmark results.

        Args:
            before: Benchmark results before tuning
            after: Benchmark results after tuning

        Returns:
            Dictionary containing comparison with improvements
        """
        comparison = {
            'timestamp': datetime.now().isoformat(),
            'cpu': {},
            'storage': {},
            'network': {}
        }

        # CPU comparison
        if 'cpu' in before and 'cpu' in after:
            if before['cpu'].get('single_thread') and after['cpu'].get('single_thread'):
                before_st = before['cpu']['single_thread'].get('events_per_second', 0)
                after_st = after['cpu']['single_thread'].get('events_per_second', 0)
                if before_st > 0:
                    improvement = ((after_st - before_st) / before_st) * 100
                    comparison['cpu']['single_thread_improvement_percent'] = round(improvement, 2)

            if before['cpu'].get('multi_thread') and after['cpu'].get('multi_thread'):
                before_mt = before['cpu']['multi_thread'].get('events_per_second', 0)
                after_mt = after['cpu']['multi_thread'].get('events_per_second', 0)
                if before_mt > 0:
                    improvement = ((after_mt - before_mt) / before_mt) * 100
                    comparison['cpu']['multi_thread_improvement_percent'] = round(improvement, 2)

        # Storage comparison
        if 'storage' in before and 'storage' in after:
            for device in before.get('storage', {}).get('devices', {}):
                if device in after.get('storage', {}).get('devices', {}):
                    b_dev = before['storage']['devices'][device]
                    a_dev = after['storage']['devices'][device]

                    comparison['storage'][device] = {}

                    for metric in ['sequential_read_mbps', 'sequential_write_mbps',
                                   'random_read_iops', 'random_write_iops']:
                        if metric in b_dev and metric in a_dev:
                            before_val = b_dev[metric]
                            after_val = a_dev[metric]
                            if before_val > 0:
                                improvement = ((after_val - before_val) / before_val) * 100
                                comparison['storage'][device][f'{metric}_improvement_percent'] = round(improvement, 2)

        # Network comparison
        if 'network' in before and 'network' in after:
            if 'latency' in before['network'] and 'latency' in after['network']:
                b_lat = before['network']['latency'].get('avg_ms', 0)
                a_lat = after['network']['latency'].get('avg_ms', 0)
                if b_lat > 0:
                    # Lower latency is better, so negative improvement is good
                    improvement = ((b_lat - a_lat) / b_lat) * 100
                    comparison['network']['latency_improvement_percent'] = round(improvement, 2)

        return comparison

    def save_results(self, results: Dict[str, Any], name: str = 'benchmark') -> str:
        """
        Save benchmark results to file.

        Args:
            results: Benchmark results to save
            name: Name prefix for the file

        Returns:
            Path to saved file
        """
        filename = f"{name}_{datetime.now():%Y%m%d_%H%M%S}.json"
        filepath = self.results_dir / filename

        with open(filepath, 'w') as f:
            json.dump(results, f, indent=2, default=str)

        self.logger.info(f"Benchmark results saved: {filepath}")
        return str(filepath)

    def load_results(self, filepath: str) -> Dict[str, Any]:
        """
        Load benchmark results from file.

        Args:
            filepath: Path to results file

        Returns:
            Loaded benchmark results
        """
        with open(filepath) as f:
            return json.load(f)

    def _command_available(self, command: str) -> bool:
        """Check if a command is available."""
        try:
            subprocess.run(
                ['which', command],
                capture_output=True, timeout=5
            )
            return True
        except Exception:
            return False


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    benchmarker = Benchmarker(Path('/tmp/benchmarks'))

    print("=== CPU Benchmark ===")
    cpu_results = benchmarker.benchmark_cpu(duration=5)
    print(json.dumps(cpu_results, indent=2))

    print("\n=== Network Benchmark ===")
    network_results = benchmarker.benchmark_network()
    print(json.dumps(network_results, indent=2))
