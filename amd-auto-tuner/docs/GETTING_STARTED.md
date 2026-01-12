# AMD Auto Tuner - Getting Started

This guide will help you get up and running with AMD Auto Tuner in minutes.

## Prerequisites

- Linux operating system (Ubuntu, Fedora, Arch, or similar)
- AMD Ryzen, Threadripper, or EPYC processor
- Python 3.8 or newer
- Root/sudo access for tuning operations

## Installation

### Automated Installation (Recommended)

```bash
# Clone or download the repository
cd amd-auto-tuner

# Run the installation script
sudo ./install.sh
```

The installation script will:
1. Detect your Linux distribution
2. Install required system packages
3. Install Python dependencies
4. Set up the command-line tool
5. Configure hardware sensors

### Manual Installation

If you prefer manual installation:

```bash
# Install system dependencies (Ubuntu/Debian)
sudo apt install python3 python3-pip ethtool lm-sensors linux-cpupower sysbench fio

# Install Python dependencies
pip3 install -r requirements.txt

# Make executable
chmod +x main.py
```

## First Steps

### 1. Detect Your Hardware

```bash
amd-tuner detect
```

This shows your CPU model, Zen generation, storage devices, and network interfaces.

### 2. Check Current Settings

```bash
amd-tuner report
```

This generates a comprehensive report of current system settings.

### 3. Run a Benchmark

```bash
sudo amd-tuner benchmark --cpu
```

This runs a CPU benchmark to establish baseline performance.

### 4. Apply a Profile

```bash
# First, see what changes would be made
sudo amd-tuner profile balanced --dry-run

# Then apply the profile
sudo amd-tuner profile balanced
```

## Common Use Cases

### Gaming Session

```bash
# Before gaming
sudo amd-tuner profile gaming

# After gaming (optional)
sudo amd-tuner profile balanced
```

### Compiling Large Projects

```bash
# Maximum performance for compilation
sudo amd-tuner profile performance

# Return to normal after
sudo amd-tuner profile balanced
```

### Laptop Power Saving

```bash
# Extend battery life
sudo amd-tuner profile powersave

# Plugged in
sudo amd-tuner profile balanced
```

### Server Optimization

```bash
# Optimize for server workloads
sudo amd-tuner profile server
```

### HPC/Scientific Computing

```bash
# Apply HPC profile (for EPYC/Threadripper)
sudo amd-tuner profile hpc

# Or custom HPC tuning
sudo amd-tuner tune-hpc --huge-pages --numa-aware --irq-affinity

# With 1GB huge pages
sudo amd-tuner tune-hpc --huge-pages --huge-pages-size 1G
```

### Memory Optimization

```bash
# Tune memory for low latency
sudo amd-tuner tune-memory --swappiness 10 --thp always

# Tune for database workloads
sudo amd-tuner tune-memory --swappiness 1 --thp madvise
```

## Understanding Profiles

| Profile | Governor | Boost | Use Case |
|---------|----------|-------|----------|
| performance | performance | on | Maximum speed, high power |
| balanced | schedutil | on | Daily use, efficiency |
| powersave | powersave | off | Battery saving |
| gaming | performance | on | Low latency gaming |
| server | schedutil | on | Server workloads |
| hpc | performance | on | Scientific computing, simulations |

## Dry Run Mode

Always test changes with `--dry-run` first:

```bash
sudo amd-tuner profile performance --dry-run
```

This shows exactly what would change without applying anything.

## Restoring Settings

If something goes wrong:

```bash
# Restore from automatic backup
sudo amd-tuner restore
```

## Verbose Output

For troubleshooting:

```bash
sudo amd-tuner profile balanced -v
```

## Measuring Improvement

```bash
# Run benchmark before tuning
sudo amd-tuner benchmark > before.json

# Apply profile
sudo amd-tuner profile performance

# Run benchmark after
sudo amd-tuner benchmark > after.json

# Compare results
# (manually compare or use examples.py)
```

## Persisting Settings

Settings are applied at runtime. To persist across reboots:

```bash
# Enable the systemd service
sudo systemctl enable amd-auto-tuner

# Edit to choose default profile
sudo nano /etc/systemd/system/amd-auto-tuner.service
```

## Configuration File

Customize behavior in `/etc/amd-auto-tuner/config.yaml`:

```yaml
cpu:
  enabled: true
  safe_mode: true
  max_temperature_celsius: 85

storage:
  enabled: true

network:
  enabled: true
  optimize_sysctl: true
```

## Next Steps

1. Read the full [User Guide](README.md) for all commands
2. Explore [Architecture](ARCHITECTURE.md) to understand internals
3. Check `examples.py` for programmatic usage
4. Run `amd-tuner --help` for all options

## Getting Help

```bash
# General help
amd-tuner --help

# Command-specific help
amd-tuner profile --help
amd-tuner tune-cpu --help
```

## Troubleshooting

### "Permission denied"
Use `sudo` for tuning operations.

### "Command not found"
Ensure `/usr/local/bin` is in your PATH or use full path.

### CPU frequency not changing
Check if your CPU supports frequency scaling:
```bash
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors
```

### Sensors not working
Run sensor detection:
```bash
sudo sensors-detect --auto
```
