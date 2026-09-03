#!/usr/bin/env bash
set -euo pipefail

# Prepare only the isolated ObraSignal development workspace used by Factory Cloud.
# This script never touches production, merges branches, or activates providers.

CONTROL_REPO="${CONTROL_REPO:-/opt/factory-cloud/current}"
WORKSPACE="${OBRASIGNAL_WORKSPACE:-/srv/factory-cloud/apps/obrasignal}"
REPO_URL="${OBRASIGNAL_REPO_URL:-https://github.com/MarcosTaz/Obrasignal.git}"
APP_USER="factory-cloud-obrasignal"

if [[ "${EUID}" -ne 0 ]]; then
  echo "prepare-obrasignal-workspace.sh must run as root on the isolated host" >&2
  exit 2
fi
if ! id -u "${APP_USER}" >/dev/null 2>&1; then
  echo "missing ${APP_USER}; run install.sh user provisioning first" >&2
  exit 3
fi

SOURCE_LINE="$(python3 - "${CONTROL_REPO}/factory_cloud/apps.json" <<'PY'
import json
import re
import sys
from pathlib import Path

sha_re = re.compile(r"^[0-9a-f]{40}$")
payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
for app in payload.get("applications", []):
    if app.get("app_id") != "obrasignal":
        continue
    canonical = app.get("source_truth") or {}
    canonical_repo = str(canonical.get("repository") or "").strip()
    if canonical.get("verified") is not True or not canonical_repo:
        raise SystemExit("ObraSignal canonical source truth is not verified")

    execution = app.get("execution_source") or {}
    if execution:
        repo = str(execution.get("repository") or "").strip()
        branch = str(execution.get("branch") or "").strip()
        head = str(execution.get("head") or "").strip()
        if execution.get("verified") is not True:
            raise SystemExit("ObraSignal execution source is not verified")
        if repo != canonical_repo:
            raise SystemExit("ObraSignal execution source repository differs from canonical repository")
    else:
        branch = str(canonical.get("canonical_branch") or "").strip()
        head = str(canonical.get("canonical_head") or "").strip()

    if not branch or not sha_re.fullmatch(head):
        raise SystemExit("ObraSignal execution source branch/head is incomplete")
    print(f"{branch}\t{head}")
    break
else:
    raise SystemExit("ObraSignal missing from Factory Cloud registry")
PY
)"
IFS=$'\t' read -r EXECUTION_BRANCH EXPECTED_HEAD <<< "${SOURCE_LINE}"

install -d -o root -g root -m 0755 /srv/factory-cloud /srv/factory-cloud/apps

if [[ -e "${WORKSPACE}" && ! -d "${WORKSPACE}/.git" ]]; then
  echo "${WORKSPACE} exists but is not a git workspace" >&2
  exit 4
fi

if [[ ! -d "${WORKSPACE}/.git" ]]; then
  runuser -u "${APP_USER}" -- git clone --no-checkout "${REPO_URL}" "${WORKSPACE}"
else
  dirty="$(runuser -u "${APP_USER}" -- git -C "${WORKSPACE}" status --porcelain)"
  if [[ -n "${dirty}" ]]; then
    echo "${WORKSPACE} has local changes; refusing to move its HEAD" >&2
    exit 5
  fi
fi

runuser -u "${APP_USER}" -- git -C "${WORKSPACE}" fetch origin "${EXECUTION_BRANCH}"
if ! runuser -u "${APP_USER}" -- git -C "${WORKSPACE}" cat-file -e "${EXPECTED_HEAD}^{commit}"; then
  echo "registered execution head ${EXPECTED_HEAD} is unavailable in the workspace" >&2
  exit 6
fi
runuser -u "${APP_USER}" -- git -C "${WORKSPACE}" checkout --detach "${EXPECTED_HEAD}"
OBSERVED_HEAD="$(runuser -u "${APP_USER}" -- git -C "${WORKSPACE}" rev-parse HEAD)"
if [[ "${OBSERVED_HEAD}" != "${EXPECTED_HEAD}" ]]; then
  echo "workspace execution-head mismatch after checkout" >&2
  exit 7
fi

echo "ObraSignal Factory Cloud workspace prepared at ${EXECUTION_BRANCH}@${OBSERVED_HEAD}"
