import os
from dataclasses import dataclass

from minio import Minio


def get_bucket() -> str:
    return os.environ.get("MINIO_BUCKET", "documents")


def _access_key() -> str:
    return os.environ.get("MINIO_ACCESS_KEY", os.environ.get("MINIO_ROOT_USER", "minio"))


def _secret_key() -> str:
    return os.environ.get("MINIO_SECRET_KEY", os.environ.get("MINIO_ROOT_PASSWORD", "minio12345"))


def get_minio_client() -> Minio:
    # MinIO python client ждёт endpoint БЕЗ схемы: "minio:9000"
    endpoint = os.environ.get("MINIO_ENDPOINT", "minio:9000")
    secure = os.environ.get("MINIO_SECURE", "0") == "1"
    return Minio(endpoint, access_key=_access_key(), secret_key=_secret_key(), secure=secure, cert_check=False)


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
    return Minio(endpoint, access_key=_access_key(), secret_key=_secret_key(), secure=secure, cert_check=False)


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
