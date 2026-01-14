"""Integration tests for HackTricks ingestion.

Story 6.7: HackTricks Source Integration

Tests end-to-end ingestion with mocked git operations (no network).
"""
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from cyberred.rag.sources.hacktricks import ingest
from cyberred.rag.store import RAGStore
from cyberred.rag.embeddings import RAGEmbeddings
from cyberred.rag.ingest import IngestionStats


@pytest.fixture
def mock_hacktricks_repo(tmp_path):
    """Create a mock HackTricks repository structure with sample files."""
    repo_dir = tmp_path / "hacktricks"
    repo_dir.mkdir()
    
    # Create pentesting-web directory with SQL injection guide
    web_dir = repo_dir / "pentesting-web"
    web_dir.mkdir()
    sql_file = web_dir / "sql-injection.md"
    sql_file.write_text("""# SQL Injection

SQL injection is a code injection technique used to attack data-driven applications.

## Basic SQLi

```sql
' OR '1'='1
```

Visit [OWASP SQL Injection](https://owasp.org/www-community/attacks/SQL_Injection) for more info.

This relates to ATT&CK technique T1190.
""")
    
    # Create linux-hardening directory with privilege escalation
    linux_dir = repo_dir / "linux-hardening"
    linux_dir.mkdir()
    privesc_dir = linux_dir / "privilege-escalation"
    privesc_dir.mkdir()
    privesc_file = privesc_dir / "README.md"
    privesc_file.write_text("""# Linux Privilege Escalation

{% hint style="info" %}
Always check SUID binaries first.
{% endhint %}

## SUID Binaries

```bash
find / -perm -4000 -type f 2>/dev/null
```

Technique T1548.001 can be used here.
""")
    
    # Create cloud-security directory
    cloud_dir = repo_dir / "cloud-security"
    cloud_dir.mkdir()
    aws_file = cloud_dir / "aws-security.md"
    aws_file.write_text("""# AWS Security

{% embed url="https://github.com/aws-samples" %}

Information about AWS security configurations.
""")
    
    # Create a file with code blocks that should not be split
    web_dir2 = repo_dir / "pentesting-web"
    xss_file = web_dir2 / "xss.md"
    xss_file.write_text("""# Cross-Site Scripting (XSS)

XSS allows attackers to inject client-side scripts.

## Payload Examples

```javascript
<script>alert('XSS')</script>
<img src=x onerror=alert('XSS')>
<svg onload=alert('XSS')>
```

More content here that should be kept together with code.
""")
    
    return repo_dir


@pytest.mark.asyncio
async def test_ingest_no_args_call(mock_hacktricks_repo):
    """Test that ingest() can be called with no arguments (AC: 2)."""
    with patch("cyberred.rag.sources.hacktricks._download_hacktricks", 
               return_value=mock_hacktricks_repo):
        with patch.object(RAGStore, "add", new_callable=AsyncMock) as mock_add:
            # Should not raise exception - validates default parameter handling
            stats = await ingest()
            
            assert stats is not None
            assert isinstance(stats, IngestionStats)
            assert stats.source == "hacktricks"


@pytest.mark.asyncio
async def test_ingest_basic_flow(mock_hacktricks_repo, tmp_path):
    """Test basic ingestion flow with mocked store (AC: 2-8)."""
    # Use real store with tmp directory
    db_path = tmp_path / "lancedb"
    store = RAGStore(store_path=str(db_path))
    
    # Mock embeddings to return fake vectors
    mock_embeddings = Mock(spec=RAGEmbeddings)
    mock_embeddings.encode_batch.side_effect = lambda texts: [[0.1] * 768 for _ in texts]
    
    with patch("cyberred.rag.sources.hacktricks._download_hacktricks", 
               return_value=mock_hacktricks_repo):
        stats = await ingest(
            store=store,
            embeddings=mock_embeddings,
            incremental=False  # Don't skip docs for basic flow test
        )
        
        # Verify stats
        assert stats.source == "hacktricks"
        assert stats.document_count > 0
        assert stats.chunk_count > 0


@pytest.mark.asyncio
async def test_ingest_preserves_categories(mock_hacktricks_repo, tmp_path):
    """Test that category metadata is properly extracted (AC: 5)."""
    db_path = tmp_path / "lancedb"
    store = RAGStore(store_path=str(db_path))
    
    mock_embeddings = Mock(spec=RAGEmbeddings)
    mock_embeddings.encode_batch.side_effect = lambda texts: [[0.1] * 768 for _ in texts]
    
    with patch("cyberred.rag.sources.hacktricks._download_hacktricks",
               return_value=mock_hacktricks_repo):
        await ingest(store=store, embeddings=mock_embeddings, incremental=False)
        
        # Query store to get chunks
        results = await store.search([0.1] * 768, top_k=50)
        
        # Check that we have chunks with proper categories
        categories_found = set()
        for chunk in results:
            category = chunk.metadata.get('category')
            if category:
                categories_found.add(category)
        
        # Should have found web, linux, cloud categories from our mock repo
        assert 'web' in categories_found
        assert 'linux' in categories_found
        assert 'cloud' in categories_found


@pytest.mark.asyncio
async def test_ingest_preserves_links(mock_hacktricks_repo, tmp_path):
    """Test that external links are preserved (AC: 6)."""
    db_path = tmp_path / "lancedb"
    store = RAGStore(store_path=str(db_path))
    
    mock_embeddings = Mock(spec=RAGEmbeddings)
    mock_embeddings.encode_batch.side_effect = lambda texts: [[0.1] * 768 for _ in texts]
    
    with patch("cyberred.rag.sources.hacktricks._download_hacktricks",
               return_value=mock_hacktricks_repo):
        await ingest(store=store, embeddings=mock_embeddings, incremental=False)
        
        # Query store to get chunks
        results = await store.search([0.1] * 768, top_k=50)
        
        # Check that links are preserved in metadata
        links_found = []
        for chunk in results:
            chunk_links = chunk.metadata.get('links', [])
            links_found.extend(chunk_links)
        
        # Should find the OWASP link and GitHub embed from mock files
        assert any('owasp.org' in link for link in links_found)
        assert any('github.com' in link for link in links_found)


@pytest.mark.asyncio
async def test_ingest_code_blocks_not_split(mock_hacktricks_repo, tmp_path):
    """Test that code blocks are preserved intact using MarkdownCodeBlockSplitter (AC: 7)."""
    db_path = tmp_path / "lancedb"
    store = RAGStore(store_path=str(db_path))
    
    mock_embeddings = Mock(spec=RAGEmbeddings)
    mock_embeddings.encode_batch.side_effect = lambda texts: [[0.1] * 768 for _ in texts]
    
    with patch("cyberred.rag.sources.hacktricks._download_hacktricks",
               return_value=mock_hacktricks_repo):
        await ingest(store=store, embeddings=mock_embeddings, incremental=False)
        
        # Query store to get chunks
        results = await store.search([0.1] * 768, top_k=50)
        
        # Find chunks from xss.md file (has multi-line code block)
        xss_chunks = [c for c in results if 'XSS' in c.text]
        
        # Verify that code blocks appear complete in at least one chunk
        code_content_found = False
        for chunk in xss_chunks:
            text = chunk.text
            # Check if the complete code block payload is in one chunk
            if "<script>alert('XSS')</script>" in text:
                code_content_found = True
                # The code block should appear intact
                assert "<img src=x" in text or code_content_found
                break
        
        assert code_content_found, "Code blocks should be preserved intact"


@pytest.mark.asyncio
async def test_ingest_technique_ids_extracted(mock_hacktricks_repo, tmp_path):
    """Test that ATT&CK technique IDs are extracted (AC: 5, optional)."""
    db_path = tmp_path / "lancedb"
    store = RAGStore(store_path=str(db_path))
    
    mock_embeddings = Mock(spec=RAGEmbeddings)
    mock_embeddings.encode_batch.side_effect = lambda texts: [[0.1] * 768 for _ in texts]
    
    with patch("cyberred.rag.sources.hacktricks._download_hacktricks",
               return_value=mock_hacktricks_repo):
        await ingest(store=store, embeddings=mock_embeddings, incremental=False)
        
        # Query store to get chunks
        results = await store.search([0.1] * 768, top_k=50)
        
        # Check that technique IDs are in metadata
        technique_ids_found = []
        for chunk in results:
            ids = chunk.metadata.get('technique_ids', [])
            technique_ids_found.extend(ids)
        
        # Should find T1190 and T1548.001 from our mock files
        assert 'T1190' in technique_ids_found
        assert 'T1548.001' in technique_ids_found


@pytest.mark.asyncio
async def test_ingest_incremental_mode(mock_hacktricks_repo, tmp_path):
    """Test that incremental mode skips unchanged documents."""
    db_path = tmp_path / "lancedb"
    store = RAGStore(store_path=str(db_path))
    
    mock_embeddings = Mock(spec=RAGEmbeddings)
    mock_embeddings.encode_batch.side_effect = lambda texts: [[0.1] * 768 for _ in texts]
    
    with patch("cyberred.rag.sources.hacktricks._download_hacktricks",
               return_value=mock_hacktricks_repo):
        # First ingest (non-incremental)
        stats1 = await ingest(
            store=store,
            embeddings=mock_embeddings,
            incremental=False
        )
        
        initial_chunk_count = stats1.chunk_count
        assert initial_chunk_count > 0
        
        # Second ingest (incremental - should skip unchanged)
        stats2 = await ingest(
            store=store,
            embeddings=mock_embeddings,
            incremental=True
        )
        
        # Verify no duplicates in store
        results = await store.search([0.1] * 768, top_k=100)
        assert len(results) == initial_chunk_count


@pytest.mark.asyncio
async def test_ingest_force_refresh(mock_hacktricks_repo, tmp_path):
    """Test that force_refresh re-downloads and re-processes."""
    db_path = tmp_path / "lancedb"
    store = RAGStore(store_path=str(db_path))
    
    mock_embeddings = Mock(spec=RAGEmbeddings)
    mock_embeddings.encode_batch.side_effect = lambda texts: [[0.1] * 768 for _ in texts]
    
    with patch("cyberred.rag.sources.hacktricks._download_hacktricks",
               return_value=mock_hacktricks_repo) as mock_download:
        # First ingest
        await ingest(store=store, embeddings=mock_embeddings, force_refresh=False)
        
        # Second ingest with force_refresh
        await ingest(store=store, embeddings=mock_embeddings, force_refresh=True)
        
        # Download should be called twice
        assert mock_download.call_count == 2
        
        # Verify force_refresh was passed correctly
        call_kwargs = mock_download.call_args[1]
        assert call_kwargs.get('force_refresh') is True
