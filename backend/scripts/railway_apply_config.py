#!/usr/bin/env python3
"""Apply this repo's Railway deploy settings to a service.

Why this exists
---------------
``backend/railway.json`` declares a ``preDeployCommand`` so migrations run as a
gated step before each release. That file is **not applied for CLI deploys**
(``railway up``): a service deployed that way comes up healthy with an
unmigrated database, and every endpoint returns 500 until something runs
alembic. Verified on a real deploy.

The Infrastructure-as-Code format cannot express it either — ``railway config
migrate`` emits ``preDeployCommand`` as an inert comment, and ``railway config
pull`` does not return it even when it is set and running. So the setting lives
on the Railway service itself, which makes it click-ops that no fresh service or
new environment inherits.

This script closes that gap: it applies the settings from railway.json to a
named service through Railway's API, so the configuration is reproducible from
the repository instead of remembered.

Usage (from backend/, with the Railway CLI linked to a project)::

    railway link -p <project> -e <environment>
    python scripts/railway_apply_config.py --service api

Re-running is safe; the mutation is idempotent.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

RAILWAY_JSON = Path(__file__).resolve().parent.parent / "railway.json"

# Railway's ServiceInstanceUpdateInput.preDeployCommand is [String!], but it
# wants the whole command as ONE element. Passing argv-style
# ["python", "-m", "alembic", ...] is rejected with "Invalid input".
# Kept on ONE line deliberately. Passing a multi-line document as a single argv
# element fails with HTTP 400 through the Windows railway.CMD shim.
MUTATION = (
    'mutation {{ serviceInstanceUpdate('
    'serviceId: "{service_id}", '
    'environmentId: "{environment_id}", '
    'input: {{ {fields} }}) }}'
)


def _run(args: list[str]) -> str:
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.exit(f"command failed: {' '.join(args)}\n{proc.stderr.strip()}")
    return proc.stdout


def _require_cli() -> str:
    cli = shutil.which("railway")
    if not cli:
        sys.exit("railway CLI not found. Install with: npm i -g @railway/cli")
    return cli


def _find_ids(cli: str, service_name: str) -> tuple[str, str]:
    """Pull the environment id and the target service's id from `railway status`."""
    raw = _run([cli, "status", "--json"])
    start = raw.find("{")
    if start < 0:
        sys.exit("could not parse `railway status --json` — is a project linked?")
    data = json.loads(raw[start:])

    env_id = None
    service_id = None

    def walk(node):
        nonlocal env_id, service_id
        if isinstance(node, dict):
            if node.get("name") == service_name and "id" in node and service_id is None:
                service_id = node["id"]
            for key, value in node.items():
                if key in ("environmentId", "environment_id") and isinstance(value, str):
                    env_id = env_id or value
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(data)

    if not env_id:
        env_id = data.get("environment", {}).get("id") if isinstance(data.get("environment"), dict) else None
    if not service_id:
        sys.exit(f"service {service_name!r} not found in the linked project")
    if not env_id:
        sys.exit("could not determine the environment id from `railway status --json`")
    return service_id, env_id


def _fields_from_railway_json() -> str:
    if not RAILWAY_JSON.is_file():
        sys.exit(f"{RAILWAY_JSON} not found")
    deploy = json.loads(RAILWAY_JSON.read_text(encoding="utf-8")).get("deploy", {})

    parts = []
    pre = deploy.get("preDeployCommand")
    if pre:
        # Accept a string or a list in railway.json; always send one element.
        command = pre if isinstance(pre, str) else " ".join(pre)
        parts.append(f"preDeployCommand: [{json.dumps(command)}]")
    if deploy.get("healthcheckPath"):
        parts.append(f"healthcheckPath: {json.dumps(deploy['healthcheckPath'])}")
    if deploy.get("healthcheckTimeout"):
        parts.append(f"healthcheckTimeout: {int(deploy['healthcheckTimeout'])}")

    if not parts:
        sys.exit("nothing to apply — railway.json has no deploy settings")
    return ", ".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--service", default="api", help="Railway service name (default: api)")
    parser.add_argument("--dry-run", action="store_true", help="print the mutation without sending it")
    args = parser.parse_args()

    cli = _require_cli()
    fields = _fields_from_railway_json()
    service_id, environment_id = _find_ids(cli, args.service)
    mutation = MUTATION.format(service_id=service_id, environment_id=environment_id, fields=fields)

    if args.dry_run:
        print(mutation)
        return

    out = _run([cli, "api", mutation])
    start = out.find("{")
    payload = json.loads(out[start:]) if start >= 0 else {}
    if payload.get("errors"):
        for err in payload["errors"]:
            print("ERROR:", err.get("message"), file=sys.stderr)
        sys.exit(1)

    print(f"applied deploy config to service {args.service!r}:")
    print("  " + fields.replace(", ", "\n  "))
    print("\nRedeploy for it to take effect:  railway up -s " + args.service)


if __name__ == "__main__":
    main()
