"""GST Item Master + Rate History + Bulk Update endpoints.
Extracted from gst_billing.py to keep that file focused on invoices/config/plans.
All endpoints are admin-only and share the same `/gst/items` URL space.
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from io import BytesIO
import uuid

from database import db
from deps import require_admin
from helpers import log_audit

# Local import (in function bodies) of ensure_seed avoids a circular import
# between routes.gst_billing and routes.gst_items at module-load time.

router = APIRouter()


# ============ ITEM MASTER CRUD ============

@router.get("/gst/items")
async def list_items(user: dict = Depends(require_admin)):
    from routes.gst_billing import ensure_seed
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
    """Update an item. If name/hsn/unit/gst_rate changed, cascade those attributes
    (NOT unit_price) to every active connection plan line linked to this item via item_id.
    Historical invoices are never touched - they store snapshots."""
    allowed = {"name", "hsn", "unit", "gst_rate", "default_rate", "is_active"}
    updates = {k: v for k, v in data.items() if k in allowed}
    if "gst_rate" in updates:
        updates["gst_rate"] = float(updates["gst_rate"])
    if "default_rate" in updates:
        updates["default_rate"] = float(updates["default_rate"])
    if "name" in updates:
        updates["name"] = str(updates["name"]).strip()
    existing = await db.gst_items.find_one({"id": item_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Item not found")
    await db.gst_items.update_one({"id": item_id}, {"$set": updates})

    # Record rate history if default_rate / gst_rate / is_active changed
    after_for_history = {**existing, **updates}
    effective_from = (data.get("effective_from") or "").strip()
    await _record_rate_history(existing, after_for_history, effective_from, user, reason="single_update")

    # Cascade to plan items - only attributes that should follow the master
    cascade_keys = {"name", "hsn", "unit", "gst_rate"}
    cascade_updates = {k: updates[k] for k in cascade_keys if k in updates}
    affected_plans = 0
    if cascade_updates:
        plans = await db.gst_plans.find({"items.item_id": item_id}).to_list(500)
        for plan in plans:
            new_items = []
            changed = False
            for it in plan.get("items", []):
                if it.get("item_id") == item_id:
                    if "name" in cascade_updates:
                        it["item_name"] = cascade_updates["name"]
                    if "hsn" in cascade_updates:
                        it["hsn"] = cascade_updates["hsn"]
                    if "unit" in cascade_updates:
                        it["unit"] = cascade_updates["unit"]
                    if "gst_rate" in cascade_updates:
                        it["gst_rate"] = float(cascade_updates["gst_rate"])
                    changed = True
                new_items.append(it)
            if changed:
                await db.gst_plans.update_one({"id": plan["id"]},
                                              {"$set": {"items": new_items,
                                                        "updated_at": datetime.now(timezone.utc).isoformat()}})
                affected_plans += 1

    await log_audit(user.get("id", ""), user.get("name", ""), "update", "gst_item",
                    item_id, f"Fields: {','.join(updates.keys())}; cascaded to {affected_plans} plans")
    return {"message": "Item updated", "affected_plans": affected_plans}


@router.delete("/gst/items/{item_id}")
async def delete_item(item_id: str, user: dict = Depends(require_admin)):
    """Soft-delete (deactivate) an item. Existing plan lines and invoices remain unchanged
    for historical record purposes - they will still display the item name."""
    res = await db.gst_items.update_one({"id": item_id}, {"$set": {"is_active": False}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    await log_audit(user.get("id", ""), user.get("name", ""), "deactivate", "gst_item", item_id, "")
    return {"message": "Item deactivated"}


@router.post("/gst/items/{item_id}/activate")
async def activate_item(item_id: str, user: dict = Depends(require_admin)):
    """Reactivate a previously-deactivated item so it can be used in new plans/invoices again."""
    res = await db.gst_items.update_one({"id": item_id}, {"$set": {"is_active": True}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    await log_audit(user.get("id", ""), user.get("name", ""), "activate", "gst_item", item_id, "")
    return {"message": "Item activated"}


# ============ ITEM RATE HISTORY ============
async def _record_rate_history(item_before: dict, item_after: dict, effective_from: str, user: dict, reason: str = ""):
    """Append a history record whenever default_rate, gst_rate, or is_active changes."""
    changed = (
        float(item_before.get("default_rate") or 0) != float(item_after.get("default_rate") or 0)
        or float(item_before.get("gst_rate") or 0) != float(item_after.get("gst_rate") or 0)
        or bool(item_before.get("is_active", True)) != bool(item_after.get("is_active", True))
    )
    if not changed:
        return None
    entry = {
        "id": str(uuid.uuid4()),
        "item_id": item_after.get("id") or item_before.get("id"),
        "item_name": item_after.get("name") or item_before.get("name"),
        "item_code": (item_after.get("name") or "").strip()[:24].upper().replace(" ", "_"),
        "hsn": item_after.get("hsn") or item_before.get("hsn") or "",
        "unit": item_after.get("unit") or item_before.get("unit") or "",
        "gst_rate": float(item_after.get("gst_rate") or 0),
        "prev_rate": float(item_before.get("default_rate") or 0),
        "new_rate": float(item_after.get("default_rate") or 0),
        "effective_from": effective_from or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "updated_by_id": user.get("id", ""),
        "updated_by_name": user.get("name", ""),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "is_active": bool(item_after.get("is_active", True)),
        "reason": reason,
    }
    await db.gst_item_history.insert_one(entry.copy())
    entry.pop("_id", None)
    return entry


@router.get("/gst/items/history")
async def get_item_history(item_id: Optional[str] = None, start_date: Optional[str] = None,
                            end_date: Optional[str] = None, user: dict = Depends(require_admin)):
    q: Dict[str, Any] = {}
    if item_id:
        q["item_id"] = item_id
    if start_date or end_date:
        q["effective_from"] = {}
        if start_date:
            q["effective_from"]["$gte"] = start_date
        if end_date:
            q["effective_from"]["$lte"] = end_date
    rows = await db.gst_item_history.find(q, {"_id": 0}).sort("updated_at", -1).to_list(20000)
    return {"rows": rows, "count": len(rows)}


@router.get("/gst/items/history/excel")
async def export_item_history_excel(item_id: Optional[str] = None, start_date: Optional[str] = None,
                                     end_date: Optional[str] = None, user: dict = Depends(require_admin)):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    q: Dict[str, Any] = {}
    if item_id:
        q["item_id"] = item_id
    if start_date or end_date:
        q["effective_from"] = {}
        if start_date:
            q["effective_from"]["$gte"] = start_date
        if end_date:
            q["effective_from"]["$lte"] = end_date
    rows = await db.gst_item_history.find(q, {"_id": 0}).sort("updated_at", -1).to_list(50000)

    wb = Workbook()
    ws = wb.active
    ws.title = "Item Rate History"
    thin = Side(style="thin", color="BBBBBB")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    headers = ["Item Name", "Item Code", "Unit", "HSN Code", "GST Rate %",
               "Previous Rate", "Updated Rate", "Effective From",
               "Updated By", "Updated Date & Time", "Status"]

    # Use shared branded-header helper for consistency with other exports
    from export_helpers import get_company_info_for_export, embed_logo_openpyxl, cleanup_logo_tempfile
    company = await get_company_info_for_export()
    period_str = f"{start_date or 'All'} to {end_date or 'All'}"
    logo_path = embed_logo_openpyxl(
        ws, company,
        title=f"Item Rate History (by {user.get('name', '')})",
        period=period_str,
        last_col_letter=get_column_letter(len(headers)),
    )
    ws.append([])  # row 4 spacer

    HEADER_ROW = 5
    for c_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=HEADER_ROW, column=c_idx, value=h)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1E5A8C")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = border

    def _fmt_dt(s):
        if not s:
            return ""
        s = str(s).split("T")
        date = s[0].split("-")
        if len(date) == 3:
            d = f"{date[2]}-{date[1]}-{date[0]}"
        else:
            d = s[0]
        if len(s) > 1:
            return f"{d} {s[1][:5]}"
        return d

    row = HEADER_ROW + 1
    for r in rows:
        vals = [
            r.get("item_name", ""),
            r.get("item_code", ""),
            r.get("unit", ""),
            r.get("hsn", ""),
            float(r.get("gst_rate") or 0),
            float(r.get("prev_rate") or 0),
            float(r.get("new_rate") or 0),
            _fmt_dt(r.get("effective_from", "")),
            r.get("updated_by_name", ""),
            _fmt_dt(r.get("updated_at", "")),
            "Active" if r.get("is_active", True) else "Inactive",
        ]
        for c_idx, v in enumerate(vals, 1):
            cell = ws.cell(row=row, column=c_idx, value=v)
            cell.border = border
            cell.font = Font(size=9)
            if c_idx in (5, 6, 7):  # rate columns
                cell.number_format = "#,##0.00"
                cell.alignment = Alignment(horizontal="right")
            elif c_idx in (4, 8, 10, 11):  # HSN, dates, status
                cell.alignment = Alignment(horizontal="center")
            else:
                cell.alignment = Alignment(horizontal="left", wrap_text=True)
        row += 1
    ws.freeze_panes = f"A{HEADER_ROW + 1}"
    ws.auto_filter.ref = f"A{HEADER_ROW}:{get_column_letter(len(headers))}{row}"
    widths = [28, 18, 10, 12, 10, 13, 13, 14, 18, 18, 10]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.print_title_rows = f"{HEADER_ROW}:{HEADER_ROW}"

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    cleanup_logo_tempfile(logo_path)
    fname = f"Item_Rate_History_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.xlsx"
    return StreamingResponse(iter([buf.read()]),
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f'attachment; filename="{fname}"'})


# ============ BULK UPDATE / TEMPLATE ============
@router.get("/gst/items/template/excel")
async def download_bulk_template(user: dict = Depends(require_admin)):
    """Pre-filled Excel template of all current items - admin can edit and re-upload."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter

    items = await db.gst_items.find({}, {"_id": 0}).sort("name", 1).to_list(2000)
    wb = Workbook()
    ws = wb.active
    ws.title = "Item Master Bulk Update"
    headers = ["id", "name", "hsn", "unit", "gst_rate", "default_rate", "is_active", "effective_from"]
    for c_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=c_idx, value=h)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1E5A8C")
        cell.alignment = Alignment(horizontal="center")
    for r_idx, it in enumerate(items, 2):
        ws.cell(row=r_idx, column=1, value=it.get("id"))
        ws.cell(row=r_idx, column=2, value=it.get("name"))
        ws.cell(row=r_idx, column=3, value=it.get("hsn"))
        ws.cell(row=r_idx, column=4, value=it.get("unit"))
        ws.cell(row=r_idx, column=5, value=float(it.get("gst_rate") or 0))
        ws.cell(row=r_idx, column=6, value=float(it.get("default_rate") or 0))
        ws.cell(row=r_idx, column=7, value="active" if it.get("is_active", True) else "inactive")
        ws.cell(row=r_idx, column=8, value="")  # admin fills effective_from per row (optional)
    ws["I1"] = "Instructions"
    ws["I1"].font = Font(bold=True)
    ws["I2"] = "Edit any cell (except id). Leave id blank to create a NEW item."
    ws["I3"] = "is_active accepts: active/inactive/true/false/1/0"
    ws["I4"] = "effective_from: YYYY-MM-DD (optional; defaults to today if blank)"
    for c, w in enumerate([38, 30, 12, 12, 10, 14, 12, 14, 60], 1):
        ws.column_dimensions[get_column_letter(c)].width = w
    ws.freeze_panes = "A2"
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(iter([buf.read()]),
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": 'attachment; filename="ItemMaster_BulkTemplate.xlsx"'})


def _parse_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    s = str(v or "").strip().lower()
    return s in ("active", "true", "1", "yes", "y")


async def _apply_bulk_rows(parsed: List[dict], default_effective_from: str, user: dict) -> dict:
    """Apply a list of bulk-update rows. Each row keys: id (optional - blank means create),
    name, hsn, unit, gst_rate, default_rate, is_active, effective_from (optional per-row)."""
    created = 0
    updated = 0
    skipped = 0
    errors: List[dict] = []
    rate_changes = 0
    for i, row in enumerate(parsed, 1):
        try:
            name = (row.get("name") or "").strip()
            if not name:
                errors.append({"row": i, "error": "name is required"})
                skipped += 1
                continue
            payload = {
                "name": name,
                "hsn": (row.get("hsn") or "").strip(),
                "unit": (row.get("unit") or "Nos").strip() or "Nos",
                "gst_rate": float(row.get("gst_rate") or 0),
                "default_rate": float(row.get("default_rate") or 0),
                "is_active": _parse_bool(row.get("is_active", True)),
            }
            row_eff = (row.get("effective_from") or "").strip() or default_effective_from or datetime.now(timezone.utc).strftime("%Y-%m-%d")
            item_id = (row.get("id") or "").strip()
            if item_id:
                before = await db.gst_items.find_one({"id": item_id})
                if not before:
                    errors.append({"row": i, "error": f"item id {item_id} not found"})
                    skipped += 1
                    continue
                await db.gst_items.update_one({"id": item_id}, {"$set": payload})
                after = {**before, **payload}
                hist = await _record_rate_history(before, after, row_eff, user, reason="bulk_update")
                if hist:
                    rate_changes += 1
                # Cascade attribute changes to plans (name/hsn/unit/gst_rate)
                cascade_keys = {"name", "hsn", "unit", "gst_rate"}
                cascade_updates = {k: payload[k] for k in cascade_keys if payload.get(k) != before.get(k)}
                if cascade_updates:
                    plans = await db.gst_plans.find({"items.item_id": item_id}).to_list(500)
                    for plan in plans:
                        new_items = []
                        changed = False
                        for it in plan.get("items", []):
                            if it.get("item_id") == item_id:
                                if "name" in cascade_updates:
                                    it["item_name"] = cascade_updates["name"]
                                if "hsn" in cascade_updates:
                                    it["hsn"] = cascade_updates["hsn"]
                                if "unit" in cascade_updates:
                                    it["unit"] = cascade_updates["unit"]
                                if "gst_rate" in cascade_updates:
                                    it["gst_rate"] = float(cascade_updates["gst_rate"])
                                changed = True
                            new_items.append(it)
                        if changed:
                            await db.gst_plans.update_one({"id": plan["id"]}, {"$set": {"items": new_items}})
                updated += 1
            else:
                new_id = str(uuid.uuid4())
                new_doc = {
                    "id": new_id, **payload, "created_at": datetime.now(timezone.utc).isoformat()
                }
                await db.gst_items.insert_one(new_doc.copy())
                new_doc.pop("_id", None)
                # Record initial history entry (prev=0, new=default_rate)
                await _record_rate_history({"id": new_id, "default_rate": 0, "gst_rate": 0, "is_active": True},
                                            new_doc, row_eff, user, reason="bulk_create")
                created += 1
                rate_changes += 1
        except (TypeError, ValueError) as e:
            errors.append({"row": i, "error": str(e)})
            skipped += 1
    return {
        "created": created, "updated": updated, "rate_changes": rate_changes,
        "skipped": skipped, "errors": errors,
        "effective_from": default_effective_from,
    }


@router.post("/gst/items/bulk-update")
async def bulk_update_items_json(data: dict, user: dict = Depends(require_admin)):
    """JSON bulk update. Body: {effective_from: 'YYYY-MM-DD', items: [{id?, name, hsn, unit, gst_rate, default_rate, is_active, effective_from?}, ...]}"""
    items = data.get("items") or []
    if not isinstance(items, list) or not items:
        raise HTTPException(status_code=400, detail="items[] required")
    effective_from = (data.get("effective_from") or "").strip()
    result = await _apply_bulk_rows(items, effective_from, user)
    await log_audit(user.get("id", ""), user.get("name", ""), "bulk_update", "gst_items", "",
                    f"created={result['created']} updated={result['updated']} skipped={result['skipped']}")
    return result


@router.post("/gst/items/bulk-upload")
async def bulk_upload_items_excel(file: UploadFile = File(...), effective_from: str = Form(""),
                                   user: dict = Depends(require_admin)):
    """Multipart Excel/CSV upload. Columns must be: id (optional), name, hsn, unit, gst_rate, default_rate, is_active, effective_from (optional)."""
    fname = (file.filename or "").lower()
    contents = await file.read()
    parsed_rows: List[dict] = []
    try:
        if fname.endswith(".csv"):
            import csv
            from io import StringIO
            text = contents.decode("utf-8-sig")
            reader = csv.DictReader(StringIO(text))
            parsed_rows = list(reader)
        else:
            from openpyxl import load_workbook
            wb = load_workbook(BytesIO(contents), data_only=True)
            ws = wb.active
            headers_row = [str(c.value or "").strip().lower() for c in ws[1]]
            for r in ws.iter_rows(min_row=2, values_only=True):
                if all((v is None or str(v).strip() == "") for v in r):
                    continue
                row_dict = {headers_row[i]: r[i] for i in range(min(len(headers_row), len(r)))}
                parsed_rows.append(row_dict)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not parse file: {e}")
    if not parsed_rows:
        raise HTTPException(status_code=400, detail="No rows found in file")
    result = await _apply_bulk_rows(parsed_rows, (effective_from or "").strip(), user)
    await log_audit(user.get("id", ""), user.get("name", ""), "bulk_upload", "gst_items", "",
                    f"file={file.filename} created={result['created']} updated={result['updated']}")
    return result
