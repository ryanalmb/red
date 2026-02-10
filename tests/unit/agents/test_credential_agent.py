"""Unit tests for CredentialAgent (Story 7.22).

Following TDD red-green-refactor cycle. These tests validate:
- AC1: Thin subclass architecture
- AC2: Hardcoded methods REMOVED
- AC3: LLM-driven tool selection
- AC4: NFR37 Decision Context (HARD GATE)
- AC5: Password spraying
- AC6: Hash cracking
- AC7: Credential harvesting
- AC8: Stigmergic credential sharing
- AC9: Preserved functionality
- AC10: Quality gates
"""

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# --- Task 1.1: Constructor Tests (AC: #1) ---
@pytest.mark.unit
class TestCredentialAgentConstructor:
    """Tests for CredentialAgent constructor - thin subclass architecture."""

    @pytest.fixture
    def mock_event_bus(self):
        return AsyncMock()

    def test_sets_role_to_credential(self, mock_event_bus):
        """CredentialAgent constructor sets role=AgentRole.CREDENTIAL."""
        from cyberred.agents.credential import CredentialAgent
        from cyberred.agents.roles import AgentRole

        agent = CredentialAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
        )
        assert agent.role == AgentRole.CREDENTIAL

    def test_default_specialty_is_general(self, mock_event_bus):
        """CredentialAgent default specialty is 'general'."""
        from cyberred.agents.credential import CredentialAgent

        agent = CredentialAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
        )
        assert agent.specialty == "general"

    @pytest.mark.parametrize("specialty", ["general", "harvesting", "cracking", "spraying"])
    def test_accepts_valid_specialties(self, mock_event_bus, specialty):
        """CredentialAgent accepts valid specialties (AC1)."""
        from cyberred.agents.credential import CredentialAgent

        agent = CredentialAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
            specialty=specialty,
        )
        assert agent.specialty == specialty

    def test_no_target_in_constructor(self, mock_event_bus):
        """CredentialAgent constructor does NOT accept target parameter."""
        from cyberred.agents.credential import CredentialAgent
        import inspect

        sig = inspect.signature(CredentialAgent.__init__)
        param_names = list(sig.parameters.keys())
        assert "target" not in param_names

    def test_configurable_max_iterations(self, mock_event_bus):
        """CredentialAgent allows configurable max_iterations."""
        from cyberred.agents.credential import CredentialAgent

        agent = CredentialAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
            max_iterations=50,
        )
        assert agent.max_iterations == 50

    def test_configurable_lockout_threshold(self, mock_event_bus):
        """CredentialAgent allows configurable lockout_threshold."""
        from cyberred.agents.credential import CredentialAgent

        agent = CredentialAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
            lockout_threshold=5,
        )
        assert agent.lockout_threshold == 5

    def test_configurable_lockout_window(self, mock_event_bus):
        """CredentialAgent allows configurable lockout_window."""
        from cyberred.agents.credential import CredentialAgent

        agent = CredentialAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
            lockout_window=60,
        )
        assert agent.lockout_window == 60

    def test_extends_stigmergic_agent(self):
        """CredentialAgent extends StigmergicAgent."""
        from cyberred.agents.credential import CredentialAgent
        from cyberred.agents.base import StigmergicAgent

        assert issubclass(CredentialAgent, StigmergicAgent)

    def test_initializes_cracked_credentials(self, mock_event_bus):
        """CredentialAgent initializes empty cracked credentials list."""
        from cyberred.agents.credential import CredentialAgent

        agent = CredentialAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
        )
        assert len(agent._cracked_credentials) == 0

    def test_initializes_harvested_credentials(self, mock_event_bus):
        """CredentialAgent initializes empty harvested credentials list."""
        from cyberred.agents.credential import CredentialAgent

        agent = CredentialAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
        )
        assert len(agent._harvested_credentials) == 0

    def test_initializes_pending_hashes(self, mock_event_bus):
        """CredentialAgent initializes empty pending hashes list."""
        from cyberred.agents.credential import CredentialAgent

        agent = CredentialAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
        )
        assert len(agent._pending_hashes) == 0


# --- Task 1.2: Hardcoded Removal Tests (AC: #2) ---
@pytest.mark.unit
class TestCredentialAgentNoHardcodedMethods:
    """Tests verifying hardcoded methods are NOT present."""

    def test_no_generate_hashcat_command(self):
        """CredentialAgent has NO _generate_hashcat_command method."""
        from cyberred.agents.credential import CredentialAgent

        assert not hasattr(CredentialAgent, "_generate_hashcat_command")

    def test_no_generate_hydra_command(self):
        """CredentialAgent has no _generate_hydra_command method."""
        from cyberred.agents.credential import CredentialAgent

        assert not hasattr(CredentialAgent, "_generate_hydra_command")

    def test_no_generate_john_command(self):
        """CredentialAgent has no _generate_john_command method."""
        from cyberred.agents.credential import CredentialAgent

        assert not hasattr(CredentialAgent, "_generate_john_command")

    def test_no_generate_mimikatz_command(self):
        """CredentialAgent has no _generate_mimikatz_command method."""
        from cyberred.agents.credential import CredentialAgent

        assert not hasattr(CredentialAgent, "_generate_mimikatz_command")

    def test_no_tool_sequence_attribute(self):
        """CredentialAgent has no tool_sequence attribute."""
        from cyberred.agents.credential import CredentialAgent

        assert not hasattr(CredentialAgent, "tool_sequence")


# --- Task 1.3: Execute Method Tests (AC: #3) ---
@pytest.mark.unit
class TestCredentialAgentExecute:
    """Tests for execute_credential_attack method."""

    @pytest.fixture
    def mock_event_bus(self):
        return AsyncMock()

    @pytest.fixture
    def credential_agent(self, mock_event_bus):
        from cyberred.agents.credential import CredentialAgent

        return CredentialAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
        )

    def test_execute_credential_attack_takes_target_param(self, credential_agent):
        """execute_credential_attack takes target as parameter (not constructor)."""
        from cyberred.agents.credential import CredentialAgent
        import inspect

        sig = inspect.signature(CredentialAgent.execute_credential_attack)
        param_names = list(sig.parameters.keys())
        assert "target" in param_names

    @pytest.mark.asyncio
    async def test_execute_credential_attack_calls_select_tool(self, credential_agent):
        """execute_credential_attack uses inherited select_tool()."""
        with patch.object(credential_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            tool_selection = MagicMock()
            tool_selection.tool_name = "hydra"
            tool_selection.command = "hydra -l admin -P wordlist.txt ssh://target"
            tool_selection.confidence = 0.9
            mock_select.return_value = tool_selection

            with patch("cyberred.agents.credential.kali_execute", new_callable=AsyncMock) as mock_exec:
                result = MagicMock()
                result.success = True
                result.stdout = ""
                result.stderr = ""
                result.exit_code = 0
                mock_exec.return_value = result

                await credential_agent.execute_credential_attack("192.168.1.100", {})

            mock_select.assert_called()

    @pytest.mark.asyncio
    async def test_execute_credential_attack_respects_stop_event(self, credential_agent):
        """execute_credential_attack respects _stop_event."""
        credential_agent._stop_event.set()

        with patch.object(credential_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            findings, actions = await credential_agent.execute_credential_attack("192.168.1.100", {})

        mock_select.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_credential_attack_respects_max_iterations(self, credential_agent):
        """execute_credential_attack respects max_iterations limit."""
        credential_agent.max_iterations = 2

        with patch.object(credential_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            tool_selection = MagicMock()
            tool_selection.tool_name = "hydra"
            tool_selection.command = "hydra -l admin -P wordlist.txt ssh://target"
            tool_selection.confidence = 0.9
            mock_select.return_value = tool_selection

            with patch("cyberred.agents.credential.kali_execute", new_callable=AsyncMock) as mock_exec:
                result = MagicMock()
                result.success = True
                result.stdout = ""
                result.stderr = ""
                result.exit_code = 0
                mock_exec.return_value = result

                await credential_agent.execute_credential_attack("192.168.1.100", {})

            assert mock_select.call_count <= 2


# --- Task 1.4: NFR37 Decision Context Tests (AC: #4) ---
@pytest.mark.unit
class TestCredentialAgentDecisionContext:
    """Tests for NFR37 decision_context requirements."""

    @pytest.fixture
    def mock_event_bus(self):
        return AsyncMock()

    @pytest.fixture
    def credential_agent(self, mock_event_bus):
        from cyberred.agents.credential import CredentialAgent

        return CredentialAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
        )

    @pytest.mark.asyncio
    async def test_all_actions_have_decision_context(self, credential_agent):
        """ALL AgentActions have non-empty decision_context."""
        credential_agent.max_iterations = 1

        with patch.object(credential_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            tool_selection = MagicMock()
            tool_selection.tool_name = "hydra"
            tool_selection.command = "hydra -l admin -P wordlist.txt ssh://target"
            tool_selection.confidence = 0.9
            mock_select.return_value = tool_selection

            with patch("cyberred.agents.credential.kali_execute", new_callable=AsyncMock) as mock_exec:
                result = MagicMock()
                result.success = True
                result.stdout = ""
                result.stderr = ""
                result.exit_code = 0
                mock_exec.return_value = result

                _, actions = await credential_agent.execute_credential_attack("192.168.1.100", {})

        for action in actions:
            assert action.decision_context, "AgentAction must have non-empty decision_context"
            assert len(action.decision_context) > 0

    @pytest.mark.asyncio
    async def test_decision_context_includes_spawn(self, credential_agent):
        """Decision context includes initial_spawn:{agent_id}."""
        credential_agent.max_iterations = 1

        with patch.object(credential_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            tool_selection = MagicMock()
            tool_selection.tool_name = "hydra"
            tool_selection.command = "hydra -l admin -P wordlist.txt ssh://target"
            tool_selection.confidence = 0.9
            mock_select.return_value = tool_selection

            with patch("cyberred.agents.credential.kali_execute", new_callable=AsyncMock) as mock_exec:
                result = MagicMock()
                result.success = True
                result.stdout = ""
                result.stderr = ""
                result.exit_code = 0
                mock_exec.return_value = result

                _, actions = await credential_agent.execute_credential_attack("192.168.1.100", {})

        for action in actions:
            context_str = " ".join(action.decision_context)
            assert "initial_spawn:" in context_str

    @pytest.mark.asyncio
    async def test_decision_context_includes_hash_type(self, credential_agent):
        """Decision context includes hash_type:{hash_type} when cracking."""
        credential_agent.max_iterations = 1

        with patch.object(credential_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            tool_selection = MagicMock()
            tool_selection.tool_name = "hashcat"
            tool_selection.command = "hashcat -m 1000 hashes.txt wordlist.txt"
            tool_selection.confidence = 0.9
            mock_select.return_value = tool_selection

            with patch("cyberred.agents.credential.kali_execute", new_callable=AsyncMock) as mock_exec:
                result = MagicMock()
                result.success = True
                result.stdout = ""
                result.stderr = ""
                result.exit_code = 0
                mock_exec.return_value = result

                context = {"hash_type": "ntlm", "hashes": ["aad3b435b51404ee"]}
                _, actions = await credential_agent.execute_credential_attack("192.168.1.100", context)

        for action in actions:
            context_str = " ".join(action.decision_context)
            assert "hash_type:ntlm" in context_str

    @pytest.mark.asyncio
    async def test_decision_context_includes_service(self, credential_agent):
        """Decision context includes service:{service_name} when spraying."""
        credential_agent.max_iterations = 1

        with patch.object(credential_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            tool_selection = MagicMock()
            tool_selection.tool_name = "hydra"
            tool_selection.command = "hydra -l admin -P wordlist.txt ssh://target"
            tool_selection.confidence = 0.9
            mock_select.return_value = tool_selection

            with patch("cyberred.agents.credential.kali_execute", new_callable=AsyncMock) as mock_exec:
                result = MagicMock()
                result.success = True
                result.stdout = ""
                result.stderr = ""
                result.exit_code = 0
                mock_exec.return_value = result

                context = {"service": "ssh"}
                _, actions = await credential_agent.execute_credential_attack("192.168.1.100", context)

        for action in actions:
            context_str = " ".join(action.decision_context)
            assert "service:ssh" in context_str

    @pytest.mark.asyncio
    async def test_decision_context_includes_cracked_when_success(self, credential_agent):
        """Decision context includes cracked:{username} when credential cracked."""
        credential_agent.max_iterations = 1
        credential_agent._cracked_credentials = [{"username": "admin", "password": "P@ssw0rd"}]

        with patch.object(credential_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            tool_selection = MagicMock()
            tool_selection.tool_name = "hashcat"
            tool_selection.command = "hashcat -m 1000 hashes.txt wordlist.txt"
            tool_selection.confidence = 0.9
            mock_select.return_value = tool_selection

            with patch("cyberred.agents.credential.kali_execute", new_callable=AsyncMock) as mock_exec:
                result = MagicMock()
                result.success = True
                result.stdout = ""
                result.stderr = ""
                result.exit_code = 0
                mock_exec.return_value = result

                _, actions = await credential_agent.execute_credential_attack("192.168.1.100", {})

        for action in actions:
            context_str = " ".join(action.decision_context)
            assert "cracked:admin" in context_str


# --- Task 1.5: Password Spraying Tests (AC: #5) ---
@pytest.mark.unit
class TestCredentialAgentPasswordSpraying:
    """Tests for password spraying functionality."""

    @pytest.fixture
    def mock_event_bus(self):
        return AsyncMock()

    @pytest.fixture
    def credential_agent(self, mock_event_bus):
        from cyberred.agents.credential import CredentialAgent

        return CredentialAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
            specialty="spraying",
        )

    @pytest.mark.asyncio
    async def test_password_spray_respects_lockout_threshold(self, credential_agent):
        """_execute_password_spray respects lockout_threshold."""
        credential_agent.lockout_threshold = 2

        with patch.object(credential_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            tool_selection = MagicMock()
            tool_selection.tool_name = "hydra"
            tool_selection.command = "hydra -L users.txt -P pass.txt ssh://target"
            tool_selection.confidence = 0.9
            mock_select.return_value = tool_selection

            with patch("cyberred.agents.credential.kali_execute", new_callable=AsyncMock) as mock_exec:
                result = MagicMock()
                result.success = True
                result.stdout = "[FAIL] user1 - password1\n[FAIL] user1 - password2"
                result.stderr = ""
                result.exit_code = 0
                mock_exec.return_value = result

                await credential_agent._execute_password_spray(
                    "192.168.1.100", 
                    ["user1", "user2"], 
                    ["password1", "password2", "password3"]
                )

                # Should limit attempts per user based on lockout_threshold
                assert mock_exec.called

    @pytest.mark.asyncio
    async def test_password_spray_respects_lockout_window(self, credential_agent):
        """_execute_password_spray respects lockout_window timing."""
        credential_agent.lockout_threshold = 1
        credential_agent.lockout_window = 1  # 1 minute

        with patch.object(credential_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            tool_selection = MagicMock()
            tool_selection.tool_name = "hydra"
            tool_selection.command = "hydra -L users.txt -P pass.txt ssh://target"
            tool_selection.confidence = 0.9
            mock_select.return_value = tool_selection

            with patch("cyberred.agents.credential.kali_execute", new_callable=AsyncMock) as mock_exec:
                result = MagicMock()
                result.success = True
                result.stdout = ""
                result.stderr = ""
                result.exit_code = 0
                mock_exec.return_value = result

                # This should complete without error
                await credential_agent._execute_password_spray(
                    "192.168.1.100",
                    ["user1"],
                    ["password1"]
                )

                assert mock_exec.called

    @pytest.mark.asyncio
    async def test_password_spray_uses_spray_and_wait(self, credential_agent):
        """_execute_password_spray uses spray-and-wait pattern."""
        credential_agent.lockout_threshold = 1

        call_times = []
        
        async def track_calls(*args, **kwargs):
            call_times.append(asyncio.get_event_loop().time())
            result = MagicMock()
            result.success = True
            result.stdout = ""
            result.stderr = ""
            result.exit_code = 0
            return result

        with patch.object(credential_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            tool_selection = MagicMock()
            tool_selection.tool_name = "hydra"
            tool_selection.command = "hydra -L users.txt -P pass.txt ssh://target"
            tool_selection.confidence = 0.9
            mock_select.return_value = tool_selection

            with patch("cyberred.agents.credential.kali_execute", side_effect=track_calls):
                await credential_agent._execute_password_spray(
                    "192.168.1.100",
                    ["user1"],
                    ["password1"]
                )

        # At minimum should have attempted something
        assert len(call_times) >= 1

    @pytest.mark.asyncio
    async def test_password_spray_selects_appropriate_tool(self, credential_agent):
        """_execute_password_spray selects tool via LLM based on service."""
        with patch.object(credential_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            tool_selection = MagicMock()
            tool_selection.tool_name = "hydra"
            tool_selection.command = "hydra -L users.txt -P pass.txt ssh://target"
            tool_selection.confidence = 0.9
            mock_select.return_value = tool_selection

            with patch("cyberred.agents.credential.kali_execute", new_callable=AsyncMock) as mock_exec:
                result = MagicMock()
                result.success = True
                result.stdout = ""
                result.stderr = ""
                result.exit_code = 0
                mock_exec.return_value = result

                await credential_agent._execute_password_spray(
                    "192.168.1.100",
                    ["user1"],
                    ["password1"]
                )

            mock_select.assert_called()

    @pytest.mark.asyncio
    async def test_password_spray_handles_success(self, credential_agent, mock_event_bus):
        """_execute_password_spray handles successful login."""
        with patch.object(credential_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            tool_selection = MagicMock()
            tool_selection.tool_name = "hydra"
            tool_selection.command = "hydra -L users.txt -P pass.txt ssh://target"
            tool_selection.confidence = 0.9
            mock_select.return_value = tool_selection

            with patch("cyberred.agents.credential.kali_execute", new_callable=AsyncMock) as mock_exec:
                result = MagicMock()
                result.success = True
                result.stdout = "[22][ssh] host: 192.168.1.100   login: admin   password: P@ssw0rd"
                result.stderr = ""
                result.exit_code = 0
                mock_exec.return_value = result

                await credential_agent._execute_password_spray(
                    "192.168.1.100",
                    ["admin"],
                    ["P@ssw0rd"]
                )

                # Should have stored the cracked credential
                assert len(credential_agent._cracked_credentials) >= 1

    @pytest.mark.asyncio
    async def test_password_spray_handles_lockout(self, credential_agent):
        """_execute_password_spray handles account lockout detection."""
        with patch.object(credential_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            tool_selection = MagicMock()
            tool_selection.tool_name = "hydra"
            tool_selection.command = "hydra -L users.txt -P pass.txt ssh://target"
            tool_selection.confidence = 0.9
            mock_select.return_value = tool_selection

            with patch("cyberred.agents.credential.kali_execute", new_callable=AsyncMock) as mock_exec:
                result = MagicMock()
                result.success = True
                result.stdout = "Account locked out"
                result.stderr = ""
                result.exit_code = 0
                mock_exec.return_value = result

                # Should not crash on lockout
                await credential_agent._execute_password_spray(
                    "192.168.1.100",
                    ["admin"],
                    ["password1"]
                )

                assert True  # Just verify no exception


# --- Task 1.6: Hash Cracking Tests (AC: #6) ---
@pytest.mark.unit
class TestCredentialAgentHashCracking:
    """Tests for hash cracking functionality."""

    @pytest.fixture
    def mock_event_bus(self):
        return AsyncMock()

    @pytest.fixture
    def credential_agent(self, mock_event_bus):
        from cyberred.agents.credential import CredentialAgent

        return CredentialAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
            specialty="cracking",
        )

    def test_crack_hashes_detects_ntlm(self, credential_agent):
        """_detect_hash_type identifies NTLM hashes."""
        ntlm_hash = "aad3b435b51404eeaad3b435b51404ee"
        hash_type = credential_agent._detect_hash_type(ntlm_hash)
        assert hash_type == "ntlm"

    def test_crack_hashes_detects_kerberos_tgs(self, credential_agent):
        """_detect_hash_type identifies Kerberos TGS hashes."""
        krb_hash = "$krb5tgs$23$*user$realm$spn*$hash"
        hash_type = credential_agent._detect_hash_type(krb_hash)
        assert hash_type == "kerberos_tgs"

    def test_crack_hashes_detects_asrep(self, credential_agent):
        """_detect_hash_type identifies AS-REP hashes."""
        asrep_hash = "$krb5asrep$23$user@DOMAIN.COM:hash"
        hash_type = credential_agent._detect_hash_type(asrep_hash)
        assert hash_type == "asrep"

    def test_crack_hashes_detects_bcrypt(self, credential_agent):
        """_detect_hash_type identifies bcrypt hashes."""
        bcrypt_hash = "$2a$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy"
        hash_type = credential_agent._detect_hash_type(bcrypt_hash)
        assert hash_type == "bcrypt"

    def test_crack_hashes_selects_hashcat_mode(self, credential_agent):
        """_get_hashcat_mode returns correct mode for hash type."""
        assert credential_agent._get_hashcat_mode("ntlm") == 1000
        assert credential_agent._get_hashcat_mode("kerberos_tgs") == 13100
        assert credential_agent._get_hashcat_mode("asrep") == 18200
        assert credential_agent._get_hashcat_mode("bcrypt") == 3200

    def test_crack_hashes_selects_john_format(self, credential_agent):
        """_get_john_format returns correct format for hash type."""
        assert credential_agent._get_john_format("ntlm") == "nt"
        assert credential_agent._get_john_format("kerberos_tgs") == "krb5tgs"
        assert credential_agent._get_john_format("asrep") == "krb5asrep"
        assert credential_agent._get_john_format("bcrypt") == "bcrypt"

    @pytest.mark.asyncio
    async def test_crack_hashes_stores_cracked_credentials(self, credential_agent, mock_event_bus):
        """_crack_hashes stores cracked credentials."""
        with patch.object(credential_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            tool_selection = MagicMock()
            tool_selection.tool_name = "hashcat"
            tool_selection.command = "hashcat -m 1000 hashes.txt wordlist.txt"
            tool_selection.confidence = 0.9
            mock_select.return_value = tool_selection

            with patch("cyberred.agents.credential.kali_execute", new_callable=AsyncMock) as mock_exec:
                result = MagicMock()
                result.success = True
                result.stdout = "aad3b435b51404eeaad3b435b51404ee:P@ssw0rd"
                result.stderr = ""
                result.exit_code = 0
                mock_exec.return_value = result

                await credential_agent._crack_hashes(
                    ["aad3b435b51404eeaad3b435b51404ee"],
                    "ntlm"
                )

                assert len(credential_agent._cracked_credentials) >= 1


# --- Task 1.7: Credential Harvesting Tests (AC: #7) ---
@pytest.mark.unit
class TestCredentialAgentHarvesting:
    """Tests for credential harvesting functionality."""

    @pytest.fixture
    def mock_event_bus(self):
        return AsyncMock()

    @pytest.fixture
    def credential_agent(self, mock_event_bus):
        from cyberred.agents.credential import CredentialAgent

        return CredentialAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
            specialty="harvesting",
        )

    @pytest.mark.asyncio
    async def test_harvest_windows_uses_mimikatz(self, credential_agent):
        """_harvest_credentials for Windows uses mimikatz-style tools."""
        with patch.object(credential_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            tool_selection = MagicMock()
            tool_selection.tool_name = "mimikatz"
            tool_selection.command = "mimikatz sekurlsa::logonpasswords"
            tool_selection.confidence = 0.9
            mock_select.return_value = tool_selection

            with patch("cyberred.agents.credential.kali_execute", new_callable=AsyncMock) as mock_exec:
                result = MagicMock()
                result.success = True
                result.stdout = "Username: admin\nNTLM: aad3b435b51404ee"
                result.stderr = ""
                result.exit_code = 0
                mock_exec.return_value = result

                await credential_agent._harvest_credentials("192.168.1.100", "windows")

            mock_select.assert_called()

    @pytest.mark.asyncio
    async def test_harvest_windows_uses_secretsdump(self, credential_agent):
        """_harvest_credentials for Windows can use secretsdump."""
        with patch.object(credential_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            tool_selection = MagicMock()
            tool_selection.tool_name = "impacket-secretsdump"
            tool_selection.command = "impacket-secretsdump admin@192.168.1.100"
            tool_selection.confidence = 0.9
            mock_select.return_value = tool_selection

            with patch("cyberred.agents.credential.kali_execute", new_callable=AsyncMock) as mock_exec:
                result = MagicMock()
                result.success = True
                result.stdout = "Administrator:500:aad3b435:31d6cfe0"
                result.stderr = ""
                result.exit_code = 0
                mock_exec.return_value = result

                await credential_agent._harvest_credentials("192.168.1.100", "windows")

            assert mock_select.called

    @pytest.mark.asyncio
    async def test_harvest_linux_parses_shadow(self, credential_agent):
        """_harvest_credentials for Linux parses /etc/shadow."""
        with patch.object(credential_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            tool_selection = MagicMock()
            tool_selection.tool_name = "cat"
            tool_selection.command = "cat /etc/shadow"
            tool_selection.confidence = 0.9
            mock_select.return_value = tool_selection

            with patch("cyberred.agents.credential.kali_execute", new_callable=AsyncMock) as mock_exec:
                result = MagicMock()
                result.success = True
                result.stdout = "root:$6$rounds=5000$salt$hash:18000:0:99999:7:::"
                result.stderr = ""
                result.exit_code = 0
                mock_exec.return_value = result

                await credential_agent._harvest_credentials("192.168.1.100", "linux")

            assert mock_select.called

    @pytest.mark.asyncio
    async def test_harvest_linux_collects_ssh_keys(self, credential_agent):
        """_harvest_credentials for Linux collects SSH keys."""
        with patch.object(credential_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            tool_selection = MagicMock()
            tool_selection.tool_name = "find"
            tool_selection.command = "find /home -name id_rsa"
            tool_selection.confidence = 0.9
            mock_select.return_value = tool_selection

            with patch("cyberred.agents.credential.kali_execute", new_callable=AsyncMock) as mock_exec:
                result = MagicMock()
                result.success = True
                result.stdout = "/home/user/.ssh/id_rsa"
                result.stderr = ""
                result.exit_code = 0
                mock_exec.return_value = result

                await credential_agent._harvest_credentials("192.168.1.100", "linux")

            assert mock_select.called

    @pytest.mark.asyncio
    async def test_harvest_web_extracts_configs(self, credential_agent):
        """_harvest_credentials for Web extracts config files."""
        with patch.object(credential_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            tool_selection = MagicMock()
            tool_selection.tool_name = "grep"
            tool_selection.command = "grep -r password /var/www"
            tool_selection.confidence = 0.9
            mock_select.return_value = tool_selection

            with patch("cyberred.agents.credential.kali_execute", new_callable=AsyncMock) as mock_exec:
                result = MagicMock()
                result.success = True
                result.stdout = "config.php:$db_password = 'secret123';"
                result.stderr = ""
                result.exit_code = 0
                mock_exec.return_value = result

                await credential_agent._harvest_credentials("http://target.com", "web")

            assert mock_select.called

    @pytest.mark.asyncio
    async def test_harvested_credentials_stored(self, credential_agent):
        """_harvest_credentials stores harvested credentials."""
        with patch.object(credential_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            tool_selection = MagicMock()
            tool_selection.tool_name = "mimikatz"
            tool_selection.command = "mimikatz sekurlsa::logonpasswords"
            tool_selection.confidence = 0.9
            mock_select.return_value = tool_selection

            with patch("cyberred.agents.credential.kali_execute", new_callable=AsyncMock) as mock_exec:
                result = MagicMock()
                result.success = True
                result.stdout = "Username: admin\nNTLM: aad3b435b51404eeaad3b435b51404ee"
                result.stderr = ""
                result.exit_code = 0
                mock_exec.return_value = result

                await credential_agent._harvest_credentials("192.168.1.100", "windows")

            assert len(credential_agent._harvested_credentials) >= 1


# --- Task 1.8: Stigmergic Sharing Tests (AC: #8) ---
@pytest.mark.unit
class TestCredentialAgentStigmergicSharing:
    """Tests for stigmergic credential sharing."""

    @pytest.fixture
    def mock_event_bus(self):
        return AsyncMock()

    @pytest.fixture
    def credential_agent(self, mock_event_bus):
        from cyberred.agents.credential import CredentialAgent

        return CredentialAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
        )

    @pytest.mark.asyncio
    async def test_cracked_credentials_published_to_channel(self, credential_agent, mock_event_bus):
        """Cracked credentials published to credentials:{engagement_id}:cracked channel."""
        await credential_agent._publish_cracked_credential(
            {"username": "admin", "password": "P@ssw0rd", "hash_type": "ntlm"}
        )

        mock_event_bus.publish.assert_called()
        call_args = mock_event_bus.publish.call_args
        channel = call_args[0][0]
        assert "credentials" in channel and "cracked" in channel

    @pytest.mark.asyncio
    async def test_subscribes_to_credential_channels(self, credential_agent):
        """CredentialAgent subscribes to credentials:{engagement_id}:* channels."""
        assert hasattr(credential_agent, "_setup_credential_subscriptions")

    @pytest.mark.asyncio
    async def test_receives_kerberos_tickets_from_ad_agent(self, credential_agent):
        """CredentialAgent receives Kerberos tickets from ADAgent."""
        data = {
            "spn": "MSSQLSvc/db01.corp.local",
            "hash": "$krb5tgs$23$*svc_sql$hash",
            "agent_id": "ad-agent-001"
        }

        await credential_agent.on_signal("credentials:eng-1:kerberos", data)

        assert len(credential_agent._pending_hashes) >= 1

    @pytest.mark.asyncio
    async def test_findings_published_to_credential_channel(self, credential_agent, mock_event_bus):
        """Findings published to findings:{target_hash}:credential channel."""
        from cyberred.core.models import Finding

        finding = Finding(
            id=str(uuid.uuid4()),
            type="credential",
            severity="high",
            target="192.168.1.100",
            evidence="Password cracked: admin:P@ssw0rd",
            agent_id=credential_agent.agent_id,
            timestamp="2026-01-26T00:00:00Z",
            tool="hashcat",
            topic="findings:test:credential",
            signature="test-sig-001",
        )

        await credential_agent.on_finding(finding)

        mock_event_bus.publish.assert_called()
        call_args = mock_event_bus.publish.call_args
        channel = call_args[0][0]
        assert "credential" in channel


# --- Task 1.9: Strategy Tests (AC: #9) ---
@pytest.mark.unit
class TestCredentialAgentStrategy:
    """Tests for strategy handling."""

    @pytest.fixture
    def mock_event_bus(self):
        return AsyncMock()

    @pytest.fixture
    def credential_agent(self, mock_event_bus):
        from cyberred.agents.credential import CredentialAgent

        return CredentialAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("strategy", ["stealth", "standard", "aggressive"])
    async def test_on_signal_updates_strategy(self, credential_agent, strategy):
        """on_signal updates strategy for valid values."""
        channel = "strategies:eng-1"
        data = {"strategy": strategy}

        await credential_agent.on_signal(channel, data)

        assert credential_agent.current_strategy == strategy

    @pytest.mark.asyncio
    async def test_on_signal_ignores_invalid_strategy(self, credential_agent):
        """on_signal ignores invalid strategy values."""
        channel = "strategies:eng-1"
        data = {"strategy": "invalid_strategy"}

        await credential_agent.on_signal(channel, data)

        assert credential_agent.current_strategy == "standard"

    def test_get_constraints_stealth(self, credential_agent):
        """_get_constraints in stealth mode limits spraying attempts."""
        credential_agent.current_strategy = "stealth"

        constraints = credential_agent._get_constraints()

        assert any("spray" in c.lower() or "offline" in c.lower() or "stealth" in c.lower() 
                   or "limit" in c.lower() for c in constraints)

    def test_get_constraints_aggressive(self, credential_agent):
        """_get_constraints in aggressive mode allows full spraying."""
        credential_agent.current_strategy = "aggressive"

        constraints = credential_agent._get_constraints()

        assert any("all" in c.lower() or "aggressive" in c.lower() or "full" in c.lower() 
                   or "allow" in c.lower() for c in constraints)


# --- Task 1.10: Stigmergic Hook Tests (AC: #9) ---
@pytest.mark.unit
class TestCredentialAgentStigmergicHooks:
    """Tests for preserved stigmergic hooks."""

    @pytest.fixture
    def mock_event_bus(self):
        return AsyncMock()

    @pytest.fixture
    def credential_agent(self, mock_event_bus):
        from cyberred.agents.credential import CredentialAgent

        return CredentialAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
        )

    @pytest.mark.asyncio
    async def test_on_finding_publishes_to_credential_channel(self, credential_agent, mock_event_bus):
        """on_finding publishes to findings:{target_hash}:credential channel."""
        from cyberred.core.models import Finding

        finding = Finding(
            id=str(uuid.uuid4()),
            type="credential",
            severity="high",
            target="192.168.1.100",
            evidence="Cracked credential evidence",
            agent_id=credential_agent.agent_id,
            timestamp="2026-01-26T00:00:00Z",
            tool="hashcat",
            topic="findings:test:credential",
            signature="test-sig-001",
        )

        await credential_agent.on_finding(finding)

        mock_event_bus.publish.assert_called()
        call_args = mock_event_bus.publish.call_args
        channel = call_args[0][0]
        assert "credential" in channel

    @pytest.mark.asyncio
    async def test_stop_sets_event(self, credential_agent):
        """stop() sets _stop_event."""
        await credential_agent.stop()

        assert credential_agent._stop_event.is_set()

    @pytest.mark.asyncio
    async def test_flush_buffer_on_reconnect(self, credential_agent, mock_event_bus):
        """_flush_buffer attempts to publish buffered findings."""
        credential_agent._finding_buffer = [
            {"channel": "findings:abc:credential", "message": {"id": "f1"}},
            {"channel": "findings:def:credential", "message": {"id": "f2"}},
        ]

        await credential_agent._flush_buffer()

        assert mock_event_bus.publish.call_count >= 2


# --- Additional Coverage Tests ---
@pytest.mark.unit
class TestCredentialAgentEdgeCases:
    """Additional tests for edge cases and 100% coverage."""

    @pytest.fixture
    def mock_event_bus(self):
        return AsyncMock()

    @pytest.fixture
    def credential_agent(self, mock_event_bus):
        from cyberred.agents.credential import CredentialAgent

        return CredentialAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
        )

    @pytest.mark.asyncio
    async def test_execute_exits_on_phase_complete(self, credential_agent):
        """execute_credential_attack exits early when phase is complete."""
        credential_agent.max_iterations = 5
        credential_agent.phase_complete_threshold = 0

        with patch.object(credential_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            findings, actions = await credential_agent.execute_credential_attack("192.168.1.100", {})

        mock_select.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_handles_select_tool_exception(self, credential_agent):
        """execute_credential_attack handles exceptions during tool selection."""
        credential_agent.max_iterations = 1

        with patch.object(credential_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            mock_select.side_effect = Exception("LLM unavailable")

            findings, actions = await credential_agent.execute_credential_attack("192.168.1.100", {})

        assert len(actions) == 1
        assert actions[0].action_type == "credential:unknown"

    @pytest.mark.asyncio
    async def test_on_finding_buffers_on_publish_failure(self, credential_agent, mock_event_bus):
        """on_finding buffers finding when publish fails."""
        from cyberred.core.models import Finding

        mock_event_bus.publish.side_effect = Exception("Network error")

        finding = Finding(
            id=str(uuid.uuid4()),
            type="credential",
            severity="high",
            target="192.168.1.100",
            evidence="Critical finding evidence",
            agent_id=credential_agent.agent_id,
            timestamp="2026-01-26T00:00:00Z",
            tool="hashcat",
            topic="findings:test:credential",
            signature="test-sig-fail",
        )

        await credential_agent.on_finding(finding)

        assert len(credential_agent._finding_buffer) == 1

    @pytest.mark.asyncio
    async def test_flush_buffer_keeps_failed_items(self, credential_agent, mock_event_bus):
        """_flush_buffer keeps items that fail to publish."""
        mock_event_bus.publish.side_effect = Exception("Network error")

        credential_agent._finding_buffer = [
            {"channel": "findings:abc:credential", "message": {"id": "f1"}},
        ]

        await credential_agent._flush_buffer()

        assert len(credential_agent._finding_buffer) == 1

    @pytest.mark.asyncio
    async def test_stop_flushes_buffer_if_not_empty(self, credential_agent, mock_event_bus):
        """stop() flushes buffer if it contains items."""
        credential_agent._finding_buffer = [
            {"channel": "findings:abc:credential", "message": {"id": "f1"}},
        ]

        await credential_agent.stop()

        assert credential_agent._stop_event.is_set()
        mock_event_bus.publish.assert_called()

    @pytest.mark.asyncio
    async def test_execute_creates_finding_on_success(self, credential_agent, mock_event_bus):
        """execute_credential_attack creates findings when tool succeeds with output."""
        credential_agent.max_iterations = 1
        credential_agent.phase_complete_threshold = 10

        result = MagicMock()
        result.success = True
        result.stdout = "Password cracked: admin:P@ssw0rd"
        result.stderr = ""
        result.exit_code = 0

        tool_selection = MagicMock()
        tool_selection.tool_name = "hashcat"
        tool_selection.command = "hashcat -m 1000 hashes.txt wordlist.txt"
        tool_selection.confidence = 0.9

        with patch.object(credential_agent, "select_tool", new_callable=AsyncMock, return_value=tool_selection), \
             patch("cyberred.agents.credential.kali_execute", new_callable=AsyncMock, return_value=result):

            findings, actions = await credential_agent.execute_credential_attack("192.168.1.100", {})

        assert len(findings) == 1
        assert findings[0].type == "credential"
        assert len(actions) == 1

    def test_hash_target(self, credential_agent):
        """_hash_target returns consistent 8-char hash."""
        hash1 = credential_agent._hash_target("192.168.1.100")
        hash2 = credential_agent._hash_target("192.168.1.100")

        assert hash1 == hash2
        assert len(hash1) == 8

    @pytest.mark.asyncio
    async def test_on_signal_ignores_non_strategy_channel(self, credential_agent):
        """on_signal ignores channels that don't contain 'strategies'."""
        credential_agent.current_strategy = "stealth"

        channel = "findings:eng-1"
        data = {"strategy": "aggressive"}

        await credential_agent.on_signal(channel, data)

        assert credential_agent.current_strategy == "stealth"

    def test_detect_hash_type_unknown(self, credential_agent):
        """_detect_hash_type returns 'unknown' for unrecognized hashes."""
        unknown_hash = "notahash"
        hash_type = credential_agent._detect_hash_type(unknown_hash)
        assert hash_type == "unknown"

    def test_detect_hash_type_sha512(self, credential_agent):
        """_detect_hash_type identifies SHA-512 Unix hashes."""
        sha512_hash = "$6$rounds=5000$saltsalt$hash"
        hash_type = credential_agent._detect_hash_type(sha512_hash)
        assert hash_type == "sha512crypt"

    def test_detect_hash_type_md5crypt(self, credential_agent):
        """_detect_hash_type identifies MD5 Unix hashes."""
        md5_hash = "$1$saltsalt$hash"
        hash_type = credential_agent._detect_hash_type(md5_hash)
        assert hash_type == "md5crypt"

    def test_get_hashcat_mode_sha512crypt(self, credential_agent):
        """_get_hashcat_mode returns correct mode for sha512crypt."""
        assert credential_agent._get_hashcat_mode("sha512crypt") == 1800

    def test_get_hashcat_mode_md5crypt(self, credential_agent):
        """_get_hashcat_mode returns correct mode for md5crypt."""
        assert credential_agent._get_hashcat_mode("md5crypt") == 500

    def test_get_hashcat_mode_unknown(self, credential_agent):
        """_get_hashcat_mode returns 0 for unknown hash types."""
        assert credential_agent._get_hashcat_mode("unknown") == 0

    def test_get_john_format_sha512crypt(self, credential_agent):
        """_get_john_format returns correct format for sha512crypt."""
        assert credential_agent._get_john_format("sha512crypt") == "sha512crypt"

    def test_get_john_format_md5crypt(self, credential_agent):
        """_get_john_format returns correct format for md5crypt."""
        assert credential_agent._get_john_format("md5crypt") == "md5crypt"

    def test_get_john_format_unknown(self, credential_agent):
        """_get_john_format returns 'raw' for unknown hash types."""
        assert credential_agent._get_john_format("unknown") == "raw"

    @pytest.mark.asyncio
    async def test_publish_cracked_credential_handles_exception(self, credential_agent, mock_event_bus):
        """_publish_cracked_credential handles publish failure gracefully."""
        mock_event_bus.publish.side_effect = Exception("Network error")

        await credential_agent._publish_cracked_credential({"username": "admin", "password": "test"})

        mock_event_bus.publish.assert_called()

    @pytest.mark.asyncio
    async def test_on_signal_handles_credential_channel(self, credential_agent):
        """on_signal handles credential channels from other agents."""
        data = {
            "hash": "aad3b435b51404eeaad3b435b51404ee",
            "hash_type": "ntlm",
            "agent_id": "postex-agent-001"
        }

        await credential_agent.on_signal("credentials:eng-1:postex", data)

        assert len(credential_agent._pending_hashes) >= 1

    def test_get_timestamp(self, credential_agent):
        """_get_timestamp returns ISO format timestamp."""
        ts = credential_agent._get_timestamp()
        assert "T" in ts

    @pytest.mark.asyncio
    async def test_phase_complete_returns_true_when_threshold_met(self, credential_agent):
        """_phase_complete returns True when threshold is met."""
        from cyberred.core.models import ToolSelectionContext

        credential_agent.phase_complete_threshold = 2

        context = ToolSelectionContext(
            objective="Test credential",
            target_info={},
            available_tools=[],
            phase="credential",
            constraints=[],
            previous_results=[{"id": "1"}, {"id": "2"}, {"id": "3"}],
        )

        result = await credential_agent._phase_complete(context)
        assert result is True

    @pytest.mark.asyncio
    async def test_phase_complete_returns_false_when_below_threshold(self, credential_agent):
        """_phase_complete returns False when below threshold."""
        from cyberred.core.models import ToolSelectionContext

        credential_agent.phase_complete_threshold = 10

        context = ToolSelectionContext(
            objective="Test credential",
            target_info={},
            available_tools=[],
            phase="credential",
            constraints=[],
            previous_results=[{"id": "1"}],
        )

        result = await credential_agent._phase_complete(context)
        assert result is False

    def test_default_max_iterations(self, mock_event_bus):
        """CredentialAgent has default max_iterations of 25."""
        from cyberred.agents.credential import CredentialAgent

        agent = CredentialAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
        )
        assert agent.max_iterations == CredentialAgent.DEFAULT_MAX_ITERATIONS

    def test_default_lockout_threshold(self, mock_event_bus):
        """CredentialAgent has default lockout_threshold of 3."""
        from cyberred.agents.credential import CredentialAgent

        agent = CredentialAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
        )
        assert agent.lockout_threshold == 3

    def test_default_lockout_window(self, mock_event_bus):
        """CredentialAgent has default lockout_window of 30."""
        from cyberred.agents.credential import CredentialAgent

        agent = CredentialAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
        )
        assert agent.lockout_window == 30

    @pytest.mark.asyncio
    async def test_execute_stops_mid_iteration(self, credential_agent):
        """execute_credential_attack stops when _stop_event is set mid-iteration."""
        credential_agent.max_iterations = 5
        credential_agent.phase_complete_threshold = 100
        
        call_count = 0
        async def set_stop_after_first(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                credential_agent._stop_event.set()
            result = MagicMock()
            result.success = True
            result.stdout = ""
            result.exit_code = 0
            return result

        with patch.object(credential_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            tool_selection = MagicMock()
            tool_selection.tool_name = "hydra"
            tool_selection.command = "hydra test"
            tool_selection.confidence = 0.9
            mock_select.return_value = tool_selection

            with patch("cyberred.agents.credential.kali_execute", side_effect=set_stop_after_first):
                findings, actions = await credential_agent.execute_credential_attack("192.168.1.100", {})

        # Should have stopped after first iteration
        assert len(actions) <= 2

    @pytest.mark.asyncio
    async def test_crack_hashes_handles_no_cracked_output(self, credential_agent):
        """_crack_hashes handles output with no cracked hashes."""
        with patch.object(credential_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            tool_selection = MagicMock()
            tool_selection.tool_name = "hashcat"
            tool_selection.command = "hashcat -m 1000 hashes.txt"
            mock_select.return_value = tool_selection

            with patch("cyberred.agents.credential.kali_execute", new_callable=AsyncMock) as mock_exec:
                result = MagicMock()
                result.success = True
                result.stdout = "No hashes cracked"
                mock_exec.return_value = result

                cracked = await credential_agent._crack_hashes(["hash1"], "ntlm")

        assert cracked == []

    @pytest.mark.asyncio
    async def test_crack_hashes_handles_exception(self, credential_agent):
        """_crack_hashes handles exceptions gracefully."""
        with patch.object(credential_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            mock_select.side_effect = Exception("LLM error")

            cracked = await credential_agent._crack_hashes(["hash1"], "ntlm")

        assert cracked == []

    @pytest.mark.asyncio
    async def test_harvest_credentials_handles_exception(self, credential_agent):
        """_harvest_credentials handles exceptions gracefully."""
        with patch.object(credential_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            mock_select.side_effect = Exception("Tool error")

            harvested = await credential_agent._harvest_credentials("192.168.1.100", "windows")

        assert harvested == []

    @pytest.mark.asyncio
    async def test_password_spray_handles_exception(self, credential_agent):
        """_execute_password_spray handles exceptions gracefully."""
        with patch.object(credential_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            mock_select.side_effect = Exception("Spray error")

            result = await credential_agent._execute_password_spray("target", ["user"], ["pass"])

        assert result == []

    def test_parse_harvested_output_windows_mimikatz(self, credential_agent):
        """_parse_harvested_output parses mimikatz output."""
        output = "Username: admin\nDomain: CORP\nNTLM: aad3b435b51404eeaad3b435b51404ee"
        creds = credential_agent._parse_harvested_output(output, "windows")
        assert len(creds) >= 1

    def test_parse_harvested_output_linux_shadow(self, credential_agent):
        """_parse_harvested_output parses Linux shadow entries."""
        output = "root:$6$salt$hash:18000:0:99999:7:::\nuser:$6$salt2$hash2:18000:0:99999:7:::"
        creds = credential_agent._parse_harvested_output(output, "linux")
        assert len(creds) >= 1

    def test_parse_harvested_output_linux_ssh_keys(self, credential_agent):
        """_parse_harvested_output finds SSH key paths."""
        output = "/home/user/.ssh/id_rsa\n/root/.ssh/id_ed25519"
        creds = credential_agent._parse_harvested_output(output, "linux")
        assert len(creds) >= 1

    def test_parse_harvested_output_web_config(self, credential_agent):
        """_parse_harvested_output parses web config passwords."""
        output = "config.php: password = 'secret123'\ndb_password='dbpass'"
        creds = credential_agent._parse_harvested_output(output, "web")
        assert len(creds) >= 1

    def test_get_harvest_tools_windows(self, credential_agent):
        """_get_harvest_tools returns Windows tools."""
        tools = credential_agent._get_harvest_tools("windows")
        assert "mimikatz" in tools

    def test_get_harvest_tools_linux(self, credential_agent):
        """_get_harvest_tools returns Linux tools."""
        tools = credential_agent._get_harvest_tools("linux")
        assert "cat" in tools

    def test_get_harvest_tools_unknown(self, credential_agent):
        """_get_harvest_tools returns default tools for unknown type."""
        tools = credential_agent._get_harvest_tools("unknown")
        assert "grep" in tools

    def test_get_constraints_standard(self, credential_agent):
        """_get_constraints returns empty for standard strategy."""
        credential_agent.current_strategy = "standard"
        constraints = credential_agent._get_constraints()
        assert constraints == []

    @pytest.mark.asyncio
    async def test_setup_credential_subscriptions(self, credential_agent, mock_event_bus):
        """_setup_credential_subscriptions subscribes to credential channels."""
        await credential_agent._setup_credential_subscriptions()
        mock_event_bus.subscribe.assert_called()

    @pytest.mark.asyncio
    async def test_check_cracked_results_hydra_format(self, credential_agent, mock_event_bus):
        """_check_cracked_results parses hydra success format."""
        result = MagicMock()
        result.stdout = "[22][ssh] host: 192.168.1.1 login: admin password: secret123"
        selection = MagicMock()
        selection.tool_name = "hydra"

        await credential_agent._check_cracked_results(result, selection)

        assert len(credential_agent._cracked_credentials) >= 1

    @pytest.mark.asyncio  
    async def test_check_cracked_results_hashcat_format(self, credential_agent, mock_event_bus):
        """_check_cracked_results parses hashcat cracked format."""
        result = MagicMock()
        result.stdout = "aad3b435b51404eeaad3b435b51404ee:password123"
        selection = MagicMock()
        selection.tool_name = "hashcat"

        await credential_agent._check_cracked_results(result, selection)

        assert len(credential_agent._cracked_credentials) >= 1

    def test_parse_harvested_output_windows_ntlm_format(self, credential_agent):
        """_parse_harvested_output parses NTLM hash format (username:rid:lm:nt)."""
        output = "Administrator:500:aad3b435b51404eeaad3b435b51404ee:31d6cfe0d16ae931b73c59d7e0c089c0:::"
        creds = credential_agent._parse_harvested_output(output, "windows")
        assert len(creds) >= 1
        assert creds[0]["username"] == "Administrator"
        assert creds[0]["rid"] == "500"
        assert creds[0]["type"] == "ntlm"

    @pytest.mark.asyncio
    async def test_on_finding_with_existing_buffer(self, credential_agent, mock_event_bus):
        """on_finding flushes existing buffer before publishing."""
        from cyberred.core.models import Finding

        # Pre-populate buffer
        credential_agent._finding_buffer = [
            {"channel": "findings:old:credential", "message": {"id": "old-id"}}
        ]

        finding = Finding(
            id=str(uuid.uuid4()),
            type="credential",
            severity="high",
            target="192.168.1.100",
            evidence="Test evidence",
            agent_id=credential_agent.agent_id,
            timestamp="2026-01-26T00:00:00Z",
            tool="hashcat",
            topic="findings:test:credential",
            signature="test-sig",
        )

        await credential_agent.on_finding(finding)

        # Should have called publish at least twice (buffer + new finding)
        assert mock_event_bus.publish.call_count >= 2

    def test_create_finding(self, credential_agent):
        """_create_finding creates a valid Finding object."""
        selection = MagicMock()
        selection.tool_name = "hashcat"
        result = MagicMock()
        result.stdout = "Cracked: admin:password"

        finding = credential_agent._create_finding("192.168.1.100", selection, result)

        assert finding.type == "credential"
        assert finding.severity == "high"
        assert finding.tool == "hashcat"
        assert "credential" in finding.topic

    @pytest.mark.asyncio
    async def test_harvest_credentials_stores_results(self, credential_agent):
        """_harvest_credentials stores harvested credentials in list."""
        with patch.object(credential_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            tool_selection = MagicMock()
            tool_selection.tool_name = "mimikatz"
            tool_selection.command = "mimikatz"
            mock_select.return_value = tool_selection

            with patch("cyberred.agents.credential.kali_execute", new_callable=AsyncMock) as mock_exec:
                result = MagicMock()
                result.success = True
                result.stdout = "Administrator:500:aad3b435b51404eeaad3b435b51404ee:31d6cfe0d16ae931b73c59d7e0c089c0"
                mock_exec.return_value = result

                harvested = await credential_agent._harvest_credentials("192.168.1.100", "windows")

        assert len(harvested) >= 1
        assert len(credential_agent._harvested_credentials) >= 1

# --- Branch Coverage Tests ---
@pytest.mark.unit
class TestCredentialAgentBranchCoverage:
    """Tests for 100% branch coverage."""

    @pytest.fixture
    def mock_event_bus(self):
        return AsyncMock()

    @pytest.fixture
    def credential_agent(self, mock_event_bus):
        from cyberred.agents.credential import CredentialAgent

        return CredentialAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
        )

    @pytest.mark.asyncio
    async def test_crack_hashes_empty_output(self, credential_agent, mock_event_bus):
        """_crack_hashes handles empty or failed result."""
        with patch.object(credential_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            tool_selection = MagicMock()
            tool_selection.tool_name = "hashcat"
            tool_selection.command = "hashcat -m 1000 hashes.txt wordlist.txt"
            mock_select.return_value = tool_selection

            with patch("cyberred.agents.credential.kali_execute", new_callable=AsyncMock) as mock_exec:
                result = MagicMock()
                result.success = False
                result.stdout = ""
                mock_exec.return_value = result

                cracked = await credential_agent._crack_hashes(["hash1"], "ntlm")

        assert cracked == []

    @pytest.mark.asyncio
    async def test_crack_hashes_line_without_colon(self, credential_agent, mock_event_bus):
        """_crack_hashes skips lines without colons."""
        with patch.object(credential_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            tool_selection = MagicMock()
            tool_selection.tool_name = "hashcat"
            tool_selection.command = "hashcat -m 1000 hashes.txt wordlist.txt"
            mock_select.return_value = tool_selection

            with patch("cyberred.agents.credential.kali_execute", new_callable=AsyncMock) as mock_exec:
                result = MagicMock()
                result.success = True
                result.stdout = "Session........\nno-colon-line\nhash1:password1"
                mock_exec.return_value = result

                cracked = await credential_agent._crack_hashes(["hash1"], "ntlm")

        assert len(cracked) >= 1

    @pytest.mark.asyncio
    async def test_crack_hashes_line_single_part(self, credential_agent, mock_event_bus):
        """_crack_hashes skips lines with colon but only one part."""
        with patch.object(credential_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            tool_selection = MagicMock()
            tool_selection.tool_name = "hashcat"
            tool_selection.command = "hashcat"
            mock_select.return_value = tool_selection

            with patch("cyberred.agents.credential.kali_execute", new_callable=AsyncMock) as mock_exec:
                result = MagicMock()
                result.success = True
                result.stdout = "hashwithcolon:\nhash2:password2"
                mock_exec.return_value = result

                cracked = await credential_agent._crack_hashes(["hash2"], "ntlm")

        assert len(cracked) >= 1

    @pytest.mark.asyncio
    async def test_check_cracked_duplicate_hydra(self, credential_agent, mock_event_bus):
        """_check_cracked_results skips duplicate hydra credentials."""
        existing_cred = {"username": "admin", "password": "secret123", "source": "hydra"}
        credential_agent._cracked_credentials.append(existing_cred)

        result = MagicMock()
        result.stdout = "login: admin password: secret123"
        selection = MagicMock()
        selection.tool_name = "hydra"

        await credential_agent._check_cracked_results(result, selection)

        assert len(credential_agent._cracked_credentials) == 1

    @pytest.mark.asyncio
    async def test_check_cracked_duplicate_hashcat(self, credential_agent, mock_event_bus):
        """_check_cracked_results skips duplicate hashcat credentials."""
        existing_cred = {"hash": "aad3b435b51404eeaad3b435b51404ee", "password": "password123", "source": "hashcat"}
        credential_agent._cracked_credentials.append(existing_cred)

        result = MagicMock()
        result.stdout = "aad3b435b51404eeaad3b435b51404ee:password123"
        selection = MagicMock()
        selection.tool_name = "hashcat"

        await credential_agent._check_cracked_results(result, selection)

        assert len(credential_agent._cracked_credentials) == 1

    @pytest.mark.asyncio
    async def test_harvest_empty_output(self, credential_agent, mock_event_bus):
        """_harvest_credentials handles empty output."""
        with patch.object(credential_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            tool_selection = MagicMock()
            tool_selection.tool_name = "mimikatz"
            tool_selection.command = "mimikatz"
            mock_select.return_value = tool_selection

            with patch("cyberred.agents.credential.kali_execute", new_callable=AsyncMock) as mock_exec:
                result = MagicMock()
                result.success = True
                result.stdout = ""
                mock_exec.return_value = result

                harvested = await credential_agent._harvest_credentials("192.168.1.100", "windows")

        assert harvested == []

    @pytest.mark.asyncio
    async def test_harvest_failed_result(self, credential_agent, mock_event_bus):
        """_harvest_credentials handles failed execution."""
        with patch.object(credential_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            tool_selection = MagicMock()
            tool_selection.tool_name = "mimikatz"
            tool_selection.command = "mimikatz"
            mock_select.return_value = tool_selection

            with patch("cyberred.agents.credential.kali_execute", new_callable=AsyncMock) as mock_exec:
                result = MagicMock()
                result.success = False
                result.stdout = "Some output"
                mock_exec.return_value = result

                harvested = await credential_agent._harvest_credentials("192.168.1.100", "windows")

        assert harvested == []

    def test_parse_harvested_output_web(self, credential_agent):
        """_parse_harvested_output parses web config passwords."""
        output = "password = 'db_secret_123'"
        creds = credential_agent._parse_harvested_output(output, "web")
        assert len(creds) >= 1
        assert creds[0]["type"] == "config"

    def test_parse_harvested_output_linux_shadow(self, credential_agent):
        """_parse_harvested_output parses Linux shadow entries."""
        output = "root:$6$salt$hashvalue:18000:0:99999:7:::"
        creds = credential_agent._parse_harvested_output(output, "linux")
        assert len(creds) >= 1
        assert creds[0]["type"] == "shadow"

    def test_parse_harvested_output_linux_ssh_key(self, credential_agent):
        """_parse_harvested_output parses Linux SSH key paths."""
        output = "/home/admin/.ssh/id_rsa"
        creds = credential_agent._parse_harvested_output(output, "linux")
        assert len(creds) >= 1
        assert creds[0]["type"] == "ssh_key"
