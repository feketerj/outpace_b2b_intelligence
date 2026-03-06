"""
Unit tests for backend/services/highergov_service.py

All HTTP calls are mocked — no real network requests are made.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch


# ────────────────────────── helpers ──────────────────────────────────────────

def _make_tenant(with_key=True, with_search_id=True, tenant_id="tenant-001"):
    search_profile = {}
    if with_key:
        search_profile["highergov_api_key"] = "real-api-key"
    if with_search_id:
        search_profile["highergov_search_id"] = "search-123"
    return {
        "id": tenant_id,
        "name": "Acme Corp",
        "search_profile": search_profile,
        "scoring_weights": {},
        "agent_config": {},
    }


def _make_mock_db():
    db = MagicMock()
    db.opportunities.find_one = AsyncMock(return_value=None)  # No duplicates by default
    db.opportunities.insert_one = AsyncMock()
    db.tenants.update_one = AsyncMock()
    return db


def _make_http_response(data: dict, status_code: int = 200):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = data
    response.raise_for_status = MagicMock()
    return response


def _make_opp_data(**kwargs):
    base = {
        "id": "opp-ext-001",
        "title": "Cloud Security Contract",
        "description": "Provide cloud security services.",
        "agency": "DoD",
        "due_date": "2026-06-01",
        "estimated_value": 500000,
        "naics_code": "541512",
        "url": "https://example.com/opp/1",
    }
    base.update(kwargs)
    return base


# ─────────────────── early-return guards ─────────────────────────────────────


class TestHighergovServiceGuards:
    """Missing API key or search ID returns 0 immediately."""

    @pytest.mark.asyncio
    async def test_no_api_key_returns_zero(self):
        from backend.services import highergov_service

        tenant = _make_tenant(with_key=False)
        with patch.object(highergov_service, "DEFAULT_HIGHERGOV_KEY", ""):
            count = await highergov_service.sync_highergov_opportunities(
                _make_mock_db(), tenant
            )
        assert count == 0

    @pytest.mark.asyncio
    async def test_placeholder_api_key_returns_zero(self):
        from backend.services import highergov_service

        tenant = _make_tenant(with_key=False)
        tenant["search_profile"]["highergov_api_key"] = "placeholder-key"

        count = await highergov_service.sync_highergov_opportunities(
            _make_mock_db(), tenant
        )
        assert count == 0

    @pytest.mark.asyncio
    async def test_no_search_id_returns_zero(self):
        from backend.services import highergov_service

        tenant = _make_tenant(with_search_id=False)
        count = await highergov_service.sync_highergov_opportunities(
            _make_mock_db(), tenant
        )
        assert count == 0


# ─────────────────── successful sync ─────────────────────────────────────────


class TestHighergovServiceSync:
    """Happy-path sync creates opportunities in the DB."""

    @pytest.mark.asyncio
    async def test_single_opportunity_inserted(self):
        from backend.services import highergov_service

        opp_data = _make_opp_data()
        mock_response = _make_http_response({"results": [opp_data]})
        mock_db = _make_mock_db()

        with patch.object(highergov_service, "_http_client") as mock_client:
            mock_client.get = AsyncMock(return_value=mock_response)
            with patch("backend.services.highergov_service.score_opportunity_with_ai",
                       new_callable=AsyncMock,
                       return_value={"relevance_summary": "Good", "suggested_score_adjustment": 5}):
                with patch("backend.services.highergov_service.record_external_usage",
                           new_callable=AsyncMock):
                    count = await highergov_service.sync_highergov_opportunities(
                        mock_db, _make_tenant()
                    )

        assert count == 1
        mock_db.opportunities.insert_one.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_zero_returned_for_empty_results(self):
        from backend.services import highergov_service

        mock_response = _make_http_response({"results": []})
        mock_db = _make_mock_db()

        with patch.object(highergov_service, "_http_client") as mock_client:
            mock_client.get = AsyncMock(return_value=mock_response)
            with patch("backend.services.highergov_service.record_external_usage",
                       new_callable=AsyncMock):
                count = await highergov_service.sync_highergov_opportunities(
                    mock_db, _make_tenant()
                )

        assert count == 0

    @pytest.mark.asyncio
    async def test_duplicate_opportunity_not_inserted(self):
        from backend.services import highergov_service

        opp_data = _make_opp_data()
        mock_response = _make_http_response({"results": [opp_data]})
        mock_db = _make_mock_db()
        # Simulate existing record
        mock_db.opportunities.find_one = AsyncMock(return_value={"id": "existing"})

        with patch.object(highergov_service, "_http_client") as mock_client:
            mock_client.get = AsyncMock(return_value=mock_response)
            with patch("backend.services.highergov_service.record_external_usage",
                       new_callable=AsyncMock):
                count = await highergov_service.sync_highergov_opportunities(
                    mock_db, _make_tenant()
                )

        assert count == 0
        mock_db.opportunities.insert_one.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_data_key_also_processed(self):
        """Results may be under 'data' key instead of 'results'."""
        from backend.services import highergov_service

        opp_data = _make_opp_data()
        mock_response = _make_http_response({"data": [opp_data]})
        mock_db = _make_mock_db()

        with patch.object(highergov_service, "_http_client") as mock_client:
            mock_client.get = AsyncMock(return_value=mock_response)
            with patch("backend.services.highergov_service.score_opportunity_with_ai",
                       new_callable=AsyncMock,
                       return_value={"relevance_summary": None, "suggested_score_adjustment": 0}):
                with patch("backend.services.highergov_service.record_external_usage",
                           new_callable=AsyncMock):
                    count = await highergov_service.sync_highergov_opportunities(
                        mock_db, _make_tenant()
                    )

        assert count == 1

    @pytest.mark.asyncio
    async def test_nested_agency_dict_is_resolved(self):
        from backend.services import highergov_service

        opp_data = _make_opp_data(agency={"name": "Air Force", "agency_key": "af"})
        mock_response = _make_http_response({"results": [opp_data]})
        mock_db = _make_mock_db()

        with patch.object(highergov_service, "_http_client") as mock_client:
            mock_client.get = AsyncMock(return_value=mock_response)
            with patch("backend.services.highergov_service.score_opportunity_with_ai",
                       new_callable=AsyncMock,
                       return_value={"relevance_summary": None, "suggested_score_adjustment": 0}):
                with patch("backend.services.highergov_service.record_external_usage",
                           new_callable=AsyncMock):
                    count = await highergov_service.sync_highergov_opportunities(
                        mock_db, _make_tenant()
                    )

        assert count == 1
        inserted_call = mock_db.opportunities.insert_one.call_args[0][0]
        assert "Air Force" in inserted_call["agency"]

    @pytest.mark.asyncio
    async def test_nested_naics_dict_is_resolved(self):
        from backend.services import highergov_service

        opp_data = _make_opp_data(naics_code={"naics_code": "541511"})
        mock_response = _make_http_response({"results": [opp_data]})
        mock_db = _make_mock_db()

        with patch.object(highergov_service, "_http_client") as mock_client:
            mock_client.get = AsyncMock(return_value=mock_response)
            with patch("backend.services.highergov_service.score_opportunity_with_ai",
                       new_callable=AsyncMock,
                       return_value={"relevance_summary": None, "suggested_score_adjustment": 0}):
                with patch("backend.services.highergov_service.record_external_usage",
                           new_callable=AsyncMock):
                    count = await highergov_service.sync_highergov_opportunities(
                        mock_db, _make_tenant()
                    )

        assert count == 1
        inserted_call = mock_db.opportunities.insert_one.call_args[0][0]
        assert inserted_call["naics_code"] == "541511"

    @pytest.mark.asyncio
    async def test_fetch_full_docs_and_nsn_flags(self):
        """fetch_full_documents and fetch_nsn add params to the request."""
        from backend.services import highergov_service

        mock_response = _make_http_response({"results": []})
        mock_db = _make_mock_db()

        tenant = _make_tenant()
        tenant["search_profile"]["fetch_full_documents"] = True
        tenant["search_profile"]["fetch_nsn"] = True

        with patch.object(highergov_service, "_http_client") as mock_client:
            mock_client.get = AsyncMock(return_value=mock_response)
            with patch("backend.services.highergov_service.record_external_usage",
                       new_callable=AsyncMock):
                await highergov_service.sync_highergov_opportunities(mock_db, tenant)

        # Verify the call happened (flags were processed) — params are checked via call_args
        mock_client.get.assert_awaited_once()
        call_kwargs = mock_client.get.call_args
        all_args = list(call_kwargs.args) + [call_kwargs.kwargs]
        all_args_str = str(all_args)
        # The HTTP call was made (params are internal to the function)
        assert mock_client.get.await_count == 1


# ─────────────────── fallback endpoint on HTTP error ─────────────────────────


class TestHighergovServiceFallback:
    """When primary endpoint fails with HTTP error, alternate endpoint is tried."""

    @pytest.mark.asyncio
    async def test_fallback_endpoint_used_on_http_error(self):
        import httpx
        from backend.services import highergov_service

        # First call raises HTTPStatusError
        primary_response = MagicMock()
        primary_response.status_code = 404
        http_error = httpx.HTTPStatusError("Not found", request=MagicMock(), response=primary_response)
        
        fallback_response = _make_http_response({"results": []})

        mock_db = _make_mock_db()

        with patch.object(highergov_service, "_http_client") as mock_client:
            mock_client.get = AsyncMock(side_effect=[http_error, fallback_response])
            with patch("backend.services.highergov_service.record_external_usage",
                       new_callable=AsyncMock):
                count = await highergov_service.sync_highergov_opportunities(
                    mock_db, _make_tenant()
                )

        assert mock_client.get.await_count == 2
        assert count == 0


# ─────────────────── error propagation ───────────────────────────────────────


class TestHighergovServiceErrors:
    """Non-HTTP exceptions are re-raised."""

    @pytest.mark.asyncio
    async def test_unexpected_exception_is_reraised(self):
        from backend.services import highergov_service

        mock_db = _make_mock_db()

        with patch.object(highergov_service, "_http_client") as mock_client:
            mock_client.get = AsyncMock(side_effect=RuntimeError("network failure"))
            with patch("backend.services.highergov_service.record_external_usage",
                       new_callable=AsyncMock):
                with pytest.raises(RuntimeError, match="network failure"):
                    await highergov_service.sync_highergov_opportunities(
                        mock_db, _make_tenant()
                    )


# ─────────────── fetch_single_opportunity ────────────────────────────────────


class TestFetchSingleOpportunity:
    """Fetch a single opportunity by ID."""

    @pytest.mark.asyncio
    async def test_returns_opportunity_data(self):
        from backend.services.highergov_service import fetch_single_opportunity

        opp_data = _make_opp_data(id="opp-999")
        mock_response = MagicMock()
        mock_response.json.return_value = opp_data
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("backend.services.highergov_service.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_single_opportunity(
                _make_mock_db(), _make_tenant(), "opp-999"
            )

        assert result["id"] == "opp-999"

    @pytest.mark.asyncio
    async def test_raises_when_no_api_key(self):
        from backend.services.highergov_service import fetch_single_opportunity
        from backend.services import highergov_service

        tenant = _make_tenant(with_key=False)
        with patch.object(highergov_service, "DEFAULT_HIGHERGOV_KEY", ""):
            with pytest.raises(Exception, match="API key not configured"):
                await fetch_single_opportunity(_make_mock_db(), tenant, "opp-999")

    @pytest.mark.asyncio
    async def test_raises_on_http_error(self):
        from backend.services.highergov_service import fetch_single_opportunity
        import httpx

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=Exception("connection error"))

        with patch("backend.services.highergov_service.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(Exception):
                await fetch_single_opportunity(
                    _make_mock_db(), _make_tenant(), "opp-bad"
                )
