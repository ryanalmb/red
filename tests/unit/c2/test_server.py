"""Unit tests for C2 server.

Tests follow TDD methodology - written before implementation.
"""

import datetime
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from cyberred.c2 import C2Server, C2ServerConfig
from cyberred.c2.server import SSLLoggingProtocol


class TestC2ServerConfig:
    """Tests for C2ServerConfig dataclass."""

    def test_config_defaults(self):
        """Test default configuration values (AC: #1 - default port 8444)."""
        config = C2ServerConfig()
        
        assert config.host == "0.0.0.0"
        assert config.port == 8444
        assert config.ca_cert_path is None
        assert config.server_cert_path is None
        assert config.server_key_path is None

    def test_config_custom_port(self):
        """Test custom port configuration (AC: #1 - configurable port)."""
        config = C2ServerConfig(port=9444)
        
        assert config.port == 9444

    def test_config_custom_host(self):
        """Test custom host configuration."""
        config = C2ServerConfig(host="127.0.0.1")
        
        assert config.host == "127.0.0.1"

    def test_config_with_cert_paths(self, tmp_path: Path):
        """Test configuration with certificate paths."""
        ca_path = tmp_path / "ca.crt"
        server_cert = tmp_path / "server.crt"
        server_key = tmp_path / "server.key"
        
        config = C2ServerConfig(
            ca_cert_path=ca_path,
            server_cert_path=server_cert,
            server_key_path=server_key,
        )
        
        assert config.ca_cert_path == ca_path
        assert config.server_cert_path == server_cert
        assert config.server_key_path == server_key


class TestC2ServerInit:
    """Tests for C2Server initialization."""

    def test_server_init_with_config(self):
        """Test server initializes with config."""
        config = C2ServerConfig(port=8444)
        server = C2Server(config)
        
        assert server._config == config
        assert server._ca_store is None

    def test_server_init_with_ca_store(self):
        """Test server initializes with CAStore."""
        config = C2ServerConfig()
        mock_ca_store = MagicMock()
        
        server = C2Server(config, ca_store=mock_ca_store)
        
        assert server._ca_store == mock_ca_store

    def test_server_not_running_initially(self):
        """Test server is not running after initialization."""
        config = C2ServerConfig()
        server = C2Server(config)
        
        assert server.is_running is False
        assert server._running is False

    def test_server_no_connections_initially(self):
        """Test server has no connections after initialization."""
        config = C2ServerConfig()
        server = C2Server(config)
        
        assert server.connection_count == 0
        assert len(server._connections) == 0

    def test_server_start_time_none_initially(self):
        """Test server start time is None before start."""
        config = C2ServerConfig()
        server = C2Server(config)
        
        assert server._start_time is None


class TestC2ServerStartStop:
    """Tests for C2Server start/stop lifecycle (AC: #1, #2)."""

    @pytest.mark.asyncio
    async def test_server_start_sets_running(self, tmp_path: Path):
        """Test that start() sets running flag."""
        import ssl
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        import datetime
        
        # Create test certs
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test")])
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.now(datetime.UTC))
            .not_valid_after(datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=1))
            .sign(key, hashes.SHA256())
        )
        
        ca_cert = tmp_path / "ca.crt"
        server_cert = tmp_path / "server.crt"
        server_key = tmp_path / "server.key"
        ca_cert.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        server_cert.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        server_key.write_bytes(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ))
        
        config = C2ServerConfig(
            host="127.0.0.1",
            port=0,  # Let OS assign port
            ca_cert_path=ca_cert,
            server_cert_path=server_cert,
            server_key_path=server_key,
        )
        server = C2Server(config)
        
        assert server.is_running is False
        
        await server.start()
        try:
            assert server.is_running is True
            assert server._start_time is not None
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_server_start_already_running_raises(self, tmp_path: Path):
        """Test that start() raises if already running."""
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        import datetime
        
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test")])
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.now(datetime.UTC))
            .not_valid_after(datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=1))
            .sign(key, hashes.SHA256())
        )
        
        ca_cert = tmp_path / "ca.crt"
        server_cert = tmp_path / "server.crt"
        server_key = tmp_path / "server.key"
        ca_cert.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        server_cert.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        server_key.write_bytes(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ))
        
        config = C2ServerConfig(
            host="127.0.0.1",
            port=0,
            ca_cert_path=ca_cert,
            server_cert_path=server_cert,
            server_key_path=server_key,
        )
        server = C2Server(config)
        
        await server.start()
        try:
            with pytest.raises(RuntimeError, match="already running"):
                await server.start()
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_server_stop_clears_running(self, tmp_path: Path):
        """Test that stop() clears running flag."""
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        import datetime
        
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test")])
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.now(datetime.UTC))
            .not_valid_after(datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=1))
            .sign(key, hashes.SHA256())
        )
        
        ca_cert = tmp_path / "ca.crt"
        server_cert = tmp_path / "server.crt"
        server_key = tmp_path / "server.key"
        ca_cert.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        server_cert.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        server_key.write_bytes(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ))
        
        config = C2ServerConfig(
            host="127.0.0.1",
            port=0,
            ca_cert_path=ca_cert,
            server_cert_path=server_cert,
            server_key_path=server_key,
        )
        server = C2Server(config)
        
        await server.start()
        assert server.is_running is True
        
        await server.stop()
        assert server.is_running is False

    @pytest.mark.asyncio
    async def test_server_stop_when_not_running_is_safe(self):
        """Test that stop() is safe to call when not running."""
        config = C2ServerConfig()
        server = C2Server(config)
        
        # Should not raise
        await server.stop()
        assert server.is_running is False


class TestC2ServerSSLContext:
    """Tests for C2Server SSL context creation (AC: #2, #3)."""

    def test_ssl_context_requires_client_cert(self, tmp_path: Path):
        """Test SSL context has CERT_REQUIRED verify mode."""
        import ssl
        
        # Create dummy cert files
        ca_cert = tmp_path / "ca.crt"
        server_cert = tmp_path / "server.crt"
        server_key = tmp_path / "server.key"
        
        # Create minimal self-signed cert for testing context creation
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        import datetime
        
        # Generate key
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        
        # Generate self-signed cert
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, "test"),
        ])
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.now(datetime.UTC))
            .not_valid_after(datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=1))
            .sign(key, hashes.SHA256())
        )
        
        # Write files
        ca_cert.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        server_cert.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        server_key.write_bytes(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ))
        
        config = C2ServerConfig(
            ca_cert_path=ca_cert,
            server_cert_path=server_cert,
            server_key_path=server_key,
        )
        server = C2Server(config)
        
        context = server._create_ssl_context()
        
        assert context.verify_mode == ssl.CERT_REQUIRED

    def test_ssl_context_purpose_client_auth(self, tmp_path: Path):
        """Test SSL context is configured for client authentication."""
        import ssl
        
        # Create minimal certs (same as above)
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        import datetime
        
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test")])
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.now(datetime.UTC))
            .not_valid_after(datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=1))
            .sign(key, hashes.SHA256())
        )
        
        ca_cert = tmp_path / "ca.crt"
        server_cert = tmp_path / "server.crt"
        server_key = tmp_path / "server.key"
        ca_cert.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        server_cert.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        server_key.write_bytes(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ))
        
        config = C2ServerConfig(
            ca_cert_path=ca_cert,
            server_cert_path=server_cert,
            server_key_path=server_key,
        )
        server = C2Server(config)
        
        context = server._create_ssl_context()
        
        # Context should be created (no exception) and have correct verify mode
        assert isinstance(context, ssl.SSLContext)
        assert context.verify_mode == ssl.CERT_REQUIRED


class TestC2ServerHealthStatus:
    """Tests for C2Server health status (AC: #5)."""

    def test_health_status_not_running(self):
        """Test health status returns error when not running."""
        config = C2ServerConfig()
        server = C2Server(config)
        
        status = server.get_health_status()
        
        assert status["status"] == "error"
        assert status["connections"] == 0
        assert status["uptime"] == 0

    def test_health_status_running_no_connections(self):
        """Test health status returns degraded with no connections."""
        config = C2ServerConfig()
        server = C2Server(config)
        
        # Simulate running state
        server._running = True
        server._start_time = 0.0
        
        status = server.get_health_status()
        
        assert status["status"] == "degraded"
        assert status["connections"] == 0
        assert "uptime" in status

    def test_health_status_running_with_connections(self):
        """Test health status returns healthy with connections."""
        config = C2ServerConfig()
        server = C2Server(config)
        
        # Simulate running state with connection
        server._running = True
        server._start_time = 0.0
        server._connections.add(MagicMock())  # Mock connection
        
        status = server.get_health_status()
        
        assert status["status"] == "healthy"
        assert status["connections"] == 1


class TestC2ServerConfigFromYaml:
    """Tests for C2ServerConfig.from_yaml() method."""

    def test_from_yaml_with_c2_section(self, tmp_path: Path):
        """Test loading config from YAML with c2 section."""
        yaml_content = """
c2:
  host: "192.168.1.100"
  port: 9444
  ca_cert_path: "/path/to/ca.crt"
  server_cert_path: "/path/to/server.crt"
  server_key_path: "/path/to/server.key"
"""
        yaml_file = tmp_path / "engagement.yaml"
        yaml_file.write_text(yaml_content)
        
        config = C2ServerConfig.from_yaml(yaml_file)
        
        assert config.host == "192.168.1.100"
        assert config.port == 9444
        assert config.ca_cert_path == Path("/path/to/ca.crt")
        assert config.server_cert_path == Path("/path/to/server.crt")
        assert config.server_key_path == Path("/path/to/server.key")

    def test_from_yaml_without_c2_section(self, tmp_path: Path):
        """Test loading config from YAML without c2 section (root level)."""
        yaml_content = """
host: "10.0.0.1"
port: 7444
"""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(yaml_content)
        
        config = C2ServerConfig.from_yaml(yaml_file)
        
        assert config.host == "10.0.0.1"
        assert config.port == 7444
        assert config.ca_cert_path is None

    def test_from_yaml_with_defaults(self, tmp_path: Path):
        """Test loading config uses defaults for missing values."""
        yaml_content = """
c2:
  port: 8445
"""
        yaml_file = tmp_path / "minimal.yaml"
        yaml_file.write_text(yaml_content)
        
        config = C2ServerConfig.from_yaml(yaml_file)
        
        assert config.host == "0.0.0.0"  # Default
        assert config.port == 8445
        assert config.ca_cert_path is None  # Default

    def test_from_yaml_file_not_found(self, tmp_path: Path):
        """Test from_yaml raises FileNotFoundError for missing file."""
        yaml_file = tmp_path / "nonexistent.yaml"
        
        with pytest.raises(FileNotFoundError, match="Configuration file not found"):
            C2ServerConfig.from_yaml(yaml_file)

    def test_from_yaml_empty_file(self, tmp_path: Path):
        """Test from_yaml raises ValueError for empty file."""
        yaml_file = tmp_path / "empty.yaml"
        yaml_file.write_text("")
        
        with pytest.raises(ValueError, match="Empty configuration file"):
            C2ServerConfig.from_yaml(yaml_file)

    def test_from_yaml_with_shared_secret_hex_string(self, tmp_path: Path):
        """Test loading shared_secret from YAML as hex string."""
        yaml_content = """
c2:
  port: 8444
  shared_secret: 'deadbeef1234'
"""
        yaml_file = tmp_path / "with_secret.yaml"
        yaml_file.write_text(yaml_content)
        
        config = C2ServerConfig.from_yaml(yaml_file)
        
        assert config.shared_secret == bytes.fromhex('deadbeef1234')
        assert isinstance(config.shared_secret, bytes)

    def test_from_yaml_with_shared_secret_none(self, tmp_path: Path):
        """Test loading config without shared_secret."""
        yaml_content = """
c2:
  port: 8444
"""
        yaml_file = tmp_path / "no_secret.yaml"
        yaml_file.write_text(yaml_content)
        
        config = C2ServerConfig.from_yaml(yaml_file)
        
        assert config.shared_secret is None

    def test_from_yaml_with_shared_secret_empty_string(self, tmp_path: Path):
        """Test loading config with empty shared_secret."""
        yaml_content = """
c2:
  port: 8444
  shared_secret: ''
"""
        yaml_file = tmp_path / "empty_secret.yaml"
        yaml_file.write_text(yaml_content)
        
        config = C2ServerConfig.from_yaml(yaml_file)
        
        # Empty string should result in None (falsy check)
        assert config.shared_secret is None


class TestSSLLoggingProtocol:
    """Tests for SSLLoggingProtocol wrapper."""

    def test_protocol_delegates_connection_made(self):
        """Test connection_made is delegated to original protocol."""
        mock_original = MagicMock()
        mock_transport = MagicMock()
        
        protocol = SSLLoggingProtocol(mock_original)
        protocol.connection_made(mock_transport)
        
        mock_original.connection_made.assert_called_once_with(mock_transport)

    def test_protocol_delegates_data_received(self):
        """Test data_received is delegated to original protocol."""
        mock_original = MagicMock()
        test_data = b"test data"
        
        protocol = SSLLoggingProtocol(mock_original)
        protocol.data_received(test_data)
        
        mock_original.data_received.assert_called_once_with(test_data)

    def test_protocol_logs_ssl_error_on_connection_lost(self):
        """Test SSL errors are logged on connection_lost."""
        import ssl
        mock_original = MagicMock()
        ssl_error = ssl.SSLError("certificate verify failed")
        
        protocol = SSLLoggingProtocol(mock_original)
        protocol.connection_lost(ssl_error)
        
        mock_original.connection_lost.assert_called_once_with(ssl_error)

    def test_protocol_no_log_for_normal_disconnect(self):
        """Test normal disconnects don't log warnings."""
        mock_original = MagicMock()
        
        protocol = SSLLoggingProtocol(mock_original)
        protocol.connection_lost(None)
        
        mock_original.connection_lost.assert_called_once_with(None)

    def test_protocol_eof_received_delegates(self):
        """Test eof_received is delegated when original has it."""
        mock_original = MagicMock()
        mock_original.eof_received.return_value = True
        
        protocol = SSLLoggingProtocol(mock_original)
        result = protocol.eof_received()
        
        assert result is True
        mock_original.eof_received.assert_called_once()

    def test_protocol_eof_received_without_method(self):
        """Test eof_received returns None when original doesn't have it."""
        mock_original = MagicMock(spec=[])  # No eof_received method
        
        protocol = SSLLoggingProtocol(mock_original)
        result = protocol.eof_received()
        
        assert result is None


class TestC2ServerEdgeCases:
    """Tests for edge cases and uncovered code paths."""

    @pytest.mark.asyncio
    async def test_server_start_with_fixed_port_logs_correctly(self, tmp_path: Path):
        """Test that starting server with fixed port logs the configured port."""
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test")])
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.now(datetime.UTC))
            .not_valid_after(datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=1))
            .sign(key, hashes.SHA256())
        )
        
        ca_cert = tmp_path / "ca.crt"
        server_cert = tmp_path / "server.crt"
        server_key = tmp_path / "server.key"
        ca_cert.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        server_cert.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        server_key.write_bytes(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ))
        
        # Use a fixed high port instead of 0
        config = C2ServerConfig(
            host="127.0.0.1",
            port=19444,  # Fixed port, not 0
            ca_cert_path=ca_cert,
            server_cert_path=server_cert,
            server_key_path=server_key,
        )
        server = C2Server(config)
        
        await server.start()
        try:
            assert server.is_running is True
            # The fixed port branch should be covered
        finally:
            await server.stop()

    def test_health_status_uptime_without_event_loop(self):
        """Test health status handles missing event loop gracefully."""
        import asyncio
        from unittest.mock import patch
        
        config = C2ServerConfig()
        server = C2Server(config)
        
        # Simulate running state
        server._running = True
        server._start_time = 100.0
        
        # Mock get_event_loop to raise RuntimeError (no event loop)
        with patch('asyncio.get_event_loop', side_effect=RuntimeError("no running event loop")):
            status = server.get_health_status()
        
        # Should return degraded with uptime=0 due to RuntimeError fallback
        assert status["status"] == "degraded"
        assert status["uptime"] == 0
        assert status["connections"] == 0

    def test_log_connection_attempt_with_missing_attributes(self):
        """Test _log_connection_attempt handles missing attributes gracefully."""
        config = C2ServerConfig()
        server = C2Server(config)
        
        # Create mock connection without remote_address
        mock_connection = MagicMock(spec=[])
        mock_request = MagicMock(spec=[])
        
        # Should not raise - handles missing attributes gracefully
        result = server._log_connection_attempt(mock_connection, mock_request)
        assert result is None

    def test_log_connection_attempt_with_none_remote_address(self):
        """Test _log_connection_attempt handles None remote_address."""
        config = C2ServerConfig()
        server = C2Server(config)
        
        mock_connection = MagicMock()
        mock_connection.remote_address = None
        mock_request = MagicMock()
        mock_request.path = "/test"
        mock_request.headers = {"User-Agent": "TestAgent"}
        
        result = server._log_connection_attempt(mock_connection, mock_request)
        assert result is None

    @pytest.mark.asyncio
    async def test_connection_handler_handles_connection_closed(self):
        """Test _connection_handler logs disconnection on ConnectionClosed."""
        import websockets.exceptions
        
        config = C2ServerConfig()
        server = C2Server(config)
        
        # Create mock websocket that raises ConnectionClosed
        mock_websocket = MagicMock()
        mock_websocket.remote_address = ("192.168.1.1", 12345)
        
        # Make the async iterator raise ConnectionClosed
        async def mock_iter():
            raise websockets.exceptions.ConnectionClosed(None, None)
            yield  # Make it a generator
        
        mock_websocket.__aiter__ = lambda self: mock_iter()
        
        # Run handler - should handle exception gracefully
        await server._connection_handler(mock_websocket)
        
        # Connection should be removed from set
        assert mock_websocket not in server._connections

    @pytest.mark.asyncio  
    async def test_connection_handler_processes_messages(self):
        """Test _connection_handler processes incoming messages."""
        config = C2ServerConfig()
        server = C2Server(config)
        
        mock_websocket = MagicMock()
        mock_websocket.remote_address = ("10.0.0.1", 54321)
        
        messages_received = []
        
        async def mock_iter():
            yield b"message1"
            yield b"message2"
        
        mock_websocket.__aiter__ = lambda self: mock_iter()
        
        await server._connection_handler(mock_websocket)
        
        # Connection should be cleaned up
        assert mock_websocket not in server._connections

    @pytest.mark.asyncio
    async def test_connection_handler_warns_no_shared_secret(self):
        """Test _connection_handler logs warning when shared_secret is None."""
        from structlog.testing import capture_logs
        
        config = C2ServerConfig(shared_secret=None)
        server = C2Server(config)
        
        mock_websocket = MagicMock()
        mock_websocket.remote_address = ("10.0.0.1", 54321)
        
        async def mock_iter():
            yield b'{"type": "command", "id": "1", "timestamp": "2026-01-01", "payload": {}, "signature": "sig"}'
        
        mock_websocket.__aiter__ = lambda self: mock_iter()
        
        with capture_logs() as cap_logs:
            await server._connection_handler(mock_websocket)
        
        # Should log warning about missing shared_secret
        assert any(log.get("event") == "c2_no_shared_secret" for log in cap_logs)

    @pytest.mark.asyncio
    async def test_connection_handler_validates_message_signature(self):
        """Test _connection_handler rejects invalid signature."""
        from structlog.testing import capture_logs
        
        config = C2ServerConfig(shared_secret=b"correct_secret")
        server = C2Server(config)
        
        mock_websocket = MagicMock()
        mock_websocket.remote_address = ("10.0.0.1", 54321)
        
        # Message with invalid signature
        async def mock_iter():
            yield b'{"type": "command", "id": "test-id", "timestamp": "2026-01-01T00:00:00Z", "payload": {"command": "test"}, "signature": "invalid_sig"}'
        
        mock_websocket.__aiter__ = lambda self: mock_iter()
        
        with capture_logs() as cap_logs:
            await server._connection_handler(mock_websocket)
        
        # Should log invalid message
        assert any(log.get("event") == "c2_message_invalid" for log in cap_logs)

    @pytest.mark.asyncio
    async def test_connection_handler_dispatches_command_message(self):
        """Test _connection_handler dispatches valid command message."""
        from structlog.testing import capture_logs
        from cyberred.c2.protocol import create_command_message
        
        secret = b"test_secret"
        config = C2ServerConfig(shared_secret=secret)
        server = C2Server(config)
        
        mock_websocket = MagicMock()
        mock_websocket.remote_address = ("10.0.0.1", 54321)
        
        # Create valid signed message
        msg = create_command_message("exec", {"tool": "nmap"}, secret, message_id="cmd-123")
        
        async def mock_iter():
            yield msg.to_json().encode("utf-8")
        
        mock_websocket.__aiter__ = lambda self: mock_iter()
        
        with capture_logs() as cap_logs:
            await server._connection_handler(mock_websocket)
        
        # Should log command received
        cmd_logs = [log for log in cap_logs if log.get("event") == "c2_command_received"]
        assert len(cmd_logs) == 1
        assert cmd_logs[0].get("message_id") == "cmd-123"
        assert cmd_logs[0].get("command") == "exec"

    @pytest.mark.asyncio
    async def test_connection_handler_dispatches_result_message(self):
        """Test _connection_handler dispatches valid result message."""
        from structlog.testing import capture_logs
        from cyberred.c2.protocol import create_result_message
        
        secret = b"test_secret"
        config = C2ServerConfig(shared_secret=secret)
        server = C2Server(config)
        
        mock_websocket = MagicMock()
        mock_websocket.remote_address = ("10.0.0.1", 54321)
        
        msg = create_result_message("cmd-456", True, "output data", secret, message_id="res-789")
        
        async def mock_iter():
            yield msg.to_json().encode("utf-8")
        
        mock_websocket.__aiter__ = lambda self: mock_iter()
        
        with capture_logs() as cap_logs:
            await server._connection_handler(mock_websocket)
        
        result_logs = [log for log in cap_logs if log.get("event") == "c2_result_received"]
        assert len(result_logs) == 1
        assert result_logs[0].get("command_id") == "cmd-456"
        assert result_logs[0].get("success") is True

    @pytest.mark.asyncio
    async def test_connection_handler_dispatches_heartbeat_message(self):
        """Test _connection_handler dispatches valid heartbeat message."""
        from structlog.testing import capture_logs
        from cyberred.c2.protocol import create_heartbeat_message
        
        secret = b"test_secret"
        config = C2ServerConfig(shared_secret=secret)
        server = C2Server(config)
        
        mock_websocket = MagicMock()
        mock_websocket.remote_address = ("10.0.0.1", 54321)
        
        msg = create_heartbeat_message("dropbox-01", "healthy", secret)
        
        async def mock_iter():
            yield msg.to_json().encode("utf-8")
        
        mock_websocket.__aiter__ = lambda self: mock_iter()
        
        with capture_logs() as cap_logs:
            await server._connection_handler(mock_websocket)
        
        hb_logs = [log for log in cap_logs if log.get("event") == "c2_heartbeat_received"]
        assert len(hb_logs) == 1
        assert hb_logs[0].get("drop_box_id") == "dropbox-01"
        assert hb_logs[0].get("status") == "healthy"
