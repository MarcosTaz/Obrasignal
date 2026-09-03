#!/usr/bin/env bash
set -euo pipefail

# Host-side provisioning only. Run on the explicitly authorized isolated Factory Cloud host.
# This script does not create production credentials, app secrets, deployments, or billing authority.

REPO_DIR="${REPO_DIR:-/opt/factory-cloud/current}"
STATE_DIR="${STATE_DIR:-/var/lib/factory-cloud}"
CONFIG_DIR="${CONFIG_DIR:-/etc/factory-cloud}"
APPS="${APPS:-obrasignal}"
PREPARE_WORKSPACES="${PREPARE_WORKSPACES:-1}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "install.sh must run as root on the isolated Factory Cloud host" >&2
  exit 2
fi

getent group factory-cloud >/dev/null || groupadd --system factory-cloud
id -u factory-cloud-control >/dev/null 2>&1 || useradd --system --home-dir /nonexistent --no-create-home --shell /usr/sbin/nologin --gid factory-cloud factory-cloud-control

# setgid keeps SQLite/WAL/SHM files on the shared metadata group even when an
# isolated app user creates them. Service UMask=0007 keeps them group-writable.
install -d -o factory-cloud-control -g factory-cloud -m 2770 "${STATE_DIR}"
install -d -o root -g factory-cloud -m 0750 "${CONFIG_DIR}" "${CONFIG_DIR}/apps"
install -m 0644 "${REPO_DIR}/factory_cloud/runtime/systemd/factory-cloud-control.service" /etc/systemd/system/factory-cloud-control.service
install -m 0644 "${REPO_DIR}/factory_cloud/runtime/systemd/factory-cloud-app@.service" /etc/systemd/system/factory-cloud-app@.service
install -m 0644 "${REPO_DIR}/factory_cloud/runtime/systemd/factory-cloud.target" /etc/systemd/system/factory-cloud.target

for app in ${APPS}; do
  user="factory-cloud-${app}"
  getent group "${user}" >/dev/null || groupadd --system "${user}"
  if ! id -u "${user}" >/dev/null 2>&1; then
    useradd --system --home-dir /nonexistent --no-create-home --shell /usr/sbin/nologin --gid "${user}" --groups factory-cloud "${user}"
  else
    usermod -a -G factory-cloud "${user}"
  fi

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

# ObraSignal has a concrete repository-safe verification adapter. Prepare only
# its isolated development checkout; K3 is intentionally not provisioned here.
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
