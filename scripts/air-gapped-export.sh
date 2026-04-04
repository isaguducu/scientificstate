#!/bin/bash
# Air-gapped export — online registry snapshot → USB directory.
#
# Usage: air-gapped-export.sh <output-dir>
#
# Copies registry index, TUF metadata, trust chain, and packages
# (latest 2 versions per module) for offline transport.
#
# Produces MANIFEST.sha256 for mandatory integrity verification on import.
set -euo pipefail

OUTPUT_DIR="${1:?Usage: air-gapped-export.sh <output-dir>}"
REGISTRY_URL="${REGISTRY_URL:-http://127.0.0.1:9473}"

mkdir -p "$OUTPUT_DIR"/{registry,packages,tuf,trust}

echo "=== Exporting registry index ==="
curl -sf "$REGISTRY_URL/registry/index.json" > "$OUTPUT_DIR/registry/index.json" \
    || { echo "ERROR: Failed to fetch registry index"; exit 1; }
curl -sf "$REGISTRY_URL/registry/format-map.json" > "$OUTPUT_DIR/registry/format-map.json" \
    || echo '{}' > "$OUTPUT_DIR/registry/format-map.json"

echo "=== Exporting TUF metadata ==="
curl -sf "$REGISTRY_URL/registry/tuf/root.json" > "$OUTPUT_DIR/tuf/root.json" \
    || { echo "ERROR: Failed to fetch TUF root.json — trust chain incomplete"; exit 1; }
curl -sf "$REGISTRY_URL/registry/tuf/targets.json" > "$OUTPUT_DIR/tuf/targets.json" \
    || { echo "ERROR: Failed to fetch TUF targets.json — trust chain incomplete"; exit 1; }

echo "=== Exporting trust chain ==="
curl -sf "$REGISTRY_URL/registry/trust-chain.json" > "$OUTPUT_DIR/trust/trust-chain.json" \
    || echo "WARN: trust-chain.json not available (non-critical)"

echo "=== Pre-loading Ed25519 public key ==="
# Copy Ed25519 public key from local registry if available
LOCAL_REGISTRY="${HOME}/.scientificstate/registry"
if [ -f "$LOCAL_REGISTRY/trust/public_key.der" ]; then
    cp "$LOCAL_REGISTRY/trust/public_key.der" "$OUTPUT_DIR/trust/public_key.der"
    echo "Ed25519 public key pre-loaded from $LOCAL_REGISTRY/trust/public_key.der"
else
    echo "WARN: Ed25519 public key not found at $LOCAL_REGISTRY/trust/public_key.der"
    echo "      Air-gapped import will require manual key placement in trust/public_key.der"
fi

echo "=== Exporting packages (latest 2 versions) ==="
python3 -c "
import json, os, sys, urllib.request

index_path = '$OUTPUT_DIR/registry/index.json'
try:
    index = json.load(open(index_path))
except (json.JSONDecodeError, FileNotFoundError):
    print('ERROR: Cannot parse registry index')
    sys.exit(1)

pkg_count = 0
for pkg in index.get('packages', []):
    domain_id = pkg.get('domain_id', '')
    if not domain_id:
        continue
    for ver in pkg.get('versions', [])[:2]:
        version = ver.get('version', '')
        if not version:
            continue
        pkg_dir = f'$OUTPUT_DIR/packages/{domain_id}/v{version}'
        os.makedirs(pkg_dir, exist_ok=True)
        for f in ['manifest.json', 'package.tar.gz', 'checksum.sha256', 'signature.sig', 'sigstore.bundle.json']:
            url = f'$REGISTRY_URL/packages/{domain_id}/v{version}/{f}'
            try:
                urllib.request.urlretrieve(url, f'{pkg_dir}/{f}')
            except Exception:
                if f in ('manifest.json', 'package.tar.gz', 'signature.sig'):
                    print(f'ERROR: Failed to fetch required file {f} for {domain_id}/v{version}')
                    sys.exit(1)
        pkg_count += 1

print(f'Exported {pkg_count} package version(s)')
"

echo "=== Generating export manifest ==="
cd "$OUTPUT_DIR"
find . -type f ! -name 'MANIFEST.sha256' | sort | while IFS= read -r file; do
    shasum -a 256 "$file"
done > MANIFEST.sha256

echo "✅ Air-gapped export complete: $OUTPUT_DIR"
