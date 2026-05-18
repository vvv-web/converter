import os
import time
import httpx

KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://keycloak:8080").rstrip("/")
NSI_URL = os.getenv("NSI_URL", "http://nsi:8000").rstrip("/")
DOCS_URL = os.getenv("DOCS_URL", "http://documents:8000").rstrip("/")
USERNAME = os.getenv("SEED_USERNAME", "operator")
PASSWORD = os.environ["SEED_PASSWORD"]
CLIENT_ID = os.getenv("SEED_CLIENT_ID", "uom-cli")
ADMIN_REALM = os.getenv("KEYCLOAK_ADMIN_AUTH_REALM", "master")
ADMIN_USERNAME = os.getenv("KEYCLOAK_ADMIN_USERNAME") or os.getenv("KEYCLOAK_ADMIN", "admin")
ADMIN_PASSWORD = os.environ["KEYCLOAK_ADMIN_PASSWORD"]
ADMIN_APP_USERNAME = os.getenv("ADMIN_APP_USERNAME", "administrator")
ADMIN_APP_PASSWORD = os.getenv("ADMIN_APP_PASSWORD") or ADMIN_PASSWORD
S2S_CLIENT_ID = os.getenv("S2S_CLIENT_ID", "documents-service")
S2S_CLIENT_SECRET = os.environ["S2S_CLIENT_SECRET"]


def wait_http_ok(url: str, timeout_s: int = 240) -> None:
    deadline = time.time() + timeout_s
    last = None
    while time.time() < deadline:
        try:
            r = httpx.get(url, timeout=5)
            if r.status_code == 200:
                return
            last = f"{r.status_code} {r.text[:200]}"
        except Exception as e:
            last = str(e)
        time.sleep(1)
    raise RuntimeError(f"Service not ready: {url}. Last={last}")


def admin_auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def admin_url(path: str) -> str:
    return f"{KEYCLOAK_URL}/admin/realms/uom/{path.lstrip('/')}"


def get_admin_token() -> str:
    r = httpx.post(
        f"{KEYCLOAK_URL}/realms/{ADMIN_REALM}/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def ensure_user_password(admin_token: str, username: str, password: str) -> None:
    r = httpx.get(
        admin_url("users"),
        params={"username": username, "exact": "true"},
        headers=admin_auth(admin_token),
        timeout=20,
    )
    r.raise_for_status()
    users = r.json()
    user = next((item for item in users if item.get("username") == username), None)
    if not user:
        raise RuntimeError(f"Keycloak realm import must provide user {username!r} before seed runs")
    httpx.put(
        admin_url(f"users/{user['id']}/reset-password"),
        headers=admin_auth(admin_token),
        json={"type": "password", "value": password, "temporary": False},
        timeout=20,
    ).raise_for_status()


def ensure_client_secret(admin_token: str, client_id: str, client_secret: str) -> None:
    r = httpx.get(
        admin_url("clients"),
        params={"clientId": client_id},
        headers=admin_auth(admin_token),
        timeout=20,
    )
    r.raise_for_status()
    clients = r.json()
    client = next((item for item in clients if item.get("clientId") == client_id), None)
    if not client:
        raise RuntimeError(f"Keycloak realm import must provide client {client_id!r} before seed runs")
    client_repr = httpx.get(
        admin_url(f"clients/{client['id']}"),
        headers=admin_auth(admin_token),
        timeout=20,
    )
    client_repr.raise_for_status()
    payload = client_repr.json()
    payload["secret"] = client_secret
    httpx.put(
        admin_url(f"clients/{client['id']}"),
        headers=admin_auth(admin_token),
        json=payload,
        timeout=20,
    ).raise_for_status()


def get_token() -> str:
    r = httpx.post(
        f"{KEYCLOAK_URL}/realms/uom/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": CLIENT_ID,
            "username": USERNAME,
            "password": PASSWORD,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def get_uoms(token: str):
    r = httpx.get(f"{NSI_URL}/api/v1/uoms/", headers=auth(token), timeout=20)
    r.raise_for_status()
    return r.json()


def get_uom_cats(token: str):
    r = httpx.get(f"{NSI_URL}/api/v1/uom-categories/", headers=auth(token), timeout=20)
    r.raise_for_status()
    return r.json()


def ensure_uom(token: str, code: str, name: str, category_id: int, factor_to_base: str, precision: int) -> int:
    r = httpx.get(f"{NSI_URL}/api/v1/uoms/", headers=auth(token), timeout=20)
    r.raise_for_status()
    for u in r.json():
        if u.get("code") == code:
            return u["id"]
    rr = httpx.post(
        f"{NSI_URL}/api/v1/uoms/",
        headers={**auth(token), "Content-Type": "application/json"},
        json={
            "code": code,
            "name": name,
            "category": category_id,
            "factor_to_base": factor_to_base,
            "precision": precision,
        },
        timeout=20,
    )
    rr.raise_for_status()
    return rr.json()["id"]


def ensure_item_category(token: str, name: str, default_uom_id: int) -> int:
    r = httpx.get(f"{NSI_URL}/api/v1/item-categories/", headers=auth(token), timeout=20)
    r.raise_for_status()
    for c in r.json():
        if c.get("name") == name:
            current_default_uom = c.get("default_uom")
            if current_default_uom != default_uom_id:
                httpx.patch(
                    f"{NSI_URL}/api/v1/item-categories/{c['id']}/",
                    headers={**auth(token), "Content-Type": "application/json"},
                    json={"default_uom": default_uom_id},
                    timeout=20,
                ).raise_for_status()
            return c["id"]
    rr = httpx.post(
        f"{NSI_URL}/api/v1/item-categories/",
        headers={**auth(token), "Content-Type": "application/json"},
        json={"name": name, "default_uom": default_uom_id, "is_active": True},
        timeout=20,
    )
    rr.raise_for_status()
    return rr.json()["id"]


def ensure_item(token: str, sku: str, name: str, category_id: int, posting_uom_id: int) -> int:
    r = httpx.get(f"{NSI_URL}/api/v1/items/", headers=auth(token), timeout=20)
    r.raise_for_status()
    for it in r.json():
        if it.get("sku") == sku:
            return it["id"]
    rr = httpx.post(
        f"{NSI_URL}/api/v1/items/",
        headers={**auth(token), "Content-Type": "application/json"},
        json={
            "sku": sku,
            "name": name,
            "category": category_id,
            "is_active": True,
            "policy": {
                "storage_uom": posting_uom_id,
                "posting_uom": posting_uom_id,
                "allow_fractional": True,
                "rounding_precision": 6,
            },
        },
        timeout=20,
    )
    rr.raise_for_status()
    return rr.json()["id"]


def ensure_category_package(token: str, category_id: int, package_uom_id: int, content_uom_id: int, qty: str) -> None:
    r = httpx.get(f"{NSI_URL}/api/v1/category-packages/", headers=auth(token), timeout=20)
    if r.status_code == 404:
        return
    r.raise_for_status()
    for p in r.json():
        if p.get("category") == category_id and p.get("package_uom") == package_uom_id and p.get("content_uom") == content_uom_id:
            return
    rr = httpx.post(
        f"{NSI_URL}/api/v1/category-packages/",
        headers={**auth(token), "Content-Type": "application/json"},
        json={
            "category": category_id,
            "package_uom": package_uom_id,
            "content_uom": content_uom_id,
            "content_qty": qty,
            "status": "active",
            "supplier_code": "",
            "barcode": "",
            "effective_from": None,
            "effective_to": None,
        },
        timeout=20,
    )
    rr.raise_for_status()


def ensure_global_uom_rule(token: str, from_uom_id: int, to_uom_id: int, mult: str) -> None:
    r = httpx.get(f"{NSI_URL}/api/v1/global-uom-rules/", headers=auth(token), timeout=20)
    if r.status_code == 404:
        return
    r.raise_for_status()
    for g in r.json():
        if g.get("from_uom") == from_uom_id and g.get("to_uom") == to_uom_id:
            return
    rr = httpx.post(
        f"{NSI_URL}/api/v1/global-uom-rules/",
        headers={**auth(token), "Content-Type": "application/json"},
        json={"from_uom": from_uom_id, "to_uom": to_uom_id, "multiplier": mult, "status": "active"},
        timeout=20,
    )
    rr.raise_for_status()


def ensure_rule_pcs_weight(token: str, item_id: int, from_cat_id: int, to_cat_id: int, kg_per_pc: str) -> None:
    r = httpx.get(f"{NSI_URL}/api/v1/rules/", headers=auth(token), timeout=20)
    r.raise_for_status()
    pair = {from_cat_id, to_cat_id}
    for rule in r.json():
        if (
            rule.get("item") == item_id
            and rule.get("rule_type") == "pcs_weight"
            and {rule.get("from_category"), rule.get("to_category")} == pair
        ):
            current_kg_per_pc = str((rule.get("params") or {}).get("kg_per_pc", ""))
            if current_kg_per_pc != str(kg_per_pc) or rule.get("status") != "active":
                httpx.put(
                    f"{NSI_URL}/api/v1/rules/{rule['id']}/",
                    headers={**auth(token), "Content-Type": "application/json"},
                    json={
                        "id": rule["id"],
                        "item": item_id,
                        "from_category": from_cat_id,
                        "to_category": to_cat_id,
                        "rule_type": "pcs_weight",
                        "conditions": rule.get("conditions") or {},
                        "params": {"kg_per_pc": kg_per_pc},
                        "priority": rule.get("priority", 0),
                        "status": "active",
                        "effective_from": rule.get("effective_from"),
                        "effective_to": rule.get("effective_to"),
                        "supersedes": rule.get("supersedes"),
                    },
                    timeout=20,
                ).raise_for_status()
            return
    httpx.post(
        f"{NSI_URL}/api/v1/rules/",
        headers={**auth(token), "Content-Type": "application/json"},
        json={
            "item": item_id,
            "from_category": from_cat_id,
            "to_category": to_cat_id,
            "rule_type": "pcs_weight",
            "conditions": {},
            "params": {"kg_per_pc": kg_per_pc},
            "priority": 0,
            "status": "active",
        },
        timeout=20,
    ).raise_for_status()


def ensure_rule_density(token: str, item_id: int, from_cat_id: int, to_cat_id: int, density_kg_per_l: str) -> None:
    r = httpx.get(f"{NSI_URL}/api/v1/rules/", headers=auth(token), timeout=20)
    r.raise_for_status()
    pair = {from_cat_id, to_cat_id}
    for rule in r.json():
        if (
            rule.get("item") == item_id
            and rule.get("rule_type") == "density"
            and {rule.get("from_category"), rule.get("to_category")} == pair
        ):
            current_density = str((rule.get("params") or {}).get("density_kg_per_l", ""))
            if current_density != str(density_kg_per_l) or rule.get("status") != "active":
                httpx.put(
                    f"{NSI_URL}/api/v1/rules/{rule['id']}/",
                    headers={**auth(token), "Content-Type": "application/json"},
                    json={
                        "id": rule["id"],
                        "item": item_id,
                        "from_category": from_cat_id,
                        "to_category": to_cat_id,
                        "rule_type": "density",
                        "conditions": rule.get("conditions") or {},
                        "params": {"density_kg_per_l": density_kg_per_l},
                        "priority": rule.get("priority", 0),
                        "status": "active",
                        "effective_from": rule.get("effective_from"),
                        "effective_to": rule.get("effective_to"),
                        "supersedes": rule.get("supersedes"),
                    },
                    timeout=20,
                ).raise_for_status()
            return

    httpx.post(
        f"{NSI_URL}/api/v1/rules/",
        headers={**auth(token), "Content-Type": "application/json"},
        json={
            "item": item_id,
            "from_category": from_cat_id,
            "to_category": to_cat_id,
            "rule_type": "density",
            "conditions": {},
            "params": {"density_kg_per_l": density_kg_per_l},
            "priority": 0,
            "status": "active",
        },
        timeout=20,
    ).raise_for_status()


def cleanup_legacy_items(token: str, keep_skus: set[str]) -> None:
    r = httpx.get(f"{NSI_URL}/api/v1/items/", headers=auth(token), timeout=20)
    r.raise_for_status()
    legacy_skus = {"PIPE-DEMO-001", "BOLT-DEMO-001", "DEMO-ITEM-001"}
    for it in r.json():
        sku = str(it.get("sku") or "")
        if sku in keep_skus:
            continue
        if sku in legacy_skus or sku.startswith("E2E-") or sku.startswith("E2E_"):
            httpx.delete(f"{NSI_URL}/api/v1/items/{it['id']}/", headers=auth(token), timeout=20).raise_for_status()


def main() -> None:
    wait_http_ok(f"{NSI_URL}/healthz")
    wait_http_ok(f"{DOCS_URL}/healthz")
    wait_http_ok(f"{KEYCLOAK_URL}/realms/uom")

    admin_token = get_admin_token()
    ensure_user_password(admin_token, USERNAME, PASSWORD)
    ensure_user_password(admin_token, ADMIN_APP_USERNAME, ADMIN_APP_PASSWORD)
    ensure_client_secret(admin_token, S2S_CLIENT_ID, S2S_CLIENT_SECRET)

    token = get_token()

    uoms = get_uoms(token)
    uom_by_code = {u["code"]: u for u in uoms}

    cats = get_uom_cats(token)
    cat_by_code = {c["code"]: c for c in cats}

    volume_cat_id = cat_by_code.get("VOLUME", {}).get("id")
    if volume_cat_id and "M3" not in uom_by_code:
        ensure_uom(token, "M3", "Кубический метр", volume_cat_id, "1000", 3)
        uoms = get_uoms(token)
        uom_by_code = {u["code"]: u for u in uoms}

    # global rules examples (will update factor_to_base for from_uom)
    if "CM" in uom_by_code and "M" in uom_by_code:
        ensure_global_uom_rule(token, uom_by_code["CM"]["id"], uom_by_code["M"]["id"], "0.01")
        ensure_global_uom_rule(token, uom_by_code["M"]["id"], uom_by_code["CM"]["id"], "100")
    if "TON" in uom_by_code and "KG" in uom_by_code:
        ensure_global_uom_rule(token, uom_by_code["TON"]["id"], uom_by_code["KG"]["id"], "1000")
        ensure_global_uom_rule(token, uom_by_code["KG"]["id"], uom_by_code["TON"]["id"], "0.001")
    if "M3" in uom_by_code and "L" in uom_by_code:
        ensure_global_uom_rule(token, uom_by_code["M3"]["id"], uom_by_code["L"]["id"], "1000")
        ensure_global_uom_rule(token, uom_by_code["L"]["id"], uom_by_code["M3"]["id"], "0.001")

    # item categories + seeded items
    kg_id = uom_by_code.get("KG", {}).get("id")
    pcs_id = uom_by_code.get("PCS", {}).get("id")
    m3_id = uom_by_code.get("M3", {}).get("id") or uom_by_code.get("L", {}).get("id")
    if not kg_id:
        raise RuntimeError("Missing UoM KG")
    if not m3_id:
        raise RuntimeError("Missing UoM for VOLUME base (expected M3 or L)")
    fast_cat_id = ensure_item_category(token, "Fasteners", kg_id)
    bulk_cat_id = ensure_item_category(token, "Сыпучие стройматериалы", m3_id)

    fastener_items = [
        ("FAST-BOLT-M20X65-GOST7798-001", "Болт M20x65, 8,8, ГОСТ 7798-70 оц.", "0.219"),
        ("FAST-NUT-M16-8.8-ZN-KP8-001", "Гайка M16, 8,8, оцинк КП 8", "0.0333"),
        ("FAST-NUT-M20-8.8-ZN-KP8-KK-001", "Гайка M20, 8,8, оцинк КП 8 KK", "0.0640"),
        ("FAST-WASHER-16-8.8-ZN-M16-DIN125-001", "Шайба 16, 8,8, оц М16 DIN 125", "0.0113"),
        ("FAST-WASHER-20-8.8-ZN-M20-DIN125-KKSR-001", "Шайба 20, 8,8, оц М20 DIN 125 KK/SR", "0.0172"),
        ("FAST-WASHER-LARGE-M16-ZN-DIN9021-001", "Шайба увеличенная М16 ОЦ (25кг) DIN9021 (ГОСТ 6958)", "0.0409"),
        ("FAST-NUT-M16-DIN934-001", "Гайка M16 DIN 934", "0.0333"),
        ("FAST-NUT-M20-DIN934-001", "Гайка M20 DIN 934", "0.0640"),
        ("FAST-WASHER-D16-DIN125-001", "Шайба d16 , DIN 125", "0.0113"),
        ("FAST-WASHER-D20-DIN125-001", "Шайба d20 , DIN 125", "0.0172"),
        ("FAST-BOLT-20X60-DIN933-001", "Болт 20х60 DIN 933", "0.2440"),
        ("FAST-BOLT-16X55-DIN933-001", "Болт 16х55 DIN 933", "0.1122"),
    ]
    bulk_items = [
        ("BULK-CRUSH-M800-20-40-001", "Щебень М 800, фракция 20-40 мм", "1.41"),
        ("BULK-CRUSH-M800-20-40-002", "Щебень М 800, фракция 20-40 мм", "1.41"),
        ("BULK-GRAVEL-5X20-001", "Щебень гравийный 5х20", "1.4"),
        (
            "BULK-DENSE-ROCK-M800-20-40-001",
            "Щебень из плотных горных пород для строительных работ М 800, фракция 20-40 мм",
            "1.45",
        ),
        ("BULK-RIVER-SAND-001", "Песок речной", "1.6"),
        ("BULK-NATURAL-SAND-II-MEDIUM-001", "Песок природный для строительных работ II класс, средний", "1.55"),
    ]
    keep_skus = {sku for sku, _, _ in fastener_items} | {sku for sku, _, _ in bulk_items}
    cleanup_legacy_items(token, keep_skus)

    if pcs_id and kg_id and cat_by_code.get("COUNT") and cat_by_code.get("MASS"):
        for sku, name, kg_per_pc in fastener_items:
            fast_item_id = ensure_item(token, sku, name, fast_cat_id, kg_id)
            ensure_rule_pcs_weight(token, fast_item_id, cat_by_code["COUNT"]["id"], cat_by_code["MASS"]["id"], kg_per_pc)

    for sku, name, density in bulk_items:
        bulk_item_id = ensure_item(token, sku, name, bulk_cat_id, m3_id)
        if cat_by_code.get("MASS") and cat_by_code.get("VOLUME"):
            ensure_rule_density(token, bulk_item_id, cat_by_code["MASS"]["id"], cat_by_code["VOLUME"]["id"], density)

    print("[seed] done")


if __name__ == "__main__":
    main()
