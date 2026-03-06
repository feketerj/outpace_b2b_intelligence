"""
Unit tests for backend/stress_test_tenants.py

Tests pure helper/utility functions by mocking the `requests` library.
No real HTTP calls are made.
"""

import pytest
from unittest.mock import MagicMock, patch


# ────────────────────── helpers / fixtures ───────────────────────────────────

def _mock_json_response(data: dict, status_code: int = 200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = data
    resp.text = str(data)
    return resp


# ────────────────────── login_admin ──────────────────────────────────────────


class TestLoginAdmin:
    def test_successful_login_sets_token(self):
        import backend.stress_test_tenants as st

        resp = _mock_json_response({"access_token": "my-token"}, 200)
        with patch("backend.stress_test_tenants.requests.post", return_value=resp):
            token = st.login_admin()

        assert token == "my-token"
        assert st.ADMIN_TOKEN == "my-token"

    def test_failed_login_raises(self):
        import backend.stress_test_tenants as st

        resp = _mock_json_response({}, 401)
        resp.text = "Unauthorized"
        with patch("backend.stress_test_tenants.requests.post", return_value=resp):
            with pytest.raises(Exception, match="Admin login failed"):
                st.login_admin()


# ────────────────────── headers ──────────────────────────────────────────────


class TestHeaders:
    def test_returns_authorization_header(self):
        import backend.stress_test_tenants as st

        st.ADMIN_TOKEN = "bearer-token-xyz"
        headers = st.headers()
        assert headers["Authorization"] == "Bearer bearer-token-xyz"
        assert headers["Content-Type"] == "application/json"


# ────────────────────── create_tenant ────────────────────────────────────────


class TestCreateTenant:
    def test_successful_creation_returns_data(self):
        import backend.stress_test_tenants as st

        st.ADMIN_TOKEN = "tok"
        resp = _mock_json_response({"id": "t-001", "slug": "scale-test-1"}, 201)
        with patch("backend.stress_test_tenants.requests.post", return_value=resp):
            data, ms = st.create_tenant(1)

        assert data["id"] == "t-001"
        assert ms >= 0

    def test_failed_creation_returns_none(self):
        import backend.stress_test_tenants as st

        st.ADMIN_TOKEN = "tok"
        resp = _mock_json_response({"detail": "error"}, 400)
        with patch("backend.stress_test_tenants.requests.post", return_value=resp):
            data, ms = st.create_tenant(1)

        assert data is None

    def test_error_is_recorded_in_results(self):
        import backend.stress_test_tenants as st

        st.ADMIN_TOKEN = "tok"
        # Clear errors first
        st.results["errors"] = []
        resp = _mock_json_response({"detail": "bad"}, 400)
        with patch("backend.stress_test_tenants.requests.post", return_value=resp):
            st.create_tenant(99)

        assert any("Tenant 99" in e for e in st.results["errors"])


# ────────────────────── create_user ──────────────────────────────────────────


class TestCreateUser:
    def test_successful_user_creation(self):
        import backend.stress_test_tenants as st

        st.ADMIN_TOKEN = "tok"
        resp = _mock_json_response({"id": "u-001", "email": "user1@test.com"}, 201)
        with patch("backend.stress_test_tenants.requests.post", return_value=resp):
            data, ms = st.create_user("t-001", 1, 1)

        assert data["id"] == "u-001"
        assert ms >= 0

    def test_failed_user_creation_returns_none(self):
        import backend.stress_test_tenants as st

        st.ADMIN_TOKEN = "tok"
        resp = _mock_json_response({"detail": "conflict"}, 409)
        with patch("backend.stress_test_tenants.requests.post", return_value=resp):
            data, ms = st.create_user("t-001", 1, 1)

        assert data is None


# ────────────────────── create_opportunity ───────────────────────────────────


class TestCreateOpportunity:
    def test_successful_opportunity_creation(self):
        import backend.stress_test_tenants as st

        st.ADMIN_TOKEN = "tok"
        resp = _mock_json_response({"id": "opp-001"}, 201)
        with patch("backend.stress_test_tenants.requests.post", return_value=resp):
            data, ms = st.create_opportunity("t-001", 1, 1)

        assert data["id"] == "opp-001"

    def test_failed_opportunity_returns_none(self):
        import backend.stress_test_tenants as st

        st.ADMIN_TOKEN = "tok"
        resp = _mock_json_response({"detail": "error"}, 500)
        with patch("backend.stress_test_tenants.requests.post", return_value=resp):
            data, ms = st.create_opportunity("t-001", 1, 1)

        assert data is None


# ────────────────────── verify_tenant_count ──────────────────────────────────


class TestVerifyTenantCount:
    def test_correct_count_passes(self):
        import backend.stress_test_tenants as st

        st.ADMIN_TOKEN = "tok"
        resp = _mock_json_response({"pagination": {"total": 22}})
        with patch("backend.stress_test_tenants.requests.get", return_value=resp):
            result = st.verify_tenant_count()

        assert result["passed"] is True
        assert result["actual"] == 22

    def test_wrong_count_fails(self):
        import backend.stress_test_tenants as st

        st.ADMIN_TOKEN = "tok"
        resp = _mock_json_response({"pagination": {"total": 10}})
        with patch("backend.stress_test_tenants.requests.get", return_value=resp):
            result = st.verify_tenant_count()

        assert result["passed"] is False
        assert result["actual"] == 10


# ────────────────────── verify_users_per_tenant ──────────────────────────────


class TestVerifyUsersPerTenant:
    def test_two_users_passes(self):
        import backend.stress_test_tenants as st

        st.ADMIN_TOKEN = "tok"
        users = [
            {"tenant_id": "t-5", "id": "u-1"},
            {"tenant_id": "t-5", "id": "u-2"},
        ]
        resp = _mock_json_response({"data": users})
        with patch("backend.stress_test_tenants.requests.get", return_value=resp):
            passed, count = st.verify_users_per_tenant("t-5", 5)

        assert passed is True
        assert count == 2

    def test_one_user_fails(self):
        import backend.stress_test_tenants as st

        st.ADMIN_TOKEN = "tok"
        users = [{"tenant_id": "t-5", "id": "u-1"}]
        resp = _mock_json_response({"data": users})
        with patch("backend.stress_test_tenants.requests.get", return_value=resp):
            passed, count = st.verify_users_per_tenant("t-5", 5)

        assert passed is False


# ────────────────────── verify_opportunities_per_tenant ──────────────────────


class TestVerifyOpportunitiesPerTenant:
    def test_fifty_opportunities_passes(self):
        import backend.stress_test_tenants as st

        st.ADMIN_TOKEN = "tok"
        login_resp = _mock_json_response({"access_token": "user-tok"}, 200)
        list_resp = _mock_json_response({"pagination": {"total": 50}})

        with patch("backend.stress_test_tenants.requests.post", return_value=login_resp):
            with patch("backend.stress_test_tenants.requests.get", return_value=list_resp):
                passed, count = st.verify_opportunities_per_tenant("t-5", 5)

        assert passed is True
        assert count == 50

    def test_wrong_count_fails(self):
        import backend.stress_test_tenants as st

        st.ADMIN_TOKEN = "tok"
        login_resp = _mock_json_response({"access_token": "user-tok"}, 200)
        list_resp = _mock_json_response({"pagination": {"total": 30}})

        with patch("backend.stress_test_tenants.requests.post", return_value=login_resp):
            with patch("backend.stress_test_tenants.requests.get", return_value=list_resp):
                passed, count = st.verify_opportunities_per_tenant("t-5", 5)

        assert passed is False

    def test_login_failure_returns_false(self):
        import backend.stress_test_tenants as st

        st.ADMIN_TOKEN = "tok"
        login_resp = _mock_json_response({}, 401)
        login_resp.text = "Unauthorized"

        with patch("backend.stress_test_tenants.requests.post", return_value=login_resp):
            passed, result = st.verify_opportunities_per_tenant("t-5", 5)

        assert passed is False


# ────────────────────── verify_isolation ─────────────────────────────────────


class TestVerifyIsolation:
    def test_isolation_passes_when_no_cross_tenant_data(self):
        import backend.stress_test_tenants as st

        st.ADMIN_TOKEN = "tok"
        login_resp = _mock_json_response({"access_token": "user-tok"}, 200)
        # Return opps from tenant-15 only (no tenant-7 items)
        list_resp = _mock_json_response({"data": [{"tenant_id": "t-15", "id": "o1"}]})

        with patch("backend.stress_test_tenants.requests.post", return_value=login_resp):
            with patch("backend.stress_test_tenants.requests.get", return_value=list_resp):
                result = st.verify_isolation("t-7", "t-15")

        assert result["passed"] is True

    def test_isolation_fails_when_cross_tenant_data_visible(self):
        import backend.stress_test_tenants as st

        st.ADMIN_TOKEN = "tok"
        login_resp = _mock_json_response({"access_token": "user-tok"}, 200)
        # Include a tenant-7 opportunity (LEAK!)
        list_resp = _mock_json_response({
            "data": [
                {"tenant_id": "t-7", "id": "leaked"},
                {"tenant_id": "t-15", "id": "own"},
            ]
        })

        with patch("backend.stress_test_tenants.requests.post", return_value=login_resp):
            with patch("backend.stress_test_tenants.requests.get", return_value=list_resp):
                result = st.verify_isolation("t-7", "t-15")

        assert result["passed"] is False


# ────────────────────── measure_list_performance ─────────────────────────────


class TestMeasureListPerformance:
    def test_fast_response_passes(self):
        import backend.stress_test_tenants as st

        st.ADMIN_TOKEN = "tok"
        login_resp = _mock_json_response({"access_token": "user-tok"}, 200)
        list_resp = _mock_json_response({"data": []})

        with patch("backend.stress_test_tenants.requests.post", return_value=login_resp):
            with patch("backend.stress_test_tenants.requests.get", return_value=list_resp):
                result = st.measure_list_performance("t-15", 15)

        assert result["passed"] is True  # Mock is always fast
        assert "elapsed_ms" in result


# ────────────────────── cleanup ──────────────────────────────────────────────


class TestCleanup:
    def test_cleanup_deletes_scale_test_tenants(self):
        import backend.stress_test_tenants as st

        st.ADMIN_TOKEN = "tok"

        tenants_resp = _mock_json_response({
            "data": [
                {"id": "t-001", "slug": "scale-test-1"},
                {"id": "t-002", "slug": "other-tenant"},  # Should NOT be deleted
            ]
        })
        users_resp = _mock_json_response({"data": []})
        opps_resp = _mock_json_response({"data": []})
        delete_resp = _mock_json_response({}, 200)

        with patch("backend.stress_test_tenants.requests.get",
                   side_effect=[tenants_resp, users_resp, opps_resp]):
            with patch("backend.stress_test_tenants.requests.delete", return_value=delete_resp) as mock_delete:
                count = st.cleanup()

        # Only scale-test-1 should be deleted
        assert count == 1
