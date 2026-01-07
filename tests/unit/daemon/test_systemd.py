"""Unit tests for systemd integration module."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from unittest import mock

import pytest

from cyberred.daemon.systemd import (
    SERVICE_TEMPLATE,
    DEFAULT_SERVICE_PATH,
    generate_service_file,
    write_service_file,
    create_service_user,
    ensure_storage_directory,
    reload_systemd,
    enable_service,
    disable_service,
    stop_service,
    remove_service_file,
    _get_default_exec_path,
)


class TestServiceTemplate:
    """Tests for the service file template."""

    def test_template_contains_unit_section(self) -> None:
        """Template includes [Unit] section."""
        assert "[Unit]" in SERVICE_TEMPLATE

    def test_template_contains_service_section(self) -> None:
        """Template includes [Service] section."""
        assert "[Service]" in SERVICE_TEMPLATE

    def test_template_contains_install_section(self) -> None:
        """Template includes [Install] section."""
        assert "[Install]" in SERVICE_TEMPLATE

    def test_template_has_restart_on_failure(self) -> None:
        """Template has Restart=on-failure for automatic restart."""
        assert "Restart=on-failure" in SERVICE_TEMPLATE

    def test_template_has_restart_sec(self) -> None:
        """Template has RestartSec=5 for restart delay."""
        assert "RestartSec=5" in SERVICE_TEMPLATE

    def test_template_has_type_simple(self) -> None:
        """Template uses Type=simple for foreground mode."""
        assert "Type=simple" in SERVICE_TEMPLATE

    def test_template_has_standard_output_journal(self) -> None:
        """Template directs output to journal."""
        assert "StandardOutput=journal" in SERVICE_TEMPLATE

    def test_template_has_standard_error_journal(self) -> None:
        """Template directs errors to journal."""
        assert "StandardError=journal" in SERVICE_TEMPLATE

    def test_template_has_pythonunbuffered(self) -> None:
        """Template sets PYTHONUNBUFFERED for real-time logging."""
        assert 'Environment="PYTHONUNBUFFERED=1"' in SERVICE_TEMPLATE

    def test_template_has_exec_path_placeholder(self) -> None:
        """Template has {exec_path} placeholder."""
        assert "{exec_path}" in SERVICE_TEMPLATE

    def test_template_has_user_placeholder(self) -> None:
        """Template has {user} placeholder."""
        assert "{user}" in SERVICE_TEMPLATE

    def test_template_depends_on_network(self) -> None:
        """Template starts after network.target."""
        assert "network.target" in SERVICE_TEMPLATE

    def test_template_depends_on_redis(self) -> None:
        """Template starts after redis.service."""
        assert "redis.service" in SERVICE_TEMPLATE

    def test_template_wanted_by_multi_user(self) -> None:
        """Template is wanted by multi-user.target."""
        assert "WantedBy=multi-user.target" in SERVICE_TEMPLATE


class TestGetDefaultExecPath:
    """Tests for executable path detection."""

    @mock.patch("shutil.which")
    def test_returns_cyber_red_in_path(self, mock_which: mock.Mock) -> None:
        """Returns cyber-red from PATH if available."""
        mock_which.return_value = "/usr/bin/cyber-red"
        result = _get_default_exec_path()
        assert result == Path("/usr/bin/cyber-red")
        mock_which.assert_called_once_with("cyber-red")

    @mock.patch("shutil.which")
    def test_returns_fallback_when_not_in_path(self, mock_which: mock.Mock) -> None:
        """Returns /usr/local/bin/cyber-red fallback when not in PATH."""
        mock_which.return_value = None
        result = _get_default_exec_path()
        assert result == Path("/usr/local/bin/cyber-red")


class TestGenerateServiceFile:
    """Tests for generate_service_file function."""

    def test_generate_service_file_default(self) -> None:
        """Generates service file with default values."""
        content = generate_service_file()
        assert "User=cyberred" in content
        assert "ExecStart=" in content
        assert "ExecStop=" in content

    def test_generate_service_file_custom_user(self) -> None:
        """Generates service file with custom user."""
        content = generate_service_file(user="myuser")
        assert "User=myuser" in content
        assert "User=cyberred" not in content

    def test_generate_service_file_custom_exec_path(self) -> None:
        """Generates service file with custom executable path."""
        custom_path = Path("/opt/cyber-red/bin/cyber-red")
        content = generate_service_file(exec_path=custom_path)
        assert str(custom_path) in content
        assert f"ExecStart={custom_path} daemon start --foreground" in content
        assert f"ExecStop={custom_path} daemon stop" in content

    def test_generate_service_file_both_custom(self) -> None:
        """Generates service file with both custom user and path."""
        custom_path = Path("/custom/path")
        content = generate_service_file(user="testuser", exec_path=custom_path)
        assert "User=testuser" in content
        assert str(custom_path) in content


    def test_generate_service_file_custom_path_str(self) -> None:
        """Generates service file with custom executable path as string."""
        custom_path = "/usr/bin/custom-red"
        # Type ignore because we're testing runtime behavior with maybe-invalid types
        content = generate_service_file(exec_path=custom_path) # type: ignore
        assert custom_path in content

    def test_generate_service_file_invalid_user_injection(self) -> None:
        """Raises ValueError for invalid username (injection attempt)."""
        with pytest.raises(ValueError, match="Invalid username"):
            generate_service_file(user="root\nExecStartPre=/bin/evil")

    def test_generate_service_file_invalid_user_chars(self) -> None:
        """Raises ValueError for invalid characters in username."""
        with pytest.raises(ValueError, match="Invalid username"):
            generate_service_file(user="user$name")

    def test_generate_service_file_valid_users(self) -> None:
        """Accepts valid usernames."""
        valid_users = ["root", "cyber_red", "my-user", "user123", "_service"]
        for user in valid_users:
            content = generate_service_file(user=user)
            assert f"User={user}" in content

class TestWriteServiceFile:
    """Tests for write_service_file function."""

    @mock.patch("os.geteuid")
    def test_write_service_file_not_root(self, mock_geteuid: mock.Mock) -> None:
        """Raises PermissionError when not root."""
        mock_geteuid.return_value = 1000  # Non-root UID
        with pytest.raises(PermissionError, match="root privileges"):
            write_service_file("content")

    @mock.patch("os.geteuid")
    @mock.patch("os.chmod")
    @mock.patch("os.rename")
    @mock.patch("tempfile.mkstemp")
    def test_write_service_file_success(
        self,
        mock_mkstemp: mock.Mock,
        mock_rename: mock.Mock,
        mock_chmod: mock.Mock,
        mock_geteuid: mock.Mock,
        tmp_path: Path,
    ) -> None:
        """Successfully writes service file as root."""
        mock_geteuid.return_value = 0  # Root
        temp_file = tmp_path / "temp.service"
        temp_file.touch()
        mock_mkstemp.return_value = (os.open(str(temp_file), os.O_WRONLY), str(temp_file))

        service_path = tmp_path / "cyber-red.service"
        write_service_file("test content", service_path)

        mock_chmod.assert_called_once_with(str(temp_file), 0o644)
        mock_rename.assert_called_once()

    @mock.patch("os.geteuid")
    @mock.patch("os.path.exists")
    @mock.patch("os.unlink")
    @mock.patch("os.chmod")
    @mock.patch("tempfile.mkstemp")
    def test_write_service_file_cleanup_on_error(
        self,
        mock_mkstemp: mock.Mock,
        mock_chmod: mock.Mock,
        mock_unlink: mock.Mock,
        mock_exists: mock.Mock,
        mock_geteuid: mock.Mock,
        tmp_path: Path,
    ) -> None:
        """Cleans up temp file on rename failure."""
        mock_geteuid.return_value = 0  # Root
        temp_file = tmp_path / "temp.service"
        temp_file.touch()
        mock_mkstemp.return_value = (os.open(str(temp_file), os.O_WRONLY), str(temp_file))

        # Make chmod raise to trigger exception path
        mock_chmod.side_effect = OSError("Permission denied")
        mock_exists.return_value = True

        service_path = tmp_path / "cyber-red.service"
        with pytest.raises(OSError, match="Permission denied"):
            write_service_file("test content", service_path)

        # Verify cleanup was called
        mock_unlink.assert_called_once_with(str(temp_file))

    @mock.patch("os.geteuid")
    @mock.patch("os.path.exists")
    @mock.patch("os.unlink")
    @mock.patch("os.chmod")
    @mock.patch("tempfile.mkstemp")
    def test_write_service_file_cleanup_skipped_if_no_temp_file(
        self,
        mock_mkstemp: mock.Mock,
        mock_chmod: mock.Mock,
        mock_unlink: mock.Mock,
        mock_exists: mock.Mock,
        mock_geteuid: mock.Mock,
        tmp_path: Path,
    ) -> None:
        """Skips cleanup if temp file doesn't exist."""
        mock_geteuid.return_value = 0  # Root
        temp_file = tmp_path / "temp.service"
        temp_file.touch()
        mock_mkstemp.return_value = (os.open(str(temp_file), os.O_WRONLY), str(temp_file))

        # Make chmod raise to trigger exception path
        mock_chmod.side_effect = OSError("Permission denied")
        # Temp file doesn't exist (already cleaned up somehow)
        mock_exists.return_value = False

        service_path = tmp_path / "cyber-red.service"
        with pytest.raises(OSError, match="Permission denied"):
            write_service_file("test content", service_path)

        # Verify cleanup was NOT called since file doesn't exist
        mock_unlink.assert_not_called()


class TestCreateServiceUser:
    """Tests for create_service_user function."""

    @mock.patch("os.geteuid")
    def test_create_service_user_not_root(self, mock_geteuid: mock.Mock) -> None:
        """Raises PermissionError when not root."""
        mock_geteuid.return_value = 1000
        with pytest.raises(PermissionError, match="root privileges"):
            create_service_user()

    @mock.patch("os.geteuid")
    @mock.patch("subprocess.run")
    def test_create_service_user_already_exists(
        self,
        mock_run: mock.Mock,
        mock_geteuid: mock.Mock,
    ) -> None:
        """Returns False when user already exists."""
        mock_geteuid.return_value = 0
        mock_run.return_value = mock.Mock(returncode=0)  # id command success

        result = create_service_user("cyberred")

        assert result is False
        mock_run.assert_called_once_with(["id", "cyberred"], capture_output=True)

    @mock.patch("os.geteuid")
    @mock.patch("subprocess.run")
    def test_create_service_user_new_user(
        self,
        mock_run: mock.Mock,
        mock_geteuid: mock.Mock,
    ) -> None:
        """Creates new user when doesn't exist."""
        mock_geteuid.return_value = 0
        # First call (id) fails, second call (useradd) succeeds
        mock_run.side_effect = [
            mock.Mock(returncode=1),  # id - user doesn't exist
            mock.Mock(returncode=0),  # useradd - success
        ]

        result = create_service_user("cyberred")

        assert result is True
        assert mock_run.call_count == 2
        # Verify useradd call
        useradd_call = mock_run.call_args_list[1]
        assert useradd_call[0][0][0] == "useradd"
        assert "--system" in useradd_call[0][0]
        assert "--create-home" in useradd_call[0][0]


class TestEnsureStorageDirectory:
    """Tests for ensure_storage_directory function."""

    @mock.patch("os.geteuid")
    def test_ensure_storage_directory_not_root(self, mock_geteuid: mock.Mock) -> None:
        """Raises PermissionError when not root."""
        mock_geteuid.return_value = 1000
        with pytest.raises(PermissionError, match="root privileges"):
            ensure_storage_directory(Path("/var/lib/cyber-red"))

    @mock.patch("os.geteuid")
    @mock.patch("subprocess.run")
    @mock.patch("pathlib.Path.mkdir")
    def test_ensure_storage_directory_success(
        self,
        mock_mkdir: mock.Mock,
        mock_run: mock.Mock,
        mock_geteuid: mock.Mock,
    ) -> None:
        """Creates directory and sets ownership."""
        mock_geteuid.return_value = 0
        mock_run.return_value = mock.Mock(returncode=0)

        ensure_storage_directory(Path("/var/lib/cyber-red"), "cyberred")

        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_run.assert_called_once()
        assert "chown" in mock_run.call_args[0][0]


class TestReloadSystemd:
    """Tests for reload_systemd function."""

    @mock.patch("os.geteuid")
    def test_reload_systemd_not_root(self, mock_geteuid: mock.Mock) -> None:
        """Raises PermissionError when not root."""
        mock_geteuid.return_value = 1000
        with pytest.raises(PermissionError, match="root privileges"):
            reload_systemd()

    @mock.patch("os.geteuid")
    @mock.patch("subprocess.run")
    def test_reload_systemd_success(
        self,
        mock_run: mock.Mock,
        mock_geteuid: mock.Mock,
    ) -> None:
        """Calls systemctl daemon-reload."""
        mock_geteuid.return_value = 0
        mock_run.return_value = mock.Mock(returncode=0)

        reload_systemd()

        mock_run.assert_called_once_with(["systemctl", "daemon-reload"], check=True)


class TestEnableService:
    """Tests for enable_service function."""

    @mock.patch("os.geteuid")
    def test_enable_service_not_root(self, mock_geteuid: mock.Mock) -> None:
        """Raises PermissionError when not root."""
        mock_geteuid.return_value = 1000
        with pytest.raises(PermissionError, match="root privileges"):
            enable_service()

    @mock.patch("os.geteuid")
    @mock.patch("subprocess.run")
    def test_enable_service_success(
        self,
        mock_run: mock.Mock,
        mock_geteuid: mock.Mock,
    ) -> None:
        """Calls systemctl enable."""
        mock_geteuid.return_value = 0
        mock_run.return_value = mock.Mock(returncode=0)

        enable_service("cyber-red")

        mock_run.assert_called_once_with(["systemctl", "enable", "cyber-red"], check=True)


class TestDisableService:
    """Tests for disable_service function."""

    @mock.patch("subprocess.run")
    def test_disable_service_success(self, mock_run: mock.Mock) -> None:
        """Calls systemctl disable."""
        mock_run.return_value = mock.Mock(returncode=0)

        disable_service("cyber-red")

        mock_run.assert_called_once_with(["systemctl", "disable", "cyber-red"], check=True)


class TestStopService:
    """Tests for stop_service function."""

    @mock.patch("subprocess.run")
    def test_stop_service_running(self, mock_run: mock.Mock) -> None:
        """Stops running service."""
        mock_run.return_value = mock.Mock(returncode=0)

        stop_service("cyber-red")

        mock_run.assert_called_once_with(
            ["systemctl", "stop", "cyber-red"],
            capture_output=True,
        )

    @mock.patch("subprocess.run")
    def test_stop_service_not_running(self, mock_run: mock.Mock) -> None:
        """Handles non-running service gracefully."""
        mock_run.return_value = mock.Mock(returncode=5)  # Service not running

        # Should not raise
        stop_service("cyber-red")

        mock_run.assert_called_once()


class TestRemoveServiceFile:
    """Tests for remove_service_file function."""

    def test_remove_service_file_not_found(self, tmp_path: Path) -> None:
        """Raises FileNotFoundError when file doesn't exist."""
        nonexistent = tmp_path / "nonexistent.service"
        with pytest.raises(FileNotFoundError, match="not found"):
            remove_service_file(nonexistent)

    def test_remove_service_file_success(self, tmp_path: Path) -> None:
        """Removes existing service file."""
        service_file = tmp_path / "cyber-red.service"
        service_file.write_text("[Unit]\nDescription=Test\n")

        remove_service_file(service_file)

        assert not service_file.exists()
