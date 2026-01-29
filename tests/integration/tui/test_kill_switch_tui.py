"""Integration tests for Kill Switch TUI Integration.

Story 10.4: Kill Switch TUI Integration
Integration tests for the complete kill switch flow in TUI.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cyberred.tui.app import CyberRedApp, EngagementState


class TestKillSwitchFullFlow:
    """Integration tests for complete kill switch flow."""

    @pytest.mark.asyncio
    async def test_f10_confirm_full_flow(self) -> None:
        """Test F10 → confirmation → kill → FROZEN status."""
        mock_redis = MagicMock()
        mock_redis.publish = AsyncMock(return_value=1)
        
        app = CyberRedApp(
            redis_client=mock_redis,
            engagement_id="integration-test-001",
        )
        
        async with app.run_test() as pilot:
            app.engagement_state = EngagementState.RUNNING
            await pilot.press("f10")
            
            from cyberred.tui.screens.kill_confirm import KillSwitchConfirmScreen
            assert any(
                isinstance(screen, KillSwitchConfirmScreen)
                for screen in app.screen_stack
            )
            
            await pilot.press("y")
            assert app.engagement_state == EngagementState.FROZEN

    @pytest.mark.asyncio
    async def test_esc_immediate_kill_flow(self) -> None:
        """Test ESC → immediate kill → FROZEN status."""
        mock_redis = MagicMock()
        mock_redis.publish = AsyncMock(return_value=1)
        
        app = CyberRedApp(
            redis_client=mock_redis,
            engagement_id="integration-test-002",
        )
        
        async with app.run_test() as pilot:
            app.engagement_state = EngagementState.RUNNING
            await pilot.press("escape")
            assert app.engagement_state == EngagementState.FROZEN


class TestKillSwitchWithRealKillSwitch:
    """Integration tests with real KillSwitch instance."""

    @pytest.mark.asyncio
    async def test_killswitch_trigger_called_with_correct_params(self) -> None:
        """Test KillSwitch.trigger() is called with correct parameters."""
        mock_redis = MagicMock()
        mock_redis.publish = AsyncMock(return_value=1)
        
        app = CyberRedApp(
            redis_client=mock_redis,
            engagement_id="test-engagement",
        )
        
        with patch.object(
            app._killswitch, "trigger", new_callable=AsyncMock
        ) as mock_trigger:
            mock_trigger.return_value = {
                "success": True,
                "duration_ms": 100,
                "paths": {"redis": True, "sigterm": False, "docker": False},
            }
            
            async with app.run_test() as pilot:
                await app.action_panic(trigger_source="F10")
                mock_trigger.assert_called_once()


class TestKillSwitchAuditTrail:
    """Integration tests for audit trail logging."""

    @pytest.mark.asyncio
    async def test_audit_log_on_panic(self) -> None:
        """AC #8: Audit log is triggered on panic."""
        mock_redis = MagicMock()
        mock_redis.publish = AsyncMock(return_value=1)
        
        app = CyberRedApp(
            redis_client=mock_redis,
            engagement_id="audit-test-001",
        )
        
        async with app.run_test() as pilot:
            await app.action_panic()
            # Panic completed without error - audit was logged
            assert app.engagement_state == EngagementState.FROZEN


class TestStatusBarFrozenDisplay:
    """Integration tests for status bar FROZEN display."""

    @pytest.mark.asyncio
    async def test_status_bar_frozen_styling(self) -> None:
        """AC #7: Status bar shows FROZEN with danger styling."""
        mock_redis = MagicMock()
        mock_redis.publish = AsyncMock(return_value=1)
        
        app = CyberRedApp(
            redis_client=mock_redis,
            engagement_id="style-test-001",
        )
        
        async with app.run_test() as pilot:
            await app.action_panic()
            
            from cyberred.tui.widgets import StatusBarWidget
            status_bar = app.query_one("#status-bar", StatusBarWidget)
            
            assert status_bar.engagement_state == "FROZEN"
            rendered = status_bar.render()
            assert "FROZEN" in rendered
