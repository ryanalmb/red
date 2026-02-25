"""Natural Language Interpreter for Drop Box Deployment.

Story 12.8: Natural Language Drop Box Setup - Task 2

Parses natural language input to extract deployment parameters using LLM Gateway.
Handles ambiguous inputs with clarification requests.

Usage:
    from cyberred.c2.nl_interpreter import DropBoxDeploymentInterpreter, DeploymentPlan
    
    interpreter = DropBoxDeploymentInterpreter()
    plan = await interpreter.interpret("Deploy a drop box on my Android at 192.168.1.100")
"""

from __future__ import annotations

import ipaddress
import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

import structlog

from cyberred.llm.provider import LLMRequest

log = structlog.get_logger()

# Supported platforms per story requirements
SUPPORTED_PLATFORMS = {"android", "windows", "linux", "macos", "ios"}

# System prompt for NL interpretation
NL_INTERPRETER_SYSTEM_PROMPT = """You are a drop box deployment assistant. Extract deployment parameters from natural language.

Extract:
- platform: android, windows, linux, macos, or ios
- ip_address: Target IP address or hostname
- hostname: Friendly name for the drop box (optional, generate if not provided)

Respond in JSON format ONLY (no markdown, no explanation):
{
    "platform": "<platform>",
    "ip_address": "<ip>",
    "hostname": "<name>",
    "confidence": <0.0-1.0>
}

If you cannot determine required fields, set confidence < 0.5 and include "clarification_needed": "<question>".

Examples:
- "Deploy on my Android at 192.168.1.100" → {"platform": "android", "ip_address": "192.168.1.100", "hostname": "android-dropbox", "confidence": 0.95}
- "Set up a Windows drop box on the office server" → {"platform": "windows", "ip_address": "", "hostname": "office-server", "confidence": 0.3, "clarification_needed": "What is the IP address of the office server?"}
- "Linux dropbox at server.local" → {"platform": "linux", "ip_address": "server.local", "hostname": "linux-server-local", "confidence": 0.9}
"""

# Maximum input length to prevent prompt injection
MAX_NL_INPUT_LENGTH = 500


@dataclass
class DeploymentPlan:
    """Parsed deployment plan from NL input.
    
    Attributes:
        platform: Target platform (android, windows, linux, macos, ios).
        ip_address: Target IP address or hostname.
        hostname: Friendly name for the drop box.
        options: Additional deployment options.
        confidence: Confidence score from LLM (0.0-1.0).
        clarification_needed: Question to ask user if confidence is low.
    """
    
    platform: str
    ip_address: str
    hostname: Optional[str] = None
    options: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    clarification_needed: Optional[str] = None
    
    def __post_init__(self) -> None:
        """Normalize platform to lowercase."""
        self.platform = self.platform.lower() if self.platform else ""
    
    def validate(self) -> list[str]:
        """Return list of validation errors, empty if valid.
        
        Returns:
            List of error messages. Empty list means valid.
        """
        errors: list[str] = []
        
        # Validate platform
        if not self.platform:
            errors.append("Platform is required")
        elif self.platform not in SUPPORTED_PLATFORMS:
            errors.append(f"Unsupported platform: {self.platform}. Supported: {', '.join(sorted(SUPPORTED_PLATFORMS))}")
        
        # Validate IP/hostname
        if not self.ip_address:
            errors.append("IP address or hostname is required")
        else:
            # Try to parse as IP address
            try:
                ipaddress.ip_address(self.ip_address)
            except ValueError:
                # Not an IP - validate as hostname
                if not re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9.-]*[a-zA-Z0-9])?$', self.ip_address):
                    errors.append(f"Invalid IP address or hostname: {self.ip_address}")
        
        return errors
    
    def is_valid(self) -> bool:
        """Check if plan is valid.
        
        Returns:
            True if no validation errors.
        """
        return len(self.validate()) == 0
    
    def needs_clarification(self) -> bool:
        """Check if plan needs clarification from user.
        
        Returns:
            True if confidence is low or clarification is needed.
        """
        return self.confidence < 0.5 or self.clarification_needed is not None
    
    def generate_drop_box_id(self) -> str:
        """Generate unique drop box ID from hostname or UUID.
        
        Returns:
            Sanitized drop box ID suitable for certificate CN.
        """
        if self.hostname:
            # Sanitize hostname for use as ID
            sanitized = re.sub(r'[^a-zA-Z0-9-]', '-', self.hostname.lower())
            sanitized = re.sub(r'-+', '-', sanitized).strip('-')
            if sanitized:
                return f"{sanitized}-{self.platform}"
        
        # Generate from IP if no hostname
        if self.ip_address:
            ip_part = re.sub(r'[^a-zA-Z0-9]', '-', self.ip_address)
            return f"{self.platform}-{ip_part}"
        
        # Fallback to UUID
        return f"{self.platform}-{uuid.uuid4().hex[:8]}"


class InterpretationError(Exception):
    """Error during NL interpretation."""
    
    def __init__(self, message: str, suggestion: Optional[str] = None) -> None:
        """Initialize with message and optional suggestion.
        
        Args:
            message: Error message.
            suggestion: Optional suggestion for user.
        """
        super().__init__(message)
        self.suggestion = suggestion


class DropBoxDeploymentInterpreter:
    """Interprets natural language input for drop box deployment.
    
    Uses LLM Gateway to parse NL input into structured DeploymentPlan.
    Handles ambiguous inputs with clarification requests.
    
    Attributes:
        _gateway: LLM Gateway instance (lazy loaded).
    """
    
    def __init__(self) -> None:
        """Initialize interpreter."""
        self._gateway = None
    
    def _get_gateway(self):
        """Lazy load LLM Gateway.
        
        Returns:
            LLMGateway instance.
            
        Raises:
            RuntimeError: If gateway not initialized.
        """
        if self._gateway is None:
            from cyberred.llm.gateway import get_gateway
            self._gateway = get_gateway()
        return self._gateway
    
    async def interpret(self, nl_input: str) -> DeploymentPlan:
        """Interpret natural language input into DeploymentPlan.
        
        Args:
            nl_input: Natural language description of deployment.
            
        Returns:
            DeploymentPlan with parsed parameters.
            
        Raises:
            InterpretationError: If input cannot be parsed.
            ValueError: If input is empty or too long.
        """
        # Validate input
        if not nl_input or not nl_input.strip():
            raise ValueError("Input cannot be empty")
        
        nl_input = nl_input.strip()
        
        if len(nl_input) > MAX_NL_INPUT_LENGTH:
            raise ValueError(f"Input too long. Maximum {MAX_NL_INPUT_LENGTH} characters allowed.")
        
        log.info("nl_interpreter_processing", input_length=len(nl_input))
        
        try:
            gateway = self._get_gateway()
            
            # Build request with system prompt
            request = LLMRequest(
                prompt=f"Parse this deployment request:\n\n{nl_input}",
                model="auto",
                temperature=0.3,  # Lower temperature for more consistent parsing
                max_tokens=5000,
                system_prompt=NL_INTERPRETER_SYSTEM_PROMPT,
            )
            
            # Get LLM response
            response = await gateway.agent_complete(request)
            
            # Check for error response
            if response.finish_reason and response.finish_reason.startswith("error:"):
                raise InterpretationError(
                    "AI service temporarily unavailable. Please try again or use manual setup.",
                    suggestion="Example: Deploy on Android at 192.168.1.100"
                )
            
            # Parse JSON response
            plan = self._parse_response(response.content)
            
            log.info(
                "nl_interpreter_success",
                platform=plan.platform,
                ip_address=plan.ip_address,
                confidence=plan.confidence,
            )
            
            return plan
            
        except InterpretationError:
            raise
        except json.JSONDecodeError as e:
            log.error("nl_interpreter_json_error", error=str(e))
            raise InterpretationError(
                "Could not parse AI response. Please try rephrasing.",
                suggestion="Try: 'Deploy a [platform] drop box at [IP address]'"
            )
        except Exception as e:
            log.error("nl_interpreter_error", error=str(e))
            raise InterpretationError(
                f"Interpretation failed: {str(e)}",
                suggestion="Example commands:\n- Deploy on Android at 192.168.1.100\n- Set up Windows drop box on 10.0.0.50\n- Linux dropbox at server.local"
            )
    
    def _parse_response(self, content: str) -> DeploymentPlan:
        """Parse LLM response into DeploymentPlan.
        
        Args:
            content: Raw LLM response content.
            
        Returns:
            DeploymentPlan instance.
            
        Raises:
            InterpretationError: If response cannot be parsed.
        """
        # Strip any markdown code blocks
        content = content.strip()
        if content.startswith("```"):
            # Remove markdown code fence
            lines = content.split("\n")
            content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        
        # Parse JSON
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON from response using balanced-brace matching
            extracted = self._extract_json_object(content)
            if extracted:
                data = json.loads(extracted)
            else:
                raise InterpretationError(
                    "Could not parse response format",
                    suggestion="Please try with a clearer description"
                )
        
        # Extract fields
        platform = data.get("platform", "").lower()
        ip_address = data.get("ip_address", "")
        hostname = data.get("hostname")
        confidence = float(data.get("confidence", 0.5))
        clarification = data.get("clarification_needed")
        
        # Build plan
        plan = DeploymentPlan(
            platform=platform,
            ip_address=ip_address,
            hostname=hostname,
            confidence=confidence,
            clarification_needed=clarification,
        )
        
        # Add helpful error messages for missing fields
        if not platform and not clarification:
            plan.clarification_needed = "Could not determine platform. Please specify: Android, Windows, Linux, or macOS"
            plan.confidence = 0.3
        
        if not ip_address and not clarification:
            if plan.clarification_needed:
                plan.clarification_needed += "\nAlso, please include the target IP address or hostname."
            else:
                plan.clarification_needed = "Could not determine target IP. Please include the IP address or hostname."
            plan.confidence = min(plan.confidence, 0.3)
        
        return plan

    @staticmethod
    def _extract_json_object(text: str) -> str | None:
        """Extract the first JSON object from text using balanced-brace matching.
        
        Handles nested objects like {"platform": "linux", "options": {"port": 8080}}.
        
        Args:
            text: Text that may contain a JSON object.
            
        Returns:
            Extracted JSON string or None if not found.
        """
        start = text.find('{')
        if start == -1:
            return None
        
        depth = 0
        in_string = False
        escape_next = False
        
        for i in range(start, len(text)):
            char = text[i]
            
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\' and in_string:
                escape_next = True
                continue
            
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
            
            if in_string:
                continue
            
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
        
        return None


# Example NL inputs for testing
EXAMPLE_NL_INPUTS = [
    "Deploy a drop box on my Android phone at 192.168.1.100",
    "Set up Windows drop box on 10.0.0.50",
    "Linux dropbox at server.local",
    "macOS dropbox at macbook.local called office-mac",
    "Deploy on my phone",  # Ambiguous - missing platform and IP
    "Windows drop box",  # Ambiguous - missing IP
]
