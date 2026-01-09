"""Intelligence Error Metrics Tracking."""

from typing import Dict, Any

class IntelligenceErrorMetrics:
    """Track intelligence source error and timeout rates."""
    
    def __init__(self) -> None:
        self._timeouts: Dict[str, int] = {}
        self._errors: Dict[str, Dict[str, int]] = {}  # source -> {error_type: count}
    
    def record_timeout(self, source_name: str) -> None:
        """Record a source timeout.
        
        Args:
            source_name: Name of the source that timed out.
        """
        self._timeouts[source_name] = self._timeouts.get(source_name, 0) + 1
    
    def record_error(self, source_name: str, error_type: str) -> None:
        """Record a source error.
        
        Args:
            source_name: Name of the source that errored.
            error_type: Type of error (e.g., "ConnectionError", "ValueError").
        """
        if source_name not in self._errors:
            self._errors[source_name] = {}
        self._errors[source_name][error_type] = (
            self._errors[source_name].get(error_type, 0) + 1
        )

    def get_metrics(self) -> Dict[str, Any]:
        """Get all error metrics.
        
        Returns:
            Dict containing timeouts, errors, total_timeouts, and total_errors.
        """
        return {
            "timeouts": dict(self._timeouts),
            "errors": {k: dict(v) for k, v in self._errors.items()},
            "total_timeouts": sum(self._timeouts.values()),
            "total_errors": sum(
                sum(v.values()) for v in self._errors.values()
            ),
        }
    
    def get_source_metrics(self, source_name: str) -> Dict[str, Any]:
        """Get metrics for a specific source.
        
        Args:
            source_name: Name of the source.
            
        Returns:
            Dict containing timeouts and errors for the source.
        """
        return {
            "timeouts": self._timeouts.get(source_name, 0),
            "errors": dict(self._errors.get(source_name, {})),
        }
    
    def reset(self) -> None:
        """Reset all metrics."""
        self._timeouts.clear()
        self._errors.clear()
