from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import requests


class KeycloakAdminError(RuntimeError):
    pass


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if value:
        return value
    raise KeycloakAdminError(f"{name} must be set")


@dataclass
class _TokenState:
    token: str = ""
    expires_at: float = 0.0


class KeycloakAdminClient:
    def __init__(self):
        self.base_url = os.environ.get("KEYCLOAK_ADMIN_BASE_URL", "http://keycloak:8080").rstrip("/")
        self.realm = os.environ.get("KEYCLOAK_ADMIN_REALM", "uom")
        self.admin_realm = os.environ.get("KEYCLOAK_ADMIN_AUTH_REALM", "master")
        self.client_id = os.environ.get("KEYCLOAK_ADMIN_CLIENT_ID", "admin-cli")
        self.username = os.environ.get("KEYCLOAK_ADMIN_USERNAME", os.environ.get("KEYCLOAK_ADMIN", "admin"))
        self.password = _require_env("KEYCLOAK_ADMIN_PASSWORD")
        self.timeout = float(os.environ.get("KEYCLOAK_ADMIN_TIMEOUT", "20"))
        self._token = _TokenState()

    def _token_url(self) -> str:
        return f"{self.base_url}/realms/{self.admin_realm}/protocol/openid-connect/token"

    def _admin_api_url(self, path: str) -> str:
        return f"{self.base_url}/admin/realms/{self.realm}/{path.lstrip('/')}"

    def _ensure_token(self) -> str:
        now = time.time()
        if self._token.token and now < self._token.expires_at - 15:
            return self._token.token

        resp = requests.post(
            self._token_url(),
            data={
                "grant_type": "password",
                "client_id": self.client_id,
                "username": self.username,
                "password": self.password,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=self.timeout,
        )
        if resp.status_code >= 400:
            raise KeycloakAdminError(f"Token request failed: {resp.status_code} {resp.text[:300]}")

        body = resp.json()
        token = body.get("access_token")
        expires_in = int(body.get("expires_in") or 60)
        if not token:
            raise KeycloakAdminError("Token response has no access_token")

        self._token = _TokenState(token=token, expires_at=now + expires_in)
        return token

    def _request(self, method: str, path: str, json: Any | None = None, expected: tuple[int, ...] = (200,)) -> requests.Response:
        token = self._ensure_token()
        resp = requests.request(
            method=method,
            url=self._admin_api_url(path),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=json,
            timeout=self.timeout,
        )
        if resp.status_code not in expected:
            raise KeycloakAdminError(f"{method} {path} failed: {resp.status_code} {resp.text[:400]}")
        return resp

    def list_roles(self) -> list[dict]:
        resp = self._request("GET", "roles?max=2000")
        return resp.json() or []

    def get_role(self, name: str) -> dict:
        resp = self._request("GET", f"roles/{name}")
        return resp.json() or {}

    def get_role_composites(self, name: str) -> list[dict]:
        resp = self._request("GET", f"roles/{name}/composites")
        return resp.json() or []

    def create_role(self, name: str, description: str = "", attributes: dict[str, list[str]] | None = None) -> None:
        payload = {
            "name": name,
            "description": description or "",
            "composite": False,
        }
        if attributes:
            payload["attributes"] = attributes
        self._request("POST", "roles", json=payload, expected=(201, 204))

    def set_role_composites(self, role_name: str, includes: list[str]) -> None:
        role = self.get_role(role_name)
        current = self.get_role_composites(role_name)
        if current:
            self._request("DELETE", f"roles/{role_name}/composites", json=current, expected=(204,))

        if not includes:
            return

        all_roles = {r["name"]: r for r in self.list_roles() if r.get("name")}
        missing = [n for n in includes if n not in all_roles]
        if missing:
            raise KeycloakAdminError(f"Unknown roles in composite: {', '.join(missing)}")
        payload = [{"id": all_roles[n]["id"], "name": n} for n in includes]
        self._request("POST", f"roles/{role['name']}/composites", json=payload, expected=(204,))

    def list_users(self) -> list[dict]:
        resp = self._request("GET", "users?max=2000")
        return resp.json() or []

    def user_roles(self, user_id: str) -> list[dict]:
        resp = self._request("GET", f"users/{user_id}/role-mappings/realm")
        return resp.json() or []

    def create_user(
        self,
        username: str,
        password: str,
        enabled: bool = True,
        email: str = "",
        first_name: str = "",
        last_name: str = "",
    ) -> str:
        payload = {
            "username": username,
            "enabled": bool(enabled),
            "email": email or "",
            "firstName": first_name or "",
            "lastName": last_name or "",
        }
        resp = self._request("POST", "users", json=payload, expected=(201,))
        location = resp.headers.get("Location", "").strip()
        user_id = location.rsplit("/", 1)[-1] if location else ""
        if not user_id:
            users = [u for u in self.list_users() if u.get("username") == username]
            if not users:
                raise KeycloakAdminError("User created but id cannot be resolved")
            user_id = users[0]["id"]

        self._request(
            "PUT",
            f"users/{user_id}/reset-password",
            json={
                "type": "password",
                "value": password,
                "temporary": False,
            },
            expected=(204,),
        )
        return user_id

    def set_user_roles(self, user_id: str, roles: list[str]) -> None:
        current = self.user_roles(user_id)
        if current:
            self._request("DELETE", f"users/{user_id}/role-mappings/realm", json=current, expected=(204,))

        if not roles:
            return

        all_roles = {r["name"]: r for r in self.list_roles() if r.get("name")}
        missing = [n for n in roles if n not in all_roles]
        if missing:
            raise KeycloakAdminError(f"Unknown roles: {', '.join(missing)}")

        payload = [{"id": all_roles[n]["id"], "name": n} for n in roles]
        self._request("POST", f"users/{user_id}/role-mappings/realm", json=payload, expected=(204,))
