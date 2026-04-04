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

# Step 2: Codesign
echo ">>> Code signing..."
codesign --deep --force --verify --verbose \
    --sign "$APPLE_SIGNING_IDENTITY" \
    --options runtime \
    "$APP_BUNDLE"

codesign --verify --verbose "$APP_BUNDLE"
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

# Step 5: Staple
echo ">>> Stapling notarization ticket..."
xcrun stapler staple "$DMG_PATH"

echo ""
echo "=== macOS build complete ==="
echo "DMG: $DMG_PATH"
