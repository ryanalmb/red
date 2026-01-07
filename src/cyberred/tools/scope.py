"""Scope Validator - Hard-Gate Deterministic Scope Validation.

This module implements the SAFETY-CRITICAL scope validator for Cyber-Red.
It enforces deterministic (code-based, not AI) scope validation to prevent
unauthorized attacks on out-of-scope targets.

Requirements:
- FR20: Hard-gate scope validation (deterministic)
- FR21: All scope checks logged to audit trail
- ERR6: Fail-closed on any error

Security Features:
- NFKC Unicode normalization to prevent homoglyph attacks
- Command injection detection (;, |, &&, ||, $(), `)
- Reserved IP blocking (loopback, link-local, multicast, broadcast)
- Fail-closed error handling (DENY on any error)

Usage:
    from cyberred.tools import ScopeValidator
    
    validator = ScopeValidator.from_file("scope.yaml")
    validator.validate(target="192.168.1.100", port=80, protocol="tcp")
    validator.validate(command="nmap -p 80 192.168.1.100")
"""

from __future__ import annotations

import logging
import re
import shlex
import unicodedata
from dataclasses import dataclass, field
from ipaddress import (
    IPv4Address,
    IPv4Network,
    IPv6Address,
    IPv6Network,
    ip_address,
    ip_network,
)
from pathlib import Path
from typing import Any, Optional, Union
from urllib.parse import urlparse

import structlog
import yaml

from cyberred.core.exceptions import ScopeViolationError

# Configure structlog to use stdlib logging for caplog compatibility
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

# Structured logger for audit trail
log = structlog.get_logger(__name__)

# Command injection patterns to detect
INJECTION_PATTERNS = [
    (r"(?<!['\"])[;](?!['\"])", "semicolon"),  # Unquoted semicolon
    (r"(?<!['\"])[|](?!['\"])", "pipe"),  # Unquoted pipe
    (r"&&", "and_chain"),  # AND chain
    (r"\|\|", "or_chain"),  # OR chain
    (r"\$\(", "command_substitution"),  # Command substitution
    (r"`", "backtick"),  # Backtick execution
    (r"\n", "newline"),  # Newline injection
]


@dataclass
class ScopeConfig:
    """Configuration for scope validation.

    Attributes:
        allowed_networks: List of allowed IP networks (CIDR or single IP).
        allowed_hostnames: List of allowed hostnames (exact or wildcard).
        allowed_ports: List of allowed ports or port ranges. None = all allowed.
        allowed_protocols: List of allowed protocols. None = all allowed.
        allow_private: Whether to allow RFC 1918 private IPs.
        allow_loopback: Whether to allow loopback addresses (default: False).
    """

    allowed_networks: list[Union[IPv4Network, IPv6Network]] = field(
        default_factory=list
    )
    allowed_hostnames: list[str] = field(default_factory=list)
    allowed_ports: Optional[list[Union[int, tuple[int, int]]]] = None
    allowed_protocols: Optional[list[str]] = None
    allow_private: bool = False
    allow_loopback: bool = False


class ScopeValidator:
    """Hard-gate deterministic scope validator.

    This validator is SAFETY-CRITICAL. It enforces scope boundaries
    to prevent unauthorized attacks on out-of-scope targets.

    All validations are:
    - Deterministic (code-based, not AI)
    - Fail-closed (deny on any error)
    - Logged to audit trail

    Attributes:
        config: The scope configuration.
    """

    def __init__(self, config: ScopeConfig) -> None:
        """Initialize ScopeValidator with configuration.

        Args:
            config: The scope configuration.

        Raises:
            ValueError: If config is invalid.
        """
        if not isinstance(config, ScopeConfig):
            raise ValueError("config must be a ScopeConfig instance")
        self.config = config

    @classmethod
    def from_config(cls, config_dict: dict[str, Any]) -> ScopeValidator:
        """Create ScopeValidator from configuration dictionary.

        Args:
            config_dict: Configuration dictionary with scope settings.

        Returns:
            ScopeValidator instance.

        Raises:
            ValueError: If config is empty, malformed, or invalid.
        """
        if not config_dict:
            raise ValueError("Configuration cannot be empty")

        # Handle nested 'scope' key
        if "scope" in config_dict:
            config_dict = config_dict["scope"]

        # Validate required fields
        allowed_targets = config_dict.get("allowed_targets")
        if allowed_targets is None:
            raise ValueError("allowed_targets is required in scope configuration")
        if not isinstance(allowed_targets, list):
            raise ValueError("allowed_targets must be a list")

        # Parse targets into networks and hostnames
        networks: list[Union[IPv4Network, IPv6Network]] = []
        hostnames: list[str] = []

        for target in allowed_targets:
            if not isinstance(target, str):
                raise ValueError(f"Invalid target: {target}")
            try:
                # Try parsing as network (includes single IPs)
                net = ip_network(target, strict=False)
                networks.append(net)
            except ValueError:
                # Not a valid IP/CIDR, treat as hostname
                hostnames.append(target.lower())

        # Parse ports
        allowed_ports: Optional[list[Union[int, tuple[int, int]]]] = None
        if "allowed_ports" in config_dict:
            ports_raw = config_dict["allowed_ports"]
            if ports_raw is not None:
                allowed_ports = []
                if not isinstance(ports_raw, list):
                    raise ValueError("allowed_ports must be a list")
                for port in ports_raw:
                    if isinstance(port, int):
                        allowed_ports.append(port)
                    elif isinstance(port, (list, tuple)) and len(port) == 2:
                        allowed_ports.append((int(port[0]), int(port[1])))
                    else:
                        raise ValueError(f"Invalid port specification: {port}")

        # Parse protocols
        allowed_protocols: Optional[list[str]] = None
        if "allowed_protocols" in config_dict:
            protocols_raw = config_dict["allowed_protocols"]
            if protocols_raw is not None:
                if not isinstance(protocols_raw, list):
                    raise ValueError("allowed_protocols must be a list")
                allowed_protocols = [p.lower() for p in protocols_raw]

        # Parse flags
        allow_private = config_dict.get("allow_private", False)
        allow_loopback = config_dict.get("allow_loopback", False)

        config = ScopeConfig(
            allowed_networks=networks,
            allowed_hostnames=hostnames,
            allowed_ports=allowed_ports,
            allowed_protocols=allowed_protocols,
            allow_private=allow_private,
            allow_loopback=allow_loopback,
        )

        return cls(config)

    @classmethod
    def from_file(cls, path: Union[str, Path]) -> ScopeValidator:
        """Create ScopeValidator from YAML file.

        Args:
            path: Path to YAML configuration file.

        Returns:
            ScopeValidator instance.

        Raises:
            FileNotFoundError: If file does not exist.
            ValueError: If file contains invalid configuration.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Scope file not found: {path}")

        with open(path) as f:
            config_dict = yaml.safe_load(f)

        return cls.from_config(config_dict)

    def _normalize_input(self, text: Optional[str]) -> str:
        """Apply NFKC normalization to prevent Unicode bypass attacks.

        Args:
            text: Input text to normalize.

        Returns:
            Normalized text.

        Raises:
            ScopeViolationError: If text contains null bytes or control chars.
        """
        if text is None:
            raise ScopeViolationError(
                target="None",
                command="",
                scope_rule="null_input",
                message="Target cannot be None (fail-closed)",
            )

        if not text.strip():
            raise ScopeViolationError(
                target="",
                command="",
                scope_rule="empty_input",
                message="Target cannot be empty (fail-closed)",
            )

        # Apply NFKC normalization
        normalized = unicodedata.normalize("NFKC", text)
        
        # Remove zero-width characters that may bypass validation
        # U+200B (zero-width space), U+200C (zero-width non-joiner), etc.
        zero_width_chars = "\u200b\u200c\u200d\u200e\u200f\ufeff"
        for zwc in zero_width_chars:
            normalized = normalized.replace(zwc, "")

        # Check for null bytes
        if "\x00" in normalized:
            raise ScopeViolationError(
                target=text,
                command="",
                scope_rule="null_byte",
                message="Null byte detected in input (fail-closed)",
            )

        # Check for control characters (except tab, newline, carriage return)
        for char in normalized:
            if ord(char) < 32 and char not in "\t\r":
                if char == "\n":
                    # Newline injection - blocked separately
                    continue
                raise ScopeViolationError(
                    target=text,
                    command="",
                    scope_rule="control_char",
                    message=f"Control character detected: U+{ord(char):04X}",
                )

        return normalized.strip()

    def _is_reserved(self, ip: Union[IPv4Address, IPv6Address]) -> bool:
        """Check if IP is reserved (always blocked).

        Reserved addresses that are ALWAYS blocked regardless of scope:
        - Loopback (127.0.0.0/8, ::1)
        - Link-local (169.254.0.0/16, fe80::/10)
        - Multicast (224.0.0.0/4, ff00::/8)
        - Broadcast (255.255.255.255)
        - Unspecified (0.0.0.0, ::)

        Args:
            ip: IP address to check.

        Returns:
            True if IP is reserved and should be blocked.
        """
        # Always block loopback (unless explicitly allowed, which is not recommended)
        if ip.is_loopback and not self.config.allow_loopback:
            return True

        # Always block link-local
        if ip.is_link_local:
            return True

        # Always block multicast
        if ip.is_multicast:
            return True

        # Always block unspecified
        if ip.is_unspecified:
            return True

        # Block private IPs if not allowed (but don't block documentation ranges)
        # IPv6 documentation range 2001:db8::/32 is NOT private, it's "reserved"
        # but we should allow it when explicitly in scope
        if not self.config.allow_private and ip.is_private:
            return True

        return False

    def _is_ip_in_scope(self, ip: Union[IPv4Address, IPv6Address]) -> bool:
        """Check if IP address is within allowed scope.

        Args:
            ip: IP address to check.

        Returns:
            True if IP is in scope.
        """
        try:
            if not self.config.allowed_networks:
                return False

            for network in self.config.allowed_networks:
                if ip in network:
                    return True
            return False
        except (TypeError, AttributeError):
            # Fail-closed on any error
            return False

    def _is_hostname_in_scope(self, hostname: str) -> bool:
        """Check if hostname is within allowed scope.

        Supports exact matches and wildcard patterns (*.example.com).

        Args:
            hostname: Hostname to check.

        Returns:
            True if hostname is in scope.
        """
        hostname = hostname.lower()

        for allowed in self.config.allowed_hostnames:
            if allowed.startswith("*."):
                # Wildcard match
                suffix = allowed[1:]  # Remove the leading "*"
                if hostname.endswith(suffix) or hostname == allowed[2:]:
                    return True
            elif hostname == allowed:
                # Exact match
                return True

        return False

    def _is_port_allowed(self, port: int) -> bool:
        """Check if port is allowed.

        Args:
            port: Port number to check.

        Returns:
            True if port is allowed (or no port restrictions).
        """
        if self.config.allowed_ports is None:
            return True  # No restrictions

        if not self.config.allowed_ports:
            return False  # Empty list = block all

        for allowed in self.config.allowed_ports:
            if isinstance(allowed, int):
                if port == allowed:
                    return True
            elif isinstance(allowed, tuple):
                start, end = allowed
                if start <= port <= end:
                    return True

        return False

    def _is_protocol_allowed(self, protocol: str) -> bool:
        """Check if protocol is allowed.

        Args:
            protocol: Protocol name to check (case-insensitive).

        Returns:
            True if protocol is allowed (or no protocol restrictions).
        """
        if self.config.allowed_protocols is None:
            return True  # No restrictions

        return protocol.lower() in self.config.allowed_protocols

    def _check_injection(self, command: str) -> None:
        """Check for command injection patterns.

        Uses a robust state machine to parse quotes and detect dangerous
        shell metacharacters outside of safe contexts.

        Args:
            command: Command string to check.

        Raises:
            ScopeViolationError: If injection pattern detected.
        """
        # 1. Validate quote balance with shlex
        try:
            shlex.split(command)
        except ValueError as e:
            raise ScopeViolationError(
                target="",
                command=command,
                scope_rule="parse_error",
                message=f"Command parsing failed (unbalanced quotes?): {e}",
            )

        # 2. State machine to check characters in context
        in_single_quote = False
        in_double_quote = False
        escaped = False

        for i, char in enumerate(command):
            # Handle escapes
            if escaped:
                escaped = False
                continue

            # Backslash handling
            if char == "\\":
                # Inside single quotes, backslash is literal (mostly), so it doesn't escape the next char
                # effectively. However, in this simple parser, if we are in single quotes,
                # we ignore everything anyway until the closing quote.
                # If NOT in single quotes, backslash escapes the next char.
                if not in_single_quote:
                    escaped = True
                continue

            # Handle quote toggling
            if char == "'" and not in_double_quote:
                in_single_quote = not in_single_quote
                continue
            elif char == '"' and not in_single_quote:
                in_double_quote = not in_double_quote
                continue

            # --- Safety Checks ---

            # Context 1: Single Quotes '...'
            # Everything is literal. Safe.
            if in_single_quote:
                continue

            # Context 2: Double Quotes "..."
            # Dangerous: ` (backtick), $ (substitution/variable)
            # Safe: ; | & (literal in double quotes)
            if in_double_quote:
                if char == "`":
                    raise ScopeViolationError(
                        target="",
                        command=command,
                        scope_rule="injection_backtick_double_quote",
                        message="Backtick execution detected in double quotes",
                    )
                if char == "$":
                    # We block all $ in double quotes to be safe against $(...) and $VAR
                    raise ScopeViolationError(
                        target="",
                        command=command,
                        scope_rule="injection_dollar_double_quote",
                        message="Variable/Command substitution ($) detected in double quotes",
                    )

            # Context 3: Unquoted
            # Dangerous: ; | & ` $ ( ) \n
            else:
                if char in ";|&`$()\n":
                    raise ScopeViolationError(
                        target="",
                        command=command,
                        scope_rule=f"injection_unquoted_{char}",
                        message=f"Command injection detected: unquoted '{char}'",
                    )

    def _parse_target_from_command(
        self, command: str
    ) -> tuple[Optional[str], Optional[int], Optional[str]]:
        """Extract target, port, and protocol from command string.

        Args:
            command: Command string to parse.

        Returns:
            Tuple of (target, port, protocol).
        """
        # Parse command into arguments
        try:
            args = shlex.split(command)
        except ValueError:
            return None, None, None

        target = None
        port = None
        protocol = None

        # Look for IP addresses, hostnames, URLs in arguments
        ip_pattern = re.compile(
            r"^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?:/\d{1,2})?|"
            r"[0-9a-fA-F:]+(?:/\d{1,3})?)$"
        )
        url_pattern = re.compile(r"^(https?|ftp|tcp|udp)://")

        i = 0
        while i < len(args):
            arg = args[i]

            # Skip flags that take no argument
            if arg.startswith("-") and len(arg) == 2 and arg not in ("-p", "-u"):
                i += 1
                continue
                
            # Skip flags that take an argument (like -c 4 in ping)
            if arg.startswith("-") and arg not in ("-p", "-u"):
                # Skip this flag and its argument
                if i + 1 < len(args) and not args[i + 1].startswith("-"):
                    # Check if next arg looks like a value (not IP/hostname)
                    next_arg = args[i + 1]
                    if next_arg.isdigit() or len(next_arg) <= 3:
                        i += 2
                        continue
                i += 1
                continue

            # Check for -p port flag
            if arg == "-p" and i + 1 < len(args):
                port_str = args[i + 1].split(",")[0]  # Take first port
                try:
                    port = int(port_str)
                except ValueError:
                    pass
                i += 2
                continue

            # Check for URL
            if url_pattern.match(arg):
                parsed = urlparse(arg)
                target = parsed.hostname
                if parsed.port:
                    port = parsed.port
                if parsed.scheme in ("tcp", "udp"):
                    protocol = parsed.scheme
                i += 1
                continue

            # Check for -u URL flag (sqlmap style)
            if arg == "-u" and i + 1 < len(args):
                url_arg = args[i + 1]
                if url_pattern.match(url_arg):
                    parsed = urlparse(url_arg)
                    target = parsed.hostname
                    if parsed.port:
                        port = parsed.port
                i += 2
                continue

            # Check for IP address or CIDR
            if ip_pattern.match(arg):
                target = arg
                i += 1
                continue

            # Check for hostname-like patterns (contains dot, no special chars)
            if "." in arg and not arg.startswith("-"):
                # Could be hostname or IP:port
                if ":" in arg and not arg.count(":") > 1:  # Not IPv6
                    host_part, port_part = arg.rsplit(":", 1)
                    target = host_part
                    try:
                        port = int(port_part)
                    except ValueError:
                        pass
                else:
                    target = arg
                i += 1
                continue

            i += 1

        return target, port, protocol

    def _log_validation(
        self, target: str, decision: str, reason: str, **extra: Any
    ) -> None:
        """Log validation decision to audit trail.

        Args:
            target: Target being validated.
            decision: ALLOW or DENY.
            reason: Reason for decision.
            **extra: Additional context fields.
        """
        log.info(
            "scope_validation",
            target=target,
            decision=decision,
            reason=reason,
            **extra,
        )

    def validate(
        self,
        target: Optional[str] = None,
        port: Optional[int] = None,
        protocol: Optional[str] = None,
        command: Optional[str] = None,
    ) -> bool:
        """Validate that target/command is within scope.

        This is the main entry point for scope validation. It validates
        targets against the configured scope and returns True if allowed.

        Args:
            target: Target IP address, hostname, or URL.
            port: Port number to validate.
            protocol: Protocol to validate (tcp, udp, icmp).
            command: Command string to parse and validate.

        Returns:
            True if target is in scope.

        Raises:
            ScopeViolationError: If target is out of scope or validation fails.
        """
        try:
            # If command is provided, extract target from it
            if command is not None:
                command = self._normalize_input(command)
                self._check_injection(command)
                cmd_target, cmd_port, cmd_protocol = self._parse_target_from_command(
                    command
                )
                if cmd_target:
                    target = cmd_target
                if cmd_port and port is None:
                    port = cmd_port
                if cmd_protocol and protocol is None:
                    protocol = cmd_protocol

            # Normalize target
            if target is not None:
                target = self._normalize_input(target)

            # Handle URL in target
            if target and (
                target.startswith("http://") or target.startswith("https://")
            ):
                parsed = urlparse(target)
                target = parsed.hostname
                if parsed.port and port is None:
                    port = parsed.port

            # Handle host:port format
            if target and ":" in target and target.count(":") == 1:
                host_part, port_part = target.rsplit(":", 1)
                try:
                    port = int(port_part)
                    target = host_part
                except ValueError:
                    pass

            # Validate target is provided
            if not target:
                raise ScopeViolationError(
                    target="",
                    command=command or "",
                    scope_rule="missing_target",
                    message="No target provided for validation",
                )

            # Try to parse as IP address
            is_ip = False
            ip_obj: Optional[Union[IPv4Address, IPv6Address]] = None
            try:
                # Handle CIDR notation by extracting base IP
                if "/" in target:
                    base_ip = target.split("/")[0]
                    ip_obj = ip_address(base_ip)
                else:
                    ip_obj = ip_address(target)
                is_ip = True
            except ValueError:
                is_ip = False

            # Validate IP addresses
            if is_ip and ip_obj:
                # Check reserved ranges (ALWAYS blocked)
                if self._is_reserved(ip_obj):
                    self._log_validation(
                        target, "DENY", "Reserved IP address", is_reserved=True
                    )
                    raise ScopeViolationError(
                        target=target,
                        command=command or "",
                        scope_rule="reserved_ip",
                        message=f"Reserved IP address: {target}",
                    )

                # Check if in allowed networks
                if not self._is_ip_in_scope(ip_obj):
                    self._log_validation(target, "DENY", "IP not in allowed networks")
                    raise ScopeViolationError(
                        target=target,
                        command=command or "",
                        scope_rule="ip_out_of_scope",
                        message=f"IP {target} not in allowed networks",
                    )

            # Validate hostnames
            elif not is_ip:  # pragma: no branch
                if not self._is_hostname_in_scope(target):
                    self._log_validation(target, "DENY", "Hostname not in scope")
                    raise ScopeViolationError(
                        target=target,
                        command=command or "",
                        scope_rule="hostname_out_of_scope",
                        message=f"Hostname {target} not in allowed list",
                    )

            # Validate port if provided
            if port is not None:
                if not self._is_port_allowed(port):
                    self._log_validation(
                        target, "DENY", f"Port {port} not allowed", port=port
                    )
                    raise ScopeViolationError(
                        target=target,
                        command=command or "",
                        scope_rule="port_blocked",
                        message=f"Port {port} not in allowed list",
                    )

            # Validate protocol if provided
            if protocol is not None:
                if not self._is_protocol_allowed(protocol):
                    self._log_validation(
                        target,
                        "DENY",
                        f"Protocol {protocol} not allowed",
                        protocol=protocol,
                    )
                    raise ScopeViolationError(
                        target=target,
                        command=command or "",
                        scope_rule="protocol_blocked",
                        message=f"Protocol {protocol} not in allowed list",
                    )

            # All checks passed
            self._log_validation(
                target,
                "ALLOW",
                "Target in scope",
                port=port,
                protocol=protocol,
            )
            return True

        except ScopeViolationError:
            # Re-raise scope violations
            raise
        except Exception as e:
            # Fail-closed on ANY unexpected error
            self._log_validation(
                target or "", "DENY", f"Validation error: {e}", error=str(e)
            )
            raise ScopeViolationError(
                target=target or "",
                command=command or "",
                scope_rule="validation_error",
                message=f"Scope validation failed (fail-closed): {e}",
            ) from e
