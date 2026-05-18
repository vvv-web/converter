import os
import ssl
from dataclasses import dataclass

import urllib3
from minio import Minio


def get_bucket() -> str:
    return os.environ.get("MINIO_BUCKET", "documents")


def _access_key() -> str:
    return os.environ.get("MINIO_ACCESS_KEY", os.environ.get("MINIO_ROOT_USER", "minio"))


def _secret_key() -> str:
    value = os.environ.get("MINIO_SECRET_KEY") or os.environ.get("MINIO_ROOT_PASSWORD")
    if value:
        return value
    raise RuntimeError("MINIO_SECRET_KEY or MINIO_ROOT_PASSWORD must be set")


def build_minio_http_client(ca_cert_path: str | None) -> urllib3.PoolManager | None:
    if not ca_cert_path:
        return None

    return urllib3.PoolManager(
        cert_reqs=ssl.CERT_REQUIRED,
        ca_certs=ca_cert_path,
    )


def create_minio_client(endpoint: str, secure: bool, ca_cert_path: str | None) -> Minio:
    kwargs = {
        "access_key": _access_key(),
        "secret_key": _secret_key(),
        "secure": secure,
        "cert_check": secure,
    }
    if secure:
        http_client = build_minio_http_client(ca_cert_path)
        if http_client is not None:
            kwargs["http_client"] = http_client
    return Minio(endpoint, **kwargs)


def get_minio_client() -> Minio:
    # MinIO python client ждёт endpoint БЕЗ схемы: "minio:9000"
    endpoint = os.environ.get("MINIO_ENDPOINT", "minio:9000")
    secure = os.environ.get("MINIO_SECURE", "0") == "1"
    ca_cert_path = os.environ.get("MINIO_CA_CERT_PATH")
    return create_minio_client(endpoint, secure=secure, ca_cert_path=ca_cert_path)


def _looks_like_host_browser(host: str) -> bool:
    # host could be "localhost:8002"
    h = host.split(":")[0].strip().lower()
    return h in {"localhost", "127.0.0.1"} or h.endswith(".localhost")


def get_minio_presign_client(request_host: str | None = None) -> Minio:
    """Return MinIO client configured for presigned URLs.

    Goal:
      - if request comes from browser hitting Documents via localhost -> sign URLs for localhost:9000
      - if request comes from inside docker (host like 'documents') -> sign URLs for minio:9000
    """
    public_endpoint = os.environ.get("MINIO_PUBLIC_ENDPOINT") or "localhost:9000"
    internal_endpoint = os.environ.get("MINIO_INTERNAL_ENDPOINT") or os.environ.get("MINIO_ENDPOINT") or "minio:9000"

    if request_host and not _looks_like_host_browser(request_host):
        endpoint = internal_endpoint
    else:
        endpoint = public_endpoint

    secure = os.environ.get("MINIO_PUBLIC_SECURE", os.environ.get("MINIO_SECURE", "0")) == "1"
    ca_cert_path = os.environ.get("MINIO_CA_CERT_PATH")
    return create_minio_client(endpoint, secure=secure, ca_cert_path=ca_cert_path)


def ensure_bucket(client: Minio, bucket: str) -> None:
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)


@dataclass
class MinioStream:
    """File-like wrapper to make sure urllib3 connection is released."""
    resp: object

    def read(self, *args, **kwargs):
        return self.resp.read(*args, **kwargs)

    def close(self):
        try:
            self.resp.close()
        finally:
            try:
                self.resp.release_conn()
            except Exception:
                pass
