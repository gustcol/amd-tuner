#!/bin/bash
# =============================================================================
# AMD Auto Tuner - Installation Script
# =============================================================================
# This script automatically installs all dependencies and sets up the
# AMD Auto Tuner framework on Linux systems.
#
# Supported distributions:
#   - Ubuntu/Debian
#   - Fedora/RHEL/CentOS
#   - Arch Linux
#
# Usage:
#   ./install.sh [OPTIONS]
#
# Options:
#   --help, -h      Show this help message
#   --dev           Install development dependencies
#   --no-confirm    Skip confirmation prompts
#   --uninstall     Remove AMD Auto Tuner
# =============================================================================

set -euo pipefail

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="/opt/amd-auto-tuner"
BIN_LINK="/usr/local/bin/amd-tuner"
CONFIG_DIR="/etc/amd-auto-tuner"

# Flags
DEV_MODE=false
NO_CONFIRM=false
UNINSTALL=false

# =============================================================================
# Helper Functions
# =============================================================================

print_banner() {
    echo -e "${BLUE}"
    echo "=============================================="
    echo "       AMD Auto Tuner Installation"
    echo "=============================================="
    echo -e "${NC}"
}

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

detect_distro() {
    if [[ -f /etc/os-release ]]; then
        # shellcheck source=/dev/null
        source /etc/os-release
        DISTRO_ID="${ID:-unknown}"
        DISTRO_LIKE="${ID_LIKE:-$DISTRO_ID}"
    else
        DISTRO_ID="unknown"
        DISTRO_LIKE="unknown"
    fi

    log_info "Detected distribution: $DISTRO_ID"
}

confirm_action() {
    if [[ "$NO_CONFIRM" == "true" ]]; then
        return 0
    fi

    local prompt="${1:-Continue?}"
    echo -e -n "${YELLOW}${prompt} [y/N]: ${NC}"
    read -r response
    case "$response" in
        [yY][eE][sS]|[yY])
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

# =============================================================================
# Package Installation Functions
# =============================================================================

install_packages_debian() {
    log_step "Installing packages for Debian/Ubuntu..."

    apt-get update

    # Core dependencies
    apt-get install -y \
        python3 \
        python3-pip \
        python3-venv \
        ethtool \
        lm-sensors \
        linux-cpupower \
        cpufrequtils \
        pciutils \
        iproute2

    # Benchmarking tools
    apt-get install -y \
        sysbench \
        fio \
        iperf3 \
        stress-ng || log_warn "Some benchmarking tools could not be installed"

    # Development tools (optional)
    if [[ "$DEV_MODE" == "true" ]]; then
        apt-get install -y \
            shellcheck \
            git \
            build-essential
    fi
}

install_packages_fedora() {
    log_step "Installing packages for Fedora/RHEL..."

    dnf install -y \
        python3 \
        python3-pip \
        ethtool \
        lm_sensors \
        kernel-tools \
        pciutils \
        iproute

    # Benchmarking tools
    dnf install -y \
        sysbench \
        fio \
        iperf3 \
        stress-ng || log_warn "Some benchmarking tools could not be installed"

    # Development tools (optional)
    if [[ "$DEV_MODE" == "true" ]]; then
        dnf install -y \
            ShellCheck \
            git \
            gcc \
            gcc-c++
    fi
}

install_packages_arch() {
    log_step "Installing packages for Arch Linux..."

    pacman -Sy --noconfirm \
        python \
        python-pip \
        ethtool \
        lm_sensors \
        cpupower \
        pciutils \
        iproute2

    # Benchmarking tools
    pacman -S --noconfirm \
        sysbench \
        fio \
        iperf3 \
        stress || log_warn "Some benchmarking tools could not be installed"

    # Development tools (optional)
    if [[ "$DEV_MODE" == "true" ]]; then
        pacman -S --noconfirm \
            shellcheck \
            git \
            base-devel
    fi
}

install_system_packages() {
    log_step "Installing system packages..."

    case "$DISTRO_ID" in
        ubuntu|debian|linuxmint|pop)
            install_packages_debian
            ;;
        fedora|rhel|centos|rocky|almalinux)
            install_packages_fedora
            ;;
        arch|manjaro|endeavouros)
            install_packages_arch
            ;;
        *)
            if [[ "$DISTRO_LIKE" == *"debian"* ]]; then
                install_packages_debian
            elif [[ "$DISTRO_LIKE" == *"fedora"* ]] || [[ "$DISTRO_LIKE" == *"rhel"* ]]; then
                install_packages_fedora
            elif [[ "$DISTRO_LIKE" == *"arch"* ]]; then
                install_packages_arch
            else
                log_error "Unsupported distribution: $DISTRO_ID"
                log_info "Please install dependencies manually:"
                echo "  - python3, python3-pip"
                echo "  - ethtool, lm-sensors, cpupower"
                echo "  - sysbench, fio (optional, for benchmarks)"
                exit 1
            fi
            ;;
    esac
}

install_python_packages() {
    log_step "Installing Python packages..."

    # Create virtual environment (optional but recommended)
    if [[ -d "$INSTALL_DIR" ]]; then
        cd "$INSTALL_DIR"

        if [[ ! -d "venv" ]]; then
            python3 -m venv venv
        fi

        # shellcheck source=/dev/null
        source venv/bin/activate

        pip install --upgrade pip
        pip install -r requirements.txt

        if [[ "$DEV_MODE" == "true" ]]; then
            pip install mypy pytest black flake8 pylint
        fi

        deactivate
    else
        # Install globally if not using install directory
        pip3 install PyYAML

        if [[ "$DEV_MODE" == "true" ]]; then
            pip3 install mypy pytest black flake8 pylint
        fi
    fi
}

install_ty() {
    log_step "Installing ty (type checker)..."

    # ty is from astral-sh, typically installed via cargo or pipx
    if command -v cargo &> /dev/null; then
        cargo install ty 2>/dev/null || log_warn "Could not install ty via cargo"
    elif command -v pipx &> /dev/null; then
        pipx install ty 2>/dev/null || log_warn "Could not install ty via pipx"
    else
        # Try pip as fallback
        pip3 install ty 2>/dev/null || log_warn "ty not available, using mypy as alternative"
    fi
}

# =============================================================================
# Installation Functions
# =============================================================================

install_application() {
    log_step "Installing AMD Auto Tuner..."

    # Create installation directory
    mkdir -p "$INSTALL_DIR"
    mkdir -p "$CONFIG_DIR"

    # Copy files
    cp -r "$SCRIPT_DIR"/* "$INSTALL_DIR/"

    # Copy default config if not exists
    if [[ ! -f "$CONFIG_DIR/config.yaml" ]]; then
        cp "$SCRIPT_DIR/config/config.yaml" "$CONFIG_DIR/"
    fi

    # Create symlink to config
    ln -sf "$CONFIG_DIR/config.yaml" "$INSTALL_DIR/config/config.yaml"

    # Create executable symlink
    cat > "$BIN_LINK" << 'WRAPPER'
#!/bin/bash
# AMD Auto Tuner wrapper script
INSTALL_DIR="/opt/amd-auto-tuner"

if [[ -d "$INSTALL_DIR/venv" ]]; then
    source "$INSTALL_DIR/venv/bin/activate"
fi

python3 "$INSTALL_DIR/main.py" "$@"
WRAPPER

    chmod +x "$BIN_LINK"

    # Set permissions
    chmod -R 755 "$INSTALL_DIR"
    chmod 644 "$CONFIG_DIR/config.yaml"
}

setup_sensors() {
    log_step "Setting up hardware sensors..."

    # Run sensors-detect if available
    if command -v sensors-detect &> /dev/null; then
        sensors-detect --auto 2>/dev/null || log_warn "sensors-detect failed"
    fi

    # Load k10temp module for AMD CPUs
    modprobe k10temp 2>/dev/null || true

    # Enable sensors service
    if command -v systemctl &> /dev/null; then
        systemctl enable lm_sensors 2>/dev/null || true
        systemctl start lm_sensors 2>/dev/null || true
    fi
}

create_systemd_service() {
    log_step "Creating systemd service (optional)..."

    cat > /etc/systemd/system/amd-auto-tuner.service << 'SERVICE'
[Unit]
Description=AMD Auto Tuner - Apply performance profile at boot
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/amd-tuner profile balanced
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
SERVICE

    log_info "Systemd service created. Enable with: systemctl enable amd-auto-tuner"
}

# =============================================================================
# Uninstallation Functions
# =============================================================================

uninstall_application() {
    log_step "Uninstalling AMD Auto Tuner..."

    # Remove symlink
    rm -f "$BIN_LINK"

    # Remove systemd service
    if [[ -f /etc/systemd/system/amd-auto-tuner.service ]]; then
        systemctl disable amd-auto-tuner 2>/dev/null || true
        rm -f /etc/systemd/system/amd-auto-tuner.service
        systemctl daemon-reload
    fi

    # Ask about config removal
    if [[ -d "$CONFIG_DIR" ]]; then
        if confirm_action "Remove configuration files?"; then
            rm -rf "$CONFIG_DIR"
        fi
    fi

    # Remove installation directory
    if [[ -d "$INSTALL_DIR" ]]; then
        rm -rf "$INSTALL_DIR"
    fi

    log_info "AMD Auto Tuner has been uninstalled"
}

# =============================================================================
# Verification Functions
# =============================================================================

verify_installation() {
    log_step "Verifying installation..."

    local errors=0

    # Check main script
    if [[ ! -f "$INSTALL_DIR/main.py" ]]; then
        log_error "main.py not found"
        ((errors++))
    fi

    # Check modules
    for module in hardware_detector cpu_tuner storage_tuner network_tuner benchmarker config_manager; do
        if [[ ! -f "$INSTALL_DIR/modules/${module}.py" ]]; then
            log_error "Module $module not found"
            ((errors++))
        fi
    done

    # Check executable
    if [[ ! -x "$BIN_LINK" ]]; then
        log_error "Executable not found or not executable"
        ((errors++))
    fi

    # Test execution
    if ! "$BIN_LINK" --version &>/dev/null; then
        log_error "Failed to execute amd-tuner"
        ((errors++))
    fi

    if [[ $errors -eq 0 ]]; then
        log_info "All checks passed!"
        return 0
    else
        log_error "$errors error(s) found"
        return 1
    fi
}

print_usage() {
    log_step "Installation complete!"
    echo ""
    echo "Usage:"
    echo "  amd-tuner detect              # Detect hardware"
    echo "  amd-tuner benchmark           # Run benchmarks"
    echo "  amd-tuner profile performance # Apply performance profile"
    echo "  amd-tuner profile balanced    # Apply balanced profile"
    echo "  amd-tuner profile powersave   # Apply power saving profile"
    echo "  amd-tuner restore             # Restore previous settings"
    echo "  amd-tuner --help              # Show all options"
    echo ""
    echo "Configuration file: $CONFIG_DIR/config.yaml"
    echo ""
}

# =============================================================================
# Main Script
# =============================================================================

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --help|-h)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --help, -h      Show this help message"
                echo "  --dev           Install development dependencies"
                echo "  --no-confirm    Skip confirmation prompts"
                echo "  --uninstall     Remove AMD Auto Tuner"
                exit 0
                ;;
            --dev)
                DEV_MODE=true
                shift
                ;;
            --no-confirm)
                NO_CONFIRM=true
                shift
                ;;
            --uninstall)
                UNINSTALL=true
                shift
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
}

main() {
    parse_args "$@"

    print_banner

    check_root
    detect_distro

    if [[ "$UNINSTALL" == "true" ]]; then
        if confirm_action "This will remove AMD Auto Tuner. Continue?"; then
            uninstall_application
        fi
        exit 0
    fi

    echo "This script will install AMD Auto Tuner and its dependencies."
    echo ""
    if ! confirm_action "Continue with installation?"; then
        log_info "Installation cancelled"
        exit 0
    fi

    install_system_packages
    install_application
    install_python_packages

    if [[ "$DEV_MODE" == "true" ]]; then
        install_ty
    fi

    setup_sensors
    create_systemd_service
    verify_installation

    print_usage
}

main "$@"
