#!/usr/bin/env python3
"""Validate rendered VPS Compose config without reading server secrets."""

from __future__ import annotations

import json
import sys
from pathlib import Path


EXPECTED_HOST = "converter.acom-offer-desk.ru"
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

    for name in OPENAPI_SERVICES:
        env = service_environment(services.get(name, {}))
        if env.get("ALLOWED_HOSTS") != EXPECTED_HOST:
            fail(f"{name} ALLOWED_HOSTS must render to {EXPECTED_HOST}")
        if env.get("OPENAPI_PUBLIC_ENABLED") != "0":
            fail(f"{name} must render OPENAPI_PUBLIC_ENABLED=0")

    worker_env = service_environment(services.get("documents_worker", {}))
    if worker_env.get("ALLOWED_HOSTS") != EXPECTED_HOST:
        fail("documents_worker ALLOWED_HOSTS must render to the public Converter host only")

    for svc_name in ("documents", "documents_worker"):
        broker = service_environment(services.get(svc_name, {})).get("CELERY_BROKER_URL", "")
        if "guest:guest" in broker:
            fail(f"{svc_name} CELERY_BROKER_URL must not use default guest:guest")

    rabbit_env = service_environment(services.get("rabbitmq", {}))
    if not rabbit_env.get("RABBITMQ_DEFAULT_USER"):
        fail("rabbitmq must set RABBITMQ_DEFAULT_USER in rendered config")

    print("OK: rendered VPS Compose config and env example satisfy SB invariants.")


if __name__ == "__main__":
    main()
