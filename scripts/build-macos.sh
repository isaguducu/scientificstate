#!/usr/bin/env bash
# ScientificState — macOS build, codesign, notarize
#
# Usage:  bash scripts/build-macos.sh
#
# Required env vars:
#   APPLE_SIGNING_IDENTITY  — Developer ID certificate name
#   APPLE_ID                — Apple ID email
#   APPLE_TEAM_ID           — Team identifier
#   APPLE_APP_PASSWORD      — App-specific password for notarytool
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DESKTOP_DIR="$PROJECT_ROOT/Desktop"

echo "=== macOS build: ScientificState Desktop ==="

# Validate required env vars
for var in APPLE_SIGNING_IDENTITY APPLE_ID APPLE_TEAM_ID APPLE_APP_PASSWORD; do
    if [ -z "${!var:-}" ]; then
        echo "ERROR: $var is not set."
        exit 1
    fi
done

cd "$DESKTOP_DIR"

DAEMON_DIR="$PROJECT_ROOT/Core/daemon"
ENTITLEMENTS="$DESKTOP_DIR/src-tauri/entitlements.plist"

# Step 0: Build daemon sidecar binary (PyInstaller one-file)
echo ">>> Building daemon sidecar binary..."
if [ -f "$DAEMON_DIR/pyproject.toml" ]; then
    cd "$DAEMON_DIR"
    if command -v pyinstaller >/dev/null 2>&1; then
        pyinstaller --onefile --name scientificstate-daemon \
            --distpath "$DESKTOP_DIR/src-tauri/" \
            src/main.py
    else
        echo "WARN: pyinstaller not found — building with uv/shiv fallback"
        uv build --wheel --out-dir "$DESKTOP_DIR/src-tauri/"
    fi
    cd "$DESKTOP_DIR"
fi

# Step 1: Tauri build (universal binary)
echo ">>> Building Tauri universal binary..."
npm run tauri build -- --target universal-apple-darwin

# Locate the .app bundle
APP_BUNDLE=$(find "$DESKTOP_DIR/src-tauri/target/universal-apple-darwin/release/bundle/macos" -name "*.app" -maxdepth 1 | head -n 1)
if [ -z "$APP_BUNDLE" ]; then
    echo "ERROR: .app bundle not found."
    exit 1
fi
echo "App bundle: $APP_BUNDLE"

# Step 1.5: Bundle daemon sidecar into .app
echo ">>> Bundling daemon sidecar into .app..."
SIDECAR_BIN="$DESKTOP_DIR/src-tauri/scientificstate-daemon"
if [ -f "$SIDECAR_BIN" ]; then
    cp "$SIDECAR_BIN" "$APP_BUNDLE/Contents/MacOS/scientificstate-daemon"
    chmod +x "$APP_BUNDLE/Contents/MacOS/scientificstate-daemon"
    echo "Daemon sidecar bundled."
else
    echo "WARN: Daemon sidecar binary not found at $SIDECAR_BIN — skipping bundle."
fi

# Step 2: Codesign with entitlements and hardened runtime
echo ">>> Code signing..."
CODESIGN_ARGS=(
    --deep --force --verify --verbose
    --sign "$APPLE_SIGNING_IDENTITY"
    --options runtime
)
# Use entitlements plist if it exists
if [ -f "$ENTITLEMENTS" ]; then
    CODESIGN_ARGS+=(--entitlements "$ENTITLEMENTS")
    echo "Using entitlements: $ENTITLEMENTS"
fi

# Sign the sidecar binary first (inside-out signing)
if [ -f "$APP_BUNDLE/Contents/MacOS/scientificstate-daemon" ]; then
    echo ">>> Signing daemon sidecar..."
    codesign --force --verify --verbose \
        --sign "$APPLE_SIGNING_IDENTITY" \
        --options runtime \
        "$APP_BUNDLE/Contents/MacOS/scientificstate-daemon"
fi

# Sign the main app bundle
codesign "${CODESIGN_ARGS[@]}" "$APP_BUNDLE"

# Step 2.5: Verify signature
echo ">>> Verifying code signature..."
codesign --verify --verbose=2 "$APP_BUNDLE"
spctl --assess --type exec --verbose "$APP_BUNDLE" || echo "WARN: Gatekeeper assessment failed (expected for dev builds)."
echo "Codesign verified."

# Step 3: Create DMG
DMG_NAME="ScientificState-$(cat "$DESKTOP_DIR/package.json" | python -c 'import json,sys; print(json.load(sys.stdin)["version"])')-universal.dmg"
DMG_PATH="$DESKTOP_DIR/dist/$DMG_NAME"
mkdir -p "$DESKTOP_DIR/dist"

echo ">>> Creating DMG..."
hdiutil create -volname "ScientificState" \
    -srcfolder "$APP_BUNDLE" \
    -ov -format UDZO \
    "$DMG_PATH"

# Step 4: Notarize
echo ">>> Submitting for notarization..."
xcrun notarytool submit "$DMG_PATH" \
    --apple-id "$APPLE_ID" \
    --team-id "$APPLE_TEAM_ID" \
    --password "$APPLE_APP_PASSWORD" \
    --wait

# Step 5: Staple notarization ticket
echo ">>> Stapling notarization ticket..."
xcrun stapler staple "$DMG_PATH"

# Step 6: Validate stapled ticket
echo ">>> Validating stapled ticket..."
xcrun stapler validate "$DMG_PATH"

echo ""
echo "=== macOS build complete ==="
echo "DMG: $DMG_PATH"
echo "SHA-256: $(shasum -a 256 "$DMG_PATH" | cut -d ' ' -f 1)"
