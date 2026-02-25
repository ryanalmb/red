"""Network ingress guard for Docker-published SSH services.

Applies deterministic DOCKER-USER iptables/ip6tables rules so the daemon can
re-harden SSH exposure on every startup (including post-reboot service starts).
"""

from __future__ import annotations

import ipaddress
import os
import shlex
import shutil
import subprocess
from typing import Any

import structlog


log = structlog.get_logger()


DEFAULT_SSH_INGRESS_ALLOW_V4 = (
    "127.0.0.0/8",
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
)
DEFAULT_SSH_INGRESS_ALLOW_V6 = ("::1/128",)


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _parse_port(value: str | None, default: int) -> int:
    if not value:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    if parsed < 1 or parsed > 65535:
        return default
    return parsed


def _parse_cidrs(raw: str | None, *, version: int, default: tuple[str, ...]) -> list[str]:
    source = raw if raw is not None else ",".join(default)
    parsed: list[str] = []
    for token in source.split(","):
        candidate = token.strip()
        if not candidate:
            continue
        try:
            network = ipaddress.ip_network(candidate, strict=False)
        except ValueError:
            continue
        if network.version != version:
            continue
        parsed.append(str(network))
    if parsed:
        return parsed
    return list(default)


def _run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=False)


def _ensure_chain(binary: str, chain: str, errors: list[str]) -> None:
    create = _run_command([binary, "-N", chain])
    if create.returncode == 0:
        return
    stderr = (create.stderr or "").strip().lower()
    if "chain already exists" in stderr:
        return
    errors.append(f"{binary} create chain failed: {(create.stderr or '').strip()}")


def _delete_existing_port_rules(binary: str, chain: str, port: int, errors: list[str]) -> None:
    listing = _run_command([binary, "-S", chain])
    if listing.returncode != 0:
        errors.append(f"{binary} list chain failed: {(listing.stderr or '').strip()}")
        return

    for raw_line in listing.stdout.splitlines():
        line = raw_line.strip()
        if not line.startswith(f"-A {chain} "):
            continue
        tokens = shlex.split(line)
        if len(tokens) < 4 or tokens[:2] != ["-A", chain]:
            continue
        if "-p" not in tokens or "--dport" not in tokens:
            continue
        try:
            proto = tokens[tokens.index("-p") + 1]
            dport = int(tokens[tokens.index("--dport") + 1])
        except (ValueError, IndexError):
            continue
        if proto != "tcp" or dport != port:
            continue
        remove = _run_command([binary, "-D", chain, *tokens[2:]])
        if remove.returncode != 0:
            errors.append(
                f"{binary} remove rule failed: {(remove.stderr or '').strip()} ({line})"
            )


def _append_rule(binary: str, chain: str, rule: list[str], errors: list[str]) -> bool:
    command = [binary, "-A", chain, *rule]
    apply_result = _run_command(command)
    if apply_result.returncode != 0:
        errors.append(f"{binary} add rule failed: {(apply_result.stderr or '').strip()} ({' '.join(rule)})")
        return False
    return True


def ensure_ssh_ingress_guard() -> dict[str, Any]:
    """Apply deterministic SSH ingress filter rules on DOCKER-USER chain."""
    enabled = _parse_bool(
        os.getenv("CYBERRED_SSH_INGRESS_GUARD_ENABLED"),
        True,
    )
    if not enabled:
        return {"enabled": False}

    port = _parse_port(os.getenv("CYBERRED_SSH_INGRESS_GUARD_PORT"), 2222)
    allow_v4 = _parse_cidrs(
        os.getenv("CYBERRED_SSH_INGRESS_GUARD_ALLOW_V4"),
        version=4,
        default=DEFAULT_SSH_INGRESS_ALLOW_V4,
    )
    allow_v6 = _parse_cidrs(
        os.getenv("CYBERRED_SSH_INGRESS_GUARD_ALLOW_V6"),
        version=6,
        default=DEFAULT_SSH_INGRESS_ALLOW_V6,
    )

    errors: list[str] = []
    rules_added_v4 = 0
    rules_added_v6 = 0
    chain = "DOCKER-USER"

    iptables_path = shutil.which("iptables")
    if iptables_path:
        _ensure_chain(iptables_path, chain, errors)
        _delete_existing_port_rules(iptables_path, chain, port, errors)
        for cidr in allow_v4:
            rule = ["-s", cidr, "-p", "tcp", "-m", "tcp", "--dport", str(port), "-j", "RETURN"]
            if _append_rule(iptables_path, chain, rule, errors):
                rules_added_v4 += 1
        drop_rule = ["-p", "tcp", "-m", "tcp", "--dport", str(port), "-j", "DROP"]
        if _append_rule(iptables_path, chain, drop_rule, errors):
            rules_added_v4 += 1
    else:
        errors.append("iptables not found on PATH")

    ip6tables_path = shutil.which("ip6tables")
    if ip6tables_path:
        _ensure_chain(ip6tables_path, chain, errors)
        _delete_existing_port_rules(ip6tables_path, chain, port, errors)
        for cidr in allow_v6:
            rule = ["-s", cidr, "-p", "tcp", "-m", "tcp", "--dport", str(port), "-j", "RETURN"]
            if _append_rule(ip6tables_path, chain, rule, errors):
                rules_added_v6 += 1
        drop_rule = ["-p", "tcp", "-m", "tcp", "--dport", str(port), "-j", "DROP"]
        if _append_rule(ip6tables_path, chain, drop_rule, errors):
            rules_added_v6 += 1
    else:
        errors.append("ip6tables not found on PATH")

    result: dict[str, Any] = {
        "enabled": True,
        "port": port,
        "allow_v4": allow_v4,
        "allow_v6": allow_v6,
        "rules_added_v4": rules_added_v4,
        "rules_added_v6": rules_added_v6,
        "errors": errors,
    }

    if errors:
        log.warning("ssh_ingress_guard_partial_failure", **result)
    else:
        log.info("ssh_ingress_guard_applied", **result)
    return result
