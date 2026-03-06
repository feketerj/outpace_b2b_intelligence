"""
Unit tests for backend/scheduler/sync_scheduler.py

All async operations and external API calls are mocked.
"""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone


# ────────────────────── helpers ──────────────────────────────────────────────

def _make_mock_db():
    db = MagicMock()
    db.sync_logs.insert_one = AsyncMock()
    db.sync_failures.insert_one = AsyncMock()
    db.tenants.update_one = AsyncMock()
    db.tenants.find = MagicMock()
    return db


def _make_tenant(tenant_id="t-001", name="Acme", status="active", schedule_cron=None):
    t = {
        "id": tenant_id,
        "name": name,
        "status": status,
        "search_profile": {},
        "intelligence_config": {},
    }
    if schedule_cron:
        t["intelligence_config"]["schedule_cron"] = schedule_cron
    return t


# ─────────────────── _sync_with_retry ────────────────────────────────────────


class TestSyncWithRetry:
    """Retry helper handles success and exhaustion."""

    @pytest.mark.asyncio
    async def test_success_on_first_attempt(self):
        from backend.scheduler.sync_scheduler import _sync_with_retry

        db = _make_mock_db()
        coro_factory = AsyncMock(return_value=5)

        result, exc = await _sync_with_retry("highergov", coro_factory, "t-001", db)

        assert result == 5
        assert exc is None
        coro_factory.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_success_on_second_attempt(self):
        from backend.scheduler.sync_scheduler import _sync_with_retry

        db = _make_mock_db()
        call_count = 0

        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("transient error")
            return 3

        with patch("backend.scheduler.sync_scheduler.asyncio.sleep", new_callable=AsyncMock):
            result, exc = await _sync_with_retry("highergov", flaky, "t-001", db)

        assert result == 3
        assert exc is None
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_all_attempts_exhausted_returns_last_exc(self):
        from backend.scheduler.sync_scheduler import _sync_with_retry

        db = _make_mock_db()
        err = RuntimeError("permanent failure")
        coro_factory = AsyncMock(side_effect=err)

        with patch("backend.scheduler.sync_scheduler.asyncio.sleep", new_callable=AsyncMock):
            result, exc = await _sync_with_retry("highergov", coro_factory, "t-001", db)

        assert result is None
        assert exc is err

    @pytest.mark.asyncio
    async def test_dead_letter_records_written_on_failure(self):
        from backend.scheduler.sync_scheduler import _sync_with_retry

        db = _make_mock_db()
        coro_factory = AsyncMock(side_effect=Exception("boom"))

        with patch("backend.scheduler.sync_scheduler.asyncio.sleep", new_callable=AsyncMock):
            await _sync_with_retry("highergov", coro_factory, "t-001", db)

        # 3 attempts = 3 dead-letter records
        assert db.sync_failures.insert_one.await_count == 3

    @pytest.mark.asyncio
    async def test_db_write_failure_does_not_propagate(self):
        """Failure to write dead-letter record should NOT raise."""
        from backend.scheduler.sync_scheduler import _sync_with_retry

        db = _make_mock_db()
        db.sync_failures.insert_one = AsyncMock(side_effect=Exception("db error"))
        coro_factory = AsyncMock(side_effect=Exception("main error"))

        with patch("backend.scheduler.sync_scheduler.asyncio.sleep", new_callable=AsyncMock):
            result, exc = await _sync_with_retry("highergov", coro_factory, "t-001", db)

        # Should return last exc from coro, not from DB write
        assert "main error" in str(exc)


# ─────────────────── sync_tenant_data ────────────────────────────────────────


class TestSyncTenantData:
    """sync_tenant_data orchestrates highergov + perplexity syncs."""

    @pytest.mark.asyncio
    async def test_both_syncs_succeed(self):
        from backend.scheduler import sync_scheduler

        db = _make_mock_db()
        tenant = _make_tenant()

        with patch("backend.scheduler.sync_scheduler.sync_highergov_opportunities",
                   new_callable=AsyncMock, return_value=3):
            with patch("backend.scheduler.sync_scheduler.sync_perplexity_intelligence",
                       new_callable=AsyncMock, return_value=2):
                result = await sync_scheduler.sync_tenant_data(db, tenant)

        assert result["opportunities_synced"] == 3
        assert result["intelligence_synced"] == 2
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_highergov_failure_recorded_in_errors(self):
        from backend.scheduler import sync_scheduler

        db = _make_mock_db()
        tenant = _make_tenant()

        with patch("backend.scheduler.sync_scheduler.sync_highergov_opportunities",
                   new_callable=AsyncMock, side_effect=Exception("HG failed")):
            with patch("backend.scheduler.sync_scheduler.sync_perplexity_intelligence",
                       new_callable=AsyncMock, return_value=1):
                with patch("backend.scheduler.sync_scheduler.asyncio.sleep",
                           new_callable=AsyncMock):
                    result = await sync_scheduler.sync_tenant_data(db, tenant)

        assert result["opportunities_synced"] == 0
        assert any("HigherGov" in e for e in result["errors"])

    @pytest.mark.asyncio
    async def test_perplexity_failure_recorded_in_errors(self):
        from backend.scheduler import sync_scheduler

        db = _make_mock_db()
        tenant = _make_tenant()

        with patch("backend.scheduler.sync_scheduler.sync_highergov_opportunities",
                   new_callable=AsyncMock, return_value=5):
            with patch("backend.scheduler.sync_scheduler.sync_perplexity_intelligence",
                       new_callable=AsyncMock, side_effect=Exception("PX failed")):
                with patch("backend.scheduler.sync_scheduler.asyncio.sleep",
                           new_callable=AsyncMock):
                    result = await sync_scheduler.sync_tenant_data(db, tenant)

        assert result["intelligence_synced"] == 0
        assert any("Perplexity" in e for e in result["errors"])

    @pytest.mark.asyncio
    async def test_sync_log_is_persisted(self):
        from backend.scheduler import sync_scheduler

        db = _make_mock_db()
        tenant = _make_tenant()

        with patch("backend.scheduler.sync_scheduler.sync_highergov_opportunities",
                   new_callable=AsyncMock, return_value=0):
            with patch("backend.scheduler.sync_scheduler.sync_perplexity_intelligence",
                       new_callable=AsyncMock, return_value=0):
                await sync_scheduler.sync_tenant_data(db, tenant)

        db.sync_logs.insert_one.assert_awaited_once()
        log_arg = db.sync_logs.insert_one.call_args[0][0]
        assert log_arg["tenant_id"] == "t-001"
        assert "status" in log_arg

    @pytest.mark.asyncio
    async def test_tenant_last_synced_at_updated(self):
        from backend.scheduler import sync_scheduler

        db = _make_mock_db()
        tenant = _make_tenant()

        with patch("backend.scheduler.sync_scheduler.sync_highergov_opportunities",
                   new_callable=AsyncMock, return_value=0):
            with patch("backend.scheduler.sync_scheduler.sync_perplexity_intelligence",
                       new_callable=AsyncMock, return_value=0):
                await sync_scheduler.sync_tenant_data(db, tenant)

        db.tenants.update_one.assert_awaited_once()


# ─────────────────── daily_sync_all_tenants ──────────────────────────────────


class TestDailySyncAllTenants:
    """daily_sync_all_tenants iterates over active tenants."""

    @pytest.mark.asyncio
    async def test_syncs_all_active_tenants(self):
        from backend.scheduler import sync_scheduler

        db = _make_mock_db()
        tenants = [_make_tenant("t-001"), _make_tenant("t-002")]

        cursor = MagicMock()
        cursor.to_list = AsyncMock(return_value=tenants)
        db.tenants.find.return_value = cursor

        with patch("backend.scheduler.sync_scheduler.sync_tenant_data",
                   new_callable=AsyncMock) as mock_sync:
            with patch("backend.scheduler.sync_scheduler.asyncio.sleep",
                       new_callable=AsyncMock):
                await sync_scheduler.daily_sync_all_tenants(db)

        assert mock_sync.await_count == 2

    @pytest.mark.asyncio
    async def test_continues_on_tenant_error(self):
        """Error in one tenant should not stop others."""
        from backend.scheduler import sync_scheduler

        db = _make_mock_db()
        tenants = [_make_tenant("t-001"), _make_tenant("t-002")]

        cursor = MagicMock()
        cursor.to_list = AsyncMock(return_value=tenants)
        db.tenants.find.return_value = cursor

        call_count = 0

        async def sync_with_first_error(db, tenant):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Tenant 1 failed")
            return {}

        with patch("backend.scheduler.sync_scheduler.sync_tenant_data",
                   side_effect=sync_with_first_error):
            with patch("backend.scheduler.sync_scheduler.asyncio.sleep",
                       new_callable=AsyncMock):
                # Should not raise
                await sync_scheduler.daily_sync_all_tenants(db)

        assert call_count == 2  # Both tenants attempted


# ─────────────────── stop_scheduler ──────────────────────────────────────────


class TestStopScheduler:
    def test_stop_running_scheduler(self):
        from backend.scheduler.sync_scheduler import stop_scheduler

        mock_scheduler = MagicMock()
        type(mock_scheduler).running = property(lambda self: True)
        mock_scheduler.shutdown = MagicMock()

        with patch("backend.scheduler.sync_scheduler.scheduler", mock_scheduler):
            stop_scheduler()
            mock_scheduler.shutdown.assert_called_once()

    def test_stop_already_stopped_scheduler(self):
        from backend.scheduler.sync_scheduler import stop_scheduler

        mock_scheduler = MagicMock()
        type(mock_scheduler).running = property(lambda self: False)

        with patch("backend.scheduler.sync_scheduler.scheduler", mock_scheduler):
            # Should not raise
            stop_scheduler()
            mock_scheduler.shutdown.assert_not_called()



# ─────────────────── start_scheduler ────────────────────────────────────────


class TestStartScheduler:
    """start_scheduler sets up cron jobs."""

    def test_start_scheduler_adds_default_job(self):
        from backend.scheduler import sync_scheduler

        mock_scheduler = MagicMock()
        type(mock_scheduler).running = property(lambda self: False)

        with patch("backend.scheduler.sync_scheduler.scheduler", mock_scheduler):
            with patch.dict(os.environ, {"RETENTION_ENABLED": "false"}, clear=False):
                sync_scheduler.start_scheduler(MagicMock())

        mock_scheduler.add_job.assert_called()
        mock_scheduler.start.assert_called_once()

    def test_start_scheduler_with_retention_enabled(self):
        import os
        from backend.scheduler import sync_scheduler

        mock_scheduler = MagicMock()
        type(mock_scheduler).running = property(lambda self: False)

        with patch("backend.scheduler.sync_scheduler.scheduler", mock_scheduler):
            with patch.dict(os.environ, {
                "RETENTION_ENABLED": "true",
                "RETENTION_CRON": "0 3 * * *",
            }, clear=False):
                sync_scheduler.start_scheduler(MagicMock())

        # Should add at least 2 jobs (default + retention)
        assert mock_scheduler.add_job.call_count >= 2

    def test_start_scheduler_with_invalid_retention_cron(self):
        import os
        from backend.scheduler import sync_scheduler

        mock_scheduler = MagicMock()
        type(mock_scheduler).running = property(lambda self: False)

        with patch("backend.scheduler.sync_scheduler.scheduler", mock_scheduler):
            with patch.dict(os.environ, {
                "RETENTION_ENABLED": "true",
                "RETENTION_CRON": "bad cron format",  # Invalid
            }, clear=False):
                sync_scheduler.start_scheduler(MagicMock())

        # Should still start (just without retention job)
        mock_scheduler.start.assert_called_once()


# ─────────────────── setup_tenant_schedules ──────────────────────────────────


class TestSetupTenantSchedules:
    """setup_tenant_schedules adds jobs for tenants with custom crons."""

    @pytest.mark.asyncio
    async def test_custom_cron_adds_job(self):
        import os
        from backend.scheduler import sync_scheduler

        db = _make_mock_db()
        tenant = _make_tenant("t-custom", schedule_cron="30 6 * * *")
        cursor = MagicMock()
        cursor.to_list = AsyncMock(return_value=[tenant])
        db.tenants.find.return_value = cursor

        mock_scheduler = MagicMock()
        type(mock_scheduler).running = property(lambda self: False)

        with patch("backend.scheduler.sync_scheduler.scheduler", mock_scheduler):
            await sync_scheduler.setup_tenant_schedules(db)

        mock_scheduler.add_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_default_cron_does_not_add_extra_job(self):
        """Tenants with default cron (0 2 * * *) should not get extra jobs."""
        from backend.scheduler import sync_scheduler

        db = _make_mock_db()
        tenant = _make_tenant("t-default", schedule_cron="0 2 * * *")
        cursor = MagicMock()
        cursor.to_list = AsyncMock(return_value=[tenant])
        db.tenants.find.return_value = cursor

        mock_scheduler = MagicMock()
        type(mock_scheduler).running = property(lambda self: False)

        with patch("backend.scheduler.sync_scheduler.scheduler", mock_scheduler):
            await sync_scheduler.setup_tenant_schedules(db)

        mock_scheduler.add_job.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_schedule_cron_skips_tenant(self):
        from backend.scheduler import sync_scheduler

        db = _make_mock_db()
        tenant = _make_tenant("t-no-cron")  # No schedule_cron
        cursor = MagicMock()
        cursor.to_list = AsyncMock(return_value=[tenant])
        db.tenants.find.return_value = cursor

        mock_scheduler = MagicMock()
        type(mock_scheduler).running = property(lambda self: False)

        with patch("backend.scheduler.sync_scheduler.scheduler", mock_scheduler):
            await sync_scheduler.setup_tenant_schedules(db)

        mock_scheduler.add_job.assert_not_called()


class TestSyncSingleTenantById:
    @pytest.mark.asyncio
    async def test_syncs_found_tenant(self):
        from backend.scheduler import sync_scheduler

        db = _make_mock_db()
        tenant = _make_tenant()
        db.tenants.find_one = AsyncMock(return_value=tenant)

        with patch("backend.scheduler.sync_scheduler.sync_tenant_data",
                   new_callable=AsyncMock) as mock_sync:
            await sync_scheduler.sync_single_tenant_by_id(db, "t-001")

        mock_sync.assert_awaited_once_with(db, tenant)

    @pytest.mark.asyncio
    async def test_does_nothing_for_missing_tenant(self):
        from backend.scheduler import sync_scheduler

        db = _make_mock_db()
        db.tenants.find_one = AsyncMock(return_value=None)

        with patch("backend.scheduler.sync_scheduler.sync_tenant_data",
                   new_callable=AsyncMock) as mock_sync:
            await sync_scheduler.sync_single_tenant_by_id(db, "missing-id")

        mock_sync.assert_not_awaited()
