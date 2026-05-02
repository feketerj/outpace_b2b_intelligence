"""
Regression tests for security findings from production-readiness review.
"""

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from backend.models import TokenData, UserCreate, UserRole, UserUpdate


NOW = datetime.now(timezone.utc).isoformat()


def token(role: UserRole, tenant_id: str | None = "tenant-a") -> TokenData:
    return TokenData(
        user_id=f"{role.value}-user",
        email=f"{role.value}@example.test",
        role=role,
        tenant_id=tenant_id,
    )


class FakeCursor:
    def __init__(self, docs):
        self.docs = docs

    def sort(self, *_args, **_kwargs):
        return self

    def skip(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    async def to_list(self, length=None):
        return self.docs if length is None else self.docs[:length]


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = list(docs or [])
        self.find_one = AsyncMock(side_effect=self._find_one)
        self.insert_one = AsyncMock(side_effect=self._insert_one)
        self.update_one = AsyncMock(side_effect=self._update_one)
        self.update_many = AsyncMock(return_value=SimpleNamespace(modified_count=1))
        self.delete_many = AsyncMock(return_value=SimpleNamespace(deleted_count=1))
        self.count_documents = AsyncMock(return_value=len(self.docs))

    async def _find_one(self, query, *_args, **_kwargs):
        for doc in self.docs:
            if all(doc.get(key) == value for key, value in query.items()):
                return dict(doc)
        return None

    async def _insert_one(self, doc):
        self.docs.append(dict(doc))
        return SimpleNamespace(inserted_id=doc.get("id"))

    async def _update_one(self, query, update, *_args, **_kwargs):
        for doc in self.docs:
            if all(doc.get(key) == value for key, value in query.items()):
                doc.update(update.get("$set", {}))
                return SimpleNamespace(modified_count=1)
        return SimpleNamespace(modified_count=0)

    def find(self, query, *_args, **_kwargs):
        docs = [
            dict(doc)
            for doc in self.docs
            if all(doc.get(key) == value for key, value in query.items())
        ]
        return FakeCursor(docs)


def fake_db(**collections):
    names = (
        "tenants",
        "users",
        "refresh_tokens",
        "opportunities",
        "intelligence",
        "chat_messages",
        "chat_turns",
        "knowledge_snippets",
        "kb_documents",
        "kb_chunks",
        "sync_logs",
        "external_api_usage",
        "tenant_costs",
    )
    db = MagicMock()
    for name in names:
        setattr(db, name, collections.get(name, FakeCollection()))
    db.__getitem__.side_effect = lambda name: getattr(db, name)
    return db


@pytest.mark.asyncio
async def test_public_registration_is_disabled_by_default():
    from backend.routes.auth import register

    db = fake_db()
    user_data = UserCreate(
        email="new-user@example.test",
        full_name="New User",
        password="SecurePass123!",
        role=UserRole.TENANT_USER,
        tenant_id="tenant-a",
    )

    with patch.dict("os.environ", {"ALLOW_PUBLIC_REGISTRATION": ""}, clear=False):
        with patch("backend.routes.auth.get_db", return_value=db):
            with pytest.raises(HTTPException) as exc_info:
                await register.__wrapped__(request=MagicMock(), user_data=user_data)

    assert exc_info.value.status_code == 403
    db.users.insert_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_public_registration_cannot_create_privileged_users_when_enabled():
    from backend.routes.auth import register

    db = fake_db(tenants=FakeCollection([{"id": "tenant-a", "name": "Tenant A"}]))
    user_data = UserCreate(
        email="admin@example.test",
        full_name="Admin User",
        password="SecurePass123!",
        role=UserRole.SUPER_ADMIN,
        tenant_id="tenant-a",
    )

    with patch.dict("os.environ", {"ALLOW_PUBLIC_REGISTRATION": "true"}, clear=False):
        with patch("backend.routes.auth.get_db", return_value=db):
            with pytest.raises(HTTPException) as exc_info:
                await register.__wrapped__(request=MagicMock(), user_data=user_data)

    assert exc_info.value.status_code == 403
    db.users.insert_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_public_registration_requires_tenant_id_when_enabled():
    from backend.routes.auth import register

    db = fake_db()
    user_data = UserCreate(
        email="new-user@example.test",
        full_name="New User",
        password="SecurePass123!",
        role=UserRole.TENANT_USER,
        tenant_id=None,
    )

    with patch.dict("os.environ", {"ALLOW_PUBLIC_REGISTRATION": "true"}, clear=False):
        with patch("backend.routes.auth.get_db", return_value=db):
            with pytest.raises(HTTPException) as exc_info:
                await register.__wrapped__(request=MagicMock(), user_data=user_data)

    assert exc_info.value.status_code == 400
    db.users.insert_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_public_registration_creates_only_tenant_user_when_enabled():
    from backend.routes.auth import register

    db = fake_db(tenants=FakeCollection([{"id": "tenant-a", "name": "Tenant A"}]))
    user_data = UserCreate(
        email="new-user@example.test",
        full_name="New User",
        password="SecurePass123!",
        role=UserRole.TENANT_USER,
        tenant_id="tenant-a",
    )

    with patch.dict("os.environ", {"ALLOW_PUBLIC_REGISTRATION": "true"}, clear=False):
        with patch("backend.routes.auth.get_db", return_value=db):
            created = await register.__wrapped__(request=MagicMock(), user_data=user_data)

    assert created.role == UserRole.TENANT_USER
    inserted = db.users.docs[0]
    assert inserted["role"] == UserRole.TENANT_USER.value
    assert inserted["tenant_id"] == "tenant-a"
    assert "hashed_password" in inserted


@pytest.mark.asyncio
async def test_tenant_admin_cannot_change_user_role():
    from backend.routes.users import update_user

    db = fake_db(users=FakeCollection([{
        "id": "user-2",
        "email": "user2@example.test",
        "full_name": "User Two",
        "role": "tenant_user",
        "tenant_id": "tenant-a",
        "created_at": NOW,
        "updated_at": NOW,
        "last_login": None,
    }]))

    with patch("backend.routes.users.get_db", return_value=db):
        with pytest.raises(HTTPException) as exc_info:
            await update_user(
                "user-2",
                UserUpdate(role=UserRole.TENANT_ADMIN),
                current_user=token(UserRole.TENANT_ADMIN, "tenant-a"),
            )

    assert exc_info.value.status_code == 403
    db.users.update_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_role_change_revokes_existing_refresh_tokens():
    from backend.routes.users import update_user

    db = fake_db(users=FakeCollection([{
        "id": "user-2",
        "email": "user2@example.test",
        "full_name": "User Two",
        "role": "tenant_user",
        "tenant_id": "tenant-a",
        "created_at": NOW,
        "updated_at": NOW,
        "last_login": None,
    }]))

    with patch("backend.routes.users.get_db", return_value=db):
        updated = await update_user(
            "user-2",
            UserUpdate(role=UserRole.TENANT_ADMIN),
            current_user=token(UserRole.SUPER_ADMIN, None),
        )

    assert updated.role == UserRole.TENANT_ADMIN
    db.refresh_tokens.update_many.assert_awaited_once()


@pytest.mark.asyncio
async def test_tenant_user_cannot_export_tenant_data():
    from backend.routes.tenants import export_tenant_data

    db = fake_db(tenants=FakeCollection([{"id": "tenant-a", "name": "Tenant A", "slug": "tenant-a"}]))

    with patch("backend.routes.tenants.get_db", return_value=db):
        with pytest.raises(HTTPException) as exc_info:
            await export_tenant_data(
                "tenant-a",
                current_user=token(UserRole.TENANT_USER, "tenant-a"),
            )

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_tenant_export_redacts_sensitive_fields():
    from backend.routes.tenants import export_tenant_data

    db = fake_db(
        tenants=FakeCollection([{
            "id": "tenant-a",
            "name": "Tenant A",
            "slug": "tenant-a",
            "search_profile": {"highergov_api_key": "hg-secret"},
        }]),
        users=FakeCollection([{
            "id": "user-1",
            "tenant_id": "tenant-a",
            "email": "user1@example.test",
            "hashed_password": "hash-secret",
        }]),
    )

    with patch("backend.routes.tenants.get_db", return_value=db):
        response = await export_tenant_data(
            "tenant-a",
            current_user=token(UserRole.TENANT_ADMIN, "tenant-a"),
        )

    body = b"".join([chunk async for chunk in response.body_iterator])
    payload = json.loads(body.decode("utf-8"))

    assert payload["tenant"]["search_profile"]["highergov_api_key"] == "[REDACTED]"
    assert payload["users"][0]["hashed_password"] == "[REDACTED]"


@pytest.mark.asyncio
async def test_tenant_admin_cannot_read_other_tenant():
    from backend.routes.tenants import get_tenant

    db = fake_db(tenants=FakeCollection([{
        "id": "tenant-b",
        "name": "Tenant B",
        "slug": "tenant-b",
        "created_at": NOW,
        "updated_at": NOW,
    }]))

    with patch("backend.routes.tenants.get_db", return_value=db):
        with pytest.raises(HTTPException) as exc_info:
            await get_tenant("tenant-b", current_user=token(UserRole.TENANT_ADMIN, "tenant-a"))

    assert exc_info.value.status_code == 403
    db.tenants.find_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_cached_intelligence_config_still_checks_tenant_access_first():
    from backend.routes.config import _tenant_config_cache, get_intelligence_config

    _tenant_config_cache.clear()
    _tenant_config_cache["tenant-a:intelligence_config"] = {
        "tenant_id": "tenant-a",
        "tenant_name": "Tenant A",
        "intelligence_config": {"enabled": True},
    }

    with pytest.raises(HTTPException) as exc_info:
        await get_intelligence_config(
            "tenant-a",
            current_user=token(UserRole.TENANT_ADMIN, "tenant-b"),
        )

    assert exc_info.value.status_code == 403
