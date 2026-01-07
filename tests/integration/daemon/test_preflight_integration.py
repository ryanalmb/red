"""Integration tests for pre-flight checks using real services.

These tests use testcontainers for Redis and real certificates,
following the architecture's "NO MOCKED TESTS" principle.
"""

from pathlib import Path

import pytest
from testcontainers.redis import RedisContainer

from cyberred.daemon.preflight import (
    RedisCheck,
    LLMCheck,
    ScopeCheck,
    CertCheck,
    DiskCheck,
    MemoryCheck,
    PreFlightRunner,
    CheckStatus,
    CheckPriority,
)


def get_redis_url(container: RedisContainer) -> str:
    """Build Redis connection URL from container."""
    host = container.get_container_host_ip()
    port = container.get_exposed_port(6379)
    return f"redis://{host}:{port}"


class TestRedisCheckIntegration:
    """Integration tests for RedisCheck with real Redis."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_redis_check_real_connection(self) -> None:
        """RedisCheck should pass when connecting to real Redis."""
        with RedisContainer() as redis_container:
            check = RedisCheck()
            result = await check.execute({
                "redis_url": get_redis_url(redis_container)
            })
            
            assert result.status == CheckStatus.PASS
            assert "reachable" in result.message.lower()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_redis_check_connection_refused(self) -> None:
        """RedisCheck should fail when Redis is unreachable."""
        check = RedisCheck()
        result = await check.execute({
            "redis_url": "redis://localhost:59999"  # Non-existent port
        })
        
        assert result.status == CheckStatus.FAIL
        assert "failed" in result.message.lower()


class TestCertCheckIntegration:
    """Integration tests for CertCheck with real certificates."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_cert_check_valid_real_cert(self, valid_cert_path: Path) -> None:
        """CertCheck should pass for a real certificate with >24h validity."""
        check = CertCheck()
        result = await check.execute({
            "c2_enabled": True,
            "c2_cert_path": str(valid_cert_path)
        })
        
        assert result.status == CheckStatus.PASS
        assert "valid" in result.message.lower()
        # Should report hours remaining
        assert "h remaining" in result.message.lower()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_cert_check_expiring_real_cert(self, expiring_cert_path: Path) -> None:
        """CertCheck should fail for a real certificate with <24h validity."""
        check = CertCheck()
        result = await check.execute({
            "c2_enabled": True,
            "c2_cert_path": str(expiring_cert_path)
        })
        
        assert result.status == CheckStatus.FAIL
        assert "24" in result.message  # Mentions 24h requirement

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_cert_check_expired_real_cert(self, expired_cert_path: Path) -> None:
        """CertCheck should fail for an already-expired real certificate."""
        check = CertCheck()
        result = await check.execute({
            "c2_enabled": True,
            "c2_cert_path": str(expired_cert_path)
        })
        
        assert result.status == CheckStatus.FAIL
        assert "expired" in result.message.lower()


class TestScopeCheckIntegration:
    """Integration tests for ScopeCheck with real files."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_scope_check_real_file(self, scope_file: Path) -> None:
        """ScopeCheck should pass for a real valid scope file."""
        check = ScopeCheck()
        result = await check.execute({
            "scope_path": str(scope_file)
        })
        
        assert result.status == CheckStatus.PASS
        assert "valid" in result.message.lower()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_scope_check_real_missing_file(self) -> None:
        """ScopeCheck should fail for a non-existent file."""
        check = ScopeCheck()
        result = await check.execute({
            "scope_path": "/this/path/does/not/exist/scope.yaml"
        })
        
        assert result.status == CheckStatus.FAIL
        assert "not found" in result.message.lower()


class TestDiskCheckIntegration:
    """Integration tests for DiskCheck with real system."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_disk_check_real_system(self) -> None:
        """DiskCheck should work against real disk (should pass on most systems)."""
        check = DiskCheck()
        result = await check.execute({})
        
        # Most test systems should have >10% free
        assert result.status in (CheckStatus.PASS, CheckStatus.WARN)
        assert "free" in result.message.lower()


class TestMemoryCheckIntegration:
    """Integration tests for MemoryCheck with real system."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_memory_check_real_system(self) -> None:
        """MemoryCheck should work against real memory (should pass on most systems)."""
        check = MemoryCheck()
        result = await check.execute({})
        
        # Most test systems should have >1GB RAM
        assert result.status in (CheckStatus.PASS, CheckStatus.WARN)
        assert "available" in result.message.lower() or "memory" in result.message.lower()


class TestPreFlightRunnerIntegration:
    """Integration tests for full pre-flight sequence."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_preflight_sequence_with_redis(
        self,
        scope_file: Path,
        valid_cert_path: Path
    ) -> None:
        """Full pre-flight sequence should work with real Redis and certs."""
        with RedisContainer() as redis_container:
            runner = PreFlightRunner()
            
            config = {
                "redis_url": get_redis_url(redis_container),
                "scope_path": str(scope_file),
                "c2_enabled": True,
                "c2_cert_path": str(valid_cert_path),
                "openai_api_key": "sk-test-key",  # Will fail LLM check but that's expected
            }
            
            results = await runner.run_all(config)
            
            # Should have results for all 6 checks
            assert len(results) == 6
            
            # Find specific results
            redis_result = next(r for r in results if r.name == "REDIS_CHECK")
            scope_result = next(r for r in results if r.name == "SCOPE_CHECK")
            cert_result = next(r for r in results if r.name == "CERT_CHECK")
            disk_result = next(r for r in results if r.name == "DISK_CHECK")
            memory_result = next(r for r in results if r.name == "MEMORY_CHECK")
            
            # Redis should pass (real container)
            assert redis_result.status == CheckStatus.PASS
            
            # Scope should pass (real file)
            assert scope_result.status == CheckStatus.PASS
            
            # Cert should pass (real valid cert)
            assert cert_result.status == CheckStatus.PASS
            
            # Disk and memory should not fail on most systems
            assert disk_result.status in (CheckStatus.PASS, CheckStatus.WARN)
            assert memory_result.status in (CheckStatus.PASS, CheckStatus.WARN)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_preflight_blocks_on_p0_failure(
        self,
        valid_cert_path: Path
    ) -> None:
        """PreFlightRunner should properly detect P0 failures."""
        from cyberred.core.exceptions import PreFlightCheckError
        
        runner = PreFlightRunner()
        
        config = {
            "redis_url": "redis://localhost:59999",  # Will fail - no Redis
            "scope_path": "/nonexistent/scope.yaml",  # Will fail - no file
            "c2_enabled": True,
            "c2_cert_path": str(valid_cert_path),
        }
        
        results = await runner.run_all(config)
        
        # Should have P0 failures
        with pytest.raises(PreFlightCheckError) as exc_info:
            runner.validate_results(results)
        
        # Error should contain the failed checks (attribute is 'results', not 'failed_checks')
        assert len(exc_info.value.results) > 0
