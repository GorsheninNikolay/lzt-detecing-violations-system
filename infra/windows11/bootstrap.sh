#!/bin/bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_MODE=a
install -d -m 700 /etc/lzt
printf '#!/bin/sh\nexit 101\n' > /usr/sbin/policy-rc.d
chmod 755 /usr/sbin/policy-rc.d
apt-get update
apt-get install -y --no-install-recommends systemd-sysv ca-certificates curl python3 python3-venv postgresql-17 nginx libgl1 libglib2.0-0 logrotate
systemctl --root=/ disable nginx.service postgresql.service
printf '[boot]\nsystemd=true\n[user]\ndefault=root\n' > /etc/wsl.conf
install -d -m 755 /opt/lzt /opt/lzt/bin /opt/lzt/python /opt/lzt/releases
python3 -m venv /opt/lzt/tools-venv
/opt/lzt/tools-venv/bin/python -m pip install --disable-pip-version-check uv==0.12.7
export UV_PYTHON_INSTALL_DIR=/opt/lzt/python
export UV_CACHE_DIR=/opt/lzt/uv-cache
/opt/lzt/tools-venv/bin/uv python install 3.13.15
/opt/lzt/tools-venv/bin/uv venv --python 3.13.15 /opt/lzt/venv
printf 'Bootstrap complete; restart only the LztEvidence distro before setup_app.py\n'
