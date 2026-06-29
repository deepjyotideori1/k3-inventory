"""
GST Billing module for the Inventory dashboard.
Stores invoices in a dedicated `gst_invoices` collection — separate from
sales/orders/accessory_sales, so legacy data is never touched. Auto-generates
a draft invoice when a sales entry is created (see sales.py hook), and exposes
manual `Generate from sale` + full CRUD + cancellation flow.
"""
from fastapi import APIRouter, HTTPException, Depends, Response, Query
from fastapi.responses import StreamingResponse
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from io import BytesIO
import calendar
import uuid

from database import db
from deps import get_current_user
from helpers import log_audit, format_inr

router = APIRouter()

# ---------- Item Master (HSN + GST rate) ----------
DEFAULT_ITEMS = [
    {"name": "Domestic LPG", "hsn": "271119", "unit": "KG", "gst_rate": 5},
    {"name": "Empty Cylinder Domestic 15 KG", "hsn": "73110010", "unit": "Nos", "gst_rate": 18},
    {"name": "Domestic Regulator", "hsn": "84812000", "unit": "Nos", "gst_rate": 18},
    {"name": "Hose Pipe 1.3 Mtr", "hsn": "40092100", "unit": "Nos", "gst_rate": 18},
    {"name": "Lighter & Knife", "hsn": "96131000", "unit": "Nos", "gst_rate": 18},
    {"name": "Cooker 3.5 Ltr", "hsn": "73211110", "unit": "Nos", "gst_rate": 18},
    {"name": "Two Stove Burner", "hsn": "73211210", "unit": "Nos", "gst_rate": 18},
    {"name": "Commercial LPG", "hsn": "271119", "unit": "KG", "gst_rate": 18},
    {"name": "Empty Cylinder Commercial 21 KG", "hsn": "73110010", "unit": "Nos", "gst_rate": 18},
    {"name": "Commercial Regulator", "hsn": "84812000", "unit": "Nos", "gst_rate": 18},
    {"name": "Siera High Pressure Regulator", "hsn": "84812000", "unit": "Nos", "gst_rate": 18},
    {"name": "Pigtail Hose Pipe", "hsn": "40092100", "unit": "Nos", "gst_rate": 18},
    {"name": "Hose Roll (Custom)", "hsn": "40092100", "unit": "Nos", "gst_rate": 18},
    {"name": "Gas Card", "hsn": "996913", "unit": "Nos", "gst_rate": 12},
    {"name": "Admin Charge", "hsn": "998399", "unit": "Package", "gst_rate": 18},
]


async def ensure_seed():
    """Idempotent: seeds items + default config if missing."""
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
            "default_tax_mode": "intra_state",  # 'intra_state' (CGST+SGST) or 'inter_state' (IGST)
            "place_of_supply": "",
            "next_seq": 1,
            "current_fy": "",
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
    # Reset sequence when FY changes
    if cfg.get("current_fy") != fy:
        await db.gst_config.update_one(
            {"key": "gst_config"}, {"$set": {"current_fy": fy, "next_seq": 1}}
        )
        seq = 1
    else:
        seq = int(cfg.get("next_seq") or 1)
    await db.gst_config.update_one(
        {"key": "gst_config"}, {"$inc": {"next_seq": 1}}
    )
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
async def get_gst_config(user: dict = Depends(get_current_user)):
    await ensure_seed()
    cfg = await db.gst_config.find_one({"key": "gst_config"}, {"_id": 0})
    return cfg


@router.put("/gst/config")
async def update_gst_config(data: dict, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    allowed = {"prefix", "suffix", "default_tax_mode", "place_of_supply"}
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
async def list_items(user: dict = Depends(get_current_user)):
    await ensure_seed()
    items = await db.gst_items.find({}, {"_id": 0}).sort("name", 1).to_list(500)
    return items


@router.post("/gst/items")
async def create_item(data: dict, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
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
async def update_item(item_id: str, data: dict, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
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
async def delete_item(item_id: str, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    await db.gst_items.update_one({"id": item_id}, {"$set": {"is_active": False}})
    return {"message": "Item deactivated"}


# ============ INVOICES ============
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
    user: dict = Depends(get_current_user),
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


@router.get("/gst/invoices/{invoice_id}")
async def get_invoice(invoice_id: str, user: dict = Depends(get_current_user)):
    inv = await db.gst_invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return inv


@router.post("/gst/invoices")
async def create_invoice(data: dict, user: dict = Depends(get_current_user)):
    """Manual invoice creation OR generate-from-sale (pass sale_id + sale_type)."""
    await ensure_seed()
    cfg = await db.gst_config.find_one({"key": "gst_config"})
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
        "bill_type": data.get("bill_type") or "manual",  # new_connection / refill / accessory / manual
        "payment_mode": data.get("payment_mode") or "cash",
        "remarks": data.get("remarks") or "",
        "line_items": line_items,
        **totals,
        "status": "active",
        "sale_id": data.get("sale_id") or "",
        "sale_type": data.get("sale_type") or "",
        "created_by_id": user.get("id", ""),
        "created_by_name": user.get("name", ""),
        "created_at": now.isoformat(),
    }
    await db.gst_invoices.insert_one(invoice.copy())
    invoice.pop("_id", None)
    await log_audit(user.get("id", ""), user.get("name", ""), "create", "gst_invoice",
                    invoice["id"], f"Invoice {invoice['invoice_number']} for {invoice['customer_name']}")
    return invoice


@router.put("/gst/invoices/{invoice_id}")
async def update_invoice(invoice_id: str, data: dict, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only can edit invoices")
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
async def cancel_invoice(invoice_id: str, data: dict = None, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
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
async def delete_invoice(invoice_id: str, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    res = await db.gst_invoices.delete_one({"id": invoice_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Invoice not found")
    await log_audit(user.get("id", ""), user.get("name", ""), "delete", "gst_invoice", invoice_id, "")
    return {"message": "Invoice deleted"}


# ============ AUTO-GEN HOOK (called from sales/orders/accessories) ============
async def auto_generate_invoice_from_sale(sale: dict, sale_type: str, user: dict) -> Optional[dict]:
    """Best-effort: generate an active GST invoice from a freshly-created sale.
    Used as a non-blocking hook — failures are swallowed and logged.
    """
    try:
        await ensure_seed()
        cfg = await db.gst_config.find_one({"key": "gst_config"})
        tax_mode = cfg.get("default_tax_mode", "intra_state")

        # Build line items based on sale type
        line_items = []
        # sale shape varies — try common fields
        cyl_size = sale.get("cylinder_size") or sale.get("cylinder_type") or ""
        is_commercial = "21" in str(cyl_size) or "commercial" in str(sale.get("connection_type", "")).lower()
        gas_name = "Commercial LPG" if is_commercial else "Domestic LPG"
        qty = float(sale.get("quantity") or sale.get("cylinders") or 1)
        rate = float(sale.get("amount") or sale.get("total_amount") or 0) / max(qty, 1)
        if rate <= 0:
            rate = float(sale.get("rate") or 0)
        # Map the gas item
        gas_item = await db.gst_items.find_one({"name": gas_name}, {"_id": 0})
        if gas_item and rate > 0:
            line_items.append({
                "item_id": gas_item["id"],
                "item_name": gas_item["name"],
                "hsn": gas_item["hsn"],
                "unit": "KG",
                "gst_rate": gas_item["gst_rate"],
                "quantity": qty * (15 if not is_commercial else 21),  # net weight per cylinder
                "rate": round(rate / (15 if not is_commercial else 21), 2),
            })
        if not line_items:
            return None
        payload = {
            "sale_id": sale.get("id"),
            "sale_type": sale_type,
            "bill_type": sale_type,
            "customer_id": sale.get("customer_id") or "",
            "customer_name": sale.get("consumer_name") or sale.get("customer_name") or "",
            "customer_phone": sale.get("phone") or "",
            "customer_address": sale.get("address") or "",
            "tax_mode": tax_mode,
            "payment_mode": sale.get("payment_mode") or "cash",
            "invoice_date": sale.get("date"),
            "line_items": line_items,
        }
        return await create_invoice(payload, user)
    except Exception as e:
        # Log but don't break the sale flow
        try:
            await log_audit(user.get("id", ""), user.get("name", ""), "error", "gst_invoice", "",
                            f"Auto-gen failed: {str(e)[:200]}")
        except Exception:
            pass
        return None


@router.post("/gst/invoices/generate-from-sale/{sale_type}/{sale_id}")
async def generate_from_sale(sale_type: str, sale_id: str, user: dict = Depends(get_current_user)):
    """Manual trigger for legacy/old sales."""
    if sale_type not in ("sales_entry", "order", "accessory_sale"):
        raise HTTPException(status_code=400, detail="Invalid sale_type")
    coll = {"sales_entry": db.sales_entries, "order": db.orders, "accessory_sale": db.accessory_sales}[sale_type]
    sale = await coll.find_one({"id": sale_id}, {"_id": 0})
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")
    # Don't double-generate
    existing = await db.gst_invoices.find_one({"sale_id": sale_id, "sale_type": sale_type, "status": "active"})
    if existing:
        raise HTTPException(status_code=400, detail=f"Active invoice already exists: {existing.get('invoice_number')}")
    inv = await auto_generate_invoice_from_sale(sale, sale_type, user)
    if not inv:
        raise HTTPException(status_code=400, detail="Could not generate invoice — missing customer/amount data")
    return inv


# ============ PDF EXPORT ============
@router.get("/gst/invoices/{invoice_id}/pdf")
async def export_invoice_pdf(invoice_id: str, user: dict = Depends(get_current_user)):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.units import mm
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet

    inv = await db.gst_invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    company = await db.hrms_settings.find_one({"key": "company_info"}, {"_id": 0}) or {}

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=12 * mm, rightMargin=12 * mm,
                             topMargin=12 * mm, bottomMargin=12 * mm)
    styles = getSampleStyleSheet()
    elements = []
    title_style = ParagraphStyle("t", fontSize=14, alignment=1, fontName="Helvetica-Bold",
                                  textColor=colors.HexColor("#1E5A8C"))
    small = ParagraphStyle("s", fontSize=8, alignment=0)
    elements.append(Paragraph(company.get("name", "Company"), title_style))
    elements.append(Paragraph(company.get("address", ""), small))
    if inv.get("status") == "cancelled":
        elements.append(Paragraph("<font color='red'><b>** CANCELLED **</b></font>", title_style))
    elements.append(Paragraph(f"<b>TAX INVOICE</b>", title_style))
    elements.append(Spacer(1, 4 * mm))

    meta = [
        ["Invoice No:", inv["invoice_number"], "Date:", inv["invoice_date"]],
        ["Bill To:", inv["customer_name"], "Phone:", inv.get("customer_phone", "")],
        ["Address:", inv.get("customer_address", "")[:80], "GSTIN:", inv.get("customer_gstin", "")],
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
            li.get("quantity", 0), format_inr(li.get("rate", 0)),
            format_inr(li.get("taxable_value", 0)), f"{li.get('gst_rate', 0)}%",
            format_inr(li.get("cgst", 0)), format_inr(li.get("sgst", 0)),
            format_inr(li.get("igst", 0)), format_inr(li.get("line_total", 0)),
        ])
    # Totals row
    rows.append(["", "", "", "", "", "TOTAL",
                 format_inr(inv["sub_total"]), "",
                 format_inr(inv["total_cgst"]), format_inr(inv["total_sgst"]),
                 format_inr(inv["total_igst"]), format_inr(inv["grand_total"])])

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
    elements.append(Paragraph(f"<b>Grand Total: ₹ {format_inr(inv['grand_total'])}</b>",
                              ParagraphStyle("g", fontSize=12, alignment=2, fontName="Helvetica-Bold")))
    if inv.get("remarks"):
        elements.append(Spacer(1, 4 * mm))
        elements.append(Paragraph(f"<b>Remarks:</b> {inv['remarks']}", small))

    doc.build(elements)
    buf.seek(0)
    fname = f"Invoice_{inv['invoice_number'].replace('/', '_')}.pdf"
    return Response(content=buf.read(), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


# ============ EXCEL EXPORT (list of filtered invoices) ============
@router.get("/gst/invoices/export/excel")
async def export_invoices_excel(
    search: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user: dict = Depends(get_current_user),
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
            if c >= 8 and c <= 13:
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
