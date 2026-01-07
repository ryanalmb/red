import pytest
import os
import re
import uuid
from cyberred.tools.output import OutputProcessor
from cyberred.llm import initialize_gateway, shutdown_gateway


def strip_markdown_json(content: str) -> str:
    """Strip markdown code fences from LLM response if present.
    
    LLMs often wrap JSON in ```json ... ``` blocks.
    """
    # Remove leading/trailing whitespace
    content = content.strip()
    # Check for markdown code fence
    if content.startswith("```"):
        # Find the end of the first line (language specifier)
        first_newline = content.find("\n")
        if first_newline != -1:
            # Remove opening fence
            content = content[first_newline + 1:]
        # Remove closing fence
        if content.endswith("```"):
            content = content[:-3].strip()
    return content

@pytest.mark.integration
@pytest.mark.requires_nim
class TestTier2RealNIMAPI:
    """Integration tests with real NIM API."""
    
    @pytest.fixture(autouse=True)
    async def setup_gateway(self):
        """Initialize real gateway for tests (skip if no key)."""
        api_key = os.getenv("NVIDIA_API_KEY")
        if not api_key:
            pytest.skip("No NVIDIA_API_KEY found")
            
        from cyberred.llm import (
            RateLimiter, ModelRouter, LLMPriorityQueue, 
            NIMProvider, TaskComplexity
        )
            
        # Initialize dependencies
        rate_limiter = RateLimiter(rpm=30)
        queue = LLMPriorityQueue()
        
        # Setup providers
        # We need to map TaskComplexity enum to NIMProvider
        # Note: NIMProvider.for_tier takes string "FAST", "STANDARD", etc.
        nim_fast = NIMProvider.for_tier("FAST", api_key)
        nim_standard = NIMProvider.for_tier("STANDARD", api_key)
        
        providers = {
            TaskComplexity.FAST: nim_fast,
            TaskComplexity.STANDARD: nim_standard,
            TaskComplexity.COMPLEX: nim_standard # reuse standard for complex if needed or just minimal set
        }
        
        router = ModelRouter(providers=providers, default_tier=TaskComplexity.FAST)
        
        # Initialize gateway
        gw = initialize_gateway(rate_limiter, router, queue)
        await gw.start()
        yield
        await gw.stop()
        shutdown_gateway()
        
    @pytest.mark.asyncio
    async def test_real_llm_summarizes_nmap_output(self):
        """Verify real LLM extracts findings from nmap-like output."""
        from cyberred.tools.output import TIER2_SUMMARIZATION_PROMPT
        from cyberred.llm import LLMRequest, get_gateway
        import json
        
        # Use unknown tool to trigger Tier 2
        stdout = """
Nmap scan report for 192.168.1.1
Host is up (0.0010s latency).
Not shown: 998 closed ports
PORT   STATE SERVICE
22/tcp open  ssh
80/tcp open  http
MAC Address: 00:11:22:33:44:55 (Unknown)
"""
        tool = "custom_netscan"
        exit_code = 0
        
        prompt = TIER2_SUMMARIZATION_PROMPT.format(
            tool=tool,
            exit_code=exit_code,
            stdout=stdout[:4000],
            stderr=""
        )
        
        request = LLMRequest(
            prompt=prompt,
            model="auto",
            max_tokens=2048,
            temperature=0.0
        )
        
        gateway = get_gateway()
        response = await gateway.complete(request)
        
        # Parse result (handle markdown code fences)
        try:
            cleaned_content = strip_markdown_json(response.content)
            data = json.loads(cleaned_content)
            findings = data.get("findings", [])
            summary = data.get("summary", "")
        except json.JSONDecodeError:
            pytest.fail(f"LLM returned invalid JSON: {response.content}")
        
        # Verify findings extracted
        assert len(findings) > 0
        
        # Check structure
        finding = findings[0]
        assert finding.get("type")
        assert finding.get("description")
        
        # Check content relevance
        found_ssh = any("22" in f.get("evidence", "") or "ssh" in f.get("description", "").lower() for f in findings)
        found_http = any("80" in f.get("evidence", "") or "http" in f.get("description", "").lower() for f in findings)
        assert found_ssh or found_http

    @pytest.mark.asyncio
    async def test_real_llm_json_tool_output(self):
        """Test LLM with JSON-like tool output format (Sample 2/3)."""
        from cyberred.tools.output import TIER2_SUMMARIZATION_PROMPT
        from cyberred.llm import LLMRequest, get_gateway
        import json
        
        stdout = """
[
  {
    "vulnerability": "XSS",
    "severity": "High",
    "location": "/login"
  }
]
"""
        tool = "json_tool"
        
        prompt = TIER2_SUMMARIZATION_PROMPT.format(
            tool=tool,
            exit_code=0,
            stdout=stdout[:4000],
            stderr=""
        )
        
        request = LLMRequest(
            prompt=prompt,
            model="auto",
            max_tokens=2048,
            temperature=0.0
        )
        
        gateway = get_gateway()
        response = await gateway.complete(request)
        cleaned_content = strip_markdown_json(response.content)
        data = json.loads(cleaned_content)
        findings = data.get("findings", [])
        
        assert len(findings) > 0
        assert any("XSS" in f.get("description", "") or "XSS" in f.get("type", "") for f in findings)

    @pytest.mark.asyncio
    async def test_real_llm_plain_text_output(self):
        """Test LLM with plain text tool output format (Sample 3/3)."""
        from cyberred.tools.output import TIER2_SUMMARIZATION_PROMPT
        from cyberred.llm import LLMRequest, get_gateway
        import json
        
        # Sample 3: Plain text output (like gobuster or ffuf)
        stdout = """
===============================================================
Gobuster v3.1.0
===============================================================
[+] Url:                     http://target.local
[+] Threads:                 10
===============================================================
/admin                (Status: 200) [Size: 1234]
/backup               (Status: 403) [Size: 287]
/config               (Status: 200) [Size: 512]
/.git                 (Status: 301) [Size: 0] [--> /.git/]
===============================================================
"""
        tool = "directory_scanner"
        
        prompt = TIER2_SUMMARIZATION_PROMPT.format(
            tool=tool,
            exit_code=0,
            stdout=stdout[:4000],
            stderr=""
        )
        
        request = LLMRequest(
            prompt=prompt,
            model="auto",
            max_tokens=2048,
            temperature=0.0
        )
        
        gateway = get_gateway()
        response = await gateway.complete(request)
        cleaned_content = strip_markdown_json(response.content)
        data = json.loads(cleaned_content)
        findings = data.get("findings", [])
        
        # Should detect exposed directories/files
        assert len(findings) > 0
        # Verify cleanup: gateway is cleaned up by fixture, no rate limit exceeded
        # (verified by successful response without RateLimitError)

