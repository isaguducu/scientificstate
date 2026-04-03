"""
ScientificState Module CLI

Usage:
    python -m src.cli.module_cli list
    python -m src.cli.module_cli search <query>
    python -m src.cli.module_cli install <domain_id>
    python -m src.cli.module_cli package <path> [--key <private_key_path>]
    python -m src.cli.module_cli publish <path> [--key <private_key_path>] [--portal <url>]
    python -m src.cli.module_cli revoke <domain_id> <version> <reason>

All commands communicate with the local daemon at http://127.0.0.1:9473.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

_DAEMON_URL = "http://127.0.0.1:9473"
_DEFAULT_PORTAL_URL = "https://scientificstate.org/api/modules/publish"


def _daemon_get(path: str) -> dict | list:
    """HTTP GET to daemon."""
    url = f"{_DAEMON_URL}{path}"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        print(f"Error {e.code}: {body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Cannot reach daemon at {_DAEMON_URL}: {e.reason}", file=sys.stderr)
        sys.exit(1)


def _daemon_post(path: str, body: dict) -> dict:
    """HTTP POST to daemon."""
    url = f"{_DAEMON_URL}{path}"
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        resp_body = e.read().decode() if e.fp else ""
        print(f"Error {e.code}: {resp_body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Cannot reach daemon at {_DAEMON_URL}: {e.reason}", file=sys.stderr)
        sys.exit(1)


def cmd_list(_args: argparse.Namespace) -> None:
    """List installed modules."""
    modules = _daemon_get("/modules")
    if not modules:
        print("No modules installed.")
        return
    # Table format
    print(f"{'DOMAIN_ID':<30} {'VERSION':<12} {'INSTALL_PATH'}")
    print("-" * 80)
    for m in modules:
        print(f"{m['domain_id']:<30} {m['version']:<12} {m.get('install_path', '')}")


def cmd_search(args: argparse.Namespace) -> None:
    """Search modules by keyword."""
    params = f"?q={args.query}" if args.query else ""
    results = _daemon_get(f"/modules/search{params}")
    if not results:
        print("No modules found.")
        return
    print(f"{'DOMAIN_ID':<30} {'VERSION':<12} {'INSTALL_PATH'}")
    print("-" * 80)
    for m in results:
        print(f"{m['domain_id']:<30} {m['version']:<12} {m.get('install_path', '')}")


def cmd_install(args: argparse.Namespace) -> None:
    """Install a module (placeholder — requires manifest/package/key)."""
    print(f"Install '{args.name}': requires manifest, package, and public key.")
    print("Use the Desktop Module Store UI for interactive installation.")


def cmd_package(args: argparse.Namespace) -> None:
    """Package a local module."""
    body: dict = {"source_path": args.path}
    if args.key:
        body["private_key_path"] = args.key
    result = _daemon_post("/modules/package", body)
    print(f"Tarball:    {result.get('tarball_path')}")
    print(f"Hash:       {result.get('tarball_hash')}")
    print(f"Manifest:   {result.get('manifest_path')}")
    if result.get("signature"):
        print(f"Signature:  {result['signature'][:40]}...")


def cmd_publish(args: argparse.Namespace) -> None:
    """Package + publish to portal."""
    # Step 1: Package locally
    body: dict = {"source_path": args.path}
    if args.key:
        body["private_key_path"] = args.key
    result = _daemon_post("/modules/package", body)

    tarball_path = result.get("tarball_path")
    manifest_path = result.get("manifest_path")
    if not tarball_path or not manifest_path:
        print("Package step failed.", file=sys.stderr)
        sys.exit(1)

    # Step 2: Publish to portal
    portal_url = args.portal or _DEFAULT_PORTAL_URL
    print(f"Package ready. Publishing to {portal_url}...")
    print(f"  tarball:   {tarball_path}")
    print(f"  manifest:  {manifest_path}")
    print(f"  hash:      {result.get('tarball_hash')}")

    # Portal publish would upload the tarball + manifest
    # For now, print instructions
    print("\nPortal publish is not yet implemented in CLI.")
    print("Upload the tarball and manifest manually or use the Desktop UI.")


def cmd_revoke(args: argparse.Namespace) -> None:
    """Revoke a module version."""
    result = _daemon_post("/modules/revoke", {
        "domain_id": args.domain_id,
        "version": args.version,
        "reason": args.reason,
    })
    if result.get("success"):
        print(f"Revoked: {args.domain_id}@{args.version}")
    else:
        print("Revocation failed.", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="scientificstate module",
        description="ScientificState Module Management CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # list
    sub.add_parser("list", help="List installed modules")

    # search
    p_search = sub.add_parser("search", help="Search modules")
    p_search.add_argument("query", help="Search query string")

    # install
    p_install = sub.add_parser("install", help="Install a module")
    p_install.add_argument("name", help="Module domain_id to install")

    # package
    p_package = sub.add_parser("package", help="Package a local module")
    p_package.add_argument("path", help="Path to module directory")
    p_package.add_argument("--key", help="Path to Ed25519 private key for signing")

    # publish
    p_publish = sub.add_parser("publish", help="Package + publish to portal")
    p_publish.add_argument("path", help="Path to module directory")
    p_publish.add_argument("--key", help="Path to Ed25519 private key for signing")
    p_publish.add_argument("--portal", help=f"Portal URL (default: {_DEFAULT_PORTAL_URL})")

    # revoke
    p_revoke = sub.add_parser("revoke", help="Revoke a module version")
    p_revoke.add_argument("domain_id", help="Module domain_id")
    p_revoke.add_argument("version", help="Version to revoke")
    p_revoke.add_argument("reason", help="Revocation reason")

    args = parser.parse_args()

    handlers = {
        "list": cmd_list,
        "search": cmd_search,
        "install": cmd_install,
        "package": cmd_package,
        "publish": cmd_publish,
        "revoke": cmd_revoke,
    }
    handlers[args.command](args)


if __name__ == "__main__":
    main()
