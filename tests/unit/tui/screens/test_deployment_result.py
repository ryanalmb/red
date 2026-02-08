"""Unit tests for DeploymentResultScreen.

Story 12.8: Natural Language Drop Box Setup - Task 9.2

Tests deployment result screen.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from textual.app import App
from textual.widgets import Static, Button

from cyberred.tui.screens.deployment_result import DeploymentResultScreen
from cyberred.c2.nl_interpreter import DeploymentPlan


class TestDeploymentResultScreen:
    """Tests for DeploymentResultScreen."""
    
    @pytest.fixture
    def valid_plan(self):
        """Create valid deployment plan."""
        return DeploymentPlan(
            platform="android",
            ip_address="192.168.1.100",
            hostname="test-phone",
            confidence=0.9,
        )
    
    @pytest.fixture
    def temp_paths(self, tmp_path):
        """Create temporary certificate paths."""
        cert_path = tmp_path / "dropbox.crt"
        key_path = tmp_path / "dropbox.key"
        ca_path = tmp_path / "ca.crt"
        
        cert_path.write_text("CERT CONTENT")
        key_path.write_text("KEY CONTENT")
        ca_path.write_text("CA CONTENT")
        
        return cert_path, key_path, ca_path
    
    def test_screen_imports(self):
        """Test screen can be imported."""
        assert DeploymentResultScreen is not None
    
    def test_screen_title(self):
        """Test screen has correct title."""
        assert DeploymentResultScreen.TITLE == "Deployment Complete"
    
    def test_screen_bindings(self):
        """Test screen has required bindings."""
        binding_keys = [b.key for b in DeploymentResultScreen.BINDINGS]
        assert "escape" in binding_keys
        assert "c" in binding_keys
    
    def test_screen_creation(self, valid_plan, temp_paths):
        """Test screen can be created with parameters."""
        cert_path, key_path, ca_path = temp_paths
        instructions = "Test instructions"
        
        screen = DeploymentResultScreen(
            plan=valid_plan,
            drop_box_id="test-dropbox",
            cert_path=cert_path,
            key_path=key_path,
            ca_path=ca_path,
            instructions=instructions,
        )
        
        assert screen is not None
        assert screen._plan == valid_plan
        assert screen._drop_box_id == "test-dropbox"
        assert screen._instructions == instructions
    
    def test_screen_creation_with_qr(self, valid_plan, temp_paths):
        """Test screen can be created with QR code."""
        cert_path, key_path, ca_path = temp_paths
        qr_code = "██████\n██  ██\n██████"
        
        screen = DeploymentResultScreen(
            plan=valid_plan,
            drop_box_id="test-dropbox",
            cert_path=cert_path,
            key_path=key_path,
            ca_path=ca_path,
            instructions="Test",
            qr_code=qr_code,
        )
        
        assert screen._qr_code == qr_code
    
    def test_screen_has_css(self, valid_plan, temp_paths):
        """Test screen has CSS defined."""
        cert_path, key_path, ca_path = temp_paths
        
        screen = DeploymentResultScreen(
            plan=valid_plan,
            drop_box_id="test-dropbox",
            cert_path=cert_path,
            key_path=key_path,
            ca_path=ca_path,
            instructions="Test",
        )
        
        assert screen.DEFAULT_CSS is not None
        assert "DeploymentResultScreen" in screen.DEFAULT_CSS


class TestDeploymentResultScreenIntegration:
    """Integration tests for deployment result screen."""
    
    @pytest.fixture
    def valid_plan(self):
        """Create valid deployment plan."""
        return DeploymentPlan(
            platform="android",
            ip_address="192.168.1.100",
            hostname="test-phone",
            confidence=0.9,
        )
    
    @pytest.fixture
    def temp_paths(self, tmp_path):
        """Create temporary certificate paths."""
        cert_path = tmp_path / "dropbox.crt"
        key_path = tmp_path / "dropbox.key"
        ca_path = tmp_path / "ca.crt"
        
        cert_path.write_text("CERT CONTENT")
        key_path.write_text("KEY CONTENT")
        ca_path.write_text("CA CONTENT")
        
        return cert_path, key_path, ca_path
    
    @pytest.mark.asyncio
    async def test_screen_mounts(self, valid_plan, temp_paths):
        """Test screen can be mounted."""
        cert_path, key_path, ca_path = temp_paths
        
        class TestApp(App):
            def compose(self):
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            screen = DeploymentResultScreen(
                plan=valid_plan,
                drop_box_id="test-dropbox",
                cert_path=cert_path,
                key_path=key_path,
                ca_path=ca_path,
                instructions="Test instructions",
            )
            app.push_screen(screen)
            await pilot.pause()
            
            assert isinstance(app.screen, DeploymentResultScreen)
    
    @pytest.mark.asyncio
    async def test_screen_has_done_button(self, valid_plan, temp_paths):
        """Test screen contains Done button."""
        cert_path, key_path, ca_path = temp_paths
        
        class TestApp(App):
            def compose(self):
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            screen = DeploymentResultScreen(
                plan=valid_plan,
                drop_box_id="test-dropbox",
                cert_path=cert_path,
                key_path=key_path,
                ca_path=ca_path,
                instructions="Test",
            )
            app.push_screen(screen)
            await pilot.pause()
            
            done_btn = app.screen.query_one("#done-btn", Button)
            assert done_btn is not None
    
    @pytest.mark.asyncio
    async def test_screen_has_copy_cert_button(self, valid_plan, temp_paths):
        """Test screen contains Copy Cert Path button."""
        cert_path, key_path, ca_path = temp_paths
        
        class TestApp(App):
            def compose(self):
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            screen = DeploymentResultScreen(
                plan=valid_plan,
                drop_box_id="test-dropbox",
                cert_path=cert_path,
                key_path=key_path,
                ca_path=ca_path,
                instructions="Test",
            )
            app.push_screen(screen)
            await pilot.pause()
            
            copy_btn = app.screen.query_one("#copy-cert-btn", Button)
            assert copy_btn is not None
    
    @pytest.mark.asyncio
    async def test_screen_with_qr_code(self, valid_plan, temp_paths):
        """Test screen displays QR code for mobile platforms."""
        cert_path, key_path, ca_path = temp_paths
        qr_code = "██████\n██  ██\n██████"
        
        class TestApp(App):
            def compose(self):
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            screen = DeploymentResultScreen(
                plan=valid_plan,
                drop_box_id="test-dropbox",
                cert_path=cert_path,
                key_path=key_path,
                ca_path=ca_path,
                instructions="Test",
                qr_code=qr_code,
            )
            app.push_screen(screen)
            await pilot.pause()
            
            # QR tab should exist
            assert screen._qr_code == qr_code
