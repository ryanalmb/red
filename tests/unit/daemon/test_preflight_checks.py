"""Unit tests for individual pre-flight checks using dependency injection.

These tests use injected factory functions instead of mocking imports,
providing cleaner and more explicit test behavior.
"""

from collections import namedtuple
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

import pytest
import redis.sentinel

from cyberred.daemon.preflight import (
    DiskCheck,
    MemoryCheck,
    ScopeCheck,
    RedisCheck,
    LLMCheck,
    CertCheck,
    ResourceAdmissionCheck,
    CheckStatus,
    CheckPriority,
    CERT_MIN_HOURS_REMAINING,
)


# Named tuple to simulate disk usage result
DiskUsage = namedtuple("DiskUsage", ["total", "free"])

# Named tuple to simulate memory info
MemoryInfo = namedtuple("MemoryInfo", ["available"])


class TestDiskCheck:
    """Tests for DiskCheck with injected disk_usage function."""

    @pytest.mark.asyncio
    async def test_disk_check_pass(self) -> None:
        """DiskCheck should pass if > 10% free."""
        def mock_disk_usage(path: str) -> DiskUsage:
            return DiskUsage(total=100, free=20)
        
        check = DiskCheck(disk_usage_fn=mock_disk_usage)
        result = await check.execute({})
        
        assert result.status == CheckStatus.PASS
        assert "Disk space OK" in result.message
        assert result.details["free_percent"] == 20.0

    @pytest.mark.asyncio
    async def test_disk_check_warn(self) -> None:
        """DiskCheck should WARN (not FAIL) if <= 10% free (P1 threshold)."""
        def mock_disk_usage(path: str) -> DiskUsage:
            return DiskUsage(total=100, free=5)
        
        check = DiskCheck(disk_usage_fn=mock_disk_usage)
        result = await check.execute({})
        
        assert result.status == CheckStatus.WARN
        assert "Low disk space" in result.message

    @pytest.mark.asyncio
    async def test_disk_check_path_fallback(self) -> None:
        """DiskCheck should fallback to '/' if path doesn't exist."""
        def mock_disk_usage(path: str) -> DiskUsage:
            return DiskUsage(total=100, free=20)
        
        check = DiskCheck(disk_usage_fn=mock_disk_usage)
        result = await check.execute({"storage_path": "/nonexistent/path/that/does/not/exist"})
        
        assert result.status == CheckStatus.PASS
        assert result.details["path"] == "/"

    @pytest.mark.asyncio
    async def test_disk_check_exception(self) -> None:
        """DiskCheck should fail gracefully on exception."""
        def mock_disk_usage(path: str) -> DiskUsage:
            raise RuntimeError("Disk error")
        
        check = DiskCheck(disk_usage_fn=mock_disk_usage)
        result = await check.execute({})
        
        assert result.status == CheckStatus.FAIL
        assert "Disk check failed" in result.message


class TestMemoryCheck:
    """Tests for MemoryCheck with injected memory function."""

    @pytest.mark.asyncio
    async def test_memory_check_pass(self) -> None:
        """MemoryCheck should pass if > 1GB available."""
        def mock_memory() -> MemoryInfo:
            return MemoryInfo(available=2 * 1024**3)  # 2GB
        
        check = MemoryCheck(memory_fn=mock_memory)
        result = await check.execute({})
        
        assert result.status == CheckStatus.PASS
        assert "Memory OK" in result.message

    @pytest.mark.asyncio
    async def test_memory_check_warn(self) -> None:
        """MemoryCheck should WARN if <= 1GB available."""
        def mock_memory() -> MemoryInfo:
            return MemoryInfo(available=int(0.5 * 1024**3))  # 0.5GB
        
        check = MemoryCheck(memory_fn=mock_memory)
        result = await check.execute({})
        
        assert result.status == CheckStatus.WARN
        assert "Low memory" in result.message

    @pytest.mark.asyncio
    async def test_memory_check_exception(self) -> None:
        """MemoryCheck should fail gracefully on exception."""
        def mock_memory() -> MemoryInfo:
            raise RuntimeError("Memory read error")
        
        check = MemoryCheck(memory_fn=mock_memory)
        result = await check.execute({})
        
        assert result.status == CheckStatus.FAIL
        assert "Memory check failed" in result.message


class TestScopeCheck:
    """Tests for ScopeCheck with injected file functions."""

    @pytest.mark.asyncio
    async def test_scope_check_pass(self) -> None:
        """ScopeCheck should pass for valid scope file."""
        def mock_exists(path: str) -> bool:
            return True
        
        def mock_yaml_loader(path: str) -> dict:
            return {"targets": ["10.0.0.1"]}
        
        check = ScopeCheck(file_exists_fn=mock_exists, yaml_loader_fn=mock_yaml_loader)
        result = await check.execute({"scope_path": "/path/to/scope.yaml"})
        
        assert result.status == CheckStatus.PASS

    @pytest.mark.asyncio
    async def test_scope_check_file_not_found(self) -> None:
        """ScopeCheck should fail if file missing."""
        def mock_exists(path: str) -> bool:
            return False
        
        check = ScopeCheck(file_exists_fn=mock_exists)
        result = await check.execute({"scope_path": "/nonexistent.yaml"})
        
        assert result.status == CheckStatus.FAIL
        assert "not found" in result.message

    @pytest.mark.asyncio
    async def test_scope_check_missing_path(self) -> None:
        """ScopeCheck should fail if scope_path missing in config."""
        check = ScopeCheck()
        result = await check.execute({})
        
        assert result.status == CheckStatus.FAIL
        assert "missing 'scope_path'" in result.message

    @pytest.mark.asyncio
    async def test_scope_check_empty_file(self) -> None:
        """ScopeCheck should fail if file empty."""
        def mock_exists(path: str) -> bool:
            return True
        
        def mock_yaml_loader(path: str) -> dict:
            return None  # Empty YAML
        
        check = ScopeCheck(file_exists_fn=mock_exists, yaml_loader_fn=mock_yaml_loader)
        result = await check.execute({"scope_path": "/empty.yaml"})
        
        assert result.status == CheckStatus.FAIL
        assert "empty or invalid" in result.message

    @pytest.mark.asyncio
    async def test_scope_check_invalid_format(self) -> None:
        """ScopeCheck should fail if NOT a dictionary."""
        def mock_exists(path: str) -> bool:
            return True
        
        def mock_yaml_loader(path: str) -> list:
            return ["item1", "item2"]  # List, not dict
        
        check = ScopeCheck(file_exists_fn=mock_exists, yaml_loader_fn=mock_yaml_loader)
        result = await check.execute({"scope_path": "/list.yaml"})
        
        assert result.status == CheckStatus.FAIL
        assert "must be a YAML dictionary" in result.message

    @pytest.mark.asyncio
    async def test_scope_check_parse_error(self) -> None:
        """ScopeCheck should fail on YAML parse error."""
        def mock_exists(path: str) -> bool:
            return True
        
        def mock_yaml_loader(path: str) -> dict:
            raise ValueError("Invalid YAML syntax")
        
        check = ScopeCheck(file_exists_fn=mock_exists, yaml_loader_fn=mock_yaml_loader)
        result = await check.execute({"scope_path": "/broken.yaml"})
        
        assert result.status == CheckStatus.FAIL
        assert "Scope parse error" in result.message


class TestRedisCheck:
    """Tests for RedisCheck with injected Redis factories."""

    @pytest.mark.asyncio
    async def test_redis_check_pass(self) -> None:
        """RedisCheck should pass if reachable (standard mode)."""
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        
        def mock_redis_factory(url: str, **kwargs) -> MagicMock:
            return mock_client
        
        check = RedisCheck(redis_client_factory=mock_redis_factory)
        result = await check.execute({})
        
        assert result.status == CheckStatus.PASS
        assert "reachable" in result.message.lower()
        mock_client.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_redis_check_fail(self) -> None:
        """RedisCheck should fail if unreachable (standard mode)."""
        def mock_redis_factory(url: str, **kwargs) -> MagicMock:
            mock_client = MagicMock()
            mock_client.ping.side_effect = ConnectionError("Connection refused")
            return mock_client
        
        check = RedisCheck(redis_client_factory=mock_redis_factory)
        result = await check.execute({})
        
        assert result.status == CheckStatus.FAIL
        assert "Redis connection failed" in result.message

    @pytest.mark.asyncio
    async def test_redis_sentinel_pass(self) -> None:
        """RedisCheck should pass if Sentinel master is elected."""
        mock_master_client = MagicMock()
        mock_master_client.ping.return_value = True
        
        mock_sentinel = MagicMock()
        mock_sentinel.discover_master.return_value = ("192.168.1.1", 6379)
        mock_sentinel.master_for.return_value = mock_master_client
        
        def mock_sentinel_factory(hosts, **kwargs) -> MagicMock:
            return mock_sentinel
        
        check = RedisCheck(sentinel_factory=mock_sentinel_factory)
        result = await check.execute({
            "sentinel_hosts": [("sentinel1", 26379)],
            "sentinel_service": "mymaster"
        })
        
        assert result.status == CheckStatus.PASS
        assert "master" in result.message.lower()
        assert "192.168.1.1:6379" in result.message

    @pytest.mark.asyncio
    async def test_redis_sentinel_no_master(self) -> None:
        """RedisCheck should fail if Sentinel has no master elected."""
        mock_sentinel = MagicMock()
        mock_sentinel.discover_master.side_effect = redis.sentinel.MasterNotFoundError("No master")
        
        def mock_sentinel_factory(hosts, **kwargs) -> MagicMock:
            return mock_sentinel
        
        check = RedisCheck(sentinel_factory=mock_sentinel_factory)
        result = await check.execute({
            "sentinel_hosts": [("sentinel1", 26379)],
            "sentinel_service": "mymaster"
        })
        
        assert result.status == CheckStatus.FAIL
        assert "no master elected" in result.message.lower()

    @pytest.mark.asyncio
    async def test_redis_sentinel_connection_error(self) -> None:
        """RedisCheck should fail if Sentinel connection fails."""
        def mock_sentinel_factory(hosts, **kwargs) -> MagicMock:
            mock_sentinel = MagicMock()
            mock_sentinel.discover_master.side_effect = ConnectionError("Sentinel unreachable")
            return mock_sentinel
        
        check = RedisCheck(sentinel_factory=mock_sentinel_factory)
        result = await check.execute({
            "sentinel_hosts": [("sentinel1", 26379)],
        })
        
        assert result.status == CheckStatus.FAIL
        assert "Sentinel check failed" in result.message


class TestLLMCheck:
    """Tests for LLMCheck with injected HTTP client factory."""

    @pytest.mark.asyncio
    async def test_llm_check_pass(self) -> None:
        """LLMCheck should pass when API responds with 200."""
        models_response = MagicMock()
        models_response.status_code = 200
        models_response.json.return_value = {
            "data": [{"id": "mistralai/devstral-2-123b-instruct-2512"}]
        }

        completion_response = MagicMock()
        completion_response.status_code = 200
        
        mock_client = AsyncMock()
        mock_client.get.return_value = models_response
        mock_client.post.return_value = completion_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        
        def mock_http_factory():
            return mock_client
        
        check = LLMCheck(http_client_factory=mock_http_factory)
        result = await check.execute({"openai_api_key": "sk-123"})
        
        assert result.status == CheckStatus.PASS
        assert "reachable" in result.message.lower()

    @pytest.mark.asyncio
    async def test_llm_check_missing_key(self, monkeypatch) -> None:
        """LLMCheck should fail if API key missing."""
        for var in (
            "NVIDIA_API_KEY",
            "NVIDIA_NIM_API_KEY",
            "CYBERRED_LLM__NIM_API_KEY",
            "OPENAI_API_KEY",
        ):
            monkeypatch.delenv(var, raising=False)
        check = LLMCheck()
        result = await check.execute({})  # No key in config or env
        
        assert result.status == CheckStatus.FAIL
        assert "API Key missing" in result.message

    @pytest.mark.asyncio
    async def test_llm_check_401(self) -> None:
        """LLMCheck should fail on 401 Unauthorized."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        
        def mock_http_factory():
            return mock_client
        
        check = LLMCheck(http_client_factory=mock_http_factory)
        result = await check.execute({"openai_api_key": "sk-invalid"})
        
        assert result.status == CheckStatus.FAIL
        assert "401" in result.message

    @pytest.mark.asyncio
    async def test_llm_check_500(self) -> None:
        """LLMCheck should fail on server errors."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        
        def mock_http_factory():
            return mock_client
        
        check = LLMCheck(http_client_factory=mock_http_factory)
        result = await check.execute({"openai_api_key": "sk-123"})
        
        assert result.status == CheckStatus.FAIL
        assert "500" in result.message

    @pytest.mark.asyncio
    async def test_llm_check_connection_error(self) -> None:
        """LLMCheck should fail on connection error."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Connection refused")
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        
        def mock_http_factory():
            return mock_client
        
        check = LLMCheck(http_client_factory=mock_http_factory)
        result = await check.execute({"openai_api_key": "sk-123"})
        
        assert result.status == CheckStatus.FAIL
        assert "ping failed" in result.message


class TestCertCheck:
    """Tests for CertCheck with injected certificate loader."""

    @pytest.mark.asyncio
    async def test_cert_check_disabled(self) -> None:
        """CertCheck should pass if C2 disabled."""
        check = CertCheck()
        result = await check.execute({"c2_enabled": False})
        
        assert result.status == CheckStatus.PASS
        assert "C2 disabled" in result.message

    @pytest.mark.asyncio
    async def test_cert_check_missing(self) -> None:
        """CertCheck should fail if cert file missing."""
        check = CertCheck()
        result = await check.execute({"c2_enabled": True, "c2_cert_path": "/nonexistent/cert.pem"})
        
        assert result.status == CheckStatus.FAIL
        assert "Cert missing" in result.message

    @pytest.mark.asyncio
    async def test_cert_check_empty(self, tmp_path: Path) -> None:
        """CertCheck should fail if cert file empty."""
        cert_file = tmp_path / "empty.pem"
        cert_file.touch()
        
        check = CertCheck()
        result = await check.execute({"c2_enabled": True, "c2_cert_path": str(cert_file)})
        
        assert result.status == CheckStatus.FAIL
        assert "Cert empty" in result.message

    @pytest.mark.asyncio
    async def test_cert_check_valid_expiry(self, tmp_path: Path) -> None:
        """CertCheck should pass if cert has >24h validity."""
        cert_file = tmp_path / "cert.pem"
        cert_file.write_text("CERT DATA")  # Just needs to be non-empty
        
        not_after = datetime.now(timezone.utc) + timedelta(hours=48)
        hours_remaining = 48.0
        
        def mock_cert_loader(path: str) -> tuple[datetime, float]:
            return not_after, hours_remaining
        
        check = CertCheck(cert_loader=mock_cert_loader)
        result = await check.execute({"c2_enabled": True, "c2_cert_path": str(cert_file)})
        
        assert result.status == CheckStatus.PASS
        assert "valid" in result.message.lower()

    @pytest.mark.asyncio
    async def test_cert_check_expiring_soon(self, tmp_path: Path) -> None:
        """CertCheck should fail if cert has <24h validity."""
        cert_file = tmp_path / "cert.pem"
        cert_file.write_text("CERT DATA")
        
        not_after = datetime.now(timezone.utc) + timedelta(hours=12)
        hours_remaining = 12.0
        
        def mock_cert_loader(path: str) -> tuple[datetime, float]:
            return not_after, hours_remaining
        
        check = CertCheck(cert_loader=mock_cert_loader)
        result = await check.execute({"c2_enabled": True, "c2_cert_path": str(cert_file)})
        
        assert result.status == CheckStatus.FAIL
        assert "24" in result.message  # Mentions 24h requirement

    @pytest.mark.asyncio
    async def test_cert_check_expired(self, tmp_path: Path) -> None:
        """CertCheck should fail if cert is already expired."""
        cert_file = tmp_path / "cert.pem"
        cert_file.write_text("CERT DATA")
        
        not_after = datetime.now(timezone.utc) - timedelta(hours=1)
        hours_remaining = -1.0
        
        def mock_cert_loader(path: str) -> tuple[datetime, float]:
            return not_after, hours_remaining
        
        check = CertCheck(cert_loader=mock_cert_loader)
        result = await check.execute({"c2_enabled": True, "c2_cert_path": str(cert_file)})
        
        assert result.status == CheckStatus.FAIL
        assert "expired" in result.message.lower()

    @pytest.mark.asyncio
    async def test_cert_check_loader_exception(self, tmp_path: Path) -> None:
        """CertCheck should fail gracefully on certificate parsing error."""
        cert_file = tmp_path / "cert.pem"
        cert_file.write_text("INVALID CERT DATA")
        
        def mock_cert_loader(path: str) -> tuple[datetime, float]:
            raise ValueError("Unable to parse certificate")
        
        check = CertCheck(cert_loader=mock_cert_loader)
        result = await check.execute({"c2_enabled": True, "c2_cert_path": str(cert_file)})
        
        assert result.status == CheckStatus.FAIL
        assert "failed" in result.message.lower()

    @pytest.mark.asyncio
    async def test_cert_check_execute_exception(self, tmp_path: Path) -> None:
        """CertCheck should fail gracefully when os.path.getsize raises exception."""
        from unittest.mock import patch
        
        cert_file = tmp_path / "locked.pem"
        cert_file.write_text("CERT DATA")
        
        check = CertCheck()
        
        # Patch os.path.getsize to raise after os.path.exists passes
        with patch("os.path.getsize", side_effect=PermissionError("Permission denied")):
            result = await check.execute({"c2_enabled": True, "c2_cert_path": str(cert_file)})
        
        assert result.status == CheckStatus.FAIL
        assert "Cert check failed" in result.message


class TestResourceAdmissionCheck:
    """Tests for ResourceAdmissionCheck with injected host metrics."""

    VirtualMemory = namedtuple("VirtualMemory", ["available", "total", "percent"])
    CpuTimes = namedtuple("CpuTimes", ["iowait"])

    @pytest.mark.asyncio
    async def test_resource_admission_pass_and_contract(self) -> None:
        """Should pass and return a resource_contract when host has headroom."""

        def mock_memory() -> TestResourceAdmissionCheck.VirtualMemory:
            return TestResourceAdmissionCheck.VirtualMemory(
                available=32 * 1024**3,
                total=64 * 1024**3,
                percent=50.0,
            )

        def mock_cpu_percent(interval: float | None = None) -> float:
            return 10.0

        def mock_cpu_times_percent(interval: float | None = None) -> TestResourceAdmissionCheck.CpuTimes:
            return TestResourceAdmissionCheck.CpuTimes(iowait=2.0)

        def mock_cpu_count() -> int:
            return 8

        def mock_loadavg() -> tuple[float, float, float]:
            return (1.0, 1.0, 1.0)

        check = ResourceAdmissionCheck(
            memory_fn=mock_memory,
            cpu_percent_fn=mock_cpu_percent,
            cpu_times_percent_fn=mock_cpu_times_percent,
            cpu_count_fn=mock_cpu_count,
            loadavg_fn=mock_loadavg,
        )
        config = {
            "target_agents": 600,
            "worker_pool_size": 10,
            "roe": {"max_concurrent_tools": 8},
        }
        result = await check.execute(config)

        assert result.status in (CheckStatus.PASS, CheckStatus.WARN)
        assert isinstance(result.details, dict)
        contract = result.details.get("resource_contract")
        assert isinstance(contract, dict)
        assert contract.get("target_agents") == 600
        assert contract.get("expected_workers") == 10
        assert contract.get("max_agents_allowed_now") is not None
        assert isinstance(contract.get("policy"), dict)

    @pytest.mark.asyncio
    async def test_resource_admission_fail_on_memory_shortage(self) -> None:
        """Should fail when available memory is below required_memory_mb."""

        def mock_memory() -> TestResourceAdmissionCheck.VirtualMemory:
            return TestResourceAdmissionCheck.VirtualMemory(
                available=2 * 1024**3,
                total=4 * 1024**3,
                percent=95.0,
            )

        def mock_cpu_percent(interval: float | None = None) -> float:
            return 10.0

        def mock_cpu_times_percent(interval: float | None = None) -> TestResourceAdmissionCheck.CpuTimes:
            return TestResourceAdmissionCheck.CpuTimes(iowait=2.0)

        check = ResourceAdmissionCheck(
            memory_fn=mock_memory,
            cpu_percent_fn=mock_cpu_percent,
            cpu_times_percent_fn=mock_cpu_times_percent,
            cpu_count_fn=lambda: 8,
            loadavg_fn=lambda: (1.0, 1.0, 1.0),
        )
        result = await check.execute({"target_agents": 100, "worker_pool_size": 10})

        assert result.status == CheckStatus.FAIL
        assert "blocked" in result.message.lower() or "failed" in result.message.lower()
