#!/usr/bin/env bash
# Install the plug-in into the local Krita profile and enable it.
#
# Usage: scripts/install.sh
#
# PYKRITA and KRITARC override where Krita keeps Python plug-ins and its
# settings file. The plug-in is enabled in kritarc only while Krita is
# closed, because Krita rewrites kritarc when it exits.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NAME="krita_8bfhost_bridge"

case "$(uname -s)" in
  Darwin)
    PYKRITA="${PYKRITA:-$HOME/Library/Application Support/krita/pykrita}"
    KRITARC="${KRITARC:-$HOME/Library/Preferences/kritarc}"
    ;;
  *)
    PYKRITA="${PYKRITA:-${XDG_DATA_HOME:-$HOME/.local/share}/krita/pykrita}"
    KRITARC="${KRITARC:-${XDG_CONFIG_HOME:-$HOME/.config}/kritarc}"
    ;;
esac

mkdir -p "$PYKRITA"
# Remove this install, and the one from before the package was renamed.
rm -rf "${PYKRITA:?}/$NAME" "$PYKRITA/$NAME.desktop" "$PYKRITA/krita8bf" "$PYKRITA/krita8bf.desktop"
cp -r "$ROOT/$NAME" "$PYKRITA/"
cp "$ROOT/$NAME.desktop" "$PYKRITA/"
find "$PYKRITA/$NAME" -name __pycache__ -type d -prune -exec rm -rf {} +
echo "Installed to $PYKRITA"

enable_hint="Enable \"Photoshop Filters (8bf)\" in Settings > Configure Krita > Python Plugin Manager, then restart Krita."

if pgrep -f '(^|/)\.?krita(-wrapped)?( |$)' >/dev/null 2>&1; then
  echo "Krita is running, so kritarc was left alone. Restart Krita to load the new code."
  echo "$enable_hint"
  exit 0
fi

if [ -f "$KRITARC" ]; then
  cp "$KRITARC" "$KRITARC.bak"
  # Set enable_<name>=true in [python], adding the key or the section as needed.
  awk -v key="enable_$NAME" '
    /^\[/ {
      if (in_python && !done) { print key "=true"; done = 1 }
      in_python = ($0 == "[python]")
    }
    in_python && index($0, key "=") == 1 { print key "=true"; done = 1; next }
    { print }
    END {
      if (in_python && !done) { print key "=true"; done = 1 }
      if (!done) { print ""; print "[python]"; print key "=true" }
    }
  ' "$KRITARC.bak" >"$KRITARC"
  echo "Enabled in $KRITARC (previous version saved as $KRITARC.bak)"
else
  printf '[python]\nenable_%s=true\n' "$NAME" >"$KRITARC"
  echo "Enabled in new $KRITARC"
fi
echo "Start Krita and find the filters under Tools > Scripts."
