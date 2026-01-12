#!/bin/bash
#
# AMD Auto Tuner - Systemd Installation Script
# Installs and configures systemd service and timer units
#
# Usage:
#   sudo ./install-systemd.sh [options]
#
# Options:
#   --boot-only    Only install boot service (no timer)
#   --hpc          Install HPC-specific service
#   --timer        Install periodic timer
#   --all          Install all services
#   --uninstall    Remove all services
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYSTEMD_DIR="/etc/systemd/system"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root"
        exit 1
    fi
}

install_boot_service() {
    log_info "Installing boot service..."
    cp "${SCRIPT_DIR}/amd-auto-tuner-boot.service" "${SYSTEMD_DIR}/"
    systemctl daemon-reload
    systemctl enable amd-auto-tuner-boot.service
    log_info "Boot service installed and enabled"
}

install_timer() {
    log_info "Installing timer service..."
    cp "${SCRIPT_DIR}/amd-auto-tuner.service" "${SYSTEMD_DIR}/"
    cp "${SCRIPT_DIR}/amd-auto-tuner.timer" "${SYSTEMD_DIR}/"
    systemctl daemon-reload
    systemctl enable amd-auto-tuner.timer
    systemctl start amd-auto-tuner.timer
    log_info "Timer installed and started"
}

install_hpc_service() {
    log_info "Installing HPC service..."
    cp "${SCRIPT_DIR}/amd-auto-tuner-hpc.service" "${SYSTEMD_DIR}/"
    systemctl daemon-reload
    log_info "HPC service installed (enable manually with: systemctl enable amd-auto-tuner-hpc.service)"
}

uninstall_all() {
    log_info "Uninstalling all AMD Auto Tuner systemd units..."

    # Stop and disable services
    for service in amd-auto-tuner-boot amd-auto-tuner amd-auto-tuner-hpc; do
        if systemctl is-active --quiet "${service}.service" 2>/dev/null; then
            systemctl stop "${service}.service" || true
        fi
        if systemctl is-enabled --quiet "${service}.service" 2>/dev/null; then
            systemctl disable "${service}.service" || true
        fi
    done

    # Stop and disable timer
    if systemctl is-active --quiet amd-auto-tuner.timer 2>/dev/null; then
        systemctl stop amd-auto-tuner.timer || true
    fi
    if systemctl is-enabled --quiet amd-auto-tuner.timer 2>/dev/null; then
        systemctl disable amd-auto-tuner.timer || true
    fi

    # Remove unit files
    rm -f "${SYSTEMD_DIR}/amd-auto-tuner.service"
    rm -f "${SYSTEMD_DIR}/amd-auto-tuner.timer"
    rm -f "${SYSTEMD_DIR}/amd-auto-tuner-boot.service"
    rm -f "${SYSTEMD_DIR}/amd-auto-tuner-hpc.service"

    systemctl daemon-reload
    log_info "All AMD Auto Tuner systemd units removed"
}

show_status() {
    echo ""
    echo "=== AMD Auto Tuner Systemd Status ==="
    echo ""

    for unit in amd-auto-tuner-boot.service amd-auto-tuner.timer amd-auto-tuner-hpc.service; do
        if [[ -f "${SYSTEMD_DIR}/${unit}" ]]; then
            status=$(systemctl is-enabled "${unit}" 2>/dev/null || echo "not installed")
            active=$(systemctl is-active "${unit}" 2>/dev/null || echo "inactive")
            echo "  ${unit}: enabled=${status}, active=${active}"
        else
            echo "  ${unit}: not installed"
        fi
    done

    echo ""
}

show_help() {
    cat << EOF
AMD Auto Tuner - Systemd Installation Script

Usage: sudo $0 [options]

Options:
  --boot-only    Install only the boot service
  --timer        Install the periodic timer
  --hpc          Install HPC-specific service
  --all          Install all services
  --uninstall    Remove all services
  --status       Show current status
  --help         Show this help message

Examples:
  sudo $0 --boot-only     # Apply profile at every boot
  sudo $0 --all           # Full installation
  sudo $0 --uninstall     # Remove all services

EOF
}

main() {
    check_root

    if [[ $# -eq 0 ]]; then
        show_help
        exit 0
    fi

    case "${1:-}" in
        --boot-only)
            install_boot_service
            show_status
            ;;
        --timer)
            install_timer
            show_status
            ;;
        --hpc)
            install_hpc_service
            show_status
            ;;
        --all)
            install_boot_service
            install_timer
            install_hpc_service
            show_status
            ;;
        --uninstall)
            uninstall_all
            ;;
        --status)
            show_status
            ;;
        --help|-h)
            show_help
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
