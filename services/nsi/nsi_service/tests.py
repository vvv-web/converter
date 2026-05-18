from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase
from django.urls import Resolver404, resolve

from apps.authn.keycloak_admin import KeycloakAdminError, KeycloakAdminClient


class OpenApiPublicFlagTests(SimpleTestCase):
    def test_openapi_routes_are_not_registered_by_default(self):
        self.assertFalse(settings.OPENAPI_PUBLIC_ENABLED)

        for path in ("/api/schema/", "/api/docs/"):
            with self.assertRaises(Resolver404):
                resolve(path)


class KeycloakAdminClientConfigTests(SimpleTestCase):
    @patch.dict("os.environ", {}, clear=True)
    def test_admin_password_must_come_from_env(self):
        with self.assertRaises(KeycloakAdminError):
            KeycloakAdminClient()
