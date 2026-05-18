import ssl
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.test import RequestFactory
from django.test import SimpleTestCase
from django.urls import Resolver404, resolve

from apps.documents_core.serializers import InvoiceFileSerializer
from apps.documents_core.storage import build_minio_http_client
from documents_service.settings import build_celery_broker_ssl_config


class OpenApiPublicFlagTests(SimpleTestCase):
    def test_openapi_routes_are_not_registered_by_default(self):
        self.assertFalse(settings.OPENAPI_PUBLIC_ENABLED)

        for path in ("/api/schema/", "/api/docs/"):
            with self.assertRaises(Resolver404):
                resolve(path)


class BrokerTlsConfigTests(SimpleTestCase):
    @patch.dict(
        "os.environ",
        {
            "CELERY_BROKER_SSL_CA_CERT": "/etc/rabbitmq/tls/ca_certificate.pem",
            "CELERY_BROKER_SSL_CERTFILE": "/etc/rabbitmq/tls/client_certificate.pem",
            "CELERY_BROKER_SSL_KEYFILE": "/etc/rabbitmq/tls/client_key.pem",
        },
        clear=False,
    )
    def test_amqps_uses_certificate_verification(self):
        ssl_config = build_celery_broker_ssl_config("amqps://user:pass@rabbitmq:5671//")

        self.assertEqual(ssl_config["cert_reqs"], ssl.CERT_REQUIRED)
        self.assertEqual(ssl_config["ca_certs"], "/etc/rabbitmq/tls/ca_certificate.pem")
        self.assertEqual(ssl_config["certfile"], "/etc/rabbitmq/tls/client_certificate.pem")
        self.assertEqual(ssl_config["keyfile"], "/etc/rabbitmq/tls/client_key.pem")

    def test_plain_amqp_does_not_enable_ssl_policy(self):
        self.assertIsNone(build_celery_broker_ssl_config("amqp://user:pass@rabbitmq:5672//"))


class MinioTlsConfigTests(SimpleTestCase):
    def test_minio_http_client_requires_ca_validation(self):
        http_client = build_minio_http_client("/etc/minio/certs/CAs/public.crt")

        self.assertEqual(http_client.connection_pool_kw["cert_reqs"], ssl.CERT_REQUIRED)
        self.assertEqual(http_client.connection_pool_kw["ca_certs"], "/etc/minio/certs/CAs/public.crt")

    def test_minio_http_client_is_optional_without_custom_ca(self):
        self.assertIsNone(build_minio_http_client(None))


class InvoiceFileSerializerTests(SimpleTestCase):
    def test_download_url_uses_canonical_trailing_slash(self):
        request = RequestFactory().get("/api/v1/invoices/1/")
        serializer = InvoiceFileSerializer(context={"request": request})

        file_obj = SimpleNamespace(invoice_id=1, id=2)

        self.assertEqual(
            serializer.get_download_url(file_obj),
            "http://testserver/api/v1/invoices/1/files/2/download/",
        )
