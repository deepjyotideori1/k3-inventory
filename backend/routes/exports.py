from fastapi import APIRouter, HTTPException, Depends, Response
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from database import db
from deps import get_current_user, require_admin, security
from helpers import format_inr
from datetime import datetime, timezone, timedelta
from io import BytesIO
from typing import List, Optional, Dict, Any
import uuid
import json

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import xlsxwriter

router = APIRouter()

# ============ EXPORT ROUTES ============

@router.get("/export/pdf")
async def export_pdf(
    warehouse_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    report_type: str = "daily",
    user: dict = Depends(get_current_user)
):
    buffer = BytesIO()
    # A4 landscape for fit-to-page
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=15, leftMargin=15, topMargin=15, bottomMargin=15)
    elements = []
    styles = getSampleStyleSheet()
    
    # Header font size 14 bold, body font size 13
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=14, spaceAfter=5, alignment=1, textColor=colors.HexColor('#15803d'))
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=12, spaceAfter=3, alignment=1)
    
    elements.append(Paragraph("K3 GAS SERVICE - Khayal Hamesha", title_style))
    
    if report_type == "daily":
        query = {}
        if user['role'] != 'admin':
            query['warehouse_id'] = user.get('warehouse_id')
        elif warehouse_id:
            query['warehouse_id'] = warehouse_id
        
        if start_date:
            query['date'] = {'$gte': start_date}
        if end_date:
            if 'date' in query:
                query['date']['$lte'] = end_date
            else:
                query['date'] = {'$lte': end_date}
        
        reports = await db.daily_reports.find(query, {'_id': 0}).sort('date', -1).to_list(1000)
        
        warehouse_name = "All Warehouses"
        if user['role'] != 'admin':
            warehouse_name = user.get('warehouse_name', 'My Warehouse')
        elif warehouse_id:
            wh = await db.warehouses.find_one({'id': warehouse_id}, {'_id': 0})
            warehouse_name = wh['name'] if wh else warehouse_id
        
        elements.append(Paragraph(f"Daily Inventory Report - {warehouse_name}", subtitle_style))
        if start_date and end_date:
            elements.append(Paragraph(f"Period: {start_date} to {end_date}", ParagraphStyle('Period', fontSize=10, alignment=1)))
        elements.append(Spacer(1, 5))
        
        # Comprehensive table - fit to A4 landscape
        data = [[
            'Date', 'Warehouse',
            'Op.15F', 'Op.21F', 'Op.15E', 'Op.21E',
            'Sold15', 'Sold21', 'Ref15', 'Ref21',
            'Refill to\nPlant 15kg', 'Refill to\nPlant 21kg', 'Received from\nPlant-15kg', 'Received from\nPlant-21kg',
            'Cl.15F', 'Cl.21F', 'Cl.15E', 'Cl.21E', 'Stat'
        ]]
        
        for r in reports:
            status = "Disc" if r.get('has_discrepancy') else "OK"
            data.append([
                r.get('date', '')[-5:],  # Show MM-DD only
                r.get('warehouse_name', '')[:8],
                r.get('opening_15kg_filled', 0),
                r.get('opening_21kg_filled', 0),
                r.get('opening_15kg_empty', 0),
                r.get('opening_21kg_empty', 0),
                r.get('sold_15kg_filled', 0),
                r.get('sold_21kg_filled', 0),
                r.get('refilling_15kg', 0),
                r.get('refilling_21kg', 0),
                r.get('refilling_plant_15kg', 0),
                r.get('refilling_plant_21kg', 0),
                r.get('received_from_plant_15kg', 0),
                r.get('received_from_plant_21kg', 0),
                r.get('closing_15kg_filled', 0),
                r.get('closing_21kg_filled', 0),
                r.get('closing_15kg_empty', 0),
                r.get('closing_21kg_empty', 0),
                status
            ])
        
        # Calculate column widths to fit A4 landscape (842 points width - 30 margins = 812)
        # Wider columns for the longer headers (Refill to Plant, Received from Plant)
        col_widths = [40, 42, 32, 32, 32, 32, 32, 32, 32, 32, 52, 52, 55, 55, 32, 32, 32, 32, 26]
        table = Table(data, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#15803d')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 6),  # Header - smaller for longer text
            ('FONTSIZE', (0, 1), (-1, -1), 7),  # Body
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BACKGROUND', (2, 1), (5, -1), colors.HexColor('#dbeafe')),  # Opening - blue
            ('BACKGROUND', (6, 1), (13, -1), colors.HexColor('#fef3c7')),  # Activity - yellow
            ('BACKGROUND', (14, 1), (17, -1), colors.HexColor('#dcfce7')),  # Closing - green
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements.append(table)
    
    elif report_type == "plant":
        query = {}
        if start_date:
            query['date'] = {'$gte': start_date}
        if end_date:
            if 'date' in query:
                query['date']['$lte'] = end_date
            else:
                query['date'] = {'$lte': end_date}
        
        reports = await db.plant_reports.find(query, {'_id': 0}).sort('date', -1).to_list(1000)
        
        elements.append(Paragraph("Plant Hollongi Report", subtitle_style))
        if start_date and end_date:
            elements.append(Paragraph(f"Period: {start_date} to {end_date}", ParagraphStyle('Period', fontSize=10, alignment=1)))
        elements.append(Spacer(1, 5))
        
        # Comprehensive Plant table with all form data
        data = [[
            'Date',
            'Op.Tank', 'Op.15F', 'Op.21F', 'Op.15E', 'Op.21E',
            'Reload', 'Recv15', 'Recv21',
            'Refill15', 'Refill21',
            'Del.15', 'Del.21',
            'Cl.Tank', 'Cl.15F', 'Cl.21F', 'Cl.15E', 'Cl.21E'
        ]]
        
        for r in reports:
            # Calculate totals for deliveries
            del_15 = sum([d.get('quantity', 0) for d in r.get('delivery_15kg', [])])
            del_21 = sum([d.get('quantity', 0) for d in r.get('delivery_21kg', [])])
            recv_15 = sum([d.get('quantity', 0) for d in r.get('received_empty_15kg', [])])
            recv_21 = sum([d.get('quantity', 0) for d in r.get('received_empty_21kg', [])])
            
            data.append([
                r.get('date', '')[-5:],
                r.get('opening_bullet_tank_kg', 0),
                r.get('opening_15kg_filled', 0),
                r.get('opening_21kg_filled', 0),
                r.get('opening_15kg_empty', 0),
                r.get('opening_21kg_empty', 0),
                r.get('day_reloading_kg', 0),
                recv_15,
                recv_21,
                r.get('day_refilled_15kg', 0),
                r.get('day_refilled_21kg', 0),
                del_15,
                del_21,
                r.get('closing_bullet_tank_kg', 0),
                r.get('closing_15kg_filled', 0),
                r.get('closing_21kg_filled', 0),
                r.get('closing_15kg_empty', 0),
                r.get('closing_21kg_empty', 0)
            ])
        
        col_widths = [42] + [42]*17
        table = Table(data, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#15803d')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 7),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 4),
            ('BACKGROUND', (1, 1), (5, -1), colors.HexColor('#dbeafe')),  # Opening - blue
            ('BACKGROUND', (6, 1), (6, -1), colors.HexColor('#cffafe')),  # Reloading - cyan
            ('BACKGROUND', (7, 1), (12, -1), colors.HexColor('#fef3c7')),  # Activity - yellow
            ('BACKGROUND', (13, 1), (17, -1), colors.HexColor('#dcfce7')),  # Closing - green
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements.append(table)
        
        # Add detailed warehouse breakdown for each report
        elements.append(Spacer(1, 15))
        elements.append(Paragraph("Warehouse-wise Breakdown", subtitle_style))
        elements.append(Spacer(1, 5))
        
        for r in reports:
            report_date = r.get('date', '')
            deliveries = r.get('delivery_15kg', []) + r.get('delivery_21kg', [])
            received = r.get('received_empty_15kg', []) + r.get('received_empty_21kg', [])
            
            if deliveries or received:
                elements.append(Paragraph(f"Date: {report_date}", ParagraphStyle('DateHeader', fontSize=10, fontName='Helvetica-Bold')))
                elements.append(Spacer(1, 3))
                
                # Delivery to Warehouses table
                if r.get('delivery_15kg', []) or r.get('delivery_21kg', []):
                    elements.append(Paragraph("Delivery to Warehouses (Filled Cylinders)", ParagraphStyle('SubHeader', fontSize=9, textColor=colors.HexColor('#4338ca'))))
                    del_data = [['Warehouse', '15kg Filled', '21kg Filled']]
                    warehouse_del = {}
                    for d in r.get('delivery_15kg', []):
                        wname = d.get('warehouse_name', 'Unknown')
                        if wname not in warehouse_del:
                            warehouse_del[wname] = {'qty15': 0, 'qty21': 0}
                        warehouse_del[wname]['qty15'] = d.get('quantity', 0)
                    for d in r.get('delivery_21kg', []):
                        wname = d.get('warehouse_name', 'Unknown')
                        if wname not in warehouse_del:
                            warehouse_del[wname] = {'qty15': 0, 'qty21': 0}
                        warehouse_del[wname]['qty21'] = d.get('quantity', 0)
                    for wname, qty in warehouse_del.items():
                        del_data.append([wname, qty['qty15'], qty['qty21']])
                    
                    del_table = Table(del_data, colWidths=[150, 80, 80])
                    del_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#c7d2fe')),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, -1), 8),
                        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ]))
                    elements.append(del_table)
                    elements.append(Spacer(1, 5))
                
                # Empty Received from Warehouses table
                if r.get('received_empty_15kg', []) or r.get('received_empty_21kg', []):
                    elements.append(Paragraph("Empty Received from Warehouses", ParagraphStyle('SubHeader', fontSize=9, textColor=colors.HexColor('#c2410c'))))
                    recv_data = [['Warehouse', '15kg Empty', '21kg Empty']]
                    warehouse_recv = {}
                    for d in r.get('received_empty_15kg', []):
                        wname = d.get('warehouse_name', 'Unknown')
                        if wname not in warehouse_recv:
                            warehouse_recv[wname] = {'qty15': 0, 'qty21': 0}
                        warehouse_recv[wname]['qty15'] = d.get('quantity', 0)
                    for d in r.get('received_empty_21kg', []):
                        wname = d.get('warehouse_name', 'Unknown')
                        if wname not in warehouse_recv:
                            warehouse_recv[wname] = {'qty15': 0, 'qty21': 0}
                        warehouse_recv[wname]['qty21'] = d.get('quantity', 0)
                    for wname, qty in warehouse_recv.items():
                        recv_data.append([wname, qty['qty15'], qty['qty21']])
                    
                    recv_table = Table(recv_data, colWidths=[150, 80, 80])
                    recv_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#fed7aa')),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, -1), 8),
                        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ]))
                    elements.append(recv_table)
                
                elements.append(Spacer(1, 8))
    
    doc.build(elements)
    buffer.seek(0)
    
    date_str = datetime.now().strftime('%d%m%y')
    if report_type == "daily":
        filename = f"Daily_Inventory_Report_{date_str}.pdf"
    else:
        filename = f"Plant_Hollongi_Report_{date_str}.pdf"
    
    return Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/export/excel")
async def export_excel(
    warehouse_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    report_type: str = "daily",
    user: dict = Depends(get_current_user)
):
    buffer = BytesIO()
    workbook = xlsxwriter.Workbook(buffer)
    worksheet = workbook.add_worksheet('Report')
    
    # Formats
    header_format = workbook.add_format({'bold': True, 'bg_color': '#15803d', 'font_color': 'white', 'align': 'center', 'border': 1, 'text_wrap': True})
    cell_format = workbook.add_format({'align': 'center', 'border': 1})
    title_format = workbook.add_format({'bold': True, 'font_size': 16, 'align': 'center', 'font_color': '#15803d'})
    opening_format = workbook.add_format({'align': 'center', 'border': 1, 'bg_color': '#dbeafe'})
    activity_format = workbook.add_format({'align': 'center', 'border': 1, 'bg_color': '#fef3c7'})
    closing_format = workbook.add_format({'align': 'center', 'border': 1, 'bg_color': '#dcfce7'})
    
    if report_type == "daily":
        query = {}
        # Filter by warehouse - non-admin users can only see their own warehouse
        if user['role'] != 'admin':
            query['warehouse_id'] = user.get('warehouse_id')
        elif warehouse_id:
            query['warehouse_id'] = warehouse_id
        
        if start_date:
            query['date'] = {'$gte': start_date}
        if end_date:
            if 'date' in query:
                query['date']['$lte'] = end_date
            else:
                query['date'] = {'$lte': end_date}
        
        reports = await db.daily_reports.find(query, {'_id': 0}).sort('date', -1).to_list(1000)
        
        # Get warehouse name for title
        warehouse_name = "All Warehouses"
        if user['role'] != 'admin':
            warehouse_name = user.get('warehouse_name', 'My Warehouse')
        elif warehouse_id:
            wh = await db.warehouses.find_one({'id': warehouse_id}, {'_id': 0})
            warehouse_name = wh['name'] if wh else warehouse_id
        
        worksheet.merge_range('A1:S1', f'K3 GAS SERVICE - Daily Inventory Report - {warehouse_name}', title_format)
        if start_date and end_date:
            worksheet.merge_range('A2:S2', f'Period: {start_date} to {end_date}', workbook.add_format({'align': 'center'}))
        
        # Comprehensive headers
        headers = [
            'Date', 'Warehouse',
            'Open 15kg Filled', 'Open 21kg Filled', 'Open 15kg Empty', 'Open 21kg Empty',
            'Sold 15kg', 'Sold 21kg',
            'Refill 15kg', 'Refill 21kg',
            'Refill to Plant 15kg', 'Refill to Plant 21kg',
            'Received from Plant-15kg', 'Received from Plant-21kg',
            'Close 15kg Filled', 'Close 21kg Filled', 'Close 15kg Empty', 'Close 21kg Empty',
            'Status'
        ]
        
        row_start = 3
        for col, header in enumerate(headers):
            worksheet.write(row_start, col, header, header_format)
            worksheet.set_column(col, col, 12 if col > 1 else 15)  # Set column width
        
        for row, r in enumerate(reports, start=row_start + 1):
            # Date and Warehouse
            worksheet.write(row, 0, r.get('date', ''), cell_format)
            worksheet.write(row, 1, r.get('warehouse_name', ''), cell_format)
            
            # Opening Stock (blue)
            worksheet.write(row, 2, r.get('opening_15kg_filled', 0), opening_format)
            worksheet.write(row, 3, r.get('opening_21kg_filled', 0), opening_format)
            worksheet.write(row, 4, r.get('opening_15kg_empty', 0), opening_format)
            worksheet.write(row, 5, r.get('opening_21kg_empty', 0), opening_format)
            
            # Day Activities (yellow)
            worksheet.write(row, 6, r.get('sold_15kg_filled', 0), activity_format)
            worksheet.write(row, 7, r.get('sold_21kg_filled', 0), activity_format)
            worksheet.write(row, 8, r.get('refilling_15kg', 0), activity_format)
            worksheet.write(row, 9, r.get('refilling_21kg', 0), activity_format)
            worksheet.write(row, 10, r.get('refilling_plant_15kg', 0), activity_format)
            worksheet.write(row, 11, r.get('refilling_plant_21kg', 0), activity_format)
            worksheet.write(row, 12, r.get('received_from_plant_15kg', 0), activity_format)
            worksheet.write(row, 13, r.get('received_from_plant_21kg', 0), activity_format)
            
            # Closing Stock (green)
            worksheet.write(row, 14, r.get('closing_15kg_filled', 0), closing_format)
            worksheet.write(row, 15, r.get('closing_21kg_filled', 0), closing_format)
            worksheet.write(row, 16, r.get('closing_15kg_empty', 0), closing_format)
            worksheet.write(row, 17, r.get('closing_21kg_empty', 0), closing_format)
            
            # Status
            status = "Discrepancy" if r.get('has_discrepancy') else "OK"
            worksheet.write(row, 18, status, cell_format)
    
    elif report_type == "plant":
        query = {}
        if start_date:
            query['date'] = {'$gte': start_date}
        if end_date:
            if 'date' in query:
                query['date']['$lte'] = end_date
            else:
                query['date'] = {'$lte': end_date}
        
        reports = await db.plant_reports.find(query, {'_id': 0}).sort('date', -1).to_list(1000)
        
        worksheet.merge_range('A1:R1', 'K3 GAS SERVICE - Plant Hollongi Report', title_format)
        if start_date and end_date:
            worksheet.merge_range('A2:R2', f'Period: {start_date} to {end_date}', workbook.add_format({'align': 'center'}))
        
        # Comprehensive headers for Plant with Day Reloading
        headers = [
            'Date',
            'Op.Tank(kg)', 'Op.15F', 'Op.21F', 'Op.15E', 'Op.21E',
            'Reload(kg)', 'Recv.15E', 'Recv.21E',
            'Refill.15', 'Refill.21',
            'Del.15F', 'Del.21F',
            'Cl.Tank(kg)', 'Cl.15F', 'Cl.21F', 'Cl.15E', 'Cl.21E'
        ]
        
        # Create a reloading format (cyan background)
        reloading_format = workbook.add_format({'bg_color': '#cffafe', 'align': 'center', 'border': 1})
        
        for col, header in enumerate(headers):
            worksheet.write(3, col, header, header_format)
            worksheet.set_column(col, col, 10)
        
        for row, r in enumerate(reports, start=4):
            # Calculate totals for deliveries and received
            del_15 = sum([d.get('quantity', 0) for d in r.get('delivery_15kg', [])])
            del_21 = sum([d.get('quantity', 0) for d in r.get('delivery_21kg', [])])
            recv_15 = sum([d.get('quantity', 0) for d in r.get('received_empty_15kg', [])])
            recv_21 = sum([d.get('quantity', 0) for d in r.get('received_empty_21kg', [])])
            
            worksheet.write(row, 0, r.get('date', ''), cell_format)
            # Opening
            worksheet.write(row, 1, r.get('opening_bullet_tank_kg', 0), opening_format)
            worksheet.write(row, 2, r.get('opening_15kg_filled', 0), opening_format)
            worksheet.write(row, 3, r.get('opening_21kg_filled', 0), opening_format)
            worksheet.write(row, 4, r.get('opening_15kg_empty', 0), opening_format)
            worksheet.write(row, 5, r.get('opening_21kg_empty', 0), opening_format)
            # Day Reloading
            worksheet.write(row, 6, r.get('day_reloading_kg', 0), reloading_format)
            # Activities
            worksheet.write(row, 7, recv_15, activity_format)
            worksheet.write(row, 8, recv_21, activity_format)
            worksheet.write(row, 9, r.get('day_refilled_15kg', 0), activity_format)
            worksheet.write(row, 10, r.get('day_refilled_21kg', 0), activity_format)
            worksheet.write(row, 11, del_15, activity_format)
            worksheet.write(row, 12, del_21, activity_format)
            # Closing
            worksheet.write(row, 13, r.get('closing_bullet_tank_kg', 0), closing_format)
            worksheet.write(row, 14, r.get('closing_15kg_filled', 0), closing_format)
            worksheet.write(row, 15, r.get('closing_21kg_filled', 0), closing_format)
            worksheet.write(row, 16, r.get('closing_15kg_empty', 0), closing_format)
            worksheet.write(row, 17, r.get('closing_21kg_empty', 0), closing_format)
        
        # Create second sheet for warehouse breakdown
        breakdown_sheet = workbook.add_worksheet('Warehouse Breakdown')
        breakdown_sheet.merge_range('A1:E1', 'Warehouse-wise Breakdown', title_format)
        
        breakdown_header_format = workbook.add_format({'bold': True, 'bg_color': '#15803d', 'font_color': 'white', 'align': 'center', 'border': 1})
        delivery_header_format = workbook.add_format({'bold': True, 'bg_color': '#c7d2fe', 'align': 'center', 'border': 1})
        received_header_format = workbook.add_format({'bold': True, 'bg_color': '#fed7aa', 'align': 'center', 'border': 1})
        
        breakdown_sheet.set_column(0, 0, 12)  # Date
        breakdown_sheet.set_column(1, 1, 10)  # Type
        breakdown_sheet.set_column(2, 2, 15)  # Warehouse
        breakdown_sheet.set_column(3, 3, 12)  # 15kg
        breakdown_sheet.set_column(4, 4, 12)  # 21kg
        
        breakdown_headers = ['Date', 'Type', 'Warehouse', '15kg Qty', '21kg Qty']
        for col, header in enumerate(breakdown_headers):
            breakdown_sheet.write(2, col, header, breakdown_header_format)
        
        breakdown_row = 3
        for r in reports:
            report_date = r.get('date', '')
            
            # Delivery to Warehouses
            warehouse_del = {}
            for d in r.get('delivery_15kg', []):
                wname = d.get('warehouse_name', 'Unknown')
                if wname not in warehouse_del:
                    warehouse_del[wname] = {'qty15': 0, 'qty21': 0}
                warehouse_del[wname]['qty15'] = d.get('quantity', 0)
            for d in r.get('delivery_21kg', []):
                wname = d.get('warehouse_name', 'Unknown')
                if wname not in warehouse_del:
                    warehouse_del[wname] = {'qty15': 0, 'qty21': 0}
                warehouse_del[wname]['qty21'] = d.get('quantity', 0)
            
            for wname, qty in warehouse_del.items():
                breakdown_sheet.write(breakdown_row, 0, report_date, cell_format)
                breakdown_sheet.write(breakdown_row, 1, 'Delivery', delivery_header_format)
                breakdown_sheet.write(breakdown_row, 2, wname, cell_format)
                breakdown_sheet.write(breakdown_row, 3, qty['qty15'], cell_format)
                breakdown_sheet.write(breakdown_row, 4, qty['qty21'], cell_format)
                breakdown_row += 1
            
            # Empty Received from Warehouses
            warehouse_recv = {}
            for d in r.get('received_empty_15kg', []):
                wname = d.get('warehouse_name', 'Unknown')
                if wname not in warehouse_recv:
                    warehouse_recv[wname] = {'qty15': 0, 'qty21': 0}
                warehouse_recv[wname]['qty15'] = d.get('quantity', 0)
            for d in r.get('received_empty_21kg', []):
                wname = d.get('warehouse_name', 'Unknown')
                if wname not in warehouse_recv:
                    warehouse_recv[wname] = {'qty15': 0, 'qty21': 0}
                warehouse_recv[wname]['qty21'] = d.get('quantity', 0)
            
            for wname, qty in warehouse_recv.items():
                breakdown_sheet.write(breakdown_row, 0, report_date, cell_format)
                breakdown_sheet.write(breakdown_row, 1, 'Empty Recv', received_header_format)
                breakdown_sheet.write(breakdown_row, 2, wname, cell_format)
                breakdown_sheet.write(breakdown_row, 3, qty['qty15'], cell_format)
                breakdown_sheet.write(breakdown_row, 4, qty['qty21'], cell_format)
                breakdown_row += 1
    
    workbook.close()
    buffer.seek(0)
    
    # Generate filename based on report type
    date_str = datetime.now().strftime('%d%m%y')
    if report_type == "daily":
        filename = f"Daily_Inventory_Report_{date_str}.xlsx"
    else:
        filename = f"Plant_Hollongi_Report_{date_str}.xlsx"
    
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# ============ ROOT ROUTES ============

@router.get("/")
async def root():
    return {"message": "K3 GAS SERVICE API", "version": "1.0.0"}

