"""
GST Billing module for the Inventory dashboard.
Stores invoices in a dedicated `gst_invoices` collection - separate from
sales/orders/accessory_sales, so legacy data is never touched. Auto-generates
an invoice when a NEW sales/accessory entry is created (via internal hook),
and exposes manual `Generate from sale` + full CRUD + cancellation flow.
Access: Admin only.
"""
from fastapi import APIRouter, HTTPException, Depends, Response, Query, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from io import BytesIO
import uuid
import re
import logging

from database import db
from deps import get_current_user, require_admin
from helpers import log_audit, format_inr

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------- Item Master (HSN + GST rate defaults for K3 Gas Service) ----------
DEFAULT_ITEMS = [
    {"name": "Domestic LPG Refill", "hsn": "271119", "unit": "Cylinder", "gst_rate": 5},
    {"name": "Commercial LPG Refill", "hsn": "271119", "unit": "Cylinder", "gst_rate": 18},
    {"name": "Domestic New Connection", "hsn": "271119", "unit": "Cylinder", "gst_rate": 18},
    {"name": "Commercial New Connection", "hsn": "271119", "unit": "Cylinder", "gst_rate": 18},
    {"name": "Empty Cylinder Domestic 15 KG", "hsn": "73110010", "unit": "Nos", "gst_rate": 18},
    {"name": "Empty Cylinder Commercial 21 KG", "hsn": "73110010", "unit": "Nos", "gst_rate": 18},
    {"name": "Domestic Regulator", "hsn": "84812000", "unit": "Nos", "gst_rate": 18},
    {"name": "Commercial Regulator", "hsn": "84812000", "unit": "Nos", "gst_rate": 18},
    {"name": "Hose Pipe", "hsn": "40092100", "unit": "Nos", "gst_rate": 18},
    {"name": "Lighter & Knife", "hsn": "96131000", "unit": "Nos", "gst_rate": 18},
    {"name": "Cooker", "hsn": "73211110", "unit": "Nos", "gst_rate": 18},
    {"name": "Stove Burner", "hsn": "73211210", "unit": "Nos", "gst_rate": 18},
    {"name": "Gas Card", "hsn": "996913", "unit": "Nos", "gst_rate": 12},
    {"name": "Admin Charge", "hsn": "998399", "unit": "Service", "gst_rate": 18},
]


# ---------- Connection Plans (auto-itemize new connection sales) ----------
# Sourced from K3 Gas Service Excel: "new connection plans with items details"
# Unit prices are 0 by default - admin must set them via the UI.
# Naming: plan_type uses domestic_X / commercial_X format.
DEFAULT_PLANS = [
    {
        "name": "New Single Domestic Connection (without Accessories)",
        "plan_type": "domestic_single_basic",
        "connection_type": "domestic",
        "cylinder_count": 1,
        "has_accessories": False,
        "items": [
            {"item_name": "Domestic LPG", "hsn": "271119", "unit": "KG", "quantity": 15, "gst_rate": 5},
            {"item_name": "Empty Cylinder Domestic 15 KG", "hsn": "73110010", "unit": "Nos", "quantity": 1, "gst_rate": 18},
            {"item_name": "Domestic Regulator", "hsn": "84812000", "unit": "Nos", "quantity": 1, "gst_rate": 18},
            {"item_name": "Hose Pipe 1.3 Mtr", "hsn": "40092100", "unit": "Nos", "quantity": 1, "gst_rate": 18},
            {"item_name": "Lighter & Knife", "hsn": "96131000", "unit": "Nos", "quantity": 1, "gst_rate": 18},
            {"item_name": "Cooker 3.5 Ltr", "hsn": "73211110", "unit": "Nos", "quantity": 1, "gst_rate": 18},
            {"item_name": "Gas Card", "hsn": "996913", "unit": "Nos", "quantity": 1, "gst_rate": 12},
            {"item_name": "Admin Charge", "hsn": "998399", "unit": "Package", "quantity": 1, "gst_rate": 18},
        ],
    },
    {
        "name": "New Single Domestic Connection (with Accessories)",
        "plan_type": "domestic_single_full",
        "connection_type": "domestic",
        "cylinder_count": 1,
        "has_accessories": True,
        "items": [
            {"item_name": "Domestic LPG", "hsn": "271119", "unit": "KG", "quantity": 15, "gst_rate": 5},
            {"item_name": "Empty Cylinder Domestic 15 KG", "hsn": "73110010", "unit": "Nos", "quantity": 1, "gst_rate": 18},
            {"item_name": "Domestic Regulator", "hsn": "84812000", "unit": "Nos", "quantity": 1, "gst_rate": 18},
            {"item_name": "Hose Pipe 1.3 Mtr", "hsn": "40092100", "unit": "Nos", "quantity": 1, "gst_rate": 18},
            {"item_name": "Lighter & Knife", "hsn": "96131000", "unit": "Nos", "quantity": 1, "gst_rate": 18},
            {"item_name": "Cooker 3.5 Ltr", "hsn": "73211110", "unit": "Nos", "quantity": 1, "gst_rate": 18},
            {"item_name": "Two Stove Burner", "hsn": "73211210", "unit": "Nos", "quantity": 1, "gst_rate": 18},
            {"item_name": "Gas Card", "hsn": "996913", "unit": "Nos", "quantity": 1, "gst_rate": 12},
            {"item_name": "Admin Charge", "hsn": "998399", "unit": "Package", "quantity": 1, "gst_rate": 18},
        ],
    },
    {
        "name": "New Double Domestic Connection (without Accessories)",
        "plan_type": "domestic_double_basic",
        "connection_type": "domestic",
        "cylinder_count": 2,
        "has_accessories": False,
        "items": [
            {"item_name": "Domestic LPG", "hsn": "271119", "unit": "KG", "quantity": 30, "gst_rate": 5},
            {"item_name": "Empty Cylinder Domestic 15 KG", "hsn": "73110010", "unit": "Nos", "quantity": 2, "gst_rate": 18},
            {"item_name": "Domestic Regulator", "hsn": "84812000", "unit": "Nos", "quantity": 1, "gst_rate": 18},
            {"item_name": "Hose Pipe 1.3 Mtr", "hsn": "40092100", "unit": "Nos", "quantity": 1, "gst_rate": 18},
            {"item_name": "Lighter & Knife", "hsn": "96131000", "unit": "Nos", "quantity": 1, "gst_rate": 18},
            {"item_name": "Cooker 3.5 Ltr", "hsn": "73211110", "unit": "Nos", "quantity": 1, "gst_rate": 18},
            {"item_name": "Gas Card", "hsn": "996913", "unit": "Nos", "quantity": 1, "gst_rate": 12},
            {"item_name": "Admin Charge", "hsn": "998399", "unit": "Package", "quantity": 1, "gst_rate": 18},
        ],
    },
    {
        "name": "New Double Domestic Connection (with Accessories)",
        "plan_type": "domestic_double_full",
        "connection_type": "domestic",
        "cylinder_count": 2,
        "has_accessories": True,
        "items": [
            {"item_name": "Domestic LPG", "hsn": "271119", "unit": "KG", "quantity": 30, "gst_rate": 5},
            {"item_name": "Empty Cylinder Domestic 15 KG", "hsn": "73110010", "unit": "Nos", "quantity": 2, "gst_rate": 18},
            {"item_name": "Domestic Regulator", "hsn": "84812000", "unit": "Nos", "quantity": 1, "gst_rate": 18},
            {"item_name": "Hose Pipe 1.3 Mtr", "hsn": "40092100", "unit": "Nos", "quantity": 1, "gst_rate": 18},
            {"item_name": "Lighter & Knife", "hsn": "96131000", "unit": "Nos", "quantity": 1, "gst_rate": 18},
            {"item_name": "Cooker 3.5 Ltr", "hsn": "73211110", "unit": "Nos", "quantity": 1, "gst_rate": 18},
            {"item_name": "Two Stove Burner", "hsn": "73211210", "unit": "Nos", "quantity": 1, "gst_rate": 18},
            {"item_name": "Gas Card", "hsn": "996913", "unit": "Nos", "quantity": 1, "gst_rate": 12},
            {"item_name": "Admin Charge", "hsn": "998399", "unit": "Package", "quantity": 1, "gst_rate": 18},
        ],
    },
]


def _commercial_plan(name: str, plan_type: str, count: int) -> dict:
    return {
        "name": name,
        "plan_type": plan_type,
        "connection_type": "commercial",
        "cylinder_count": count,
        "has_accessories": False,
        "items": [
            {"item_name": "Commercial LPG", "hsn": "271119", "unit": "KG", "quantity": 21 * count, "gst_rate": 18},
            {"item_name": "Empty Cylinder Commercial 21 KG", "hsn": "73110010", "unit": "Nos", "quantity": count, "gst_rate": 18},
            {"item_name": "Commercial Regulator", "hsn": "84812000", "unit": "Nos", "quantity": 1, "gst_rate": 18},
            {"item_name": "Hose Pipe 1.3 Mtr", "hsn": "40092100", "unit": "Nos", "quantity": 1, "gst_rate": 18},
            {"item_name": "Gas Card", "hsn": "996913", "unit": "Nos", "quantity": 1, "gst_rate": 12},
            {"item_name": "Admin Charge", "hsn": "998399", "unit": "Package", "quantity": 1, "gst_rate": 18},
        ],
    }


DEFAULT_PLANS.extend([
    _commercial_plan("Single Commercial New Connection Plan", "commercial_1", 1),
    _commercial_plan("2 Nos Commercial New Connection Plan", "commercial_2", 2),
    _commercial_plan("3 Nos Commercial New Connection Plan", "commercial_3", 3),
    _commercial_plan("4 Nos Commercial New Connection Plan", "commercial_4", 4),
    _commercial_plan("6 Nos Commercial New Connection Plan", "commercial_6", 6),
    _commercial_plan("10 Nos Commercial New Connection Plan", "commercial_10", 10),
    _commercial_plan("15 Nos Commercial New Connection Plan", "commercial_15", 15),
])


async def ensure_seed():
    """Idempotent: seeds default items + plans + config if missing.
    Also backfills item_id linkage on plan items for the Auto-Sync feature."""
    if await db.gst_items.count_documents({}) == 0:
        await db.gst_items.insert_many([
            {**it, "id": str(uuid.uuid4()), "is_active": True,
             "default_rate": 0,
             "created_at": datetime.now(timezone.utc).isoformat()}
            for it in DEFAULT_ITEMS
        ])
    if await db.gst_plans.count_documents({}) == 0:
        now_iso = datetime.now(timezone.utc).isoformat()
        await db.gst_plans.insert_many([
            {
                **{k: v for k, v in p.items() if k != "items"},
                "id": str(uuid.uuid4()),
                "is_active": True,
                "items": [{**it, "unit_price": 0, "item_id": None} for it in p["items"]],
                "created_at": now_iso,
            }
            for p in DEFAULT_PLANS
        ])

    # Backfill item_id on plan items by matching on item_name (idempotent - skips if already set)
    plans_to_backfill = await db.gst_plans.find({"items.item_id": None}, {"id": 1, "items": 1}).to_list(500)
    if plans_to_backfill:
        all_items = await db.gst_items.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)
        # Map normalized name -> id (case-insensitive, trimmed)
        name_to_id: Dict[str, str] = {(it["name"] or "").strip().lower(): it["id"] for it in all_items}
        for plan in plans_to_backfill:
            changed = False
            for it in plan.get("items", []):
                if not it.get("item_id"):
                    match_id = name_to_id.get((it.get("item_name") or "").strip().lower())
                    if match_id:
                        it["item_id"] = match_id
                        changed = True
            if changed:
                await db.gst_plans.update_one({"id": plan["id"]}, {"$set": {"items": plan["items"]}})

    existing_cfg = await db.gst_config.find_one({"key": "gst_config"})
    if not existing_cfg:
        await db.gst_config.insert_one({
            "key": "gst_config",
            "prefix": "INV",
            "suffix": "",
            "default_tax_mode": "intra_state",
            "place_of_supply": "Arunachal Pradesh",
            "next_seq": 1,
            "current_fy": "",
            "auto_generate": True,
            # Company branding
            "company_name": "K3 GAS SERVICE",
            "company_tagline": "",
            "company_address": "",
            "company_gstin": "",
            "company_state": "Arunachal Pradesh",
            "company_state_code": "12",
            "company_phone": "",
            "company_email": "",
            "company_logo_url": "",
            # Bank details
            "bank_name": "",
            "bank_account_no": "",
            "bank_ifsc": "",
            "bank_branch": "",
            "bank_account_holder": "",
            # Terms & Conditions + Signatory
            "terms_conditions": "1. Goods once sold will not be taken back.\n2. Subject to local jurisdiction.\n3. Payment due within 7 days of invoice date.",
            "signatory_name": "",
            "signatory_designation": "Authorized Signatory",
        })
    else:
        # Backfill missing fields for older configs
        missing = {}
        defaults = {
            "company_name": "K3 GAS SERVICE", "company_tagline": "", "company_address": "",
            "company_gstin": "", "company_state": "Arunachal Pradesh", "company_state_code": "12",
            "company_phone": "", "company_email": "", "company_logo_url": "",
            "bank_name": "", "bank_account_no": "", "bank_ifsc": "", "bank_branch": "",
            "bank_account_holder": "",
            "terms_conditions": "1. Goods once sold will not be taken back.\n2. Subject to local jurisdiction.\n3. Payment due within 7 days of invoice date.",
            "signatory_name": "", "signatory_designation": "Authorized Signatory",
        }
        for k, v in defaults.items():
            if k not in existing_cfg:
                missing[k] = v
        if missing:
            await db.gst_config.update_one({"key": "gst_config"}, {"$set": missing})


def fy_string(d: datetime) -> str:
    """Indian fiscal year string e.g. 2026-27 (Apr-Mar)."""
    yr = d.year
    if d.month < 4:
        start, end = yr - 1, yr
    else:
        start, end = yr, yr + 1
    return f"{start}-{str(end)[-2:]}"


def amount_in_words_inr(amount: float) -> str:
    """Convert an Indian rupee amount to title-cased words. Returns 'Rupees X Only' or with paise.
    Normalises num2words en_IN output (removes 'And' connectors and hyphens) to match the
    frontend amountInWords helper so PDF and on-screen wording stay identical."""
    def _normalise(t: str) -> str:
        return t.replace(" And ", " ").replace("-", " ").replace("  ", " ").strip()
    try:
        from num2words import num2words
        whole = int(amount)
        paise = int(round((amount - whole) * 100))
        rupees_text = _normalise(num2words(whole, lang='en_IN').replace(',', '').title())
        if paise > 0:
            paise_text = _normalise(num2words(paise, lang='en_IN').replace(',', '').title())
            return f"Rupees {rupees_text} and {paise_text} Paise Only"
        return f"Rupees {rupees_text} Only"
    except Exception:
        return f"Rupees {amount:.2f} Only"


async def next_invoice_number(when: Optional[datetime] = None) -> str:
    await ensure_seed()
    when = when or datetime.now(timezone.utc)
    fy = fy_string(when)
    # Atomic: reset seq if FY changed, else just inc.
    cfg = await db.gst_config.find_one_and_update(
        {"key": "gst_config", "current_fy": fy},
        {"$inc": {"next_seq": 1}},
        return_document=False,
    )
    if not cfg:
        # FY changed (or first run for this FY) - atomically reset
        cfg = await db.gst_config.find_one_and_update(
            {"key": "gst_config"},
            {"$set": {"current_fy": fy, "next_seq": 2}},
            return_document=False,
        )
        seq = 1
    else:
        seq = int(cfg.get("next_seq") or 1)
    prefix = (cfg or {}).get("prefix") or "INV"
    suffix = (cfg or {}).get("suffix") or ""
    suf_part = f"/{suffix}" if suffix else ""
    return f"{prefix}/{fy}/{seq:04d}{suf_part}"


def compute_totals(line_items: List[dict], tax_mode: str) -> dict:
    sub_total = 0.0
    total_cgst = 0.0
    total_sgst = 0.0
    total_igst = 0.0
    for it in line_items:
        qty = float(it.get("quantity") or 0)
        rate = float(it.get("rate") or 0)
        gst_pct = float(it.get("gst_rate") or 0)
        taxable = round(qty * rate, 2)
        if tax_mode == "inter_state":
            igst = round(taxable * gst_pct / 100.0, 2)
            cgst = sgst = 0.0
        else:
            cgst = sgst = round(taxable * gst_pct / 200.0, 2)
            igst = 0.0
        it["taxable_value"] = taxable
        it["cgst"] = cgst
        it["sgst"] = sgst
        it["igst"] = igst
        it["total_gst"] = round(cgst + sgst + igst, 2)
        it["line_total"] = round(taxable + cgst + sgst + igst, 2)
        sub_total += taxable
        total_cgst += cgst
        total_sgst += sgst
        total_igst += igst
    sub_total = round(sub_total, 2)
    total_cgst = round(total_cgst, 2)
    total_sgst = round(total_sgst, 2)
    total_igst = round(total_igst, 2)
    total_gst = round(total_cgst + total_sgst + total_igst, 2)
    # Total before round-off, then round grand total to nearest rupee.
    total_before_roundoff = round(sub_total + total_gst, 2)
    grand_total = float(round(total_before_roundoff))
    round_off = round(grand_total - total_before_roundoff, 2)
    return {
        "sub_total": sub_total,
        "total_cgst": total_cgst,
        "total_sgst": total_sgst,
        "total_igst": total_igst,
        "total_gst": total_gst,
        "total_before_roundoff": total_before_roundoff,
        "round_off": round_off,
        "grand_total": grand_total,
    }


# ============ DISCREPANCY DETECTION ============
DISCREPANCY_TOLERANCE = 1.0  # ±₹1 rounding allowance


# ============ WAREHOUSE FILTER (role-based) ============
def apply_warehouse_filter(query: dict, warehouse_ids: Optional[str], user: dict) -> dict:
    """Mutates and returns `query` with warehouse constraints applied.

    - Admin users: filter by comma-separated warehouse_ids if given; otherwise no filter (see all).
    - Non-admin users: HARD-LOCKED to their own `user.warehouse_id`.
    """
    role = (user or {}).get("role", "").lower()
    is_admin = role in ("admin", "super_admin", "master_admin")
    if not is_admin:
        own = (user or {}).get("warehouse_id") or ""
        query["warehouse_id"] = own or "__no_warehouse__"
        return query
    if warehouse_ids:
        ids = [w.strip() for w in warehouse_ids.split(",") if w.strip()]
        if ids:
            query["warehouse_id"] = {"$in": ids}
    return query


def _dangling_compute_payment_fields_placeholder():
    """Deprecated no-op — kept only to preserve line-number stability during refactor."""
    return None


async def compute_expected_amount(payload: dict) -> Optional[float]:
    """Returns the expected grand_total for an invoice payload based on:
       1. The linked Connection Plan (if connection_plan_id is set and all plan items have rates)
       2. The Item Master default_rate × quantity × (1 + gst_rate/100) sum (when items map to gst_items)
    Returns None when no expected amount can be computed (e.g., manual ad-hoc items)."""
    tax_mode = (payload.get("tax_mode") or "intra_state").lower()

    # 1) Plan-based expected amount
    plan_id = payload.get("connection_plan_id")
    if plan_id:
        plan = await db.gst_plans.find_one({"id": plan_id, "is_active": True}, {"_id": 0})
        if plan and plan.get("items"):
            if all(float(it.get("unit_price") or 0) > 0 for it in plan["items"]):
                synth = [{
                    "quantity": float(it.get("quantity") or 0),
                    "rate": float(it.get("unit_price") or 0),
                    "gst_rate": float(it.get("gst_rate") or 0),
                } for it in plan["items"]]
                return compute_totals(synth, tax_mode)["grand_total"]

    # 2) Item-master expected amount: every line_item must resolve to a gst_items row with default_rate>0
    line_items = payload.get("line_items") or []
    if not line_items:
        return None
    synth: List[dict] = []
    all_resolved = True
    for li in line_items:
        item_id = li.get("item_id")
        item: Optional[dict] = None
        if item_id:
            item = await db.gst_items.find_one({"id": item_id}, {"_id": 0})
        if not item:
            # try name match
            name = (li.get("item_name") or "").strip()
            if name:
                item = await db.gst_items.find_one({"name": name}, {"_id": 0})
        if not item or float(item.get("default_rate") or 0) <= 0:
            all_resolved = False
            break
        qty = float(li.get("quantity") or 0)
        gst_rate = float(item.get("gst_rate") or 0)
        # default_rate is inclusive (matches plan unit_price). Convert to taxable per unit.
        taxable_per_unit = round(float(item["default_rate"]) * 100.0 / (100.0 + gst_rate), 2)
        synth.append({"quantity": qty, "rate": taxable_per_unit, "gst_rate": gst_rate})
    if not all_resolved or not synth:
        return None
    return compute_totals(synth, tax_mode)["grand_total"]


def discrepancy_payload(expected: Optional[float], actual: float) -> dict:
    """Compute discrepancy fields. Returns {is_discrepancy, expected, actual, diff}."""
    if expected is None:
        return {"is_discrepancy": False, "expected_amount": None,
                "actual_amount": round(actual, 2), "discrepancy_amount": 0.0}
    diff = round(actual - expected, 2)
    is_mismatch = abs(diff) > DISCREPANCY_TOLERANCE
    return {
        "is_discrepancy": is_mismatch,
        "expected_amount": round(expected, 2),
        "actual_amount": round(actual, 2),
        "discrepancy_amount": diff,
    }


def compute_payment_fields(grand_total: float, cash_received: float = 0,
                            online_received: float = 0,
                            payment_mode: Optional[str] = None) -> dict:
    """Computes payment-status helpers for invoices.

    Returns:
      cash_received, online_received, pending_amount, payment_status

    Status rules:
      - Paid       : grand_total - (cash + online) <= ₹1 (rounding tolerance)
      - Partial    : 0 < paid < grand_total
      - Pending    : nothing paid yet
      - blank      : grand_total <= 0 (no expectation)
    """
    grand = round(float(grand_total or 0), 2)
    cash = round(float(cash_received or 0), 2)
    online = round(float(online_received or 0), 2)
    paid = round(cash + online, 2)
    if grand <= 0:
        return {"cash_received": cash, "online_received": online,
                "pending_amount": 0.0, "payment_status": ""}
    pending = round(grand - paid, 2)
    if pending <= 1.0 and paid > 0:
        status = "Paid"
    elif paid <= 0:
        status = "Pending"
    elif paid < grand:
        status = "Partial"
    else:
        status = "Paid"
    return {
        "cash_received": cash,
        "online_received": online,
        "pending_amount": max(0.0, pending),
        "payment_status": status,
    }


async def sync_invoice_payment_from_sale(sale: dict, sale_type: str) -> Optional[dict]:
    """Called when a sale is edited. If an active GST invoice is linked to this sale,
    recompute its cash_received/online_received/pending_amount/payment_status from the
    updated sale. Returns the new payment fields (or None if no linked invoice).

    Business rules match _auto_generate_invoice: for accessory_sales without an explicit
    cash/online split, we bucket the grand_total by payment_mode (cash | online | pending).
    For sales_entries we take cash_amount + online_amount as-is.
    """
    inv = await db.gst_invoices.find_one(
        {"sale_id": sale.get("id"), "sale_type": sale_type, "status": "active"},
        {"_id": 0},
    )
    if not inv:
        return None

    sale_cash = float(sale.get("cash_amount") or 0)
    sale_online = float(sale.get("online_amount") or 0)
    if sale_type == "accessory_sale" and (sale_cash + sale_online) == 0:
        grand_for_split = float(sale.get("grand_total") or sale.get("amount") or 0)
        pm = (sale.get("payment_mode") or "cash").lower()
        if pm == "online":
            sale_online = grand_for_split
        elif pm == "pending":
            pass  # keep both 0 → Pending
        else:
            sale_cash = grand_for_split

    pay = compute_payment_fields(
        inv.get("grand_total", 0),
        sale_cash,
        sale_online,
        sale.get("payment_mode") or inv.get("payment_mode"),
    )
    pay["updated_at"] = datetime.now(timezone.utc).isoformat()
    if sale.get("payment_mode"):
        pay["payment_mode"] = sale["payment_mode"]
    await db.gst_invoices.update_one({"id": inv["id"]}, {"$set": pay})
    return pay


async def validate_sale_discrepancy(sale: dict, sale_type: str) -> dict:
    """Compute expected vs actual for a sale BEFORE it is persisted. Used by
    routes/sales.py and routes/accessories.py to enforce the mandatory-reason rule
    on sales entries.

    Returns the discrepancy_payload(...) dict. When expected_amount cannot be
    determined (no plan, no matching item master), returns is_discrepancy=False
    so the sale is saved silently — same behaviour as before this feature."""
    actual = float(sale.get("amount") or 0)
    if actual <= 0:
        return discrepancy_payload(None, 0.0)

    if sale_type == "sales_entry":
        ct = (sale.get("connection_type") or "").lower()
        is_refill = "refill" in ct
        is_commercial = "commercial" in ct
        # NOTE: A bare connection_type like 'domestic' (no '_refill' suffix) is
        # treated as a new-connection sale by design — matches the SalesDashboard
        # form layout where Refill flows always set 'domestic_refill' / 'commercial_refill'.
        # Plan-based: only for new connections
        plan_id = sale.get("connection_plan_id")
        if plan_id and not is_refill:
            plan = await db.gst_plans.find_one({"id": plan_id, "is_active": True}, {"_id": 0})
            if plan and plan.get("items") and all(float(it.get("unit_price") or 0) > 0 for it in plan["items"]):
                synth = [{
                    "quantity": float(it.get("quantity") or 0),
                    "rate": round(float(it.get("unit_price") or 0) * 100.0 / (100.0 + float(it.get("gst_rate") or 0)), 2),
                    "gst_rate": float(it.get("gst_rate") or 0),
                } for it in plan["items"]]
                expected = compute_totals(synth, "intra_state")["grand_total"]
                return discrepancy_payload(expected, actual)

        # Item-master based: refill or new connection without plan
        if is_refill:
            item_name = "Commercial LPG Refill" if is_commercial else "Domestic LPG Refill"
            qty = int(sale.get("no_of_refills", 0) or 0) or 1
        else:
            item_name = "Commercial New Connection" if is_commercial else "Domestic New Connection"
            cyl = str(sale.get("cylinder_nos", "")).strip()
            try:
                qty = int(cyl) if cyl else 1
            except ValueError:
                qty = max(1, len([p for p in cyl.split(",") if p.strip()]))
        gst_item = await db.gst_items.find_one({"name": item_name}, {"_id": 0})
        if gst_item and float(gst_item.get("default_rate") or 0) > 0:
            expected = float(gst_item["default_rate"]) * qty
            return discrepancy_payload(expected, actual)

    elif sale_type == "accessory_sale":
        # Accessories are sold at dealer-set variable prices and do NOT have a
        # "configured rate" in Item Master or Connection Plans. The discrepancy
        # rule (which compares to a fixed expected amount) does not apply here.
        # Return early with no discrepancy so the sale is saved as-is.
        return discrepancy_payload(None, actual)

    return discrepancy_payload(None, actual)



# ============ CONFIG ============
@router.get("/gst/config")
async def get_gst_config(user: dict = Depends(require_admin)):
    await ensure_seed()
    cfg = await db.gst_config.find_one({"key": "gst_config"}, {"_id": 0})
    return cfg


@router.put("/gst/config")
async def update_gst_config(data: dict, user: dict = Depends(require_admin)):
    allowed = {
        "prefix", "suffix", "default_tax_mode", "place_of_supply", "auto_generate",
        "company_name", "company_tagline", "company_address", "company_gstin",
        "company_state", "company_state_code", "company_phone", "company_email",
        "company_logo_url",
        "bank_name", "bank_account_no", "bank_ifsc", "bank_branch", "bank_account_holder",
        "terms_conditions", "signatory_name", "signatory_designation",
    }
    updates = {k: v for k, v in data.items() if k in allowed}
    if updates.get("default_tax_mode") and updates["default_tax_mode"] not in ("intra_state", "inter_state"):
        raise HTTPException(status_code=400, detail="default_tax_mode must be intra_state or inter_state")

    # Sanitize prefix/suffix — the invoice number template is `<prefix>/<FY>/<seq>[/<suffix>]`
    # so allowing slashes, spaces, or FY-like segments here produces broken numbers like
    # `K3/2026-27/0001/2026-27/0037`. We keep only the FIRST clean token before any `/`
    # and drop FY-like patterns silently.
    import re as _re
    def _sanitize_token(v):
        if v is None:
            return v
        # Keep only the first `/`-separated token
        s = str(v).strip().split("/")[0].split("\\")[0].strip()
        # Drop FY-like segments (YYYY-YY or YYYY-YYYY)
        if _re.fullmatch(r"\d{4}-\d{2,4}", s):
            return ""
        return s.replace(" ", "")[:10]
    if "prefix" in updates:
        updates["prefix"] = _sanitize_token(updates["prefix"]) or "INV"
    if "suffix" in updates:
        updates["suffix"] = _sanitize_token(updates["suffix"]) or ""

    await db.gst_config.update_one({"key": "gst_config"}, {"$set": updates}, upsert=True)
    await log_audit(user.get("id", ""), user.get("name", ""), "update", "gst_config", "",
                    f"Updated: {','.join(updates.keys())}")
    cfg = await db.gst_config.find_one({"key": "gst_config"}, {"_id": 0})
    return cfg


@router.post("/gst/invoices/repair-numbers")
async def repair_invoice_numbers(user: dict = Depends(require_admin)):
    """One-time cleanup: fix malformed invoice_numbers like
    `K3/2026-27/0001/2026-27/0037` -> `K3/2026-27/0037` by keeping the FIRST
    FY-segment + LAST 4-digit sequence. Idempotent: correctly-formed numbers
    are left untouched.
    """
    import re as _re
    docs = await db.gst_invoices.find({}, {"_id": 0, "id": 1, "invoice_number": 1}).to_list(200000)
    fixed: List[dict] = []
    fy_re = _re.compile(r"\d{4}-\d{2,4}")
    seq_re = _re.compile(r"\d{3,6}")
    for d in docs:
        num = d.get("invoice_number") or ""
        parts = [p for p in num.split("/") if p.strip()]
        # Correct form has EXACTLY 3 segments: prefix, FY, seq
        if len(parts) <= 3:
            continue
        prefix = parts[0]
        fys = [p for p in parts if fy_re.fullmatch(p)]
        seqs = [p for p in parts if seq_re.fullmatch(p) and not fy_re.fullmatch(p)]
        if not fys or not seqs:
            continue
        new_num = f"{prefix}/{fys[0]}/{seqs[-1]}"
        if new_num == num:
            continue
        await db.gst_invoices.update_one({"id": d["id"]}, {"$set": {"invoice_number": new_num}})
        fixed.append({"id": d["id"], "before": num, "after": new_num})
    await log_audit(user.get("id", ""), user.get("name", ""), "repair", "gst_invoice", "",
                    f"Repaired {len(fixed)} invoice numbers")
    return {"repaired": len(fixed), "changes": fixed[:100]}


# Note: Item Master CRUD + Rate History + Bulk Update endpoints have been
# extracted to routes/gst_items.py for modularity. This file now focuses on
# config, connection plans, and invoices.


# ============ CONNECTION PLANS (Item-wise billing templates) ============
def _validate_plan_items(items: list) -> list:
    if not isinstance(items, list) or not items:
        raise HTTPException(status_code=400, detail="At least one plan item is required")
    cleaned_items = []
    for it in items:
        if not (it.get("item_name") or "").strip():
            raise HTTPException(status_code=400, detail="item_name required for every line")
        cleaned_items.append({
            "item_id": (it.get("item_id") or "").strip() or None,
            "item_name": it["item_name"].strip(),
            "hsn": (it.get("hsn") or "").strip(),
            "unit": it.get("unit") or "Nos",
            "quantity": float(it.get("quantity") or 0),
            "gst_rate": float(it.get("gst_rate") or 0),
            "unit_price": float(it.get("unit_price") or 0),
        })
    return cleaned_items


def _validate_plan_payload(data: dict) -> list:
    if not (data.get("name") or "").strip():
        raise HTTPException(status_code=400, detail="Plan name required")
    return _validate_plan_items(data.get("items") or [])


@router.get("/gst/plans")
async def list_plans(user: dict = Depends(require_admin)):
    await ensure_seed()
    plans = await db.gst_plans.find({}, {"_id": 0}).sort("plan_type", 1).to_list(200)
    return plans


@router.get("/gst/plans/{plan_id}")
async def get_plan(plan_id: str, user: dict = Depends(require_admin)):
    plan = await db.gst_plans.find_one({"id": plan_id}, {"_id": 0})
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


@router.post("/gst/plans")
async def create_plan(data: dict, user: dict = Depends(require_admin)):
    items = _validate_plan_payload(data)
    plan = {
        "id": str(uuid.uuid4()),
        "name": data["name"].strip(),
        "plan_type": (data.get("plan_type") or "custom").strip(),
        "connection_type": data.get("connection_type") or "domestic",
        "cylinder_count": int(data.get("cylinder_count") or 1),
        "has_accessories": bool(data.get("has_accessories", False)),
        "items": items,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.gst_plans.insert_one(plan.copy())
    plan.pop("_id", None)
    await log_audit(user.get("id", ""), user.get("name", ""), "create", "gst_plan",
                    plan["id"], f"Plan: {plan['name']}")
    return plan


@router.put("/gst/plans/{plan_id}")
async def update_plan(plan_id: str, data: dict, user: dict = Depends(require_admin)):
    existing = await db.gst_plans.find_one({"id": plan_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Plan not found")
    items = _validate_plan_items(data["items"]) if data.get("items") is not None else existing.get("items", [])
    updates = {
        "name": (data.get("name") or existing["name"]).strip(),
        "plan_type": data.get("plan_type") or existing.get("plan_type"),
        "connection_type": data.get("connection_type") or existing.get("connection_type"),
        "cylinder_count": int(data.get("cylinder_count") or existing.get("cylinder_count", 1)),
        "has_accessories": bool(data.get("has_accessories", existing.get("has_accessories", False))),
        "items": items,
        "is_active": bool(data.get("is_active", existing.get("is_active", True))),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.gst_plans.update_one({"id": plan_id}, {"$set": updates})
    await log_audit(user.get("id", ""), user.get("name", ""), "update", "gst_plan",
                    plan_id, f"Updated plan {updates['name']}")
    return await db.gst_plans.find_one({"id": plan_id}, {"_id": 0})


@router.delete("/gst/plans/{plan_id}")
async def delete_plan(plan_id: str, user: dict = Depends(require_admin)):
    res = await db.gst_plans.update_one({"id": plan_id}, {"$set": {"is_active": False}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Plan not found")
    return {"message": "Plan deactivated"}


def _match_plan_for_sale(plans: List[dict], connection_type: str, cylinder_count: int,
                         has_accessories: bool) -> Optional[dict]:
    """Pick the best plan matching a new connection sale.
    Domestic: matches cylinder_count (1 or 2) + has_accessories flag.
    Commercial: matches the closest cylinder count (1, 2, 3, 4, 6, 10, 15).
    """
    is_commercial = "commercial" in (connection_type or "")
    is_domestic = "domestic" in (connection_type or "") or not is_commercial
    candidates = [p for p in plans if p.get("is_active") and
                  ((is_commercial and p.get("connection_type") == "commercial") or
                   (is_domestic and p.get("connection_type") == "domestic"))]
    if not candidates:
        return None
    if is_domestic:
        # Pick by cylinder_count + has_accessories
        target_count = 2 if cylinder_count >= 2 else 1
        filtered = [p for p in candidates
                    if p.get("cylinder_count") == target_count
                    and p.get("has_accessories") == has_accessories]
        if filtered:
            return filtered[0]
        # Fallback: ignore accessories preference
        filtered = [p for p in candidates if p.get("cylinder_count") == target_count]
        return filtered[0] if filtered else None
    # Commercial: find closest cylinder_count
    candidates_sorted = sorted(candidates, key=lambda p: abs((p.get("cylinder_count") or 1) - cylinder_count))
    return candidates_sorted[0] if candidates_sorted else None


# ============ INVOICES - LIST / SUMMARY / EXPORTS (must come BEFORE /{id} routes) ============
@router.get("/gst/invoices/summary")
async def get_invoice_summary(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    month: Optional[int] = None,
    year: Optional[int] = None,
    fy: Optional[str] = None,
    payment_status: Optional[str] = None,
    item_type: Optional[str] = None,
    warehouse_ids: Optional[str] = None,
    user: dict = Depends(require_admin),
):
    await ensure_seed()
    q: Dict[str, Any] = {}
    apply_warehouse_filter(q, warehouse_ids, user)
    if payment_status:
        q["payment_status"] = payment_status
    if item_type:
        q["bill_type"] = item_type
    if start_date or end_date:
        q["invoice_date"] = {}
        if start_date:
            q["invoice_date"]["$gte"] = start_date
        if end_date:
            q["invoice_date"]["$lte"] = end_date
    if month and year:
        from calendar import monthrange
        _, last = monthrange(year, month)
        q["invoice_date"] = {"$gte": f"{year}-{month:02d}-01", "$lte": f"{year}-{month:02d}-{last:02d}"}
    elif year:
        q["invoice_date"] = {"$gte": f"{year}-01-01", "$lte": f"{year}-12-31"}
    if fy:
        try:
            start_yr = int(str(fy).split("-")[0])
            q["invoice_date"] = {"$gte": f"{start_yr}-04-01", "$lte": f"{start_yr + 1}-03-31"}
        except (ValueError, IndexError):
            pass

    pipeline = [
        {"$match": q} if q else {"$match": {}},
        {"$group": {
            "_id": "$status",
            "count": {"$sum": 1},
            "total": {"$sum": "$grand_total"},
            "total_gst": {"$sum": "$total_gst"},
        }}
    ]
    rows = await db.gst_invoices.aggregate(pipeline).to_list(100)
    summary = {
        "active": {"count": 0, "total": 0.0, "total_gst": 0.0},
        "cancelled": {"count": 0, "total": 0.0, "total_gst": 0.0},
    }
    for r in rows:
        st = r.get("_id") or "active"
        summary[st] = {
            "count": r["count"],
            "total": round(r["total"], 2),
            "total_gst": round(r["total_gst"], 2),
        }
    summary["total_invoices"] = summary["active"]["count"] + summary["cancelled"]["count"]
    summary["total_amount"] = round(summary["active"]["total"], 2)  # excluding cancelled
    summary["total_gst_collected"] = round(summary["active"]["total_gst"], 2)
    return summary


@router.get("/gst/invoices/export/excel")
async def export_invoices_excel(
    search: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    month: Optional[int] = None,
    year: Optional[int] = None,
    fy: Optional[str] = None,
    payment_status: Optional[str] = None,
    item_type: Optional[str] = None,
    warehouse_ids: Optional[str] = None,
    user: dict = Depends(require_admin),
):
    """Item-wise Invoice Register Excel export with all spec columns,
    frozen header, autofilter, wrapped text, auto column widths, bold totals."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    q: Dict[str, Any] = {}
    apply_warehouse_filter(q, warehouse_ids, user)
    if status:
        q["status"] = status
    if payment_status:
        q["payment_status"] = payment_status
    if item_type:
        q["bill_type"] = item_type
    if start_date or end_date:
        q["invoice_date"] = {}
        if start_date:
            q["invoice_date"]["$gte"] = start_date
        if end_date:
            q["invoice_date"]["$lte"] = end_date
    if month and year:
        from calendar import monthrange
        _, last = monthrange(year, month)
        q["invoice_date"] = {"$gte": f"{year}-{month:02d}-01", "$lte": f"{year}-{month:02d}-{last:02d}"}
    elif year:
        q["invoice_date"] = {"$gte": f"{year}-01-01", "$lte": f"{year}-12-31"}
    if fy:
        try:
            start_yr = int(str(fy).split("-")[0])
            q["invoice_date"] = {"$gte": f"{start_yr}-04-01", "$lte": f"{start_yr + 1}-03-31"}
        except (ValueError, IndexError):
            pass
    if search:
        q["$or"] = [{"invoice_number": {"$regex": search, "$options": "i"}},
                    {"memo_no": {"$regex": search, "$options": "i"}},
                    {"customer_name": {"$regex": search, "$options": "i"}},
                    {"customer_phone": {"$regex": search, "$options": "i"}}]

    invoices = await db.gst_invoices.find(q, {"_id": 0}).sort([("invoice_date", -1), ("created_at", -1)]).to_list(50000)
    cfg = await db.gst_config.find_one({"key": "gst_config"}, {"_id": 0}) or {}

    wb = Workbook()
    ws = wb.active
    ws.title = "Invoice Register"

    # Title rows with company info
    ws["A1"] = cfg.get("company_name", "K3 GAS SERVICE")
    ws["A1"].font = Font(bold=True, size=14, color="1E5A8C")
    ws.merge_cells("A1:H1")
    ws["A2"] = f"GSTIN: {cfg.get('company_gstin', '')}    |    {cfg.get('company_address', '')}"
    ws["A2"].font = Font(size=9, color="555555")
    ws.merge_cells("A2:H2")
    ws["A3"] = f"Invoice Register   |   Period: {start_date or 'All'} to {end_date or 'All'}   |   Generated: {datetime.now(timezone.utc).strftime('%d-%m-%Y %H:%M')} by {user.get('name', '')}"
    ws["A3"].font = Font(italic=True, size=9, color="666666")
    ws.merge_cells("A3:H3")

    headers = [
        "Sl No.", "Invoice Number", "Invoice Date", "Status", "Customer Name", "Customer Mobile",
        "Customer GSTIN", "Item Name", "HSN Code", "Quantity", "Unit", "Rate",
        "Taxable Value", "GST %", "CGST %", "CGST Amount", "SGST %", "SGST Amount",
        "IGST %", "IGST Amount", "Total GST", "Discount", "Round Off", "Grand Total",
        "Payment Mode", "Warehouse", "Sales Executive", "Created By", "Created Date",
        "Cancelled By", "Cancelled Date", "Cancellation Reason",
        # New columns (appended to keep existing index math intact)
        "Memo No.", "Cash Received", "Online Received", "Total Paid", "Pending Amount", "Payment Status",
    ]
    header_row = 5
    thin = Side(style="thin", color="BBBBBB")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    for i, h in enumerate(headers, 1):
        c = ws.cell(row=header_row, column=i, value=h)
        c.font = Font(bold=True, color="FFFFFF", size=10)
        c.fill = PatternFill("solid", fgColor="1E5A8C")
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = border

    # Right-aligned amount columns (col indices 1-based)
    amount_cols = {12, 13, 16, 18, 20, 21, 22, 23, 24, 34, 35, 36, 37}
    center_cols = {1, 3, 9, 14, 15, 17, 19, 29, 31, 33, 38}

    def _fmt_date(s):
        if not s:
            return ""
        try:
            # YYYY-MM-DD -> DD-MM-YYYY
            parts = str(s).split("T")[0].split("-")
            if len(parts) == 3:
                return f"{parts[2]}-{parts[1]}-{parts[0]}"
        except Exception:
            pass
        return str(s)

    sl_no = 0
    row = header_row + 1
    total_taxable = total_cgst = total_sgst = total_igst = total_grand = 0.0
    for inv in invoices:
        items = inv.get("line_items") or [{}]
        is_first = True
        for li in items:
            sl_no += 1 if is_first else 0
            qty = float(li.get("quantity") or 0)
            rate = float(li.get("rate") or 0)
            taxable = float(li.get("taxable_value") or 0)
            gst_rate = float(li.get("gst_rate") or 0)
            cgst = float(li.get("cgst") or 0)
            sgst = float(li.get("sgst") or 0)
            igst = float(li.get("igst") or 0)
            total_taxable += taxable
            total_cgst += cgst
            total_sgst += sgst
            total_igst += igst
            if is_first:
                total_grand += float(inv.get("grand_total") or 0)
            vals = [
                sl_no if is_first else "",
                inv["invoice_number"] if is_first else "",
                _fmt_date(inv.get("invoice_date")) if is_first else "",
                inv.get("status", "") if is_first else "",
                inv.get("customer_name", "") if is_first else "",
                inv.get("customer_phone", "") if is_first else "",
                inv.get("customer_gstin", "") if is_first else "",
                li.get("item_name", ""),
                li.get("hsn", ""),
                qty,
                li.get("unit", ""),
                rate,
                taxable,
                gst_rate,
                gst_rate / 2,
                cgst,
                gst_rate / 2,
                sgst,
                gst_rate,
                igst,
                cgst + sgst + igst,
                0,  # discount
                float(inv.get("round_off") or 0) if is_first else "",  # round off
                float(inv.get("grand_total") or 0) if is_first else "",
                inv.get("payment_mode", "") if is_first else "",
                inv.get("warehouse_name", "") if is_first else "",
                inv.get("sales_executive_name", "") if is_first else "",
                inv.get("created_by_name", "") if is_first else "",
                _fmt_date(inv.get("created_at", "")[:10]) if is_first else "",
                inv.get("cancelled_by_name", "") if is_first else "",
                _fmt_date((inv.get("cancelled_at") or "")[:10]) if is_first else "",
                inv.get("cancellation_reason", "") if is_first else "",
                # New columns (per-invoice — only on first line of a multi-line invoice)
                (inv.get("memo_no") or inv.get("invoice_number")) if is_first else "",
                (float(inv.get("cash_received") or 0)) if is_first else "",
                (float(inv.get("online_received") or 0)) if is_first else "",
                (float(inv.get("cash_received") or 0) + float(inv.get("online_received") or 0)) if is_first else "",
                (float(inv.get("pending_amount") or 0)) if is_first else "",
                (inv.get("payment_status") or "") if is_first else "",
            ]
            for c_idx, v in enumerate(vals, 1):
                cell = ws.cell(row=row, column=c_idx, value=v)
                cell.border = border
                if c_idx in amount_cols and isinstance(v, (int, float)):
                    cell.number_format = "#,##0.00"
                    cell.alignment = Alignment(horizontal="right", vertical="top", wrap_text=True)
                elif c_idx in center_cols:
                    cell.alignment = Alignment(horizontal="center", vertical="top", wrap_text=True)
                else:
                    cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
                if inv.get("status") == "cancelled":
                    cell.font = Font(strike=True, color="C00000", size=9)
                else:
                    cell.font = Font(size=9)
            row += 1
            is_first = False

    # Totals row
    if invoices:
        for col_idx in range(1, len(headers) + 1):
            ws.cell(row=row, column=col_idx).fill = PatternFill("solid", fgColor="E0EDDF")
            ws.cell(row=row, column=col_idx).font = Font(bold=True, size=10)
            ws.cell(row=row, column=col_idx).border = border
        ws.cell(row=row, column=8, value="TOTAL").alignment = Alignment(horizontal="right")
        ws.cell(row=row, column=13, value=round(total_taxable, 2)).number_format = "#,##0.00"
        ws.cell(row=row, column=13).alignment = Alignment(horizontal="right")
        ws.cell(row=row, column=16, value=round(total_cgst, 2)).number_format = "#,##0.00"
        ws.cell(row=row, column=16).alignment = Alignment(horizontal="right")
        ws.cell(row=row, column=18, value=round(total_sgst, 2)).number_format = "#,##0.00"
        ws.cell(row=row, column=18).alignment = Alignment(horizontal="right")
        ws.cell(row=row, column=20, value=round(total_igst, 2)).number_format = "#,##0.00"
        ws.cell(row=row, column=20).alignment = Alignment(horizontal="right")
        ws.cell(row=row, column=21, value=round(total_cgst + total_sgst + total_igst, 2)).number_format = "#,##0.00"
        ws.cell(row=row, column=21).alignment = Alignment(horizontal="right")
        ws.cell(row=row, column=24, value=round(total_grand, 2)).number_format = "#,##0.00"
        ws.cell(row=row, column=24).alignment = Alignment(horizontal="right")

    # Freeze headers + autofilter
    ws.freeze_panes = f"A{header_row + 1}"
    ws.auto_filter.ref = f"A{header_row}:{get_column_letter(len(headers))}{row}"

    # Auto column widths based on header
    widths = [6, 18, 12, 10, 25, 14, 18, 30, 12, 8, 8, 11, 13, 7, 7, 12, 7, 12, 7, 12, 12, 9, 9, 14, 13, 14, 16, 14, 12, 14, 12, 24]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # Repeat header on print
    ws.print_title_rows = f"{header_row}:{header_row}"
    ws.page_setup.orientation = ws.ORIENTATION_LANDSCAPE
    ws.page_setup.fitToWidth = 1
    ws.sheet_properties.pageSetUpPr.fitToPage = True

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    fname = f"Invoice_Register_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.xlsx"
    return StreamingResponse(iter([buf.read()]),
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f'attachment; filename="{fname}"'})


@router.post("/gst/invoices/generate-from-sale/{sale_type}/{sale_id}")
async def generate_from_sale(sale_type: str, sale_id: str, user: dict = Depends(require_admin)):
    """Manual trigger for legacy/old sales."""
    if sale_type not in ("sales_entry", "accessory_sale"):
        raise HTTPException(status_code=400, detail="Invalid sale_type. Use sales_entry or accessory_sale.")
    coll = {"sales_entry": db.sales_entries, "accessory_sale": db.accessory_sales}[sale_type]
    sale = await coll.find_one({"id": sale_id}, {"_id": 0})
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")
    existing = await db.gst_invoices.find_one({"sale_id": sale_id, "sale_type": sale_type, "status": "active"})
    if existing:
        raise HTTPException(status_code=400, detail=f"Active invoice already exists: {existing.get('invoice_number')}")
    inv = await _auto_generate_invoice(sale, sale_type, user)
    if not inv:
        raise HTTPException(status_code=400, detail="Could not generate invoice - missing customer/amount data")
    return inv


@router.get("/gst/invoices")
async def list_invoices(
    page: int = 1,
    limit: int = 100,
    search: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    month: Optional[int] = None,
    year: Optional[int] = None,
    fy: Optional[str] = None,
    payment_mode: Optional[str] = None,
    payment_status: Optional[str] = None,
    item_type: Optional[str] = None,
    warehouse_ids: Optional[str] = None,
    user: dict = Depends(require_admin),
):
    await ensure_seed()
    q: Dict[str, Any] = {}
    apply_warehouse_filter(q, warehouse_ids, user)
    if status:
        q["status"] = status
    if payment_mode:
        q["payment_mode"] = payment_mode
    if payment_status:
        q["payment_status"] = payment_status
    if item_type:
        q["bill_type"] = item_type
    if start_date:
        q.setdefault("invoice_date", {})["$gte"] = start_date
    if end_date:
        q.setdefault("invoice_date", {})["$lte"] = end_date
    if month and year:
        from calendar import monthrange
        _, last = monthrange(year, month)
        q["invoice_date"] = {"$gte": f"{year}-{month:02d}-01", "$lte": f"{year}-{month:02d}-{last:02d}"}
    elif year:
        q["invoice_date"] = {"$gte": f"{year}-01-01", "$lte": f"{year}-12-31"}
    if fy:
        # Indian FY like "2026-27" -> Apr 1 2026 to Mar 31 2027
        try:
            start_yr = int(str(fy).split("-")[0])
            q["invoice_date"] = {"$gte": f"{start_yr}-04-01", "$lte": f"{start_yr + 1}-03-31"}
        except (ValueError, IndexError):
            pass
    if search and search.strip():
        s = search.strip()
        q["$or"] = [
            {"invoice_number": {"$regex": s, "$options": "i"}},
            {"memo_no": {"$regex": s, "$options": "i"}},
            {"customer_name": {"$regex": s, "$options": "i"}},
            {"customer_phone": {"$regex": s, "$options": "i"}},
        ]
    skip = (page - 1) * limit
    total = await db.gst_invoices.count_documents(q)
    invoices = await db.gst_invoices.find(q, {"_id": 0}).sort([("invoice_date", -1), ("created_at", -1)]).skip(skip).limit(limit).to_list(limit)
    return {"invoices": invoices, "total": total, "page": page, "pages": (total + limit - 1) // limit}


# ============ INVOICES - SINGLE (these must come AFTER list/summary/export) ============
@router.get("/gst/customer-lookup")
async def customer_lookup(
    q: Optional[str] = None,
    customer_id: Optional[str] = None,
    limit: int = 15,
    user: dict = Depends(require_admin),
):
    """Search Customer Master by name / consumer_no / phone (min 2 chars),
    OR fetch a single customer by customer_id.
    Non-admins are hard-locked to their own warehouse."""
    query: Dict[str, Any] = {}
    role = (user or {}).get("role", "").lower()
    is_admin = role in ("admin", "super_admin", "master_admin")
    if not is_admin:
        own = user.get("warehouse_id") or ""
        query["warehouse_id"] = own if own else "__no_warehouse__"

    if customer_id:
        query["id"] = customer_id
        c = await db.customers.find_one(query, {"_id": 0})
        return {"customer": c or None}

    s = (q or "").strip()
    if len(s) < 2:
        return {"customers": []}
    query["$or"] = [
        {"customer_name": {"$regex": s, "$options": "i"}},
        {"consumer_no": {"$regex": s, "$options": "i"}},
        {"phone": {"$regex": s, "$options": "i"}},
    ]
    docs = await db.customers.find(query, {"_id": 0}).sort("customer_name", 1).limit(max(1, min(50, limit))).to_list(50)

    wh_ids = list({d.get("warehouse_id") for d in docs if d.get("warehouse_id")})
    wh_map: Dict[str, str] = {}
    if wh_ids:
        for w in await db.warehouses.find({"id": {"$in": wh_ids}}, {"_id": 0, "id": 1, "name": 1}).to_list(100):
            wh_map[w["id"]] = w.get("name", "")
    for d in docs:
        d["warehouse_name"] = wh_map.get(d.get("warehouse_id", ""), "")
    return {"customers": docs}


@router.post("/gst/invoices")
async def create_invoice(data: dict, user: dict = Depends(require_admin)):
    """Manual invoice creation. Validates against expected amount (from connection plan
    or item master). If a mismatch >₹1 is detected and no `discrepancy_reason` is given,
    returns HTTP 400 with the expected/actual/diff so the client can prompt for a reason."""
    await ensure_seed()
    cfg = await db.gst_config.find_one({"key": "gst_config"}) or {}
    tax_mode = (data.get("tax_mode") or cfg.get("default_tax_mode") or "intra_state").lower()
    line_items = data.get("line_items") or []
    if not line_items:
        raise HTTPException(status_code=400, detail="At least one line item is required")
    totals = compute_totals(line_items, tax_mode)

    # ---- Customer Master hydration (single source of truth) ----
    # When customer_id is supplied, pull authoritative details from the Customer
    # Master and stamp them onto the invoice as a point-in-time snapshot.
    # Fields the client sent still win for anything the master doesn't own
    # (like customer_gstin, which lives on the invoice only).
    customer_id = (data.get("customer_id") or "").strip()
    customer_source = "manual"
    if customer_id:
        cust = await db.customers.find_one({"id": customer_id}, {"_id": 0})
        if cust:
            customer_source = "master"
            data["customer_name"] = cust.get("customer_name") or data.get("customer_name") or ""
            data["customer_phone"] = cust.get("phone") or data.get("customer_phone") or ""
            data["customer_address"] = cust.get("address") or data.get("customer_address") or ""
            data["customer_consumer_no"] = cust.get("consumer_no") or ""
            data["customer_connection_type"] = (cust.get("connection_type") or "").lower()
            # If warehouse wasn't explicitly sent, inherit from the customer record
            if not data.get("warehouse_id"):
                data["warehouse_id"] = cust.get("warehouse_id") or ""
                if cust.get("warehouse_id"):
                    wh = await db.warehouses.find_one({"id": cust["warehouse_id"]}, {"_id": 0, "name": 1})
                    if wh:
                        data["warehouse_name"] = wh.get("name", "")
    data["customer_source"] = customer_source

    # ---- Discrepancy detection ----
    expected = await compute_expected_amount({**data, "tax_mode": tax_mode})
    disc = discrepancy_payload(expected, totals["grand_total"])
    reason = (data.get("discrepancy_reason") or "").strip()
    if disc["is_discrepancy"] and not reason:
        raise HTTPException(status_code=400, detail={
            "code": "discrepancy_requires_reason",
            "message": "Amount mismatch detected — justification required to save.",
            "expected_amount": disc["expected_amount"],
            "actual_amount": disc["actual_amount"],
            "discrepancy_amount": disc["discrepancy_amount"],
        })

    now = datetime.now(timezone.utc)
    invoice_number = data.get("invoice_number") or await next_invoice_number(now)
    # Memo No fallback: use invoice number when not supplied
    memo_no = (data.get("memo_no") or "").strip() or invoice_number
    pay = compute_payment_fields(
        totals["grand_total"],
        data.get("cash_received"),
        data.get("online_received"),
        data.get("payment_mode"),
    )
    invoice = {
        "id": str(uuid.uuid4()),
        "invoice_number": invoice_number,
        "memo_no": memo_no,
        "invoice_date": data.get("invoice_date") or now.strftime("%Y-%m-%d"),
        "fy": fy_string(now),
        "customer_id": data.get("customer_id") or "",
        "customer_name": (data.get("customer_name") or "").strip(),
        "customer_phone": (data.get("customer_phone") or "").strip(),
        "customer_address": data.get("customer_address") or "",
        "customer_gstin": (data.get("customer_gstin") or "").strip().upper(),
        # Historical snapshots of Customer Master fields at time of invoicing
        "customer_consumer_no": (data.get("customer_consumer_no") or "").strip(),
        "customer_connection_type": (data.get("customer_connection_type") or "").strip().lower(),
        "customer_source": data.get("customer_source") or "manual",  # 'master' | 'manual'
        "place_of_supply": data.get("place_of_supply") or cfg.get("place_of_supply", ""),
        "tax_mode": tax_mode,
        "bill_type": data.get("bill_type") or "manual",
        "payment_mode": data.get("payment_mode") or "cash",
        "remarks": data.get("remarks") or "",
        "line_items": line_items,
        **totals,
        **pay,
        "status": "active",
        "sale_id": data.get("sale_id") or "",
        "sale_type": data.get("sale_type") or "",
        "connection_plan_id": data.get("connection_plan_id") or "",
        "warehouse_id": data.get("warehouse_id") or "",
        "warehouse_name": data.get("warehouse_name") or "",
        "created_by_id": user.get("id", ""),
        "created_by_name": user.get("name", ""),
        "created_at": now.isoformat(),
        # Discrepancy fields
        "is_discrepancy": disc["is_discrepancy"],
        "expected_amount": disc["expected_amount"],
        "actual_amount": disc["actual_amount"],
        "discrepancy_amount": disc["discrepancy_amount"],
        "discrepancy_reason": reason if disc["is_discrepancy"] else "",
        "discrepancy_status": "pending" if disc["is_discrepancy"] else "",
    }
    await db.gst_invoices.insert_one(invoice.copy())
    invoice.pop("_id", None)
    audit_detail = f"Invoice {invoice['invoice_number']} for {invoice['customer_name']}"
    if disc["is_discrepancy"]:
        audit_detail += f" | DISCREPANCY: expected ₹{disc['expected_amount']} actual ₹{disc['actual_amount']} diff ₹{disc['discrepancy_amount']} reason: {reason}"
    await log_audit(user.get("id", ""), user.get("name", ""),
                    "create_discrepancy" if disc["is_discrepancy"] else "create",
                    "gst_invoice", invoice["id"], audit_detail)
    return invoice


@router.get("/gst/invoices/{invoice_id}")
async def get_invoice(invoice_id: str, user: dict = Depends(require_admin)):
    inv = await db.gst_invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return inv


@router.put("/gst/invoices/{invoice_id}")
async def update_invoice(invoice_id: str, data: dict, user: dict = Depends(require_admin)):
    existing = await db.gst_invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if existing.get("status") == "cancelled":
        raise HTTPException(status_code=400, detail="Cannot edit a cancelled invoice")
    editable = {
        "invoice_date", "customer_name", "customer_phone", "customer_address",
        "customer_gstin", "customer_consumer_no", "customer_connection_type",
        "place_of_supply", "tax_mode", "payment_mode",
        "remarks", "line_items", "bill_type", "connection_plan_id",
        "memo_no", "cash_received", "online_received",
    }
    updates = {k: v for k, v in data.items() if k in editable}
    if "memo_no" in updates:
        updates["memo_no"] = (updates["memo_no"] or "").strip() or existing.get("invoice_number")
    if "line_items" in updates or "tax_mode" in updates:
        tax_mode = updates.get("tax_mode") or existing.get("tax_mode")
        line_items = updates.get("line_items") or existing.get("line_items") or []
        totals = compute_totals(line_items, tax_mode)
        updates["line_items"] = line_items
        updates.update(totals)

        # Re-validate discrepancy on edit
        expected = await compute_expected_amount({
            **{k: existing.get(k) for k in ("connection_plan_id",)},
            **{k: updates.get(k, existing.get(k)) for k in ("tax_mode", "line_items")},
        })
        disc = discrepancy_payload(expected, totals["grand_total"])
        reason = (data.get("discrepancy_reason") or existing.get("discrepancy_reason") or "").strip()
        if disc["is_discrepancy"] and not reason:
            raise HTTPException(status_code=400, detail={
                "code": "discrepancy_requires_reason",
                "message": "Amount mismatch detected — justification required to save.",
                "expected_amount": disc["expected_amount"],
                "actual_amount": disc["actual_amount"],
                "discrepancy_amount": disc["discrepancy_amount"],
            })
        updates["is_discrepancy"] = disc["is_discrepancy"]
        updates["expected_amount"] = disc["expected_amount"]
        updates["actual_amount"] = disc["actual_amount"]
        updates["discrepancy_amount"] = disc["discrepancy_amount"]
        if disc["is_discrepancy"]:
            updates["discrepancy_reason"] = reason
            # Edit by admin re-opens for review unless review status already set in this call
            if not existing.get("discrepancy_status"):
                updates["discrepancy_status"] = "pending"
        else:
            # Edit fixed the mismatch - clear discrepancy fields
            updates["discrepancy_reason"] = ""
            updates["discrepancy_status"] = ""
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    updates["updated_by_name"] = user.get("name", "")
    # Recompute payment status if grand_total or cash_received / online_received changed
    if any(k in updates for k in ("line_items", "tax_mode", "cash_received", "online_received", "payment_mode")):
        grand_total_new = updates.get("grand_total", existing.get("grand_total", 0))
        pay = compute_payment_fields(
            grand_total_new,
            updates.get("cash_received", existing.get("cash_received", 0)),
            updates.get("online_received", existing.get("online_received", 0)),
            updates.get("payment_mode", existing.get("payment_mode")),
        )
        updates.update(pay)
    await db.gst_invoices.update_one({"id": invoice_id}, {"$set": updates})
    await log_audit(user.get("id", ""), user.get("name", ""), "update", "gst_invoice", invoice_id,
                    f"Fields: {','.join(updates.keys())}")
    return await db.gst_invoices.find_one({"id": invoice_id}, {"_id": 0})


# ============ DISCREPANCY REVIEW ENDPOINTS ============
@router.get("/gst/discrepancies")
async def list_discrepancies(status: Optional[str] = None, start_date: Optional[str] = None,
                              end_date: Optional[str] = None,
                              warehouse_ids: Optional[str] = None,
                              user: dict = Depends(require_admin)):
    """List all invoices flagged as discrepancy. Filter by status (pending/approved/rejected/corrected)
    and optional invoice_date range."""
    q: Dict[str, Any] = {"is_discrepancy": True}
    apply_warehouse_filter(q, warehouse_ids, user)
    if status and status != "all":
        q["discrepancy_status"] = status
    if start_date or end_date:
        q["invoice_date"] = {}
        if start_date:
            q["invoice_date"]["$gte"] = start_date
        if end_date:
            q["invoice_date"]["$lte"] = end_date
    rows = await db.gst_invoices.find(q, {"_id": 0}).sort("created_at", -1).to_list(2000)
    # Summary stats
    summary = {
        "total": len(rows),
        "pending": sum(1 for r in rows if r.get("discrepancy_status") == "pending"),
        "approved": sum(1 for r in rows if r.get("discrepancy_status") == "approved"),
        "rejected": sum(1 for r in rows if r.get("discrepancy_status") == "rejected"),
        "corrected": sum(1 for r in rows if r.get("discrepancy_status") == "corrected"),
        "total_difference": round(sum(float(r.get("discrepancy_amount") or 0) for r in rows), 2),
    }
    return {"rows": rows, "summary": summary}


@router.post("/gst/discrepancies/{invoice_id}/review")
async def review_discrepancy(invoice_id: str, data: dict, user: dict = Depends(require_admin)):
    """Approve or reject a discrepancy. Body: {action: 'approve'|'reject', note: str}"""
    action = (data.get("action") or "").lower()
    if action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="action must be 'approve' or 'reject'")
    note = (data.get("note") or "").strip()
    inv = await db.gst_invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if not inv.get("is_discrepancy"):
        raise HTTPException(status_code=400, detail="Invoice is not flagged as a discrepancy")
    now = datetime.now(timezone.utc).isoformat()
    new_status = "approved" if action == "approve" else "rejected"
    await db.gst_invoices.update_one({"id": invoice_id}, {"$set": {
        "discrepancy_status": new_status,
        "discrepancy_reviewed_by": user.get("id", ""),
        "discrepancy_reviewed_by_name": user.get("name", ""),
        "discrepancy_reviewed_at": now,
        "discrepancy_review_note": note,
    }})
    await log_audit(user.get("id", ""), user.get("name", ""),
                    f"discrepancy_{action}", "gst_invoice", invoice_id,
                    f"{inv.get('invoice_number')} | expected ₹{inv.get('expected_amount')} actual ₹{inv.get('actual_amount')} diff ₹{inv.get('discrepancy_amount')} | note: {note}")
    return await db.gst_invoices.find_one({"id": invoice_id}, {"_id": 0})


@router.post("/gst/discrepancies/{invoice_id}/correct")
async def correct_discrepancy(invoice_id: str, data: dict, user: dict = Depends(require_admin)):
    """Admin corrects the invoice by updating line_items so the grand_total matches the
    expected amount. After correction, the invoice is marked as corrected and discrepancy
    flags are cleared. Body: {line_items: [...], note: str}."""
    line_items = data.get("line_items") or []
    if not line_items:
        raise HTTPException(status_code=400, detail="line_items required to correct invoice")
    note = (data.get("note") or "").strip()
    existing = await db.gst_invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if not existing.get("is_discrepancy"):
        raise HTTPException(status_code=400, detail="Invoice is not flagged as a discrepancy")
    tax_mode = existing.get("tax_mode") or "intra_state"
    totals = compute_totals(line_items, tax_mode)
    expected = await compute_expected_amount({
        "connection_plan_id": existing.get("connection_plan_id"),
        "tax_mode": tax_mode,
        "line_items": line_items,
    })
    disc = discrepancy_payload(expected, totals["grand_total"])
    now = datetime.now(timezone.utc).isoformat()
    updates = {
        "line_items": line_items,
        **totals,
        "is_discrepancy": disc["is_discrepancy"],
        "expected_amount": disc["expected_amount"],
        "actual_amount": disc["actual_amount"],
        "discrepancy_amount": disc["discrepancy_amount"],
        "discrepancy_status": "pending" if disc["is_discrepancy"] else "corrected",
        "discrepancy_reviewed_by": user.get("id", ""),
        "discrepancy_reviewed_by_name": user.get("name", ""),
        "discrepancy_reviewed_at": now,
        "discrepancy_review_note": note,
        "updated_at": now,
        "updated_by_name": user.get("name", ""),
    }
    if not disc["is_discrepancy"]:
        updates["discrepancy_reason"] = ""  # cleared since mismatch resolved
    await db.gst_invoices.update_one({"id": invoice_id}, {"$set": updates})
    await log_audit(user.get("id", ""), user.get("name", ""), "discrepancy_correct", "gst_invoice",
                    invoice_id, f"{existing.get('invoice_number')} | corrected to ₹{totals['grand_total']} | new diff ₹{disc['discrepancy_amount']} | note: {note}")
    return await db.gst_invoices.find_one({"id": invoice_id}, {"_id": 0})


# ============ PARTY LEDGER ============
@router.get("/gst/party-ledger")
async def party_ledger(
    customer_id: Optional[str] = None,
    customer_phone: Optional[str] = None,
    customer_name: Optional[str] = None,
    period: Optional[str] = None,        # all | today | this_month | this_year | custom
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    warehouse_ids: Optional[str] = None,
    user: dict = Depends(require_admin),
):
    """Per-customer ledger of all GST invoices with payment breakdown + totals.

    Resolution rules (one of these must be provided):
    - customer_id   : exact match on invoice.customer_id
    - customer_phone: exact match on invoice.customer_phone
    - customer_name : case-insensitive prefix match on invoice.customer_name

    Response: {rows, totals, customer} — rows are sorted latest-first.
    """
    if not (customer_id or customer_phone or customer_name):
        raise HTTPException(status_code=400, detail="One of customer_id / customer_phone / customer_name is required")

    q: Dict[str, Any] = {"status": {"$ne": "cancelled"}}
    apply_warehouse_filter(q, warehouse_ids, user)
    if customer_id:
        q["customer_id"] = customer_id
    elif customer_phone:
        q["customer_phone"] = customer_phone.strip()
    else:
        q["customer_name"] = {"$regex": f"^{re.escape(customer_name.strip())}", "$options": "i"}

    # Period filters
    today = datetime.now(timezone.utc).date()
    period_lc = (period or "").lower()
    if period_lc == "today":
        q["invoice_date"] = {"$gte": today.isoformat(), "$lte": today.isoformat()}
    elif period_lc == "this_month":
        from calendar import monthrange
        _, last = monthrange(today.year, today.month)
        q["invoice_date"] = {"$gte": f"{today.year}-{today.month:02d}-01",
                             "$lte": f"{today.year}-{today.month:02d}-{last:02d}"}
    elif period_lc == "this_year":
        q["invoice_date"] = {"$gte": f"{today.year}-01-01",
                             "$lte": f"{today.year}-12-31"}
    elif start_date or end_date:
        q["invoice_date"] = {}
        if start_date:
            q["invoice_date"]["$gte"] = start_date
        if end_date:
            q["invoice_date"]["$lte"] = end_date
    # period == 'all' or empty → no date filter

    invs = await db.gst_invoices.find(q, {"_id": 0}).sort([("invoice_date", -1), ("created_at", -1)]).to_list(20000)

    rows: List[dict] = []
    t_inv_total = 0.0
    t_taxable = 0.0
    t_gst = 0.0
    t_cash = 0.0
    t_online = 0.0
    t_paid = 0.0
    t_pending = 0.0
    for inv in invs:
        sub = float(inv.get("sub_total") or 0)
        gst = float(inv.get("total_gst") or 0)
        grand = float(inv.get("grand_total") or 0)
        cash = float(inv.get("cash_received") or 0)
        online = float(inv.get("online_received") or 0)
        paid = round(cash + online, 2)
        pending = float(inv.get("pending_amount") if inv.get("pending_amount") is not None
                         else max(0.0, grand - paid))
        rows.append({
            "id": inv.get("id"),
            "memo_no": inv.get("memo_no") or inv.get("invoice_number"),
            "invoice_number": inv.get("invoice_number"),
            "invoice_date": inv.get("invoice_date"),
            "created_at": inv.get("created_at"),
            "invoice_type": (inv.get("bill_type") or "manual").replace("_", " "),
            "taxable_amount": round(sub, 2),
            "gst_amount": round(gst, 2),
            "total_invoice_amount": round(grand, 2),
            "cash_received": round(cash, 2),
            "online_received": round(online, 2),
            "total_paid": paid,
            "pending_balance": round(pending, 2),
            "payment_status": inv.get("payment_status") or "",
            "created_by": inv.get("created_by_name") or "",
        })
        t_inv_total += grand
        t_taxable += sub
        t_gst += gst
        t_cash += cash
        t_online += online
        t_paid += paid
        t_pending += pending

    totals = {
        "count": len(rows),
        "total_invoice_value": round(t_inv_total, 2),
        "total_taxable": round(t_taxable, 2),
        "total_gst": round(t_gst, 2),
        "total_cash_received": round(t_cash, 2),
        "total_online_received": round(t_online, 2),
        "total_paid": round(t_paid, 2),
        "total_pending_balance": round(t_pending, 2),
    }

    # Resolve the customer header info from the latest invoice if present
    customer_header = {}
    if invs:
        customer_header = {
            "customer_id": invs[0].get("customer_id") or "",
            "customer_name": invs[0].get("customer_name") or "",
            "customer_phone": invs[0].get("customer_phone") or "",
            "customer_address": invs[0].get("customer_address") or "",
            "customer_gstin": invs[0].get("customer_gstin") or "",
        }
    return {"rows": rows, "totals": totals, "customer": customer_header}


@router.get("/gst/party-ledger/customers")
async def party_ledger_customers(warehouse_ids: Optional[str] = None, user: dict = Depends(require_admin)):
    """Distinct customers that have at least one non-cancelled invoice. Used to
    populate the customer picker in the Party Ledger tab. Respects warehouse filter."""
    match: Dict[str, Any] = {"status": {"$ne": "cancelled"}}
    apply_warehouse_filter(match, warehouse_ids, user)
    pipeline = [
        {"$match": match},
        {"$group": {
            "_id": {"name": "$customer_name", "phone": "$customer_phone"},
            "customer_id": {"$first": "$customer_id"},
            "last_invoice_date": {"$max": "$invoice_date"},
            "invoice_count": {"$sum": 1},
        }},
        {"$sort": {"last_invoice_date": -1}},
        {"$limit": 2000},
    ]
    rows = await db.gst_invoices.aggregate(pipeline).to_list(2000)
    out = []
    for r in rows:
        out.append({
            "customer_id": r.get("customer_id") or "",
            "customer_name": (r["_id"].get("name") or "").strip(),
            "customer_phone": (r["_id"].get("phone") or "").strip(),
            "last_invoice_date": r.get("last_invoice_date"),
            "invoice_count": r.get("invoice_count", 0),
        })
    return out


# ============ WAREHOUSE-WISE SUMMARY ============
@router.get("/gst/warehouse-summary")
async def warehouse_summary(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    warehouse_ids: Optional[str] = None,
    user: dict = Depends(require_admin),
):
    """Per-warehouse aggregated 8-metric grid:
    total_invoices, total_sales (grand_total sum), taxable_value, gst_collected,
    cash_collections, online_collections, pending_amount, discrepancy_count.
    Returns rows sorted by total_sales DESC + a grand-total row."""
    match: Dict[str, Any] = {"status": {"$ne": "cancelled"}}
    apply_warehouse_filter(match, warehouse_ids, user)
    if start_date:
        match.setdefault("invoice_date", {})["$gte"] = start_date
    if end_date:
        match.setdefault("invoice_date", {})["$lte"] = end_date

    # Also load all active warehouses so an admin can see zero-row warehouses
    all_wh = await db.warehouses.find({}, {"_id": 0}).sort("name", 1).to_list(500)
    wh_map = {w["id"]: w for w in all_wh}

    pipeline = [
        {"$match": match},
        {"$group": {
            "_id": "$warehouse_id",
            "warehouse_name": {"$first": "$warehouse_name"},
            "total_invoices": {"$sum": 1},
            "total_sales": {"$sum": "$grand_total"},
            "taxable_value": {"$sum": "$sub_total"},
            "gst_collected": {"$sum": "$total_gst"},
            "cash_collections": {"$sum": "$cash_received"},
            "online_collections": {"$sum": "$online_received"},
            "pending_amount": {"$sum": "$pending_amount"},
            "discrepancy_count": {"$sum": {"$cond": ["$is_discrepancy", 1, 0]}},
        }},
    ]
    rows_agg = await db.gst_invoices.aggregate(pipeline).to_list(500)
    by_id = {r["_id"] or "": r for r in rows_agg}

    # Admin sees ALL warehouses (including zero-row); non-admin only their own
    role = (user or {}).get("role", "").lower()
    is_admin = role in ("admin", "super_admin", "master_admin")
    if is_admin:
        base_wh_ids = list(wh_map.keys())
        if warehouse_ids:
            allowed = {w.strip() for w in warehouse_ids.split(",") if w.strip()}
            base_wh_ids = [wid for wid in base_wh_ids if wid in allowed]
    else:
        own = user.get("warehouse_id") or ""
        base_wh_ids = [own] if own else []

    def _round(v):
        try:
            return round(float(v or 0), 2)
        except (TypeError, ValueError):
            return 0.0

    rows: List[dict] = []
    for wid in base_wh_ids:
        wh = wh_map.get(wid) or {}
        agg = by_id.get(wid, {})
        rows.append({
            "warehouse_id": wid,
            "warehouse_name": wh.get("name") or agg.get("warehouse_name") or "(unknown)",
            "warehouse_code": wh.get("code") or "",
            "is_plant": bool(wh.get("is_plant", False)),
            "total_invoices": int(agg.get("total_invoices", 0)),
            "total_sales": _round(agg.get("total_sales", 0)),
            "taxable_value": _round(agg.get("taxable_value", 0)),
            "gst_collected": _round(agg.get("gst_collected", 0)),
            "cash_collections": _round(agg.get("cash_collections", 0)),
            "online_collections": _round(agg.get("online_collections", 0)),
            "pending_amount": _round(agg.get("pending_amount", 0)),
            "discrepancy_count": int(agg.get("discrepancy_count", 0)),
        })
    # Include any invoices with warehouse_id NOT in wh_map (orphaned/legacy) — group as one bucket
    orphaned = {wid: agg for wid, agg in by_id.items() if wid and wid not in wh_map and (not is_admin or (not warehouse_ids or wid in {w.strip() for w in (warehouse_ids or '').split(',')}))}
    for wid, agg in orphaned.items():
        rows.append({
            "warehouse_id": wid,
            "warehouse_name": agg.get("warehouse_name") or "(unassigned)",
            "warehouse_code": "",
            "is_plant": False,
            "total_invoices": int(agg.get("total_invoices", 0)),
            "total_sales": _round(agg.get("total_sales", 0)),
            "taxable_value": _round(agg.get("taxable_value", 0)),
            "gst_collected": _round(agg.get("gst_collected", 0)),
            "cash_collections": _round(agg.get("cash_collections", 0)),
            "online_collections": _round(agg.get("online_collections", 0)),
            "pending_amount": _round(agg.get("pending_amount", 0)),
            "discrepancy_count": int(agg.get("discrepancy_count", 0)),
        })

    rows.sort(key=lambda r: r["total_sales"], reverse=True)
    totals = {
        "total_invoices": sum(r["total_invoices"] for r in rows),
        "total_sales": _round(sum(r["total_sales"] for r in rows)),
        "taxable_value": _round(sum(r["taxable_value"] for r in rows)),
        "gst_collected": _round(sum(r["gst_collected"] for r in rows)),
        "cash_collections": _round(sum(r["cash_collections"] for r in rows)),
        "online_collections": _round(sum(r["online_collections"] for r in rows)),
        "pending_amount": _round(sum(r["pending_amount"] for r in rows)),
        "discrepancy_count": sum(r["discrepancy_count"] for r in rows),
    }
    return {"rows": rows, "totals": totals}


@router.get("/gst/warehouse-summary/excel")
async def warehouse_summary_excel(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    warehouse_ids: Optional[str] = None,
    user: dict = Depends(require_admin),
):
    """Branded workbook: Sheet 1 = grand totals + per-warehouse KPI table.
    Sheets 2..N = one detail sheet per warehouse listing its invoices."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from export_helpers import get_company_info_for_export, embed_logo_openpyxl, cleanup_logo_tempfile

    # 1) Aggregate summary (reuse the same query as warehouse_summary)
    match: Dict[str, Any] = {"status": {"$ne": "cancelled"}}
    apply_warehouse_filter(match, warehouse_ids, user)
    if start_date:
        match.setdefault("invoice_date", {})["$gte"] = start_date
    if end_date:
        match.setdefault("invoice_date", {})["$lte"] = end_date

    all_wh = await db.warehouses.find({}, {"_id": 0}).sort("name", 1).to_list(500)
    wh_map = {w["id"]: w for w in all_wh}

    role = (user or {}).get("role", "").lower()
    is_admin = role in ("admin", "super_admin", "master_admin")
    if is_admin:
        base_wh_ids = list(wh_map.keys())
        if warehouse_ids:
            allowed = {w.strip() for w in warehouse_ids.split(",") if w.strip()}
            base_wh_ids = [wid for wid in base_wh_ids if wid in allowed]
    else:
        own = user.get("warehouse_id") or ""
        base_wh_ids = [own] if own else []

    invoices = await db.gst_invoices.find(match, {"_id": 0}).sort([("warehouse_name", 1), ("invoice_date", -1)]).to_list(200000)

    # Group invoices by warehouse
    by_wh_invoices: Dict[str, List[dict]] = {}
    for inv in invoices:
        wid = inv.get("warehouse_id") or ""
        by_wh_invoices.setdefault(wid, []).append(inv)

    def _r(v):
        try:
            return round(float(v or 0), 2)
        except (TypeError, ValueError):
            return 0.0

    # Build per-warehouse KPI rows
    kpi_rows: List[dict] = []
    for wid in base_wh_ids:
        wh = wh_map.get(wid) or {}
        wh_invs = by_wh_invoices.get(wid, [])
        kpi_rows.append({
            "warehouse_id": wid,
            "warehouse_name": wh.get("name") or "(unknown)",
            "warehouse_code": wh.get("code") or "",
            "is_plant": bool(wh.get("is_plant", False)),
            "total_invoices": len(wh_invs),
            "total_sales": _r(sum(i.get("grand_total") or 0 for i in wh_invs)),
            "taxable_value": _r(sum(i.get("sub_total") or 0 for i in wh_invs)),
            "gst_collected": _r(sum(i.get("total_gst") or 0 for i in wh_invs)),
            "cash_collections": _r(sum(i.get("cash_received") or 0 for i in wh_invs)),
            "online_collections": _r(sum(i.get("online_received") or 0 for i in wh_invs)),
            "pending_amount": _r(sum(i.get("pending_amount") or 0 for i in wh_invs)),
            "discrepancy_count": sum(1 for i in wh_invs if i.get("is_discrepancy")),
        })

    # Orphaned invoices (warehouse_id not in wh_map) - included when admin
    orphaned_ids = [wid for wid in by_wh_invoices.keys() if wid and wid not in wh_map]
    if is_admin:
        if warehouse_ids:
            allowed_set = {w.strip() for w in warehouse_ids.split(",") if w.strip()}
            orphaned_ids = [wid for wid in orphaned_ids if wid in allowed_set]
        for wid in orphaned_ids:
            wh_invs = by_wh_invoices.get(wid, [])
            kpi_rows.append({
                "warehouse_id": wid,
                "warehouse_name": (wh_invs[0].get("warehouse_name") if wh_invs else "") or "(unassigned)",
                "warehouse_code": "",
                "is_plant": False,
                "total_invoices": len(wh_invs),
                "total_sales": _r(sum(i.get("grand_total") or 0 for i in wh_invs)),
                "taxable_value": _r(sum(i.get("sub_total") or 0 for i in wh_invs)),
                "gst_collected": _r(sum(i.get("total_gst") or 0 for i in wh_invs)),
                "cash_collections": _r(sum(i.get("cash_received") or 0 for i in wh_invs)),
                "online_collections": _r(sum(i.get("online_received") or 0 for i in wh_invs)),
                "pending_amount": _r(sum(i.get("pending_amount") or 0 for i in wh_invs)),
                "discrepancy_count": sum(1 for i in wh_invs if i.get("is_discrepancy")),
            })

    kpi_rows.sort(key=lambda r: r["total_sales"], reverse=True)

    # 2) Build the workbook
    wb = Workbook()
    thin = Side(style="thin", color="BBBBBB")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    period = f"{start_date or 'All'} to {end_date or 'All'}"
    company = await get_company_info_for_export()

    # Sheet 1: Summary
    ws = wb.active
    ws.title = "Summary"
    headers1 = [
        ("Warehouse", "warehouse_name"),
        ("Code", "warehouse_code"),
        ("Invoices", "total_invoices"),
        ("Total Sales", "total_sales"),
        ("Taxable Value", "taxable_value"),
        ("GST Collected", "gst_collected"),
        ("Cash Received", "cash_collections"),
        ("Online Received", "online_collections"),
        ("Pending", "pending_amount"),
        ("Discrepancies", "discrepancy_count"),
    ]
    last_col1 = get_column_letter(len(headers1))
    logo_path = embed_logo_openpyxl(ws, company,
                                     title="GST Warehouse-wise Summary",
                                     period=period,
                                     last_col_letter=last_col1)

    header_row = 5
    for c_idx, (lbl, _key) in enumerate(headers1, 1):
        cell = ws.cell(row=header_row, column=c_idx, value=lbl)
        cell.font = Font(bold=True, color="FFFFFF", size=10)
        cell.fill = PatternFill("solid", fgColor="1E5A8C")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = border

    r = header_row + 1
    for row in kpi_rows:
        for c_idx, (_lbl, key) in enumerate(headers1, 1):
            cell = ws.cell(row=r, column=c_idx, value=row.get(key, ""))
            cell.border = border
            cell.font = Font(size=9)
            if key in ("total_sales", "taxable_value", "gst_collected", "cash_collections", "online_collections", "pending_amount"):
                cell.number_format = "#,##0.00"
                cell.alignment = Alignment(horizontal="right")
            elif key in ("total_invoices", "discrepancy_count"):
                cell.alignment = Alignment(horizontal="center")
            else:
                cell.alignment = Alignment(horizontal="left")
        r += 1

    # Totals row
    if kpi_rows:
        for c_idx, (_lbl, key) in enumerate(headers1, 1):
            cell = ws.cell(row=r, column=c_idx)
            cell.fill = PatternFill("solid", fgColor="E0EDDF")
            cell.font = Font(bold=True, size=10)
            cell.border = border
            if c_idx == 1:
                cell.value = "GRAND TOTAL"
                cell.alignment = Alignment(horizontal="right")
            elif key in ("total_sales", "taxable_value", "gst_collected", "cash_collections", "online_collections", "pending_amount"):
                cell.value = round(sum(row[key] for row in kpi_rows), 2)
                cell.number_format = "#,##0.00"
                cell.alignment = Alignment(horizontal="right")
            elif key in ("total_invoices", "discrepancy_count"):
                cell.value = sum(row[key] for row in kpi_rows)
                cell.alignment = Alignment(horizontal="center")

    ws.freeze_panes = f"A{header_row + 1}"
    ws.auto_filter.ref = f"A{header_row}:{last_col1}{r}"
    widths = [26, 10, 10, 16, 16, 15, 15, 15, 14, 13]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # Sheets 2..N: One per warehouse (only for warehouses that have invoices)
    detail_headers = [
        ("Invoice No.", "invoice_number", "left"),
        ("Memo No.", "memo_no", "left"),
        ("Date", "invoice_date", "center"),
        ("Customer", "customer_name", "left"),
        ("Mobile", "customer_phone", "left"),
        ("Type", "bill_type", "center"),
        ("Sub Total", "sub_total", "amount"),
        ("Total GST", "total_gst", "amount"),
        ("Grand Total", "grand_total", "amount"),
        ("Cash", "cash_received", "amount"),
        ("Online", "online_received", "amount"),
        ("Pending", "pending_amount", "amount"),
        ("Payment Status", "payment_status", "center"),
        ("Status", "status", "center"),
    ]
    last_col2 = get_column_letter(len(detail_headers))

    for kpi in kpi_rows:
        wh_invs = by_wh_invoices.get(kpi["warehouse_id"], [])
        if not wh_invs:
            continue
        sheet_name = (kpi["warehouse_name"] or "Warehouse")[:31].replace("/", "-").replace("\\", "-")
        # Avoid duplicate names
        base = sheet_name
        suffix_n = 2
        while sheet_name in wb.sheetnames:
            sheet_name = f"{base[:28]}_{suffix_n}"
            suffix_n += 1
        ws2 = wb.create_sheet(sheet_name)
        embed_logo_openpyxl(ws2, company,
                             title=f"{kpi['warehouse_name']} - Invoices",
                             period=period,
                             last_col_letter=last_col2)
        for c_idx, (lbl, _key, _align) in enumerate(detail_headers, 1):
            cell = ws2.cell(row=header_row, column=c_idx, value=lbl)
            cell.font = Font(bold=True, color="FFFFFF", size=10)
            cell.fill = PatternFill("solid", fgColor="1E5A8C")
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = border

        rr = header_row + 1
        for inv in wh_invs:
            for c_idx, (_lbl, key, align) in enumerate(detail_headers, 1):
                v = inv.get(key, "")
                cell = ws2.cell(row=rr, column=c_idx, value=v)
                cell.border = border
                cell.font = Font(size=9)
                if align == "amount" and isinstance(v, (int, float)):
                    cell.number_format = "#,##0.00"
                    cell.alignment = Alignment(horizontal="right")
                elif align == "center":
                    cell.alignment = Alignment(horizontal="center")
                else:
                    cell.alignment = Alignment(horizontal="left", wrap_text=True)
            rr += 1
        # Totals row per sheet
        for c_idx, (_lbl, key, align) in enumerate(detail_headers, 1):
            cell = ws2.cell(row=rr, column=c_idx)
            cell.fill = PatternFill("solid", fgColor="E0EDDF")
            cell.font = Font(bold=True, size=10)
            cell.border = border
            if c_idx == 1:
                cell.value = "TOTAL"
                cell.alignment = Alignment(horizontal="right")
            elif align == "amount":
                total = round(sum(float(i.get(key) or 0) for i in wh_invs), 2)
                cell.value = total
                cell.number_format = "#,##0.00"
                cell.alignment = Alignment(horizontal="right")

        ws2.freeze_panes = f"A{header_row + 1}"
        ws2.auto_filter.ref = f"A{header_row}:{last_col2}{rr}"
        col_widths = [18, 14, 12, 24, 14, 14, 12, 12, 14, 12, 12, 12, 14, 12]
        for i, w in enumerate(col_widths, 1):
            ws2.column_dimensions[get_column_letter(i)].width = w
        ws2.page_setup.orientation = ws2.ORIENTATION_LANDSCAPE

    buf = BytesIO()
    wb.save(buf)
    cleanup_logo_tempfile(logo_path)
    buf.seek(0)
    fname = f"Warehouse_Summary_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.xlsx"
    return StreamingResponse(iter([buf.read()]),
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f'attachment; filename="{fname}"'})


@router.post("/gst/invoices/backfill-payments")
async def backfill_payments(user: dict = Depends(require_admin)):
    """One-time admin maintenance: backfill memo_no + cash_received + online_received +
    payment_status on historical invoices. Source of truth: the linked sales_entry or
    accessory_sale via sale_id. Idempotent."""
    updated = 0
    skipped = 0
    cursor = db.gst_invoices.find({"status": {"$ne": "cancelled"}, "$or": [
        {"payment_status": {"$in": [None, ""]}},
        {"memo_no": {"$in": [None, ""]}},
    ]}, {"_id": 0})
    async for inv in cursor:
        try:
            sale_id = inv.get("sale_id")
            sale_type = inv.get("sale_type")
            memo_no = inv.get("memo_no") or ""
            cash = float(inv.get("cash_received") or 0)
            online = float(inv.get("online_received") or 0)
            if sale_id and not (memo_no and (cash + online) > 0):
                if sale_type == "sales_entry":
                    sale = await db.sales_entries.find_one({"id": sale_id}, {"_id": 0})
                    if sale:
                        memo_no = memo_no or sale.get("memo_no") or ""
                        cash = float(sale.get("cash_amount") or 0)
                        online = float(sale.get("online_amount") or 0)
                elif sale_type == "accessory_sale":
                    sale = await db.accessory_sales.find_one({"id": sale_id}, {"_id": 0})
                    if sale:
                        memo_no = memo_no or sale.get("memo_no") or ""
                        grand_for_split = float(sale.get("grand_total") or sale.get("amount") or 0)
                        pm = (sale.get("payment_mode") or "cash").lower()
                        if pm == "online":
                            online = grand_for_split
                        elif pm == "pending":
                            pass
                        else:
                            cash = grand_for_split
            memo_no = memo_no or inv.get("invoice_number")  # final fallback
            pay = compute_payment_fields(float(inv.get("grand_total") or 0), cash, online)
            await db.gst_invoices.update_one({"id": inv["id"]}, {"$set": {
                "memo_no": memo_no,
                **pay,
            }})
            updated += 1
        except (TypeError, ValueError, KeyError):
            skipped += 1
    await log_audit(user.get("id", ""), user.get("name", ""), "backfill_payments", "gst_invoice", "",
                    f"updated={updated} skipped={skipped}")
    return {"updated": updated, "skipped": skipped}



@router.post("/gst/invoices/{invoice_id}/cancel")
async def cancel_invoice(invoice_id: str, data: dict = None, user: dict = Depends(require_admin)):
    res = await db.gst_invoices.update_one(
        {"id": invoice_id},
        {"$set": {
            "status": "cancelled",
            "cancelled_at": datetime.now(timezone.utc).isoformat(),
            "cancelled_by_name": user.get("name", ""),
            "cancellation_reason": (data or {}).get("reason", ""),
        }}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Invoice not found")
    await log_audit(user.get("id", ""), user.get("name", ""), "cancel", "gst_invoice", invoice_id,
                    (data or {}).get("reason", ""))
    return {"message": "Invoice cancelled"}


@router.delete("/gst/invoices/{invoice_id}")
async def delete_invoice(invoice_id: str, user: dict = Depends(require_admin)):
    res = await db.gst_invoices.delete_one({"id": invoice_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Invoice not found")
    await log_audit(user.get("id", ""), user.get("name", ""), "delete", "gst_invoice", invoice_id, "")
    return {"message": "Invoice deleted"}


# ============ AUTO-GEN HOOK (called from sales.py / accessories.py for NEW entries) ============
async def _auto_generate_invoice(sale: dict, sale_type: str, user: dict) -> Optional[dict]:
    """Best-effort: generate active GST invoice from a freshly-created sale.
    Used as a non-blocking hook - failures swallowed and logged.
    sale_type: 'sales_entry' or 'accessory_sale'
    Note: Plant warehouse sales are NOT invoiced (plant operations are internal).
    """
    try:
        await ensure_seed()
        # Skip Plant warehouse sales entirely (no customer invoice for internal plant ops)
        wh_name = (sale.get("warehouse_name") or "").lower()
        if "plant" in wh_name or "hollongi" in wh_name:
            return None
        cfg = await db.gst_config.find_one({"key": "gst_config"}) or {}
        if not cfg.get("auto_generate", True):
            return None
        tax_mode = cfg.get("default_tax_mode", "intra_state")

        # Skip if invoice already linked to this sale
        existing = await db.gst_invoices.find_one(
            {"sale_id": sale.get("id"), "sale_type": sale_type, "status": "active"}
        )
        if existing:
            return None

        line_items: List[dict] = []
        bill_type = ""
        cust_name = ""
        cust_phone = ""
        cust_addr = ""
        payment_mode = sale.get("payment_mode", "cash")
        invoice_date = sale.get("date")

        if sale_type == "sales_entry":
            ct = sale.get("connection_type", "")
            is_refill = "refill" in ct
            is_commercial = "commercial" in ct
            cust_name = sale.get("consumer_name") or ""
            cust_addr = sale.get("address") or ""

            if is_refill:
                # Refills stay single-line (per agreed business rule)
                item_name = "Commercial LPG Refill" if is_commercial else "Domestic LPG Refill"
                qty = int(sale.get("no_of_refills", 0) or 0) or 1
                amount = float(sale.get("amount") or 0)
                if amount <= 0 or qty <= 0:
                    return None
                rate = round(amount / qty, 2)
                gst_item = await db.gst_items.find_one({"name": item_name}, {"_id": 0})
                gst_rate = float(gst_item.get("gst_rate") if gst_item else 5)
                hsn = gst_item.get("hsn") if gst_item else "271119"
                unit = gst_item.get("unit") if gst_item else "Cylinder"
                taxable_per_unit = round(rate * 100.0 / (100.0 + gst_rate), 2)
                line_items.append({
                    "item_name": item_name,
                    "hsn": hsn,
                    "unit": unit,
                    "gst_rate": gst_rate,
                    "quantity": qty,
                    "rate": taxable_per_unit,
                })
                bill_type = "refill"
            else:
                # NEW CONNECTION: try plan-based itemized billing
                cyl = str(sale.get("cylinder_nos", "")).strip()
                try:
                    cyl_count = int(cyl) if cyl else 1
                except ValueError:
                    cyl_count = max(1, len([p for p in cyl.split(",") if p.strip()]))
                amount = float(sale.get("amount") or 0)
                if amount <= 0 or cyl_count <= 0:
                    return None

                has_accessories = bool(sale.get("has_accessories"))  # set explicitly from sales form
                plan_id = sale.get("connection_plan_id")
                plan: Optional[dict] = None
                if plan_id:
                    plan = await db.gst_plans.find_one({"id": plan_id, "is_active": True}, {"_id": 0})
                if not plan:
                    plans = await db.gst_plans.find({"is_active": True}, {"_id": 0}).to_list(200)
                    plan = _match_plan_for_sale(plans, ct, cyl_count, has_accessories)

                # Only use plan if every item has a unit_price > 0 (admin has configured rates)
                if plan and plan.get("items") and all(float(it.get("unit_price") or 0) > 0 for it in plan["items"]):
                    for it in plan["items"]:
                        line_items.append({
                            "item_name": it["item_name"],
                            "hsn": it.get("hsn", ""),
                            "unit": it.get("unit", "Nos"),
                            "gst_rate": float(it.get("gst_rate") or 0),
                            "quantity": float(it.get("quantity") or 0),
                            "rate": float(it.get("unit_price") or 0),
                        })
                else:
                    # Fallback: single-line invoice using sale amount as inclusive total
                    item_name = "Commercial New Connection" if is_commercial else "Domestic New Connection"
                    rate = round(amount / cyl_count, 2)
                    gst_item = await db.gst_items.find_one({"name": item_name}, {"_id": 0})
                    gst_rate = float(gst_item.get("gst_rate") if gst_item else 18)
                    hsn = gst_item.get("hsn") if gst_item else "271119"
                    unit = gst_item.get("unit") if gst_item else "Cylinder"
                    taxable_per_unit = round(rate * 100.0 / (100.0 + gst_rate), 2)
                    line_items.append({
                        "item_name": item_name,
                        "hsn": hsn,
                        "unit": unit,
                        "gst_rate": gst_rate,
                        "quantity": cyl_count,
                        "rate": taxable_per_unit,
                    })
                bill_type = "new_connection"

        elif sale_type == "accessory_sale":
            items = sale.get("items") or []
            for it in items:
                acc_name = it.get("accessory_name", "")
                qty = float(it.get("quantity") or 0)
                rate = float(it.get("unit_price") or 0)
                if qty <= 0 or rate <= 0:
                    continue
                # Look up GST rate from gst_items by name match, default 18%
                gst_item = await db.gst_items.find_one(
                    {"name": {"$regex": f"^{re.escape(acc_name)}", "$options": "i"}}, {"_id": 0}
                )
                gst_rate = float(gst_item.get("gst_rate") if gst_item else 18)
                hsn = gst_item.get("hsn") if gst_item else "84812000"
                unit = gst_item.get("unit") if gst_item else "Nos"
                taxable_per_unit = round(rate * 100.0 / (100.0 + gst_rate), 2)
                line_items.append({
                    "item_name": acc_name,
                    "hsn": hsn,
                    "unit": unit,
                    "gst_rate": gst_rate,
                    "quantity": qty,
                    "rate": taxable_per_unit,
                })
            bill_type = "accessory"
            cust_name = sale.get("customer_name") or ""
            cust_phone = sale.get("customer_phone") or ""
            cust_addr = sale.get("customer_address") or ""

        if not line_items:
            return None

        # For accessory sales (payment_mode-driven), derive per-mode amounts so
        # the invoice's cash_received / online_received / pending fields reflect reality.
        sale_cash = float(sale.get("cash_amount") or 0)
        sale_online = float(sale.get("online_amount") or 0)
        if sale_type == "accessory_sale" and (sale_cash + sale_online) == 0:
            grand_for_split = float(sale.get("grand_total") or sale.get("amount") or 0)
            pm = (sale.get("payment_mode") or "cash").lower()
            if pm == "online":
                sale_online = grand_for_split
            elif pm == "pending":
                pass  # both stay 0 → invoice gets payment_status='Pending'
            else:
                sale_cash = grand_for_split

        payload = {
            "sale_id": sale.get("id"),
            "sale_type": sale_type,
            "bill_type": bill_type,
            "customer_id": sale.get("customer_id") or "",
            "customer_name": cust_name,
            "customer_phone": cust_phone,
            "customer_address": cust_addr,
            "tax_mode": tax_mode,
            "payment_mode": payment_mode,
            "invoice_date": invoice_date,
            "line_items": line_items,
            "connection_plan_id": sale.get("connection_plan_id") or "",
            "warehouse_id": sale.get("warehouse_id", ""),
            "warehouse_name": sale.get("warehouse_name", ""),
            # Memo No from sale entry (consumer-facing receipt no)
            "memo_no": sale.get("memo_no") or "",
            # Propagate received-amounts from sale entry → invoice payment fields
            "cash_received": sale_cash,
            "online_received": sale_online,
            # Propagate discrepancy reason from the source sale (validated at sale-entry layer)
            "discrepancy_reason": sale.get("discrepancy_reason") or "",
        }
        return await create_invoice(payload, user)
    except Exception as e:
        logger.error(f"Auto-gen GST invoice failed: {e}")
        return None


# Public alias for use from other route modules
async def auto_generate_invoice_from_sale(sale: dict, sale_type: str, user: dict) -> Optional[dict]:
    return await _auto_generate_invoice(sale, sale_type, user)


async def rebuild_linked_invoice_from_sale(sale: dict, sale_type: str, user: dict) -> Optional[dict]:
    """Called when a sale is EDITED. Rebuilds the customer/line-item/payment fields
    of the linked active GST invoice in place — preserves invoice_number and id
    so downstream references stay valid. If no linked invoice exists (auto-gen
    was off at create time), generates a fresh one."""
    inv = await db.gst_invoices.find_one(
        {"sale_id": sale.get("id"), "sale_type": sale_type, "status": "active"},
        {"_id": 0},
    )
    if not inv:
        return await _auto_generate_invoice(sale, sale_type, user)

    # Rebuild line items using the same logic as _auto_generate_invoice for accessory sales
    line_items: List[dict] = []
    if sale_type == "accessory_sale":
        for it in (sale.get("items") or []):
            acc_name = it.get("accessory_name", "")
            qty = float(it.get("quantity") or 0)
            rate = float(it.get("unit_price") or 0)
            if qty <= 0 or rate <= 0:
                continue
            gst_item = await db.gst_items.find_one(
                {"name": {"$regex": f"^{re.escape(acc_name)}", "$options": "i"}}, {"_id": 0}
            )
            gst_rate = float(gst_item.get("gst_rate") if gst_item else 18)
            hsn = gst_item.get("hsn") if gst_item else "84812000"
            unit = gst_item.get("unit") if gst_item else "Nos"
            taxable_per_unit = round(rate * 100.0 / (100.0 + gst_rate), 2)
            line_items.append({
                "item_name": acc_name,
                "hsn": hsn,
                "unit": unit,
                "gst_rate": gst_rate,
                "quantity": qty,
                "rate": taxable_per_unit,
            })
    if not line_items:
        return None

    cfg = await db.gst_config.find_one({"key": "gst_config"}) or {}
    tax_mode = (inv.get("tax_mode") or cfg.get("default_tax_mode") or "intra_state").lower()
    totals = compute_totals(line_items, tax_mode)

    # Derive per-mode cash/online for accessory sales the same way _auto_generate does
    sale_cash = float(sale.get("cash_amount") or 0)
    sale_online = float(sale.get("online_amount") or 0)
    if sale_type == "accessory_sale" and (sale_cash + sale_online) == 0:
        grand_for_split = float(sale.get("grand_total") or sale.get("amount") or totals.get("grand_total") or 0)
        pm = (sale.get("payment_mode") or "cash").lower()
        if pm == "online":
            sale_online = grand_for_split
        elif pm == "pending":
            pass
        else:
            sale_cash = grand_for_split

    pay = compute_payment_fields(totals["grand_total"], sale_cash, sale_online,
                                 sale.get("payment_mode") or inv.get("payment_mode"))
    update = {
        "customer_name": sale.get("customer_name") or inv.get("customer_name") or "",
        "customer_phone": sale.get("customer_phone") or inv.get("customer_phone") or "",
        "customer_address": sale.get("customer_address") or inv.get("customer_address") or "",
        "memo_no": sale.get("memo_no") or inv.get("memo_no") or "",
        "invoice_date": sale.get("date") or inv.get("invoice_date"),
        "line_items": line_items,
        "sub_total": totals["sub_total"],
        "total_gst": totals["total_gst"],
        "total_cgst": totals.get("total_cgst", 0),
        "total_sgst": totals.get("total_sgst", 0),
        "total_igst": totals.get("total_igst", 0),
        "grand_total": totals["grand_total"],
        "cash_received": pay["cash_received"],
        "online_received": pay["online_received"],
        "pending_amount": pay["pending_amount"],
        "payment_status": pay["payment_status"],
        "payment_mode": sale.get("payment_mode") or inv.get("payment_mode"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.gst_invoices.update_one({"id": inv["id"]}, {"$set": update})
    return {**inv, **update}


async def cancel_linked_invoice_from_sale(sale_id: str, sale_type: str, user: dict) -> None:
    """When a sale is deleted, cancel any active auto-generated GST invoice
    linked to it so it disappears from active reports/ledgers."""
    inv = await db.gst_invoices.find_one(
        {"sale_id": sale_id, "sale_type": sale_type, "status": "active"},
        {"_id": 0, "id": 1},
    )
    if not inv:
        return
    await db.gst_invoices.update_one(
        {"id": inv["id"]},
        {"$set": {
            "status": "cancelled",
            "cancelled_at": datetime.now(timezone.utc).isoformat(),
            "cancelled_by": user.get("id") or "",
            "cancel_reason": f"Auto-cancelled: source {sale_type} deleted",
        }},
    )


# ============ PDF EXPORT (single invoice - Tax Invoice format) ============
@router.get("/gst/invoices/{invoice_id}/pdf")
async def export_invoice_pdf(invoice_id: str, user: dict = Depends(require_admin)):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, KeepTogether
    from reportlab.lib.units import mm
    from reportlab.lib.styles import ParagraphStyle
    import requests as _requests
    from io import BytesIO as _BIO

    inv = await db.gst_invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    cfg = await db.gst_config.find_one({"key": "gst_config"}, {"_id": 0}) or {}

    buf = BytesIO()
    PAGE_W = 210 * mm
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=10 * mm, rightMargin=10 * mm,
                             topMargin=10 * mm, bottomMargin=10 * mm,
                             title=f"Tax Invoice {inv['invoice_number']}")
    elements = []
    PRIMARY = colors.HexColor("#1E5A8C")
    LIGHT = colors.HexColor("#E8F1F8")

    style_company = ParagraphStyle("co", fontSize=16, leading=18, fontName="Helvetica-Bold", textColor=PRIMARY)
    style_addr = ParagraphStyle("ad", fontSize=8, leading=10, fontName="Helvetica")
    style_title = ParagraphStyle("ti", fontSize=12, alignment=1, fontName="Helvetica-Bold", textColor=PRIMARY)
    style_label = ParagraphStyle("lb", fontSize=8, fontName="Helvetica-Bold")
    style_body = ParagraphStyle("bd", fontSize=8, fontName="Helvetica", leading=10)
    style_small = ParagraphStyle("sm", fontSize=7, fontName="Helvetica", leading=9, textColor=colors.grey)

    # ---- HEADER: logo + company info ----
    logo_url = cfg.get("company_logo_url") or ""
    logo_cell = ""
    if logo_url:
        try:
            img_data = _requests.get(logo_url, timeout=5).content
            logo_cell = Image(_BIO(img_data), width=25 * mm, height=25 * mm)
        except Exception:
            logo_cell = ""
    company_info = [
        Paragraph(cfg.get("company_name", "K3 GAS SERVICE"), style_company),
    ]
    if cfg.get("company_tagline"):
        company_info.append(Paragraph(cfg["company_tagline"], style_addr))
    if cfg.get("company_address"):
        company_info.append(Paragraph(cfg["company_address"], style_addr))
    contact = " | ".join(filter(None, [cfg.get("company_phone"), cfg.get("company_email")]))
    if contact:
        company_info.append(Paragraph(contact, style_addr))
    if cfg.get("company_gstin"):
        company_info.append(Paragraph(f"<b>GSTIN:</b> {cfg['company_gstin']}    <b>State:</b> {cfg.get('company_state', '')} ({cfg.get('company_state_code', '')})", style_addr))

    header_tbl = Table([[logo_cell, company_info]], colWidths=[30 * mm, 160 * mm])
    header_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, 0), "CENTER"),
    ]))
    elements.append(header_tbl)
    elements.append(Spacer(1, 2 * mm))

    # Status banner
    is_cancelled = inv.get("status") == "cancelled"
    title_text = "TAX INVOICE"
    if is_cancelled:
        title_text = "TAX INVOICE — <font color='red'>CANCELLED</font>"
    title_tbl = Table([[Paragraph(title_text, style_title)]], colWidths=[PAGE_W - 20 * mm])
    title_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.7, PRIMARY),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(title_tbl)
    elements.append(Spacer(1, 3 * mm))

    # ---- INVOICE META + CUSTOMER BLOCK ----
    def _fmt_dt(s):
        if not s:
            return ""
        s = str(s).split("T")[0]
        parts = s.split("-")
        return f"{parts[2]}-{parts[1]}-{parts[0]}" if len(parts) == 3 else s

    meta_left = [
        [Paragraph("<b>Invoice No:</b>", style_label), Paragraph(inv["invoice_number"], style_body)],
        [Paragraph("<b>Memo No:</b>", style_label), Paragraph(inv.get("memo_no") or inv["invoice_number"], style_body)],
        [Paragraph("<b>Invoice Date:</b>", style_label), Paragraph(_fmt_dt(inv.get("invoice_date")), style_body)],
        [Paragraph("<b>Place of Supply:</b>", style_label), Paragraph(inv.get("place_of_supply") or cfg.get("place_of_supply", ""), style_body)],
        [Paragraph("<b>Tax Mode:</b>", style_label),
         Paragraph("Intra-state (CGST+SGST)" if inv.get("tax_mode") == "intra_state" else "Inter-state (IGST)", style_body)],
        [Paragraph("<b>Payment Mode:</b>", style_label),
         Paragraph((inv.get("payment_mode") or "").upper(), style_body)],
    ]
    meta_right = [
        [Paragraph("<b>Bill To:</b>", style_label), Paragraph(inv.get("customer_name") or "-", style_body)],
        [Paragraph("<b>Address:</b>", style_label), Paragraph(inv.get("customer_address") or "-", style_body)],
        [Paragraph("<b>Mobile:</b>", style_label), Paragraph(inv.get("customer_phone") or "-", style_body)],
        [Paragraph("<b>GSTIN:</b>", style_label), Paragraph(inv.get("customer_gstin") or "-", style_body)],
        [Paragraph("<b>Warehouse:</b>", style_label), Paragraph(inv.get("warehouse_name") or "-", style_body)],
    ]
    meta_left_tbl = Table(meta_left, colWidths=[28 * mm, 60 * mm])
    meta_right_tbl = Table(meta_right, colWidths=[22 * mm, 70 * mm])
    for t in (meta_left_tbl, meta_right_tbl):
        t.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
    customer_tbl = Table([[meta_left_tbl, meta_right_tbl]], colWidths=[(PAGE_W - 20 * mm) / 2, (PAGE_W - 20 * mm) / 2])
    customer_tbl.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(customer_tbl)
    elements.append(Spacer(1, 3 * mm))

    # ---- LINE ITEMS TABLE ----
    is_intra = inv.get("tax_mode") == "intra_state"
    if is_intra:
        headers = ["#", "Item Description", "HSN", "Unit", "Qty", "Rate", "Taxable",
                   "CGST%", "CGST Amt", "SGST%", "SGST Amt", "Total"]
        col_widths = [8, 50 * mm, 16 * mm, 12 * mm, 11 * mm, 16 * mm, 19 * mm, 11 * mm, 16 * mm, 11 * mm, 16 * mm, 18 * mm]
    else:
        headers = ["#", "Item Description", "HSN", "Unit", "Qty", "Rate", "Taxable",
                   "IGST%", "IGST Amt", "Total"]
        col_widths = [8, 60 * mm, 18 * mm, 14 * mm, 12 * mm, 18 * mm, 22 * mm, 14 * mm, 20 * mm, 22 * mm]

    rows = [[Paragraph(f"<b>{h}</b>", style_body) for h in headers]]
    for i, li in enumerate(inv["line_items"], 1):
        qty = li.get("quantity", 0)
        rate = li.get("rate", 0)
        taxable = li.get("taxable_value", 0)
        gst_rate = li.get("gst_rate", 0)
        if is_intra:
            row_data = [
                str(i),
                Paragraph(li.get("item_name", ""), style_body),
                str(li.get("hsn", "")),
                str(li.get("unit", "")),
                f"{qty:g}",
                format_inr(rate, use_symbol=False),
                format_inr(taxable, use_symbol=False),
                f"{gst_rate/2:g}%",
                format_inr(li.get("cgst", 0), use_symbol=False),
                f"{gst_rate/2:g}%",
                format_inr(li.get("sgst", 0), use_symbol=False),
                format_inr(li.get("line_total", 0), use_symbol=False),
            ]
        else:
            row_data = [
                str(i),
                Paragraph(li.get("item_name", ""), style_body),
                str(li.get("hsn", "")),
                str(li.get("unit", "")),
                f"{qty:g}",
                format_inr(rate, use_symbol=False),
                format_inr(taxable, use_symbol=False),
                f"{gst_rate:g}%",
                format_inr(li.get("igst", 0), use_symbol=False),
                format_inr(li.get("line_total", 0), use_symbol=False),
            ]
        rows.append(row_data)

    # Totals row
    if is_intra:
        rows.append([
            "", Paragraph("<b>TOTAL</b>", style_body), "", "", "", "",
            format_inr(inv["sub_total"], use_symbol=False),
            "", format_inr(inv["total_cgst"], use_symbol=False),
            "", format_inr(inv["total_sgst"], use_symbol=False),
            format_inr(inv["grand_total"], use_symbol=False),
        ])
    else:
        rows.append([
            "", Paragraph("<b>TOTAL</b>", style_body), "", "", "", "",
            format_inr(inv["sub_total"], use_symbol=False),
            "", format_inr(inv["total_igst"], use_symbol=False),
            format_inr(inv["grand_total"], use_symbol=False),
        ])

    items_tbl = Table(rows, colWidths=col_widths, repeatRows=1)
    items_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (4, 1), (-1, -2), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (2, 1), (4, -1), "CENTER"),
        ("BACKGROUND", (0, -1), (-1, -1), LIGHT),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("ALIGN", (-1, -1), (-1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(items_tbl)
    elements.append(Spacer(1, 3 * mm))

    # ---- TOTALS SUMMARY + AMOUNT IN WORDS ----
    grand = float(inv["grand_total"])
    round_off = float(inv.get("round_off") or 0)
    total_before_ro = float(inv.get("total_before_roundoff") or (grand - round_off))
    summary_data = [
        ["Sub Total:", f"Rs. {format_inr(inv['sub_total'], use_symbol=False)}"],
    ]
    if is_intra:
        summary_data.append(["Total CGST:", f"Rs. {format_inr(inv['total_cgst'], use_symbol=False)}"])
        summary_data.append(["Total SGST:", f"Rs. {format_inr(inv['total_sgst'], use_symbol=False)}"])
    else:
        summary_data.append(["Total IGST:", f"Rs. {format_inr(inv['total_igst'], use_symbol=False)}"])
    # Show Total before Round Off + Round Off rows only when round_off field exists on the invoice
    if "round_off" in inv:
        summary_data.append(["Total Before Round Off:", f"Rs. {format_inr(total_before_ro, use_symbol=False)}"])
        ro_sign = "+" if round_off >= 0 else "−"
        summary_data.append(["Round Off:", f"{ro_sign} Rs. {format_inr(abs(round_off), use_symbol=False)}"])
    summary_data.append([Paragraph("<b>Grand Total:</b>", style_label),
                         Paragraph(f"<b>Rs. {format_inr(grand, use_symbol=False)}</b>", style_label)])
    # Payment status block
    _cash = float(inv.get("cash_received") or 0)
    _online = float(inv.get("online_received") or 0)
    _pending = float(inv.get("pending_amount") or 0)
    _status = inv.get("payment_status") or ""
    if (_cash + _online + _pending) > 0 or _status:
        summary_data.append(["Cash Received:", f"Rs. {format_inr(_cash, use_symbol=False)}"])
        summary_data.append(["Online Received:", f"Rs. {format_inr(_online, use_symbol=False)}"])
        summary_data.append(["Pending Amount:", f"Rs. {format_inr(_pending, use_symbol=False)}"])
        summary_data.append([Paragraph("<b>Payment Status:</b>", style_label),
                             Paragraph(f"<b>{_status or '-'}</b>", style_label)])

    summary_tbl = Table(summary_data, colWidths=[35 * mm, 35 * mm])
    summary_tbl.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("BACKGROUND", (0, -1), (-1, -1), LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
        ("INNERGRID", (0, 0), (-1, -1), 0.2, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))

    # Amount in words
    words = amount_in_words_inr(grand)
    words_para = Paragraph(f"<b>Amount in Words:</b> {words}", style_body)
    words_tbl = Table([[words_para]], colWidths=[110 * mm])
    words_tbl.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    bottom = Table([[words_tbl, summary_tbl]], colWidths=[110 * mm, 80 * mm])
    bottom.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    elements.append(bottom)
    elements.append(Spacer(1, 3 * mm))

    # ---- BANK DETAILS + TERMS + SIGNATORY ----
    bank_lines = []
    if cfg.get("bank_name"):
        bank_lines.append(Paragraph("<b>Bank Details:</b>", style_label))
        bank_lines.append(Paragraph(f"<b>Bank:</b> {cfg.get('bank_name', '')}", style_body))
        if cfg.get("bank_account_holder"):
            bank_lines.append(Paragraph(f"<b>A/c Holder:</b> {cfg['bank_account_holder']}", style_body))
        if cfg.get("bank_account_no"):
            bank_lines.append(Paragraph(f"<b>A/c No:</b> {cfg['bank_account_no']}", style_body))
        if cfg.get("bank_ifsc"):
            bank_lines.append(Paragraph(f"<b>IFSC:</b> {cfg['bank_ifsc']}", style_body))
        if cfg.get("bank_branch"):
            bank_lines.append(Paragraph(f"<b>Branch:</b> {cfg['bank_branch']}", style_body))

    terms_text = cfg.get("terms_conditions") or ""
    terms_lines = [Paragraph("<b>Terms &amp; Conditions:</b>", style_label)]
    for line in str(terms_text).split("\n"):
        if line.strip():
            terms_lines.append(Paragraph(line.strip(), style_small))
    if inv.get("remarks"):
        terms_lines.append(Spacer(1, 2 * mm))
        terms_lines.append(Paragraph(f"<b>Remarks:</b> {inv['remarks']}", style_small))

    signatory_cell = [
        Spacer(1, 12 * mm),
        Paragraph(f"For <b>{cfg.get('company_name', 'K3 GAS SERVICE')}</b>", style_body),
        Spacer(1, 12 * mm),
        Paragraph(cfg.get("signatory_name", ""), style_body),
        Paragraph(f"<i>{cfg.get('signatory_designation', 'Authorized Signatory')}</i>", style_small),
    ]

    footer_tbl = Table([[bank_lines, terms_lines, signatory_cell]],
                       colWidths=[60 * mm, 75 * mm, 55 * mm])
    footer_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    elements.append(KeepTogether(footer_tbl))
    elements.append(Spacer(1, 3 * mm))
    elements.append(Paragraph(
        f"This is a computer-generated invoice. Generated on {datetime.now(timezone.utc).strftime('%d-%m-%Y %H:%M')} | "
        f"Subject to {cfg.get('company_state', 'Arunachal Pradesh')} jurisdiction.",
        ParagraphStyle("ft", fontSize=6, alignment=1, textColor=colors.grey)))

    doc.build(elements)
    buf.seek(0)
    fname = f"Invoice_{inv['invoice_number'].replace('/', '_')}.pdf"
    return Response(content=buf.read(), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})
