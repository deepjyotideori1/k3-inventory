"""
GST Billing Reports module - 10 reports with Excel/PDF exports.
Each report supports date range filtering and follows the same formatting rules:
- Excel: frozen header, autofilter, autowidth, wrapped text, bold totals, right-aligned amounts
- PDF: landscape for wide reports, page numbers, repeating header, company branding

Reports:
1. Daily Sales       (group by date)
2. Monthly Sales     (group by month)
3. GST Report        (GSTR-1 style B2B + B2C)
4. HSN Summary       (group by HSN code)
5. Item-wise Sales   (group by item_name + HSN)
6. Customer-wise     (group by customer_name)
7. Warehouse-wise    (group by warehouse_name, excludes Plant)
8. Cancelled         (status='cancelled')
9. Payment-wise      (group by payment_mode)
10. Tax Summary      (group by GST rate)

Plant Hollongi data is excluded from invoicing entirely (per business rule).
"""
from fastapi import APIRouter, HTTPException, Depends, Response
from fastapi.responses import StreamingResponse
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from io import BytesIO
from collections import defaultdict
import logging

from database import db
from deps import require_admin

logger = logging.getLogger(__name__)
router = APIRouter()

REPORT_TYPES = {
    "daily_sales", "monthly_sales", "gst_report", "hsn_summary",
    "item_wise", "customer_wise", "warehouse_wise", "cancelled",
    "payment_wise", "tax_summary",
}


# ---------------- Helpers ----------------
def _fmt_dmy(s):
    if not s:
        return ""
    try:
        parts = str(s).split("T")[0].split("-")
        if len(parts) == 3:
            return f"{parts[2]}-{parts[1]}-{parts[0]}"
    except Exception:
        pass
    return str(s)


def _round(x):
    return round(float(x or 0), 2)


async def _fetch_invoices(start_date: Optional[str], end_date: Optional[str],
                          include_cancelled: bool = False) -> List[dict]:
    q: Dict[str, Any] = {}
    if not include_cancelled:
        q["status"] = "active"
    if start_date or end_date:
        q["invoice_date"] = {}
        if start_date:
            q["invoice_date"]["$gte"] = start_date
        if end_date:
            q["invoice_date"]["$lte"] = end_date
    invoices = await db.gst_invoices.find(q, {"_id": 0}).sort("invoice_date", 1).to_list(200000)
    return invoices


# ---------------- Report builders (return rows + summary + columns) ----------------
async def _build_daily_sales(start_date, end_date):
    invoices = await _fetch_invoices(start_date, end_date)
    by_day: Dict[str, dict] = {}
    for inv in invoices:
        d = inv.get("invoice_date") or ""
        row = by_day.setdefault(d, {
            "date": d, "invoices": 0, "sub_total": 0, "cgst": 0, "sgst": 0, "igst": 0,
            "total_gst": 0, "grand_total": 0,
        })
        row["invoices"] += 1
        row["sub_total"] += float(inv.get("sub_total") or 0)
        row["cgst"] += float(inv.get("total_cgst") or 0)
        row["sgst"] += float(inv.get("total_sgst") or 0)
        row["igst"] += float(inv.get("total_igst") or 0)
        row["total_gst"] += float(inv.get("total_gst") or 0)
        row["grand_total"] += float(inv.get("grand_total") or 0)
    rows = sorted([{**r,
                    "sub_total": _round(r["sub_total"]),
                    "cgst": _round(r["cgst"]), "sgst": _round(r["sgst"]),
                    "igst": _round(r["igst"]), "total_gst": _round(r["total_gst"]),
                    "grand_total": _round(r["grand_total"])} for r in by_day.values()],
                  key=lambda x: x["date"])
    summary = {k: _round(sum(r[k] for r in rows)) for k in ("sub_total", "cgst", "sgst", "igst", "total_gst", "grand_total")}
    summary["invoices"] = sum(r["invoices"] for r in rows)
    columns = [
        ("Date", "date", "center"),
        ("Invoices", "invoices", "center"),
        ("Sub Total", "sub_total", "amount"),
        ("CGST", "cgst", "amount"),
        ("SGST", "sgst", "amount"),
        ("IGST", "igst", "amount"),
        ("Total GST", "total_gst", "amount"),
        ("Grand Total", "grand_total", "amount"),
    ]
    return rows, summary, columns


async def _build_monthly_sales(start_date, end_date):
    invoices = await _fetch_invoices(start_date, end_date)
    by_month: Dict[str, dict] = {}
    for inv in invoices:
        d = (inv.get("invoice_date") or "")[:7]  # YYYY-MM
        row = by_month.setdefault(d, {
            "month": d, "invoices": 0, "sub_total": 0, "cgst": 0, "sgst": 0, "igst": 0,
            "total_gst": 0, "grand_total": 0,
        })
        row["invoices"] += 1
        row["sub_total"] += float(inv.get("sub_total") or 0)
        row["cgst"] += float(inv.get("total_cgst") or 0)
        row["sgst"] += float(inv.get("total_sgst") or 0)
        row["igst"] += float(inv.get("total_igst") or 0)
        row["total_gst"] += float(inv.get("total_gst") or 0)
        row["grand_total"] += float(inv.get("grand_total") or 0)
    rows = sorted([{**r,
                    "sub_total": _round(r["sub_total"]),
                    "cgst": _round(r["cgst"]), "sgst": _round(r["sgst"]),
                    "igst": _round(r["igst"]), "total_gst": _round(r["total_gst"]),
                    "grand_total": _round(r["grand_total"])} for r in by_month.values()],
                  key=lambda x: x["month"])
    summary = {k: _round(sum(r[k] for r in rows)) for k in ("sub_total", "cgst", "sgst", "igst", "total_gst", "grand_total")}
    summary["invoices"] = sum(r["invoices"] for r in rows)
    columns = [
        ("Month", "month", "center"),
        ("Invoices", "invoices", "center"),
        ("Sub Total", "sub_total", "amount"),
        ("CGST", "cgst", "amount"),
        ("SGST", "sgst", "amount"),
        ("IGST", "igst", "amount"),
        ("Total GST", "total_gst", "amount"),
        ("Grand Total", "grand_total", "amount"),
    ]
    return rows, summary, columns


async def _build_gst_report(start_date, end_date):
    """GSTR-1 style: B2B (with GSTIN) + B2C (without GSTIN), per invoice."""
    invoices = await _fetch_invoices(start_date, end_date)
    rows = []
    for inv in invoices:
        gstin = (inv.get("customer_gstin") or "").strip()
        rows.append({
            "type": "B2B" if gstin else "B2C",
            "invoice_number": inv["invoice_number"],
            "invoice_date": _fmt_dmy(inv.get("invoice_date")),
            "customer_name": inv.get("customer_name", ""),
            "customer_gstin": gstin or "—",
            "place_of_supply": inv.get("place_of_supply", ""),
            "tax_mode": inv.get("tax_mode", ""),
            "sub_total": _round(inv.get("sub_total")),
            "cgst": _round(inv.get("total_cgst")),
            "sgst": _round(inv.get("total_sgst")),
            "igst": _round(inv.get("total_igst")),
            "total_gst": _round(inv.get("total_gst")),
            "round_off": _round(inv.get("round_off")),
            "grand_total": _round(inv.get("grand_total")),
        })
    rows.sort(key=lambda r: (r["type"], r["invoice_date"]))
    summary = {
        "b2b_count": sum(1 for r in rows if r["type"] == "B2B"),
        "b2c_count": sum(1 for r in rows if r["type"] == "B2C"),
        "sub_total": _round(sum(r["sub_total"] for r in rows)),
        "cgst": _round(sum(r["cgst"] for r in rows)),
        "sgst": _round(sum(r["sgst"] for r in rows)),
        "igst": _round(sum(r["igst"] for r in rows)),
        "total_gst": _round(sum(r["total_gst"] for r in rows)),
        "round_off": _round(sum(r["round_off"] for r in rows)),
        "grand_total": _round(sum(r["grand_total"] for r in rows)),
    }
    columns = [
        ("Type", "type", "center"),
        ("Invoice No.", "invoice_number", "left"),
        ("Date", "invoice_date", "center"),
        ("Customer", "customer_name", "left"),
        ("GSTIN", "customer_gstin", "left"),
        ("Place of Supply", "place_of_supply", "left"),
        ("Tax Mode", "tax_mode", "center"),
        ("Sub Total", "sub_total", "amount"),
        ("CGST", "cgst", "amount"),
        ("SGST", "sgst", "amount"),
        ("IGST", "igst", "amount"),
        ("Total GST", "total_gst", "amount"),
        ("Round Off", "round_off", "amount"),
        ("Grand Total", "grand_total", "amount"),
    ]
    return rows, summary, columns


async def _build_hsn_summary(start_date, end_date):
    """GSTR-1 HSN Summary: group all line items by HSN code."""
    invoices = await _fetch_invoices(start_date, end_date)
    by_hsn: Dict[str, dict] = {}
    for inv in invoices:
        for li in inv.get("line_items", []):
            hsn = (li.get("hsn") or "").strip() or "—"
            unit = li.get("unit", "")
            gst_rate_norm = float(li.get("gst_rate") or 0)
            key = f"{hsn}|{unit}|{gst_rate_norm}"
            row = by_hsn.setdefault(key, {
                "hsn": hsn, "unit": unit, "gst_rate": gst_rate_norm,
                "quantity": 0, "taxable_value": 0, "cgst": 0, "sgst": 0, "igst": 0, "total_value": 0,
            })
            row["quantity"] += float(li.get("quantity") or 0)
            row["taxable_value"] += float(li.get("taxable_value") or 0)
            row["cgst"] += float(li.get("cgst") or 0)
            row["sgst"] += float(li.get("sgst") or 0)
            row["igst"] += float(li.get("igst") or 0)
            row["total_value"] += float(li.get("line_total") or 0)
    rows = sorted([{**r,
                    "quantity": _round(r["quantity"]),
                    "taxable_value": _round(r["taxable_value"]),
                    "cgst": _round(r["cgst"]), "sgst": _round(r["sgst"]),
                    "igst": _round(r["igst"]), "total_value": _round(r["total_value"])}
                   for r in by_hsn.values()], key=lambda x: x["hsn"])
    summary = {k: _round(sum(r[k] for r in rows))
               for k in ("quantity", "taxable_value", "cgst", "sgst", "igst", "total_value")}
    columns = [
        ("HSN Code", "hsn", "center"),
        ("Unit", "unit", "center"),
        ("GST %", "gst_rate", "center"),
        ("Total Quantity", "quantity", "amount"),
        ("Taxable Value", "taxable_value", "amount"),
        ("CGST", "cgst", "amount"),
        ("SGST", "sgst", "amount"),
        ("IGST", "igst", "amount"),
        ("Total Value", "total_value", "amount"),
    ]
    return rows, summary, columns


async def _build_item_wise(start_date, end_date):
    invoices = await _fetch_invoices(start_date, end_date)
    by_item: Dict[str, dict] = {}
    for inv in invoices:
        for li in inv.get("line_items", []):
            name = li.get("item_name", "—")
            hsn = li.get("hsn", "")
            key = f"{name}|{hsn}"
            row = by_item.setdefault(key, {
                "item_name": name, "hsn": hsn, "unit": li.get("unit", ""),
                "quantity": 0, "taxable_value": 0, "total_gst": 0, "total_value": 0,
                "invoices": set(),
            })
            row["quantity"] += float(li.get("quantity") or 0)
            row["taxable_value"] += float(li.get("taxable_value") or 0)
            row["total_gst"] += float(li.get("total_gst") or 0)
            row["total_value"] += float(li.get("line_total") or 0)
            row["invoices"].add(inv["invoice_number"])
    rows = sorted([{
        "item_name": r["item_name"], "hsn": r["hsn"], "unit": r["unit"],
        "invoices": len(r["invoices"]),
        "quantity": _round(r["quantity"]),
        "taxable_value": _round(r["taxable_value"]),
        "total_gst": _round(r["total_gst"]),
        "total_value": _round(r["total_value"]),
    } for r in by_item.values()], key=lambda x: -x["total_value"])
    summary = {k: _round(sum(r[k] for r in rows))
               for k in ("quantity", "taxable_value", "total_gst", "total_value")}
    summary["invoices"] = sum(r["invoices"] for r in rows)
    columns = [
        ("Item Name", "item_name", "left"),
        ("HSN", "hsn", "center"),
        ("Unit", "unit", "center"),
        ("Invoices", "invoices", "center"),
        ("Quantity", "quantity", "amount"),
        ("Taxable Value", "taxable_value", "amount"),
        ("Total GST", "total_gst", "amount"),
        ("Total Value", "total_value", "amount"),
    ]
    return rows, summary, columns


async def _build_customer_wise(start_date, end_date):
    invoices = await _fetch_invoices(start_date, end_date)
    by_cust: Dict[str, dict] = {}
    for inv in invoices:
        key = (inv.get("customer_name") or "—") + "|" + (inv.get("customer_phone") or "")
        row = by_cust.setdefault(key, {
            "customer_name": inv.get("customer_name", "—"),
            "customer_phone": inv.get("customer_phone", ""),
            "customer_gstin": inv.get("customer_gstin", ""),
            "invoices": 0, "sub_total": 0, "total_gst": 0, "grand_total": 0,
        })
        row["invoices"] += 1
        row["sub_total"] += float(inv.get("sub_total") or 0)
        row["total_gst"] += float(inv.get("total_gst") or 0)
        row["grand_total"] += float(inv.get("grand_total") or 0)
    rows = sorted([{**r,
                    "sub_total": _round(r["sub_total"]),
                    "total_gst": _round(r["total_gst"]),
                    "grand_total": _round(r["grand_total"])} for r in by_cust.values()],
                  key=lambda x: -x["grand_total"])
    summary = {k: _round(sum(r[k] for r in rows)) for k in ("sub_total", "total_gst", "grand_total")}
    summary["invoices"] = sum(r["invoices"] for r in rows)
    summary["customers"] = len(rows)
    columns = [
        ("Customer Name", "customer_name", "left"),
        ("Mobile", "customer_phone", "left"),
        ("GSTIN", "customer_gstin", "left"),
        ("Invoices", "invoices", "center"),
        ("Sub Total", "sub_total", "amount"),
        ("Total GST", "total_gst", "amount"),
        ("Grand Total", "grand_total", "amount"),
    ]
    return rows, summary, columns


async def _build_warehouse_wise(start_date, end_date):
    invoices = await _fetch_invoices(start_date, end_date)
    by_wh: Dict[str, dict] = {}
    for inv in invoices:
        wh = inv.get("warehouse_name") or "—"
        # Skip Plant warehouses (no invoices generated for plant anyway, but be defensive)
        if "plant" in wh.lower() or "hollongi" in wh.lower():
            continue
        row = by_wh.setdefault(wh, {
            "warehouse": wh, "invoices": 0, "sub_total": 0,
            "total_gst": 0, "grand_total": 0,
        })
        row["invoices"] += 1
        row["sub_total"] += float(inv.get("sub_total") or 0)
        row["total_gst"] += float(inv.get("total_gst") or 0)
        row["grand_total"] += float(inv.get("grand_total") or 0)
    rows = sorted([{**r,
                    "sub_total": _round(r["sub_total"]),
                    "total_gst": _round(r["total_gst"]),
                    "grand_total": _round(r["grand_total"])} for r in by_wh.values()],
                  key=lambda x: -x["grand_total"])
    summary = {k: _round(sum(r[k] for r in rows)) for k in ("sub_total", "total_gst", "grand_total")}
    summary["invoices"] = sum(r["invoices"] for r in rows)
    columns = [
        ("Warehouse / Branch", "warehouse", "left"),
        ("Invoices", "invoices", "center"),
        ("Sub Total", "sub_total", "amount"),
        ("Total GST", "total_gst", "amount"),
        ("Grand Total", "grand_total", "amount"),
    ]
    return rows, summary, columns


async def _build_cancelled(start_date, end_date):
    q: Dict[str, Any] = {"status": "cancelled"}
    if start_date or end_date:
        q["invoice_date"] = {}
        if start_date:
            q["invoice_date"]["$gte"] = start_date
        if end_date:
            q["invoice_date"]["$lte"] = end_date
    invoices = await db.gst_invoices.find(q, {"_id": 0}).sort("invoice_date", -1).to_list(50000)
    rows = []
    for inv in invoices:
        rows.append({
            "invoice_number": inv["invoice_number"],
            "invoice_date": _fmt_dmy(inv.get("invoice_date")),
            "customer_name": inv.get("customer_name", ""),
            "grand_total": _round(inv.get("grand_total")),
            "cancelled_at": _fmt_dmy((inv.get("cancelled_at") or "")[:10]),
            "cancelled_by": inv.get("cancelled_by_name", ""),
            "cancellation_reason": inv.get("cancellation_reason", ""),
        })
    summary = {
        "count": len(rows),
        "lost_value": _round(sum(r["grand_total"] for r in rows)),
    }
    columns = [
        ("Invoice No.", "invoice_number", "left"),
        ("Invoice Date", "invoice_date", "center"),
        ("Customer", "customer_name", "left"),
        ("Amount", "grand_total", "amount"),
        ("Cancelled Date", "cancelled_at", "center"),
        ("Cancelled By", "cancelled_by", "left"),
        ("Reason", "cancellation_reason", "left"),
    ]
    return rows, summary, columns


async def _build_payment_wise(start_date, end_date):
    invoices = await _fetch_invoices(start_date, end_date)
    by_mode: Dict[str, dict] = defaultdict(lambda: {"payment_mode": "", "invoices": 0,
                                                     "sub_total": 0, "total_gst": 0, "grand_total": 0})
    for inv in invoices:
        mode = (inv.get("payment_mode") or "unknown").lower()
        row = by_mode[mode]
        row["payment_mode"] = mode.upper()
        row["invoices"] += 1
        row["sub_total"] += float(inv.get("sub_total") or 0)
        row["total_gst"] += float(inv.get("total_gst") or 0)
        row["grand_total"] += float(inv.get("grand_total") or 0)
    rows = sorted([{**r,
                    "sub_total": _round(r["sub_total"]),
                    "total_gst": _round(r["total_gst"]),
                    "grand_total": _round(r["grand_total"])} for r in by_mode.values()],
                  key=lambda x: -x["grand_total"])
    summary = {k: _round(sum(r[k] for r in rows)) for k in ("sub_total", "total_gst", "grand_total")}
    summary["invoices"] = sum(r["invoices"] for r in rows)
    columns = [
        ("Payment Mode", "payment_mode", "center"),
        ("Invoices", "invoices", "center"),
        ("Sub Total", "sub_total", "amount"),
        ("Total GST", "total_gst", "amount"),
        ("Grand Total", "grand_total", "amount"),
    ]
    return rows, summary, columns


async def _build_tax_summary(start_date, end_date):
    """Group invoice line items by GST rate slab; show CGST/SGST/IGST collected per slab."""
    invoices = await _fetch_invoices(start_date, end_date)
    by_rate: Dict[float, dict] = {}
    for inv in invoices:
        for li in inv.get("line_items", []):
            rate = float(li.get("gst_rate") or 0)
            row = by_rate.setdefault(rate, {
                "gst_rate": rate, "taxable": 0, "cgst": 0, "sgst": 0, "igst": 0, "total_gst": 0,
            })
            row["taxable"] += float(li.get("taxable_value") or 0)
            row["cgst"] += float(li.get("cgst") or 0)
            row["sgst"] += float(li.get("sgst") or 0)
            row["igst"] += float(li.get("igst") or 0)
            row["total_gst"] += float(li.get("total_gst") or 0)
    rows = sorted([{**r,
                    "taxable": _round(r["taxable"]),
                    "cgst": _round(r["cgst"]), "sgst": _round(r["sgst"]),
                    "igst": _round(r["igst"]), "total_gst": _round(r["total_gst"])} for r in by_rate.values()],
                  key=lambda x: x["gst_rate"])
    summary = {k: _round(sum(r[k] for r in rows)) for k in ("taxable", "cgst", "sgst", "igst", "total_gst")}
    columns = [
        ("GST Rate %", "gst_rate", "center"),
        ("Taxable Value", "taxable", "amount"),
        ("CGST", "cgst", "amount"),
        ("SGST", "sgst", "amount"),
        ("IGST", "igst", "amount"),
        ("Total GST", "total_gst", "amount"),
    ]
    return rows, summary, columns


# ---------------- Report dispatcher ----------------
async def _build_report(report_type: str, start_date: Optional[str], end_date: Optional[str]):
    builders = {
        "daily_sales": _build_daily_sales,
        "monthly_sales": _build_monthly_sales,
        "gst_report": _build_gst_report,
        "hsn_summary": _build_hsn_summary,
        "item_wise": _build_item_wise,
        "customer_wise": _build_customer_wise,
        "warehouse_wise": _build_warehouse_wise,
        "cancelled": _build_cancelled,
        "payment_wise": _build_payment_wise,
        "tax_summary": _build_tax_summary,
    }
    fn = builders.get(report_type)
    if not fn:
        raise HTTPException(status_code=400, detail=f"Unknown report_type. Must be one of: {sorted(REPORT_TYPES)}")
    return await fn(start_date, end_date)


REPORT_LABELS = {
    "daily_sales": "Daily Sales Report",
    "monthly_sales": "Monthly Sales Report",
    "gst_report": "GST Report (GSTR-1 Style)",
    "hsn_summary": "HSN Summary",
    "item_wise": "Item-wise Sales Report",
    "customer_wise": "Customer-wise Sales Report",
    "warehouse_wise": "Warehouse-wise Sales Report",
    "cancelled": "Cancelled Invoice Report",
    "payment_wise": "Payment-wise Sales Report",
    "tax_summary": "Tax Summary Report",
}


# ============ ENDPOINTS ============
@router.get("/gst/reports/list")
async def list_reports(user: dict = Depends(require_admin)):
    return [{"key": k, "label": v} for k, v in REPORT_LABELS.items()]


@router.get("/gst/reports/{report_type}")
async def get_report(report_type: str, start_date: Optional[str] = None,
                     end_date: Optional[str] = None, user: dict = Depends(require_admin)):
    rows, summary, columns = await _build_report(report_type, start_date, end_date)
    return {
        "report_type": report_type,
        "label": REPORT_LABELS.get(report_type, report_type),
        "start_date": start_date,
        "end_date": end_date,
        "columns": [{"label": c[0], "key": c[1], "align": c[2]} for c in columns],
        "rows": rows,
        "summary": summary,
    }


@router.get("/gst/reports/{report_type}/excel")
async def export_report_excel(report_type: str, start_date: Optional[str] = None,
                              end_date: Optional[str] = None, user: dict = Depends(require_admin)):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    rows, summary, columns = await _build_report(report_type, start_date, end_date)
    label = REPORT_LABELS.get(report_type, report_type)
    cfg = await db.gst_config.find_one({"key": "gst_config"}, {"_id": 0}) or {}

    wb = Workbook()
    ws = wb.active
    ws.title = label[:31]  # excel sheet name limit
    thin = Side(style="thin", color="BBBBBB")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    # Title rows
    n_cols = len(columns)
    last_col_letter = get_column_letter(n_cols)
    ws["A1"] = cfg.get("company_name", "K3 GAS SERVICE")
    ws["A1"].font = Font(bold=True, size=14, color="1E5A8C")
    ws.merge_cells(f"A1:{last_col_letter}1")
    ws["A2"] = f"GSTIN: {cfg.get('company_gstin', '')}    |    {cfg.get('company_address', '')}"
    ws["A2"].font = Font(size=9, color="555555")
    ws.merge_cells(f"A2:{last_col_letter}2")
    ws["A3"] = f"{label}   |   Period: {start_date or 'All'} to {end_date or 'All'}   |   Generated: {datetime.now(timezone.utc).strftime('%d-%m-%Y %H:%M')} by {user.get('name', '')}"
    ws["A3"].font = Font(italic=True, size=9, color="666666")
    ws.merge_cells(f"A3:{last_col_letter}3")

    # Header row
    HEADER_ROW = 5
    for c_idx, (lbl, _key, _align) in enumerate(columns, 1):
        cell = ws.cell(row=HEADER_ROW, column=c_idx, value=lbl)
        cell.font = Font(bold=True, color="FFFFFF", size=10)
        cell.fill = PatternFill("solid", fgColor="1E5A8C")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = border

    # Data rows
    row_idx = HEADER_ROW + 1
    for r in rows:
        for c_idx, (_lbl, key, align) in enumerate(columns, 1):
            v = r.get(key, "")
            cell = ws.cell(row=row_idx, column=c_idx, value=v)
            cell.border = border
            cell.font = Font(size=9)
            if align == "amount" and isinstance(v, (int, float)):
                cell.number_format = "#,##0.00"
                cell.alignment = Alignment(horizontal="right", vertical="top", wrap_text=True)
            elif align == "center":
                cell.alignment = Alignment(horizontal="center", vertical="top", wrap_text=True)
            else:
                cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
        row_idx += 1

    # Totals row
    if rows:
        for c_idx, (lbl, key, align) in enumerate(columns, 1):
            cell = ws.cell(row=row_idx, column=c_idx)
            cell.fill = PatternFill("solid", fgColor="E0EDDF")
            cell.font = Font(bold=True, size=10)
            cell.border = border
            if c_idx == 1:
                cell.value = "TOTAL"
                cell.alignment = Alignment(horizontal="right")
            elif align == "amount" and isinstance(summary.get(key), (int, float)):
                cell.value = summary[key]
                cell.number_format = "#,##0.00"
                cell.alignment = Alignment(horizontal="right")
            elif key == "invoices" and "invoices" in summary:
                cell.value = summary["invoices"]
                cell.alignment = Alignment(horizontal="center")

    # Freeze + autofilter
    ws.freeze_panes = f"A{HEADER_ROW + 1}"
    ws.auto_filter.ref = f"A{HEADER_ROW}:{last_col_letter}{row_idx}"

    # Auto column widths based on header & data
    for c_idx, (lbl, key, align) in enumerate(columns, 1):
        max_len = len(str(lbl))
        for r in rows[:200]:  # sample to avoid huge scans
            v = r.get(key, "")
            max_len = max(max_len, len(str(v)))
        ws.column_dimensions[get_column_letter(c_idx)].width = min(max(max_len + 2, 8), 38)

    ws.print_title_rows = f"{HEADER_ROW}:{HEADER_ROW}"
    ws.page_setup.orientation = ws.ORIENTATION_LANDSCAPE if n_cols > 6 else ws.ORIENTATION_PORTRAIT
    ws.page_setup.fitToWidth = 1
    ws.sheet_properties.pageSetUpPr.fitToPage = True

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    fname = f"{label.replace(' ', '_').replace('/', '_')}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.xlsx"
    return StreamingResponse(iter([buf.read()]),
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f'attachment; filename="{fname}"'})


@router.get("/gst/reports/{report_type}/pdf")
async def export_report_pdf(report_type: str, start_date: Optional[str] = None,
                            end_date: Optional[str] = None, user: dict = Depends(require_admin)):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.units import mm
    from reportlab.lib.styles import ParagraphStyle

    rows, summary, columns = await _build_report(report_type, start_date, end_date)
    label = REPORT_LABELS.get(report_type, report_type)
    cfg = await db.gst_config.find_one({"key": "gst_config"}, {"_id": 0}) or {}

    n_cols = len(columns)
    use_landscape = n_cols > 6
    pagesize = landscape(A4) if use_landscape else A4

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=pagesize,
                             leftMargin=8 * mm, rightMargin=8 * mm,
                             topMargin=10 * mm, bottomMargin=12 * mm,
                             title=label)
    PRIMARY = colors.HexColor("#1E5A8C")
    LIGHT = colors.HexColor("#E8F1F8")
    elements = []
    style_h = ParagraphStyle("h", fontSize=12, alignment=1, fontName="Helvetica-Bold", textColor=PRIMARY)
    style_m = ParagraphStyle("m", fontSize=8, alignment=1, textColor=colors.HexColor("#555555"))
    style_s = ParagraphStyle("s", fontSize=7, alignment=1, textColor=colors.grey)

    elements.append(Paragraph(cfg.get("company_name", "K3 GAS SERVICE"), style_h))
    contact_bits = []
    if cfg.get("company_gstin"):
        contact_bits.append(f"GSTIN: {cfg['company_gstin']}")
    if cfg.get("company_address"):
        contact_bits.append(cfg['company_address'])
    if contact_bits:
        elements.append(Paragraph(" | ".join(contact_bits), style_m))
    elements.append(Paragraph(f"<b>{label}</b>", ParagraphStyle("rt", fontSize=11, alignment=1,
                                                                 fontName="Helvetica-Bold",
                                                                 textColor=colors.HexColor("#333333"))))
    elements.append(Paragraph(
        f"Period: {start_date or 'All'} to {end_date or 'All'}  |  "
        f"Generated: {datetime.now(timezone.utc).strftime('%d-%m-%Y %H:%M')} by {user.get('name', '')}",
        style_s))
    elements.append(Spacer(1, 3 * mm))

    # Table
    header_row = [Paragraph(f"<b>{c[0]}</b>", ParagraphStyle("th", fontSize=7,
                                                              fontName="Helvetica-Bold",
                                                              textColor=colors.white, alignment=1))
                  for c in columns]
    data = [header_row]
    for r in rows:
        row = []
        for (_lbl, key, align) in columns:
            v = r.get(key, "")
            if align == "amount" and isinstance(v, (int, float)):
                v = f"{v:,.2f}"
            row.append(Paragraph(str(v), ParagraphStyle("td", fontSize=7,
                                                         fontName="Helvetica",
                                                         alignment={"center": 1, "amount": 2, "left": 0}.get(align, 0))))
        data.append(row)
    # Totals row
    if rows:
        total_row = []
        for c_idx, (lbl, key, align) in enumerate(columns):
            if c_idx == 0:
                total_row.append(Paragraph("<b>TOTAL</b>",
                                            ParagraphStyle("tt", fontSize=8, fontName="Helvetica-Bold",
                                                           alignment=2)))
            elif align == "amount" and isinstance(summary.get(key), (int, float)):
                total_row.append(Paragraph(f"<b>{summary[key]:,.2f}</b>",
                                            ParagraphStyle("tt", fontSize=8, fontName="Helvetica-Bold",
                                                           alignment=2)))
            elif key == "invoices" and "invoices" in summary:
                total_row.append(Paragraph(f"<b>{summary['invoices']}</b>",
                                            ParagraphStyle("tt", fontSize=8, fontName="Helvetica-Bold",
                                                           alignment=1)))
            else:
                total_row.append("")
        data.append(total_row)

    # Auto column widths
    page_w = (297 - 16) * mm if use_landscape else (210 - 16) * mm
    col_widths = [page_w / n_cols] * n_cols

    tbl = Table(data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, -1), (-1, -1), LIGHT) if rows else ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold") if rows else ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    elements.append(tbl)
    elements.append(Spacer(1, 3 * mm))
    elements.append(Paragraph(
        f"Total rows: {len(rows)}",
        ParagraphStyle("ft", fontSize=7, alignment=2, textColor=colors.grey)))

    # Page numbers via onLaterPages / onFirstPage callbacks
    def _page_footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 6)
        canvas.setFillColor(colors.grey)
        w, _h = pagesize
        canvas.drawCentredString(w / 2, 6 * mm, f"{cfg.get('company_name', 'K3 GAS SERVICE')} | {label} | Page {doc_.page}")
        canvas.restoreState()

    doc.build(elements, onFirstPage=_page_footer, onLaterPages=_page_footer)
    buf.seek(0)
    fname = f"{label.replace(' ', '_').replace('/', '_')}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.pdf"
    return Response(content=buf.read(), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})
