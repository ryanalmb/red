
import pytest
import time
import shutil
from pathlib import Path
from cyberred.tools.output import OutputProcessor
from cyberred.core.models import Finding
from typing import List, Any

# Initial parser content (Version 1)
PARSER_V1 = """
from typing import List, Any
import uuid
from cyberred.core.models import Finding

def parse(stdout: str, stderr: str, exit_code: int, agent_id: str, target: str) -> List[Any]:
    return [Finding(
        id=str(uuid.uuid4()), 
        type="test_v1", 
        severity="info", 
        target=target, 
        evidence="v1 evidence", 
        agent_id=agent_id, 
        timestamp="2023-01-01T00:00:00+00:00", 
        tool="integ_test", 
        topic="topic", 
        signature=""
    )]
"""

# Updated parser content (Version 2)
PARSER_V2 = """
from typing import List, Any
import uuid
from cyberred.core.models import Finding

def parse(stdout: str, stderr: str, exit_code: int, agent_id: str, target: str) -> List[Any]:
    return [Finding(
        id=str(uuid.uuid4()), 
        type="test_v2", 
        severity="high", 
        target=target, 
        evidence="v2 evidence", 
        agent_id=agent_id, 
        timestamp="2023-01-01T00:00:00+00:00", 
        tool="integ_test", 
        topic="topic", 
        signature=""
    )]
"""

class TestParserHotReloadIntegration:
    """Integration tests for Parser Hot Reload feature."""
    
    @pytest.fixture
    def parsers_dir(self, tmp_path):
        """Create a temporary directory for parsers."""
        p = tmp_path / "custom_parsers"
        p.mkdir()
        return p
        
    @pytest.fixture
    def processor(self, parsers_dir):
        """Initialize OutputProcessor with the temp dir and start watcher."""
        proc = OutputProcessor(parsers_dir=parsers_dir)
        proc.start_watcher()
        yield proc
        proc.stop_watcher()

    def wait_for_condition(self, condition_func, timeout=5.0, interval=0.1):
        """Helper to wait for a condition to become true."""
        start = time.time()
        while time.time() - start < timeout:
            if condition_func():
                return True
            time.sleep(interval)
        return False

    def test_full_lifecycle(self, parsers_dir, processor):
        """Verify Create -> Update -> Delete lifecycle."""
        
        parser_path = parsers_dir / "integ_test.py"
        agent_id = "00000000-0000-0000-0000-000000000000"
        
        # 1. CREATE
        print(f"\n[INTEG] Creating parser at {parser_path}")
        parser_path.write_text(PARSER_V1)
        
        # Wait for registration
        assert self.wait_for_condition(lambda: "integ_test" in processor.get_registered_parsers()), \
            "Parser was not registered after creation"
            
        # Verify execution V1
        result = processor.process("out", "err", "integ_test", 0, agent_id, "target")
        assert result.tier == 1
        assert len(result.findings) > 0
        assert result.findings[0].type == "test_v1"
        
        # 2. UPDATE
        print(f"[INTEG] Updating parser at {parser_path}")
        # Ensure mtime changes
        time.sleep(1.1) 
        parser_path.write_text(PARSER_V2)
        
        # Wait for reload (check if output changes)
        def check_v2():
            res = processor.process("out", "err", "integ_test", 0, agent_id, "target")
            return res.tier == 1 and res.findings[0].type == "test_v2"
            
        assert self.wait_for_condition(check_v2), "Parser was not updated to V2"
        
        # 3. DELETE
        print(f"[INTEG] Deleting parser at {parser_path}")
        parser_path.unlink()
        
        # Wait for unregistration
        assert self.wait_for_condition(lambda: "integ_test" not in processor.get_registered_parsers()), \
            "Parser was not unregistered after deletion"
            
        # Verify fallback (Tier 2/3)
        # Note: process() will fall back to Tier 2 (LLM) or Tier 3 if parser missing.
        # Since we don't hold the lock during the whole process check, strictly speaking
        # it isn't in registered parsers.
        result = processor.process("out", "err", "integ_test", 0, agent_id, "target")
        assert result.tier != 1, "Should not use Tier 1 parser after deletion"

    def test_lifecycle_logging(self, parsers_dir, processor, caplog):
        """Verify lifecycle events emit expected log messages (AC5)."""
        import logging
        caplog.set_level(logging.INFO)
        
        parser_path = parsers_dir / "log_test.py"
        agent_id = "00000000-0000-0000-0000-000000000000"
        
        # Create parser
        parser_path.write_text(PARSER_V1.replace("integ_test", "log_test"))
        assert self.wait_for_condition(lambda: "log_test" in processor.get_registered_parsers())
        
        # Verify registration log
        assert any("parser_reloaded" in record.message or "parser_registered" in record.message 
                   for record in caplog.records), \
            f"Expected parser registration log. Got: {[r.message for r in caplog.records]}"
        
        caplog.clear()
        
        # Update parser
        time.sleep(1.1)
        parser_path.write_text(PARSER_V2.replace("integ_test", "log_test"))
        
        def check_updated():
            res = processor.process("out", "err", "log_test", 0, agent_id, "target")
            return res.tier == 1 and res.findings[0].type == "test_v2"
        assert self.wait_for_condition(check_updated)
        
        # Verify reload log
        assert any("parser_reloaded" in record.message for record in caplog.records), \
            f"Expected parser_reloaded log. Got: {[r.message for r in caplog.records]}"
        
        caplog.clear()
        
        # Delete parser
        parser_path.unlink()
        assert self.wait_for_condition(lambda: "log_test" not in processor.get_registered_parsers())
        
        # Verify unregistration log
        assert any("parser_deleted" in record.message or "parser_unregistered" in record.message 
                   for record in caplog.records), \
            f"Expected parser unregistration log. Got: {[r.message for r in caplog.records]}"

    def test_debounce_rapid_changes(self, parsers_dir, processor):
        """Verify rapid file changes are debounced into single reload (AC7)."""
        parser_path = parsers_dir / "debounce_test.py"
        agent_id = "00000000-0000-0000-0000-000000000000"
        
        # Create initial parser
        parser_path.write_text(PARSER_V1.replace("integ_test", "debounce_test").replace("test_v1", "version_0"))
        assert self.wait_for_condition(lambda: "debounce_test" in processor.get_registered_parsers())
        
        # Rapid fire changes (3 changes in ~100ms, well within 500ms debounce)
        for i in range(1, 4):
            content = PARSER_V1.replace("integ_test", "debounce_test").replace("test_v1", f"version_{i}")
            parser_path.write_text(content)
            time.sleep(0.03)  # 30ms between each write
        
        # Wait for debounce window (500ms) + some buffer
        time.sleep(0.7)
        
        # Verify only the LAST version is active
        result = processor.process("out", "err", "debounce_test", 0, agent_id, "target")
        assert result.tier == 1, "Parser should be registered"
        assert result.findings[0].type == "version_3", \
            f"Expected version_3 (last write), got {result.findings[0].type}"
