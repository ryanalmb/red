"""Waiver Pre-Flight Check for Story 13.9.

This module implements a pre-flight check that validates the presence
of a waiver acceptance record in engagement configuration before allowing
the engagement to start.
"""

from pathlib import Path
from typing import Any

import structlog

from cyberred.daemon.preflight import (
    PreFlightCheck,
    CheckResult,
    CheckStatus,
    CheckPriority,
)

log = structlog.get_logger()


class WaiverPreFlightCheck(PreFlightCheck):
    """Pre-flight check for waiver acceptance validation.
    
    Validates that:
    1. Engagement config contains waiver_hash field
    2. waiver_hash is a valid SHA-256 format (64 hex characters)
    3. waiver_timestamp is present
    
    This is a P0 (blocking) check - engagement cannot start without
    a valid waiver acceptance record.
    """
    
    @property
    def name(self) -> str:
        """Check name for reporting."""
        return "Waiver Acceptance"
    
    @property
    def priority(self) -> CheckPriority:
        """Check priority - P0 (blocking)."""
        return CheckPriority.P0
    
    async def execute(self, config: dict[str, Any]) -> CheckResult:
        """Execute waiver validation check.
        
        Args:
            config: Engagement configuration dict.
        
        Returns:
            CheckResult with PASS if waiver valid, FAIL otherwise.
        """
        # Check for waiver_hash field
        waiver_hash = config.get("waiver_hash")
        
        if not waiver_hash:
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAIL,
                priority=self.priority,
                message="No waiver acceptance found. Engagement requires pre-engagement liability waiver.",
                details={
                    "required_field": "waiver_hash",
                    "action": "Complete waiver acceptance before starting engagement",
                }
            )
        
        # Validate waiver_hash format (SHA-256 = 64 hex characters)
        if not isinstance(waiver_hash, str) or len(waiver_hash) != 64:
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAIL,
                priority=self.priority,
                message=f"Invalid waiver hash format: expected 64 hex characters, got {len(waiver_hash) if isinstance(waiver_hash, str) else 'non-string'}",
                details={
                    "waiver_hash": waiver_hash,
                    "expected_format": "SHA-256 (64 hex characters)",
                }
            )
        
        # Validate it's hexadecimal
        try:
            int(waiver_hash, 16)
        except ValueError:
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAIL,
                priority=self.priority,
                message="Invalid waiver hash: not a valid hexadecimal string",
                details={
                    "waiver_hash": waiver_hash,
                }
            )
        
        # Check for waiver_timestamp
        waiver_timestamp = config.get("waiver_timestamp")
        
        if not waiver_timestamp:
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAIL,
                priority=self.priority,
                message="Waiver hash present but missing timestamp",
                details={
                    "required_field": "waiver_timestamp",
                }
            )
        
        # All checks passed
        log.info(
            "waiver_preflight_passed",
            waiver_hash=waiver_hash[:16] + "...",  # Log first 16 chars only
            waiver_timestamp=waiver_timestamp,
        )
        
        return CheckResult(
            name=self.name,
            status=CheckStatus.PASS,
            priority=self.priority,
            message="Waiver acceptance validated",
            details={
                "waiver_hash": waiver_hash[:16] + "...",
                "waiver_timestamp": waiver_timestamp,
                "waiver_signature": config.get("waiver_signature", "N/A"),
            }
        )
