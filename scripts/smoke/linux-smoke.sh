#!/usr/bin/env bash
# Smoke test for the Linux bundles (.deb and .AppImage).
#
# Usage: linux-smoke.sh <path-to-bundle-dir>
# The bundle dir is typically src-tauri/target/release/bundle and contains
# the `deb/` and `appimage/` subfolders produced by `tauri build`.

set -euo pipefail

BUNDLE_DIR="${1:?Usage: linux-smoke.sh <bundle-dir>}"
DEB_DIR="$BUNDLE_DIR/deb"
APPIMAGE_DIR="$BUNDLE_DIR/appimage"

echo "== Linux installer smoke test =="
echo "Bundle dir: $BUNDLE_DIR"

# --- .deb ---------------------------------------------------------------
echo
echo "-- Checking .deb bundle --"
DEB="$(find "$DEB_DIR" -maxdepth 1 -name '*.deb' -print -quit 2>/dev/null || true)"
if [ -z "$DEB" ]; then
  echo "FAIL: no .deb found under $DEB_DIR"
  exit 1
fi
echo "Found deb: $DEB"
test -s "$DEB" || { echo "FAIL: deb is empty"; exit 1; }
dpkg-deb --info "$DEB" >/dev/null || { echo "FAIL: dpkg-deb could not read $DEB"; exit 1; }
PACKAGE="$(dpkg-deb --field "$DEB" Package)"
echo "Package: $PACKAGE"

# Install the .deb so we can actually launch the installed binary.
echo "Installing $DEB ..."
sudo dpkg -i "$DEB" >/dev/null 2>&1 || sudo apt-get -f install -y >/dev/null 2>&1

# Locate the installed main binary from the package file list.
BIN="$(dpkg -L "$PACKAGE" 2>/dev/null | grep -E '/usr/(local/)?bin/' | head -n1 || true)"
if [ -z "$BIN" ] || [ ! -x "$BIN" ]; then
  echo "FAIL: no executable found in package '$PACKAGE' via dpkg -L"
  exit 1
fi
echo "Installed binary: $BIN"

# --- .AppImage ----------------------------------------------------------
echo
echo "-- Checking .AppImage bundle --"
APPIMAGE="$(find "$APPIMAGE_DIR" -maxdepth 1 -name '*.AppImage' -print -quit 2>/dev/null || true)"
if [ -z "$APPIMAGE" ]; then
  echo "FAIL: no .AppImage found under $APPIMAGE_DIR"
  exit 1
fi
echo "Found AppImage: $APPIMAGE"
test -s "$APPIMAGE" || { echo "FAIL: AppImage is empty"; exit 1; }
chmod +x "$APPIMAGE"
# AppImage runtime self-version check (does not need a display or FUSE).
"$APPIMAGE" --appimage-version >/dev/null 2>&1 || {
  echo "WARN: AppImage --appimage-version failed (FUSE missing?); continuing"
}

# --- Launch the app briefly under xvfb ---------------------------------
echo
echo "-- Launching installed app headless --"
if command -v xvfb-run >/dev/null 2>&1; then
  LOG="$(mktemp)"
  ENV_FLAGS="env GDK_BACKEND=x11 LIBGL_ALWAYS_SOFTWARE=1 WEBKIT_DISABLE_COMPOSITING_MODE=1 WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS=1"
  if command -v dbus-run-session >/dev/null 2>&1; then
    xvfb-run -a dbus-run-session -- $ENV_FLAGS timeout 20 "$BIN" >"$LOG" 2>&1 &
  else
    xvfb-run -a $ENV_FLAGS timeout 20 "$BIN" >"$LOG" 2>&1 &
  fi
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
else
  echo "SKIP: xvfb-run not installed, skipping launch check"
fi

echo
echo "== Linux smoke test passed =="
