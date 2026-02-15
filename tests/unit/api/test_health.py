"""Unit tests for health endpoint (Story 14.1, Task 4 — RED phase)."""

import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from cyberred.api.server import create_app


class TestHealthEndpoint:
    """Tests for GET /health endpoint."""

    def test_health_returns_200(self):
        """Health endpoint returns 200 OK."""
        app = create_app()
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_response_has_required_fields(self):
        """Health response includes status, uptime, and version."""
        app = create_app()
        client = TestClient(app)
        response = client.get("/health")
        data = response.json()
        assert "status" in data
        assert "uptime" in data
        assert "version" in data

    def test_health_status_is_ok(self):
        """Health status field is 'ok' when server is healthy."""
        app = create_app()
        client = TestClient(app)
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "ok"

    def test_health_version_matches_package(self):
        """Health version matches cyberred.__version__."""
        import cyberred
        app = create_app()
        client = TestClient(app)
        response = client.get("/health")
        data = response.json()
        assert data["version"] == cyberred.__version__

    def test_health_uptime_is_non_negative(self):
        """Health uptime is a non-negative float."""
        app = create_app()
        client = TestClient(app)
        response = client.get("/health")
        data = response.json()
        assert isinstance(data["uptime"], (int, float))
        assert data["uptime"] >= 0

    def test_health_no_auth_required(self):
        """Health endpoint does NOT require authentication."""
        app = create_app()
        client = TestClient(app)
        # No auth headers provided
        response = client.get("/health")
        assert response.status_code == 200


class TestHealthFunctions:
    """Tests for health module helper functions."""

    def test_set_start_time(self):
        """set_start_time sets the module-level start time."""
        from cyberred.api.routes import health
        old = health._start_time
        try:
            health.set_start_time(100.0)
            assert health._start_time == 100.0
        finally:
            health._start_time = old

    def test_get_uptime_with_start_time(self):
        """get_uptime returns positive value when start time is set."""
        from cyberred.api.routes import health
        old = health._start_time
        try:
            health.set_start_time(time.time() - 5.0)
            uptime = health.get_uptime()
            assert uptime >= 4.5
        finally:
            health._start_time = old

    def test_get_uptime_without_start_time(self):
        """get_uptime returns 0.0 when start time is None."""
        from cyberred.api.routes import health
        old = health._start_time
        try:
            health._start_time = None
            assert health.get_uptime() == 0.0
        finally:
            health._start_time = old

    def test_reset_start_time(self):
        """reset_start_time sets the module-level start time to None."""
        from cyberred.api.routes import health
        old = health._start_time
        try:
            health.set_start_time(100.0)
            assert health._start_time == 100.0
            health.reset_start_time()
            assert health._start_time is None
            assert health.get_uptime() == 0.0
        finally:
            health._start_time = old

    def test_lifespan_resets_start_time_on_shutdown(self):
        """Lifespan resets start_time to None on shutdown."""
        from cyberred.api.routes import health
        old = health._start_time
        try:
            app = create_app()
            with TestClient(app) as client:
                # During lifespan, start_time should be set
                assert health._start_time is not None
            # After exiting TestClient context (shutdown), start_time should be reset
            assert health._start_time is None
        finally:
            health._start_time = old

    def test_lifespan_sets_start_time(self):
        """Lifespan sets start_time and uptime works through TestClient."""
        from cyberred.api.routes import health
        old = health._start_time
        try:
            app = create_app()
            with TestClient(app) as client:
                response = client.get("/health")
                data = response.json()
                assert data["uptime"] >= 0
                assert health._start_time is not None
        finally:
            health._start_time = old
