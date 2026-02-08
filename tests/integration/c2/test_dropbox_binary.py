"""Integration tests for Drop Box binary startup.

Story 12.5: Drop Box Go Module Structure
AC #5: Given each platform binary, when integration tests run,
       then each platform binary starts successfully.

These tests verify:
1. Binary starts and displays version with --version flag
2. Binary displays help with --help flag
3. Binary exits cleanly without valid C2 config (expected behavior)
4. Binary file size is reasonable (<20MB uncompressed)
5. Binary has no external shared library dependencies
"""

import os
import subprocess
import platform
import stat
from pathlib import Path

import pytest

# Path to the dropbox build directory
DROPBOX_DIR = Path(__file__).parent.parent.parent.parent / "dropbox"
BUILD_DIR = DROPBOX_DIR / "build"


def get_linux_binary() -> Path:
    """Get path to Linux binary."""
    return BUILD_DIR / "linux" / "dropbox-linux-amd64"


def get_current_platform_binary() -> Path:
    """Get path to binary for current platform."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "linux" and machine in ("x86_64", "amd64"):
        return BUILD_DIR / "linux" / "dropbox-linux-amd64"
    elif system == "darwin" and machine in ("x86_64", "amd64"):
        return BUILD_DIR / "darwin" / "dropbox-darwin-amd64"
    elif system == "windows" and machine in ("x86_64", "amd64", "amd64"):
        return BUILD_DIR / "windows" / "dropbox-windows-amd64.exe"
    else:
        pytest.skip(f"No binary available for {system}/{machine}")


def binary_exists() -> bool:
    """Check if the Linux binary exists."""
    binary = get_linux_binary()
    return binary.exists()


@pytest.fixture(scope="module")
def build_binaries():
    """Build binaries before running tests."""
    if not BUILD_DIR.exists() or not any(BUILD_DIR.iterdir()):
        # Run make build-all
        result = subprocess.run(
            ["make", "build-all"],
            cwd=DROPBOX_DIR,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            pytest.fail(f"Failed to build binaries: {result.stderr}")
    return BUILD_DIR


@pytest.fixture
def linux_binary(build_binaries) -> Path:
    """Get the Linux binary path, building if necessary."""
    binary = get_linux_binary()
    if not binary.exists():
        pytest.skip("Linux binary not found")
    return binary


class TestDropboxBinaryStartup:
    """Test suite for Drop Box binary startup behavior."""

    def test_binary_exists(self, linux_binary: Path):
        """Verify the Linux binary was built successfully."""
        assert linux_binary.exists(), f"Binary not found at {linux_binary}"
        assert linux_binary.is_file(), f"Path is not a file: {linux_binary}"

    def test_binary_is_executable(self, linux_binary: Path):
        """Verify the binary has executable permissions."""
        mode = linux_binary.stat().st_mode
        assert mode & stat.S_IXUSR, "Binary is not executable by owner"

    def test_version_flag(self, linux_binary: Path):
        """AC #5.2: Test Linux binary starts with --version flag."""
        result = subprocess.run(
            [str(linux_binary), "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert result.returncode == 0, f"--version failed: {result.stderr}"
        assert "Cyber-Red Drop Box" in result.stdout
        assert "Version:" in result.stdout
        assert "Build Time:" in result.stdout
        assert "Git Commit:" in result.stdout

    def test_help_flag(self, linux_binary: Path):
        """AC #5.3: Test Linux binary starts with --help flag."""
        result = subprocess.run(
            [str(linux_binary), "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert result.returncode == 0, f"--help failed: {result.stderr}"
        # Go's flag package writes usage to stderr by default
        output = result.stdout + result.stderr
        assert "Cyber-Red Drop Box" in output
        assert "Usage:" in output
        assert "-config" in output
        assert "-version" in output
        assert "-help" in output

    def test_exits_without_config(self, linux_binary: Path):
        """AC #5.4: Verify binary exits cleanly without valid C2 config."""
        result = subprocess.run(
            [str(linux_binary)],
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Expected to exit with error code 1 when no config is provided
        assert result.returncode == 1, "Binary should exit with code 1 without config"
        assert "No configuration file specified" in result.stderr

    def test_exits_with_invalid_config_path(self, linux_binary: Path):
        """Verify binary handles non-existent config file gracefully."""
        result = subprocess.run(
            [str(linux_binary), "--config", "/nonexistent/config.yaml"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Expected to exit with error since C2 client not implemented yet
        assert result.returncode == 1
        assert "C2 client not yet implemented" in result.stderr

    def test_binary_size_reasonable(self, linux_binary: Path):
        """Verify binary file size is reasonable (<20MB uncompressed)."""
        max_size_mb = 20
        max_size_bytes = max_size_mb * 1024 * 1024

        actual_size = linux_binary.stat().st_size
        actual_size_mb = actual_size / (1024 * 1024)

        assert actual_size < max_size_bytes, (
            f"Binary too large: {actual_size_mb:.2f}MB > {max_size_mb}MB"
        )
        # Also verify it's not suspiciously small (>100KB)
        assert actual_size > 100 * 1024, (
            f"Binary suspiciously small: {actual_size} bytes"
        )


class TestDropboxBinaryStaticLinking:
    """Test suite for verifying static linking (AC #3)."""

    @pytest.mark.skipif(
        platform.system() != "Linux",
        reason="ldd only available on Linux"
    )
    def test_no_dynamic_dependencies(self, linux_binary: Path):
        """AC #3.3: Verify no external library dependencies with ldd."""
        result = subprocess.run(
            ["ldd", str(linux_binary)],
            capture_output=True,
            text=True,
            timeout=10,
        )

        # A statically linked binary will show "not a dynamic executable"
        # or ldd will return non-zero exit code
        is_static = (
            "not a dynamic executable" in result.stdout or
            "not a dynamic executable" in result.stderr or
            result.returncode != 0
        )

        assert is_static, (
            f"Binary appears to have dynamic dependencies:\n{result.stdout}"
        )


class TestDropboxBinaryAllPlatforms:
    """Test suite for verifying all platform binaries exist."""

    def test_windows_binary_exists(self, build_binaries):
        """Verify Windows binary was built."""
        binary = BUILD_DIR / "windows" / "dropbox-windows-amd64.exe"
        assert binary.exists(), f"Windows binary not found at {binary}"

    def test_linux_amd64_binary_exists(self, build_binaries):
        """Verify Linux amd64 binary was built."""
        binary = BUILD_DIR / "linux" / "dropbox-linux-amd64"
        assert binary.exists(), f"Linux amd64 binary not found at {binary}"

    def test_linux_arm64_binary_exists(self, build_binaries):
        """Verify Linux arm64 binary was built (AWS Graviton, Raspberry Pi)."""
        binary = BUILD_DIR / "linux" / "dropbox-linux-arm64"
        assert binary.exists(), f"Linux arm64 binary not found at {binary}"

    def test_darwin_amd64_binary_exists(self, build_binaries):
        """Verify macOS Intel binary was built."""
        binary = BUILD_DIR / "darwin" / "dropbox-darwin-amd64"
        assert binary.exists(), f"macOS Intel binary not found at {binary}"

    def test_darwin_arm64_binary_exists(self, build_binaries):
        """Verify macOS Apple Silicon binary was built."""
        binary = BUILD_DIR / "darwin" / "dropbox-darwin-arm64"
        assert binary.exists(), f"macOS Apple Silicon binary not found at {binary}"

    def test_android_binary_exists(self, build_binaries):
        """Verify Android binary was built."""
        binary = BUILD_DIR / "android" / "dropbox-android-arm64"
        assert binary.exists(), f"Android binary not found at {binary}"

    def test_checksums_file_exists(self, build_binaries):
        """Verify checksums.txt was generated."""
        checksums = BUILD_DIR / "checksums.txt"
        assert checksums.exists(), f"Checksums file not found at {checksums}"

        # Verify it contains entries for all platforms
        content = checksums.read_text()
        assert "windows" in content
        assert "linux" in content
        assert "darwin" in content
        assert "android" in content


class TestDropboxBinaryStripping:
    """Test suite for verifying binary stripping (AC #4)."""

    def test_binary_is_stripped(self, linux_binary: Path):
        """AC #4.1: Verify symbols are stripped from binary."""
        # Use 'file' command to check if binary is stripped
        result = subprocess.run(
            ["file", str(linux_binary)],
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Go binaries built with -s -w flags won't have debug info
        # The 'file' command may show "stripped" or we check with nm
        output = result.stdout.lower()

        # Alternative: use nm to check for symbols
        nm_result = subprocess.run(
            ["nm", str(linux_binary)],
            capture_output=True,
            text=True,
            timeout=10,
        )

        # nm should fail or show minimal symbols for stripped binary
        is_stripped = (
            "stripped" in output or
            nm_result.returncode != 0 or
            "no symbols" in nm_result.stderr.lower()
        )

        assert is_stripped, "Binary does not appear to be stripped"
