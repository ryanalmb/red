"""Integration tests for NL Drop Box Deployment flow.

Story 12.8: Natural Language Drop Box Setup - Task 9.2

Tests end-to-end NL interpretation → instruction generation → QR flow.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from cyberred.c2.nl_interpreter import (
    DeploymentPlan,
    DropBoxDeploymentInterpreter,
    SUPPORTED_PLATFORMS,
)
from cyberred.c2.deployment_instructions import get_instructions, is_mobile_platform
from cyberred.c2.qr_generator import QRPayload, generate_deployment_qr, get_cert_fingerprint


class TestNLToInstructionsFlow:
    """Integration tests for NL input → parsed plan → instructions pipeline."""

    @pytest.fixture
    def cert_paths(self, tmp_path):
        """Create temporary certificate files."""
        cert_path = tmp_path / "dropbox.crt"
        key_path = tmp_path / "dropbox.key"
        ca_path = tmp_path / "ca.crt"

        # Create minimal PEM certificate for fingerprint calculation
        cert_content = """-----BEGIN CERTIFICATE-----
MIIBkTCB+wIJAKHBfpegPjMBMA0GCSqGSIb3DQEBCwUAMBExDzANBgNVBAMMBnRl
c3RjYTAeFw0yNDAxMDEwMDAwMDBaFw0yNTAxMDEwMDAwMDBaMBExDzANBgNVBAMM
BnRlc3RjYTBcMA0GCSqGSIb3DQEBAQUAA0sAMEgCQQC7o96WzE2Bm3C8E1fJ9dKf
L0GQ3u+3hH2fJSPL0J3QKSPNfPVMZrPPFEB0MJHrxH8PN2GHqX0BrJlMbqPLRPUJ
AgMBAAGjUzBRMB0GA1UdDgQWBBQ7o96WzE2Bm3C8E1fJ9dKfL0GQ3jAfBgNVHSME
GDAWgBQ7o96WzE2Bm3C8E1fJ9dKfL0GQ3jAPBgNVHRMBAf8EBTADAQH/MA0GCSqG
SIb3DQEBCwUAA0EAu6PelsxNgZtwvBNXyfXSny9BkN7vt4R9nyUjy9Cd0CkjzXz1
TGazzxRAdDCR68R/DzdhgKl9AayZTG6jy0T1CQ==
-----END CERTIFICATE-----"""
        cert_path.write_text(cert_content)
        key_path.write_text("KEY CONTENT")
        ca_path.write_text(cert_content)

        return cert_path, key_path, ca_path

    @pytest.mark.asyncio
    async def test_android_nl_to_instructions_with_qr(self, cert_paths):
        """Test full flow: NL → DeploymentPlan → instructions + QR for Android."""
        cert_path, key_path, ca_path = cert_paths

        # Step 1: Simulate LLM response for NL interpretation
        interpreter = DropBoxDeploymentInterpreter()
        mock_gateway = MagicMock()
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "platform": "android",
            "ip_address": "192.168.1.100",
            "hostname": "android-phone",
            "confidence": 0.95,
        })
        mock_response.finish_reason = "stop"
        mock_gateway.agent_complete = AsyncMock(return_value=mock_response)

        with patch.object(interpreter, '_get_gateway', return_value=mock_gateway):
            plan = await interpreter.interpret("Deploy on Android at 192.168.1.100")

        # Step 2: Verify plan
        assert plan.is_valid()
        assert plan.platform == "android"
        assert not plan.needs_clarification()

        # Step 3: Generate drop box ID
        drop_box_id = plan.generate_drop_box_id()
        assert len(drop_box_id) > 0
        assert "android" in drop_box_id

        # Step 4: Generate instructions
        c2_url = "wss://c2.test.com:8444"
        instructions = get_instructions(
            plan.platform, cert_path, key_path, ca_path, c2_url, drop_box_id,
        )
        assert "Android" in instructions
        assert "adb" in instructions
        assert c2_url in instructions

        # Step 5: This is a mobile platform — should generate QR
        assert is_mobile_platform(plan.platform)
        fingerprint = get_cert_fingerprint(cert_path)
        payload = QRPayload(
            c2_url=c2_url,
            cert_fingerprint=fingerprint,
            drop_box_id=drop_box_id,
        )
        qr_code = generate_deployment_qr(payload)
        assert len(qr_code) > 50

    @pytest.mark.asyncio
    async def test_linux_nl_to_instructions_no_qr(self, cert_paths):
        """Test full flow for Linux: NL → instructions, no QR needed."""
        cert_path, key_path, ca_path = cert_paths

        interpreter = DropBoxDeploymentInterpreter()
        mock_gateway = MagicMock()
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "platform": "linux",
            "ip_address": "10.0.0.50",
            "hostname": "server-1",
            "confidence": 0.9,
        })
        mock_response.finish_reason = "stop"
        mock_gateway.agent_complete = AsyncMock(return_value=mock_response)

        with patch.object(interpreter, '_get_gateway', return_value=mock_gateway):
            plan = await interpreter.interpret("Linux dropbox at 10.0.0.50")

        assert plan.is_valid()
        assert plan.platform == "linux"

        drop_box_id = plan.generate_drop_box_id()
        c2_url = "wss://c2.test.com:8444"
        instructions = get_instructions(
            plan.platform, cert_path, key_path, ca_path, c2_url, drop_box_id,
        )

        assert "Linux" in instructions
        assert "systemd" in instructions.lower()
        assert not is_mobile_platform(plan.platform)

    @pytest.mark.asyncio
    async def test_all_platforms_have_complete_flow(self, cert_paths):
        """Test every supported platform produces valid instructions."""
        cert_path, key_path, ca_path = cert_paths
        c2_url = "wss://c2.test.com:8444"

        for platform in SUPPORTED_PLATFORMS:
            plan = DeploymentPlan(
                platform=platform,
                ip_address="10.0.0.1",
                hostname="test-host",
                confidence=0.95,
            )
            assert plan.is_valid(), f"Plan for {platform} should be valid"

            drop_box_id = plan.generate_drop_box_id()
            instructions = get_instructions(
                platform, cert_path, key_path, ca_path, c2_url, drop_box_id,
            )
            assert len(instructions) > 100, f"Instructions for {platform} too short"

            # Mobile platforms should produce QR codes
            if is_mobile_platform(platform):
                fingerprint = get_cert_fingerprint(cert_path)
                payload = QRPayload(
                    c2_url=c2_url,
                    cert_fingerprint=fingerprint,
                    drop_box_id=drop_box_id,
                )
                qr = generate_deployment_qr(payload)
                assert len(qr) > 50, f"QR for {platform} too short"


class TestClarificationFlow:
    """Integration tests for ambiguous input → clarification path."""

    @pytest.mark.asyncio
    async def test_ambiguous_input_triggers_clarification(self):
        """Test ambiguous NL input produces plan needing clarification."""
        interpreter = DropBoxDeploymentInterpreter()
        mock_gateway = MagicMock()
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "platform": "",
            "ip_address": "",
            "confidence": 0.2,
            "clarification_needed": "Please specify both the platform and IP address.",
        })
        mock_response.finish_reason = "stop"
        mock_gateway.agent_complete = AsyncMock(return_value=mock_response)

        with patch.object(interpreter, '_get_gateway', return_value=mock_gateway):
            plan = await interpreter.interpret("Deploy on my phone")

        # Plan should need clarification, not be valid
        assert plan.needs_clarification()
        assert plan.confidence < 0.5
        assert not plan.is_valid()

    @pytest.mark.asyncio
    async def test_partial_input_adds_clarification(self):
        """Test partial input (missing IP) adds clarification about missing fields."""
        interpreter = DropBoxDeploymentInterpreter()
        mock_gateway = MagicMock()
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "platform": "linux",
            "ip_address": "",
            "confidence": 0.6,
        })
        mock_response.finish_reason = "stop"
        mock_gateway.agent_complete = AsyncMock(return_value=mock_response)

        with patch.object(interpreter, '_get_gateway', return_value=mock_gateway):
            plan = await interpreter.interpret("Linux dropbox")

        # Should have clarification about missing IP
        assert plan.clarification_needed is not None
        assert "ip" in plan.clarification_needed.lower() or "address" in plan.clarification_needed.lower()
