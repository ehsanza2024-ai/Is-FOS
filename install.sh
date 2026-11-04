#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
# Debian 12 GTK backend. System packages are installed only with explicit consent.
if [ "${1:-}" = "--system-deps" ]; then
  . /etc/os-release
  [ "$ID" = debian ] && [ "$VERSION_ID" = 12 ] || { echo 'Automatic OS packages are configured for Debian 12 only. Install matching Python 3.11 + GTK manually on other systems.'; exit 1; }
  sudo apt-get update
  sudo apt-get install -y python3.11 python3.11-venv python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1 libgirepository1.0-dev
fi
command -v python3.11 >/dev/null || {
  echo 'Python 3.11 is required. Install it using your supported distribution package source.'
  echo 'GTK prerequisites: python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1. See docs/INSTALL_CENTRAL_FA.md.'
  exit 1
}
python3.11 -m venv --system-site-packages .venv
.venv/bin/python -m pip install -r requirements.lock.txt -r requirements-desktop.txt
.venv/bin/python -m scripts.setup_central
printf '%s\n' 'Installed. Run ./start.sh in a graphical desktop session.' 'No firewall rule was changed. See docs/INSTALL_CENTRAL_FA.md.'
