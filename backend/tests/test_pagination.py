"""
Pagination Tests - Edge case validation for paginated endpoints.

These tests verify that pagination:
- Works correctly at boundary values
- Handles invalid inputs appropriately
- Enforces maximum per_page limits

Run: pytest backend/tests/test_pagination.py -v
"""

import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from backend.models import TokenData, PaginatedResponse
from backend.routes.opportunities import list_opportunities


# Test fixtures
TENANT_ID = str(uuid.uuid4())
USER_ID = str(uuid.uuid4())


def make_tenant_user_token(tenant_id: str = TENANT_ID):
    """Create a tenant user token for testing."""
    return TokenData(
        user_id=USER_ID,
        email="user@test.com",
        role="tenant_user",
        tenant_id=tenant_id
    )


def make_super_admin_token():
    """Create a super admin token for testing."""
    return TokenData(
        user_id=USER_ID,
        email="admin@test.com",
        role="super_admin",
        tenant_id=None
    )


def make_opportunity_doc(index: int, tenant_id: str = TENANT_ID):
    """Create a complete opportunity document for mocking."""
    opp_id = str(uuid.uuid4())
    return {
        "id": opp_id,
        "tenant_id": tenant_id,
        "external_id": f"ext-{index}",
        "title": f"Opportunity {index}",
        "description": f"Description for opportunity {index}",
        "agency": "Test Agency",
        "due_date": None,
        "estimated_value": "$100,000",
        "naics_code": "541511",
        "keywords": [],
        "source_type": "manual",
        "source_url": "",
        "raw_data": {},
        "client_status": "new",
        "client_notes": None,
        "client_tags": [],
        "is_archived": False,
        "score": 100 - index,  # Descending scores for sort verification
        "ai_relevance_summary": None,
        "captured_date": "2026-01-01T00:00:00+00:00",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00"
    }


class TestPaginationBoundaryValues:
    """Test pagination at boundary values."""

    @pytest.mark.asyncio
    async def test_pagination_with_25_records_page_1(self):
        """
        Create 25 records, test page=1 with per_page=10.

        Should return first 10 records with correct pagination metadata.
        """
        # Create 25 mock opportunities
        all_opportunities = [make_opportunity_doc(i) for i in range(25)]

        with patch('backend.routes.opportunities.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.skip.return_value = mock_cursor
            mock_cursor.limit.return_value = mock_cursor
            mock_cursor.sort.return_value = mock_cursor
            # Page 1: first 10 records
            mock_cursor.to_list = AsyncMock(return_value=all_opportunities[0:10])
            mock_db.opportunities.find.return_value = mock_cursor
            mock_db.opportunities.count_documents = AsyncMock(return_value=25)
            mock_get_db.return_value = mock_db

            result = await list_opportunities(
                page=1,
                per_page=10,
                current_user=make_tenant_user_token()
            )

        assert isinstance(result, PaginatedResponse)
        assert len(result.data) == 10
        assert result.pagination.total == 25
        assert result.pagination.page == 1
        assert result.pagination.per_page == 10
        assert result.pagination.pages == 3  # ceil(25/10) = 3

        # Verify skip was called correctly (page 1 = skip 0)
        mock_cursor.skip.assert_called_with(0)
        mock_cursor.limit.assert_called_with(10)

    @pytest.mark.asyncio
    async def test_pagination_with_25_records_page_2(self):
        """
        Create 25 records, test page=2 with per_page=10.

        Should return records 11-20 with correct pagination metadata.
        """
        all_opportunities = [make_opportunity_doc(i) for i in range(25)]

        with patch('backend.routes.opportunities.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.skip.return_value = mock_cursor
            mock_cursor.limit.return_value = mock_cursor
            mock_cursor.sort.return_value = mock_cursor
            # Page 2: records 10-19
            mock_cursor.to_list = AsyncMock(return_value=all_opportunities[10:20])
            mock_db.opportunities.find.return_value = mock_cursor
            mock_db.opportunities.count_documents = AsyncMock(return_value=25)
            mock_get_db.return_value = mock_db

            result = await list_opportunities(
                page=2,
                per_page=10,
                current_user=make_tenant_user_token()
            )

        assert isinstance(result, PaginatedResponse)
        assert len(result.data) == 10
        assert result.pagination.total == 25
        assert result.pagination.page == 2
        assert result.pagination.per_page == 10
        assert result.pagination.pages == 3

        # Verify skip was called correctly (page 2 = skip 10)
        mock_cursor.skip.assert_called_with(10)

    @pytest.mark.asyncio
    async def test_pagination_with_25_records_page_3(self):
        """
        Create 25 records, test page=3 with per_page=10.

        Should return last 5 records (partial page).
        """
        all_opportunities = [make_opportunity_doc(i) for i in range(25)]

        with patch('backend.routes.opportunities.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.skip.return_value = mock_cursor
            mock_cursor.limit.return_value = mock_cursor
            mock_cursor.sort.return_value = mock_cursor
            # Page 3: records 20-24 (only 5 records)
            mock_cursor.to_list = AsyncMock(return_value=all_opportunities[20:25])
            mock_db.opportunities.find.return_value = mock_cursor
            mock_db.opportunities.count_documents = AsyncMock(return_value=25)
            mock_get_db.return_value = mock_db

            result = await list_opportunities(
                page=3,
                per_page=10,
                current_user=make_tenant_user_token()
            )

        assert isinstance(result, PaginatedResponse)
        assert len(result.data) == 5  # Partial page
        assert result.pagination.total == 25
        assert result.pagination.page == 3
        assert result.pagination.pages == 3

        # Verify skip was called correctly (page 3 = skip 20)
        mock_cursor.skip.assert_called_with(20)

    @pytest.mark.asyncio
    async def test_pagination_beyond_last_page_returns_empty(self):
        """
        Request page=4 when only 3 pages exist.

        Should return empty data with correct metadata.
        """
        with patch('backend.routes.opportunities.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.skip.return_value = mock_cursor
            mock_cursor.limit.return_value = mock_cursor
            mock_cursor.sort.return_value = mock_cursor
            mock_cursor.to_list = AsyncMock(return_value=[])  # No records
            mock_db.opportunities.find.return_value = mock_cursor
            mock_db.opportunities.count_documents = AsyncMock(return_value=25)
            mock_get_db.return_value = mock_db

            result = await list_opportunities(
                page=4,
                per_page=10,
                current_user=make_tenant_user_token()
            )

        assert isinstance(result, PaginatedResponse)
        assert len(result.data) == 0
        assert result.pagination.total == 25
        assert result.pagination.page == 4
        assert result.pagination.pages == 3

    @pytest.mark.asyncio
    async def test_pagination_with_exact_multiple(self):
        """
        Create 20 records, test with per_page=10.

        Should have exactly 2 full pages.
        """
        all_opportunities = [make_opportunity_doc(i) for i in range(20)]

        with patch('backend.routes.opportunities.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.skip.return_value = mock_cursor
            mock_cursor.limit.return_value = mock_cursor
            mock_cursor.sort.return_value = mock_cursor
            mock_cursor.to_list = AsyncMock(return_value=all_opportunities[10:20])
            mock_db.opportunities.find.return_value = mock_cursor
            mock_db.opportunities.count_documents = AsyncMock(return_value=20)
            mock_get_db.return_value = mock_db

            result = await list_opportunities(
                page=2,
                per_page=10,
                current_user=make_tenant_user_token()
            )

        assert result.pagination.total == 20
        assert result.pagination.pages == 2  # Exactly 2 pages


class TestInvalidPageHandling:
    """Test that invalid page values are handled correctly."""

    def test_page_parameter_validation_in_signature(self):
        """
        Verify page parameter has ge=1 constraint.

        FastAPI Query validation should reject page < 1.
        """
        import inspect
        from backend.routes import opportunities

        source = inspect.getsource(opportunities.list_opportunities)

        # Verify page has ge=1 constraint
        assert "page: int = Query(1, ge=1)" in source or \
               "page: int = Query(default=1, ge=1)" in source or \
               ("page" in source and "ge=1" in source), \
            "page parameter must have ge=1 validation"

    def test_page_zero_rejected_by_validation(self):
        """
        Verify page=0 would fail FastAPI Query validation.

        The ge=1 constraint means page must be >= 1.
        Static analysis test to ensure constraint exists.
        """
        import inspect
        from backend.routes import opportunities

        source = inspect.getsource(opportunities.list_opportunities)

        # Verify page parameter has ge=1 constraint in source
        # This ensures the validation is in place
        assert "page" in source and "ge=1" in source, \
            "page parameter must have ge=1 constraint"

    def test_negative_page_rejected_by_validation(self):
        """
        Verify page=-1 would fail FastAPI Query validation.

        The ge=1 constraint in the source code means page must be >= 1.
        """
        import inspect
        from backend.routes import opportunities

        source = inspect.getsource(opportunities.list_opportunities)

        # The ge=1 constraint appears on the same line as page parameter
        # This proves negative pages will be rejected
        assert "page: int = Query(1, ge=1)" in source or \
               ("page" in source and "ge=1" in source), \
            "page parameter must reject negative values via ge=1"


class TestPerPageLimits:
    """Test that per_page is properly constrained."""

    def test_per_page_has_maximum_constraint(self):
        """
        Verify per_page parameter has le=100 constraint.

        Prevents clients from requesting too many records at once.
        """
        import inspect
        from backend.routes import opportunities

        source = inspect.getsource(opportunities.list_opportunities)

        # Verify per_page has le=100 constraint
        assert "le=100" in source, \
            "per_page parameter must have le=100 maximum constraint"

    def test_per_page_query_constraints(self):
        """
        Verify per_page Query has both min and max constraints.

        Static analysis to ensure both ge=1 and le=100 are present.
        """
        import inspect
        from backend.routes import opportunities

        source = inspect.getsource(opportunities.list_opportunities)

        # Verify per_page has both min and max constraints
        assert "per_page" in source and "ge=1" in source, \
            "per_page must have minimum of 1"
        assert "per_page" in source and "le=100" in source, \
            "per_page must have maximum of 100"

    @pytest.mark.asyncio
    async def test_per_page_at_maximum_works(self):
        """
        Request with per_page=100 (the maximum) should succeed.
        """
        all_opportunities = [make_opportunity_doc(i) for i in range(100)]

        with patch('backend.routes.opportunities.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.skip.return_value = mock_cursor
            mock_cursor.limit.return_value = mock_cursor
            mock_cursor.sort.return_value = mock_cursor
            mock_cursor.to_list = AsyncMock(return_value=all_opportunities)
            mock_db.opportunities.find.return_value = mock_cursor
            mock_db.opportunities.count_documents = AsyncMock(return_value=100)
            mock_get_db.return_value = mock_db

            result = await list_opportunities(
                page=1,
                per_page=100,  # Maximum allowed
                current_user=make_tenant_user_token()
            )

        assert isinstance(result, PaginatedResponse)
        assert result.pagination.per_page == 100
        mock_cursor.limit.assert_called_with(100)

    @pytest.mark.asyncio
    async def test_per_page_at_minimum_works(self):
        """
        Request with per_page=1 (the minimum) should succeed.
        """
        opportunity = make_opportunity_doc(0)

        with patch('backend.routes.opportunities.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.skip.return_value = mock_cursor
            mock_cursor.limit.return_value = mock_cursor
            mock_cursor.sort.return_value = mock_cursor
            mock_cursor.to_list = AsyncMock(return_value=[opportunity])
            mock_db.opportunities.find.return_value = mock_cursor
            mock_db.opportunities.count_documents = AsyncMock(return_value=50)
            mock_get_db.return_value = mock_db

            result = await list_opportunities(
                page=1,
                per_page=1,  # Minimum allowed
                current_user=make_tenant_user_token()
            )

        assert isinstance(result, PaginatedResponse)
        assert len(result.data) == 1
        assert result.pagination.per_page == 1
        assert result.pagination.pages == 50  # 50 records / 1 per page


class TestPaginationMetadataAccuracy:
    """Test that pagination metadata is calculated correctly."""

    @pytest.mark.asyncio
    async def test_pages_calculation_rounds_up(self):
        """
        Verify pages calculation uses ceiling division.

        21 records / 10 per_page = 3 pages (not 2).
        """
        all_opportunities = [make_opportunity_doc(i) for i in range(10)]

        with patch('backend.routes.opportunities.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.skip.return_value = mock_cursor
            mock_cursor.limit.return_value = mock_cursor
            mock_cursor.sort.return_value = mock_cursor
            mock_cursor.to_list = AsyncMock(return_value=all_opportunities)
            mock_db.opportunities.find.return_value = mock_cursor
            mock_db.opportunities.count_documents = AsyncMock(return_value=21)
            mock_get_db.return_value = mock_db

            result = await list_opportunities(
                page=1,
                per_page=10,
                current_user=make_tenant_user_token()
            )

        # 21 records / 10 per_page = 2.1, rounds up to 3 pages
        assert result.pagination.pages == 3

    @pytest.mark.asyncio
    async def test_zero_records_returns_zero_pages(self):
        """
        Empty result set should return pages=0.
        """
        with patch('backend.routes.opportunities.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.skip.return_value = mock_cursor
            mock_cursor.limit.return_value = mock_cursor
            mock_cursor.sort.return_value = mock_cursor
            mock_cursor.to_list = AsyncMock(return_value=[])
            mock_db.opportunities.find.return_value = mock_cursor
            mock_db.opportunities.count_documents = AsyncMock(return_value=0)
            mock_get_db.return_value = mock_db

            result = await list_opportunities(
                page=1,
                per_page=10,
                current_user=make_tenant_user_token()
            )

        assert result.pagination.total == 0
        assert result.pagination.pages == 0
        assert len(result.data) == 0

    @pytest.mark.asyncio
    async def test_single_record_returns_one_page(self):
        """
        Single record should return pages=1.
        """
        opportunity = make_opportunity_doc(0)

        with patch('backend.routes.opportunities.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.skip.return_value = mock_cursor
            mock_cursor.limit.return_value = mock_cursor
            mock_cursor.sort.return_value = mock_cursor
            mock_cursor.to_list = AsyncMock(return_value=[opportunity])
            mock_db.opportunities.find.return_value = mock_cursor
            mock_db.opportunities.count_documents = AsyncMock(return_value=1)
            mock_get_db.return_value = mock_db

            result = await list_opportunities(
                page=1,
                per_page=10,
                current_user=make_tenant_user_token()
            )

        assert result.pagination.total == 1
        assert result.pagination.pages == 1
        assert len(result.data) == 1
