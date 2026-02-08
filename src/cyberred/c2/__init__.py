"""C2 (Command and Control) module for drop box communication.

Provides secure mTLS WebSocket server for drop box C2 communication per FR24.

Usage:
    from cyberred.c2 import C2Server, C2ServerConfig

    config = C2ServerConfig(port=8444)
    server = C2Server(config, ca_store)
    await server.start()

Protocol Usage:
    from cyberred.c2 import C2Message, C2MessageType, create_command_message

    msg = create_command_message("exec", {"tool": "nmap"}, shared_secret)
    json_str = msg.to_json()
"""

from cyberred.c2.protocol import (
    C2Message,
    C2MessageType,
    create_command_message,
    create_heartbeat_message,
    create_result_message,
    sign_payload,
    validate_and_parse_message,
    verify_signature,
)
from cyberred.c2.cert_manager import CertificateManager, CertManagerConfig, IssuedCert
from cyberred.c2.heartbeat_monitor import (
    ConnectionStatus,
    DropBoxConnection,
    HeartbeatMonitor,
    HeartbeatMonitorConfig,
)
from cyberred.c2.server import C2Server, C2ServerConfig
from cyberred.c2.nl_interpreter import (
    DeploymentPlan,
    DropBoxDeploymentInterpreter,
    InterpretationError,
    SUPPORTED_PLATFORMS,
)
from cyberred.c2.deployment_instructions import (
    get_instructions,
    is_mobile_platform,
)
from cyberred.c2.qr_generator import (
    QRPayload,
    generate_deployment_qr,
    generate_qr_for_cert,
    get_cert_fingerprint,
)

__all__ = [
    "CertificateManager",
    "CertManagerConfig",
    "ConnectionStatus",
    "DropBoxConnection",
    "HeartbeatMonitor",
    "HeartbeatMonitorConfig",
    "IssuedCert",
    "C2Server",
    "C2ServerConfig",
    "C2Message",
    "C2MessageType",
    "create_command_message",
    "create_result_message",
    "create_heartbeat_message",
    "sign_payload",
    "verify_signature",
    "validate_and_parse_message",
    # Story 12.8: NL Drop Box Setup
    "DeploymentPlan",
    "DropBoxDeploymentInterpreter",
    "InterpretationError",
    "SUPPORTED_PLATFORMS",
    "get_instructions",
    "is_mobile_platform",
    "QRPayload",
    "generate_deployment_qr",
    "generate_qr_for_cert",
    "get_cert_fingerprint",
]
