"""
Unit tests for backend/services/perplexity_service.py

All HTTP calls are mocked — no real network requests are made.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ────────────────────────── helpers ──────────────────────────────────────────

def _make_tenant(enabled=True, use_template=False):
    intel_config = {"enabled": enabled}
    if use_template:
        intel_config["perplexity_prompt_template"] = (
            "Analyze {{COMPANY_NAME}} competitors {{COMPETITORS}} "
            "in {{INTEREST_AREAS}} with NAICS {{NAICS_CODES}} "
            "keywords {{KEYWORDS}} date {{CURRENT_DATE}} "
            "lookback {{LOOKBACK_DAYS}} deadline {{DEADLINE_WINDOW}}"
        )
        intel_config["lookback_days"] = 14
        intel_config["deadline_window_days"] = 120
    return {
        "id": "tenant-001",
        "name": "Acme Corp",
        "intelligence_config": intel_config,
        "search_profile": {
            "competitors": ["CompA", "CompB"],
            "interest_areas": ["cloud", "defense"],
            "naics_codes": ["541512"],
            "keywords": ["cyber", "AI"],
        },
    }


def _make_mock_db():
    db = MagicMock()
    db.intelligence.insert_one = AsyncMock()
    return db


def _make_perplexity_response(content: str, citations=None):
    choice = MagicMock()
    choice.message.content = content
    result = {
        "choices": [choice],
        "citations": citations if citations is not None else ["https://source1.com"],
    }
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = result
    response.raise_for_status = MagicMock()
    return response


# ─────────────────── early-return guards ─────────────────────────────────────


class TestPerplexityServiceGuards:
    """Service returns 0 immediately for misconfigured tenants."""

    @pytest.mark.asyncio
    async def test_disabled_intelligence_returns_zero(self):
        from backend.services import perplexity_service

        tenant = _make_tenant(enabled=False)
        count = await perplexity_service.sync_perplexity_intelligence(
            _make_mock_db(), tenant
        )
        assert count == 0

    @pytest.mark.asyncio
    async def test_placeholder_key_returns_zero(self):
        from backend.services import perplexity_service

        with patch.object(perplexity_service, "PERPLEXITY_API_KEY", "placeholder-key"):
            count = await perplexity_service.sync_perplexity_intelligence(
                _make_mock_db(), _make_tenant()
            )
        assert count == 0

    @pytest.mark.asyncio
    async def test_no_key_returns_zero(self):
        from backend.services import perplexity_service

        with patch.object(perplexity_service, "PERPLEXITY_API_KEY", ""):
            count = await perplexity_service.sync_perplexity_intelligence(
                _make_mock_db(), _make_tenant()
            )
        assert count == 0

    @pytest.mark.asyncio
    async def test_no_competitors_and_no_interest_areas_skips_queries(self):
        """With no template and no query sources, no queries are generated."""
        from backend.services import perplexity_service

        tenant = _make_tenant()
        tenant["search_profile"]["competitors"] = []
        tenant["search_profile"]["interest_areas"] = []

        with patch.object(perplexity_service, "PERPLEXITY_API_KEY", "real-key"):
            with patch.object(perplexity_service, "_http_client") as mock_client:
                mock_client.post = AsyncMock()
                count = await perplexity_service.sync_perplexity_intelligence(
                    _make_mock_db(), tenant
                )

        assert count == 0
        mock_client.post.assert_not_awaited()


# ─────────────────── successful sync with citation ───────────────────────────


class TestPerplexityServiceSync:
    """Happy-path sync creates intelligence records in the DB."""

    @pytest.mark.asyncio
    async def test_competitor_query_creates_record(self):
        from backend.services import perplexity_service

        mock_response = _make_perplexity_response(
            "CompA has won several DoD contracts. (https://source1.com)",
            citations=["https://source1.com"],
        )
        mock_db = _make_mock_db()

        with patch.object(perplexity_service, "PERPLEXITY_API_KEY", "real-key"):
            with patch.object(perplexity_service, "_http_client") as mock_client:
                mock_client.post = AsyncMock(return_value=mock_response)
                with patch("backend.services.perplexity_service.record_external_usage",
                           new_callable=AsyncMock):
                    count = await perplexity_service.sync_perplexity_intelligence(
                        mock_db, _make_tenant()
                    )

        assert count >= 1
        mock_db.intelligence.insert_one.assert_awaited()

    @pytest.mark.asyncio
    async def test_no_citations_report_rejected(self):
        """Reports without citations MUST be rejected."""
        from backend.services import perplexity_service

        mock_response = _make_perplexity_response(
            "Some content without sources.",
            citations=[],  # Empty citations
        )
        mock_db = _make_mock_db()

        with patch.object(perplexity_service, "PERPLEXITY_API_KEY", "real-key"):
            with patch.object(perplexity_service, "_http_client") as mock_client:
                mock_client.post = AsyncMock(return_value=mock_response)
                with patch("backend.services.perplexity_service.record_external_usage",
                           new_callable=AsyncMock):
                    count = await perplexity_service.sync_perplexity_intelligence(
                        mock_db, _make_tenant()
                    )

        assert count == 0
        mock_db.intelligence.insert_one.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_custom_template_creates_single_query(self):
        from backend.services import perplexity_service

        mock_response = _make_perplexity_response(
            "Full template-based report. (https://source1.com)",
            citations=["https://source1.com", "https://source2.com"],
        )
        mock_db = _make_mock_db()

        with patch.object(perplexity_service, "PERPLEXITY_API_KEY", "real-key"):
            with patch.object(perplexity_service, "_http_client") as mock_client:
                mock_client.post = AsyncMock(return_value=mock_response)
                with patch("backend.services.perplexity_service.record_external_usage",
                           new_callable=AsyncMock):
                    count = await perplexity_service.sync_perplexity_intelligence(
                        mock_db, _make_tenant(use_template=True)
                    )

        # One query from the template
        assert mock_client.post.await_count == 1
        assert count == 1

    @pytest.mark.asyncio
    async def test_interest_area_query_also_creates_record(self):
        """When competitors list is empty, interest_areas triggers queries."""
        from backend.services import perplexity_service

        mock_response = _make_perplexity_response(
            "Cloud market trends. (https://source1.com)",
            citations=["https://source1.com"],
        )
        mock_db = _make_mock_db()

        tenant = _make_tenant()
        tenant["search_profile"]["competitors"] = []  # No competitors
        # Keep interest_areas

        with patch.object(perplexity_service, "PERPLEXITY_API_KEY", "real-key"):
            with patch.object(perplexity_service, "_http_client") as mock_client:
                mock_client.post = AsyncMock(return_value=mock_response)
                with patch("backend.services.perplexity_service.record_external_usage",
                           new_callable=AsyncMock):
                    count = await perplexity_service.sync_perplexity_intelligence(
                        mock_db, tenant
                    )

        assert count >= 1

    @pytest.mark.asyncio
    async def test_inserted_record_has_correct_fields(self):
        from backend.services import perplexity_service

        mock_response = _make_perplexity_response(
            "Market intelligence content. (https://source1.com)",
            citations=["https://source1.com"],
        )
        mock_db = _make_mock_db()

        with patch.object(perplexity_service, "PERPLEXITY_API_KEY", "real-key"):
            with patch.object(perplexity_service, "_http_client") as mock_client:
                mock_client.post = AsyncMock(return_value=mock_response)
                with patch("backend.services.perplexity_service.record_external_usage",
                           new_callable=AsyncMock):
                    await perplexity_service.sync_perplexity_intelligence(
                        mock_db, _make_tenant()
                    )

        call_args = mock_db.intelligence.insert_one.call_args
        record = call_args[0][0]
        assert record["tenant_id"] == "tenant-001"
        assert isinstance(record["source_urls"], list)
        assert len(record["source_urls"]) > 0
        assert "id" in record
        assert "created_at" in record


# ─────────────────── per-query error handling ────────────────────────────────


class TestPerplexityServiceErrors:
    """Errors in individual queries are caught without stopping the loop."""

    @pytest.mark.asyncio
    async def test_query_exception_does_not_raise(self):
        from backend.services import perplexity_service

        mock_db = _make_mock_db()

        with patch.object(perplexity_service, "PERPLEXITY_API_KEY", "real-key"):
            with patch.object(perplexity_service, "_http_client") as mock_client:
                mock_client.post = AsyncMock(side_effect=Exception("API timeout"))
                with patch("backend.services.perplexity_service.record_external_usage",
                           new_callable=AsyncMock):
                    count = await perplexity_service.sync_perplexity_intelligence(
                        mock_db, _make_tenant()
                    )

        assert count == 0
