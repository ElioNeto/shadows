#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# install-system-deps.sh — Install system dependencies for Shadows
#
# Usage:
#   sudo bash scripts/setup-system-deps.sh
#
# Supported distributions: Ubuntu, Debian, Fedora, Arch Linux, openSUSE
# ---------------------------------------------------------------------------

set -euo pipefail

echo "=== Shadows — System Dependency Installer ==="

# ── Detect distribution ───────────────────────────────────────────
get_distro() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        echo "$ID"
    elif command -v lsb_release &>/dev/null; then
        lsb_release -is | tr '[:upper:]' '[:lower:]'
    else
        echo "unknown"
    fi
}

DISTRO=$(get_distro)

install_ubuntu_debian() {
    echo "Detected: Ubuntu/Debian"
    apt-get update -qq
    apt-get install -y -qq \
        python3 \
        python3-pip \
        python3-pyqt5 \
        python3-psutil \
        python3-cryptography \
        python3-dbus \
        libdbus-1-dev \
        libdbus-glib-1-dev \
        libgl1-mesa-glx \
        libegl1-mesa \
        xdotool \
        pipewire \
        pipewire-pulse \
        wireplumber \
        dbus-x11 \
        busctl 2>/dev/null || true
}

install_fedora() {
    echo "Detected: Fedora"
    dnf install -y \
        python3 \
        python3-pip \
        python3-qt5 \
        python3-psutil \
        python3-cryptography \
        python3-dbus \
        dbus-devel \
        dbus-glib-devel \
        xdotool \
        pipewire \
        pipewire-pulseaudio \
        wireplumber \
        dbus-x11
}

install_arch() {
    echo "Detected: Arch Linux"
    pacman -S --noconfirm \
        python \
        python-pip \
        pyqt5 \
        python-psutil \
        python-cryptography \
        python-dbus \
        dbus \
        xdotool \
        pipewire \
        pipewire-pulse \
        wireplumber \
        dbus
}

install_opensuse() {
    echo "Detected: openSUSE"
    zypper install -y \
        python3 \
        python3-pip \
        python3-qt5 \
        python3-psutil \
        python3-cryptography \
        python3-dbus-python \
        dbus-1-devel \
        dbus-1-glib-devel \
        xdotool \
        pipewire \
        pipewire-pulseaudio \
        wireplumber \
        dbus-1-x11
}

case "$DISTRO" in
    ubuntu|debian|linuxmint|pop|elementary|zorin)
        install_ubuntu_debian
        ;;
    fedora|rhel|centos)
        install_fedora
        ;;
    arch|manjaro|endeavouros|garuda)
        install_arch
        ;;
    opensuse*|suse)
        install_opensuse
        ;;
    *)
        echo "Unsupported distribution: $DISTRO"
        echo ""
        echo "Please install the following packages manually:"
        echo "  - python3, python3-pip"
        echo "  - PyQt5 (python3-pyqt5 or pyqt5)"
        echo "  - psutil (python3-psutil)"
        echo "  - cryptography (python3-cryptography)"
        echo "  - dbus-python (python3-dbus, libdbus-1-dev)"
        echo "  - xdotool (for X11 detection)"
        echo "  - pipewire, wireplumber (for Wayland detection)"
        exit 1
        ;;
esac

echo ""
echo "=== System dependencies installed successfully ==="
echo "Now run:  pip install -r requirements.txt"
echo "Or:       pip install -e ."
