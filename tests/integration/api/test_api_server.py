"""Integration tests for API server (Story 14.1, Task 7)."""

import asyncio
import ssl

import httpx
import pytest

from cyberred.api.server import APIServer


@pytest.mark.integration
class TestAPIServerIntegration:
    """Full server integration tests with real TLS and HTTP."""

    @pytest.mark.asyncio
    async def test_server_starts_and_health_responds(self, integration_api_config):
        """Server starts and health endpoint responds 200."""
        server = APIServer(config=integration_api_config)
        task = asyncio.create_task(server.start())
        try:
            # Wait for server to be ready
            await asyncio.sleep(0.5)
            async with httpx.AsyncClient(verify=False) as client:
                resp = await client.get(
                    f"https://127.0.0.1:{integration_api_config.port}/health"
                )
                assert resp.status_code == 200
        finally:
            await server.stop()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_health_response_fields(self, integration_api_config):
        """Health response includes status, uptime, and version fields."""
        server = APIServer(config=integration_api_config)
        task = asyncio.create_task(server.start())
        try:
            await asyncio.sleep(0.5)
            async with httpx.AsyncClient(verify=False) as client:
                resp = await client.get(
                    f"https://127.0.0.1:{integration_api_config.port}/health"
                )
                data = resp.json()
                assert data["status"] == "ok"
                assert isinstance(data["uptime"], (int, float))
                assert data["uptime"] >= 0
                assert "version" in data
        finally:
            await server.stop()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_openapi_spec_served(self, integration_api_config):
        """OpenAPI spec is served at /docs and /openapi.json."""
        server = APIServer(config=integration_api_config)
        task = asyncio.create_task(server.start())
        try:
            await asyncio.sleep(0.5)
            async with httpx.AsyncClient(verify=False) as client:
                docs_resp = await client.get(
                    f"https://127.0.0.1:{integration_api_config.port}/docs"
                )
                assert docs_resp.status_code == 200

                openapi_resp = await client.get(
                    f"https://127.0.0.1:{integration_api_config.port}/openapi.json"
                )
                assert openapi_resp.status_code == 200
                data = openapi_resp.json()
                assert data["info"]["title"] == "Cyber-Red API"
        finally:
            await server.stop()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_server_stop_graceful(self, integration_api_config):
        """Server stop completes gracefully."""
        server = APIServer(config=integration_api_config)
        task = asyncio.create_task(server.start())
        try:
            await asyncio.sleep(0.5)
            # Verify it's running
            async with httpx.AsyncClient(verify=False) as client:
                resp = await client.get(
                    f"https://127.0.0.1:{integration_api_config.port}/health"
                )
                assert resp.status_code == 200

            # Stop gracefully
            await server.stop()
            # Wait for uvicorn to finish shutting down
            try:
                await asyncio.wait_for(task, timeout=3.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass

            # After stop, connection should be refused
            await asyncio.sleep(0.3)
            async with httpx.AsyncClient(verify=False) as client:
                with pytest.raises(
                    (httpx.ConnectError, httpx.RemoteProtocolError, httpx.ReadError)
                ):
                    await client.get(
                        f"https://127.0.0.1:{integration_api_config.port}/health",
                        timeout=2.0,
                    )
        except Exception:
            await server.stop()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            raise

    @pytest.mark.asyncio
    async def test_tls_enforcement(self, integration_api_config):
        """Plain HTTP connections are rejected (TLS required)."""
        server = APIServer(config=integration_api_config)
        task = asyncio.create_task(server.start())
        try:
            await asyncio.sleep(0.5)
            # Try plain HTTP — should fail
            async with httpx.AsyncClient() as client:
                with pytest.raises((httpx.ConnectError, httpx.RemoteProtocolError)):
                    await client.get(
                        f"http://127.0.0.1:{integration_api_config.port}/health"
                    )
        finally:
            await server.stop()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
