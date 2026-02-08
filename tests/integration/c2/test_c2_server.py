"""Integration tests for C2 server.

Tests mTLS handshake, connection rejection, and health endpoint.
"""

import asyncio
import ipaddress
import ssl
import pytest
from pathlib import Path
from typing import Dict

import websockets

from cyberred.core import CAStore, Keystore, generate_salt
from cyberred.c2 import C2Server, C2ServerConfig


class TestC2ServerMTLS:
    """Integration tests for mTLS functionality (AC: #2, #3, #4, #6)."""

    @pytest.mark.asyncio
    async def test_c2server_start_stop(self, ca_store_with_certs: tuple[CAStore, Dict[str, Path]]):
        """Test server starts and stops cleanly (AC: #1)."""
        ca_store, paths = ca_store_with_certs
        
        config = C2ServerConfig(
            host="127.0.0.1",
            port=0,  # Let OS assign port
            ca_cert_path=paths["ca_cert"],
            server_cert_path=paths["server_cert"],
            server_key_path=paths["server_key"],
        )
        server = C2Server(config, ca_store)
        
        # Start server
        await server.start()
        assert server.is_running is True
        
        # Stop server
        await server.stop()
        assert server.is_running is False

    @pytest.mark.asyncio
    async def test_c2server_mtls_handshake_success(self, ca_store_with_certs: tuple[CAStore, Dict[str, Path]]):
        """Test mTLS handshake succeeds with valid CA-signed certs (AC: #2, #6)."""
        ca_store, paths = ca_store_with_certs
        
        config = C2ServerConfig(
            host="127.0.0.1",
            port=0,
            ca_cert_path=paths["ca_cert"],
            server_cert_path=paths["server_cert"],
            server_key_path=paths["server_key"],
        )
        server = C2Server(config, ca_store)
        
        await server.start()
        try:
            # Get the actual port
            actual_port = server._server.sockets[0].getsockname()[1]
            
            # Create client SSL context with valid certs
            client_ssl = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
            client_ssl.load_verify_locations(cafile=str(paths["ca_cert"]))
            client_ssl.load_cert_chain(
                certfile=str(paths["client_cert"]),
                keyfile=str(paths["client_key"]),
            )
            
            # Connect to server - use localhost as server_hostname to match SAN
            uri = f"wss://127.0.0.1:{actual_port}"
            async with websockets.connect(uri, ssl=client_ssl, server_hostname="localhost") as ws:
                # Connection successful - send a test message
                await ws.send("hello")
                # Just verify connection worked
                assert server.connection_count == 1
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_c2server_rejects_no_cert(self, ca_store_with_certs: tuple[CAStore, Dict[str, Path]]):
        """Test connection rejection with no client cert (AC: #4, #6)."""
        ca_store, paths = ca_store_with_certs
        
        config = C2ServerConfig(
            host="127.0.0.1",
            port=0,
            ca_cert_path=paths["ca_cert"],
            server_cert_path=paths["server_cert"],
            server_key_path=paths["server_key"],
        )
        server = C2Server(config, ca_store)
        
        await server.start()
        try:
            actual_port = server._server.sockets[0].getsockname()[1]
            
            # Create client SSL context WITHOUT client cert
            client_ssl = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
            client_ssl.load_verify_locations(cafile=str(paths["ca_cert"]))
            # Intentionally NOT loading client cert/key
            
            uri = f"wss://127.0.0.1:{actual_port}"
            
            # Should fail because server requires client cert
            with pytest.raises((ssl.SSLError, ConnectionRefusedError, OSError)):
                async with websockets.connect(uri, ssl=client_ssl, server_hostname="c2-server"):
                    pass
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_c2server_rejects_invalid_cert(self, ca_store_with_certs: tuple[CAStore, Dict[str, Path]], tmp_path: Path):
        """Test connection rejection with self-signed (non-CA) client cert (AC: #4, #6)."""
        ca_store, paths = ca_store_with_certs
        
        config = C2ServerConfig(
            host="127.0.0.1",
            port=0,
            ca_cert_path=paths["ca_cert"],
            server_cert_path=paths["server_cert"],
            server_key_path=paths["server_key"],
        )
        server = C2Server(config, ca_store)
        
        # Create a self-signed cert NOT signed by the CA
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        import datetime
        
        rogue_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        rogue_cert = (
            x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "rogue-client")]))
            .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "rogue-client")]))
            .public_key(rogue_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.now(datetime.UTC))
            .not_valid_after(datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=1))
            .sign(rogue_key, hashes.SHA256())
        )
        
        rogue_cert_path = tmp_path / "rogue.crt"
        rogue_key_path = tmp_path / "rogue.key"
        rogue_cert_path.write_bytes(rogue_cert.public_bytes(serialization.Encoding.PEM))
        rogue_key_path.write_bytes(rogue_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ))
        
        await server.start()
        try:
            actual_port = server._server.sockets[0].getsockname()[1]
            
            # Create client SSL context with rogue cert
            client_ssl = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
            client_ssl.load_verify_locations(cafile=str(paths["ca_cert"]))
            client_ssl.load_cert_chain(
                certfile=str(rogue_cert_path),
                keyfile=str(rogue_key_path),
            )
            
            uri = f"wss://127.0.0.1:{actual_port}"
            
            # Should fail because client cert is not signed by the CA
            with pytest.raises((ssl.SSLError, ConnectionRefusedError, OSError)):
                async with websockets.connect(uri, ssl=client_ssl, server_hostname="c2-server"):
                    pass
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_c2server_rejects_expired_cert(self, tmp_path: Path):
        """Test connection rejection with expired client cert (AC: #4, #6)."""
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        import datetime
        
        # Create CA
        ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        ca_cert = (
            x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test CA")]))
            .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test CA")]))
            .public_key(ca_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=365))
            .not_valid_after(datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=365))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .sign(ca_key, hashes.SHA256())
        )
        
        # Create server cert (valid)
        server_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        server_cert = (
            x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "c2-server")]))
            .issuer_name(ca_cert.subject)
            .public_key(server_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.now(datetime.UTC))
            .not_valid_after(datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=30))
            .add_extension(
                x509.SubjectAlternativeName([
                    x509.DNSName("localhost"),
                    x509.DNSName("c2-server"),
                    x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                ]),
                critical=False,
            )
            .sign(ca_key, hashes.SHA256())
        )
        
        # Create expired client cert
        client_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        expired_client_cert = (
            x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "expired-client")]))
            .issuer_name(ca_cert.subject)
            .public_key(client_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=30))
            .not_valid_after(datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=1))  # EXPIRED
            .sign(ca_key, hashes.SHA256())
        )
        
        # Save certs
        paths = {
            "ca_cert": tmp_path / "ca.crt",
            "server_cert": tmp_path / "server.crt",
            "server_key": tmp_path / "server.key",
            "client_cert": tmp_path / "expired_client.crt",
            "client_key": tmp_path / "expired_client.key",
        }
        paths["ca_cert"].write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))
        paths["server_cert"].write_bytes(server_cert.public_bytes(serialization.Encoding.PEM))
        paths["server_key"].write_bytes(server_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ))
        paths["client_cert"].write_bytes(expired_client_cert.public_bytes(serialization.Encoding.PEM))
        paths["client_key"].write_bytes(client_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ))
        
        config = C2ServerConfig(
            host="127.0.0.1",
            port=0,
            ca_cert_path=paths["ca_cert"],
            server_cert_path=paths["server_cert"],
            server_key_path=paths["server_key"],
        )
        server = C2Server(config)
        
        await server.start()
        try:
            actual_port = server._server.sockets[0].getsockname()[1]
            
            client_ssl = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
            client_ssl.load_verify_locations(cafile=str(paths["ca_cert"]))
            client_ssl.load_cert_chain(
                certfile=str(paths["client_cert"]),
                keyfile=str(paths["client_key"]),
            )
            
            uri = f"wss://127.0.0.1:{actual_port}"
            
            # Should fail due to expired certificate - connection gets rejected
            # Can manifest as various SSL/connection errors
            with pytest.raises((ssl.SSLError, ConnectionRefusedError, OSError, websockets.exceptions.InvalidMessage, EOFError)):
                async with websockets.connect(uri, ssl=client_ssl, server_hostname="localhost"):
                    pass
        finally:
            await server.stop()


class TestC2ServerHealth:
    """Integration tests for health endpoint (AC: #5)."""

    @pytest.mark.asyncio
    async def test_c2server_health_endpoint(self, ca_store_with_certs: tuple[CAStore, Dict[str, Path]]):
        """Test health endpoint returns correct JSON (AC: #5)."""
        ca_store, paths = ca_store_with_certs
        
        config = C2ServerConfig(
            host="127.0.0.1",
            port=0,
            ca_cert_path=paths["ca_cert"],
            server_cert_path=paths["server_cert"],
            server_key_path=paths["server_key"],
        )
        server = C2Server(config, ca_store)
        
        # Before start - error status
        status = server.get_health_status()
        assert status["status"] == "error"
        assert status["connections"] == 0
        
        await server.start()
        try:
            # Running but no connections - degraded
            status = server.get_health_status()
            assert status["status"] == "degraded"
            assert status["connections"] == 0
            assert "uptime" in status
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_c2server_multiple_connections(self, ca_store_with_certs: tuple[CAStore, Dict[str, Path]]):
        """Test server handles multiple concurrent connections (AC: #6)."""
        ca_store, paths = ca_store_with_certs
        
        config = C2ServerConfig(
            host="127.0.0.1",
            port=0,
            ca_cert_path=paths["ca_cert"],
            server_cert_path=paths["server_cert"],
            server_key_path=paths["server_key"],
        )
        server = C2Server(config, ca_store)
        
        await server.start()
        try:
            actual_port = server._server.sockets[0].getsockname()[1]
            
            client_ssl = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
            client_ssl.load_verify_locations(cafile=str(paths["ca_cert"]))
            client_ssl.load_cert_chain(
                certfile=str(paths["client_cert"]),
                keyfile=str(paths["client_key"]),
            )
            
            uri = f"wss://127.0.0.1:{actual_port}"
            
            # Open multiple connections - use localhost to match SAN
            async with websockets.connect(uri, ssl=client_ssl, server_hostname="localhost") as ws1:
                assert server.connection_count == 1
                
                async with websockets.connect(uri, ssl=client_ssl, server_hostname="localhost") as ws2:
                    assert server.connection_count == 2
                    
                    # Health should be healthy with connections
                    status = server.get_health_status()
                    assert status["status"] == "healthy"
                    assert status["connections"] == 2
                
                # After ws2 closes
                await asyncio.sleep(0.1)  # Allow cleanup
                assert server.connection_count == 1
            
            # After both close
            await asyncio.sleep(0.1)
            assert server.connection_count == 0
        finally:
            await server.stop()
