import os
import asyncio
import structlog
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Union

from pymetasploit3.msfrpc import MsfRpcClient, MsfRpcError

from cyberred.intelligence.base import IntelligenceSource, IntelResult, IntelPriority

log = structlog.get_logger()

@dataclass
class MsfModuleEntry:
    """Normalized Metasploit module entry.
    
    Maps Metasploit RPC module data to flat structure for IntelResult conversion.
    
    Attributes:
        module_path: Full module path (e.g., "exploit/multi/http/tomcat_mgr_deploy")
        name: Human-readable module name
        rank: Module rank (excellent, great, good, normal, average, low, manual)
        disclosure_date: Vulnerability disclosure date (YYYY-MM-DD)
        cve_ids: List of associated CVE IDs
        description: Module description
        platform: Target platform(s) (e.g., "linux", "windows", "multi")
        arch: Target architecture(s) (e.g., "x86", "x64", "java")
        ref_names: List of reference names (CVE, EDB, URL, etc.)
    """
    module_path: str
    name: str
    rank: str
    disclosure_date: str
    cve_ids: List[str]
    description: str = ""
    platform: str = ""
    arch: str = ""
    ref_names: List[str] = field(default_factory=list)

    @classmethod
    def from_rpc_result(cls, module_path: str, info: Any) -> "MsfModuleEntry":
        """Parse Metasploit module info from RPC result.
        
        Args:
            module_path: Full module path.
            info: Module info dictionary or object from RPC.
            
        Returns:
            MsfModuleEntry with extracted fields.
        """
        def get_val(obj, key, default=None):
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)

        # Extract CVE IDs from references
        cve_ids = []
        ref_names = []
        
        references = get_val(info, "references", [])
        # References can be list of lists: [['CVE', '2017-9805'], ['URL', '...']]
        for ref in references:
            if isinstance(ref, (list, tuple)) and len(ref) >= 2:
                ref_type, ref_id = ref[0], ref[1]
                ref_names.append(f"{ref_type}-{ref_id}")
                if str(ref_type).upper() == "CVE":
                    cve_ids.append(f"CVE-{ref_id}")
        
        # Extract platform (can be list or string)
        platform = get_val(info, "platform", "")
        if isinstance(platform, list):
            platform = ",".join(platform)
        
        # Extract arch (can be list or string)
        arch = get_val(info, "arch", "")
        if isinstance(arch, list):
            arch = ",".join(arch)
            
        # disclosure_date might be datetime or string
        disclosure_date = get_val(info, "disclosure_date", "")
        if not isinstance(disclosure_date, str):
            disclosure_date = str(disclosure_date or "")
        
        return cls(
            module_path=module_path,
            name=get_val(info, "name", module_path.split("/")[-1]),
            rank=str(get_val(info, "rank", "normal")),
            disclosure_date=disclosure_date,
            cve_ids=cve_ids,
            description=get_val(info, "description", ""),
            platform=platform,
            arch=arch,
            ref_names=ref_names,
        )

class MetasploitSource(IntelligenceSource):
    """Metasploit RPC intelligence source.
    
    Queries Metasploit via msfrpcd RPC for available exploit modules
    matching discovered services/versions.
    
    Requires:
        - msfrpcd running (default port 55553)
        - Valid RPC password
        - pymetasploit3 library
    
    Configuration:
        - MSF_RPC_HOST: RPC server host (default: 127.0.0.1)
        - MSF_RPC_PORT: RPC server port (default: 55553)
        - MSF_RPC_PASSWORD: RPC authentication password
    """
    
    def __init__(
        self,
        password: Optional[str] = None,
        host: str = "127.0.0.1",
        port: int = 55553,
        timeout: float = 30.0,
        ssl: bool = True,
    ) -> None:
        super().__init__(
            name="metasploit",
            timeout=timeout,
            priority=IntelPriority.METASPLOIT,
        )
        self._password = password or os.environ.get("MSF_RPC_PASSWORD", "")
        self._host = host or os.environ.get("MSF_RPC_HOST", "127.0.0.1")
        self._port = int(os.environ.get("MSF_RPC_PORT", port))
        self._ssl = ssl
        self._client: Optional[MsfRpcClient] = None

    def _get_client(self) -> MsfRpcClient:
        """Get or create RPC client connection.
        
        Per architecture: Connection pool maintains 5 concurrent connections.
        For MVP, single connection with reconnection on failure.
        
        Returns:
            Connected MsfRpcClient instance.
            
        Raises:
            MsfRpcConnectionError: If connection fails.
        """
        if self._client is None:
            try:
                self._client = MsfRpcClient(
                    password=self._password,
                    server=self._host,
                    port=self._port,
                    ssl=self._ssl,
                )
                log.info("metasploit_connected", host=self._host, port=self._port)
            except Exception as e:
                log.warning("metasploit_connection_failed", error=str(e))
                raise
        return self._client

    async def query(self, service: str, version: str) -> List[IntelResult]:
        """Query Metasploit for modules affecting service/version.
        
        Uses Metasploit RPC to search for exploit, auxiliary, and post
        modules matching the service name and version.
        
        Args:
            service: Service name (e.g., "Apache Tomcat", "vsftpd")
            version: Version string (e.g., "9.0.30", "2.3.4")
            
        Returns:
            List of IntelResult sorted by module rank.
            Empty list on any error.
        """
        log.info("metasploit_query_start", service=service, version=version)
        
        try:
            # RPC calls are synchronous - run in executor
            loop = asyncio.get_event_loop()
            modules = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: self._search_modules(service, version)
                ),
                timeout=self._timeout,
            )
            
            results = [self._to_intel_result(m) for m in modules]
            
            # Sort by rank (excellent first)
            rank_order = {
                "excellent": 0, "great": 1, "good": 2, 
                "normal": 3, "average": 4, "low": 5, "manual": 6
            }
            results.sort(key=lambda r: rank_order.get(
                r.metadata.get("rank", "manual"), 7
            ))
            
            log.info("metasploit_query_complete", result_count=len(results))
            return results
            
        except Exception as e:
            log.warning("metasploit_query_error", error=str(e))
            return []

    def _search_modules(self, service: str, version: str) -> List[MsfModuleEntry]:
        """Search Metasploit modules matching service/version.
        
        Searches exploits, auxiliary, and post modules.
        
        Args:
            service: Service name to match.
            version: Version string to match.
            
        Returns:
            List of matching MsfModuleEntry objects.
        """
        client = self._get_client()
        matches: List[MsfModuleEntry] = []
        
        search_term = f"{service} {version}".lower().strip()
        
        # Search each module type
        for module_type in ["exploits", "auxiliary"]:
            try:
                module_list = getattr(client.modules, module_type)
                for module_path in module_list:
                    # Filter by keyword match in path
                    if not self._matches_search(module_path, search_term):
                        continue
                    
                    # Get detailed module info
                    try:
                        info = client.modules.use(module_type.rstrip('s'), module_path)
                        entry = MsfModuleEntry.from_rpc_result(module_path, info)
                        matches.append(entry)
                    except Exception as e:
                        log.debug("msf_module_info_error", path=module_path, error=str(e))
                        continue
                        
            except Exception as e:
                log.debug("msf_module_list_error", type=module_type, error=str(e))
                continue
        
        return matches
    
    def _matches_search(self, module_path: str, search_term: str) -> bool:
        """Check if module path matches search term.
        
        Args:
            module_path: Module path (e.g., "exploit/multi/http/tomcat_mgr_deploy")
            search_term: Lowercase search term.
            
        Returns:
            True if any search keyword appears in module path.
        """
        path_lower = module_path.lower()
        keywords = search_term.split()
        return any(kw in path_lower for kw in keywords)

    def _to_intel_result(self, entry: MsfModuleEntry) -> IntelResult:
        """Convert Metasploit module entry to IntelResult.
        
        Args:
            entry: Parsed Metasploit module entry.
            
        Returns:
            IntelResult with Metasploit-specific metadata.
        """
        # First CVE ID or None
        cve_id = entry.cve_ids[0] if entry.cve_ids else None
        
        # Map rank to severity
        severity = self._rank_to_severity(entry.rank)
        
        return IntelResult(
            source="metasploit",
            cve_id=cve_id,
            severity=severity,
            exploit_available=True,  # MSF module = exploit available
            exploit_path=entry.module_path,
            confidence=0.85,  # High confidence for MSF modules
            priority=IntelPriority.METASPLOIT,
            metadata={
                "module_path": entry.module_path,
                "name": entry.name,
                "rank": entry.rank,
                "disclosure_date": entry.disclosure_date,
                "cve_ids": entry.cve_ids,
                "description": entry.description,
                "platform": entry.platform,
                "arch": entry.arch,
                "ref_names": entry.ref_names,
            },
        )

    def _rank_to_severity(self, rank: str) -> str:
        """Map Metasploit module rank to severity string.
        
        Metasploit ranks indicate exploit reliability:
        - excellent: Exploit is reliable, no special conditions
        - great/good: Exploit works in most cases
        - normal/average: May require specific conditions
        - low/manual: Unreliable or requires manual interaction
        
        Args:
            rank: Metasploit module rank.
            
        Returns:
            Severity string: "critical", "high", "medium", or "low".
        """
        rank_lower = rank.lower()
        severity_map = {
            "excellent": "critical",
            "great": "high",
            "good": "high",
            "normal": "medium",
            "average": "medium",
            "low": "low",
            "manual": "low",
        }
        return severity_map.get(rank_lower, "medium")

    async def health_check(self) -> bool:
        """Check if Metasploit RPC is available.
        
        Returns:
            True if msfrpcd is reachable and auth succeeds, False otherwise.
        """
        try:
            loop = asyncio.get_event_loop()
            await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    self._get_client
                ),
                timeout=self._timeout,
            )
            return True
        except Exception:
            return False
