"""Intelligence Sources Package.

This package contains implementations of the IntelligenceSource interface
for various vulnerability intelligence sources.

Sources:
    CisaKevSource: CISA Known Exploited Vulnerabilities catalog
    NvdSource: National Vulnerability Database (NVD) API integration
    ExploitDbSource: ExploitDB/searchsploit local database integration
    NucleiSource: Nuclei template index for vulnerability detection templates
    MetasploitSource: Metasploit Framework modules
"""

from cyberred.intelligence.sources.cisa_kev import CisaKevSource, KevCatalog, KevEntry
from cyberred.intelligence.sources.nvd import NvdCveEntry, NvdSource, get_nvd_priority
from cyberred.intelligence.sources.exploitdb import ExploitDbSource, ExploitEntry
from cyberred.intelligence.sources.nuclei import NucleiSource, NucleiTemplate
from cyberred.intelligence.sources.metasploit import MetasploitSource, MsfModuleEntry
from cyberred.intelligence.aggregator import IntelligenceAggregator

__all__ = [
    "CisaKevSource",
    "KevCatalog",
    "KevEntry",
    "NvdCveEntry",
    "NvdSource",
    "get_nvd_priority",
    "ExploitDbSource",
    "ExploitEntry",
    "NucleiSource",
    "NucleiTemplate",
    "MetasploitSource",
    "MsfModuleEntry",
    "IntelligenceAggregator",
]
