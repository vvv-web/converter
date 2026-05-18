import os
import time
import uuid
from decimal import Decimal
from io import BytesIO

import requests
from openpyxl import load_workbook


KEYCLOAK_URL = os.environ.get("KEYCLOAK_URL", "http://keycloak:8080").rstrip("/")
KEYCLOAK_REALM = os.environ.get("KEYCLOAK_REALM", "uom")
KEYCLOAK_CLIENT_ID = os.environ.get("KEYCLOAK_CLIENT_ID", "uom-cli")
SEED_PASSWORD = os.environ["SEED_PASSWORD"]

NSI_URL = os.environ.get("NSI_URL", "http://nsi:8000").rstrip("/")
DOCUMENTS_URL = os.environ.get("DOCUMENTS_URL", "http://documents:8000").rstrip("/")


def _wait_until(fn, timeout_s: int = 90, interval_s: float = 1.0, err: str = "timeout"):
    deadline = time.time() + timeout_s
    last_exc = None
    while time.time() < deadline:
        try:
            v = fn()
            if v:
                return v
        except Exception as e:
            last_exc = e
        time.sleep(interval_s)
    if last_exc:
        raise RuntimeError(f"{err}: last error: {last_exc}") from last_exc
    raise RuntimeError(err)


def _token(username: str, password: str) -> str:
    def _call():
        r = requests.post(
            f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": KEYCLOAK_CLIENT_ID,
                "username": username,
                "password": password,
            },
            timeout=10,
        )
        if r.status_code != 200:
            return None
        return r.json().get("access_token")

    return _wait_until(_call, err=f"failed to get token for {username}")


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _get_json(url: str, token: str):
    r = requests.get(url, headers=_h(token), timeout=20)
    r.raise_for_status()
    return r.json()


def _post_json(url: str, token: str, payload: dict):
    r = requests.post(url, headers={**_h(token), "Content-Type": "application/json"}, json=payload, timeout=20)
    r.raise_for_status()
    return r.json()


def _ensure_uom(token: str, code: str, name: str, category_id: int, factor_to_base: str, precision: int) -> int:
    uoms = _get_json(f"{NSI_URL}/api/v1/uoms/", token)
    for u in uoms:
        if u["code"] == code:
            return int(u["id"])
    created = _post_json(
        f"{NSI_URL}/api/v1/uoms/",
        token,
        {
            "code": code,
            "name": name,
            "category": category_id,
            "factor_to_base": factor_to_base,
            "precision": precision,
        },
    )
    return int(created["id"])


def _ensure_item_category(token: str, name: str, default_uom_id: int) -> int:
    cats = _get_json(f"{NSI_URL}/api/v1/item-categories/", token)
    for c in cats:
        if c["name"] == name:
            return int(c["id"])
    created = _post_json(
        f"{NSI_URL}/api/v1/item-categories/",
        token,
        {
            "name": name,
            "default_uom": default_uom_id,
            "is_active": True,
        },
    )
    return int(created["id"])


def _select_seed_items(token: str):
    rows = _get_json(f"{NSI_URL}/api/v1/items/", token)
    by_sku = {str(x.get("sku")): x for x in rows}
    return {
        "bulk": by_sku["BULK-CRUSH-M800-20-40-001"],
        "bolt": by_sku["FAST-BOLT-20X60-DIN933-001"],
        "nut": by_sku["FAST-NUT-M16-DIN934-001"],
    }


def _wait_invoice_status(token: str, invoice_id: int, want: str, timeout_s: int = 120) -> dict:
    def _poll():
        inv = _get_json(f"{DOCUMENTS_URL}/api/v1/invoices/{invoice_id}/", token)
        st = inv["status"]
        if st == "failed":
            raise RuntimeError(f"invoice failed: {inv.get('error')}")
        return inv if st == want else None

    return _wait_until(_poll, timeout_s=timeout_s, interval_s=1.0, err=f"invoice {invoice_id} did not reach {want}")


def _dec(s: str) -> Decimal:
    return Decimal(str(s))


def test_invoice_calculate_and_generate_e2e():
    # Wait basic readiness
    _wait_until(lambda: requests.get(f"{NSI_URL}/healthz", timeout=5).status_code == 200, err="NSI not ready")
    _wait_until(lambda: requests.get(f"{DOCUMENTS_URL}/healthz", timeout=5).status_code == 200, err="Documents not ready")

    operator_token = _token("operator", SEED_PASSWORD)
    # Seed resets the operator password from env and keeps service-account roles in Keycloak.
    # Use operator for end-to-end document flow.
    clerk_token = operator_token

    # 1) Use seeded NSI items (do not create E2E items)
    items = _select_seed_items(operator_token)

    # 2) Create invoice via documents (clerk - no conversion roles)
    inv = _post_json(
        f"{DOCUMENTS_URL}/api/v1/invoices/",
        clerk_token,
        {
            "number": f"INV-E2E-{uuid.uuid4().hex[:6]}",
            "supplier": "ACME",
            "doc_date": "2026-03-03",
            "lines": [
                {"line_no": 1, "item_id": int(items["bulk"]["id"]), "qty": "1.5", "uom_code": "TON", "context": {"item_name": str(items["bulk"]["name"])}},
                {"line_no": 2, "item_id": int(items["bolt"]["id"]), "qty": "10", "uom_code": "PCS", "context": {"item_name": str(items["bolt"]["name"])}},
                {"line_no": 3, "item_id": int(items["nut"]["id"]), "qty": "100", "uom_code": "PCS", "context": {"item_name": str(items["nut"]["name"])}},
            ],
        },
    )
    invoice_id = int(inv["id"])

    # 3) Calculate
    r = requests.post(f"{DOCUMENTS_URL}/api/v1/invoices/{invoice_id}/calculate/", headers=_h(clerk_token), timeout=20)
    r.raise_for_status()

    inv_calc = _wait_invoice_status(clerk_token, invoice_id, "calculated", timeout_s=180)

    # Assert converted values line-by-line
    lines = {int(l["line_no"]): l for l in inv_calc["lines"]}

    l1 = lines[1]["converted"]
    assert _dec(l1["posting_qty"]) == Decimal("1.063830")
    assert l1["posting_uom_code"] == "M3"

    l2 = lines[2]["converted"]
    assert _dec(l2["posting_qty"]) == Decimal("2.440000")
    assert l2["posting_uom_code"] == "KG"

    l3 = lines[3]["converted"]
    assert _dec(l3["posting_qty"]) == Decimal("3.330000")
    assert l3["posting_uom_code"] == "KG"

    # 4) Generate outputs
    r = requests.post(f"{DOCUMENTS_URL}/api/v1/invoices/{invoice_id}/generate/", headers=_h(clerk_token), timeout=20)
    r.raise_for_status()

    inv_gen = _wait_invoice_status(clerk_token, invoice_id, "generated", timeout_s=180)

    files = inv_gen.get("files") or []
    assert {f["file_type"] for f in files} == {"xlsx", "pdf"}

    xlsx_url = [f["download_url"] for f in files if f["file_type"] == "xlsx"][0]
    pdf_url = [f["download_url"] for f in files if f["file_type"] == "pdf"][0]

    # Download XLSX and validate key cells
    rx = requests.get(xlsx_url, headers=_h(clerk_token), timeout=60)
    rx.raise_for_status()
    assert "spreadsheetml" in (rx.headers.get("Content-Type") or "")

    wb = load_workbook(BytesIO(rx.content))
    ws = wb.active

    # Header row should be present
    assert ws["A1"].value == "Номер накладной"

    # Find data rows by "Line" in column A starting from row 6
    rows = []
    for r_i in range(6, 20):
        line_no = ws[f"A{r_i}"].value
        if line_no in (1, 2, 3):
            rows.append((line_no, r_i))
    assert {ln for ln, _ in rows} == {1, 2, 3}

    # Posting is "qty + uom" in column E
    r1 = dict(rows)[1]
    r2 = dict(rows)[2]
    r3 = dict(rows)[3]
    assert str(ws[f"E{r1}"].value) == "1.063830 M3"
    assert str(ws[f"E{r2}"].value) == "2.440000 KG"
    assert str(ws[f"E{r3}"].value) == "3.330000 KG"
    assert str(ws[f"F{r1}"].value) == "ok"
    assert str(ws[f"F{r2}"].value) == "ok"
    assert str(ws[f"F{r3}"].value) == "ok"

    # Download PDF and validate it looks like a PDF
    rp = requests.get(pdf_url, headers=_h(clerk_token), timeout=60)
    rp.raise_for_status()
    assert (rp.headers.get("Content-Type") or "").startswith("application/pdf")
    assert rp.content[:4] == b"%PDF"


def test_invoice_supplier_variants_and_target_uom_e2e():
    _wait_until(lambda: requests.get(f"{NSI_URL}/healthz", timeout=5).status_code == 200, err="NSI not ready")
    _wait_until(lambda: requests.get(f"{DOCUMENTS_URL}/healthz", timeout=5).status_code == 200, err="Documents not ready")

    token = _token("operator", SEED_PASSWORD)

    # 1) Load one seeded bulk item.
    items = _get_json(f"{NSI_URL}/api/v1/items/", token)
    by_sku = {str(x.get("sku")): x for x in items}
    bulk_item = by_sku["BULK-CRUSH-M800-20-40-001"]
    item_id = int(bulk_item["id"])

    # 2) Resolve category ids for COUNT <-> MASS rule.
    cats = _get_json(f"{NSI_URL}/api/v1/uom-categories/", token)
    count_cat_id = next(int(c["id"]) for c in cats if str(c.get("code")) == "COUNT")
    mass_cat_id = next(int(c["id"]) for c in cats if str(c.get("code")) == "MASS")

    # 3) Create supplier-specific active rules with unique supplier names.
    suffix = uuid.uuid4().hex[:6]
    supplier_a = f"E2E-SUP-A-{suffix}"
    supplier_b = f"E2E-SUP-B-{suffix}"

    _post_json(
        f"{NSI_URL}/api/v1/rules/",
        token,
        {
            "item": item_id,
            "from_category": count_cat_id,
            "to_category": mass_cat_id,
            "rule_type": "pcs_weight",
            "conditions": {"supplier_code": supplier_a},
            "params": {"kg_per_pc": "40"},
            "priority": 200,
            "status": "active",
        },
    )
    _post_json(
        f"{NSI_URL}/api/v1/rules/",
        token,
        {
            "item": item_id,
            "from_category": count_cat_id,
            "to_category": mass_cat_id,
            "rule_type": "pcs_weight",
            "conditions": {"supplier_code": supplier_b},
            "params": {"kg_per_pc": "55"},
            "priority": 200,
            "status": "active",
        },
    )

    # 4) Create invoice lines as conversion instructions with explicit target UOM.
    inv = _post_json(
        f"{DOCUMENTS_URL}/api/v1/invoices/",
        token,
        {
            "number": f"INV-SUP-{uuid.uuid4().hex[:6]}",
            "supplier": "ACME",
            "doc_date": "2026-04-03",
            "lines": [
                {
                    "line_no": 1,
                    "item_id": item_id,
                    "qty": "2",
                    "uom_code": "BAG",
                    "to_uom_code": "KG",
                    "supplier_code": supplier_a,
                    "context": {"item_name": str(bulk_item["name"])},
                },
                {
                    "line_no": 2,
                    "item_id": item_id,
                    "qty": "2",
                    "uom_code": "BAG",
                    "to_uom_code": "KG",
                    "supplier_code": supplier_b,
                    "context": {"item_name": str(bulk_item["name"])},
                },
            ],
        },
    )
    invoice_id = int(inv["id"])

    # 5) Calculate and verify supplier variants are applied.
    r = requests.post(f"{DOCUMENTS_URL}/api/v1/invoices/{invoice_id}/calculate/", headers=_h(token), timeout=20)
    r.raise_for_status()
    inv_calc = _wait_invoice_status(token, invoice_id, "calculated", timeout_s=180)

    lines = {int(l["line_no"]): l for l in inv_calc["lines"]}
    l1 = lines[1]["converted"]
    l2 = lines[2]["converted"]

    assert _dec(l1["posting_qty"]) == Decimal("80.000000")
    assert l1["posting_uom_code"] == "KG"
    assert _dec(l2["posting_qty"]) == Decimal("110.000000")
    assert l2["posting_uom_code"] == "KG"

    # 6) Recalculate once more (must be allowed and stable).
    r = requests.post(f"{DOCUMENTS_URL}/api/v1/invoices/{invoice_id}/calculate/", headers=_h(token), timeout=20)
    r.raise_for_status()
    inv_calc_2 = _wait_invoice_status(token, invoice_id, "calculated", timeout_s=180)
    lines2 = {int(l["line_no"]): l for l in inv_calc_2["lines"]}
    assert _dec(lines2[1]["converted"]["posting_qty"]) == Decimal("80.000000")
    assert _dec(lines2[2]["converted"]["posting_qty"]) == Decimal("110.000000")
