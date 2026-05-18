#!/usr/bin/env python3
"""Validate rendered VPS Compose config without reading server secrets."""

from __future__ import annotations

import json
import sys
from pathlib import Path


EXPECTED_HOST = "converter.acom-offer-desk.ru"
# docker-compose.vps.yml добавляет имена Docker-сервисов для HTTP-проб dephealth/uniproxy (Go net/http шлёт Host из URL).
EXPECTED_DJANGO_ALLOWED_HOSTS = (
    "converter.acom-offer-desk.ru,nsi,documents,localhost,127.0.0.1"
)
OPENAPI_SERVICES = ("nsi", "documents")
PINNED_IMAGE_SERVICES = ("rabbitmq", "minio", "keycloak_db", "keycloak", "nsi_db", "documents_db")
EXPECTED_SERVICE_NETWORKS = {
    "rabbitmq": {"converter_backend"},
    "minio": {"converter_backend"},
    "keycloak_db": {"converter_db"},
    "keycloak": {"converter_frontend", "converter_backend", "converter_db"},
    "nsi_db": {"converter_db"},
    "documents_db": {"converter_db"},
    "nsi": {"converter_frontend", "converter_backend", "converter_db"},
    "documents": {"converter_frontend", "converter_backend", "converter_db"},
    "documents_worker": {"converter_backend", "converter_db"},
    "conversion": {"converter_frontend", "converter_backend"},
    "seed": {"converter_backend"},
}


def fail(message: str) -> None:
    print(f"::error::{message}")
    raise SystemExit(1)


def load_env_example(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def service_environment(service: dict) -> dict[str, str]:
    env = service.get("environment") or {}
    if isinstance(env, list):
        result = {}
        for item in env:
            key, _, value = str(item).partition("=")
            result[key] = value
        return result
    return {str(key): str(value) for key, value in env.items()}


def command_text(service: dict) -> str:
    command = service.get("command", "")
    if isinstance(command, list):
        return " ".join(str(part) for part in command)
    return str(command)


def assert_loopback_ports(name: str, service: dict) -> None:
    for port in service.get("ports") or []:
        published_ip = str(port.get("host_ip") or "")
        target = port.get("target")
        published = port.get("published")
        if published_ip != "127.0.0.1":
            fail(f"{name} publishes {published}:{target} on {published_ip or 'all interfaces'}, expected 127.0.0.1")


def service_networks(service: dict) -> set[str]:
    networks = service.get("networks") or {}
    if isinstance(networks, list):
        return {str(network) for network in networks}
    return {str(network) for network in networks}


def service_volumes(service: dict) -> list[str]:
    result: list[str] = []
    for volume in service.get("volumes") or []:
        if isinstance(volume, str):
            result.append(volume)
            continue
        source = str(volume.get("source") or "")
        target = str(volume.get("target") or "")
        read_only = volume.get("read_only")
        suffix = ":ro" if read_only else ""
        result.append(f"{source}:{target}{suffix}")
    return result


def has_read_only_mount(volumes: list[str], expected_source_suffix: str, expected_target: str) -> bool:
    suffix = f"{expected_target}:ro"
    for volume in volumes:
        if not volume.endswith(suffix):
            continue
        source, _, _ = volume.partition(f":{expected_target}:ro")
        if source == expected_source_suffix or source.endswith(expected_source_suffix.removeprefix("./")):
            return True
    return False


def main() -> None:
    if len(sys.argv) != 3:
        fail("usage: check_vps_compose_security.py <compose-config.json> <deploy/vps/.env.example>")

    config = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    env_example = load_env_example(Path(sys.argv[2]))
    services = config.get("services") or {}

    if env_example.get("CONVERTER_ALLOWED_HOSTS") != EXPECTED_HOST:
        fail("deploy/vps/.env.example must fail closed to the public Converter host only")
    if env_example.get("OPENAPI_PUBLIC_ENABLED") != "0":
        fail("deploy/vps/.env.example must keep OPENAPI_PUBLIC_ENABLED=0")
    if env_example.get("CONVERTER_POSTGRES_TLS_ENABLED") != "on":
        fail("deploy/vps/.env.example must keep PostgreSQL TLS enabled by default in security branch")
    if env_example.get("KC_DB_TLS_MODE") != "verify-server":
        fail("deploy/vps/.env.example must keep KC_DB_TLS_MODE=verify-server")
    for key in ("NSI_DATABASE_URL", "DOCUMENTS_DATABASE_URL"):
        value = env_example.get(key, "")
        if "sslmode=verify-full" not in value or "sslrootcert=/etc/postgresql/tls/root.crt" not in value:
            fail(f"{key} must require verify-full and /etc/postgresql/tls/root.crt in deploy/vps/.env.example")
    if env_example.get("MINIO_CA_CERT_PATH") != "/etc/minio/certs/CAs/public.crt":
        fail("deploy/vps/.env.example must declare MINIO_CA_CERT_PATH for internal TLS verification")
    for key in ("CELERY_BROKER_SSL_CA_CERT", "CELERY_BROKER_SSL_CERTFILE", "CELERY_BROKER_SSL_KEYFILE"):
        if not env_example.get(key):
            fail(f"deploy/vps/.env.example must declare {key}")

    for name, service in services.items():
        image = str(service.get("image") or "")
        if image.endswith(":latest") or ":latest@" in image:
            fail(f"{name} uses mutable latest image: {image}")
        if name in PINNED_IMAGE_SERVICES and "@sha256:" not in image:
            fail(f"{name} image must be pinned by digest: {image}")
        if "start-dev" in command_text(service):
            fail(f"{name} still uses Keycloak/dev command pattern")
        assert_loopback_ports(name, service)

    for name, expected_networks in EXPECTED_SERVICE_NETWORKS.items():
        actual_networks = service_networks(services.get(name, {}))
        if actual_networks != expected_networks:
            fail(f"{name} networks must be {sorted(expected_networks)}, got {sorted(actual_networks)}")

    keycloak_env = service_environment(services.get("keycloak", {}))
    if keycloak_env.get("KC_HOSTNAME_STRICT") != "true":
        fail("keycloak must set KC_HOSTNAME_STRICT=true in rendered VPS config")
    if keycloak_env.get("KC_PROXY_HEADERS") != "xforwarded":
        fail("keycloak must declare proxy header mode for host Nginx")
    if keycloak_env.get("KC_DB_TLS_MODE") != "verify-server":
        fail("keycloak must use verify-server for PostgreSQL TLS in rendered VPS config")

    for name in OPENAPI_SERVICES:
        env = service_environment(services.get(name, {}))
        if env.get("ALLOWED_HOSTS") != EXPECTED_DJANGO_ALLOWED_HOSTS:
            fail(
                f"{name} ALLOWED_HOSTS must render to {EXPECTED_DJANGO_ALLOWED_HOSTS}"
            )
        if env.get("OPENAPI_PUBLIC_ENABLED") != "0":
            fail(f"{name} must render OPENAPI_PUBLIC_ENABLED=0")
        if "sslmode=verify-full" not in env.get("DATABASE_URL", ""):
            fail(f"{name} DATABASE_URL must enforce sslmode=verify-full")
        if "sslrootcert=/etc/postgresql/tls/root.crt" not in env.get("DATABASE_URL", ""):
            fail(f"{name} DATABASE_URL must trust /etc/postgresql/tls/root.crt")

    worker_env = service_environment(services.get("documents_worker", {}))
    if worker_env.get("ALLOWED_HOSTS") != EXPECTED_DJANGO_ALLOWED_HOSTS:
        fail(
            "documents_worker ALLOWED_HOSTS must match Django VPS list "
            f"({EXPECTED_DJANGO_ALLOWED_HOSTS})"
        )
    if "sslmode=verify-full" not in worker_env.get("DATABASE_URL", ""):
        fail("documents_worker DATABASE_URL must enforce sslmode=verify-full")
    if "sslrootcert=/etc/postgresql/tls/root.crt" not in worker_env.get("DATABASE_URL", ""):
        fail("documents_worker DATABASE_URL must trust /etc/postgresql/tls/root.crt")

    for svc_name in ("documents", "documents_worker"):
        svc = services.get(svc_name, {})
        env = service_environment(svc)
        broker = env.get("CELERY_BROKER_URL", "")
        if "guest:guest" in broker:
            fail(f"{svc_name} CELERY_BROKER_URL must not use default guest:guest")
        if not broker.startswith("amqps://"):
            fail(f"{svc_name} must use amqps:// for RabbitMQ in rendered VPS config")
        for key in ("CELERY_BROKER_SSL_CA_CERT", "CELERY_BROKER_SSL_CERTFILE", "CELERY_BROKER_SSL_KEYFILE"):
            if not env.get(key):
                fail(f"{svc_name} must set {key} in rendered VPS config")
        if env.get("MINIO_CA_CERT_PATH") != "/etc/minio/certs/CAs/public.crt":
            fail(f"{svc_name} must set MINIO_CA_CERT_PATH=/etc/minio/certs/CAs/public.crt")
        volumes = service_volumes(svc)
        for expected_source, expected_target in (
            ("./deploy/vps/postgres-tls", "/etc/postgresql/tls"),
            ("./deploy/vps/tls/rabbitmq/ca_certificate.pem", "/etc/rabbitmq/tls/ca_certificate.pem"),
            ("./deploy/vps/tls/rabbitmq/client_certificate.pem", "/etc/rabbitmq/tls/client_certificate.pem"),
            ("./deploy/vps/tls/rabbitmq/client_key.pem", "/etc/rabbitmq/tls/client_key.pem"),
            ("./deploy/vps/tls/minio/public.crt", "/etc/minio/certs/CAs/public.crt"),
        ):
            if not has_read_only_mount(volumes, expected_source, expected_target):
                fail(f"{svc_name} must mount {expected_source}:{expected_target}:ro")

    rabbit_env = service_environment(services.get("rabbitmq", {}))
    if not rabbit_env.get("RABBITMQ_DEFAULT_USER"):
        fail("rabbitmq must set RABBITMQ_DEFAULT_USER in rendered config")
    if rabbit_env.get("RABBITMQ_SSL_OPTIONS__VERIFY") != "verify_peer":
        fail("rabbitmq must enable peer verification on the TLS listener")
    if rabbit_env.get("RABBITMQ_SSL_OPTIONS__FAIL_IF_NO_PEER_CERT") != "true":
        fail("rabbitmq must require client certificates on the TLS listener")
    rabbit_ports = {
        (str(port.get("host_ip") or ""), str(port.get("published")), str(port.get("target")))
        for port in services.get("rabbitmq", {}).get("ports") or []
    }
    if ("127.0.0.1", "25672", "5672") in rabbit_ports:
        fail("rabbitmq must not publish plaintext AMQP port 5672 in VPS config")

    print("OK: rendered VPS Compose config and env example satisfy SB invariants.")


if __name__ == "__main__":
    main()
