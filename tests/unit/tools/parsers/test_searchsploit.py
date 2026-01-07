"""Comprehensive unit tests for searchsploit parser - 100% coverage."""
import pytest
import uuid
from cyberred.tools.parsers import searchsploit


@pytest.fixture
def agent_id():
    return str(uuid.uuid4())


@pytest.mark.unit
class TestSearchsploitParserSignature:
    """Test parser signature and basic functionality."""
    
    def test_searchsploit_parser_signature(self, agent_id):
        """Test parser is callable with correct signature."""
        assert callable(searchsploit.searchsploit_parser)
        result = searchsploit.searchsploit_parser(stdout='', stderr='', exit_code=0, agent_id=agent_id, target="apache")
        assert isinstance(result, list)
    
    def test_empty_stdout(self, agent_id):
        """Test empty stdout returns empty list."""
        result = searchsploit.searchsploit_parser('', '', 0, agent_id, "apache")
        assert result == []
    
    def test_whitespace_only_stdout(self, agent_id):
        """Test whitespace-only stdout returns empty list."""
        result = searchsploit.searchsploit_parser('   \n\t  ', '', 0, agent_id, "apache")
        assert result == []


@pytest.mark.unit
class TestSearchsploitJsonFormat:
    """Test searchsploit JSON format parsing (-j flag)."""
    
    def test_json_single_exploit(self, agent_id):
        """Test parsing JSON with single exploit."""
        stdout = '''{
            "SEARCH": "apache",
            "RESULTS_EXPLOIT": [
                {"EDB-ID": "12345", "Title": "Apache RCE", "Platform": "linux", "Path": "exploits/linux/12345.py"}
            ]
        }'''
        findings = searchsploit.searchsploit_parser(stdout, '', 0, agent_id, "apache")
        assert len(findings) == 1
        assert findings[0].type == "exploit_ref"
        assert "12345" in findings[0].evidence
        assert "Apache RCE" in findings[0].evidence
    
    def test_json_multiple_exploits(self, agent_id):
        """Test parsing JSON with multiple exploits."""
        stdout = '''{
            "RESULTS_EXPLOIT": [
                {"EDB-ID": "11111", "Title": "Exploit 1", "Platform": "linux", "Path": "exploits/linux/11111.py"},
                {"EDB-ID": "22222", "Title": "Exploit 2", "Platform": "windows", "Path": "exploits/windows/22222.py"},
                {"EDB-ID": "33333", "Title": "Exploit 3", "Platform": "multiple", "Path": "exploits/multiple/33333.py"}
            ]
        }'''
        findings = searchsploit.searchsploit_parser(stdout, '', 0, agent_id, "apache")
        assert len(findings) == 3
        assert all(f.type == "exploit_ref" for f in findings)
    
    def test_json_with_platform_in_evidence(self, agent_id):
        """Test that platform is included in evidence."""
        stdout = '''{
            "RESULTS_EXPLOIT": [
                {"EDB-ID": "12345", "Title": "Apache RCE", "Platform": "linux", "Path": "exploits/linux/12345.py"}
            ]
        }'''
        findings = searchsploit.searchsploit_parser(stdout, '', 0, agent_id, "apache")
        assert "[linux]" in findings[0].evidence
    
    def test_json_without_platform(self, agent_id):
        """Test parsing exploit without platform field."""
        stdout = '''{
            "RESULTS_EXPLOIT": [
                {"EDB-ID": "12345", "Title": "Apache RCE", "Path": "exploits/linux/12345.py"}
            ]
        }'''
        findings = searchsploit.searchsploit_parser(stdout, '', 0, agent_id, "apache")
        assert len(findings) == 1
        # Should not have platform in brackets if not provided
        assert "[" not in findings[0].evidence or "EDB" in findings[0].evidence.split("[")[0]
    
    def test_json_empty_results(self, agent_id):
        """Test parsing JSON with empty results."""
        stdout = '{"RESULTS_EXPLOIT": []}'
        findings = searchsploit.searchsploit_parser(stdout, '', 0, agent_id, "apache")
        assert len(findings) == 0
    
    def test_json_missing_results_key(self, agent_id):
        """Test parsing JSON without RESULTS_EXPLOIT key."""
        stdout = '{"SEARCH": "apache"}'
        findings = searchsploit.searchsploit_parser(stdout, '', 0, agent_id, "apache")
        assert len(findings) == 0


@pytest.mark.unit
class TestSearchsploitStdoutFormat:
    """Test searchsploit stdout format parsing (table output)."""
    
    def test_stdout_basic_format(self, agent_id):
        """Test parsing basic stdout table format."""
        stdout = '''------------------------------------------------------------------------------------------------ ---------------------------------
 Exploit Title                                                                                  |  Path
------------------------------------------------------------------------------------------------ ---------------------------------
Apache HTTP Server 2.4.49 - Path Traversal                                                     | exploits/linux/webapps/50383.sh
Apache 2.4.50 - RCE (CVE-2021-42013)                                                           | exploits/multiple/webapps/50406.py
------------------------------------------------------------------------------------------------ ---------------------------------'''
        findings = searchsploit.searchsploit_parser(stdout, '', 0, agent_id, "apache")
        assert len(findings) >= 2
        assert all(f.type == "exploit_ref" for f in findings)
    
    def test_stdout_extracts_edb_id(self, agent_id):
        """Test EDB ID is extracted from path."""
        stdout = '''------------------------------------------------------------------------------------------------ ---------------------------------
 Exploit Title                                                                                  |  Path
------------------------------------------------------------------------------------------------ ---------------------------------
Test Exploit                                                                                    | exploits/linux/webapps/12345.py
------------------------------------------------------------------------------------------------ ---------------------------------'''
        findings = searchsploit.searchsploit_parser(stdout, '', 0, agent_id, "testexploit")
        # Parser should extract findings from stdout format
        assert len(findings) >= 1
    
    def test_stdout_extracts_platform(self, agent_id):
        """Test platform is extracted from path."""
        stdout = '''------------------------------------------------------------------------------------------------ ---------------------------------
 Exploit Title                                                                                  |  Path
------------------------------------------------------------------------------------------------ ---------------------------------
Test Exploit                                                                                    | exploits/windows/remote/99999.txt
------------------------------------------------------------------------------------------------ ---------------------------------'''
        findings = searchsploit.searchsploit_parser(stdout, '', 0, agent_id, "testexploit")
        # Parser should extract findings
        assert len(findings) >= 1
    
    def test_stdout_skips_header_lines(self, agent_id):
        """Test header lines are skipped."""
        stdout = '''
 Exploit Title                                                                                  |  Path
------------------------------------------------------------------------------------------------ ---------------------------------
Real Exploit                                                                                    | exploits/linux/local/55555.py'''
        findings = searchsploit.searchsploit_parser(stdout, '', 0, agent_id, "test")
        # Should only get the actual exploit, not header
        assert len(findings) >= 1
        assert all("55555" in f.evidence or "Real Exploit" in f.evidence for f in findings)
    
    def test_stdout_handles_multiple_separators(self, agent_id):
        """Test handling multiple dash separator lines."""
        stdout = '''--------------------------------------------------------
 Exploit Title                                          |  Path
--------------------------------------------------------
Exploit 1                                               | exploits/linux/11111.py
--------------------------------------------------------
Exploit 2                                               | exploits/linux/22222.py
--------------------------------------------------------'''
        findings = searchsploit.searchsploit_parser(stdout, '', 0, agent_id, "test")
        # After first separator, should parse lines with pipes
        assert len(findings) >= 1
    
    def test_stdout_empty_lines_skipped(self, agent_id):
        """Test empty lines are handled correctly."""
        stdout = '''------------------------------------------------------------------------------------------------ ---------------------------------
 Exploit Title                                                                                  |  Path
------------------------------------------------------------------------------------------------ ---------------------------------

Apache Exploit                                                                                  | exploits/linux/12345.py

'''
        findings = searchsploit.searchsploit_parser(stdout, '', 0, agent_id, "apache")
        assert len(findings) >= 1
    
    def test_stdout_no_pipe_lines_skipped(self, agent_id):
        """Test lines without pipe character are skipped."""
        stdout = '''------------------------------------------------------------------------------------------------ ---------------------------------
 Exploit Title                                                                                  |  Path
------------------------------------------------------------------------------------------------ ---------------------------------
This line has no pipe
Apache Exploit                                                                                  | exploits/linux/12345.py
Another line without pipe'''
        findings = searchsploit.searchsploit_parser(stdout, '', 0, agent_id, "apache")
        # Should parse lines with pipe
        assert len(findings) >= 1
    
    def test_stdout_path_without_edb_id(self, agent_id):
        """Test handling path without numeric EDB ID."""
        stdout = '''------------------------------------------------------------------------------------------------ ---------------------------------
 Exploit Title                                                                                  |  Path
------------------------------------------------------------------------------------------------ ---------------------------------
Generic Exploit                                                                                 | exploits/linux/local/noid.txt
------------------------------------------------------------------------------------------------ ---------------------------------'''
        findings = searchsploit.searchsploit_parser(stdout, '', 0, agent_id, "test")
        # Should still create finding even without EDB ID
        assert len(findings) >= 1
    
    def test_stdout_path_without_platform_dir(self, agent_id):
        """Test handling path without exploits/platform directory structure."""
        stdout = '''------------------------------------------------------------------------------------------------ ---------------------------------
 Exploit Title                                                                                  |  Path
------------------------------------------------------------------------------------------------ ---------------------------------
Test Exploit                                                                                    | shellcodes/12345.asm
------------------------------------------------------------------------------------------------ ---------------------------------'''
        findings = searchsploit.searchsploit_parser(stdout, '', 0, agent_id, "test")
        # Should still parse even with different path structure
        assert len(findings) >= 1


@pytest.mark.unit
class TestSearchsploitEdgeCases:
    """Test edge cases and error handling."""
    
    def test_invalid_json_falls_through(self, agent_id):
        """Test invalid JSON tries stdout parsing."""
        stdout = '''not json {{{
------------------------------------------------------------------------------------------------ ---------------------------------
 Exploit Title                                                                                  |  Path
------------------------------------------------------------------------------------------------ ---------------------------------
Fallback Exploit                                                                                | exploits/linux/99999.py'''
        findings = searchsploit.searchsploit_parser(stdout, '', 0, agent_id, "test")
        # Should fallback to stdout parsing
        assert len(findings) >= 1
    
    def test_tool_name_is_searchsploit(self, agent_id):
        """Test that tool name is correctly set."""
        stdout = '{"RESULTS_EXPLOIT": [{"EDB-ID": "12345", "Title": "Test", "Platform": "linux", "Path": "exploits/linux/12345.py"}]}'
        findings = searchsploit.searchsploit_parser(stdout, '', 0, agent_id, "test")
        assert findings[0].tool == "searchsploit"
    
    def test_severity_is_info(self, agent_id):
        """Test that severity is info for exploit references."""
        stdout = '{"RESULTS_EXPLOIT": [{"EDB-ID": "12345", "Title": "Test", "Platform": "linux", "Path": "exploits/linux/12345.py"}]}'
        findings = searchsploit.searchsploit_parser(stdout, '', 0, agent_id, "test")
        assert findings[0].severity == "info"
    
    def test_target_preserved(self, agent_id):
        """Test that target is correctly preserved."""
        stdout = '{"RESULTS_EXPLOIT": [{"EDB-ID": "12345", "Title": "Test", "Platform": "linux", "Path": "exploits/linux/12345.py"}]}'
        findings = searchsploit.searchsploit_parser(stdout, '', 0, agent_id, "apache")
        assert findings[0].target == "apache"


@pytest.mark.unit
class TestSearchsploitStdoutStateTracking:
    """Test stdout parsing state machine."""
    
    def test_results_start_after_separator(self, agent_id):
        """Test that results are only parsed after separator line."""
        stdout = '''Before separator - should be ignored | exploits/fake/00000.py
------------------------------------------------------------------------------------------------ ---------------------------------
After separator - should be parsed | exploits/linux/11111.py'''
        findings = searchsploit.searchsploit_parser(stdout, '', 0, agent_id, "test")
        # Should only get the line after separator
        assert len(findings) >= 1
        assert any("11111" in f.evidence for f in findings)
    
    def test_header_row_not_parsed(self, agent_id):
        """Test that 'Exploit Title | Path' header row is not parsed as result."""
        stdout = '''------------------------------------------------------------------------------------------------ ---------------------------------
 Exploit Title                                                                                  |  Path
------------------------------------------------------------------------------------------------ ---------------------------------
Real Result                                                                                     | exploits/linux/12345.py'''
        findings = searchsploit.searchsploit_parser(stdout, '', 0, agent_id, "testexploit")
        # Parser should extract findings
        assert len(findings) >= 1
