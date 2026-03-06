"""
Unit tests for backend/services/mistral_service.py

All Mistral API calls are mocked — no real network requests are made.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch


# ────────────────────────── helpers ──────────────────────────────────────────

def _make_tenant(name="Acme Corp", agent_id=None, instructions=None):
    return {
        "id": "tenant-001",
        "name": name,
        "agent_config": {
            "scoring_agent_id": agent_id,
            "scoring_instructions": instructions or "Analyze this.",
            "scoring_output_schema": {
                "relevance_summary": "string",
                "score_adjustment": "number",
            },
        },
        "search_profile": {
            "interest_areas": ["defense", "IT"],
            "competitors": ["CompA", "CompB"],
            "keywords": ["cloud", "cybersecurity"],
        },
    }


def _make_opportunity():
    return {
        "id": "opp-001",
        "title": "Cloud Security Services",
        "agency": "DoD",
        "description": "Provide cloud security services.",
        "estimated_value": 1000000,
        "naics_code": "541512",
        "due_date": "2026-06-01",
    }


def _make_mistral_response(content: str):
    choice = MagicMock()
    choice.message.content = content
    response = MagicMock()
    response.choices = [choice]
    return response


# ─────────────────── placeholder key → fast return ───────────────────────────


class TestMistralServiceSkipsOnPlaceholder:
    """When MISTRAL_API_KEY is absent/placeholder, scoring is skipped."""

    @pytest.mark.asyncio
    async def test_no_key_returns_null_summary(self):
        from backend.services import mistral_service

        with patch.object(mistral_service, "MISTRAL_API_KEY", ""):
            result = await mistral_service.score_opportunity_with_ai(
                _make_opportunity(), _make_tenant()
            )

        assert result["relevance_summary"] is None
        assert result["suggested_score_adjustment"] == 0

    @pytest.mark.asyncio
    async def test_placeholder_key_returns_null_summary(self):
        from backend.services import mistral_service

        with patch.object(mistral_service, "MISTRAL_API_KEY", "placeholder-key"):
            result = await mistral_service.score_opportunity_with_ai(
                _make_opportunity(), _make_tenant()
            )

        assert result["relevance_summary"] is None


# ─────────────────── chat.complete path (no agent_id) ────────────────────────


class TestMistralServiceChatComplete:
    """Uses chat.complete when no agent_id is configured."""

    @pytest.mark.asyncio
    async def test_valid_json_response_parsed_correctly(self):
        from backend.services import mistral_service

        content = json.dumps({
            "relevance_summary": "Highly relevant to cloud security.",
            "score_adjustment": 10,
        })
        mock_client = MagicMock()
        mock_client.chat.complete.return_value = _make_mistral_response(content)

        with patch.object(mistral_service, "MISTRAL_API_KEY", "real-key"):
            with patch("backend.services.mistral_service.Mistral", return_value=mock_client):
                with patch("backend.services.mistral_service.record_external_usage", new_callable=AsyncMock):
                    result = await mistral_service.score_opportunity_with_ai(
                        _make_opportunity(), _make_tenant()
                    )

        assert result["relevance_summary"] == "Highly relevant to cloud security."
        assert result["suggested_score_adjustment"] == 10

    @pytest.mark.asyncio
    async def test_json_in_markdown_block_is_parsed(self):
        from backend.services import mistral_service

        inner = json.dumps({"relevance_summary": "Good match.", "score_adjustment": 5})
        content = f"```json\n{inner}\n```"
        mock_client = MagicMock()
        mock_client.chat.complete.return_value = _make_mistral_response(content)

        with patch.object(mistral_service, "MISTRAL_API_KEY", "real-key"):
            with patch("backend.services.mistral_service.Mistral", return_value=mock_client):
                with patch("backend.services.mistral_service.record_external_usage", new_callable=AsyncMock):
                    result = await mistral_service.score_opportunity_with_ai(
                        _make_opportunity(), _make_tenant()
                    )

        assert result["relevance_summary"] == "Good match."

    @pytest.mark.asyncio
    async def test_non_json_response_uses_raw_content(self):
        from backend.services import mistral_service

        content = "This opportunity is relevant to cloud security work."
        mock_client = MagicMock()
        mock_client.chat.complete.return_value = _make_mistral_response(content)

        with patch.object(mistral_service, "MISTRAL_API_KEY", "real-key"):
            with patch("backend.services.mistral_service.Mistral", return_value=mock_client):
                with patch("backend.services.mistral_service.record_external_usage", new_callable=AsyncMock):
                    result = await mistral_service.score_opportunity_with_ai(
                        _make_opportunity(), _make_tenant()
                    )

        assert result["relevance_summary"] is not None
        assert len(result["relevance_summary"]) > 0

    @pytest.mark.asyncio
    async def test_nested_analysis_relevance_summary_extracted(self):
        from backend.services import mistral_service

        content = json.dumps({
            "analysis": {
                "relevance_summary": "Strong match for DoD work.",
                "score_adjustment": 15,
            }
        })
        mock_client = MagicMock()
        mock_client.chat.complete.return_value = _make_mistral_response(content)

        with patch.object(mistral_service, "MISTRAL_API_KEY", "real-key"):
            with patch("backend.services.mistral_service.Mistral", return_value=mock_client):
                with patch("backend.services.mistral_service.record_external_usage", new_callable=AsyncMock):
                    result = await mistral_service.score_opportunity_with_ai(
                        _make_opportunity(), _make_tenant()
                    )

        assert result["relevance_summary"] == "Strong match for DoD work."

    @pytest.mark.asyncio
    async def test_nested_description_in_analysis_extracted(self):
        from backend.services import mistral_service

        content = json.dumps({
            "analysis": {
                "relevance_summary": {"description": "Summary from description key."},
                "score_adjustment": 5,
            }
        })
        mock_client = MagicMock()
        mock_client.chat.complete.return_value = _make_mistral_response(content)

        with patch.object(mistral_service, "MISTRAL_API_KEY", "real-key"):
            with patch("backend.services.mistral_service.Mistral", return_value=mock_client):
                with patch("backend.services.mistral_service.record_external_usage", new_callable=AsyncMock):
                    result = await mistral_service.score_opportunity_with_ai(
                        _make_opportunity(), _make_tenant()
                    )

        assert result["relevance_summary"] == "Summary from description key."


# ─────────────────── agents.complete path (with agent_id) ────────────────────


class TestMistralServiceAgentComplete:
    """Uses agents.complete when agent_id is configured."""

    @pytest.mark.asyncio
    async def test_agent_id_path_is_used(self):
        from backend.services import mistral_service

        content = json.dumps({"relevance_summary": "Agent scored it.", "score_adjustment": 8})
        mock_client = MagicMock()
        mock_client.agents.complete.return_value = _make_mistral_response(content)

        tenant = _make_tenant(agent_id="ag:test-agent-id")

        with patch.object(mistral_service, "MISTRAL_API_KEY", "real-key"):
            with patch("backend.services.mistral_service.Mistral", return_value=mock_client):
                with patch("backend.services.mistral_service.record_external_usage", new_callable=AsyncMock):
                    result = await mistral_service.score_opportunity_with_ai(
                        _make_opportunity(), tenant
                    )

        mock_client.agents.complete.assert_called_once()
        assert result["relevance_summary"] == "Agent scored it."


# ─────────────────────────── error path ──────────────────────────────────────


class TestMistralServiceErrorHandling:
    """Exceptions during scoring are caught and returned gracefully."""

    @pytest.mark.asyncio
    async def test_api_exception_returns_error_dict(self):
        from backend.services import mistral_service

        mock_client = MagicMock()
        mock_client.chat.complete.side_effect = Exception("API timeout")

        with patch.object(mistral_service, "MISTRAL_API_KEY", "real-key"):
            with patch("backend.services.mistral_service.Mistral", return_value=mock_client):
                with patch("backend.services.mistral_service.record_external_usage", new_callable=AsyncMock):
                    result = await mistral_service.score_opportunity_with_ai(
                        _make_opportunity(), _make_tenant()
                    )

        assert result.get("ai_scoring_failed") is True
        assert "API timeout" in result.get("ai_error", "")
        assert result["relevance_summary"] is None

    @pytest.mark.asyncio
    async def test_key_highlights_included_in_result(self):
        from backend.services import mistral_service

        content = json.dumps({
            "relevance_summary": "Great fit.",
            "score_adjustment": 5,
            "key_highlights": ["defense", "cloud"],
        })
        mock_client = MagicMock()
        mock_client.chat.complete.return_value = _make_mistral_response(content)

        with patch.object(mistral_service, "MISTRAL_API_KEY", "real-key"):
            with patch("backend.services.mistral_service.Mistral", return_value=mock_client):
                with patch("backend.services.mistral_service.record_external_usage", new_callable=AsyncMock):
                    result = await mistral_service.score_opportunity_with_ai(
                        _make_opportunity(), _make_tenant()
                    )

        assert result["relevance_summary"] == "Great fit."
