from fastapi import APIRouter, HTTPException, Depends, Response
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from database import db
from deps import get_current_user, require_admin, security
from helpers import format_inr
from models import DealerCreate, DealerResponse, DealerEntryCreate, DealerEntryResponse
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

router = APIRouter()

# ============ DEALER MANAGEMENT ============

@router.post("/dealers", response_model=DealerResponse)
async def create_dealer(data: DealerCreate, user: dict = Depends(get_current_user)):
    """Create a new dealer - Plant Hollongi only"""
    dealer = {
        'id': str(uuid.uuid4()),
        'name': data.name,
        'contact': data.contact,
        'address': data.address,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'is_active': True
    }
    await db.dealers.insert_one(dealer)
    return DealerResponse(**dealer)

@router.get("/dealers")
async def get_dealers(user: dict = Depends(get_current_user)):
    """Get all dealers"""
    dealers = await db.dealers.find({'is_active': True}, {'_id': 0}).to_list(1000)
    return dealers

@router.put("/dealers/{dealer_id}")
async def update_dealer(dealer_id: str, data: DealerCreate, user: dict = Depends(get_current_user)):
    """Update a dealer"""
    result = await db.dealers.update_one(
        {'id': dealer_id},
        {'$set': {'name': data.name, 'contact': data.contact, 'address': data.address}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Dealer not found")
    dealer = await db.dealers.find_one({'id': dealer_id}, {'_id': 0})
    return dealer

@router.delete("/dealers/{dealer_id}")
async def delete_dealer(dealer_id: str, user: dict = Depends(get_current_user)):
    """Soft delete a dealer"""
    result = await db.dealers.update_one({'id': dealer_id}, {'$set': {'is_active': False}})
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Dealer not found")
    return {"message": "Dealer deleted successfully"}

# ============ DEALER ENTRIES ============

@router.post("/dealer-entries", response_model=DealerEntryResponse)
async def create_dealer_entry(data: DealerEntryCreate, user: dict = Depends(get_current_user)):
    """Create a dealer entry for cylinder issuance/refilling"""
    dealer = await db.dealers.find_one({'id': data.dealer_id, 'is_active': True}, {'_id': 0})
    if not dealer:
        raise HTTPException(status_code=404, detail="Dealer not found")
    
    # Check if entry exists for this dealer and date
    existing = await db.dealer_entries.find_one({'dealer_id': data.dealer_id, 'date': data.date}, {'_id': 0})
    
    entry = {
        'id': existing['id'] if existing else str(uuid.uuid4()),
        'dealer_id': data.dealer_id,
        'dealer_name': dealer['name'],
        'date': data.date,
        'issued_15kg': data.issued_15kg,
        'issued_21kg': data.issued_21kg,
        'refilled_15kg': data.refilled_15kg,
        'refilled_21kg': data.refilled_21kg,
        'remarks': data.remarks[:500] if data.remarks else "",
        'submitted_by': user['name'],
        'submitted_at': datetime.now(timezone.utc).isoformat()
    }
    
    if existing:
        await db.dealer_entries.update_one({'id': existing['id']}, {'$set': entry})
    else:
        entry['created_at'] = datetime.now(timezone.utc).isoformat()
        await db.dealer_entries.insert_one(entry)
    
    return DealerEntryResponse(**entry)

@router.get("/dealer-entries")
async def get_dealer_entries(
    dealer_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Get dealer entries with optional filters"""
    query = {}
    if dealer_id:
        query['dealer_id'] = dealer_id
    if start_date:
        query['date'] = {'$gte': start_date}
    if end_date:
        if 'date' in query:
            query['date']['$lte'] = end_date
        else:
            query['date'] = {'$lte': end_date}
    
    entries = await db.dealer_entries.find(query, {'_id': 0}).sort('date', -1).to_list(1000)
    return entries

@router.get("/dealer-entries/summary")
async def get_dealer_summary(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Get dealer-wise summary with totals"""
    query = {}
    if start_date:
        query['date'] = {'$gte': start_date}
    if end_date:
        if 'date' in query:
            query['date']['$lte'] = end_date
        else:
            query['date'] = {'$lte': end_date}
    
    # Aggregate by dealer
    pipeline = [
        {'$match': query} if query else {'$match': {}},
        {'$group': {
            '_id': '$dealer_id',
            'dealer_name': {'$first': '$dealer_name'},
            'total_issued_15kg': {'$sum': {'$ifNull': ['$issued_15kg', 0]}},
            'total_issued_21kg': {'$sum': {'$ifNull': ['$issued_21kg', 0]}},
            'total_refilled_15kg': {'$sum': {'$ifNull': ['$refilled_15kg', 0]}},
            'total_refilled_21kg': {'$sum': {'$ifNull': ['$refilled_21kg', 0]}},
            'total_returned_empty_15kg': {'$sum': {'$ifNull': ['$returned_empty_15kg', 0]}},
            'total_returned_empty_21kg': {'$sum': {'$ifNull': ['$returned_empty_21kg', 0]}},
            'entries_count': {'$sum': 1}
        }},
        {'$sort': {'dealer_name': 1}}
    ]
    
    summary = []
    async for item in db.dealer_entries.aggregate(pipeline):
        issued15 = item['total_issued_15kg']
        issued21 = item['total_issued_21kg']
        returned15 = item['total_returned_empty_15kg']
        returned21 = item['total_returned_empty_21kg']
        summary.append({
            'dealer_id': item['_id'],
            'dealer_name': item['dealer_name'],
            'total_issued_15kg': issued15,
            'total_issued_21kg': issued21,
            'total_refilled_15kg': item['total_refilled_15kg'],
            'total_refilled_21kg': item['total_refilled_21kg'],
            'total_returned_empty_15kg': returned15,
            'total_returned_empty_21kg': returned21,
            # Net empty balance = issued - returned (positive = dealer owes empties)
            'empty_balance_15kg': issued15 - returned15,
            'empty_balance_21kg': issued21 - returned21,
            'entries_count': item['entries_count']
        })
    
    # Calculate grand totals
    grand_totals = {
        'total_issued_15kg': sum(s['total_issued_15kg'] for s in summary),
        'total_issued_21kg': sum(s['total_issued_21kg'] for s in summary),
        'total_refilled_15kg': sum(s['total_refilled_15kg'] for s in summary),
        'total_refilled_21kg': sum(s['total_refilled_21kg'] for s in summary),
        'total_returned_empty_15kg': sum(s['total_returned_empty_15kg'] for s in summary),
        'total_returned_empty_21kg': sum(s['total_returned_empty_21kg'] for s in summary),
        'empty_balance_15kg': sum(s['empty_balance_15kg'] for s in summary),
        'empty_balance_21kg': sum(s['empty_balance_21kg'] for s in summary),
    }
    
    return {'dealers': summary, 'grand_totals': grand_totals}

@router.put("/dealer-entries/{entry_id}")
async def update_dealer_entry(entry_id: str, data: DealerEntryCreate, user: dict = Depends(get_current_user)):
    """Update a dealer entry"""
    existing = await db.dealer_entries.find_one({'id': entry_id}, {'_id': 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    dealer = await db.dealers.find_one({'id': data.dealer_id}, {'_id': 0})
    if not dealer:
        raise HTTPException(status_code=404, detail="Dealer not found")
    
    update_data = {
        'dealer_id': data.dealer_id,
        'dealer_name': dealer['name'],
        'date': data.date,
        'issued_15kg': data.issued_15kg,
        'issued_21kg': data.issued_21kg,
        'refilled_15kg': data.refilled_15kg,
        'refilled_21kg': data.refilled_21kg,
        'remarks': data.remarks[:500] if data.remarks else "",
        'submitted_by': user['name'],
        'submitted_at': datetime.now(timezone.utc).isoformat()
    }
    
    await db.dealer_entries.update_one({'id': entry_id}, {'$set': update_data})
    updated = await db.dealer_entries.find_one({'id': entry_id}, {'_id': 0})
    return updated


# ============ DEALER REPORT EXPORTS ============

# ============ DEALER REPORT EXPORTS ============

@router.get("/export/dealer-pdf")
async def export_dealer_pdf(
    dealer_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Export dealer report as PDF"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=18, textColor=colors.HexColor('#15803d'), alignment=1)
    elements.append(Paragraph("K3 GAS SERVICE - Dealer Report", title_style))
    elements.append(Paragraph("Khayal Hamesha", styles['Normal']))
    elements.append(Spacer(1, 20))
    
    query = {}
    if dealer_id:
        query['dealer_id'] = dealer_id
    if start_date:
        query['date'] = {'$gte': start_date}
    if end_date:
        if 'date' in query:
            query['date']['$lte'] = end_date
        else:
            query['date'] = {'$lte': end_date}
    
    entries = await db.dealer_entries.find(query, {'_id': 0}).sort([('dealer_name', 1), ('date', -1)]).to_list(1000)
    
    if start_date and end_date:
        elements.append(Paragraph(f"Period: {start_date} to {end_date}", styles['Normal']))
    elements.append(Spacer(1, 10))
    
    # Detail Table
    data = [['Date', 'Dealer', '15kg Issued', '21kg Issued', '15kg Refilled', '21kg Refilled', 'Remarks']]
    total_issued_15kg = 0
    total_issued_21kg = 0
    total_refilled_15kg = 0
    total_refilled_21kg = 0
    
    for e in entries:
        data.append([
            e['date'],
            e['dealer_name'],
            e['issued_15kg'],
            e['issued_21kg'],
            e['refilled_15kg'],
            e['refilled_21kg'],
            e.get('remarks', '')[:30]
        ])
        total_issued_15kg += e['issued_15kg']
        total_issued_21kg += e['issued_21kg']
        total_refilled_15kg += e['refilled_15kg']
        total_refilled_21kg += e['refilled_21kg']
    
    # Add totals row
    data.append(['TOTAL', '', total_issued_15kg, total_issued_21kg, total_refilled_15kg, total_refilled_21kg, ''])
    
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#15803d')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#166534')),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.whitesmoke),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
    ]))
    elements.append(table)
    
    # Summary section
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("Dealer-wise Summary", styles['Heading2']))
    elements.append(Spacer(1, 10))
    
    # Get summary
    pipeline = [
        {'$match': query} if query else {'$match': {}},
        {'$group': {
            '_id': '$dealer_id',
            'dealer_name': {'$first': '$dealer_name'},
            'total_issued_15kg': {'$sum': '$issued_15kg'},
            'total_issued_21kg': {'$sum': '$issued_21kg'},
            'total_refilled_15kg': {'$sum': '$refilled_15kg'},
            'total_refilled_21kg': {'$sum': '$refilled_21kg'},
        }},
        {'$sort': {'dealer_name': 1}}
    ]
    
    summary_data = [['Dealer', '15kg Issued', '21kg Issued', '15kg Refilled', '21kg Refilled']]
    async for item in db.dealer_entries.aggregate(pipeline):
        summary_data.append([
            item['dealer_name'],
            item['total_issued_15kg'],
            item['total_issued_21kg'],
            item['total_refilled_15kg'],
            item['total_refilled_21kg']
        ])
    summary_data.append(['GRAND TOTAL', total_issued_15kg, total_issued_21kg, total_refilled_15kg, total_refilled_21kg])
    
    summary_table = Table(summary_data, repeatRows=1)
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#1e3a8a')),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.whitesmoke),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(summary_table)
    
    doc.build(elements)
    buffer.seek(0)
    
    return Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Dealer_Report_{datetime.now().strftime('%d%m%y')}.pdf"}
    )

@router.get("/export/dealer-excel")
async def export_dealer_excel(
    dealer_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Export dealer report as Excel"""
    buffer = BytesIO()
    workbook = xlsxwriter.Workbook(buffer)
    
    # Formats
    header_format = workbook.add_format({'bold': True, 'bg_color': '#15803d', 'font_color': 'white', 'border': 1, 'align': 'center'})
    cell_format = workbook.add_format({'border': 1, 'align': 'center'})
    total_format = workbook.add_format({'bold': True, 'bg_color': '#166534', 'font_color': 'white', 'border': 1, 'align': 'center'})
    summary_header = workbook.add_format({'bold': True, 'bg_color': '#1e40af', 'font_color': 'white', 'border': 1, 'align': 'center'})
    summary_total = workbook.add_format({'bold': True, 'bg_color': '#1e3a8a', 'font_color': 'white', 'border': 1, 'align': 'center'})
    
    query = {}
    if dealer_id:
        query['dealer_id'] = dealer_id
    if start_date:
        query['date'] = {'$gte': start_date}
    if end_date:
        if 'date' in query:
            query['date']['$lte'] = end_date
        else:
            query['date'] = {'$lte': end_date}
    
    entries = await db.dealer_entries.find(query, {'_id': 0}).sort([('dealer_name', 1), ('date', -1)]).to_list(1000)
    
    # Sheet 1: Detailed entries
    sheet = workbook.add_worksheet('Dealer Entries')
    headers = ['Date', 'Dealer', '15kg Issued', '21kg Issued', '15kg Refilled', '21kg Refilled', 'Remarks']
    
    for col, header in enumerate(headers):
        sheet.write(0, col, header, header_format)
        sheet.set_column(col, col, 15)
    
    total_issued_15kg = 0
    total_issued_21kg = 0
    total_refilled_15kg = 0
    total_refilled_21kg = 0
    
    for row, e in enumerate(entries, 1):
        sheet.write(row, 0, e['date'], cell_format)
        sheet.write(row, 1, e['dealer_name'], cell_format)
        sheet.write(row, 2, e['issued_15kg'], cell_format)
        sheet.write(row, 3, e['issued_21kg'], cell_format)
        sheet.write(row, 4, e['refilled_15kg'], cell_format)
        sheet.write(row, 5, e['refilled_21kg'], cell_format)
        sheet.write(row, 6, e.get('remarks', ''), cell_format)
        
        total_issued_15kg += e['issued_15kg']
        total_issued_21kg += e['issued_21kg']
        total_refilled_15kg += e['refilled_15kg']
        total_refilled_21kg += e['refilled_21kg']
    
    # Totals row
    total_row = len(entries) + 1
    sheet.write(total_row, 0, 'TOTAL', total_format)
    sheet.write(total_row, 1, '', total_format)
    sheet.write(total_row, 2, total_issued_15kg, total_format)
    sheet.write(total_row, 3, total_issued_21kg, total_format)
    sheet.write(total_row, 4, total_refilled_15kg, total_format)
    sheet.write(total_row, 5, total_refilled_21kg, total_format)
    sheet.write(total_row, 6, '', total_format)
    
    # Sheet 2: Summary
    summary_sheet = workbook.add_worksheet('Dealer Summary')
    summary_headers = ['Dealer', '15kg Issued', '21kg Issued', '15kg Refilled', '21kg Refilled']
    
    for col, header in enumerate(summary_headers):
        summary_sheet.write(0, col, header, summary_header)
        summary_sheet.set_column(col, col, 18)
    
    # Get summary
    pipeline = [
        {'$match': query} if query else {'$match': {}},
        {'$group': {
            '_id': '$dealer_id',
            'dealer_name': {'$first': '$dealer_name'},
            'total_issued_15kg': {'$sum': '$issued_15kg'},
            'total_issued_21kg': {'$sum': '$issued_21kg'},
            'total_refilled_15kg': {'$sum': '$refilled_15kg'},
            'total_refilled_21kg': {'$sum': '$refilled_21kg'},
        }},
        {'$sort': {'dealer_name': 1}}
    ]
    
    row = 1
    async for item in db.dealer_entries.aggregate(pipeline):
        summary_sheet.write(row, 0, item['dealer_name'], cell_format)
        summary_sheet.write(row, 1, item['total_issued_15kg'], cell_format)
        summary_sheet.write(row, 2, item['total_issued_21kg'], cell_format)
        summary_sheet.write(row, 3, item['total_refilled_15kg'], cell_format)
        summary_sheet.write(row, 4, item['total_refilled_21kg'], cell_format)
        row += 1
    
    # Grand total
    summary_sheet.write(row, 0, 'GRAND TOTAL', summary_total)
    summary_sheet.write(row, 1, total_issued_15kg, summary_total)
    summary_sheet.write(row, 2, total_issued_21kg, summary_total)
    summary_sheet.write(row, 3, total_refilled_15kg, summary_total)
    summary_sheet.write(row, 4, total_refilled_21kg, summary_total)
    
    workbook.close()
    buffer.seek(0)
    
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=Dealer_Report_{datetime.now().strftime('%d%m%y')}.xlsx"}
    )

