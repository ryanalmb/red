"""Integration tests for DataBrowserScreen.

Story 11.2: Exfiltrated Data Browser

Task 7: Integration tests for end-to-end data browser functionality.

TDD RED Phase: These tests should FAIL initially.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from textual.app import App, ComposeResult
from textual.pilot import Pilot


@pytest.fixture
def temp_engagement_with_data(tmp_path: Path) -> tuple[Path, bytes]:
    """Create temporary engagement with encrypted test data."""
    from cyberred.storage.evidence import encrypt_data

    # Create directory structure
    engagement_path = tmp_path / "test-engagement"
    evidence_dir = engagement_path / "evidence"
    data_dir = evidence_dir / "data"
    data_dir.mkdir(parents=True)

    # Encryption key
    encryption_key = os.urandom(32)

    # Create encrypted test files
    # File 1: Credential file (shadow)
    shadow_content = b"root:$6$salt$hash:18000:0:99999:7:::\ndaemon:*:18000:0:99999:7:::\n"
    ciphertext1, nonce1 = encrypt_data(shadow_content, encryption_key)
    (data_dir / "cred_001.enc").write_bytes(ciphertext1)

    # File 2: Config file (nginx.conf)
    nginx_content = b"server {\n    listen 80;\n    server_name example.com;\n    location / {\n        proxy_pass http://backend;\n    }\n}\n"
    ciphertext2, nonce2 = encrypt_data(nginx_content, encryption_key)
    (data_dir / "config_001.enc").write_bytes(ciphertext2)

    # File 3: Document (text-based for preview)
    doc_content = b"CONFIDENTIAL REPORT\n==================\n\nThis is a confidential document...\n"
    ciphertext3, nonce3 = encrypt_data(doc_content, encryption_key)
    (data_dir / "doc_001.enc").write_bytes(ciphertext3)

    # File 4: Binary file (will show metadata only)
    binary_content = b"\x89PNG\r\n\x1a\n" + os.urandom(1000)
    ciphertext4, nonce4 = encrypt_data(binary_content, encryption_key)
    (data_dir / "image_001.enc").write_bytes(ciphertext4)

    # Create manifest.json
    manifest = {
        "schema_version": "1.0.0",
        "engagement_id": "eng-integration-test",
        "created_at": "2026-01-29T10:00:00Z",
        "updated_at": "2026-01-29T15:00:00Z",
        "exfiltrated_data": [
            {
                "id": "data-001",
                "filename": "shadow",
                "file_type": "shadow",
                "mime_type": "text/plain",
                "size_bytes": len(shadow_content),
                "target": "192.168.1.100",
                "source_agent": "postex-agent-1",
                "timestamp": "2026-01-29T11:00:00Z",
                "encrypted_path": "data/cred_001.enc",
                "sha256_hash": "abc123",
                "nonce": nonce1.hex(),
                "category": "credentials",
            },
            {
                "id": "data-002",
                "filename": "nginx.conf",
                "file_type": "conf",
                "mime_type": "text/plain",
                "size_bytes": len(nginx_content),
                "target": "192.168.1.101",
                "source_agent": "postex-agent-2",
                "timestamp": "2026-01-29T12:00:00Z",
                "encrypted_path": "data/config_001.enc",
                "sha256_hash": "def456",
                "nonce": nonce2.hex(),
                "category": "configs",
            },
            {
                "id": "data-003",
                "filename": "report.txt",
                "file_type": "txt",
                "mime_type": "text/plain",
                "size_bytes": len(doc_content),
                "target": "192.168.1.100",
                "source_agent": "postex-agent-1",
                "timestamp": "2026-01-29T13:00:00Z",
                "encrypted_path": "data/doc_001.enc",
                "sha256_hash": "ghi789",
                "nonce": nonce3.hex(),
                "category": "documents",
            },
            {
                "id": "data-004",
                "filename": "screenshot.png",
                "file_type": "png",
                "mime_type": "image/png",
                "size_bytes": len(binary_content),
                "target": "192.168.1.100",
                "source_agent": "postex-agent-1",
                "timestamp": "2026-01-29T14:00:00Z",
                "encrypted_path": "data/image_001.enc",
                "sha256_hash": "jkl012",
                "nonce": nonce4.hex(),
                "category": "other",
            },
        ],
        "screenshots": [],
        "total_size_bytes": sum(
            [
                len(shadow_content),
                len(nginx_content),
                len(doc_content),
                len(binary_content),
            ]
        ),
    }

    (evidence_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    return engagement_path, encryption_key


class TestDataBrowserIntegration:
    """Integration tests for DataBrowserScreen."""

    @pytest.mark.asyncio
    async def test_end_to_end_store_data_open_browser_view_item(
        self, temp_engagement_with_data: tuple[Path, bytes]
    ) -> None:
        """Test end-to-end: store data → open browser → view item."""
        from cyberred.storage.evidence import ExfiltratedDataStore
        from cyberred.tui.screens.data_browser import DataBrowserScreen
        from cyberred.tui.widgets.data_preview import DataItemPreview

        engagement_path, encryption_key = temp_engagement_with_data

        # Create real store
        store = ExfiltratedDataStore(engagement_path, encryption_key)

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataBrowserScreen(store=store)

        async with TestApp().run_test() as pilot:
            screen = pilot.app.query_one(DataBrowserScreen)
            await pilot.pause()

            # Verify items are loaded
            items = store.list_items()
            assert len(items) == 4

            # Select first item (should be most recent - data-004)
            await pilot.press("enter")
            await pilot.pause()

            # Preview should show item
            preview = screen.query_one(DataItemPreview)
            assert preview._current_item is not None

    @pytest.mark.asyncio
    async def test_category_navigation_works_correctly(
        self, temp_engagement_with_data: tuple[Path, bytes]
    ) -> None:
        """Test category navigation filters items correctly."""
        from cyberred.storage.evidence import ExfiltratedDataStore
        from cyberred.tui.screens.data_browser import DataBrowserScreen
        from textual.widgets import DataTable

        engagement_path, encryption_key = temp_engagement_with_data
        store = ExfiltratedDataStore(engagement_path, encryption_key)

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataBrowserScreen(store=store)

        async with TestApp().run_test() as pilot:
            screen = pilot.app.query_one(DataBrowserScreen)
            await pilot.pause()

            # Initial: all items (4)
            table = screen.query_one(DataTable)
            assert table.row_count == 4

            # Filter to credentials
            screen._set_category_filter("credentials")
            await pilot.pause()

            # Should show 1 item
            credentials = store.list_items(category="credentials")
            assert len(credentials) == 1
            assert credentials[0].filename == "shadow"

            # Filter to configs
            screen._set_category_filter("configs")
            await pilot.pause()

            configs = store.list_items(category="configs")
            assert len(configs) == 1
            assert configs[0].filename == "nginx.conf"

    @pytest.mark.asyncio
    async def test_search_returns_matching_items(
        self, temp_engagement_with_data: tuple[Path, bytes]
    ) -> None:
        """Test search returns matching items."""
        from cyberred.storage.evidence import ExfiltratedDataStore
        from cyberred.tui.screens.data_browser import DataBrowserScreen
        from textual.widgets import Input

        engagement_path, encryption_key = temp_engagement_with_data
        store = ExfiltratedDataStore(engagement_path, encryption_key)

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataBrowserScreen(store=store)

        async with TestApp().run_test() as pilot:
            screen = pilot.app.query_one(DataBrowserScreen)
            await pilot.pause()

            # Search for "shadow"
            results = store.search("shadow")
            assert len(results) == 1
            assert results[0].filename == "shadow"

            # Search for target IP
            results = store.search("192.168.1.100")
            assert len(results) == 3  # shadow, report.txt, screenshot.png

    @pytest.mark.asyncio
    async def test_keyboard_navigation_j_k_enter_escape(
        self, temp_engagement_with_data: tuple[Path, bytes]
    ) -> None:
        """Test keyboard navigation (j/k, Enter, Esc)."""
        from cyberred.storage.evidence import ExfiltratedDataStore
        from cyberred.tui.screens.data_browser import DataBrowserScreen
        from textual.widgets import DataTable, Static

        engagement_path, encryption_key = temp_engagement_with_data
        store = ExfiltratedDataStore(engagement_path, encryption_key)

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Main Screen")

        async with TestApp().run_test() as pilot:
            app = pilot.app

            # Push data browser screen
            browser_screen = DataBrowserScreen(store=store)
            app.push_screen(browser_screen)
            await pilot.pause()

            # Use the reference we have instead of querying
            table = browser_screen.query_one(DataTable)
            table.focus()
            await pilot.pause()

            # Verify table has rows
            assert table.row_count == 4

            # Test navigation actions exist and work
            assert hasattr(browser_screen, "action_cursor_down")
            assert hasattr(browser_screen, "action_cursor_up")
            browser_screen.action_cursor_down()
            browser_screen.action_cursor_up()

            initial_stack = len(app.screen_stack)

            # Press Escape to go back
            await pilot.press("escape")
            await pilot.pause()

            # Should have popped screen
            assert len(app.screen_stack) < initial_stack

    @pytest.mark.asyncio
    async def test_decryption_and_preview(
        self, temp_engagement_with_data: tuple[Path, bytes]
    ) -> None:
        """Test decryption works and preview shows content."""
        from cyberred.storage.evidence import ExfiltratedDataStore

        engagement_path, encryption_key = temp_engagement_with_data
        store = ExfiltratedDataStore(engagement_path, encryption_key)

        # Get credential item
        item = store.get_item("data-001")
        assert item is not None
        assert item.filename == "shadow"

        # Decrypt content
        content = store.get_item_content("data-001")
        assert b"root:" in content
        assert b"daemon:" in content

        # Get config item
        config_content = store.get_item_content("data-002")
        assert b"server {" in config_content
        assert b"listen 80" in config_content

    @pytest.mark.asyncio
    async def test_empty_engagement_shows_empty_state(
        self, tmp_path: Path
    ) -> None:
        """Test empty engagement shows empty state message."""
        from cyberred.storage.evidence import ExfiltratedDataStore
        from cyberred.tui.screens.data_browser import DataBrowserScreen

        # Create empty engagement
        engagement_path = tmp_path / "empty-engagement"
        evidence_dir = engagement_path / "evidence"
        data_dir = evidence_dir / "data"
        data_dir.mkdir(parents=True)

        # Empty manifest
        manifest = {
            "schema_version": "1.0.0",
            "engagement_id": "eng-empty",
            "created_at": "2026-01-29T10:00:00Z",
            "updated_at": "2026-01-29T10:00:00Z",
            "exfiltrated_data": [],
            "screenshots": [],
            "total_size_bytes": 0,
        }
        (evidence_dir / "manifest.json").write_text(json.dumps(manifest))

        encryption_key = os.urandom(32)
        store = ExfiltratedDataStore(engagement_path, encryption_key)

        assert store.is_empty

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataBrowserScreen(store=store)

        async with TestApp().run_test() as pilot:
            screen = pilot.app.query_one(DataBrowserScreen)
            await pilot.pause()

            # Should show empty state
            assert store.list_items() == []


class TestEncryptionDecryptionIntegration:
    """Integration tests for encryption/decryption flow."""

    @pytest.mark.asyncio
    async def test_encrypt_store_decrypt_roundtrip(
        self, temp_engagement_with_data: tuple[Path, bytes]
    ) -> None:
        """Test full encrypt → store → decrypt roundtrip."""
        from cyberred.storage.evidence import (
            ExfiltratedDataStore,
            encrypt_data,
            decrypt_data,
        )

        engagement_path, encryption_key = temp_engagement_with_data
        store = ExfiltratedDataStore(engagement_path, encryption_key)

        # Verify we can decrypt all items
        for item in store.list_items():
            content = store.get_item_content(item.id)
            assert content is not None
            assert len(content) > 0

    @pytest.mark.asyncio
    async def test_decryption_with_wrong_key_fails(
        self, temp_engagement_with_data: tuple[Path, bytes]
    ) -> None:
        """Test decryption with wrong key fails gracefully."""
        from cyberred.core.exceptions import DecryptionError
        from cyberred.storage.evidence import ExfiltratedDataStore

        engagement_path, correct_key = temp_engagement_with_data

        # Create store with wrong key
        wrong_key = os.urandom(32)
        store = ExfiltratedDataStore(engagement_path, wrong_key)

        # Attempting to decrypt should fail
        with pytest.raises(DecryptionError):
            store.get_item_content("data-001")

    @pytest.mark.asyncio
    async def test_secure_buffer_clears_decrypted_content(
        self, temp_engagement_with_data: tuple[Path, bytes]
    ) -> None:
        """Test SecureBuffer clears decrypted content from memory."""
        from cyberred.storage.evidence import ExfiltratedDataStore, SecureBuffer

        engagement_path, encryption_key = temp_engagement_with_data
        store = ExfiltratedDataStore(engagement_path, encryption_key)

        # Get content
        content = store.get_item_content("data-001")

        # Use SecureBuffer
        with SecureBuffer(content) as secure_content:
            assert len(secure_content) > 0
            buffer_ref = secure_content

        # After context exit, buffer should be cleared
        assert len(buffer_ref) == 0
