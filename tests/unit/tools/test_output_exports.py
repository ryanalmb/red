"""Export verification tests for OutputProcessor module.

Story 4.5 requires explicit export testing as per Dev Notes pattern.
"""
import pytest


@pytest.mark.unit
def test_output_processor_export():
    """Verify OutputProcessor is exported from cyberred.tools."""
    from cyberred.tools import OutputProcessor
    assert OutputProcessor is not None


@pytest.mark.unit
def test_processed_output_export():
    """Verify ProcessedOutput is exported from cyberred.tools."""
    from cyberred.tools import ProcessedOutput
    assert ProcessedOutput is not None


@pytest.mark.unit
def test_all_list_contains_exports():
    """Verify __all__ contains required exports."""
    from cyberred.tools import __all__
    assert "OutputProcessor" in __all__
    assert "ProcessedOutput" in __all__
