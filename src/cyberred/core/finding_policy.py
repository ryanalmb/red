"""Deterministic finding validation and severity policy helpers."""

from __future__ import annotations

import json
from typing import Any, Mapping

_SEVERITY_ORDER = ("info", "low", "medium", "high", "critical")
_SEVERITY_RANK = {name: idx for idx, name in enumerate(_SEVERITY_ORDER)}

_HARD_NEGATIVE_MARKERS = (
    "traceback",
    "eoferror",
    "segmentation fault",
    "fatal:",
    "command not found",
    "permission denied",
    "access denied",
    "authentication failed",
    "bad authentication type",
    "rpc_s_access_denied",
    "execution timed out",
    "getpasswarning",
    "inappropriate ioctl for device",
)

_NEGATIVE_MARKERS = (
    "connection refused",
    "unable to connect",
    "failed to load module",
    "unknown command",
    "no route to host",
    "host seems down",
    "could not resolve host",
    "no results from search",
    "not vulnerable",
    "timed out",
)

_POSITIVE_MARKERS = (
    "session opened",
    "meterpreter session",
    "command shell session",
    "shell access obtained",
    "exploit success",
    "vulnerability confirmed",
    "valid credentials",
    "hash cracked",
    "password cracked",
    "open port",
    "host is up",
    "subdomain:",
    "dns ",
    "zone transfer",
    "waf detected",
    "os match",
    "domain admin",
    "asrep",
    "krb5tgs",
    "hashdump",
    "ntlm hash",
    "administrator:500",
    "secretsdump",
)

_DISCOVERY_TYPES = {
    "port_scan",
    "open_port",
    "service_detection",
    "subdomain",
    "dns_record",
    "banner_grab",
    "ssl_cert",
    "host_status",
    "os_detection",
    "web_tech",
    "directory",
    "file",
    "recon",
}


def _normalize_severity(value: Any) -> str:
    severity = str(value or "info").strip().lower()
    if severity not in _SEVERITY_RANK:
        return "info"
    return severity


def _cap_severity(value: str, cap: str) -> str:
    requested_rank = _SEVERITY_RANK[_normalize_severity(value)]
    cap_rank = _SEVERITY_RANK[_normalize_severity(cap)]
    return _SEVERITY_ORDER[min(requested_rank, cap_rank)]


def _safe_json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("{") and text.endswith("}"):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                return {}
    return {}


def _extract_execution(payload: Mapping[str, Any], evidence_obj: Mapping[str, Any]) -> dict[str, Any]:
    execution = payload.get("execution")
    if isinstance(execution, dict):
        return dict(execution)
    execution = evidence_obj.get("execution")
    if isinstance(execution, dict):
        return dict(execution)
    fallback: dict[str, Any] = {}
    for key in ("stdout", "stderr", "exit_code", "error_type", "command"):
        if key in evidence_obj:
            fallback[key] = evidence_obj.get(key)
    return fallback


def _combined_text(payload: Mapping[str, Any], evidence_obj: Mapping[str, Any], execution: Mapping[str, Any]) -> str:
    parts: list[str] = []
    for key in ("evidence",):
        value = payload.get(key)
        if isinstance(value, str):
            parts.append(value)
    for key in ("raw_evidence", "summary", "description", "stdout", "stderr"):
        value = evidence_obj.get(key)
        if isinstance(value, str):
            parts.append(value)
    for key in ("stdout", "stderr"):
        value = execution.get(key)
        if isinstance(value, str):
            parts.append(value)
    return "\n".join(part for part in parts if part).lower()


def _normalize_error_type(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if text.lower() in {"", "none", "null"}:
        return ""
    return text.upper()


def _normalize_exit_code(value: Any) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text and text.lstrip("-").isdigit():
            try:
                return int(text)
            except ValueError:
                return None
    return None


def assess_finding_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Assess a finding candidate and return deterministic policy metadata."""
    evidence_obj = _safe_json_dict(payload.get("evidence"))
    execution = _extract_execution(payload, evidence_obj)
    combined = _combined_text(payload, evidence_obj, execution)
    finding_type = str(
        payload.get("type")
        or payload.get("finding_type")
        or evidence_obj.get("type")
        or ""
    ).strip().lower()

    has_text = bool(combined.strip())
    stderr_text = str(execution.get("stderr") or "").lower()
    has_hard_negative = any(marker in combined or marker in stderr_text for marker in _HARD_NEGATIVE_MARKERS)
    has_negative = any(marker in combined for marker in _NEGATIVE_MARKERS)
    has_positive = any(marker in combined for marker in _POSITIVE_MARKERS)
    error_type = _normalize_error_type(execution.get("error_type"))
    exit_code = _normalize_exit_code(execution.get("exit_code"))
    has_exec_error = bool(error_type)
    success_raw = execution.get("success")
    if isinstance(success_raw, bool) and not success_raw:
        has_exec_error = True
    if isinstance(exit_code, int) and exit_code != 0:
        has_exec_error = True

    if has_hard_negative:
        outcome = "failed"
        reason = "hard_negative_signal_detected"
    elif has_exec_error:
        outcome = "failed"
        reason = "negative_or_execution_error"
    elif has_negative and has_positive:
        outcome = "attempted"
        reason = "conflicting_signal"
    elif has_positive:
        outcome = "validated"
        reason = "positive_indicators_present"
    elif finding_type in _DISCOVERY_TYPES and has_text and not has_negative:
        outcome = "validated"
        reason = "discovery_signal_detected"
    elif has_negative:
        outcome = "failed"
        reason = "negative_or_execution_error"
    elif has_text:
        outcome = "attempted"
        reason = "inconclusive_signal"
    else:
        outcome = "failed"
        reason = "empty_evidence"

    requested_severity = _normalize_severity(payload.get("severity"))
    if outcome == "validated":
        final_severity = requested_severity
        confidence = 0.88 if has_positive else 0.74
        quality = "high" if has_positive else "medium"
    elif outcome == "attempted":
        final_severity = _cap_severity(requested_severity, "medium")
        confidence = 0.52
        quality = "medium" if has_text else "low"
    else:
        final_severity = "info"
        confidence = 0.24
        quality = "low"

    return {
        "outcome_status": outcome,
        "severity": final_severity,
        "evidence_quality": quality,
        "validation_reason": reason,
        "validation_confidence": confidence,
    }
