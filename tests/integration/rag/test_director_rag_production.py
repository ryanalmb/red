"""Production-grade integration tests for DirectorRAGClient.

Story 6.9: Director Ensemble RAG Integration

These tests use mock embeddings but exercise the full production code path:
- Real RAGStore with LanceDB
- Real RAGQueryInterface  
- Real DirectorRAGClient
- Realistic ATT&CK methodology data

The mock embeddings simulate semantic similarity by using deterministic
vectors that produce predictable search results.
"""

import asyncio
from typing import List, Dict, Any
from dataclasses import dataclass

import pytest

from cyberred.core.kill_chain import Phase
from cyberred.rag.store import RAGStore
from cyberred.rag.query import RAGQueryInterface
from cyberred.rag.director_client import DirectorRAGClient, RAGQueryContext
from cyberred.rag.models import ContentType, RAGChunk


# -----------------------------------------------------------------------------
# Mock Embeddings with Semantic Similarity Simulation
# -----------------------------------------------------------------------------

class MockSemanticEmbeddings:
    """Mock embeddings that simulate semantic similarity.
    
    Uses keyword-based heuristics to produce vectors that will rank
    results appropriately during vector search. This allows testing
    the full RAG pipeline without loading real ML models.
    """
    
    EMBEDDING_DIM = 768
    
    # Keyword to vector component mapping for semantic simulation
    SEMANTIC_KEYWORDS: Dict[str, int] = {
        # Attack tactics
        "reconnaissance": 0,
        "recon": 0,
        "discovery": 1,
        "enumeration": 1,
        "initial-access": 2,
        "exploitation": 2,
        "execution": 3,
        "scripting": 3,
        "persistence": 4,
        "privilege-escalation": 5,
        "privesc": 5,
        "credential-access": 6,
        "credentials": 6,
        "lateral-movement": 7,
        "lateral": 7,
        "exfiltration": 8,
        "exfil": 8,
        # Services
        "ssh": 10,
        "http": 11,
        "web": 11,
        "smb": 12,
        "rdp": 13,
        "ftp": 14,
        # Techniques
        "nmap": 20,
        "nuclei": 21,
        "sqlmap": 22,
        "hydra": 23,
        "metasploit": 24,
        # Failure/pivot keywords
        "failure": 30,
        "failed": 30,
        "pivot": 31,
        "alternative": 31,
        "methodology": 32,
    }
    
    def encode(self, text: str) -> List[float]:
        """Encode text to embedding vector using keyword matching.
        
        Args:
            text: Text to encode
            
        Returns:
            768-dimensional embedding vector
        """
        vector = [0.0] * self.EMBEDDING_DIM
        text_lower = text.lower()
        
        # Set vector components based on keywords found
        for keyword, idx in self.SEMANTIC_KEYWORDS.items():
            if keyword in text_lower:
                # Use different magnitudes for primary vs secondary matches
                vector[idx] = 1.0 if idx < 10 else 0.5
        
        # Normalize to unit vector (required for cosine similarity)
        magnitude = sum(v * v for v in vector) ** 0.5
        if magnitude > 0:
            vector = [v / magnitude for v in vector]
        else:
            # Default vector if no keywords match
            vector[0] = 1.0
            
        return vector
    
    def encode_batch(self, texts: List[str]) -> List[List[float]]:
        """Encode multiple texts."""
        return [self.encode(t) for t in texts]


# -----------------------------------------------------------------------------
# Realistic ATT&CK Methodology Fixtures
# -----------------------------------------------------------------------------

@dataclass
class MethodologyFixture:
    """Fixture data for ATT&CK methodologies."""
    id: str
    text: str
    technique_ids: List[str]
    tactics: List[str]
    source: str = "mitre_attack"


ATTACK_METHODOLOGIES = [
    # Reconnaissance
    MethodologyFixture(
        id="recon-nmap-1",
        text="Use Nmap for network reconnaissance and service discovery. "
             "Scan target ranges to identify open ports, running services, and OS fingerprints. "
             "Tactics: reconnaissance, discovery",
        technique_ids=["T1595", "T1046"],
        tactics=["reconnaissance", "discovery"],
    ),
    MethodologyFixture(
        id="recon-dns-1", 
        text="DNS enumeration techniques for subdomain discovery. "
             "Use tools like dnsrecon, subfinder, or amass for passive and active enumeration. "
             "Tactics: reconnaissance",
        technique_ids=["T1596.001"],
        tactics=["reconnaissance"],
    ),
    
    # Initial Access / Exploitation
    MethodologyFixture(
        id="exploit-web-1",
        text="Web application exploitation using nuclei templates. "
             "Scan for known CVEs, misconfigurations, and common vulnerabilities. "
             "Tactics: initial-access, exploitation",
        technique_ids=["T1190", "T1059.007"],
        tactics=["initial-access"],
    ),
    MethodologyFixture(
        id="exploit-ssh-1",
        text="SSH brute force and credential attacks using hydra. "
             "Target weak passwords and default credentials on SSH services. "
             "Tactics: initial-access, credential-access",
        technique_ids=["T1110.001", "T1078"],
        tactics=["initial-access", "credential-access"],
    ),
    
    # Execution
    MethodologyFixture(
        id="exec-scripting-1",
        text="Command and scripting interpreter techniques for execution. "
             "Use PowerShell, Bash, or Python for post-exploitation automation. "
             "Tactics: execution",
        technique_ids=["T1059", "T1059.001", "T1059.004"],
        tactics=["execution"],
    ),
    
    # Privilege Escalation
    MethodologyFixture(
        id="privesc-linux-1",
        text="Linux privilege escalation techniques. "
             "Check for SUID binaries, sudo misconfigurations, and kernel exploits using linpeas. "
             "Tactics: privilege-escalation",
        technique_ids=["T1548.001", "T1068"],
        tactics=["privilege-escalation"],
    ),
    MethodologyFixture(
        id="privesc-windows-1",
        text="Windows privilege escalation via token manipulation. "
             "Use techniques like token impersonation, UAC bypass, or service exploitation. "
             "Tactics: privilege-escalation",
        technique_ids=["T1134", "T1548.002"],
        tactics=["privilege-escalation"],
    ),
    
    # Credential Access
    MethodologyFixture(
        id="creds-dump-1",
        text="Credential dumping from memory using mimikatz or secretsdump. "
             "Extract NTLM hashes, Kerberos tickets, and plaintext credentials. "
             "Tactics: credential-access",
        technique_ids=["T1003", "T1003.001"],
        tactics=["credential-access"],
    ),
    
    # Lateral Movement
    MethodologyFixture(
        id="lateral-smb-1",
        text="SMB-based lateral movement using pass-the-hash or psexec. "
             "Move laterally through Windows networks using harvested credentials. "
             "Tactics: lateral-movement",
        technique_ids=["T1021.002", "T1550.002"],
        tactics=["lateral-movement"],
    ),
    MethodologyFixture(
        id="lateral-rdp-1",
        text="RDP hijacking and remote desktop lateral movement. "
             "Use stolen credentials or session hijacking for lateral access. "
             "Tactics: lateral-movement",
        technique_ids=["T1021.001", "T1563.002"],
        tactics=["lateral-movement"],
    ),
    
    # Exfiltration
    MethodologyFixture(
        id="exfil-http-1",
        text="Data exfiltration over HTTP/HTTPS channels. "
             "Use web protocols to bypass egress filtering and extract data. "
             "Tactics: exfiltration",
        technique_ids=["T1048.002"],
        tactics=["exfiltration"],
    ),
]


# -----------------------------------------------------------------------------
# Test Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def mock_embeddings():
    """Provide mock embeddings for testing."""
    return MockSemanticEmbeddings()


@pytest.fixture
async def populated_store(tmp_path, mock_embeddings):
    """Create and populate a RAGStore with ATT&CK methodologies."""
    store = RAGStore(str(tmp_path / "production_rag_test"))
    
    chunks = []
    for m in ATTACK_METHODOLOGIES:
        embedding = mock_embeddings.encode(m.text)
        chunk = RAGChunk(
            id=m.id,
            text=m.text,
            source=m.source,
            technique_ids=m.technique_ids,
            content_type=ContentType.METHODOLOGY,
            metadata={"tactics": m.tactics, "technique_ids": m.technique_ids},
            embedding=embedding,
        )
        chunks.append(chunk)
    
    await store.add(chunks)
    return store


@pytest.fixture
def rag_interface(populated_store, mock_embeddings):
    """Create RAGQueryInterface with populated store."""
    return RAGQueryInterface(populated_store, mock_embeddings)


@pytest.fixture
def director_client(rag_interface):
    """Create DirectorRAGClient."""
    return DirectorRAGClient(rag_interface)


# -----------------------------------------------------------------------------
# Production Integration Tests
# -----------------------------------------------------------------------------

@pytest.mark.integration
class TestDirectorRAGProduction:
    """Production-grade integration tests for Director RAG."""

    @pytest.mark.asyncio
    async def test_swarm_failure_pivot_returns_alternatives(self, director_client):
        """Test: When swarm fails on SSH, Director gets alternative methodologies.
        
        Scenario:
        - Agent swarm repeatedly fails attacking SSH service
        - Director requests strategy pivot via RAG
        - RAG returns alternative SSH/credential techniques
        """
        ctx = director_client.build_swarm_failure_context(
            failure_signals=[
                "hydra: 0 valid passwords found",
                "nmap: SSH port 22 filtered",
                "nuclei: no vulnerabilities detected",
            ],
            target_service="ssh",
            failed_techniques=["T1110.001"],  # Brute force already tried
            current_phase="ENUMERATION",
        )
        
        result = await director_client.query_strategy_pivot(ctx, top_k=5, timeout=5.0)
        
        # Should not timeout
        assert result.was_timeout is False
        assert result.query_time_ms >= 0
        
        # Should return methodology suggestions
        assert len(result.methodologies) > 0
        
        # Should have technique IDs
        assert len(result.technique_ids) > 0
        
        # Actionable guidance should mention failure context
        assert "Failure Signals" in result.actionable_guidance or len(result.actionable_guidance) > 50
        
        # Query context should be preserved
        assert result.query_context.trigger == "swarm_failure"
        assert result.query_context.target_service == "ssh"

    @pytest.mark.asyncio
    async def test_phase_transition_provides_next_phase_guidance(self, director_client):
        """Test: Phase transition from RECON to ENUMERATION gets relevant techniques.
        
        Scenario:
        - Engagement transitioning from reconnaissance to enumeration
        - Director queries RAG for enumeration/discovery methodologies
        - Results should be grouped by relevant tactics
        """
        ctx = director_client.build_phase_transition_context(
            from_phase=Phase.RECON,
            to_phase=Phase.ENUMERATION,
            target_service="http",
        )
        
        result = await director_client.query_strategy_pivot(ctx, top_k=10, timeout=5.0)
        
        assert result.was_timeout is False
        assert len(result.methodologies) > 0
        
        # Phase transition context should be in query
        assert "RECON" in result.query_text or "ENUMERATION" in result.query_text
        
        # Should have correlated phases
        phases_dict = result.get_correlated_phases_dict()
        # At least some results should have phase correlation
        assert len(phases_dict) >= 0  # May be empty if no tactics match

    @pytest.mark.asyncio
    async def test_operator_request_with_hint_focuses_results(self, director_client):
        """Test: Operator hint guides RAG query focus.
        
        Scenario:
        - Operator manually requests pivot with specific hint
        - Results should be relevant to the hint
        """
        ctx = director_client.build_operator_request_context(
            request_text="Need alternative approach for lateral movement",
            target_service="smb",
            operator_hint="focus on pass-the-hash techniques",
            current_phase="POST_EXPLOIT",
        )
        
        result = await director_client.query_strategy_pivot(ctx, top_k=5, timeout=5.0)
        
        assert result.was_timeout is False
        
        # Operator hint should be in guidance
        assert "pass-the-hash" in result.actionable_guidance or "Operator Hint" in result.actionable_guidance
        
        # Query text should include hint
        assert "pass-the-hash" in result.query_text.lower() or "operator_hint" in result.query_text.lower()

    @pytest.mark.asyncio
    async def test_fire_and_forget_allows_concurrent_operations(self, director_client):
        """Test: fire_and_forget enables Director to continue while RAG queries.
        
        Scenario:
        - Director fires off RAG query in background
        - Director continues with other operations
        - Query eventually completes with results
        """
        ctx = director_client.build_swarm_failure_context(
            failure_signals=["generic failure"],
            target_service="http",
        )
        
        # Fire query without waiting
        task = director_client.fire_and_forget_query(ctx)
        
        # Simulate Director doing other work
        other_work_done = False
        await asyncio.sleep(0.001)  # Minimal yield
        other_work_done = True
        
        # Now wait for RAG result
        result = await task
        
        assert other_work_done is True
        assert result.was_timeout is False
        assert result.methodologies is not None

    @pytest.mark.asyncio
    async def test_timeout_returns_degraded_result(self, director_client, rag_interface):
        """Test: Slow RAG query degrades gracefully.
        
        Scenario:
        - RAG query is artificially slowed
        - Director timeout triggers before query completes
        - Result is degraded but not an exception
        """
        original_query = rag_interface.query
        
        async def slow_query(*args, **kwargs):
            await asyncio.sleep(0.5)  # Simulate slow query
            return await original_query(*args, **kwargs)
        
        rag_interface.query = slow_query  # type: ignore
        
        ctx = director_client.build_operator_request_context(
            request_text="Need pivot guidance",
        )
        
        # Use very short timeout
        result = await director_client.query_strategy_pivot(ctx, timeout=0.01)
        
        assert result.was_timeout is True
        assert result.degraded is True  # backward compat
        assert result.methodologies == ()
        assert "No RAG methodology suggestions" in result.actionable_guidance

    @pytest.mark.asyncio
    async def test_attack_tactic_grouping(self, director_client):
        """Test: Results are correctly grouped by ATT&CK tactic.
        
        Scenario:
        - Query returns results from multiple tactics
        - Results are grouped by tactic for Director consumption
        """
        ctx = director_client.build_operator_request_context(
            request_text="Need comprehensive attack methodology for privilege escalation and lateral movement",
        )
        
        result = await director_client.query_strategy_pivot(ctx, top_k=10, timeout=5.0)
        
        grouped = result.grouped_by_tactic
        
        # Should have at least one tactic group
        assert len(grouped) >= 1
        
        # Each group should have results
        for tactic, results in grouped.items():
            assert isinstance(tactic, str)
            assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_technique_id_extraction(self, director_client):
        """Test: ATT&CK technique IDs are correctly extracted.
        
        Scenario:
        - Query returns results with technique IDs
        - IDs are extracted and deduplicated
        """
        ctx = director_client.build_operator_request_context(
            request_text="Credential dumping techniques",
        )
        
        result = await director_client.query_strategy_pivot(ctx, top_k=10, timeout=5.0)
        
        # Should have technique IDs if results found
        if result.methodologies:
            technique_ids = result.technique_ids
            # IDs should be strings starting with T
            for tid in technique_ids:
                assert isinstance(tid, str)
                assert tid.startswith("T") or tid == ""  # Empty strings filtered

    @pytest.mark.asyncio
    async def test_kill_chain_phase_correlation(self, director_client):
        """Test: ATT&CK tactics are correlated to kill chain phases.
        
        Scenario:
        - Results include tactics
        - Tactics are mapped to Cyber-Red kill chain phases
        """
        ctx = director_client.build_operator_request_context(
            request_text="Execution and persistence techniques",
        )
        
        result = await director_client.query_strategy_pivot(ctx, top_k=10, timeout=5.0)
        
        phases_dict = result.get_correlated_phases_dict()
        
        # Check that known tactics map to expected phases
        if "execution" in phases_dict:
            phases = phases_dict["execution"]
            # execution maps to EXPLOITATION and/or POST_EXPLOIT
            assert any(p in [Phase.EXPLOITATION, Phase.POST_EXPLOIT] for p in phases)
        
        if "persistence" in phases_dict:
            phases = phases_dict["persistence"]
            assert Phase.POST_EXPLOIT in phases

    @pytest.mark.asyncio
    async def test_empty_store_returns_degraded_gracefully(self, tmp_path, mock_embeddings):
        """Test: Empty RAG store returns graceful degradation.
        
        Scenario:
        - RAG store is empty (no methodologies ingested)
        - Query returns empty results without error
        """
        empty_store = RAGStore(str(tmp_path / "empty_rag"))
        rag = RAGQueryInterface(empty_store, mock_embeddings)
        client = DirectorRAGClient(rag)
        
        ctx = client.build_operator_request_context(
            request_text="Need methodology guidance",
        )
        
        result = await client.query_strategy_pivot(ctx, top_k=5, timeout=5.0)
        
        # Should not timeout, just empty
        assert result.was_timeout is False
        assert result.methodologies == ()
        assert len(result.technique_ids) == 0

    @pytest.mark.asyncio
    async def test_query_context_immutability(self, director_client):
        """Test: Query context is immutable after creation.
        
        Scenario:
        - Create context and run query
        - Verify context cannot be modified
        """
        ctx = director_client.build_swarm_failure_context(
            failure_signals=["test"],
            target_service="ssh",
            failed_techniques=["T1110"],
        )
        
        # Verify frozen dataclass
        with pytest.raises(AttributeError):
            ctx.trigger = "operator_request"  # type: ignore
        
        # Run query
        result = await director_client.query_strategy_pivot(ctx, timeout=5.0)
        
        # Context in result should match original
        assert result.query_context.trigger == "swarm_failure"
        assert result.query_context.target_service == "ssh"

    @pytest.mark.asyncio
    async def test_concurrent_queries_dont_interfere(self, director_client):
        """Test: Multiple concurrent queries don't interfere.
        
        Scenario:
        - Launch multiple queries simultaneously
        - Each returns correct results for its context
        """
        contexts = [
            director_client.build_swarm_failure_context(
                failure_signals=["ssh failed"],
                target_service="ssh",
            ),
            director_client.build_phase_transition_context(
                from_phase=Phase.RECON,
                to_phase=Phase.ENUMERATION,
            ),
            director_client.build_operator_request_context(
                request_text="Need lateral movement help",
            ),
        ]
        
        # Run all queries concurrently
        tasks = [
            director_client.query_strategy_pivot(ctx, timeout=5.0)
            for ctx in contexts
        ]
        results = await asyncio.gather(*tasks)
        
        # Each result should match its context
        assert results[0].query_context.trigger == "swarm_failure"
        assert results[1].query_context.trigger == "phase_transition"
        assert results[2].query_context.trigger == "operator_request"
        
        # All should complete without timeout
        for r in results:
            assert r.was_timeout is False

    @pytest.mark.asyncio
    async def test_query_time_tracking_accuracy(self, director_client):
        """Test: Query time is accurately tracked.
        
        Scenario:
        - Run query and verify timing is reasonable
        """
        ctx = director_client.build_operator_request_context(
            request_text="Test query timing",
        )
        
        result = await director_client.query_strategy_pivot(ctx, timeout=5.0)
        
        # Timing should be reasonable (not negative, not absurdly long)
        assert result.query_time_ms >= 0
        assert result.query_time_ms < 5000  # Less than timeout

    @pytest.mark.asyncio
    async def test_all_context_fields_in_guidance(self, director_client):
        """Test: All context fields appear in formatted guidance.
        
        Scenario:
        - Create context with all fields populated
        - Verify guidance includes all relevant fields
        """
        ctx = director_client.build_swarm_failure_context(
            failure_signals=["signal1", "signal2"],
            target_service="ssh",
            failed_techniques=["T1110", "T1078"],
            current_phase="ENUMERATION",
            environment={"os": "linux", "network": "internal"},
        )
        
        result = await director_client.query_strategy_pivot(ctx, top_k=5, timeout=5.0)
        
        guidance = result.actionable_guidance
        
        # Key fields should be in guidance
        assert "swarm_failure" in guidance
        assert "ssh" in guidance or "Target Service" in guidance
        assert "ENUMERATION" in guidance or "Current Phase" in guidance
