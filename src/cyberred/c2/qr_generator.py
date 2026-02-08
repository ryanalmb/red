"""QR Code Generator for Drop Box Deployment.

Story 12.8: Natural Language Drop Box Setup - Task 6

Generates QR codes for mobile deployment containing C2 URL and cert fingerprint.

Usage:
    from cyberred.c2.qr_generator import generate_deployment_qr, QRPayload
    
    payload = QRPayload(c2_url="wss://c2.example.com:8444", cert_fingerprint="sha256:abc123", drop_box_id="android-dropbox")
    ascii_qr = generate_deployment_qr(payload)
"""

from __future__ import annotations

import hashlib
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import structlog

log = structlog.get_logger()


@dataclass
class QRPayload:
    """QR code payload for mobile deployment.
    
    Attributes:
        c2_url: C2 server WebSocket URL.
        cert_fingerprint: SHA256 fingerprint of client certificate.
        drop_box_id: Unique drop box identifier.
    """
    c2_url: str
    cert_fingerprint: str
    drop_box_id: str
    
    def to_json(self) -> str:
        """Serialize payload to JSON string.
        
        Returns:
            JSON string representation.
        """
        return json.dumps({
            "c2_url": self.c2_url,
            "cert_fingerprint": self.cert_fingerprint,
            "drop_box_id": self.drop_box_id,
        })


def get_cert_fingerprint(cert_path: Path) -> str:
    """Calculate SHA256 fingerprint of a certificate.
    
    Args:
        cert_path: Path to PEM certificate file.
        
    Returns:
        Fingerprint string in format "sha256:hexdigest".
        
    Raises:
        FileNotFoundError: If certificate file not found.
    """
    cert_bytes = cert_path.read_bytes()
    
    # For PEM, we hash the DER content
    # Extract the base64 content between BEGIN/END markers
    import base64
    lines = cert_bytes.decode('utf-8').strip().split('\n')
    der_lines = [l for l in lines if not l.startswith('-----')]
    der_content = base64.b64decode(''.join(der_lines))
    
    fingerprint = hashlib.sha256(der_content).hexdigest()
    return f"sha256:{fingerprint}"


def generate_deployment_qr(payload: QRPayload) -> str:
    """Generate ASCII QR code for terminal display.
    
    Args:
        payload: QRPayload with deployment information.
        
    Returns:
        ASCII art QR code string.
    """
    try:
        import qrcode
        from qrcode.constants import ERROR_CORRECT_M
    except ImportError:
        log.warning("qrcode_library_not_installed")
        return _generate_fallback_qr(payload)
    
    # Create QR code
    qr = qrcode.QRCode(
        version=None,  # Auto-size
        error_correction=ERROR_CORRECT_M,
        box_size=1,
        border=1,
    )
    
    qr.add_data(payload.to_json())
    qr.make(fit=True)
    
    # Generate ASCII representation
    ascii_qr = _qr_to_ascii(qr)
    
    log.info("qr_code_generated", drop_box_id=payload.drop_box_id)
    
    return ascii_qr


def _qr_to_ascii(qr) -> str:
    """Convert QR code to ASCII art using Unicode block characters.
    
    Uses Unicode block elements for better terminal rendering:
    - Full block (█) for black modules
    - Space for white modules
    
    Args:
        qr: qrcode.QRCode instance.
        
    Returns:
        ASCII art string.
    """
    # Get the matrix
    matrix = qr.get_matrix()
    
    lines = []
    for row in matrix:
        line = ""
        for cell in row:
            if cell:
                line += "██"  # Full block for black
            else:
                line += "  "  # Space for white
        lines.append(line)
    
    return "\n".join(lines)


def _generate_fallback_qr(payload: QRPayload) -> str:
    """Generate fallback display when qrcode library not available.
    
    Args:
        payload: QRPayload with deployment information.
        
    Returns:
        Text-based fallback with manual configuration info.
    """
    return f"""
┌─────────────────────────────────────────┐
│  QR Code Library Not Installed          │
│                                         │
│  Install with: pip install qrcode       │
│                                         │
│  Manual Configuration:                  │
│  C2 URL: {payload.c2_url:<30} │
│  Drop Box ID: {payload.drop_box_id:<25} │
│  Cert Fingerprint:                      │
│  {payload.cert_fingerprint:<39} │
└─────────────────────────────────────────┘
"""


def generate_qr_for_cert(
    c2_url: str,
    cert_path: Path,
    drop_box_id: str,
) -> str:
    """Generate QR code from certificate file.
    
    Convenience function that calculates fingerprint and generates QR.
    
    Args:
        c2_url: C2 server URL.
        cert_path: Path to client certificate.
        drop_box_id: Drop box identifier.
        
    Returns:
        ASCII QR code string.
    """
    fingerprint = get_cert_fingerprint(cert_path)
    payload = QRPayload(
        c2_url=c2_url,
        cert_fingerprint=fingerprint,
        drop_box_id=drop_box_id,
    )
    return generate_deployment_qr(payload)
