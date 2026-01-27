"""AgentRole enum defining all 8 agent roles.

This module provides a centralized enumeration of all agent roles in the
penetration testing swarm. Each role corresponds to a specific behavioral
configuration and prompt.
"""

from enum import Enum


class AgentRole(Enum):
    """Enumeration of all agent roles in the penetration testing swarm.

    Each role has a lowercase string value used for prompt file lookup,
    logging, and decision_context tracking (NFR37).

    Attributes:
        RECON: Discovery and enumeration (network, OSINT, DNS).
        EXPLOIT: Vulnerability exploitation (web, network, service).
        POSTEX: Post-exploitation (Windows, Linux, macOS).
        WEBAPP: Web application testing (OWASP Top 10).
        WIRELESS: Wireless network attacks (WiFi, Bluetooth).
        AD: Active Directory attacks (Kerberos, LDAP).
        CREDENTIAL: Credential harvesting and cracking.
        FORENSICS: Digital forensics and evidence collection.
    """

    RECON = "recon"
    EXPLOIT = "exploit"
    POSTEX = "postex"
    WEBAPP = "webapp"
    WIRELESS = "wireless"
    AD = "ad"
    CREDENTIAL = "credential"
    FORENSICS = "forensics"
