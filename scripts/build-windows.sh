#!/usr/bin/env bash
# ScientificState — Windows build (NSIS installer)
#
# Usage:  bash scripts/build-windows.sh
#
# This script is intended to run on Windows (via Git Bash / MSYS2) or in CI.
#
# Optional env vars:
#   WINDOWS_CERTIFICATE_PATH  — Path to .pfx code signing certificate
#   WINDOWS_CERTIFICATE_PASSWORD — Certificate password
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DESKTOP_DIR="$PROJECT_ROOT/Desktop"

echo "=== Windows build: ScientificState Desktop ==="

cd "$DESKTOP_DIR"

# Step 1: Tauri build (x86_64 MSVC target)
echo ">>> Building Tauri Windows installer..."
npm run tauri build -- --target x86_64-pc-windows-msvc

# Locate installer output
BUNDLE_DIR="$DESKTOP_DIR/src-tauri/target/x86_64-pc-windows-msvc/release/bundle"
NSIS_DIR="$BUNDLE_DIR/nsis"
MSI_DIR="$BUNDLE_DIR/msi"

INSTALLER=""
if [ -d "$NSIS_DIR" ]; then
    INSTALLER=$(find "$NSIS_DIR" -name "*.exe" -maxdepth 1 | head -n 1)
    echo "NSIS installer: $INSTALLER"
elif [ -d "$MSI_DIR" ]; then
    INSTALLER=$(find "$MSI_DIR" -name "*.msi" -maxdepth 1 | head -n 1)
    echo "MSI installer: $INSTALLER"
fi

if [ -z "$INSTALLER" ]; then
    echo "WARN: No installer output found in $BUNDLE_DIR"
    echo "Check Tauri build logs."
    exit 1
fi

# Step 2: Code signing (optional)
if [ -n "${WINDOWS_CERTIFICATE_PATH:-}" ] && [ -n "${WINDOWS_CERTIFICATE_PASSWORD:-}" ]; then
    echo ">>> Signing installer with certificate..."
    if command -v signtool.exe >/dev/null 2>&1; then
        signtool.exe sign \
            /f "$WINDOWS_CERTIFICATE_PATH" \
            /p "$WINDOWS_CERTIFICATE_PASSWORD" \
            /tr http://timestamp.digicert.com \
            /td sha256 \
            /fd sha256 \
            "$INSTALLER"
        echo "Installer signed."
    else
        echo "WARN: signtool.exe not found — skipping code signing."
    fi
else
    echo "SKIP: No WINDOWS_CERTIFICATE_PATH set — installer unsigned."
fi

# Copy to dist/
mkdir -p "$DESKTOP_DIR/dist"
cp "$INSTALLER" "$DESKTOP_DIR/dist/"

echo ""
echo "=== Windows build complete ==="
echo "Installer: $DESKTOP_DIR/dist/$(basename "$INSTALLER")"
