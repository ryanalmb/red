import asyncio
import xml.etree.ElementTree as ET
import logging

class NmapAdapter:
    def __init__(self, worker_pool):
        self.worker_pool = worker_pool
        self.logger = logging.getLogger("NmapAdapter")

    async def scan_target(self, target_ip, ports="1-1000"):
        """
        Runs nmap and returns structured data.
        """
        cmd = f"nmap -p {ports} -sV -oX - {target_ip}"
        
        self.logger.info(f"Scanning {target_ip}...")
        xml_output = await self.worker_pool.execute_task(cmd, "nmap")
        
        if "ERROR" in xml_output:
            self.logger.error(f"Nmap Failed: {xml_output}")
            return []

        return self._parse_xml(xml_output)

    def _parse_xml(self, xml_string):
        """Parses Nmap XML output into a list of open ports."""
        try:
            root = ET.fromstring(xml_string)
            results = []
            
            for host in root.findall('host'):
                ip = host.find('address').get('addr')
                ports = host.find('ports')
                
                if ports:
                    for port in ports.findall('port'):
                        state = port.find('state').get('state')
                        if state == 'open':
                            port_id = port.get('portid')
                            service = port.find('service').get('name')
                            results.append({
                                "ip": ip,
                                "port": port_id,
                                "service": service
                            })
            return results
        except Exception as e:
            self.logger.error(f"XML Parse Error: {e}")
            return []
