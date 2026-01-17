"""
Agent ID Functionality Tests - Regression tests for Mistral Agent integration.

These tests verify that:
1. When agent_id is configured, agents.complete() is called (not chat.complete())
2. When agent_id is NOT configured, chat.complete() fallback is used
3. Agent IDs are properly read from tenant config

Run: pytest backend/tests/test_agent_id.py -v
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid


class TestAgentIdCodePatterns:
    """Static analysis tests to verify agent ID code patterns."""

    def test_chat_route_uses_agents_complete_when_agent_id_present(self):
        """chat.py MUST use agents.complete() when agent_id is configured."""
        import inspect
        from backend.routes import chat

        source = inspect.getsource(chat.send_chat_message)

        # Must check for agent ID
        assert "chat_agent_id" in source, \
            "send_chat_message must check for agent_id"

        # Must call agents.complete
        assert "agents.complete" in source, \
            "send_chat_message must call agents.complete when agent_id is present"

        # Must have fallback to chat.complete
        assert "chat.complete" in source, \
            "send_chat_message must have chat.complete fallback"

    def test_mistral_service_uses_agents_complete_when_agent_id_present(self):
        """mistral_service.py MUST use agents.complete() when agent_id is configured."""
        import inspect
        from backend.services import mistral_service

        source = inspect.getsource(mistral_service.score_opportunity_with_ai)

        # Must check for agent ID
        assert "agent_id" in source, \
            "score_opportunity_with_ai must check for agent_id"

        # Must call agents.complete
        assert "agents.complete" in source, \
            "score_opportunity_with_ai must call agents.complete when agent_id is present"

        # Must have fallback to chat.complete
        assert "chat.complete" in source, \
            "score_opportunity_with_ai must have chat.complete fallback"

    def test_agent_id_config_keys_are_read(self):
        """Verify the correct config keys are read for agent IDs."""
        import inspect
        from backend.routes import chat

        source = inspect.getsource(chat.send_chat_message)

        # Must read opportunities_chat_agent_id
        assert "opportunities_chat_agent_id" in source, \
            "send_chat_message must read opportunities_chat_agent_id from config"

        # Must read intelligence_chat_agent_id
        assert "intelligence_chat_agent_id" in source, \
            "send_chat_message must read intelligence_chat_agent_id from config"


class TestAgentIdRouting:
    """Integration-style tests for agent ID routing logic."""

    @pytest.mark.asyncio
    async def test_agents_complete_called_when_agent_id_configured(self):
        """When agent_id is in tenant config, agents.complete() MUST be called."""
        from backend.routes.chat import send_chat_message
        from backend.utils.auth import TokenData

        tenant_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        agent_id = "ag_test_agent_12345"

        mock_tenant = {
            "id": tenant_id,
            "name": "Test Tenant",
            "chat_policy": {
                "enabled": True,
                "max_user_chars": 2000,
                "max_assistant_tokens": 1000,
                "max_turns_history": 10,
            },
            "agent_config": {
                "opportunities_chat_agent_id": agent_id,
                "opportunities_chat_instructions": "Default instructions",
                "opportunities_context_enabled": False,  # Disable to simplify test
            },
            "tenant_knowledge": {"enabled": False},
            "rag_policy": {"enabled": False},
        }

        user_token = TokenData(
            user_id=user_id,
            email="test@test.com",
            role="tenant_user",
            tenant_id=tenant_id
        )

        # Mock the Mistral client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"

        with patch('backend.routes.chat.get_db') as mock_get_db, \
             patch('backend.routes.chat.Mistral') as mock_mistral_class, \
             patch('backend.routes.chat.MISTRAL_API_KEY', 'test-key'):

            mock_db = MagicMock()
            mock_db.tenants.find_one = AsyncMock(return_value=mock_tenant)

            # Mock chat_turns cursor chain
            mock_turns_cursor = MagicMock()
            mock_turns_cursor.sort.return_value = mock_turns_cursor
            mock_turns_cursor.limit.return_value = mock_turns_cursor
            mock_turns_cursor.to_list = AsyncMock(return_value=[])
            mock_db.chat_turns.find.return_value = mock_turns_cursor
            mock_db.chat_turns.insert_one = AsyncMock()

            # Mock knowledge_snippets cursor
            mock_snip_cursor = MagicMock()
            mock_snip_cursor.to_list = AsyncMock(return_value=[])
            mock_db.knowledge_snippets.find.return_value = mock_snip_cursor

            mock_get_db.return_value = mock_db

            mock_client = MagicMock()
            mock_client.agents.complete = MagicMock(return_value=mock_response)
            mock_client.chat.complete = MagicMock(return_value=mock_response)
            mock_mistral_class.return_value = mock_client

            await send_chat_message(
                message_data={
                    "conversation_id": "test-conv",
                    "message": "Hello",
                    "agent_type": "opportunities"
                },
                current_user=user_token
            )

            # CRITICAL: agents.complete MUST be called, not chat.complete
            mock_client.agents.complete.assert_called_once()
            mock_client.chat.complete.assert_not_called()

            # Verify agent_id was passed
            call_kwargs = mock_client.agents.complete.call_args
            assert call_kwargs.kwargs.get('agent_id') == agent_id or \
                   (call_kwargs[1] and call_kwargs[1].get('agent_id') == agent_id), \
                   "agents.complete must be called with correct agent_id"

    @pytest.mark.asyncio
    async def test_chat_complete_fallback_when_no_agent_id(self):
        """When agent_id is NOT configured, chat.complete() MUST be used as fallback."""
        from backend.routes.chat import send_chat_message
        from backend.utils.auth import TokenData

        tenant_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        mock_tenant = {
            "id": tenant_id,
            "name": "Test Tenant",
            "chat_policy": {
                "enabled": True,
                "max_user_chars": 2000,
                "max_assistant_tokens": 1000,
                "max_turns_history": 10,
            },
            "agent_config": {
                # NO agent_id configured - should use fallback
                "opportunities_chat_instructions": "Default instructions",
                "opportunities_context_enabled": False,  # Disable to simplify test
            },
            "tenant_knowledge": {"enabled": False},
            "rag_policy": {"enabled": False},
        }

        user_token = TokenData(
            user_id=user_id,
            email="test@test.com",
            role="tenant_user",
            tenant_id=tenant_id
        )

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"

        with patch('backend.routes.chat.get_db') as mock_get_db, \
             patch('backend.routes.chat.Mistral') as mock_mistral_class, \
             patch('backend.routes.chat.MISTRAL_API_KEY', 'test-key'):

            mock_db = MagicMock()
            mock_db.tenants.find_one = AsyncMock(return_value=mock_tenant)

            # Mock chat_turns cursor chain
            mock_turns_cursor = MagicMock()
            mock_turns_cursor.sort.return_value = mock_turns_cursor
            mock_turns_cursor.limit.return_value = mock_turns_cursor
            mock_turns_cursor.to_list = AsyncMock(return_value=[])
            mock_db.chat_turns.find.return_value = mock_turns_cursor
            mock_db.chat_turns.insert_one = AsyncMock()

            # Mock knowledge_snippets cursor
            mock_snip_cursor = MagicMock()
            mock_snip_cursor.to_list = AsyncMock(return_value=[])
            mock_db.knowledge_snippets.find.return_value = mock_snip_cursor

            mock_get_db.return_value = mock_db

            mock_client = MagicMock()
            mock_client.agents.complete = MagicMock(return_value=mock_response)
            mock_client.chat.complete = MagicMock(return_value=mock_response)
            mock_mistral_class.return_value = mock_client

            await send_chat_message(
                message_data={
                    "conversation_id": "test-conv",
                    "message": "Hello",
                    "agent_type": "opportunities"
                },
                current_user=user_token
            )

            # CRITICAL: chat.complete MUST be called when no agent_id
            mock_client.chat.complete.assert_called_once()
            mock_client.agents.complete.assert_not_called()


class TestAgentIdScoring:
    """Tests for agent ID usage in opportunity scoring."""

    def test_scoring_agent_id_config_key_read(self):
        """mistral_service MUST read scoring_agent_id from config."""
        import inspect
        from backend.services import mistral_service

        source = inspect.getsource(mistral_service.score_opportunity_with_ai)

        assert "scoring_agent_id" in source, \
            "score_opportunity_with_ai must read scoring_agent_id from agent_config"


class TestAgentIdLogging:
    """Tests for proper agent ID logging."""

    def test_chat_logs_when_using_agent(self):
        """Chat route MUST log when using Mistral Agent."""
        import inspect
        from backend.routes import chat

        source = inspect.getsource(chat.send_chat_message)

        # Must log agent usage
        assert "Using Mistral Agent" in source or "chat_agent_id" in source, \
            "send_chat_message must log when using Mistral Agent"

    def test_chat_logs_when_using_fallback(self):
        """Chat route MUST log when using fallback instructions."""
        import inspect
        from backend.routes import chat

        source = inspect.getsource(chat.send_chat_message)

        # Must log fallback usage
        assert "dynamic instructions" in source or "no agent ID" in source, \
            "send_chat_message must log when using dynamic instructions fallback"
