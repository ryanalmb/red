"""Tier 1 Parser definitions."""

# Existing parsers (Stories 4.5-4.9)
from .nmap import nmap_parser
from .nuclei import nuclei_parser
from .sqlmap import sqlmap_parser
from .ffuf import ffuf_parser
from .nikto import nikto_parser
from .hydra import hydra_parser

# Reconnaissance parsers (Story 4.10)
from .masscan import masscan_parser
from .subfinder import subfinder_parser
from .amass import amass_parser
from .whatweb import whatweb_parser
from .wafw00f import wafw00f_parser
from .dnsrecon import dnsrecon_parser
from .theharvester import theharvester_parser
from .gobuster import gobuster_parser

# Exploitation parsers (Story 4.10)
from .crackmapexec import crackmapexec_parser
from .responder import responder_parser
from .secretsdump import secretsdump_parser
from .psexec import psexec_parser
from .metasploit import metasploit_parser
from .searchsploit import searchsploit_parser

# Post-exploitation parsers (Story 4.10)
from .mimikatz import mimikatz_parser
from .bloodhound import bloodhound_parser
from .linpeas import linpeas_parser
from .winpeas import winpeas_parser
from .lazagne import lazagne_parser
from .chisel import chisel_parser

# Wireless parsers (Story 4.10)
from .aircrack import aircrack_parser
from .wifite import wifite_parser

# Credential parsers (Story 4.10)
from .john import john_parser
from .hashcat import hashcat_parser

__all__ = [
    # Original parsers (6)
    'nmap_parser', 
    'nuclei_parser', 
    'sqlmap_parser',
    'ffuf_parser',
    'nikto_parser',
    'hydra_parser',
    # Reconnaissance parsers (8)
    'masscan_parser',
    'subfinder_parser',
    'amass_parser',
    'whatweb_parser',
    'wafw00f_parser',
    'dnsrecon_parser',
    'theharvester_parser',
    'gobuster_parser',
    # Exploitation parsers (6)
    'crackmapexec_parser',
    'responder_parser',
    'secretsdump_parser',
    'psexec_parser',
    'metasploit_parser',
    'searchsploit_parser',
    # Post-exploitation parsers (6)
    'mimikatz_parser',
    'bloodhound_parser',
    'linpeas_parser',
    'winpeas_parser',
    'lazagne_parser',
    'chisel_parser',
    # Wireless parsers (2)
    'aircrack_parser',
    'wifite_parser',
    # Credential parsers (2)
    'john_parser',
    'hashcat_parser',
]
