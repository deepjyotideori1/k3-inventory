"""
GST Billing module for the Inventory dashboard.
Stores invoices in a dedicated `gst_invoices` collection - separate from
sales/orders/accessory_sales, so legacy data is never touched. Auto-generates
an invoice when a NEW sales/accessory entry is created (via internal hook),
and exposes manual `Generate from sale` + full CRUD + cancellation flow.
Access: Admin only.
"""
from fastapi import APIRouter, HTTPException, Depends, Response, Query
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
    """Idempotent: seeds default items + plans + config if missing."""
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
                "items": [{**it, "unit_price": 0} for it in p["items"]],
                "created_at": now_iso,
            }
            for p in DEFAULT_PLANS
        ])
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
    grand_total = round(sub_total + total_cgst + total_sgst + total_igst, 2)
    return {
        "sub_total": round(sub_total, 2),
        "total_cgst": round(total_cgst, 2),
        "total_sgst": round(total_sgst, 2),
        "total_igst": round(total_igst, 2),
        "total_gst": round(total_cgst + total_sgst + total_igst, 2),
        "grand_total": grand_total,
    }


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
    await db.gst_config.update_one({"key": "gst_config"}, {"$set": updates}, upsert=True)
    await log_audit(user.get("id", ""), user.get("name", ""), "update", "gst_config", "",
                    f"Updated: {','.join(updates.keys())}")
    cfg = await db.gst_config.find_one({"key": "gst_config"}, {"_id": 0})
    return cfg


# ============ ITEM MASTER ============
@router.get("/gst/items")
async def list_items(user: dict = Depends(require_admin)):
    await ensure_seed()
    items = await db.gst_items.find({}, {"_id": 0}).sort("name", 1).to_list(500)
    return items


@router.post("/gst/items")
async def create_item(data: dict, user: dict = Depends(require_admin)):
    if not data.get("name"):
        raise HTTPException(status_code=400, detail="name required")
    item = {
        "id": str(uuid.uuid4()),
        "name": data["name"].strip(),
        "hsn": (data.get("hsn") or "").strip(),
        "unit": data.get("unit") or "Nos",
        "gst_rate": float(data.get("gst_rate") or 0),
        "default_rate": float(data.get("default_rate") or 0),
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.gst_items.insert_one(item.copy())
    item.pop("_id", None)
    return item


@router.put("/gst/items/{item_id}")
async def update_item(item_id: str, data: dict, user: dict = Depends(require_admin)):
    allowed = {"name", "hsn", "unit", "gst_rate", "default_rate", "is_active"}
    updates = {k: v for k, v in data.items() if k in allowed}
    if "gst_rate" in updates:
        updates["gst_rate"] = float(updates["gst_rate"])
    if "default_rate" in updates:
        updates["default_rate"] = float(updates["default_rate"])
    res = await db.gst_items.update_one({"id": item_id}, {"$set": updates})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"message": "Item updated"}


@router.delete("/gst/items/{item_id}")
async def delete_item(item_id: str, user: dict = Depends(require_admin)):
    await db.gst_items.update_one({"id": item_id}, {"$set": {"is_active": False}})
    return {"message": "Item deactivated"}


# ============ CONNECTION PLANS (Item-wise billing templates) ============
def _validate_plan_items(items: list) -> list:
    if not isinstance(items, list) or not items:
        raise HTTPException(status_code=400, detail="At least one plan item is required")
    cleaned_items = []
    for it in items:
        if not (it.get("item_name") or "").strip():
            raise HTTPException(status_code=400, detail="item_name required for every line")
        cleaned_items.append({
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
    user: dict = Depends(require_admin),
):
    await ensure_seed()
    q: Dict[str, Any] = {}
    if start_date or end_date:
        q["invoice_date"] = {}
        if start_date:
            q["invoice_date"]["$gte"] = start_date
        if end_date:
            q["invoice_date"]["$lte"] = end_date

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
    user: dict = Depends(require_admin),
):
    """Item-wise Invoice Register Excel export with all spec columns,
    frozen header, autofilter, wrapped text, auto column widths, bold totals."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    q: Dict[str, Any] = {}
    if status:
        q["status"] = status
    if start_date or end_date:
        q["invoice_date"] = {}
        if start_date:
            q["invoice_date"]["$gte"] = start_date
        if end_date:
            q["invoice_date"]["$lte"] = end_date
    if search:
        q["$or"] = [{"invoice_number": {"$regex": search, "$options": "i"}},
                    {"customer_name": {"$regex": search, "$options": "i"}}]

    invoices = await db.gst_invoices.find(q, {"_id": 0}).sort("invoice_date", -1).to_list(50000)
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
    amount_cols = {12, 13, 16, 18, 20, 21, 22, 23, 24}
    center_cols = {1, 3, 9, 14, 15, 17, 19, 29, 31}

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
                0,  # round off
                float(inv.get("grand_total") or 0) if is_first else "",
                inv.get("payment_mode", "") if is_first else "",
                inv.get("warehouse_name", "") if is_first else "",
                inv.get("sales_executive_name", "") if is_first else "",
                inv.get("created_by_name", "") if is_first else "",
                _fmt_date(inv.get("created_at", "")[:10]) if is_first else "",
                inv.get("cancelled_by_name", "") if is_first else "",
                _fmt_date((inv.get("cancelled_at") or "")[:10]) if is_first else "",
                inv.get("cancellation_reason", "") if is_first else "",
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
    payment_mode: Optional[str] = None,
    item_type: Optional[str] = None,
    user: dict = Depends(require_admin),
):
    await ensure_seed()
    q: Dict[str, Any] = {}
    if status:
        q["status"] = status
    if payment_mode:
        q["payment_mode"] = payment_mode
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
    if search and search.strip():
        s = search.strip()
        q["$or"] = [
            {"invoice_number": {"$regex": s, "$options": "i"}},
            {"customer_name": {"$regex": s, "$options": "i"}},
            {"customer_phone": {"$regex": s, "$options": "i"}},
        ]
    skip = (page - 1) * limit
    total = await db.gst_invoices.count_documents(q)
    invoices = await db.gst_invoices.find(q, {"_id": 0}).sort("invoice_date", -1).skip(skip).limit(limit).to_list(limit)
    return {"invoices": invoices, "total": total, "page": page, "pages": (total + limit - 1) // limit}


# ============ INVOICES - SINGLE (these must come AFTER list/summary/export) ============
@router.post("/gst/invoices")
async def create_invoice(data: dict, user: dict = Depends(require_admin)):
    """Manual invoice creation."""
    await ensure_seed()
    cfg = await db.gst_config.find_one({"key": "gst_config"}) or {}
    tax_mode = (data.get("tax_mode") or cfg.get("default_tax_mode") or "intra_state").lower()
    line_items = data.get("line_items") or []
    if not line_items:
        raise HTTPException(status_code=400, detail="At least one line item is required")
    totals = compute_totals(line_items, tax_mode)
    now = datetime.now(timezone.utc)
    invoice = {
        "id": str(uuid.uuid4()),
        "invoice_number": data.get("invoice_number") or await next_invoice_number(now),
        "invoice_date": data.get("invoice_date") or now.strftime("%Y-%m-%d"),
        "fy": fy_string(now),
        "customer_id": data.get("customer_id") or "",
        "customer_name": (data.get("customer_name") or "").strip(),
        "customer_phone": (data.get("customer_phone") or "").strip(),
        "customer_address": data.get("customer_address") or "",
        "customer_gstin": (data.get("customer_gstin") or "").strip().upper(),
        "place_of_supply": data.get("place_of_supply") or cfg.get("place_of_supply", ""),
        "tax_mode": tax_mode,
        "bill_type": data.get("bill_type") or "manual",
        "payment_mode": data.get("payment_mode") or "cash",
        "remarks": data.get("remarks") or "",
        "line_items": line_items,
        **totals,
        "status": "active",
        "sale_id": data.get("sale_id") or "",
        "sale_type": data.get("sale_type") or "",
        "warehouse_id": data.get("warehouse_id") or "",
        "warehouse_name": data.get("warehouse_name") or "",
        "created_by_id": user.get("id", ""),
        "created_by_name": user.get("name", ""),
        "created_at": now.isoformat(),
    }
    await db.gst_invoices.insert_one(invoice.copy())
    invoice.pop("_id", None)
    await log_audit(user.get("id", ""), user.get("name", ""), "create", "gst_invoice",
                    invoice["id"], f"Invoice {invoice['invoice_number']} for {invoice['customer_name']}")
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
        "customer_gstin", "place_of_supply", "tax_mode", "payment_mode",
        "remarks", "line_items", "bill_type",
    }
    updates = {k: v for k, v in data.items() if k in editable}
    if "line_items" in updates or "tax_mode" in updates:
        tax_mode = updates.get("tax_mode") or existing.get("tax_mode")
        line_items = updates.get("line_items") or existing.get("line_items") or []
        totals = compute_totals(line_items, tax_mode)
        updates["line_items"] = line_items
        updates.update(totals)
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    updates["updated_by_name"] = user.get("name", "")
    await db.gst_invoices.update_one({"id": invoice_id}, {"$set": updates})
    await log_audit(user.get("id", ""), user.get("name", ""), "update", "gst_invoice", invoice_id,
                    f"Fields: {','.join(updates.keys())}")
    return await db.gst_invoices.find_one({"id": invoice_id}, {"_id": 0})


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
            "warehouse_id": sale.get("warehouse_id", ""),
            "warehouse_name": sale.get("warehouse_name", ""),
        }
        return await create_invoice(payload, user)
    except Exception as e:
        logger.error(f"Auto-gen GST invoice failed: {e}")
        return None


# Public alias for use from other route modules
async def auto_generate_invoice_from_sale(sale: dict, sale_type: str, user: dict) -> Optional[dict]:
    return await _auto_generate_invoice(sale, sale_type, user)


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
    summary_data = [
        ["Sub Total:", f"Rs. {format_inr(inv['sub_total'], use_symbol=False)}"],
    ]
    if is_intra:
        summary_data.append(["Total CGST:", f"Rs. {format_inr(inv['total_cgst'], use_symbol=False)}"])
        summary_data.append(["Total SGST:", f"Rs. {format_inr(inv['total_sgst'], use_symbol=False)}"])
    else:
        summary_data.append(["Total IGST:", f"Rs. {format_inr(inv['total_igst'], use_symbol=False)}"])
    summary_data.append(["Round Off:", "0.00"])
    summary_data.append([Paragraph("<b>Grand Total:</b>", style_label),
                         Paragraph(f"<b>Rs. {format_inr(grand, use_symbol=False)}</b>", style_label)])

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
