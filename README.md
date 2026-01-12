# AMD Auto Tuner

An automated performance tuning framework for AMD Ryzen, Threadripper, and EPYC processors on Linux.

## Overview

AMD Auto Tuner provides intelligent detection, benchmarking, and optimization of:

- **CPU**: Governor selection, frequency scaling, boost control, C-states, AMD P-State EPP
- **Storage**: I/O scheduler optimization, queue depth, read-ahead tuning
- **Network**: Ring buffers, hardware offloads, interrupt coalescing, high-speed NIC support (25G-400G)
- **HPC**: NUMA topology, huge pages (2M/1G), IRQ affinity, MPI/SLURM optimization
- **Memory**: HBM3/DDR5 optimization, NUMA balancing, THP management

## Quick Start

```bash
# Install
cd amd-auto-tuner
sudo ./install.sh

# Detect hardware
sudo amd-tuner detect

# Auto-detect and apply best profile
sudo amd-tuner auto --apply

# Apply a specific profile
sudo amd-tuner profile balanced    # General use
sudo amd-tuner profile performance # Maximum performance
sudo amd-tuner profile gaming      # Low latency gaming
sudo amd-tuner profile server      # Server workloads
sudo amd-tuner profile hpc         # HPC/Scientific computing
sudo amd-tuner profile powersave   # Battery/power saving

# Run benchmarks
sudo amd-tuner benchmark

# Restore previous settings
sudo amd-tuner restore
```

## Features

| Feature | Description |
|---------|-------------|
| Hardware Detection | Auto-detect AMD CPU architecture, Zen generation, storage, network |
| Performance Profiles | Pre-configured profiles for different workloads |
| CPU Tuning | Governor, frequency, boost, C-states, P-State EPP |
| Storage Tuning | I/O scheduler, queue depth, read-ahead, TRIM |
| Network Tuning | Ring buffers, offloads, sysctl, high-speed NICs |
| HPC Tuning | NUMA, huge pages, IRQ affinity, MPI hints, SLURM |
| Memory Tuning | HBM3, DDR5, NUMA balancing, THP, swappiness |
| Benchmarking | CPU, storage, network with before/after comparison |
| Backup & Restore | Automatic backup before changes |
| Systemd Integration | Boot-time and periodic tuning |

## Supported Hardware

### CPUs
- AMD Ryzen (Zen, Zen+, Zen 2, Zen 3, Zen 4)
- AMD Threadripper
- AMD EPYC

### High-Speed NICs
- Intel: E810/E800 (100G), XL710/X710 (40G), ice, i40e, ixgbe
- Mellanox: ConnectX-4/5/6/7 (100G-400G)
- Broadcom: bnxt_en (100G)
- AMD/Pensando: ionic (200G)

## Project Structure

```
amd-tuner/
├── amd-auto-tuner/           # Main application
│   ├── main.py               # CLI entry point
│   ├── install.sh            # Installation script
│   ├── modules/              # Core modules
│   │   ├── hardware_detector.py
│   │   ├── cpu_tuner.py
│   │   ├── storage_tuner.py
│   │   ├── network_tuner.py
│   │   ├── hpc_tuner.py
│   │   ├── memory_tuner.py
│   │   ├── benchmarker.py
│   │   └── config_manager.py
│   ├── config/               # Configuration files
│   ├── systemd/              # Systemd service files
│   └── docs/                 # Documentation
│       ├── README.md         # User guide
│       ├── ARCHITECTURE.md   # Technical architecture
│       └── GETTING_STARTED.md
├── LICENSE                   # MIT License
└── README.md                 # This file
```

## Documentation

- [User Guide](amd-auto-tuner/docs/README.md) - Complete command reference and usage
- [Getting Started](amd-auto-tuner/docs/GETTING_STARTED.md) - Quick installation and first steps
- [Architecture](amd-auto-tuner/docs/ARCHITECTURE.md) - Technical design and module details

## Requirements

- Linux (Ubuntu, Debian, Fedora, Arch, RHEL, CentOS)
- Python 3.8+
- Root/sudo access for tuning operations

## Installation

### Automated (Recommended)

```bash
cd amd-auto-tuner
sudo ./install.sh
```

### Manual

```bash
# Ubuntu/Debian
sudo apt install python3 python3-pip ethtool lm-sensors linux-cpupower sysbench fio

# Install Python dependencies
pip3 install -r amd-auto-tuner/requirements.txt
```

## Configuration

Default configuration: `/etc/amd-auto-tuner/config.yaml`

```yaml
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

profiles:
  default: balanced
```

## Systemd Integration

```bash
# Install systemd services
cd amd-auto-tuner/systemd
sudo ./install-systemd.sh --all

# Or specific services:
sudo ./install-systemd.sh --boot-only    # Apply at boot
sudo ./install-systemd.sh --timer        # Periodic tuning
sudo ./install-systemd.sh --hpc          # HPC environments
```

## Safety

- Automatic backups before any changes
- Safe mode with conservative defaults
- Temperature monitoring and limits
- Dry-run mode for previewing changes
- Easy restore functionality

## License

MIT License - see [LICENSE](LICENSE) file.

## Contributing

Contributions are welcome! Please see the documentation for architecture details before submitting changes.

## Support

For issues and feature requests, please open an issue on the project repository.
