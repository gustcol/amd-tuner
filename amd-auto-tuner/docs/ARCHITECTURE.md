# AMD Auto Tuner - Architecture Documentation

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            AMD Auto Tuner                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                              main.py                                         │
│                        (Orchestrator/CLI)                                    │
├────────────┬────────────┬────────────┬────────────┬────────────┬───────────┤
│            │            │            │            │            │            │
│  Hardware  │    CPU     │  Storage   │  Network   │    HPC     │  Memory   │
│  Detector  │   Tuner    │   Tuner    │   Tuner    │   Tuner    │  Tuner    │
│            │            │            │            │            │            │
├────────────┴────────────┴────────────┴────────────┴────────────┴───────────┤
│                              Benchmarker                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                            Config Manager                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                          Linux Kernel/sysfs                                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
amd-auto-tuner/
├── main.py                    # Main orchestrator and CLI entry point
├── install.sh                 # Installation script
├── examples.py                # Usage examples
├── requirements.txt           # Python dependencies
│
├── modules/                   # Core modules
│   ├── __init__.py           # Module exports
│   ├── hardware_detector.py  # Hardware detection
│   ├── cpu_tuner.py          # CPU optimization
│   ├── storage_tuner.py      # Storage optimization
│   ├── network_tuner.py      # Network optimization
│   ├── hpc_tuner.py          # HPC/NUMA optimization
│   ├── memory_tuner.py       # Memory subsystem optimization
│   ├── benchmarker.py        # Performance benchmarking
│   └── config_manager.py     # Configuration management
│
├── config/                    # Configuration files
│   └── config.yaml           # Default configuration
│
├── docs/                      # Documentation
│   ├── README.md             # User guide
│   ├── ARCHITECTURE.md       # This file
│   └── GETTING_STARTED.md    # Quick start guide
│
├── logs/                      # Runtime logs (auto-created)
├── backups/                   # Configuration backups (auto-created)
├── benchmarks/                # Benchmark results (auto-created)
└── reports/                   # Generated reports (auto-created)
```

## Component Details

### 1. Main Orchestrator (main.py)

The main entry point that coordinates all operations:

- **AMDAutoTuner Class**: Central orchestrator that initializes all components
- **CLI Interface**: argparse-based command-line interface
- **Profile Management**: Pre-defined and custom performance profiles
- **Interactive Mode**: Menu-driven interface for manual operation

Key responsibilities:
- Initialize and coordinate all tuning modules
- Handle CLI arguments and dispatch to appropriate methods
- Manage logging and directory structure
- Generate comprehensive reports

### 2. Hardware Detector (hardware_detector.py)

Detects and catalogs system hardware:

**CPU Detection**:
- Model, vendor, cores, threads
- Zen generation detection (Zen1, Zen+, Zen2, Zen3, Zen4)
- Frequency capabilities (min, max, current)
- Governor and boost status
- AMD P-State driver detection
- Cache hierarchy

**Storage Detection**:
- Block devices (NVMe, SSD, HDD)
- Device type detection (rotational, transport)
- Current scheduler and available schedulers
- Queue parameters (read-ahead, nr_requests)

**Network Detection**:
- Physical and virtual interfaces
- Driver identification
- Ring buffer sizes
- Offload capabilities
- Current sysctl settings

### 3. CPU Tuner (cpu_tuner.py)

Optimizes AMD CPU performance:

**Capabilities**:
- Governor selection (performance, powersave, schedutil, ondemand)
- Frequency scaling (min/max limits)
- Boost control (enable/disable)
- Energy Performance Preference (AMD P-State)
- C-state management (via ZenStates if available)
- Per-core online/offline control

**Implementation**:
- Direct sysfs manipulation (`/sys/devices/system/cpu/`)
- Backup before changes
- Validation of available governors

### 4. Storage Tuner (storage_tuner.py)

Optimizes storage device performance:

**Capabilities**:
- I/O scheduler selection (none, mq-deadline, bfq, kyber)
- Read-ahead tuning
- Queue depth (nr_requests)
- Request merging control
- TRIM support

**Workload Profiles**:
- Database: Low latency, no merging
- Webserver: Balanced read/write
- Desktop: Fair scheduling (BFQ)
- Throughput: Large read-ahead, deep queues
- Latency: Minimal read-ahead, shallow queues

### 5. Network Tuner (network_tuner.py)

Optimizes network interface performance:

**Capabilities**:
- Ring buffer sizing
- Hardware offloads (GSO, GRO, TSO, checksum)
- Interrupt coalescing
- Driver-specific optimizations
- Sysctl tuning
- High-speed NIC support (25G, 50G, 100G, 200G, 400G)

**Sysctl Optimizations**:
- Socket buffer sizes (rmem_max, wmem_max)
- TCP buffer tuning
- Backlog queue sizes
- Congestion control (BBR, CUBIC)
- TCP fast open, MTU probing

**Supported NICs**:
- Intel: ice (E810), i40e (XL710), ixgbe, igb, e1000e
- Mellanox: ConnectX-4/5/6/7 (mlx5_core)
- Broadcom: bnxt_en
- AMD/Pensando: ionic

### 6. HPC Tuner (hpc_tuner.py)

Optimizes systems for High-Performance Computing workloads:

**NUMA Optimization**:
- NUMA topology detection and mapping
- Memory interleaving configuration
- NUMA balancing control
- Node-aware process placement

**Huge Pages**:
- 2MB and 1GB huge page allocation
- Transparent Huge Pages (THP) management
- Huge page pool configuration
- NUMA-aware huge page distribution

**IRQ Affinity**:
- CPU affinity optimization for interrupts
- Network IRQ distribution across NUMA nodes
- Storage IRQ optimization

**Process Affinity**:
- CPU pinning recommendations
- NUMA-aware task placement
- Core isolation configuration

**HPC Integration**:
- MPI optimization hints and environment variables
- SLURM configuration generation
- OpenMP thread affinity settings
- Kernel parameter optimization for HPC

### 7. Memory Tuner (memory_tuner.py)

Optimizes memory subsystem performance:

**Memory Technology Support**:
- HBM3 (High Bandwidth Memory) optimization
- DDR5 configuration and tuning
- Multi-channel memory optimization

**NUMA Memory Management**:
- NUMA balancing configuration
- Memory policy settings
- Inter-node memory migration control

**Kernel Memory Settings**:
- Swappiness tuning
- Zone reclaim policy
- Dirty ratio optimization
- Page cache management
- Writeback configuration

**Transparent Huge Pages**:
- THP enable/disable control
- Defragmentation settings
- khugepaged configuration

### 8. Benchmarker (benchmarker.py)

Measures system performance:

**CPU Benchmarks**:
- Single-threaded performance (sysbench)
- Multi-threaded performance
- Fallback Python-based benchmark

**Storage Benchmarks**:
- Sequential read/write (fio)
- Random read/write IOPS
- Latency measurements
- Fallback dd-based benchmark

**Network Benchmarks**:
- Latency (ping)
- Packet loss measurement

**Features**:
- Before/after comparison
- JSON result storage
- Performance improvement calculation

### 9. Config Manager (config_manager.py)

Handles configuration:

- YAML configuration loading
- Default configuration management
- Deep merge of user overrides
- Dot-notation access (e.g., `get('cpu.enabled')`)
- Configuration validation

## Data Flow

### Apply Profile Flow

```
User Command → main.py → detect_hardware()
                              ↓
                    HardwareDetector.detect_all()
                              ↓
    ┌─────────────┬─────────────┬─────────────┬─────────────┬─────────────┐
    ↓             ↓             ↓             ↓             ↓             ↓
CPU Tuner   Storage Tuner Network Tuner  HPC Tuner   Memory Tuner
    ↓             ↓             ↓             ↓             ↓
create_backup() for each component
    ↓             ↓             ↓             ↓             ↓
apply_profile() for each component
    ↓             ↓             ↓             ↓             ↓
Write to sysfs / ethtool / sysctl / numactl
                              ↓
                         save_report()
```

### Benchmark Flow

```
User Command → main.py → run_benchmarks()
                              ↓
                    Benchmarker.benchmark_*()
                              ↓
              ┌───────────────┼───────────────┐
              ↓               ↓               ↓
         CPU Bench    Storage Bench    Network Bench
         (sysbench)      (fio)          (ping)
              ↓               ↓               ↓
         Parse results
              ↓
         save_results()
```

## Interface with Linux Kernel

### sysfs Paths

**CPU**:
- `/sys/devices/system/cpu/cpu*/cpufreq/scaling_governor`
- `/sys/devices/system/cpu/cpu*/cpufreq/scaling_min_freq`
- `/sys/devices/system/cpu/cpu*/cpufreq/scaling_max_freq`
- `/sys/devices/system/cpu/cpufreq/boost`
- `/sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference`

**Storage**:
- `/sys/block/*/queue/scheduler`
- `/sys/block/*/queue/read_ahead_kb`
- `/sys/block/*/queue/nr_requests`
- `/sys/block/*/queue/rotational`

**Network**:
- `/sys/class/net/*/mtu`
- `/sys/class/net/*/tx_queue_len`

**HPC/NUMA**:
- `/sys/devices/system/node/node*/hugepages/`
- `/sys/kernel/mm/hugepages/`
- `/proc/sys/vm/nr_hugepages`
- `/sys/devices/system/node/node*/cpulist`
- `/proc/irq/*/smp_affinity`

**Memory**:
- `/proc/sys/vm/swappiness`
- `/proc/sys/vm/dirty_ratio`
- `/proc/sys/vm/dirty_background_ratio`
- `/proc/sys/vm/zone_reclaim_mode`
- `/sys/kernel/mm/transparent_hugepage/enabled`
- `/proc/sys/kernel/numa_balancing`

### External Tools

- `ethtool`: Ring buffers, offloads, coalescing
- `sysctl`: Kernel network and memory parameters
- `sysbench`: CPU benchmarking
- `fio`: Storage benchmarking
- `sensors`: Temperature monitoring
- `numactl`: NUMA topology and memory policy
- `cpupower`: CPU frequency and governor control

## Error Handling

1. **Graceful Degradation**: If a tool isn't available, fallback methods are used
2. **Backup on Change**: Settings are backed up before modification
3. **Dry Run Mode**: Preview changes without applying
4. **Logging**: Detailed logging for troubleshooting
5. **Validation**: Configuration and hardware capability validation

## Extension Points

### Adding New Profiles

Edit `main.py`, method `_get_profile_config()`:

```python
'my_profile': {
    'cpu': {
        'governor': 'performance',
        'boost': True,
        ...
    },
    'storage': {...},
    'network': {...}
}
```

### Adding New Tuning Options

1. Add method in appropriate tuner class
2. Add sysfs path handling
3. Update `apply_profile()` to call new method
4. Update `get_current_settings()` to read new setting
