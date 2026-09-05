#!/usr/bin/env bash
# Smoke test for the macOS bundle (.dmg).
#
# Usage: macos-smoke.sh <path-to-bundle-dir>
# The bundle dir is typically src-tauri/target/release/bundle and contains
# the `dmg/` subfolder produced by `tauri build`.

set -euo pipefail

BUNDLE_DIR="${1:?Usage: macos-smoke.sh <bundle-dir>}"
DMG_DIR="$BUNDLE_DIR/dmg"

echo "== macOS installer smoke test =="
echo "Bundle dir: $BUNDLE_DIR"

DMG="$(find "$DMG_DIR" -maxdepth 1 -name '*.dmg' -print -quit 2>/dev/null || true)"
if [ -z "$DMG" ]; then
  echo "FAIL: no .dmg found under $DMG_DIR"
  exit 1
fi
echo "Found dmg: $DMG"
test -s "$DMG" || { echo "FAIL: dmg is empty"; exit 1; }

echo "Verifying dmg integrity (hdiutil verify) ..."
hdiutil verify "$DMG" || { echo "FAIL: hdiutil verify failed"; exit 1; }

MOUNT_POINT="$(mktemp -d)"
trap 'hdiutil detach "$MOUNT_POINT" -quiet >/dev/null 2>&1 || true; rm -rf "$MOUNT_POINT"' EXIT

echo "Attaching dmg ..."
hdiutil attach "$DMG" -mountpoint "$MOUNT_POINT" -nobrowse -quiet || {
  echo "FAIL: hdiutil attach failed"
  exit 1
}

APP="$(find "$MOUNT_POINT" -maxdepth 2 -name '*.app' -print -quit || true)"
if [ -z "$APP" ]; then
  echo "FAIL: no .app inside the dmg"
  exit 1
fi
echo "Found .app: $APP"

BIN="$(find "$APP/Contents/MacOS" -maxdepth 1 -type f -perm -111 -print -quit 2>/dev/null || true)"
if [ -z "$BIN" ]; then
  echo "FAIL: no executable inside $APP/Contents/MacOS"
  exit 1
fi
echo "Main binary: $BIN"

echo "Launching app binary for 8 seconds ..."
LOG="$(mktemp)"
"$BIN" >"$LOG" 2>&1 &
PID=$!
sleep 8
if kill -0 "$PID" 2>/dev/null; then
  echo "OK: app stayed alive for 8s"
  kill "$PID" 2>/dev/null || true
  wait "$PID" 2>/dev/null || true
else
  echo "FAIL: app exited early. Log:"
  cat "$LOG"
  rm -f "$LOG"
  exit 1
fi
rm -f "$LOG"

echo
echo "== macOS smoke test passed =="
