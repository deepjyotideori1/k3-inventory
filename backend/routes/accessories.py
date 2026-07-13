from fastapi import APIRouter, HTTPException, Depends, Response
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from database import db
from deps import get_current_user, require_admin, security
from helpers import format_inr
from models import (
    AccessoryCreate, AccessoryResponse,
    AccessoryDealerCreate, AccessoryDealerResponse,
    AccessoryEntryCreate, AccessoryEntryResponse,
    AccessorySaleCreate, AccessorySaleItemCreate, AccessorySaleResponse, AccessorySaleItemResponse
)
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from io import BytesIO
import uuid

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import xlsxwriter

from routes.gst_billing import auto_generate_invoice_from_sale, validate_sale_discrepancy

router = APIRouter()

# ============ LPG ACCESSORIES MANAGEMENT ============

@router.post("/accessories", response_model=AccessoryResponse)
async def create_accessory(data: AccessoryCreate, user: dict = Depends(require_admin)):
    """Create a new LPG accessory - Admin only"""
    accessory = {
        'id': str(uuid.uuid4()),
        'name': data.name,
        'description': data.description,
        'unit': data.unit,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'is_active': True
    }
    await db.accessories.insert_one(accessory)
    return AccessoryResponse(**accessory)

@router.get("/accessories")
async def get_accessories(user: dict = Depends(get_current_user)):
    """Get all accessories"""
    accessories = await db.accessories.find({'is_active': True}, {'_id': 0}).to_list(1000)
    return accessories

@router.put("/accessories/{accessory_id}")
async def update_accessory(accessory_id: str, data: AccessoryCreate, user: dict = Depends(require_admin)):
    """Update an accessory - Admin only"""
    result = await db.accessories.update_one(
        {'id': accessory_id},
        {'$set': {'name': data.name, 'description': data.description, 'unit': data.unit}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Accessory not found")
    accessory = await db.accessories.find_one({'id': accessory_id}, {'_id': 0})
    return accessory

@router.delete("/accessories/{accessory_id}")
async def delete_accessory(accessory_id: str, user: dict = Depends(require_admin)):
    """Soft delete an accessory - Admin only"""
    result = await db.accessories.update_one({'id': accessory_id}, {'$set': {'is_active': False}})
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Accessory not found")
    return {"message": "Accessory deleted successfully"}

# ============ ACCESSORY DEALERS ============

@router.post("/accessory-dealers", response_model=AccessoryDealerResponse)
async def create_accessory_dealer(data: AccessoryDealerCreate, user: dict = Depends(require_admin)):
    """Create a new accessory dealer - Admin only"""
    dealer = {
        'id': str(uuid.uuid4()),
        'name': data.name,
        'contact': data.contact,
        'address': data.address,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'is_active': True
    }
    await db.accessory_dealers.insert_one(dealer)
    return AccessoryDealerResponse(**dealer)

@router.get("/accessory-dealers")
async def get_accessory_dealers(user: dict = Depends(get_current_user)):
    """Get all accessory dealers"""
    dealers = await db.accessory_dealers.find({'is_active': True}, {'_id': 0}).to_list(1000)
    return dealers

@router.put("/accessory-dealers/{dealer_id}")
async def update_accessory_dealer(dealer_id: str, data: AccessoryDealerCreate, user: dict = Depends(require_admin)):
    """Update an accessory dealer - Admin only"""
    result = await db.accessory_dealers.update_one(
        {'id': dealer_id},
        {'$set': {'name': data.name, 'contact': data.contact, 'address': data.address}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Dealer not found")
    dealer = await db.accessory_dealers.find_one({'id': dealer_id}, {'_id': 0})
    return dealer

@router.delete("/accessory-dealers/{dealer_id}")
async def delete_accessory_dealer(dealer_id: str, user: dict = Depends(require_admin)):
    """Soft delete an accessory dealer - Admin only"""
    result = await db.accessory_dealers.update_one({'id': dealer_id}, {'$set': {'is_active': False}})
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Dealer not found")
    return {"message": "Dealer deleted successfully"}

# ============ ACCESSORY ENTRIES ============

@router.post("/accessory-entries", response_model=AccessoryEntryResponse)
async def create_accessory_entry(data: AccessoryEntryCreate, user: dict = Depends(require_admin)):
    """Create an accessory entry - Admin only"""
    accessory = await db.accessories.find_one({'id': data.accessory_id, 'is_active': True}, {'_id': 0})
    if not accessory:
        raise HTTPException(status_code=404, detail="Accessory not found")
    
    dealer = await db.accessory_dealers.find_one({'id': data.dealer_id, 'is_active': True}, {'_id': 0})
    if not dealer:
        raise HTTPException(status_code=404, detail="Dealer not found")
    
    # Check if entry exists for this accessory, dealer and date
    existing = await db.accessory_entries.find_one({
        'accessory_id': data.accessory_id,
        'dealer_id': data.dealer_id,
        'date': data.date
    }, {'_id': 0})
    
    entry = {
        'id': existing['id'] if existing else str(uuid.uuid4()),
        'accessory_id': data.accessory_id,
        'accessory_name': accessory['name'],
        'dealer_id': data.dealer_id,
        'dealer_name': dealer['name'],
        'date': data.date,
        'total_issued': data.total_issued,
        'total_sold': data.total_sold,
        'total_remaining': data.total_remaining,
        'remarks': data.remarks[:500] if data.remarks else "",
        'submitted_by': user['name'],
        'submitted_at': datetime.now(timezone.utc).isoformat()
    }
    
    if existing:
        await db.accessory_entries.update_one({'id': existing['id']}, {'$set': entry})
    else:
        entry['created_at'] = datetime.now(timezone.utc).isoformat()
        await db.accessory_entries.insert_one(entry)
    
    return AccessoryEntryResponse(**entry)

@router.get("/accessory-entries")
async def get_accessory_entries(
    accessory_id: Optional[str] = None,
    dealer_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Get accessory entries with optional filters"""
    query = {}
    if accessory_id:
        query['accessory_id'] = accessory_id
    if dealer_id:
        query['dealer_id'] = dealer_id
    if start_date:
        query['date'] = {'$gte': start_date}
    if end_date:
        if 'date' in query:
            query['date']['$lte'] = end_date
        else:
            query['date'] = {'$lte': end_date}
    
    entries = await db.accessory_entries.find(query, {'_id': 0}).sort('date', -1).to_list(1000)
    return entries

@router.get("/accessory-entries/latest-remaining")
async def get_latest_accessory_remaining(
    accessory_id: str,
    dealer_id: str,
    before_date: str,
    user: dict = Depends(get_current_user)
):
    """Get the latest remaining quantity for an accessory and dealer before a specific date"""
    # Find the most recent entry before the given date
    entry = await db.accessory_entries.find_one(
        {
            'accessory_id': accessory_id,
            'dealer_id': dealer_id,
            'date': {'$lt': before_date}
        },
        {'_id': 0},
        sort=[('date', -1)]
    )
    
    if entry:
        return {'opening_stock': entry.get('total_remaining', 0), 'last_date': entry.get('date')}
    return {'opening_stock': 0, 'last_date': None}

@router.put("/accessory-entries/{entry_id}")
async def update_accessory_entry(entry_id: str, data: AccessoryEntryCreate, user: dict = Depends(require_admin)):
    """Update an accessory entry - Admin only"""
    existing = await db.accessory_entries.find_one({'id': entry_id}, {'_id': 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    accessory = await db.accessories.find_one({'id': data.accessory_id, 'is_active': True}, {'_id': 0})
    if not accessory:
        raise HTTPException(status_code=404, detail="Accessory not found")
    
    dealer = await db.accessory_dealers.find_one({'id': data.dealer_id, 'is_active': True}, {'_id': 0})
    if not dealer:
        raise HTTPException(status_code=404, detail="Dealer not found")
    
    update_data = {
        'accessory_id': data.accessory_id,
        'accessory_name': accessory['name'],
        'dealer_id': data.dealer_id,
        'dealer_name': dealer['name'],
        'date': data.date,
        'total_issued': data.total_issued,
        'total_sold': data.total_sold,
        'total_remaining': data.total_remaining,
        'remarks': data.remarks[:500] if data.remarks else "",
        'submitted_by': user['name'],
        'submitted_at': datetime.now(timezone.utc).isoformat()
    }
    
    await db.accessory_entries.update_one({'id': entry_id}, {'$set': update_data})
    
    updated = await db.accessory_entries.find_one({'id': entry_id}, {'_id': 0})
    return updated


@router.delete("/accessory-entries/{entry_id}")
async def delete_accessory_entry(entry_id: str, user: dict = Depends(require_admin)):
    """Delete an accessory entry - Admin only. Hard delete; summary/reports
    are recomputed on the next fetch."""
    existing = await db.accessory_entries.find_one({'id': entry_id}, {'_id': 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Entry not found")
    result = await db.accessory_entries.delete_one({'id': entry_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"success": True, "id": entry_id}


@router.get("/accessory-entries/summary")
async def get_accessory_summary(
    accessory_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Get dealer-wise accessory summary with totals"""
    query = {}
    if accessory_id:
        query['accessory_id'] = accessory_id
    if start_date:
        query['date'] = {'$gte': start_date}
    if end_date:
        if 'date' in query:
            query['date']['$lte'] = end_date
        else:
            query['date'] = {'$lte': end_date}
    
    # Aggregate by dealer and accessory
    pipeline = [
        {'$match': query} if query else {'$match': {}},
        {'$group': {
            '_id': {'dealer_id': '$dealer_id', 'accessory_id': '$accessory_id'},
            'dealer_name': {'$first': '$dealer_name'},
            'accessory_name': {'$first': '$accessory_name'},
            'total_issued': {'$sum': '$total_issued'},
            'total_sold': {'$sum': '$total_sold'},
            'latest_remaining': {'$last': '$total_remaining'},
            'entries_count': {'$sum': 1}
        }},
        {'$sort': {'accessory_name': 1, 'dealer_name': 1}}
    ]
    
    summary = []
    async for item in db.accessory_entries.aggregate(pipeline):
        summary.append({
            'dealer_id': item['_id']['dealer_id'],
            'accessory_id': item['_id']['accessory_id'],
            'dealer_name': item['dealer_name'],
            'accessory_name': item['accessory_name'],
            'total_issued': item['total_issued'],
            'total_sold': item['total_sold'],
            'latest_remaining': item['latest_remaining'],
            'entries_count': item['entries_count']
        })
    
    # Calculate grand totals
    grand_totals = {
        'total_issued': sum(s['total_issued'] for s in summary),
        'total_sold': sum(s['total_sold'] for s in summary),
    }
    
    return {'summary': summary, 'grand_totals': grand_totals}

# ============ ACCESSORY REPORT EXPORTS ============

@router.get("/export/accessory-pdf")
async def export_accessory_pdf(
    accessory_id: Optional[str] = None,
    dealer_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user: dict = Depends(require_admin)
):
    """Export accessory report as PDF - Admin only"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=18, textColor=colors.HexColor('#15803d'), alignment=1)
    elements.append(Paragraph("K3 GAS SERVICE - LPG Accessories Report", title_style))
    elements.append(Paragraph("Khayal Hamesha", styles['Normal']))
    elements.append(Spacer(1, 20))
    
    query = {}
    if accessory_id:
        query['accessory_id'] = accessory_id
    if dealer_id:
        query['dealer_id'] = dealer_id
    if start_date:
        query['date'] = {'$gte': start_date}
    if end_date:
        if 'date' in query:
            query['date']['$lte'] = end_date
        else:
            query['date'] = {'$lte': end_date}
    
    entries = await db.accessory_entries.find(query, {'_id': 0}).sort([('accessory_name', 1), ('dealer_name', 1), ('date', -1)]).to_list(1000)
    
    if start_date and end_date:
        elements.append(Paragraph(f"Period: {start_date} to {end_date}", styles['Normal']))
    elements.append(Spacer(1, 10))
    
    # Detail Table
    data = [['Date', 'Accessory', 'Dealer', 'Issued', 'Sold', 'Remaining', 'Remarks']]
    total_issued = 0
    total_sold = 0
    
    for e in entries:
        data.append([
            e['date'],
            e['accessory_name'],
            e['dealer_name'],
            e['total_issued'],
            e['total_sold'],
            e['total_remaining'],
            e.get('remarks', '')[:30]
        ])
        total_issued += e['total_issued']
        total_sold += e['total_sold']
    
    data.append(['TOTAL', '', '', total_issued, total_sold, '', ''])
    
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#7c3aed')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -2), colors.HexColor('#f3e8ff')),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#5b21b6')),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.whitesmoke),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
    ]))
    elements.append(table)
    
    doc.build(elements)
    buffer.seek(0)
    
    return Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=LPG_Accessories_Report_{datetime.now().strftime('%d%m%y')}.pdf"}
    )

@router.get("/export/accessory-excel")
async def export_accessory_excel(
    accessory_id: Optional[str] = None,
    dealer_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user: dict = Depends(require_admin)
):
    """Export accessory report as Excel - Admin only"""
    buffer = BytesIO()
    workbook = xlsxwriter.Workbook(buffer)
    
    # Formats
    header_format = workbook.add_format({'bold': True, 'bg_color': '#7c3aed', 'font_color': 'white', 'border': 1, 'align': 'center'})
    cell_format = workbook.add_format({'border': 1, 'align': 'center'})
    total_format = workbook.add_format({'bold': True, 'bg_color': '#5b21b6', 'font_color': 'white', 'border': 1, 'align': 'center'})
    
    query = {}
    if accessory_id:
        query['accessory_id'] = accessory_id
    if dealer_id:
        query['dealer_id'] = dealer_id
    if start_date:
        query['date'] = {'$gte': start_date}
    if end_date:
        if 'date' in query:
            query['date']['$lte'] = end_date
        else:
            query['date'] = {'$lte': end_date}
    
    entries = await db.accessory_entries.find(query, {'_id': 0}).sort([('accessory_name', 1), ('dealer_name', 1), ('date', -1)]).to_list(1000)
    
    # Sheet: Detailed entries
    sheet = workbook.add_worksheet('Accessory Entries')
    headers = ['Date', 'Accessory', 'Dealer', 'Issued', 'Sold', 'Remaining', 'Remarks']
    
    for col, header in enumerate(headers):
        sheet.write(0, col, header, header_format)
        sheet.set_column(col, col, 15)
    
    total_issued = 0
    total_sold = 0
    
    for row, e in enumerate(entries, 1):
        sheet.write(row, 0, e['date'], cell_format)
        sheet.write(row, 1, e['accessory_name'], cell_format)
        sheet.write(row, 2, e['dealer_name'], cell_format)
        sheet.write(row, 3, e['total_issued'], cell_format)
        sheet.write(row, 4, e['total_sold'], cell_format)
        sheet.write(row, 5, e['total_remaining'], cell_format)
        sheet.write(row, 6, e.get('remarks', ''), cell_format)
        
        total_issued += e['total_issued']
        total_sold += e['total_sold']
    
    # Totals row
    total_row = len(entries) + 1
    sheet.write(total_row, 0, 'TOTAL', total_format)
    sheet.write(total_row, 1, '', total_format)
    sheet.write(total_row, 2, '', total_format)
    sheet.write(total_row, 3, total_issued, total_format)
    sheet.write(total_row, 4, total_sold, total_format)
    sheet.write(total_row, 5, '', total_format)
    sheet.write(total_row, 6, '', total_format)
    
    workbook.close()
    buffer.seek(0)
    
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=LPG_Accessories_Report_{datetime.now().strftime('%d%m%y')}.xlsx"}
    )

# ============ ACCESSORY SALES ENDPOINTS ============

@router.post("/accessory-sales")
async def create_accessory_sale(data: AccessorySaleCreate, user: dict = Depends(get_current_user)):
    """Create a new accessory sale with multiple items"""
    
    # Handle customer
    customer_id = data.customer_id
    if data.is_new_customer or not customer_id:
        # Create new customer
        new_customer = {
            'id': str(uuid.uuid4()),
            'date': data.date,
            'customer_name': data.customer_name,
            'phone': data.customer_phone,
            'address': data.customer_address,
            'consumer_no': '',
            'connection_type': 'domestic',
            'warehouse_id': data.warehouse_id or user.get('warehouse_id', ''),
            'warehouse_name': '',
            'gas_card_issued': False,
            'kyc_done': False,
            'remarks': 'Created from accessory sale',
            'created_by': user['id'],
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        # Get warehouse name
        if new_customer['warehouse_id']:
            warehouse = await db.warehouses.find_one({'id': new_customer['warehouse_id']}, {'_id': 0})
            if warehouse:
                new_customer['warehouse_name'] = warehouse['name']
        await db.customers.insert_one(new_customer)
        customer_id = new_customer['id']
    
    # Process items
    sale_items = []
    subtotal = 0
    
    for item in data.items:
        accessory = await db.accessories.find_one({'id': item.accessory_id, 'is_active': True}, {'_id': 0})
        if not accessory:
            raise HTTPException(status_code=404, detail=f"Accessory not found: {item.accessory_id}")
        
        item_total = item.quantity * item.unit_price
        sale_items.append({
            'accessory_id': item.accessory_id,
            'accessory_name': accessory['name'],
            'quantity': item.quantity,
            'unit_price': item.unit_price,
            'total_amount': item_total
        })
        subtotal += item_total
    
    # Determine warehouse
    warehouse_id = data.warehouse_id or user.get('warehouse_id', '')
    warehouse_name = ''
    if warehouse_id:
        warehouse = await db.warehouses.find_one({'id': warehouse_id}, {'_id': 0})
        if warehouse:
            warehouse_name = warehouse['name']
    
    # Create sale record
    sale = {
        'id': str(uuid.uuid4()),
        'customer_id': customer_id,
        'customer_name': data.customer_name,
        'customer_phone': data.customer_phone,
        'customer_address': data.customer_address,
        'date': data.date,
        'memo_no': data.memo_no,
        'items': sale_items,
        'subtotal': subtotal,
        'amount': subtotal,
        'grand_total': subtotal,
        'payment_mode': data.payment_mode,
        'remarks': data.remarks,
        'warehouse_id': warehouse_id,
        'warehouse_name': warehouse_name,
        'created_by': user['id'],
        'created_by_name': user['name'],
        'created_at': datetime.now(timezone.utc).isoformat()
    }

    # Note: Discrepancy validation is intentionally NOT applied to accessory sales
    # because accessories are sold at dealer-set variable prices (no fixed master rate).

    await db.accessory_sales.insert_one(sale)
    
    # Update inventory - deduct from the LATEST accessory entry for each item
    for item in data.items:
        # Find the latest entry for this accessory (across all dealers)
        latest_entry = await db.accessory_entries.find_one(
            {'accessory_id': item.accessory_id},
            {'_id': 0},
            sort=[('date', -1)]
        )
        
        if latest_entry:
            # Update the entry's total_sold and total_remaining
            current_sold = latest_entry.get('total_sold', 0)
            current_issued = latest_entry.get('total_issued', 0)
            new_sold = current_sold + item.quantity
            new_remaining = current_issued - new_sold
            
            await db.accessory_entries.update_one(
                {'id': latest_entry['id']},
                {'$set': {
                    'total_sold': new_sold, 
                    'total_remaining': max(0, new_remaining)  # Prevent negative values
                }}
            )
    
    # Remove _id if present
    sale.pop('_id', None)
    
    # Auto-generate GST invoice (best-effort, non-blocking)
    await auto_generate_invoice_from_sale(sale, 'accessory_sale', user)
    
    return sale

@router.get("/accessory-sales")
async def get_accessory_sales(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    customer_name: Optional[str] = None,
    warehouse_id: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Get all accessory sales with optional filters"""
    query = {}
    
    if start_date:
        query['date'] = {'$gte': start_date}
    if end_date:
        if 'date' in query:
            query['date']['$lte'] = end_date
        else:
            query['date'] = {'$lte': end_date}
    
    if customer_name:
        query['customer_name'] = {'$regex': customer_name, '$options': 'i'}
    
    # Filter by warehouse for non-admin
    if user['role'] != 'admin':
        query['warehouse_id'] = user.get('warehouse_id', '')
    elif warehouse_id and warehouse_id != 'all':
        query['warehouse_id'] = warehouse_id
    
    sales = await db.accessory_sales.find(query, {'_id': 0}).sort([('date', -1), ('created_at', -1)]).to_list(1000)
    return sales

@router.get("/accessory-sales/{sale_id}")
async def get_accessory_sale(sale_id: str, user: dict = Depends(get_current_user)):
    """Get a specific accessory sale by ID"""
    sale = await db.accessory_sales.find_one({'id': sale_id}, {'_id': 0})
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")
    return sale

@router.delete("/accessory-sales/{sale_id}")
async def delete_accessory_sale(sale_id: str, user: dict = Depends(require_admin)):
    """Delete an accessory sale - Admin only"""
    sale = await db.accessory_sales.find_one({'id': sale_id}, {'_id': 0})
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")
    
    await db.accessory_sales.delete_one({'id': sale_id})
    return {"message": "Sale deleted successfully"}

@router.get("/accessory-sales-summary")
async def get_accessory_sales_summary(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    warehouse_id: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Get summary of accessory sales"""
    query = {}
    
    if start_date:
        query['date'] = {'$gte': start_date}
    if end_date:
        if 'date' in query:
            query['date']['$lte'] = end_date
        else:
            query['date'] = {'$lte': end_date}
    
    if user['role'] != 'admin':
        query['warehouse_id'] = user.get('warehouse_id', '')
    elif warehouse_id:
        query['warehouse_id'] = warehouse_id
    
    sales = await db.accessory_sales.find(query, {'_id': 0}).to_list(1000)
    
    total_sales = len(sales)
    total_amount = sum(s.get('grand_total', 0) for s in sales)
    cash_amount = sum(s.get('grand_total', 0) for s in sales if s.get('payment_mode') == 'cash')
    pending_amount = sum(s.get('grand_total', 0) for s in sales if s.get('payment_mode') == 'pending')
    online_amount = sum(s.get('grand_total', 0) for s in sales if s.get('payment_mode') == 'online')
    
    # Items sold count
    total_items = sum(len(s.get('items', [])) for s in sales)
    total_qty = sum(sum(i.get('quantity', 0) for i in s.get('items', [])) for s in sales)
    
    return {
        'total_sales': total_sales,
        'total_amount': total_amount,
        'cash_amount': cash_amount,
        'pending_amount': pending_amount,
        'online_amount': online_amount,
        'total_items': total_items,
        'total_quantity': total_qty
    }

@router.get("/export/accessory-sales-pdf")
async def export_accessory_sales_pdf(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    warehouse_id: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Export accessory sales as PDF"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
    elements = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=14, fontName='Helvetica-Bold', textColor=colors.HexColor('#7c3aed'), alignment=1)
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=13, alignment=1)
    
    elements.append(Paragraph("K3 GAS SERVICE - LPG Accessories Sales Report", title_style))
    elements.append(Paragraph("Khayal Hamesha", subtitle_style))
    if start_date and end_date:
        elements.append(Paragraph(f"Period: {start_date} to {end_date}", ParagraphStyle('Period', fontSize=10, alignment=1)))
    elements.append(Spacer(1, 10))
    
    # Query
    query = {}
    if start_date:
        query['date'] = {'$gte': start_date}
    if end_date:
        if 'date' in query:
            query['date']['$lte'] = end_date
        else:
            query['date'] = {'$lte': end_date}
    
    if user['role'] != 'admin':
        query['warehouse_id'] = user.get('warehouse_id', '')
    elif warehouse_id and warehouse_id != 'all':
        query['warehouse_id'] = warehouse_id
    
    sales = await db.accessory_sales.find(query, {'_id': 0}).sort([('date', -1), ('created_at', -1)]).to_list(1000)
    
    # Flatten items for table - include Memo No
    data = [['SL', 'Date', 'Memo No', 'Customer', 'Phone', 'Accessory', 'Qty', 'Unit Price', 'Total', 'Payment', 'Warehouse', 'Created By']]
    
    sl = 1
    grand_total = 0
    for sale in sales:
        for item in sale.get('items', []):
            data.append([
                str(sl),
                sale.get('date', '')[-5:],
                sale.get('memo_no', '')[:10],
                sale.get('customer_name', '')[:12],
                sale.get('customer_phone', '')[:10],
                item.get('accessory_name', '')[:12],
                str(item.get('quantity', 0)),
                format_inr(item.get('unit_price', 0)),
                format_inr(item.get('total_amount', 0)),
                sale.get('payment_mode', 'cash')[:6].title(),
                sale.get('warehouse_name', '')[:8],
                sale.get('created_by_name', '')[:8]
            ])
            grand_total += item.get('total_amount', 0)
            sl += 1
    
    data.append(['', '', '', '', '', '', 'GRAND TOTAL:', '', format_inr(grand_total), '', '', ''])
    
    col_widths = [22, 42, 50, 70, 60, 70, 30, 55, 55, 45, 55, 55]
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#7c3aed')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e9d5ff')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ]))
    elements.append(table)
    
    doc.build(elements)
    buffer.seek(0)
    
    return Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Accessory_Sales_{datetime.now().strftime('%d%m%y')}.pdf"}
    )

@router.get("/export/accessory-sales-excel")
async def export_accessory_sales_excel(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    warehouse_id: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Export accessory sales as Excel"""
    buffer = BytesIO()
    workbook = xlsxwriter.Workbook(buffer)
    
    # Formats
    title_format = workbook.add_format({'bold': True, 'font_size': 14, 'align': 'center', 'bg_color': '#7c3aed', 'font_color': 'white'})
    header_format = workbook.add_format({'bold': True, 'bg_color': '#7c3aed', 'font_color': 'white', 'border': 1, 'align': 'center'})
    cell_format = workbook.add_format({'border': 1, 'align': 'center'})
    total_format = workbook.add_format({'bold': True, 'bg_color': '#e9d5ff', 'border': 1, 'align': 'center'})
    money_format = workbook.add_format({'border': 1, 'align': 'right', 'num_format': '#,##0.00'})
    
    # Query
    query = {}
    if start_date:
        query['date'] = {'$gte': start_date}
    if end_date:
        if 'date' in query:
            query['date']['$lte'] = end_date
        else:
            query['date'] = {'$lte': end_date}
    
    if user['role'] != 'admin':
        query['warehouse_id'] = user.get('warehouse_id', '')
    elif warehouse_id and warehouse_id != 'all':
        query['warehouse_id'] = warehouse_id
    
    sales = await db.accessory_sales.find(query, {'_id': 0}).sort([('date', -1), ('created_at', -1)]).to_list(1000)
    
    # Worksheet - include Memo No
    ws = workbook.add_worksheet('Accessory Sales')
    ws.merge_range('A1:L1', 'K3 GAS SERVICE - LPG Accessories Sales Report', title_format)
    if start_date and end_date:
        ws.merge_range('A2:L2', f'Period: {start_date} to {end_date}', workbook.add_format({'align': 'center'}))
    
    headers = ['SL No.', 'Date', 'Memo No', 'Customer Name', 'Phone', 'Accessory', 'Qty', 'Unit Price (Rs.)', 'Total (Rs.)', 'Payment', 'Warehouse', 'Created By']
    for col, header in enumerate(headers):
        ws.write(3, col, header, header_format)
        ws.set_column(col, col, 14)
    
    row = 4
    sl = 1
    grand_total = 0
    
    for sale in sales:
        for item in sale.get('items', []):
            ws.write(row, 0, sl, cell_format)
            ws.write(row, 1, sale.get('date', ''), cell_format)
            ws.write(row, 2, sale.get('memo_no', ''), cell_format)
            ws.write(row, 3, sale.get('customer_name', ''), cell_format)
            ws.write(row, 4, sale.get('customer_phone', ''), cell_format)
            ws.write(row, 5, item.get('accessory_name', ''), cell_format)
            ws.write(row, 6, item.get('quantity', 0), cell_format)
            ws.write(row, 7, item.get('unit_price', 0), money_format)
            ws.write(row, 8, item.get('total_amount', 0), money_format)
            ws.write(row, 9, sale.get('payment_mode', 'cash').title(), cell_format)
            ws.write(row, 10, sale.get('warehouse_name', ''), cell_format)
            ws.write(row, 11, sale.get('created_by_name', ''), cell_format)
            grand_total += item.get('total_amount', 0)
            sl += 1
            row += 1
    
    # Total row
    ws.write(row, 6, 'GRAND TOTAL:', total_format)
    ws.write(row, 7, '', total_format)
    ws.write(row, 8, grand_total, total_format)
    
    workbook.close()
    buffer.seek(0)
    
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=Accessory_Sales_{datetime.now().strftime('%d%m%y')}.xlsx"}
    )

