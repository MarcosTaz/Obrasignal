#!/usr/bin/env bash
set -euo pipefail

# Host-side provisioning only. Run on the explicitly authorized isolated Factory Cloud host.
# This script does not create production credentials, app secrets, deployments, or billing authority.

REPO_DIR="${REPO_DIR:-/opt/factory-cloud/current}"
STATE_DIR="${STATE_DIR:-/var/lib/factory-cloud}"
CONFIG_DIR="${CONFIG_DIR:-/etc/factory-cloud}"
APPS="${APPS:-obrasignal}"
PREPARE_WORKSPACES="${PREPARE_WORKSPACES:-1}"
QUEUE_DIR="${QUEUE_DIR:-${STATE_DIR}/queues}"
LEGACY_STATE="${STATE_DIR}/state.sqlite3"

if [[ "${EUID}" -ne 0 ]]; then
  echo "install.sh must run as root on the isolated Factory Cloud host" >&2
  exit 2
fi

getent group factory-cloud >/dev/null || groupadd --system factory-cloud
id -u factory-cloud-control >/dev/null 2>&1 || useradd --system --home-dir /nonexistent --no-create-home --shell /usr/sbin/nologin --gid factory-cloud factory-cloud-control

if [[ -f "${LEGACY_STATE}" ]]; then
  python3 - "${LEGACY_STATE}" <<'PY'
import sqlite3
import sys

path = sys.argv[1]
conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
try:
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='worker_jobs'"
    ).fetchone()
    if not exists:
        raise SystemExit(0)
    unfinished = conn.execute(
        "SELECT COUNT(*) FROM worker_jobs WHERE consumed_at IS NULL"
    ).fetchone()[0]
    if unfinished:
        print(
            f"legacy shared queue contains {unfinished} unconsumed job(s); drain/classify them before queue isolation migration",
            file=sys.stderr,
        )
        raise SystemExit(5)
finally:
    conn.close()
PY
fi

install -d -o factory-cloud-control -g factory-cloud -m 0711 "${STATE_DIR}"
install -d -o factory-cloud-control -g factory-cloud -m 0711 "${QUEUE_DIR}"
install -d -o root -g root -m 0751 "${CONFIG_DIR}"
install -d -o root -g root -m 0711 "${CONFIG_DIR}/apps"
install -m 0644 "${REPO_DIR}/factory_cloud/runtime/systemd/factory-cloud-control.service" /etc/systemd/system/factory-cloud-control.service
install -m 0644 "${REPO_DIR}/factory_cloud/runtime/systemd/factory-cloud-app@.service" /etc/systemd/system/factory-cloud-app@.service
install -m 0644 "${REPO_DIR}/factory_cloud/runtime/systemd/factory-cloud.target" /etc/systemd/system/factory-cloud.target

for app in ${APPS}; do
  user="factory-cloud-${app}"
  queue_group="factory-cloud-queue-${app}"
  getent group "${user}" >/dev/null || groupadd --system "${user}"
  getent group "${queue_group}" >/dev/null || groupadd --system "${queue_group}"
  if ! id -u "${user}" >/dev/null 2>&1; then
    useradd --system --home-dir /nonexistent --no-create-home --shell /usr/sbin/nologin --gid "${user}" "${user}"
  fi

  if id -nG "${user}" | tr ' ' '\n' | grep -Fxq factory-cloud; then
    echo "${user} still belongs to legacy shared group factory-cloud; remove that supplementary membership before restart" >&2
    exit 4
  fi

  usermod -a -G "${queue_group}" factory-cloud-control
  usermod -a -G "${queue_group}" "${user}"
  install -d -o factory-cloud-control -g "${queue_group}" -m 2770 "${QUEUE_DIR}/${app}"

  config="${CONFIG_DIR}/apps/${app}.json"
  if [[ ! -f "${config}" ]]; then
    builtin="${REPO_DIR}/factory_cloud/runtime/${app}-adapter.json"
    if [[ ! -f "${builtin}" ]]; then
      echo "missing ${config} and no built-in adapter exists for ${app}" >&2
      exit 3
    fi
    install -o root -g "${user}" -m 0640 "${builtin}" "${config}"
  else
    chown root:"${user}" "${config}"
    chmod 0640 "${config}"
  fi

done

if [[ "${PREPARE_WORKSPACES}" == "1" ]]; then
  for app in ${APPS}; do
    if [[ "${app}" == "obrasignal" ]]; then
      CONTROL_REPO="${REPO_DIR}" bash "${REPO_DIR}/factory_cloud/runtime/systemd/prepare-obrasignal-workspace.sh"
    fi
  done
fi

systemctl daemon-reload
systemctl enable factory-cloud-control.service factory-cloud.target
for app in ${APPS}; do
  systemctl enable "factory-cloud-app@${app}.service"
done
systemctl restart factory-cloud-control.service
for app in ${APPS}; do
  systemctl restart "factory-cloud-app@${app}.service"
done
systemctl start factory-cloud.target

systemctl --no-pager --full status factory-cloud-control.service
for app in ${APPS}; do
  systemctl --no-pager --full status "factory-cloud-app@${app}.service"
done
