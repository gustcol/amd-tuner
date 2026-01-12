# AMD CPU Management and Monitoring Tools - Complete Setup Guide

## Table of Contents

- [System Overview](#system-overview)
- [Prerequisites](#prerequisites)
- [Warning and Disclaimer](#warning-and-disclaimer)
- [1. Kernel Parameters and Drivers](#1-kernel-parameters-and-drivers)
- [2. CoreCtrl Installation](#2-corectrl-installation)
- [3. CPU Frequency Management Tools](#3-cpu-frequency-management-tools)
- [4. Ryzen Monitoring Tools](#4-ryzen-monitoring-tools)
- [5. Direct Kernel Interface](#5-direct-kernel-interface)
- [6. Advanced Undervolting with ZenStates-Linux](#6-advanced-undervolting-with-zenstates-linux)
- [Verification and Testing](#verification-and-testing)
- [Troubleshooting](#troubleshooting)
- [Performance Tuning Examples](#performance-tuning-examples)
- [Safety Best Practices](#safety-best-practices)
- [References](#references)

---

## System Overview

This guide covers the complete setup for AMD CPU management on Linux:
- **CPU**: AMD Ryzen/Threadripper/EPYC
- **Storage**: 512GB SSD
- **OS**: Linux (Ubuntu/Fedora/Arch-based distributions)

Supported tools and features:
- **CoreCtrl**: GUI for CPU performance profiles, frequency, and voltage control
- **cpupower/cpufreq-utils**: CPU frequency and governor management
- **k10temp/zenpower**: Temperature and power monitoring
- **Direct Kernel Files**: Manual control via `/sys/devices/system/cpu/`
- **ryzen_smu**: Advanced System Management Unit monitoring
- **ZenStates-Linux**: Advanced Ryzen undervolting and P-state control

---

## Prerequisites

### System Requirements

```bash
# Check your AMD CPU
lscpu | grep -E "Model name|Architecture|CPU\(s\)|Thread"

# Check kernel version (5.15+ recommended for latest Ryzen support)
uname -r

# Verify CPU temperature monitoring
sensors
```

### Required Packages

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y build-essential cmake git pkg-config \
    libboost-all-dev python3-pip lm-sensors \
    linux-cpupower cpufrequtils

# Fedora
sudo dnf install -y gcc gcc-c++ cmake git pkgconfig \
    boost-devel python3-pip lm_sensors kernel-tools

# Arch Linux
sudo pacman -Syu base-devel cmake git boost python-pip \
    lm_sensors cpupower
```

### Initialize Sensor Detection

```bash
# Detect all sensors
sudo sensors-detect --auto

# View current sensors
sensors
```

---

## Warning and Disclaimer

⚠️ **CRITICAL SAFETY WARNINGS** ⚠️

**Overclocking, undervolting, and manual power/frequency management can:**
- Cause system instability and crashes
- Permanently damage your CPU hardware
- Void your warranty
- Result in data corruption and loss
- Cause overheating and hardware failure
- Lead to reduced CPU lifespan

**Before proceeding:**
1. Ensure adequate cooling (verify CPU cooler installation and thermal paste)
2. Back up ALL important data
3. Start with conservative settings and test thoroughly
4. Monitor temperatures constantly (stay under 85°C for most Ryzen CPUs)
5. Never exceed manufacturer specifications
6. Test stability with tools like stress-ng, Prime95, or y-cruncher
7. Have a bootable USB ready in case system becomes unstable

**This guide is provided AS-IS with NO WARRANTY. You are solely responsible for any damage to your hardware.**

---

## 1. Kernel Parameters and Drivers

### Enable AMD CPU Features

Some advanced features require kernel parameters or module options.

#### GRUB Configuration

```bash
# Edit GRUB configuration
sudo nano /etc/default/grub
```

Add recommended parameters:

```
GRUB_CMDLINE_LINUX_DEFAULT="quiet splash processor.max_cstate=1 idle=poll"
```

**Parameter explanations:**
- `processor.max_cstate=1`: Limits C-states for better performance (increases power usage)
- `idle=poll`: Disables CPU idle states (maximum performance, high power)
- `amd_pstate=active`: Use amd-pstate driver (kernel 6.1+, for Ryzen 6000+)

**For maximum performance (high power consumption):**
```
GRUB_CMDLINE_LINUX_DEFAULT="quiet splash amd_pstate=active processor.max_cstate=1"
```

**For balanced operation (recommended):**
```
GRUB_CMDLINE_LINUX_DEFAULT="quiet splash amd_pstate=active"
```

#### Update GRUB

```bash
# Ubuntu/Debian
sudo update-grub

# Fedora/RHEL
sudo grub2-mkconfig -o /boot/grub2/grub.cfg

# Arch Linux
sudo grub-mkconfig -o /boot/grub/grub.cfg

# Reboot
sudo reboot
```

### Install Zenpower (Alternative to k10temp)

Zenpower provides more accurate power monitoring for Ryzen CPUs:

```bash
# Clone repository
git clone https://github.com/ocerman/zenpower.git
cd zenpower

# Build and install
make
sudo make install

# Blacklist k10temp to avoid conflicts
echo "blacklist k10temp" | sudo tee /etc/modprobe.d/blacklist-k10temp.conf

# Load zenpower module
sudo modprobe zenpower

# Make it load at boot
echo "zenpower" | sudo tee /etc/modules-load.d/zenpower.conf

# Verify it's working
sensors
```

---

## 2. CoreCtrl Installation

CoreCtrl provides a comprehensive GUI for AMD CPU management including frequency control, performance profiles, and monitoring.

### Method 1: Package Manager (Recommended)

```bash
# Ubuntu 22.04+
sudo add-apt-repository ppa:ernstp/mesarc
sudo apt update
sudo apt install corectrl

# Fedora
sudo dnf install corectrl

# Arch Linux
sudo pacman -S corectrl
```

### Method 2: Build from Source

```bash
# Clone repository
git clone https://gitlab.com/corectrl/corectrl.git
cd corectrl

# Install dependencies
# Ubuntu/Debian
sudo apt install -y qtbase5-dev qtcharts5-dev qtquickcontrols2-5-dev \
    qml-module-qtquick-controls2 qml-module-qtcharts \
    libbotan-2-dev libegl1-mesa-dev libkf5archive-dev libkf5auth-dev \
    libkf5coreaddons-dev libkf5widgetsaddons-dev libpolkit-qt5-1-dev \
    extra-cmake-modules gettext

# Build
mkdir build && cd build
cmake -DCMAKE_INSTALL_PREFIX=/usr -DCMAKE_BUILD_TYPE=Release ..
make -j$(nproc)
sudo make install
```

### Configuration

#### 1. Create Polkit Rule

Allow CoreCtrl to manage CPU without password prompts:

```bash
sudo nano /etc/polkit-1/rules.d/90-corectrl.rules
```

Add this content:

```javascript
polkit.addRule(function(action, subject) {
    if ((action.id == "org.corectrl.helper.init" ||
         action.id == "org.corectrl.helperkiller.init") &&
        subject.local == true &&
        subject.active == true &&
        subject.isInGroup("your_username")) {
            return polkit.Result.YES;
    }
});
```

**Replace `your_username` with your actual username.**

#### 2. Set CoreCtrl to Start at Boot

```bash
# Create autostart directory
mkdir -p ~/.config/autostart

# Copy desktop file
cp /usr/share/applications/org.corectrl.CoreCtrl.desktop ~/.config/autostart/

# Edit to start minimized (optional)
nano ~/.config/autostart/org.corectrl.CoreCtrl.desktop
# Add: --minimize-systray to the Exec line
```

#### 3. Launch CoreCtrl

```bash
corectrl
```

### CoreCtrl CPU Configuration

1. **Initial Setup**: Grant system permissions on first launch
2. **CPU Selection**: Select your AMD CPU from device list
3. **Performance Mode**: Switch from "Automatic" to "Manual" mode
4. **Configure CPU Profiles**:
   - **Performance Profile**: Maximum frequency, high power limit
   - **Balanced Profile**: Dynamic frequency scaling
   - **Power Saving Profile**: Lower frequencies, reduced power

#### CPU Frequency Control

In CoreCtrl:
- Set minimum and maximum CPU frequencies
- Choose CPU governor (performance, powersave, schedutil, ondemand)
- Configure per-core settings
- Set power limits (PPT, TDC, EDC for Ryzen)

---

## 3. CPU Frequency Management Tools

### cpupower - Comprehensive CPU Management

```bash
# Install cpupower
# Ubuntu/Debian
sudo apt install linux-cpupower

# Fedora
sudo dnf install kernel-tools

# Arch Linux
sudo pacman -S cpupower
```

#### cpupower Commands

```bash
# Show CPU frequency information
cpupower frequency-info

# Show current governor and frequencies
cpupower frequency-info -o

# Set governor to performance (maximum frequency)
sudo cpupower frequency-set -g performance

# Set governor to powersave (minimum frequency)
sudo cpupower frequency-set -g powersave

# Set governor to schedutil (kernel-managed scaling)
sudo cpupower frequency-set -g schedutil

# Set specific frequency range (e.g., 2.2GHz to 4.5GHz)
sudo cpupower frequency-set -d 2.2GHz -u 4.5GHz

# Set maximum frequency to 3.8GHz
sudo cpupower frequency-set -u 3.8GHz

# Enable turbo boost
sudo cpupower frequency-set --boost-enabled=1

# Disable turbo boost (for thermal management)
sudo cpupower frequency-set --boost-enabled=0
```

### Available CPU Governors

```bash
# List available governors
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors
```

**Common governors:**
- **performance**: Always run at maximum frequency
- **powersave**: Always run at minimum frequency
- **schedutil**: Kernel scheduler-based scaling (recommended for modern kernels)
- **ondemand**: Quickly scale based on CPU load (legacy)
- **conservative**: Gradually scale based on CPU load (legacy)

### cpufrequtils (Alternative)

```bash
# Install
sudo apt install cpufrequtils  # Ubuntu/Debian
sudo dnf install cpufrequtils  # Fedora

# Set governor for all CPUs
sudo cpufreq-set -r -g performance

# Set frequency for specific CPU
sudo cpufreq-set -c 0 -f 3.5GHz

# Show information
cpufreq-info
```

---

## 4. Ryzen Monitoring Tools

### ryzen_smu - System Management Unit Monitoring

Access advanced CPU telemetry and power monitoring:

```bash
# Clone repository
git clone https://github.com/leogx9r/ryzen_smu.git
cd ryzen_smu

# Build module
make

# Load module
sudo insmod ryzen_smu.ko

# Make it load at boot
sudo cp ryzen_smu.ko /lib/modules/$(uname -r)/kernel/drivers/
sudo depmod
echo "ryzen_smu" | sudo tee /etc/modules-load.d/ryzen_smu.conf
```

#### Monitor with ryzen_monitor

```bash
# Install Python dependencies
pip3 install --user argparse

# Clone monitoring tool
git clone https://github.com/hattedsquirrel/ryzen_monitor.git
cd ryzen_monitor

# Run monitor
sudo python3 ryzen_monitor.py
```

**Displayed information:**
- Package power (CPU power consumption)
- Core voltages and frequencies
- SoC power
- Temperature readings
- Current limits (PPT, TDC, EDC)

### sensors-detect and lm-sensors

```bash
# Full sensor detection
sudo sensors-detect

# View all sensors
sensors

# Continuous monitoring (update every 2 seconds)
watch -n 2 sensors

# JSON output for scripting
sensors -j
```

### Monitoring withhtop/btop

```bash
# Install htop
sudo apt install htop  # Ubuntu/Debian
sudo dnf install htop  # Fedora
sudo pacman -S htop    # Arch

# Install btop (modern alternative)
sudo apt install btop  # Ubuntu 22.04+
sudo pacman -S btop    # Arch

# Run
htop
# or
btop
```

Press `F2` in htop for setup, enable CPU frequency display.

---

## 5. Direct Kernel Interface

Advanced users can directly manipulate CPU settings through sysfs interfaces.

### CPU Frequency Control via sysfs

```bash
# List all CPUs
ls /sys/devices/system/cpu/

# Check current governor for CPU 0
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor

# Set performance governor for all CPUs
for cpu in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
    echo "performance" | sudo tee $cpu
done

# Set powersave governor for all CPUs
for cpu in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
    echo "powersave" | sudo tee $cpu
done

# View current frequency for all CPUs
grep "MHz" /proc/cpuinfo

# View frequency limits
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq

# Set maximum frequency to 3800 MHz for all CPUs
for cpu in /sys/devices/system/cpu/cpu*/cpufreq/scaling_max_freq; do
    echo "3800000" | sudo tee $cpu
done
```

### CPU Boost Control

```bash
# Check boost status
cat /sys/devices/system/cpu/cpufreq/boost

# Disable boost (0 = disabled, 1 = enabled)
echo 0 | sudo tee /sys/devices/system/cpu/cpufreq/boost

# Enable boost
echo 1 | sudo tee /sys/devices/system/cpu/cpufreq/boost
```

### Power Management

```bash
# View current power consumption (if zenpower is loaded)
sensors | grep -i power

# hwmon interface for power monitoring
ls /sys/class/hwmon/

# Find zenpower device
grep -r "zenpower" /sys/class/hwmon/*/name

# Example: Read power consumption
cat /sys/class/hwmon/hwmon*/power*_input
```

### CPU Core Control (Enable/Disable Cores)

```bash
# Disable CPU core 1 (DANGEROUS - can cause instability)
echo 0 | sudo tee /sys/devices/system/cpu/cpu1/online

# Enable CPU core 1
echo 1 | sudo tee /sys/devices/system/cpu/cpu1/online

# List online CPUs
grep -H . /sys/devices/system/cpu/cpu*/online
```

**⚠️ Warning**: Disabling CPU cores can cause system instability. Core 0 cannot be disabled.

---

## 6. Advanced Undervolting with ZenStates-Linux

ZenStates allows direct P-state manipulation for Ryzen CPUs, enabling undervolting and fine-tuned frequency control.

### Installation

```bash
# Clone repository
git clone https://github.com/r4m0n/ZenStates-Linux.git
cd ZenStates-Linux

# Make executable
chmod +x zenstates.py

# Install to system (optional)
sudo cp zenstates.py /usr/local/bin/zenstates
sudo chmod +x /usr/local/bin/zenstates
```

### Usage Examples

#### View Current P-States

```bash
# Display current P-state configuration
sudo ./zenstates.py -l
```

**Output example:**
```
P0 - Enabled - FID = 90 - DID = 8 - VID = 32 - Ratio = 36.00 - vCore = 1.2500
P1 - Enabled - FID = 84 - DID = 8 - VID = 38 - Ratio = 33.00 - vCore = 1.2125
P2 - Enabled - FID = 78 - DID = 8 - VID = 44 - Ratio = 30.00 - vCore = 1.1750
```

#### Undervolt CPU

```bash
# Reduce voltage by 50mV for P0 state
# Current VID = 32, each step = ~6.25mV
# 50mV / 6.25mV = 8 steps
# New VID = 32 + 8 = 40
sudo ./zenstates.py -p 0 -v 40

# Reduce voltage for all P-states by 75mV
sudo ./zenstates.py -p 0 -v 44  # P0: ~75mV reduction
sudo ./zenstates.py -p 1 -v 50  # P1: ~75mV reduction
sudo ./zenstates.py -p 2 -v 56  # P2: ~75mV reduction
```

**VID to Voltage conversion:**
- VID = 0: 1.55V
- VID = 32: 1.25V
- VID = 40: 1.20V
- VID = 64: 1.05V
- Each VID step ≈ 6.25mV

#### Disable C-States for Maximum Performance

```bash
# Disable C6 state
sudo ./zenstates.py --c6-disable

# Re-enable C6 state
sudo ./zenstates.py --c6-enable
```

#### Make Changes Persistent

Create a systemd service:

```bash
sudo nano /etc/systemd/system/zenstates.service
```

Add content:

```ini
[Unit]
Description=Apply ZenStates CPU configuration
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/zenstates -p 0 -v 40
ExecStart=/usr/local/bin/zenstates -p 1 -v 46
ExecStart=/usr/local/bin/zenstates -p 2 -v 52

[Install]
WantedBy=multi-user.target
```

Enable service:

```bash
sudo systemctl enable zenstates.service
sudo systemctl start zenstates.service
```

---

## Verification and Testing

### 1. Verify CPU Frequency Control

```bash
# Watch CPU frequencies in real-time
watch -n 1 'grep MHz /proc/cpuinfo'

# Or use cpupower
watch -n 1 'cpupower frequency-info | grep "current CPU"'

# Generate CPU load and monitor
stress-ng --cpu $(nproc) --timeout 30s &
watch -n 1 sensors
```

### 2. Stress Testing

⚠️ **Critical**: Always monitor temperatures during stress testing!

```bash
# Install stress testing tools
sudo apt install stress-ng sysbench

# CPU stress test (all cores, 10 minutes)
stress-ng --cpu $(nproc) --timeout 600s --metrics-brief

# Monitor temperatures while stress testing
watch -n 2 'sensors | grep -E "Tctl|Tdie"'

# Prime number calculation stress test
sysbench cpu --threads=$(nproc) --time=300 run
```

### 3. Stability Testing

```bash
# Install y-cruncher (Pi calculation benchmark)
wget http://www.numberworld.org/y-cruncher/y-cruncher%20v0.8.5.9545-static.tar.xz
tar xf y-cruncher*.tar.xz
cd y-cruncher*

# Run stress test
./y-cruncher stress -test

# Or use mprime (Prime95 for Linux)
wget https://www.mersenne.org/download/software/v30/30.8/p95v308b17.linux64.tar.gz
tar xf p95*.tar.gz
cd p95
./mprime -t
```

**Recommended stability testing duration:**
- Quick test: 30 minutes
- Standard test: 2-4 hours
- Thorough test: 8-12 hours
- Extreme validation: 24+ hours

### 4. Benchmark Performance

```bash
# Install Geekbench
# Download from: https://www.geekbench.com/download/linux/

# Single-core and multi-core benchmark
./geekbench5

# Or use sysbench
sysbench cpu --threads=1 run      # Single-core
sysbench cpu --threads=$(nproc) run  # Multi-core
```

---

## Troubleshooting

### System Becomes Unstable After Changes

1. **Boot into recovery mode**:
   - Reboot and select "Advanced options" in GRUB
   - Select recovery mode
   - Select "root" for root shell

2. **Revert changes**:
```bash
# Reset CPU frequency governor to default
for cpu in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
    echo "schedutil" > $cpu
done

# Re-enable CPU boost
echo 1 > /sys/devices/system/cpu/cpufreq/boost

# Reboot
reboot
```

3. **Reset GRUB parameters**:
```bash
# Edit GRUB config
nano /etc/default/grub

# Remove custom parameters, keep only basics
GRUB_CMDLINE_LINUX_DEFAULT="quiet splash"

# Update and reboot
update-grub
reboot
```

### CPU Not Boosting to Maximum Frequency

```bash
# Check if boost is enabled
cat /sys/devices/system/cpu/cpufreq/boost

# Enable boost
echo 1 | sudo tee /sys/devices/system/cpu/cpufreq/boost

# Check thermal throttling
sensors | grep -i temp

# Verify power limits aren't restricting performance
sudo dmesg | grep -i "power"
```

### High Temperatures

```bash
# Check current temperatures
sensors

# Verify fan speed (if applicable)
sensors | grep -i fan

# Check for thermal throttling
sudo dmesg | tail -50 | grep -i thermal

# Reduce maximum frequency temporarily
sudo cpupower frequency-set -u 3.5GHz

# Enable powersave governor
sudo cpupower frequency-set -g powersave
```

### CoreCtrl Not Applying Settings

```bash
# Check CoreCtrl logs
journalctl -xe | grep corectrl

# Verify polkit rules are correct
sudo cat /etc/polkit-1/rules.d/90-corectrl.rules

# Restart CoreCtrl with elevated privileges
pkill corectrl
corectrl
```

### Sensors Not Detecting CPU Temperature

```bash
# Run sensor detection again
sudo sensors-detect --auto

# Load modules manually
sudo modprobe k10temp
# or
sudo modprobe zenpower

# Check if modules are loaded
lsmod | grep -E "k10temp|zenpower"

# View kernel messages for errors
sudo dmesg | grep -i sensor
```

---

## Performance Tuning Examples

### Profile 1: Maximum Performance

```bash
# Set performance governor
sudo cpupower frequency-set -g performance

# Enable CPU boost
echo 1 | sudo tee /sys/devices/system/cpu/cpufreq/boost

# Disable C-states (if using ZenStates)
sudo zenstates --c6-disable

# Set minimum frequency to maximum
sudo cpupower frequency-set -d 3.8GHz -u 4.5GHz
```

**Use case**: Gaming, video rendering, compilation, benchmarking

**Power consumption**: Very High

### Profile 2: Balanced Performance

```bash
# Set schedutil governor (kernel-managed)
sudo cpupower frequency-set -g schedutil

# Enable boost
echo 1 | sudo tee /sys/devices/system/cpu/cpufreq/boost

# Allow wide frequency range
sudo cpupower frequency-set -d 2.2GHz -u 4.5GHz
```

**Use case**: General desktop use, web browsing, light productivity

**Power consumption**: Medium

### Profile 3: Power Saving

```bash
# Set powersave governor
sudo cpupower frequency-set -g powersave

# Disable boost
echo 0 | sudo tee /sys/devices/system/cpu/cpufreq/boost

# Limit maximum frequency
sudo cpupower frequency-set -u 3.0GHz
```

**Use case**: Laptop battery saving, low-load server, idle system

**Power consumption**: Low

### Profile 4: Undervolted Performance

```bash
# Apply undervolting (example: -75mV)
sudo zenstates -p 0 -v 44
sudo zenstates -p 1 -v 50
sudo zenstates -p 2 -v 56

# Set performance governor
sudo cpupower frequency-set -g performance

# Enable boost
echo 1 | sudo tee /sys/devices/system/cpu/cpufreq/boost
```

**Use case**: Maximum performance with reduced heat and power consumption

**Power consumption**: High (but lower than Profile 1)

**⚠️ Requires stability testing!**

---

## Safety Best Practices

### 1. Temperature Monitoring

**Always monitor temperatures:**

```bash
# Create continuous temperature log
while true; do
    echo "$(date) - $(sensors | grep Tctl)"
    sleep 5
done > ~/cpu_temps.log
```

**Safe temperature ranges:**
- **Idle**: 30-45°C
- **Load**: 60-75°C
- **Maximum (short bursts)**: 85°C
- **Dangerous**: 90°C+ (immediate action required)

### 2. Incremental Changes

**Never apply aggressive settings immediately:**

1. Start with conservative undervolt (-25mV)
2. Test stability for 1 hour
3. If stable, decrease by another 25mV
4. Repeat until instability occurs
5. Increase voltage by 12.5mV for safety margin

### 3. Backup and Recovery Plan

```bash
# Create rescue script
cat > ~/rescue-cpu.sh << 'SCRIPT'
#!/bin/bash
echo "schedutil" | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
echo 1 | sudo tee /sys/devices/system/cpu/cpufreq/boost
sudo cpupower frequency-set -d 2200MHz -u 4500MHz
echo "CPU settings reset to safe defaults"
SCRIPT

chmod +x ~/rescue-cpu.sh
```

### 4. Document Your Changes

```bash
# Create configuration log
cat > ~/cpu-config.log << EOF
Date: $(date)
CPU: $(lscpu | grep "Model name")
Governor: $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor)
Min Freq: $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq)
Max Freq: $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq)
Boost: $(cat /sys/devices/system/cpu/cpufreq/boost)
Undervolting: P0=-50mV, P1=-50mV, P2=-50mV
Notes: Stable after 4 hours stress test
 htop/btop

```bash
# Install htop
sudo apt install htop  # Ubuntu/Debian
sudo dnf install htop  # Fedora
sudo pacman -S htop    # Arch

# Install btop (modern alternative)
sudo apt install btop  # Ubuntu 22.04+
sudo pacman -S btop    # Arch

# Run
htop
# or
btop
```

Press `F2` in htop for setup, enable CPU frequency display.

---

## 5. Direct Kernel Interface

Advanced users can directly manipulate CPU settings through sysfs interfaces.

### CPU Frequency Control via sysfs

```bash
# List all CPUs
ls /sys/devices/system/cpu/

# Check current governor for CPU 0
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor

# Set performance governor for all CPUs
for cpu in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
    echo "performance" | sudo tee $cpu
done

# Set powersave governor for all CPUs
for cpu in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
    echo "powersave" | sudo tee $cpu
done

# View current frequency for all CPUs
grep "MHz" /proc/cpuinfo

# View frequency limits
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq

# Set maximum frequency to 3800 MHz for all CPUs
for cpu in /sys/devices/system/cpu/cpu*/cpufreq/scaling_max_freq; do
    echo "3800000" | sudo tee $cpu
done
```

### CPU Boost Control

```bash
# Check boost status
cat /sys/devices/system/cpu/cpufreq/boost

# Disable boost (0 = disabled, 1 = enabled)
echo 0 | sudo tee /sys/devices/system/cpu/cpufreq/boost

# Enable boost
echo 1 | sudo tee /sys/devices/system/cpu/cpufreq/boost
```

### Power Management

```bash
# View current power consumption (if zenpower is loaded)
sensors | grep -i power

# hwmon interface for power monitoring
ls /sys/class/hwmon/

# Find zenpower device
grep -r "zenpower" /sys/class/hwmon/*/name

# Example: Read power consumption
cat /sys/class/hwmon/hwmon*/power*_input
```

### CPU Core Control (Enable/Disable Cores)

```bash
# Disable CPU core 1 (DANGEROUS - can cause instability)
echo 0 | sudo tee /sys/devices/system/cpu/cpu1/online

# Enable CPU core 1
echo 1 | sudo tee /sys/devices/system/cpu/cpu1/online

# List online CPUs
grep -H . /sys/devices/system/cpu/cpu*/online
```

**⚠️ Warning**: Disabling CPU cores can cause system instability. Core 0 cannot be disabled.

---

## 6. Advanced Undervolting with ZenStates-Linux

ZenStates allows direct P-state manipulation for Ryzen CPUs, enabling undervolting and fine-tuned frequency control.

### Installation

```bash
# Clone repository
git clone https://github.com/r4m0n/ZenStates-Linux.git
cd ZenStates-Linux

# Make executable
chmod +x zenstates.py

# Install to system (optional)
sudo cp zenstates.py /usr/local/bin/zenstates
sudo chmod +x /usr/local/bin/zenstates
```

### Usage Examples

#### View Current P-States

```bash
# Display current P-state configuration
sudo ./zenstates.py -l
```

**Output example:**
```
P0 - Enabled - FID = 90 - DID = 8 - VID = 32 - Ratio = 36.00 - vCore = 1.2500
P1 - Enabled - FID = 84 - DID = 8 - VID = 38 - Ratio = 33.00 - vCore = 1.2125
P2 - Enabled - FID = 78 - DID = 8 - VID = 44 - Ratio = 30.00 - vCore = 1.1750
```

#### Undervolt CPU

```bash
# Reduce voltage by 50mV for P0 state
# Current VID = 32, each step = ~6.25mV
# 50mV / 6.25mV = 8 steps
# New VID = 32 + 8 = 40
sudo ./zenstates.py -p 0 -v 40

# Reduce voltage for all P-states by 75mV
sudo ./zenstates.py -p 0 -v 44  # P0: ~75mV reduction
sudo ./zenstates.py -p 1 -v 50  # P1: ~75mV reduction
sudo ./zenstates.py -p 2 -v 56  # P2: ~75mV reduction
```

**VID to Voltage conversion:**
- VID = 0: 1.55V
- VID = 32: 1.25V
- VID = 40: 1.20V
- VID = 64: 1.05V
- Each VID step ≈ 6.25mV

#### Disable C-States for Maximum Performance

```bash
# Disable C6 state
sudo ./zenstates.py --c6-disable

# Re-enable C6 state
sudo ./zenstates.py --c6-enable
```

#### Make Changes Persistent

Create a systemd service:

```bash
sudo nano /etc/systemd/system/zenstates.service
```

Add content:

```ini
[Unit]
Description=Apply ZenStates CPU configuration
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/zenstates -p 0 -v 40
ExecStart=/usr/local/bin/zenstates -p 1 -v 46
ExecStart=/usr/local/bin/zenstates -p 2 -v 52

[Install]
WantedBy=multi-user.target
```

Enable service:

```bash
sudo systemctl enable zenstates.service
sudo systemctl start zenstates.service
```

---

## Verification and Testing

### 1. Verify CPU Frequency Control

```bash
# Watch CPU frequencies in real-time
watch -n 1 'grep MHz /proc/cpuinfo'

# Or use cpupower
watch -n 1 'cpupower frequency-info | grep "current CPU"'

# Generate CPU load and monitor
stress-ng --cpu $(nproc) --timeout 30s &
watch -n 1 sensors
```

### 2. Stress Testing

⚠️ **Critical**: Always monitor temperatures during stress testing!

```bash
# Install stress testing tools
sudo apt install stress-ng sysbench

# CPU stress test (all cores, 10 minutes)
stress-ng --cpu $(nproc) --timeout 600s --metrics-brief

# Monitor temperatures while stress testing
watch -n 2 'sensors | grep -E "Tctl|Tdie"'

# Prime number calculation stress test
sysbench cpu --threads=$(nproc) --time=300 run
```

### 3. Stability Testing

```bash
# Install y-cruncher (Pi calculation benchmark)
wget http://www.numberworld.org/y-cruncher/y-cruncher%20v0.8.5.9545-static.tar.xz
tar xf y-cruncher*.tar.xz
cd y-cruncher*

# Run stress test
./y-cruncher stress -test

# Or use mprime (Prime95 for Linux)
wget https://www.mersenne.org/download/software/v30/30.8/p95v308b17.linux64.tar.gz
tar xf p95*.tar.gz
cd p95
./mprime -t
```

**Recommended stability testing duration:**
- Quick test: 30 minutes
- Standard test: 2-4 hours
- Thorough test: 8-12 hours
- Extreme validation: 24+ hours

### 4. Benchmark Performance

```bash
# Install Geekbench
# Download from: https://www.geekbench.com/download/linux/

# Single-core and multi-core benchmark
./geekbench5

# Or use sysbench
sysbench cpu --threads=1 run      # Single-core
sysbench cpu --threads=$(nproc) run  # Multi-core
```

---

## Troubleshooting

### System Becomes Unstable After Changes

1. **Boot into recovery mode**:
   - Reboot and select "Advanced options" in GRUB
   - Select recovery mode
   - Select "root" for root shell

2. **Revert changes**:
```bash
# Reset CPU frequency governor to default
for cpu in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
    echo "schedutil" > $cpu
done

# Re-enable CPU boost
echo 1 > /sys/devices/system/cpu/cpufreq/boost

# Reboot
reboot
```

3. **Reset GRUB parameters**:
```bash
# Edit GRUB config
nano /etc/default/grub

# Remove custom parameters, keep only basics
GRUB_CMDLINE_LINUX_DEFAULT="quiet splash"

# Update and reboot
update-grub
reboot
```

### CPU Not Boosting to Maximum Frequency

```bash
# Check if boost is enabled
cat /sys/devices/system/cpu/cpufreq/boost

# Enable boost
echo 1 | sudo tee /sys/devices/system/cpu/cpufreq/boost

# Check thermal throttling
sensors | grep -i temp

# Verify power limits aren't restricting performance
sudo dmesg | grep -i "power"
```

### High Temperatures

```bash
# Check current temperatures
sensors

# Verify fan speed (if applicable)
sensors | grep -i fan

# Check for thermal throttling
sudo dmesg | tail -50 | grep -i thermal

# Reduce maximum frequency temporarily
sudo cpupower frequency-set -u 3.5GHz

# Enable powersave governor
sudo cpupower frequency-set -g powersave
```

### CoreCtrl Not Applying Settings

```bash
# Check CoreCtrl logs
journalctl -xe | grep corectrl

# Verify polkit rules are correct
sudo cat /etc/polkit-1/rules.d/90-corectrl.rules

# Restart CoreCtrl with elevated privileges
pkill corectrl
corectrl
```

### Sensors Not Detecting CPU Temperature

```bash
# Run sensor detection again
sudo sensors-detect --auto

# Load modules manually
sudo modprobe k10temp
# or
sudo modprobe zenpower

# Check if modules are loaded
lsmod | grep -E "k10temp|zenpower"

# View kernel messages for errors
sudo dmesg | grep -i sensor
```

---

## Performance Tuning Examples

### Profile 1: Maximum Performance

```bash
# Set performance governor
sudo cpupower frequency-set -g performance

# Enable CPU boost
echo 1 | sudo tee /sys/devices/system/cpu/cpufreq/boost

# Disable C-states (if using ZenStates)
sudo zenstates --c6-disable

# Set minimum frequency to maximum
sudo cpupower frequency-set -d 3.8GHz -u 4.5GHz
```

**Use case**: Gaming, video rendering, compilation, benchmarking

**Power consumption**: Very High

### Profile 2: Balanced Performance

```bash
# Set schedutil governor (kernel-managed)
sudo cpupower frequency-set -g schedutil

# Enable boost
echo 1 | sudo tee /sys/devices/system/cpu/cpufreq/boost

# Allow wide frequency range
sudo cpupower frequency-set -d 2.2GHz -u 4.5GHz
```

**Use case**: General desktop use, web browsing, light productivity

**Power consumption**: Medium

### Profile 3: Power Saving

```bash
# Set powersave governor
sudo cpupower frequency-set -g powersave

# Disable boost
echo 0 | sudo tee /sys/devices/system/cpu/cpufreq/boost

# Limit maximum frequency
sudo cpupower frequency-set -u 3.0GHz
```

**Use case**: Laptop battery saving, low-load server, idle system

**Power consumption**: Low

### Profile 4: Undervolted Performance

```bash
# Apply undervolting (example: -75mV)
sudo zenstates -p 0 -v 44
sudo zenstates -p 1 -v 50
sudo zenstates -p 2 -v 56

# Set performance governor
sudo cpupower frequency-set -g performance

# Enable boost
echo 1 | sudo tee /sys/devices/system/cpu/cpufreq/boost
```

**Use case**: Maximum performance with reduced heat and power consumption

**Power consumption**: High (but lower than Profile 1)

**⚠️ Requires stability testing!**

---

## Safety Best Practices

### 1. Temperature Monitoring

**Always monitor temperatures:**

```bash
# Create continuous temperature log
while true; do
    echo "$(date) - $(sensors | grep Tctl)"
    sleep 5
done > ~/cpu_temps.log
```

**Safe temperature ranges:**
- **Idle**: 30-45°C
- **Load**: 60-75°C
- **Maximum (short bursts)**: 85°C
- **Dangerous**: 90°C+ (immediate action required)

### 2. Incremental Changes

**Never apply aggressive settings immediately:**

1. Start with conservative undervolt (-25mV)
2. Test stability for 1 hour
3. If stable, decrease by another 25mV
4. Repeat until instability occurs
5. Increase voltage by 12.5mV for safety margin

### 3. Backup and Recovery Plan

```bash
# Create rescue script
cat > ~/rescue-cpu.sh << 'SCRIPT'
#!/bin/bash
echo "schedutil" | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
echo 1 | sudo tee /sys/devices/system/cpu/cpufreq/boost
sudo cpupower frequency-set -d 2200MHz -u 4500MHz
echo "CPU settings reset to safe defaults"
SCRIPT

chmod +x ~/rescue-cpu.sh
```

### 4. Document Your Changes

```bash
# Create configuration log
cat > ~/cpu-config.log << EOF
Date: $(date)
CPU: $(lscpu | grep "Model name")
Governor: $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor)
Min Freq: $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq)
Max Freq: $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq)
Boost: $(cat /sys/devices/system/cpu/cpufreq/boost)
Undervolting: P0=-50mV, P1=-50mV, P2=-50mV
Notes: Stable after 4 hours stress test
EOF
```

### 5. Signs of Instability

**Watch for these symptoms:**
- Random system freezes or reboots
- Application crashes
- Calculation errors (failed Prime95 tests)
- Kernel panics in dmesg
- System log errors related to CPU

**If instability occurs:**
1. Immediately boot into safe mode or recovery
2. Revert last changes
3. Run stability tests again
4. Document what caused the issue

---

## Performance Monitoring Scripts

### Comprehensive CPU Monitor

```bash
#!/bin/bash
# Save as: ~/monitor-cpu.sh

while true; do
    clear
    echo "=== CPU Monitoring Dashboard ==="
    echo "Time: $(date)"
    echo
    echo "--- Temperatures ---"
    sensors | grep -E "Tctl|Tdie|Package"
    echo
    echo "--- Frequencies ---"
    grep MHz /proc/cpuinfo | awk '{printf "CPU%02d: %s\n", NR-1, $4}'
    echo
    echo "--- Power ---"
    sensors | grep -i power
    echo
    echo "--- Governor ---"
    cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
    echo
    echo "--- Boost ---"
    cat /sys/devices/system/cpu/cpufreq/boost
    
    sleep 2
done
```

```bash
chmod +x ~/monitor-cpu.sh
./monitor-cpu.sh
```

### Log CPU Statistics

```bash
#!/bin/bash
# Save as: ~/log-cpu-stats.sh

LOG_FILE=~/cpu_stats_$(date +%Y%m%d_%H%M%S).log

echo "Logging CPU statistics to $LOG_FILE"
echo "Press Ctrl+C to stop"

while true; do
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    TEMP=$(sensors | grep Tctl | awk '{print $2}')
    FREQ=$(grep MHz /proc/cpuinfo | head -1 | awk '{print $4}')
    POWER=$(sensors | grep -i "Package power" | awk '{print $3}')
    
    echo "$TIMESTAMP,$TEMP,$FREQ MHz,$POWER" >> $LOG_FILE
    sleep 5
done
```

---

## References

### Official Documentation

- [AMD Processor Programming Reference](https://www.amd.com/en/support/tech-docs)
- [Linux Kernel Documentation - CPUFreq](https://www.kernel.org/doc/html/latest/admin-guide/pm/cpufreq.html)
- [CoreCtrl Wiki](https://gitlab.com/corectrl/corectrl/-/wikis/home)

### Tools and Projects

- **CoreCtrl**: https://gitlab.com/corectrl/corectrl
- **ZenStates-Linux**: https://github.com/r4m0n/ZenStates-Linux
- **ryzen_smu**: https://github.com/leogx9r/ryzen_smu
- **Zenpower**: https://github.com/ocerman/zenpower
- **cpupower**: Part of linux-tools package

### Community Resources

- **r/Amd** (Reddit): Community discussions and guides
- **Level1Techs Forums**: In-depth AMD CPU discussions
- **Phoronix Forums**: Linux performance and hardware discussions

### Stress Testing Tools

- **stress-ng**: https://kernel.ubuntu.com/~cking/stress-ng/
- **Prime95/mprime**: https://www.mersenne.org/download/
- **y-cruncher**: http://www.numberworld.org/y-cruncher/

### Monitoring Tools

- **htop**: https://htop.dev/
- **btop**: https://github.com/aristocratos/btop
- **lm-sensors**: https://github.com/lm-sensors/lm-sensors

---

## License and Warranty

This guide is provided for educational purposes only. The author(s) assume NO responsibility for:
- Hardware damage
- Data loss
- System instability
- Voided warranties
- Any other consequences of following this guide

**Always proceed at your own risk and ensure you understand what each command does before executing it.**

---

## Contributing

Found an error or have improvements? Contributions are welcome:

1. Test your changes thoroughly
2. Document all steps clearly
3. Include safety warnings where appropriate
4. Provide example output where helpful

---

## Changelog

**Version 1.0** (2025-01-02)
- Initial release
- Coverage of CoreCtrl, cpupower, ZenStates, ryzen_smu, zenpower
- Comprehensive safety guidelines
- Troubleshooting section
- Performance tuning profiles
README.md Inicial de Ferramentas AMD (1.624 linhas)
Guia completo sobre CoreCtrl, LACT, ZenStates, cpupower, ryzen_smu, etc.
2️⃣ Framework de Automação AMD Auto Tuner
Estrutura completa:
amd-auto-tuner/
├── 📄 main.py                    # Orquestrador principal (400 linhas)
├── 🔧 install.sh                 # Script de instalação automática
├── 💡 examples.py                # Exemplos de uso programático
├── 📋 requirements.txt           # Dependências Python
│
├── 📦 modules/                   # Módulos de tuning
│   ├── hardware_detector.py     # Detecta CPU, storage, rede (400 linhas)
│   ├── cpu_tuner.py             # Otimização de CPU AMD (300 linhas)
│   ├── storage_tuner.py         # Otimização NVMe/SSD/HDD (250 linhas)
│   ├── network_tuner.py         # Otimização de rede (350 linhas)
│   ├── benchmarker.py           # Sistema de benchmark (200 linhas)
│   └── config_manager.py        # Gerenciamento de config (100 linhas)
│
├── ⚙️ config/
│   └── config.yaml              # Configuração personalizável
│
├── 📚 Documentação
│   ├── README.md                # Guia completo do usuário
│   ├── ARCHITECTURE.md          # Arquitetura técnica detalhada
│   └── GETTING_STARTED.md       # Início rápido
│
└── 📁 Diretórios auto-criados
    ├── logs/                    # Logs de execução
    ├── backups/                 # Backups de configurações
    ├── benchmarks/              # Resultados de benchmarks
    └── reports/                 # Relatórios de performance
🚀 Capacidades do Framework:
Detecção Automática:

✅ CPU AMD (Zen, Zen2, Zen3, Zen4)
✅ Cores, threads, frequências
✅ Discos NVMe, SSD, HDD
✅ Interfaces de rede
✅ Drivers e capacidades

Tuning Inteligente:
CPU:

Governor selection (performance, schedutil, powersave)
Frequency scaling
Boost control
C-state management
AMD P-State EPP (Zen 4+)
Perfis por workload

Storage:

I/O scheduler por tipo (none para NVMe, mq-deadline para SSD, bfq para HDD)
Queue depth optimization
Read-ahead tuning
NVMe polling
TRIM management

Network:

Ring buffer optimization
Hardware offloads
Interrupt coalescing
Sysctl tuning
BBR congestion control
Otimizações por driver (Intel, Mellanox)

Benchmarking:

CPU (single/multi-core via sysbench)
Storage I/O (fio - read/write/IOPS/latency)
Network (ping - latency/packet loss)
Comparação antes/depois

Segurança:

Backup automático antes de mudanças
Logging detalhado
Rollback capability
Modo de análise sem alterações