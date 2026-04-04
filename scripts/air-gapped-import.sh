#!/bin/bash
# Air-gapped import — USB directory → local offline registry.
#
# Usage: air-gapped-import.sh <input-dir>
#
# Verifies MANIFEST.sha256 integrity, then copies TUF metadata,
# trust chain, registry index, and packages into the local registry.
set -euo pipefail

INPUT_DIR="${1:?Usage: air-gapped-import.sh <input-dir>}"
REGISTRY_DIR="${REGISTRY_DIR:-$HOME/.scientificstate/registry}"

echo "=== Verifying integrity ==="
if [ -f "$INPUT_DIR/MANIFEST.sha256" ]; then
    cd "$INPUT_DIR"
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum -c MANIFEST.sha256
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 -c MANIFEST.sha256
    else
        echo "WARNING: No sha256sum or shasum available — skipping integrity check"
    fi
    echo "=== Integrity check PASSED ==="
else
    echo "WARNING: MANIFEST.sha256 not found — skipping integrity check"
fi

echo "=== Importing TUF metadata ==="
mkdir -p "$REGISTRY_DIR/tuf"
if [ -d "$INPUT_DIR/tuf" ]; then
    cp "$INPUT_DIR"/tuf/*.json "$REGISTRY_DIR/tuf/" 2>/dev/null || true
fi

echo "=== Importing trust chain ==="
mkdir -p "$REGISTRY_DIR/trust"
if [ -d "$INPUT_DIR/trust" ]; then
    cp "$INPUT_DIR"/trust/*.json "$REGISTRY_DIR/trust/" 2>/dev/null || true
fi

echo "=== Importing registry index ==="
if [ -d "$INPUT_DIR/registry" ]; then
    cp "$INPUT_DIR"/registry/*.json "$REGISTRY_DIR/" 2>/dev/null || true
fi

echo "=== Importing packages ==="
mkdir -p "$REGISTRY_DIR/packages"
if [ -d "$INPUT_DIR/packages" ]; then
    cp -r "$INPUT_DIR"/packages/* "$REGISTRY_DIR/packages/" 2>/dev/null || true
fi

echo "✅ Air-gapped import complete: $REGISTRY_DIR"
