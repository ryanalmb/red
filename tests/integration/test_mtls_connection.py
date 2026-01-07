"""Integration test for mTLS connection using CAStore generated certificates.

Verifies Task 12: "Test key + cert can establish mTLS connection".
"""

import socket
import ssl
import threading
import time
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import serialization

from cyberred.core import CAStore, Keystore, generate_salt


def test_mtls_connection_success(tmp_path):
    """Verify that generated certificates can establish a valid mTLS connection."""
    
    # 1. Setup CA and Certs
    # ---------------------
    salt = generate_salt()
    keystore = Keystore.from_password("test_pass", salt)
    ca_store = CAStore(keystore)
    ca_store.generate_ca("Test Root CA")

    # Generate Server Cert (valid for localhost)
    server_cert, server_key = ca_store.generate_cert(
        common_name="localhost",
        san_names=["localhost", "127.0.0.1"]
    )
    
    # Generate Client Cert
    client_cert, client_key = ca_store.generate_cert(
        common_name="client-user",
        san_names=["client"]
    )

    # Save to files for SSLContext (ssl module needs files or loaded context)
    # We will use load_cert_chain with files for simplicity or context.load_verify_locations
    
    # Paths
    ca_cert_path = tmp_path / "ca.crt"
    server_cert_path = tmp_path / "server.crt"
    server_key_path = tmp_path / "server.key"
    client_cert_path = tmp_path / "client.crt"
    client_key_path = tmp_path / "client.key"

    # Write CA Cert
    ca_cert_path.write_bytes(ca_store.serialize_cert_pem(ca_store._ca_cert))
    
    # Write Server Cert & Key
    server_cert_path.write_bytes(ca_store.serialize_cert_pem(server_cert))
    server_key_path.write_bytes(ca_store.serialize_key_pem(server_key))
    
    # Write Client Cert & Key
    client_cert_path.write_bytes(ca_store.serialize_cert_pem(client_cert))
    client_key_path.write_bytes(ca_store.serialize_key_pem(client_key))

    # 2. Start TLS Server
    # -------------------
    server_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    server_context.verify_mode = ssl.CERT_REQUIRED
    server_context.load_verify_locations(cafile=str(ca_cert_path))
    server_context.load_cert_chain(certfile=str(server_cert_path), keyfile=str(server_key_path))

    bind_port = 0  # Let OS choose
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.bind(('127.0.0.1', 0))
    server_sock.listen(1)
    server_port = server_sock.getsockname()[1]
    
    server_ready = threading.Event()
    server_msg = b"SERVER_HELLO"
    received_by_server = []

    def run_server():
        try:
            server_ready.set()
            conn, addr = server_sock.accept()
            with server_context.wrap_socket(conn, server_side=True) as ssl_conn:
                data = ssl_conn.recv(1024)
                received_by_server.append(data)
                ssl_conn.sendall(server_msg)
        except Exception as e:
            received_by_server.append(e)
        finally:
            server_sock.close()

    server_thread = threading.Thread(target=run_server)
    server_thread.start()
    
    server_ready.wait()

    # 3. Connect with TLS Client
    # --------------------------
    client_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    client_context.load_verify_locations(cafile=str(ca_cert_path))
    client_context.load_cert_chain(certfile=str(client_cert_path), keyfile=str(client_key_path))
    
    # Client connects
    client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with client_context.wrap_socket(client_sock, server_hostname="localhost") as ssl_client:
            ssl_client.connect(('127.0.0.1', server_port))
            ssl_client.sendall(b"CLIENT_HELLO")
            response = ssl_client.recv(1024)
            assert response == server_msg
    finally:
        server_thread.join(timeout=2)

    assert len(received_by_server) == 1
    assert received_by_server[0] == b"CLIENT_HELLO"
