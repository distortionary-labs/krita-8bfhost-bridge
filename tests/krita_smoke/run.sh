#!/usr/bin/env bash
# Run krita_8bfhost_bridge inside a real Krita, headless, with a throwaway profile.
#
# Needs: krita, xvfb-run, a C compiler and a dynamically linked 8bf-host in
# $EIGHTBF_HOST (release builds for Linux are static and cannot load native
# test filters). Your own Krita and 8bf-host settings are not touched: XDG_*
# and the 8bf-host config point into a temporary directory for the run.
set -euo pipefail

: "${EIGHTBF_HOST:?set EIGHTBF_HOST to a dynamically linked 8bf-host (cargo build)}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/krita_8bfhost_bridge-smoke.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

PYKRITA="$WORK/data/krita/pykrita"
PLUGINS="$WORK/plugins"
mkdir -p "$PYKRITA/k8bfsmoke" "$PLUGINS" "$WORK/config" "$WORK/cache"

cp -r "$ROOT/krita_8bfhost_bridge" "$ROOT/krita_8bfhost_bridge.desktop" "$PYKRITA/"
cp "$ROOT/tests/krita_smoke/harness.py" "$PYKRITA/k8bfsmoke/__init__.py"
cat > "$PYKRITA/k8bfsmoke.desktop" <<'EOF'
[Desktop Entry]
Type=Service
ServiceTypes=Krita/PythonPlugin
X-KDE-Library=k8bfsmoke
X-Python-2-Compatible=false
Name=krita_8bfhost_bridge smoke test
EOF
cat > "$WORK/config/kritarc" <<'EOF'
[python]
enable_krita_8bfhost_bridge=true
enable_k8bfsmoke=true

[General]
OpenGLRenderer=none
EOF

"${CC:-cc}" -shared -fPIC -O1 -o "$PLUGINS/smoke.so" "$ROOT/tests/fixtures/testfilter.c"
PYTHONPATH="$ROOT/tests" python3 -c '
import sys
from conftest import pipl_sidecar

with open(sys.argv[1], "wb") as handle:
    handle.write(pipl_sidecar("Smoke Invert", "Smoke Tests", "InvertMain"))
' "$PLUGINS/smoke.so.pipl"

export K8BF_SMOKE_REPORT="$WORK/report.json"
export K8BF_SMOKE_PLUGINS="$PLUGINS"
EIGHTBF_HOST="$(realpath "$EIGHTBF_HOST")"
export EIGHTBF_HOST
export EIGHTBF_HOST_CONFIG="$WORK/8bf-host.toml"
touch "$EIGHTBF_HOST_CONFIG"
XDG_DATA_HOME="$WORK/data" XDG_CONFIG_HOME="$WORK/config" XDG_CACHE_HOME="$WORK/cache" \
  QT_XCB_GL_INTEGRATION=none \
  timeout 300 xvfb-run -a -s "-screen 0 1280x1024x24" krita --nosplash >"$WORK/krita.log" 2>&1 || true

if [ ! -f "$K8BF_SMOKE_REPORT" ]; then
  echo "Krita did not produce a report. Last log lines:" >&2
  tail -20 "$WORK/krita.log" >&2
  exit 1
fi
python3 - "$K8BF_SMOKE_REPORT" <<'EOF'
import json, sys

report = json.load(open(sys.argv[1]))
for check in report["checks"]:
    print("%-4s %s" % ("ok" if check["ok"] else "FAIL", check["name"]))
    if not check["ok"]:
        print("     ", check["detail"])
if "error" in report:
    print(report["error"])
for message in report.get("messages", []):
    print("message:", message)
sys.exit(0 if report["ok"] else 1)
EOF
