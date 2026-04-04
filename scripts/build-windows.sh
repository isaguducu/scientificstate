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

DAEMON_DIR="$PROJECT_ROOT/Core/daemon"

cd "$DESKTOP_DIR"

# Step 0: Ensure WebView2 bootstrapper is available
WEBVIEW2_URL="https://go.microsoft.com/fwlink/p/?LinkId=2124703"
WEBVIEW2_DIR="$DESKTOP_DIR/src-tauri/webview2"
if [ ! -f "$WEBVIEW2_DIR/MicrosoftEdgeWebview2Setup.exe" ]; then
    echo ">>> Downloading WebView2 bootstrapper..."
    mkdir -p "$WEBVIEW2_DIR"
    if command -v curl >/dev/null 2>&1; then
        curl -L -o "$WEBVIEW2_DIR/MicrosoftEdgeWebview2Setup.exe" "$WEBVIEW2_URL" || \
            echo "WARN: WebView2 download failed — Tauri will use embedded installer."
    elif command -v wget >/dev/null 2>&1; then
        wget -O "$WEBVIEW2_DIR/MicrosoftEdgeWebview2Setup.exe" "$WEBVIEW2_URL" || \
            echo "WARN: WebView2 download failed — Tauri will use embedded installer."
    else
        echo "WARN: Neither curl nor wget available — skipping WebView2 download."
    fi
fi

# Step 0.5: Build daemon sidecar binary (PyInstaller one-file)
echo ">>> Building daemon sidecar binary..."
if [ -f "$DAEMON_DIR/pyproject.toml" ]; then
    cd "$DAEMON_DIR"
    if command -v pyinstaller >/dev/null 2>&1; then
        pyinstaller --onefile --name scientificstate-daemon \
            --distpath "$DESKTOP_DIR/src-tauri/" \
            src/main.py
    else
        echo "WARN: pyinstaller not found — daemon sidecar will not be bundled."
    fi
    cd "$DESKTOP_DIR"
fi

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

# Step 2: Code signing (optional — supports signtool.exe or osslsigncode)
if [ -n "${WINDOWS_CERTIFICATE_PATH:-}" ] && [ -n "${WINDOWS_CERTIFICATE_PASSWORD:-}" ]; then
    TIMESTAMP_URL="http://timestamp.digicert.com"
    echo ">>> Signing installer with certificate..."
    if command -v signtool.exe >/dev/null 2>&1; then
        signtool.exe sign \
            /f "$WINDOWS_CERTIFICATE_PATH" \
            /p "$WINDOWS_CERTIFICATE_PASSWORD" \
            /tr "$TIMESTAMP_URL" \
            /td sha256 \
            /fd sha256 \
            "$INSTALLER"
        echo "Installer signed (signtool)."
    elif command -v osslsigncode >/dev/null 2>&1; then
        echo ">>> signtool not found — falling back to osslsigncode..."
        SIGNED_INSTALLER="${INSTALLER%.exe}-signed.exe"
        osslsigncode sign \
            -pkcs12 "$WINDOWS_CERTIFICATE_PATH" \
            -pass "$WINDOWS_CERTIFICATE_PASSWORD" \
            -ts "$TIMESTAMP_URL" \
            -h sha256 \
            -in "$INSTALLER" \
            -out "$SIGNED_INSTALLER"
        mv "$SIGNED_INSTALLER" "$INSTALLER"
        echo "Installer signed (osslsigncode)."
    else
        echo "WARN: Neither signtool.exe nor osslsigncode found — skipping code signing."
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
