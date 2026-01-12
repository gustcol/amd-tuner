# AMD Auto Tuner - User Guide

## Overview

AMD Auto Tuner is an automated performance tuning framework for AMD Ryzen, Threadripper, and EPYC processors on Linux. It provides intelligent detection, benchmarking, and optimization of CPU, storage, network, HPC, and memory subsystems.

## Features

### Core Capabilities
- **Hardware Detection**: Automatically detects AMD CPU architecture, Zen generation, storage devices, and network interfaces
- **Auto-Profile Detection**: Intelligently recommends optimal profile based on hardware
- **Performance Profiles**: Pre-configured profiles for different workloads (performance, balanced, powersave, gaming, server, hpc)

### CPU Tuning
- Governor selection (performance, schedutil, powersave, ondemand, conservative)
- Frequency scaling with min/max limits
- Boost control (enable/disable)
- C-state management
- AMD P-State EPP (Energy Performance Preference)
- Per-core configuration

### Storage Tuning
- I/O scheduler optimization (none, mq-deadline, bfq, kyber)
- Queue depth (nr_requests)
- Read-ahead optimization
- TRIM management

### Network Tuning
- **High-Speed NIC Support**: 25G, 50G, 100G, 200G, 400G
- **Intel NICs**: ice, i40e, ixgbe, igb, e1000e
- **Mellanox NICs**: ConnectX-4, ConnectX-5, ConnectX-6, ConnectX-6Dx, ConnectX-7
- **Broadcom NICs**: bnxt_en
- **AMD/Pensando NICs**: ionic
- Ring buffer optimization
- Hardware offloads (TSO, GSO, GRO, LRO)
- Interrupt coalescing
- RSS (Receive Side Scaling)
- Jumbo frames
- sysctl tuning for high-throughput

### HPC Tuning (EPYC/Threadripper)
- NUMA topology optimization
- Huge pages (2M and 1G)
- IRQ affinity optimization
- Process affinity
- MPI optimization hints
- SLURM configuration generation
- Kernel optimizations for HPC workloads

### Memory Tuning
- HBM3 and DDR5 optimization
- NUMA balancing control
- Transparent Huge Pages (THP) management
- Swappiness tuning
- Zone reclaim policy
- Dirty ratio optimization

### Infrastructure
- Benchmarking: CPU, storage, and network with before/after comparison
- Backup & Restore: Automatic backup before changes
- Systemd integration: Boot-time application and periodic tuning
- JSON reports for monitoring integration

## Quick Start

```bash
# Detect hardware
sudo amd-tuner detect

# Auto-detect and apply best profile
sudo amd-tuner auto --apply

# Run benchmarks
sudo amd-tuner benchmark

# Apply a profile
sudo amd-tuner profile balanced

# Apply HPC profile (for EPYC/Threadripper)
sudo amd-tuner profile hpc

# Restore previous settings
sudo amd-tuner restore
```

## Commands

### Hardware Detection

```bash
# Detect all hardware
amd-tuner detect

# Output is JSON formatted with CPU, storage, and network info
```

### Benchmarking

```bash
# Run all benchmarks
sudo amd-tuner benchmark

# Run specific benchmarks
sudo amd-tuner benchmark --cpu
sudo amd-tuner benchmark --storage
sudo amd-tuner benchmark --network
```

### Auto Profile Detection

```bash
# Detect best profile for your hardware
sudo amd-tuner auto

# Auto-detect and apply immediately
sudo amd-tuner auto --apply
```

### Applying Profiles

```bash
# Available profiles: performance, balanced, powersave, gaming, server, hpc
sudo amd-tuner profile performance

# Apply HPC profile for EPYC/Threadripper
sudo amd-tuner profile hpc

# Dry run (see changes without applying)
sudo amd-tuner profile performance --dry-run
```

### Custom Tuning

```bash
# CPU-specific tuning
sudo amd-tuner tune-cpu --governor performance --boost true

# Storage-specific tuning
sudo amd-tuner tune-storage --scheduler mq-deadline --read-ahead 256

# Network-specific tuning
sudo amd-tuner tune-network --congestion bbr --ring-buffer-max

# High-speed network tuning (25G/100G/200G/400G)
sudo amd-tuner tune-network --high-speed

# HPC-specific tuning
sudo amd-tuner tune-hpc --huge-pages --numa-aware --irq-affinity

# HPC with 1G huge pages
sudo amd-tuner tune-hpc --huge-pages --huge-pages-size 1G

# Memory-specific tuning
sudo amd-tuner tune-memory --swappiness 10 --thp always
```

### Restore Defaults

```bash
# Restore from last backup
sudo amd-tuner restore
```

### Generate Reports

```bash
# Generate comprehensive system report
amd-tuner report
```

### Interactive Mode

```bash
# Launch interactive menu
sudo amd-tuner interactive
```

## Profiles

### Performance Profile
- Governor: performance
- Boost: enabled
- Min frequency: 80%
- C6 state: disabled
- Network: BBR congestion control, max ring buffers

**Best for**: Gaming, video rendering, compilation, benchmarking

### Balanced Profile (Default)
- Governor: schedutil
- Boost: enabled
- Min frequency: 40%
- C6 state: enabled

**Best for**: General desktop use, web browsing, light productivity

### Powersave Profile
- Governor: powersave
- Boost: disabled
- Max frequency: 70%
- C6 state: enabled

**Best for**: Laptop battery saving, low-load server, idle system

### Gaming Profile
- Governor: performance
- Boost: enabled
- Min frequency: 70%
- Interrupt coalescing: disabled (lower latency)

**Best for**: Gaming with low latency requirements

### Server Profile
- Governor: schedutil
- Boost: enabled
- Min frequency: 50%
- Network: optimized for throughput, high-speed NIC support

**Best for**: Web servers, database servers, containerized workloads

### HPC Profile
- Governor: performance
- Boost: enabled
- Min frequency: 100% (no frequency scaling)
- C6 state: disabled
- NUMA: optimized with memory interleave
- Huge pages: enabled (2M default)
- IRQ affinity: optimized
- Network: RDMA-ready, jumbo frames

**Best for**: Scientific computing, simulations, machine learning, data analytics

## Configuration

Configuration file location: `/etc/amd-auto-tuner/config.yaml`

Example configuration:

```yaml
logging:
  level: INFO
  file_logging: true

cpu:
  enabled: true
  safe_mode: true
  max_temperature_celsius: 85

storage:
  enabled: true
  auto_trim: false

network:
  enabled: true
  optimize_sysctl: true
```

## Safety Features

1. **Automatic Backups**: Settings are backed up before any changes
2. **Safe Mode**: Conservative defaults to prevent instability
3. **Temperature Monitoring**: Respects maximum temperature limits
4. **Dry Run Mode**: Preview changes before applying

## Troubleshooting

### Permission Denied
Most tuning operations require root privileges:
```bash
sudo amd-tuner profile performance
```

### Sensors Not Working
Run sensors detection:
```bash
sudo sensors-detect --auto
sudo modprobe k10temp
```

### Changes Not Persisting
Settings are applied at runtime. To persist across reboots, use the systemd integration:

```bash
# Install systemd services
cd /opt/amd-auto-tuner/systemd
sudo ./install-systemd.sh --all

# Or install specific services:
sudo ./install-systemd.sh --boot-only    # Apply profile at boot
sudo ./install-systemd.sh --timer        # Periodic re-application
sudo ./install-systemd.sh --hpc          # HPC-specific service
```

## Systemd Integration

AMD Auto Tuner provides systemd services for automated tuning:

### Boot Service
Applies optimal profile at system boot:
```bash
sudo systemctl enable amd-auto-tuner-boot.service
```

### Timer Service
Periodically re-applies optimizations (every hour by default):
```bash
sudo systemctl enable --now amd-auto-tuner.timer
```

### HPC Service
For HPC clusters, applies HPC profile after SLURM starts:
```bash
sudo systemctl enable amd-auto-tuner-hpc.service
```

### Check Status
```bash
systemctl status amd-auto-tuner-boot.service
systemctl list-timers | grep amd
```

## High-Speed Networking

AMD Auto Tuner provides optimizations for high-speed NICs:

### Supported Hardware

| Vendor | Models | Max Speed | Features |
|--------|--------|-----------|----------|
| Intel | E810, E800 | 100G | RDMA, Flow Director |
| Intel | XL710, X710 | 40G | Flow Director |
| Mellanox | ConnectX-4 | 100G | RoCE v2, RDMA |
| Mellanox | ConnectX-5 | 100G | RoCE v2, NVMe-oF |
| Mellanox | ConnectX-6 | 200G | RoCE v2, DPDK |
| Mellanox | ConnectX-7 | 400G | RoCE v2, Crypto |
| Broadcom | bnxt_en | 100G | RSS |
| AMD | Pensando ionic | 200G | DPDK |

### Optimizations Applied

For 25G+ NICs:
- Jumbo frames (MTU 9000)
- Optimized interrupt coalescing
- Maximum ring buffers
- Driver-specific tuning
- High-performance sysctl settings

For 100G+ NICs:
- Extended buffer sizes (128MB socket buffers)
- Increased netdev budget
- BPF JIT compilation

### Example Usage

```bash
# Detect NIC speeds
amd-tuner detect

# Apply high-speed optimizations
sudo amd-tuner tune-network --high-speed

# For HPC with RDMA
sudo amd-tuner profile hpc
```

### Reverting Changes
```bash
sudo amd-tuner restore
```

## File Locations

- Installation: `/opt/amd-auto-tuner/`
- Configuration: `/etc/amd-auto-tuner/config.yaml`
- Logs: `/opt/amd-auto-tuner/logs/`
- Backups: `/opt/amd-auto-tuner/backups/`
- Benchmarks: `/opt/amd-auto-tuner/benchmarks/`
- Reports: `/opt/amd-auto-tuner/reports/`

## Support

For issues and feature requests, please open an issue on the project repository.
