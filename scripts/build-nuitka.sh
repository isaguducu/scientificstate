#!/usr/bin/env bash
# ScientificState — Nuitka daemon build
# Compiles Core/daemon into a standalone binary via Nuitka.
#
# Usage:  bash scripts/build-nuitka.sh
# Requires: pip install nuitka ordered-set (or uv pip install)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DAEMON_DIR="$PROJECT_ROOT/Core/daemon"
OUTPUT_DIR="$PROJECT_ROOT/dist/daemon"

echo "=== Nuitka build: ScientificState daemon ==="
echo "Source:  $DAEMON_DIR"
echo "Output:  $OUTPUT_DIR"

# Ensure Nuitka is available
if ! python -m nuitka --version >/dev/null 2>&1; then
    echo "ERROR: Nuitka not found. Install with: pip install nuitka ordered-set"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

# Record start time for benchmark
START_TS=$(date +%s)

# Run from DAEMON_DIR so that the `src` package is importable by Nuitka
cd "$DAEMON_DIR"

python -m nuitka \
    --standalone \
    --output-dir="$OUTPUT_DIR" \
    --include-package=src \
    --follow-imports \
    --assume-yes-for-downloads \
    "src/main.py"

END_TS=$(date +%s)
ELAPSED=$((END_TS - START_TS))

echo ""
echo "=== Nuitka build complete ==="
echo "Output:       $OUTPUT_DIR"
echo "Build time:   ${ELAPSED}s"

# Startup time benchmark
echo ""
echo "=== Startup time benchmark ==="
if [ -f "$OUTPUT_DIR/main.dist/main" ]; then
    BINARY="$OUTPUT_DIR/main.dist/main"
elif [ -f "$OUTPUT_DIR/main.dist/main.exe" ]; then
    BINARY="$OUTPUT_DIR/main.dist/main.exe"
else
    echo "WARN: Could not locate compiled binary for startup benchmark."
    exit 0
fi

START_BENCH=$(python -c "import time; print(time.time())")
timeout 5 "$BINARY" --help 2>/dev/null || true
END_BENCH=$(python -c "import time; print(time.time())")
STARTUP=$(python -c "print(f'{$END_BENCH - $START_BENCH:.3f}')")
echo "Startup time: ${STARTUP}s"
