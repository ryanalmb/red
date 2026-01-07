import pytest
from cyberred.core.exceptions import CyberRedError

def test_exceptions_structure():
    """Test that preflight exceptions exist and inherit correctly."""
    from cyberred.core.exceptions import PreFlightCheckError, PreFlightWarningError
    
    # Verify inheritance
    assert issubclass(PreFlightCheckError, CyberRedError)
    assert issubclass(PreFlightWarningError, CyberRedError)
