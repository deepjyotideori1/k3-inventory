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


async def ensure_seed():
    """Idempotent: seeds default items + config if missing."""
    if await db.gst_items.count_documents({}) == 0:
        await db.gst_items.insert_many([
            {**it, "id": str(uuid.uuid4()), "is_active": True,
             "default_rate": 0,
             "created_at": datetime.now(timezone.utc).isoformat()}
            for it in DEFAULT_ITEMS
        ])
    if not await db.gst_config.find_one({"key": "gst_config"}):
        await db.gst_config.insert_one({
            "key": "gst_config",
            "prefix": "INV",
            "suffix": "",
            "default_tax_mode": "intra_state",
            "place_of_supply": "Arunachal Pradesh",
            "next_seq": 1,
            "current_fy": "",
            "auto_generate": True,
        })


def fy_string(d: datetime) -> str:
    """Indian fiscal year string e.g. 2026-27 (Apr-Mar)."""
    yr = d.year
    if d.month < 4:
        start, end = yr - 1, yr
    else:
        start, end = yr, yr + 1
    return f"{start}-{str(end)[-2:]}"


async def next_invoice_number(when: Optional[datetime] = None) -> str:
    await ensure_seed()
    when = when or datetime.now(timezone.utc)
    fy = fy_string(when)
    cfg = await db.gst_config.find_one({"key": "gst_config"})
    prefix = cfg.get("prefix") or "INV"
    suffix = cfg.get("suffix") or ""
    if cfg.get("current_fy") != fy:
        await db.gst_config.update_one(
            {"key": "gst_config"}, {"$set": {"current_fy": fy, "next_seq": 1}}
        )
        seq = 1
        await db.gst_config.update_one({"key": "gst_config"}, {"$inc": {"next_seq": 1}})
    else:
        seq = int(cfg.get("next_seq") or 1)
        await db.gst_config.update_one({"key": "gst_config"}, {"$inc": {"next_seq": 1}})
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
    allowed = {"prefix", "suffix", "default_tax_mode", "place_of_supply", "auto_generate"}
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
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment

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

    wb = Workbook()
    ws = wb.active
    ws.title = "GST Invoices"
    headers = ["Invoice No", "Date", "Status", "Customer", "Phone", "GSTIN",
               "Tax Mode", "Sub Total", "CGST", "SGST", "IGST", "Total GST", "Grand Total",
               "Payment Mode", "Bill Type"]
    for i, h in enumerate(headers, 1):
        c = ws.cell(row=1, column=i, value=h)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1E5A8C")
        c.alignment = Alignment(horizontal="center")
    for r, inv in enumerate(invoices, 2):
        vals = [
            inv["invoice_number"], inv["invoice_date"], inv["status"], inv["customer_name"],
            inv.get("customer_phone", ""), inv.get("customer_gstin", ""),
            inv["tax_mode"], inv["sub_total"], inv["total_cgst"], inv["total_sgst"],
            inv["total_igst"], inv["total_gst"], inv["grand_total"],
            inv.get("payment_mode", ""), inv.get("bill_type", ""),
        ]
        for c, v in enumerate(vals, 1):
            cell = ws.cell(row=r, column=c, value=v)
            if 8 <= c <= 13:
                cell.number_format = "#,##0.00"
    for i, w in enumerate([18, 12, 10, 25, 14, 16, 14, 12, 11, 11, 11, 12, 14, 14, 14]):
        ws.column_dimensions[chr(64 + i + 1)].width = w

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    fname = f"GST_Invoices_{datetime.now(timezone.utc).strftime('%Y%m%d')}.xlsx"
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
    """
    try:
        await ensure_seed()
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
            # Determine item & quantity
            if is_refill:
                item_name = "Commercial LPG Refill" if is_commercial else "Domestic LPG Refill"
                qty = int(sale.get("no_of_refills", 0) or 0) or 1
            else:
                item_name = "Commercial New Connection" if is_commercial else "Domestic New Connection"
                # cylinder_nos may be a number or comma list
                cyl = str(sale.get("cylinder_nos", "")).strip()
                try:
                    qty = int(cyl) if cyl else 1
                except ValueError:
                    qty = max(1, len([p for p in cyl.split(",") if p.strip()]))
            amount = float(sale.get("amount") or 0)
            if amount <= 0 or qty <= 0:
                return None
            rate = round(amount / qty, 2)
            # gst-inclusive amount -> back-calc taxable to keep grand_total == sale amount
            gst_item = await db.gst_items.find_one({"name": item_name}, {"_id": 0})
            gst_rate = float(gst_item.get("gst_rate") if gst_item else 5)
            hsn = gst_item.get("hsn") if gst_item else "271119"
            unit = gst_item.get("unit") if gst_item else "Cylinder"
            # Treat sale amount as inclusive of GST
            taxable_per_unit = round(rate * 100.0 / (100.0 + gst_rate), 2)
            line_items.append({
                "item_name": item_name,
                "hsn": hsn,
                "unit": unit,
                "gst_rate": gst_rate,
                "quantity": qty,
                "rate": taxable_per_unit,
            })
            bill_type = "refill" if is_refill else "new_connection"
            cust_name = sale.get("consumer_name") or ""
            cust_addr = sale.get("address") or ""

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
                    {"name": {"$regex": f"^{acc_name}", "$options": "i"}}, {"_id": 0}
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


# ============ PDF EXPORT (single invoice) ============
@router.get("/gst/invoices/{invoice_id}/pdf")
async def export_invoice_pdf(invoice_id: str, user: dict = Depends(require_admin)):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
    from reportlab.lib.units import mm
    from reportlab.lib.styles import ParagraphStyle
    import requests as _requests
    from io import BytesIO as _BIO

    inv = await db.gst_invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    company = await db.hrms_settings.find_one({"key": "company_info"}, {"_id": 0}) or {}

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=12 * mm, rightMargin=12 * mm,
                             topMargin=12 * mm, bottomMargin=12 * mm)
    elements = []
    title_style = ParagraphStyle("t", fontSize=14, alignment=1, fontName="Helvetica-Bold",
                                  textColor=colors.HexColor("#1E5A8C"))
    sub_style = ParagraphStyle("st", fontSize=10, alignment=1)
    small = ParagraphStyle("s", fontSize=8, alignment=0)

    # Try to embed company logo
    logo_url = company.get("logo_url") or company.get("logo")
    if logo_url:
        try:
            img_data = _requests.get(logo_url, timeout=5).content
            img = Image(_BIO(img_data), width=22 * mm, height=22 * mm)
            img.hAlign = "CENTER"
            elements.append(img)
        except Exception:
            pass

    elements.append(Paragraph(company.get("name", "K3 GAS SERVICE"), title_style))
    if company.get("tagline"):
        elements.append(Paragraph(company.get("tagline", ""), sub_style))
    if company.get("address"):
        elements.append(Paragraph(company.get("address", ""), sub_style))
    if company.get("gstin"):
        elements.append(Paragraph(f"GSTIN: {company.get('gstin', '')}", sub_style))
    elements.append(Spacer(1, 3 * mm))
    if inv.get("status") == "cancelled":
        elements.append(Paragraph("<font color='red'><b>** CANCELLED **</b></font>", title_style))
    elements.append(Paragraph("<b>TAX INVOICE</b>", title_style))
    elements.append(Spacer(1, 4 * mm))

    meta = [
        ["Invoice No:", inv["invoice_number"], "Date:", inv["invoice_date"]],
        ["Bill To:", inv["customer_name"], "Phone:", inv.get("customer_phone", "")],
        ["Address:", (inv.get("customer_address", "") or "")[:80], "GSTIN:", inv.get("customer_gstin", "")],
        ["Tax Mode:", "Intra-state (CGST+SGST)" if inv["tax_mode"] == "intra_state" else "Inter-state (IGST)",
         "Payment:", inv.get("payment_mode", "")],
    ]
    meta_tbl = Table(meta, colWidths=[28 * mm, 65 * mm, 25 * mm, 65 * mm])
    meta_tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
        ("INNERGRID", (0, 0), (-1, -1), 0.2, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elements.append(meta_tbl)
    elements.append(Spacer(1, 4 * mm))

    headers = ["#", "Item", "HSN", "Unit", "Qty", "Rate", "Taxable", "GST%",
               "CGST", "SGST", "IGST", "Total"]
    rows = [headers]
    for i, li in enumerate(inv["line_items"], 1):
        rows.append([
            i, li.get("item_name", ""), li.get("hsn", ""), li.get("unit", ""),
            li.get("quantity", 0), format_inr(li.get("rate", 0), use_symbol=False),
            format_inr(li.get("taxable_value", 0), use_symbol=False), f"{li.get('gst_rate', 0)}%",
            format_inr(li.get("cgst", 0), use_symbol=False), format_inr(li.get("sgst", 0), use_symbol=False),
            format_inr(li.get("igst", 0), use_symbol=False), format_inr(li.get("line_total", 0), use_symbol=False),
        ])
    rows.append(["", "", "", "", "", "TOTAL",
                 format_inr(inv["sub_total"], use_symbol=False), "",
                 format_inr(inv["total_cgst"], use_symbol=False), format_inr(inv["total_sgst"], use_symbol=False),
                 format_inr(inv["total_igst"], use_symbol=False), format_inr(inv["grand_total"], use_symbol=False)])

    tbl = Table(rows, colWidths=[10, 48 * mm, 18 * mm, 12 * mm, 12 * mm, 18 * mm, 22 * mm, 14, 18 * mm, 18 * mm, 18 * mm, 22 * mm])
    tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E5A8C")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("ALIGN", (4, 1), (-1, -1), "RIGHT"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#E0EDDF")),
    ]))
    elements.append(tbl)
    elements.append(Spacer(1, 6 * mm))
    elements.append(Paragraph(f"<b>Grand Total: Rs. {format_inr(inv['grand_total'], use_symbol=False)}</b>",
                              ParagraphStyle("g", fontSize=12, alignment=2, fontName="Helvetica-Bold")))
    if inv.get("remarks"):
        elements.append(Spacer(1, 4 * mm))
        elements.append(Paragraph(f"<b>Remarks:</b> {inv['remarks']}", small))

    elements.append(Spacer(1, 10 * mm))
    elements.append(Paragraph("This is a computer-generated invoice. Subject to local jurisdiction.",
                              ParagraphStyle("ft", fontSize=7, alignment=1, textColor=colors.grey)))

    doc.build(elements)
    buf.seek(0)
    fname = f"Invoice_{inv['invoice_number'].replace('/', '_')}.pdf"
    return Response(content=buf.read(), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})
