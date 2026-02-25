import json
import asyncio
import uuid
import structlog
import hashlib
import threading
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import List, Callable, Dict, Optional, TYPE_CHECKING
from pathlib import Path
if TYPE_CHECKING:
    from cyberred.tools.parser_watcher import ParserWatcher
from cyberred.core.finding_policy import assess_finding_payload
from cyberred.core.models import Finding
from cyberred.llm import get_gateway, TaskComplexity, LLMGatewayNotInitializedError, LLMRequest
from cyberred.tools.parsers.base import ParserFn

log = structlog.get_logger()


def _strip_markdown_json(content: str) -> str:
    """Strip markdown code fences from LLM response if present.
    
    LLMs often wrap JSON in ```json ... ``` blocks despite being asked for raw JSON.
    This function cleans the response for safe JSON parsing.
    """
    content = content.strip()
    if content.startswith("```"):
        first_newline = content.find("\n")
        if first_newline != -1:
            content = content[first_newline + 1:]
        if content.endswith("```"):
            content = content[:-3].strip()
    return content

TIER2_SUMMARIZATION_PROMPT = """Analyze the following security tool output and extract findings.

Tool: {tool}
Exit Code: {exit_code}
{error_context}
STDOUT:
{stdout}

STDERR:
{stderr}

Respond with a JSON object:
{{
  "findings": [
    {{
      "type": "<finding_type>",
      "severity": "<critical|high|medium|low|info>",
      "description": "<what was found>",
      "evidence": "<relevant output snippet>"
    }}
  ],
  "summary": "<brief summary of the tool execution>"
}}

If no significant findings, respond with empty findings list.
Note: Output may be partial or truncated if an error occurred. Still extract any useful findings from available data.
"""

@dataclass
class ProcessedOutput:
    """Result of processing tool output.
    
    Attributes:
        findings: List of structured Finding objects from parsing.
        summary: Human-readable summary of the output.
        raw_truncated: First 4000 chars of stdout for debugging.
        tier: Which tier produced this result (1, 2, or 3).
    """
    findings: List[Finding] = field(default_factory=list)
    summary: str = ""
    raw_truncated: str = ""
    tier: int = 3

class OutputProcessor:
    """Routes tool output to appropriate parsers."""
    
    def __init__(self, max_raw_length: int = 4000, llm_timeout: int = 30, cache_enabled: bool = True, parsers_dir: Optional[Path] = None):
        self._parsers: Dict[str, ParserFn] = {}
        self._max_raw_length = max_raw_length
        self._llm_timeout = llm_timeout
        self._cache_enabled = cache_enabled
        self._llm_cache: Dict[str, ProcessedOutput] = {}
        self._parsers_dir = parsers_dir
        self._watcher: Optional['ParserWatcher'] = None
        self._lock = threading.RLock()

    def start_watcher(self) -> None:
        """Start the parser watcher."""
        if self._parsers_dir:
            from cyberred.tools.parser_watcher import ParserWatcher
            if self._watcher is None:
                self._watcher = ParserWatcher(parsers_dir=self._parsers_dir, processor=self)
                self._watcher.start()
                log.info("output_processor_watcher_started", directory=str(self._parsers_dir))

    def stop_watcher(self) -> None:
        """Stop the parser watcher."""
        if self._watcher:
            self._watcher.stop()
            self._watcher = None
            log.info("output_processor_watcher_stopped")

    def _generate_cache_key(self, tool: str, stdout: str, stderr: str) -> str:
        """Generate cache key from tool name and output hash.
        
        Cache key format: {tool}:{sha256(stdout+stderr)[:16]}
        Using first 16 chars of hash for reasonable uniqueness without storage bloat.
        """
        # Combine content to avoid collisions when findings are in stderr
        content = stdout + stderr
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        return f"{tool.lower()}:{content_hash}"
        
    def register_parser(self, tool_name: str, parser: ParserFn) -> None:
        """Register a Tier 1 parser for a tool."""
        with self._lock:
            self._parsers[tool_name.lower()] = parser
        log.info("parser_registered", tool=tool_name)

    def unregister_parser(self, tool_name: str) -> None:
        """Unregister a parser."""
        tool_lower = tool_name.lower()
        with self._lock:
            if tool_lower in self._parsers:
                del self._parsers[tool_lower]
                log.info("parser_unregistered", tool=tool_name)
        
    def get_registered_parsers(self) -> List[str]:
        """Return list of tools with registered parsers."""
        return list(self._parsers.keys())

    def _apply_finding_policy(
        self,
        findings: List[Finding],
        *,
        tool: str,
        stdout: str,
        stderr: str,
        exit_code: int,
        error_type: Optional[str] = None,
    ) -> List[Finding]:
        for finding in findings:
            assessment = assess_finding_payload(
                {
                    "type": finding.type,
                    "severity": finding.severity,
                    "tool": finding.tool or tool,
                    "target": finding.target,
                    "evidence": finding.evidence,
                    "execution": {
                        "stdout": stdout[:2000],
                        "stderr": stderr[:1000],
                        "exit_code": exit_code,
                        "error_type": error_type,
                    },
                }
            )
            finding.severity = assessment["severity"]
        return findings
    
    def process(self, stdout: str, stderr: str, tool: str, exit_code: int, agent_id: str, target: str, error_type: Optional[str] = None) -> ProcessedOutput:
        """Process tool output.
        
        Args:
            stdout: Standard output from tool.
            stderr: Standard error from tool.
            tool: Tool name.
            exit_code: Process exit code.
            agent_id: Agent identifier.
            target: Target being scanned.
            error_type: Optional error classification (TIMEOUT, NON_ZERO_EXIT, etc.).
                       Passed to parsers and LLM for context-aware extraction.
        
        Note:
            Failed results (success=False) should still be processed for partial
            output extraction per AC2 of Story 4.13.
        """
        tool_lower = tool.lower()
        
        parser = None
        with self._lock:
            parser = self._parsers.get(tool_lower)
            
        if parser:
            log.info("using_tier1_parser", tool=tool_lower)
            try:
                # Try to call parser with error_type if it accepts the parameter
                import inspect
                sig = inspect.signature(parser)
                if 'error_type' in sig.parameters:
                    findings = parser(stdout, stderr, exit_code, agent_id, target, error_type=error_type)
                else:
                    findings = parser(stdout, stderr, exit_code, agent_id, target)
                findings = self._apply_finding_policy(
                    findings,
                    tool=tool_lower,
                    stdout=stdout,
                    stderr=stderr,
                    exit_code=exit_code,
                    error_type=error_type,
                )
                return ProcessedOutput(
                    findings=findings,
                    summary=f"Parsed {len(findings)} findings from {tool}",
                    raw_truncated=stdout[:self._max_raw_length],
                    tier=1
                )
            except Exception:
                log.exception("parser_failed", tool=tool_lower)
                log.warning(
                    "parser_fallback_to_tier2",
                    tool=tool_lower,
                    exit_code=exit_code,
                    error_type=error_type,
                )

        # Tier 2: Try LLM summarization
        try:
            return self._tier2_llm_summarize(stdout, stderr, tool, stdout[:self._max_raw_length], exit_code, agent_id, target, error_type)
        except asyncio.TimeoutError:
            log.warning("tier2_timeout", tool=tool_lower, limit=self._llm_timeout)
        except json.JSONDecodeError as e:
            log.exception("tier2_json_error", tool=tool_lower, message=str(e))
        except Exception as e:
            try:
                log.exception("llm_summarization_failed", tool=tool_lower, reason=str(e))
            except:
                pass
                
        # Tier 3 (Raw Truncated)
        log.info("using_tier3_raw", tool=tool_lower)
        log.warning(
            "output_tier3_fallback",
            tool=tool_lower,
            exit_code=exit_code,
            error_type=error_type,
            stdout_len=len(stdout or ""),
            stderr_len=len(stderr or ""),
        )
        summary = f"Raw tool output (truncated to {self._max_raw_length} chars)"
        return ProcessedOutput(
            summary=summary,
            raw_truncated=stdout[:self._max_raw_length],
            tier=3
        )

    async def async_process(self, stdout: str, stderr: str, tool: str, exit_code: int, agent_id: str, target: str, error_type: Optional[str] = None) -> ProcessedOutput:
        """Async version of process() that supports tier2 LLM summarization.

        Use this from async agent code instead of process().
        """
        tool_lower = tool.lower()

        # Tier 1: structured parser
        parser = None
        with self._lock:
            parser = self._parsers.get(tool_lower)

        if parser:
            log.info("using_tier1_parser", tool=tool_lower)
            try:
                import inspect
                sig = inspect.signature(parser)
                if 'error_type' in sig.parameters:
                    findings = parser(stdout, stderr, exit_code, agent_id, target, error_type=error_type)
                else:
                    findings = parser(stdout, stderr, exit_code, agent_id, target)
                findings = self._apply_finding_policy(
                    findings,
                    tool=tool_lower,
                    stdout=stdout,
                    stderr=stderr,
                    exit_code=exit_code,
                    error_type=error_type,
                )
                return ProcessedOutput(
                    findings=findings,
                    summary=f"Parsed {len(findings)} findings from {tool}",
                    raw_truncated=stdout[:self._max_raw_length],
                    tier=1
                )
            except Exception:
                log.exception("parser_failed", tool=tool_lower)
                log.warning(
                    "parser_fallback_to_tier2",
                    tool=tool_lower,
                    exit_code=exit_code,
                    error_type=error_type,
                )

        # Tier 2: async LLM summarization
        try:
            return await self._async_tier2_llm_summarize(
                stdout, stderr, tool, stdout[:self._max_raw_length],
                exit_code, agent_id, target, error_type
            )
        except asyncio.TimeoutError:
            log.warning("tier2_timeout", tool=tool_lower, limit=self._llm_timeout)
        except json.JSONDecodeError as e:
            log.exception("tier2_json_error", tool=tool_lower, message=str(e))
        except Exception as e:
            try:
                log.warning("async_llm_summarization_failed", tool=tool_lower, reason=str(e))
            except Exception:
                pass

        # Tier 3 (Raw Truncated)
        log.info("using_tier3_raw", tool=tool_lower)
        log.warning(
            "output_tier3_fallback",
            tool=tool_lower,
            exit_code=exit_code,
            error_type=error_type,
            stdout_len=len(stdout or ""),
            stderr_len=len(stderr or ""),
        )
        return ProcessedOutput(
            summary=f"Raw tool output (truncated to {self._max_raw_length} chars)",
            raw_truncated=stdout[:self._max_raw_length],
            tier=3
        )

    async def _async_tier2_llm_summarize(self, stdout, stderr, tool, raw_truncated, exit_code, agent_id, target, error_type: Optional[str] = None) -> ProcessedOutput:
        """Async tier2 LLM summarization."""
        cache_key = self._generate_cache_key(tool, stdout, stderr)
        if self._cache_enabled and cache_key in self._llm_cache:
            return self._llm_cache[cache_key]

        gateway = get_gateway()

        error_context = ""
        if error_type:
            error_context = f"Error Type: {error_type}\nNote: Output may be partial due to {error_type.replace('_', ' ').lower()}.\n"

        prompt = TIER2_SUMMARIZATION_PROMPT.format(
            tool=tool, exit_code=exit_code, error_context=error_context,
            stdout=stdout[:4000], stderr=stderr[:1000]
        )
        request = LLMRequest(
            prompt=prompt,
            model="auto",
            max_tokens=5000,
            temperature=0.0,
            timeout_budget_s=float(self._llm_timeout),
        )

        response = await gateway.complete(request)
        response_json = _strip_markdown_json(response.content)

        data = json.loads(response_json)
        findings = []
        for f in data.get("findings", []):
            findings.append(Finding(
                id=str(uuid.uuid4()), type=f.get("type", "unknown"),
                severity=f.get("severity", "info"), target=target,
                evidence=f.get("evidence", "") + "\n---\n" + f.get("description", ""),
                agent_id=agent_id, timestamp=datetime.now(timezone.utc).isoformat(),
                tool=tool.lower(), topic=f"findings:{agent_id}:{tool.lower()}", signature=""
            ))

        result = ProcessedOutput(findings=findings, summary=data.get("summary", ""), raw_truncated=raw_truncated, tier=2)
        result.findings = self._apply_finding_policy(
            result.findings,
            tool=tool.lower(),
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            error_type=error_type,
        )
        if self._cache_enabled:
            self._llm_cache[cache_key] = result
        return result

    def _tier2_llm_summarize(self, stdout, stderr, tool, raw_truncated, exit_code, agent_id, target, error_type: Optional[str] = None) -> ProcessedOutput:
        # asyncio.run() cannot be called from within a running event loop.
        # Agents always call process() from async context, so detect and raise
        # to fall through to tier3 (raw output). Use async_process() for tier2.
        try:
            asyncio.get_running_loop()
            raise RuntimeError("Tier2 LLM unavailable in async context — use async_process()")
        except RuntimeError as loop_err:
            if "no running event loop" not in str(loop_err):
                raise

        # Check cache if enabled
        cache_key = self._generate_cache_key(tool, stdout, stderr)
        if self._cache_enabled:
            if cache_key in self._llm_cache:
                log.info("llm_cache_hit", tool=tool.lower(), key=cache_key)
                return self._llm_cache[cache_key]

        if self._cache_enabled:
            log.info("llm_cache_miss", tool=tool.lower(), key=cache_key)

        gateway = get_gateway()

        # Build error context section for prompt
        error_context = ""
        if error_type:
            error_context = f"Error Type: {error_type}\nNote: Output may be partial due to {error_type.replace('_', ' ').lower()}.\n"

        prompt = TIER2_SUMMARIZATION_PROMPT.format(
            tool=tool,
            exit_code=exit_code,
            error_context=error_context,
            stdout=stdout[:4000],
            stderr=stderr[:1000]
        )

        request = LLMRequest(
            prompt=prompt,
            model="auto",
            max_tokens=5000,
            temperature=0.0,
            timeout_budget_s=float(self._llm_timeout),
        )

        async def call_gateway():
             return await gateway.complete(request)

        response = asyncio.run(call_gateway())
        response_json = _strip_markdown_json(response.content)
        
        data = json.loads(response_json)
        findings_data = data.get("findings", [])
        summary = data.get("summary", "")
        
        findings = []
        for f in findings_data:
            finding = Finding(
                id=str(uuid.uuid4()),
                type=f.get("type", "unknown"),
                severity=f.get("severity", "info"),
                target=target,
                evidence=f.get("evidence", "") + "\n---\n" + f.get("description", ""),
                agent_id=agent_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
                tool=tool.lower(),
                topic=f"findings:{agent_id}:{tool.lower()}",
                signature=""
            )
            findings.append(finding)
            
        result = ProcessedOutput(
            findings=findings,
            summary=summary,
            raw_truncated=raw_truncated,
            tier=2
        )
        result.findings = self._apply_finding_policy(
            result.findings,
            tool=tool.lower(),
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            error_type=error_type,
        )
        
        # Store in cache if enabled
        if self._cache_enabled:
            self._llm_cache[cache_key] = result
        return result
