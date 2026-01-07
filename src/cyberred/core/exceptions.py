"""Cyber-Red Exception Hierarchy.

This module defines the structured exception hierarchy for Cyber-Red.
All custom exceptions inherit from CyberRedError, enabling consistent
error handling across the codebase.

Exception Categories (per architecture):
- Critical/System errors → Exceptions (always raised, never "expected")
- Expected/Tool errors → Result objects (ToolResult)

Usage:
    from cyberred.core.exceptions import ScopeViolationError, KillSwitchTriggered

    # Scope violations always raise
    raise ScopeViolationError(
        target="192.168.1.100",
        command="nmap -p 22",
        scope_rule="cidr_block"
    )

    # Kill switch always raises
    raise KillSwitchTriggered(
        engagement_id="eng-001",
        triggered_by="operator",
        reason="Emergency stop"
    )
"""

from typing import Any, Optional


class CyberRedError(Exception):
    """Base exception for all Cyber-Red errors.

    All custom exceptions in Cyber-Red inherit from this class,
    enabling consistent catch-all error handling.

    Attributes:
        message: Human-readable error description.
    """

    def __init__(self, message: Optional[str] = None) -> None:
        """Initialize CyberRedError.

        Args:
            message: Optional custom message. Defaults to a generic message.
        """
        self.message = message or "A Cyber-Red error occurred."
        super().__init__(self.message)

    @property
    def context(self) -> dict[str, Any]:
        """Return context dictionary for structured logging.

        Returns:
            dict: Key-value pairs of exception context.
        """
        return {}

    def __repr__(self) -> str:
        """Return debug representation."""
        return f"{self.__class__.__name__}({self.message!r})"


class ScopeViolationError(CyberRedError):
    """Command attempted to access out-of-scope target.

    Raised when a tool or agent attempts to execute a command
    against a target that is not within the defined scope.
    Scope violations are ALWAYS exceptions - never "expected".

    Attributes:
        target: The target that was out of scope (IP, hostname, URL).
        command: The command that was attempted.
        scope_rule: The scope rule that was violated.
    """

    def __init__(
        self,
        target: str,
        command: str,
        scope_rule: str,
        message: Optional[str] = None,
    ) -> None:
        """Initialize ScopeViolationError.

        Args:
            target: The out-of-scope target.
            command: The attempted command.
            scope_rule: Name of the violated scope rule (REQUIRED).
            message: Optional custom message.
        """
        self.target = target
        self.command = command
        self.scope_rule = scope_rule

        if message is None:
            message = (
                f"Scope violation: target '{target}' is out of scope "
                f"(rule: {scope_rule})."
            )

        super().__init__(message)

    @property
    def context(self) -> dict[str, Any]:
        """Return context for scope violation."""
        return {
            "target": self.target,
            "command": self.command,
            "scope_rule": self.scope_rule,
        }

    def __repr__(self) -> str:
        """Return debug representation with attributes."""
        return (
            f"ScopeViolationError(target={self.target!r}, "
            f"command={self.command!r}, scope_rule={self.scope_rule!r})"
        )


class KillSwitchTriggered(CyberRedError):
    """Engagement halted by operator via kill switch.

    Raised when the operator triggers the kill switch to halt
    all operations. This is a safety-critical exception.

    Attributes:
        engagement_id: The engagement that was halted.
        triggered_by: Who triggered the kill switch.
        reason: Why the kill switch was triggered.
    """

    def __init__(
        self,
        engagement_id: str,
        triggered_by: str,
        reason: str,
        message: Optional[str] = None,
    ) -> None:
        """Initialize KillSwitchTriggered.

        Args:
            engagement_id: The halted engagement ID.
            triggered_by: Who triggered the kill switch (REQUIRED).
            reason: Why it was triggered (REQUIRED).
            message: Optional custom message.
        """
        self.engagement_id = engagement_id
        self.triggered_by = triggered_by
        self.reason = reason

        if message is None:
            message = (
                f"Kill switch triggered for engagement '{engagement_id}' "
                f"by {triggered_by} - {reason}."
            )

        super().__init__(message)

    @property
    def context(self) -> dict[str, Any]:
        """Return context for kill switch event."""
        return {
            "engagement_id": self.engagement_id,
            "triggered_by": self.triggered_by,
            "reason": self.reason,
        }

    def __repr__(self) -> str:
        """Return debug representation with attributes."""
        return (
            f"KillSwitchTriggered(engagement_id={self.engagement_id!r}, "
            f"triggered_by={self.triggered_by!r}, reason={self.reason!r})"
        )


class ConfigurationError(CyberRedError):
    """Configuration file or value is invalid.

    Raised when YAML configuration cannot be parsed or
    contains invalid values.

    Attributes:
        config_path: Path to the configuration file.
        key: The configuration key that caused the error.
        expected_type: The expected type for the value.
    """

    def __init__(
        self,
        config_path: str,
        key: Optional[str] = None,
        expected_type: Optional[str] = None,
        message: Optional[str] = None,
    ) -> None:
        """Initialize ConfigurationError.

        Args:
            config_path: Path to the config file.
            key: Optional key that caused the error.
            expected_type: Optional expected type.
            message: Optional custom message.
        """
        self.config_path = config_path
        self.key = key
        self.expected_type = expected_type

        if message is None:
            key_info = f" key '{key}'" if key else ""
            type_info = f" (expected {expected_type})" if expected_type else ""
            message = f"Configuration error in '{config_path}'{key_info}{type_info}."

        super().__init__(message)

    @property
    def context(self) -> dict[str, Any]:
        """Return context for configuration error."""
        return {
            "config_path": self.config_path,
            "key": self.key,
            "expected_type": self.expected_type,
        }

    def __repr__(self) -> str:
        """Return debug representation with attributes."""
        return (
            f"ConfigurationError(config_path={self.config_path!r}, "
            f"key={self.key!r}, expected_type={self.expected_type!r})"
        )


class CheckpointIntegrityError(CyberRedError):
    """Checkpoint file is tampered or has invalid scope.

    Raised when checkpoint verification fails during resume.
    This can be due to signature mismatch or scope hash mismatch.

    Attributes:
        checkpoint_path: Path to the checkpoint file.
        verification_type: Type of verification that failed ('signature' or 'scope').
    """

    def __init__(
        self,
        checkpoint_path: str,
        verification_type: Optional[str] = None,
        message: Optional[str] = None,
    ) -> None:
        """Initialize CheckpointIntegrityError.

        Args:
            checkpoint_path: Path to the checkpoint file.
            verification_type: Type of verification that failed.
            message: Optional custom message.
        """
        self.checkpoint_path = checkpoint_path
        self.verification_type = verification_type

        if message is None:
            type_info = f" ({verification_type} verification)" if verification_type else ""
            message = f"Checkpoint integrity error for '{checkpoint_path}'{type_info}."

        super().__init__(message)

    @property
    def context(self) -> dict[str, Any]:
        """Return context for checkpoint integrity error."""
        return {
            "checkpoint_path": self.checkpoint_path,
            "verification_type": self.verification_type,
        }

    def __repr__(self) -> str:
        """Return debug representation with attributes."""
        return (
            f"CheckpointIntegrityError(checkpoint_path={self.checkpoint_path!r}, "
            f"verification_type={self.verification_type!r})"
        )


class DecryptionError(CyberRedError):
    """Decryption operation failed.

    Raised when AES-GCM decryption fails due to wrong key,
    tampered ciphertext, or invalid nonce.

    Attributes:
        reason: Description of why decryption failed.
    """

    def __init__(
        self,
        reason: str | None = None,
        message: str | None = None,
    ) -> None:
        """Initialize DecryptionError.

        Args:
            reason: Description of failure cause.
            message: Optional custom message.
        """
        self.reason = reason

        if message is None:
            if reason:
                message = f"Decryption failed: {reason}"
            else:
                message = "Decryption failed - authentication or key error."

        super().__init__(message)

    @property
    def context(self) -> dict[str, Any]:
        """Return context for decryption error."""
        return {
            "reason": self.reason,
        }

    def __repr__(self) -> str:
        """Return debug representation with attributes."""
        return f"DecryptionError(reason={self.reason!r})"


class IPCProtocolError(CyberRedError):
    """Invalid or malformed IPC message.

    Raised when an IPC message cannot be decoded or validated.
    This includes JSON parse errors, missing required fields,
    and invalid message structure.

    Attributes:
        reason: Description of why the message is invalid.
    """

    def __init__(
        self,
        reason: str | None = None,
        message: str | None = None,
    ) -> None:
        """Initialize IPCProtocolError.

        Args:
            reason: Description of failure cause.
            message: Optional custom message.
        """
        self.reason = reason

        if message is None:
            if reason:
                message = f"IPC protocol error: {reason}"
            else:
                message = "IPC protocol error - invalid or malformed message."

        super().__init__(message)

    @property
    def context(self) -> dict[str, Any]:
        """Return context for IPC protocol error."""
        return {
            "reason": self.reason,
        }

    def __repr__(self) -> str:
        """Return debug representation with attributes."""
        return f"IPCProtocolError(reason={self.reason!r})"


class StreamProtocolError(CyberRedError):
    """Invalid or malformed stream event.

    Raised when a streaming event cannot be decoded or validated.
    This includes JSON parse errors, missing required fields,
    and invalid event structure.

    Attributes:
        reason: Description of why the event is invalid.
    """

    def __init__(
        self,
        reason: str | None = None,
        message: str | None = None,
    ) -> None:
        """Initialize StreamProtocolError.

        Args:
            reason: Description of failure cause.
            message: Optional custom message.
        """
        self.reason = reason

        if message is None:
            if reason:
                message = f"Stream protocol error: {reason}"
            else:
                message = "Stream protocol error - invalid or malformed event."

        super().__init__(message)

    @property
    def context(self) -> dict[str, Any]:
        """Return context for stream protocol error."""
        return {
            "reason": self.reason,
        }

    def __repr__(self) -> str:
        """Return debug representation with attributes."""
        return f"StreamProtocolError(reason={self.reason!r})"


class InvalidStateTransition(CyberRedError):
    """Invalid engagement state transition attempted.

    Raised when attempting a state transition that violates the
    engagement lifecycle state machine.

    Attributes:
        engagement_id: The engagement ID.
        from_state: Current state.
        to_state: Attempted target state.
    """

    def __init__(
        self,
        engagement_id: str,
        from_state: str,
        to_state: str,
        message: str | None = None,
    ) -> None:
        """Initialize InvalidStateTransition.

        Args:
            engagement_id: The engagement ID.
            from_state: Current state.
            to_state: Attempted target state.
            message: Optional custom message.
        """
        self.engagement_id = engagement_id
        self.from_state = from_state
        self.to_state = to_state

        if message is None:
            message = (
                f"Invalid state transition for engagement '{engagement_id}': "
                f"{from_state} → {to_state}."
            )

        super().__init__(message)

    @property
    def context(self) -> dict[str, Any]:
        """Return context for invalid state transition."""
        return {
            "engagement_id": self.engagement_id,
            "from_state": self.from_state,
            "to_state": self.to_state,
        }

    def __repr__(self) -> str:
        """Return debug representation with attributes."""
        return (
            f"InvalidStateTransition(engagement_id={self.engagement_id!r}, "
            f"from_state={self.from_state!r}, to_state={self.to_state!r})"
        )


class ResourceLimitError(CyberRedError):
    """Resource limit exceeded.

    Raised when attempting to allocate resources beyond configured limits,
    such as exceeding maximum concurrent engagements.

    Attributes:
        limit_type: Type of limit exceeded (e.g., "max_engagements").
        current_value: Current usage value.
        max_value: Maximum allowed value.
    """

    def __init__(
        self,
        message: str | None = None,
        limit_type: str | None = None,
        current_value: int | None = None,
        max_value: int | None = None,
    ) -> None:
        """Initialize ResourceLimitError.

        Args:
            message: Custom error message.
            limit_type: Type of limit exceeded.
            current_value: Current usage value.
            max_value: Maximum allowed value.
        """
        self.limit_type = limit_type
        self.current_value = current_value
        self.max_value = max_value

        if message is None:
            if limit_type and max_value is not None:
                message = f"Resource limit exceeded: {limit_type} (max: {max_value})"
            else:
                message = "Resource limit exceeded."

        super().__init__(message)

    @property
    def context(self) -> dict[str, Any]:
        """Return context for resource limit error."""
        return {
            "limit_type": self.limit_type,
            "current_value": self.current_value,
            "max_value": self.max_value,
        }

    def __repr__(self) -> str:
        """Return debug representation with attributes."""
        return (
            f"ResourceLimitError(limit_type={self.limit_type!r}, "
            f"current_value={self.current_value!r}, max_value={self.max_value!r})"
        )


class EngagementNotFoundError(CyberRedError):
    """Engagement not found.

    Raised when attempting to operate on an engagement that doesn't exist.

    Attributes:
        engagement_id: The ID that was not found.
    """

    def __init__(
        self,
        engagement_id: str,
        message: str | None = None,
    ) -> None:
        """Initialize EngagementNotFoundError.

        Args:
            engagement_id: The engagement ID that was not found.
            message: Optional custom message.
        """
        self.engagement_id = engagement_id

        if message is None:
            message = f"Engagement not found: {engagement_id}"

        super().__init__(message)

    @property
    def context(self) -> dict[str, Any]:
        """Return context for engagement not found."""
        return {"engagement_id": self.engagement_id}

    def __repr__(self) -> str:
        """Return debug representation with attributes."""
        return f"EngagementNotFoundError(engagement_id={self.engagement_id!r})"

class PreFlightCheckError(CyberRedError):
    """Pre-flight check failed (blocking).

    Raised when a P0 pre-flight check fails, preventing engagement start.

    Attributes:
        results: List of check results (failures).
    """

    def __init__(self, results: list[Any], message: Optional[str] = None) -> None:
        """Initialize PreFlightCheckError.
        
        Args:
            results: List of CheckResult objects that failed.
            message: Optional custom message.
        """
        self.results = results
        if message is None:
            failed_checks = [r.name for r in results if r.status == "FAIL"]
            message = f"Pre-flight checks failed: {', '.join(failed_checks)}"
        super().__init__(message)

    @property
    def context(self) -> dict[str, Any]:
        """Return context for pre-flight error."""
        return {
            "failed_checks": [
                {"name": r.name, "message": r.message, "priority": r.priority} 
                for r in self.results
            ]
        }


class PreFlightWarningError(CyberRedError):
    """Pre-flight check warning (requires acknowledgment).

    Raised when P1 checks fail and no ignore_warnings flag was provided.

    Attributes:
        results: List of check results (warnings).
    """

    def __init__(self, results: list[Any], message: Optional[str] = None) -> None:
        """Initialize PreFlightWarningError.
        
        Args:
            results: List of CheckResult objects that warned.
            message: Optional custom message.
        """
        self.results = results
        if message is None:
            warn_checks = [r.name for r in results if r.status == "WARN"]
            message = f"Pre-flight warnings: {', '.join(warn_checks)} (requires acknowledgment)"
        super().__init__(message)

    @property
    def context(self) -> dict[str, Any]:
        """Return context for pre-flight warning."""
        return {
            "warnings": [
                {"name": r.name, "message": r.message, "priority": r.priority} 
                for r in self.results
            ]
        }


# === LLM Provider Exceptions (Story 3.5) ===


class LLMError(CyberRedError):
    """Base exception for LLM provider errors.

    All LLM-related exceptions inherit from this class.

    Attributes:
        provider: Optional name of the LLM provider.
        model: Optional model identifier.
    """

    def __init__(
        self,
        message: str | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> None:
        """Initialize LLMError.

        Args:
            message: Error description.
            provider: Name of the LLM provider.
            model: Model identifier.
        """
        self.provider = provider
        self.model = model

        if message is None:
            message = "An LLM error occurred."

        super().__init__(message)

    @property
    def context(self) -> dict[str, Any]:
        """Return context for LLM error."""
        return {
            "provider": self.provider,
            "model": self.model,
        }

    def __repr__(self) -> str:
        """Return debug representation."""
        return f"LLMError(provider={self.provider!r}, model={self.model!r})"


class LLMProviderUnavailable(LLMError):
    """LLM provider is not reachable or available.

    Raised when the LLM provider cannot be contacted or
    returns unavailability status. Per NFR29, system should
    gracefully degrade when providers are unavailable.

    Attributes:
        provider: Name of the unavailable provider.
        retry_after: Optional seconds to wait before retry.
    """

    def __init__(
        self,
        provider: str,
        message: str | None = None,
        retry_after: int | None = None,
    ) -> None:
        """Initialize LLMProviderUnavailable.

        Args:
            provider: Name of the unavailable provider.
            message: Optional custom message.
            retry_after: Optional seconds to wait before retry.
        """
        self.retry_after = retry_after

        if message is None:
            retry_info = f" (retry after {retry_after}s)" if retry_after else ""
            message = f"LLM provider '{provider}' is unavailable{retry_info}."

        super().__init__(message, provider=provider)

    @property
    def context(self) -> dict[str, Any]:
        """Return context for provider unavailable."""
        ctx = super().context
        ctx["retry_after"] = self.retry_after
        return ctx

    def __repr__(self) -> str:
        """Return debug representation."""
        return (
            f"LLMProviderUnavailable(provider={self.provider!r}, "
            f"retry_after={self.retry_after!r})"
        )


class LLMRateLimitExceeded(LLMError):
    """LLM rate limit exceeded.

    Raised when requests exceed the rate limit (default 30 RPM).
    Per ERR2, requests should be queued or retried with backoff.

    Attributes:
        provider: Name of the provider.
        limit: The rate limit that was exceeded.
        retry_after: Seconds to wait before retry.
    """

    def __init__(
        self,
        provider: str,
        limit: int = 30,
        retry_after: int | None = None,
        message: str | None = None,
    ) -> None:
        """Initialize LLMRateLimitExceeded.

        Args:
            provider: Name of the provider.
            limit: Rate limit in RPM.
            retry_after: Seconds to wait before retry.
            message: Optional custom message.
        """
        self.limit = limit
        self.retry_after = retry_after

        if message is None:
            message = f"Rate limit exceeded for '{provider}' ({limit} RPM)."

        super().__init__(message, provider=provider)

    @property
    def context(self) -> dict[str, Any]:
        """Return context for rate limit error."""
        ctx = super().context
        ctx["limit"] = self.limit
        ctx["retry_after"] = self.retry_after
        return ctx

    def __repr__(self) -> str:
        """Return debug representation."""
        return (
            f"LLMRateLimitExceeded(provider={self.provider!r}, "
            f"limit={self.limit!r}, retry_after={self.retry_after!r})"
        )


class LLMTimeoutError(LLMError):
    """LLM request timed out.

    Raised when an LLM request exceeds the timeout threshold.
    Per ERR2, retry 3x with exponential backoff.

    Attributes:
        provider: Name of the provider.
        timeout_seconds: Timeout threshold in seconds.
        request_id: Optional request identifier.
    """

    def __init__(
        self,
        provider: str,
        timeout_seconds: float,
        request_id: str | None = None,
        message: str | None = None,
    ) -> None:
        """Initialize LLMTimeoutError.

        Args:
            provider: Name of the provider.
            timeout_seconds: Timeout threshold.
            request_id: Optional request identifier.
            message: Optional custom message.
        """
        self.timeout_seconds = timeout_seconds
        self.request_id = request_id
        
        if message is None:
            timeout_info = f" ({timeout_seconds}s)"
            message = f"LLM request to '{provider}' timed out{timeout_info}."
            
        super().__init__(message, provider=provider)

    @property
    def context(self) -> dict[str, Any]:
        """Return context for timeout error."""
        ctx = super().context
        ctx["timeout_seconds"] = self.timeout_seconds
        ctx["request_id"] = self.request_id
        return ctx

    def __repr__(self) -> str:
        """Return debug representation."""
        return (
            f"LLMTimeoutError(provider={self.provider!r}, "
            f"timeout_seconds={self.timeout_seconds!r})"
        )


class LLMGatewayNotInitializedError(CyberRedError):
    """LLM Gateway accessed before initialization.
    
    raised when get_gateway() is called before initialize_gateway().
    """
    pass


class LLMResponseError(LLMError):
    """Invalid LLM response format.

    Raised when the LLM response cannot be parsed or
    doesn't match expected format.

    Attributes:
        provider: Name of the provider.
        reason: Description of the format issue.
    """

    def __init__(
        self,
        provider: str,
        reason: str,
        message: str | None = None,
    ) -> None:
        """Initialize LLMResponseError.

        Args:
            provider: Name of the provider.
            reason: Description of the format issue.
            message: Optional custom message.
        """
        self.reason = reason

        if message is None:
            message = f"Invalid response from '{provider}': {reason}."

        super().__init__(message, provider=provider)

    @property
    def context(self) -> dict[str, Any]:
        """Return context for response error."""
        ctx = super().context
        ctx["reason"] = self.reason
        return ctx

    def __repr__(self) -> str:
        """Return debug representation."""
        return (
            f"LLMResponseError(provider={self.provider!r}, "
            f"reason={self.reason!r})"
        )

class ContainerPoolExhausted(CyberRedError):
    """Raised when container pool is exhausted and timeout reached."""
    pass
