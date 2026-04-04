from fastapi import APIRouter, HTTPException, Depends, Response
from database import db
from deps import get_current_user
from helpers import format_inr
from datetime import datetime, timezone
from typing import Optional
from io import BytesIO
import calendar
import base64
import tempfile
import os

router = APIRouter()

# ============ FONT REGISTRATION (Arial via LiberationSans) ============
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FONT_DIR = '/usr/share/fonts/truetype/liberation'
try:
    pdfmetrics.registerFont(TTFont('Arial', f'{FONT_DIR}/LiberationSans-Regular.ttf'))
    pdfmetrics.registerFont(TTFont('Arial-Bold', f'{FONT_DIR}/LiberationSans-Bold.ttf'))
    pdfmetrics.registerFont(TTFont('Arial-Italic', f'{FONT_DIR}/LiberationSans-Italic.ttf'))
    pdfmetrics.registerFont(TTFont('Arial-BoldItalic', f'{FONT_DIR}/LiberationSans-BoldItalic.ttf'))
    from reportlab.lib.fonts import addMapping
    addMapping('Arial', 0, 0, 'Arial')
    addMapping('Arial', 1, 0, 'Arial-Bold')
    addMapping('Arial', 0, 1, 'Arial-Italic')
    addMapping('Arial', 1, 1, 'Arial-BoldItalic')
except Exception as e:
    print(f"Font registration warning: {e}")


# ============ SHARED HELPERS ============

async def get_company_info():
    settings = await db.hrms_settings.find_one({'key': 'company_info'}, {'_id': 0})
    return {
        'name': settings.get('company_name', 'K3 GAS SERVICE') if settings else 'K3 GAS SERVICE',
        'tagline': settings.get('tagline', '') if settings else '',
        'address': settings.get('address', '') if settings else '',
        'email': settings.get('email', '') if settings else '',
        'helpline': settings.get('helpline', '') if settings else '',
        'logo_url': settings.get('logo_url', '') if settings else '',
    }


def decode_logo_to_tempfile(logo_data_uri):
    """Decode base64 logo data URI to a temp file for ReportLab Image"""
    if not logo_data_uri or not logo_data_uri.startswith('data:'):
        return None
    try:
        header, data = logo_data_uri.split(',', 1)
        img_bytes = base64.b64decode(data)
        ext = '.png'
        if 'jpeg' in header or 'jpg' in header:
            ext = '.jpg'
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
        tmp.write(img_bytes)
        tmp.close()
        return tmp.name
    except Exception:
        return None


def build_report_header(elements, company, title, mm):
    """
    Unified A4 report header:
    Logo -> Center
    Company Name & Tagline -> Center
    Address & Contact -> Center
    Report Title -> Center + Bold
    """
    from reportlab.platypus import Paragraph, Spacer, Image
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib import colors

    # Logo
    logo_path = decode_logo_to_tempfile(company.get('logo_url', ''))
    if logo_path:
        try:
            img = Image(logo_path, width=50, height=50)
            img.hAlign = 'CENTER'
            elements.append(img)
            elements.append(Spacer(1, 2 * mm))
        except Exception:
            pass

    # Company Name
    elements.append(Paragraph(
        company['name'],
        ParagraphStyle('CompanyName', fontName='Arial-Bold', fontSize=16, alignment=TA_CENTER, spaceAfter=1 * mm)
    ))

    # Tagline
    if company.get('tagline'):
        elements.append(Paragraph(
            company['tagline'],
            ParagraphStyle('Tagline', fontName='Arial-Italic', fontSize=9, alignment=TA_CENTER, textColor=colors.Color(0.4, 0.4, 0.4), spaceAfter=1 * mm)
        ))

    # Address & Contact
    contact_parts = []
    if company.get('address'):
        contact_parts.append(company['address'])
    contacts = []
    if company.get('email'):
        contacts.append(company['email'])
    if company.get('helpline'):
        contacts.append(company['helpline'])
    if contacts:
        contact_parts.append(' | '.join(contacts))

    for part in contact_parts:
        elements.append(Paragraph(
            part,
            ParagraphStyle('Contact', fontName='Arial', fontSize=8, alignment=TA_CENTER, textColor=colors.Color(0.5, 0.5, 0.5))
        ))

    elements.append(Spacer(1, 3 * mm))

    # Horizontal line
    from reportlab.platypus import HRFlowable
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.Color(0.7, 0.7, 0.7)))
    elements.append(Spacer(1, 3 * mm))

    # Report Title
    elements.append(Paragraph(
        title,
        ParagraphStyle('ReportTitle', fontName='Arial-Bold', fontSize=13, alignment=TA_CENTER, spaceAfter=2 * mm)
    ))
    elements.append(Spacer(1, 2 * mm))

    return logo_path  # Return for cleanup


def build_report_footer(elements, company, mm):
    """Footer tagline centered"""
    from reportlab.platypus import Paragraph, Spacer, HRFlowable
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib import colors

    elements.append(Spacer(1, 6 * mm))
    elements.append(HRFlowable(width="100%", thickness=0.3, color=colors.Color(0.8, 0.8, 0.8)))
    elements.append(Spacer(1, 2 * mm))

    footer_text = company.get('tagline', '') or company['name']
    elements.append(Paragraph(
        footer_text,
        ParagraphStyle('Footer', fontName='Arial-Italic', fontSize=7, alignment=TA_CENTER, textColor=colors.Color(0.6, 0.6, 0.6))
    ))
    elements.append(Paragraph(
        f"Generated on {datetime.now().strftime('%d-%m-%Y %H:%M')}",
        ParagraphStyle('FooterDate', fontName='Arial', fontSize=6, alignment=TA_CENTER, textColor=colors.Color(0.7, 0.7, 0.7))
    ))


def make_table_style(header_color=(0.15, 0.3, 0.6)):
    from reportlab.lib import colors
    from reportlab.platypus import TableStyle
    return TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Arial'),
        ('FONTSIZE', (0, 0), (-1, -1), 7.5),
        ('FONTNAME', (0, 0), (-1, 0), 'Arial-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 0), (-1, 0), colors.Color(*header_color)),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.Color(0.82, 0.82, 0.82)),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.Color(0.97, 0.97, 0.98)]),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ])


# ============ EMPLOYEE DIRECTORY (PDF) ============

@router.get("/hrms/reports/employees/pdf")
async def export_employees_pdf(department_id: Optional[str] = None, status: Optional[str] = None, user: dict = Depends(get_current_user)):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, Paragraph, Spacer
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib.enums import TA_CENTER

    company = await get_company_info()
    query = {}
    if department_id and department_id != 'all':
        query['department_id'] = department_id
    if status == 'active':
        query['is_active'] = True
    elif status == 'inactive':
        query['is_active'] = False

    employees = []
    async for emp in db.hrms_employees.find(query, {'_id': 0}).sort('name', 1):
        dept = await db.hrms_departments.find_one({'id': emp.get('department_id')}, {'_id': 0, 'name': 1})
        emp['department_name'] = dept['name'] if dept else 'N/A'
        employees.append(emp)

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=12 * mm, rightMargin=12 * mm, topMargin=15 * mm, bottomMargin=15 * mm)
    elements = []

    logo_path = build_report_header(elements, company, "EMPLOYEE DIRECTORY", mm)
    elements.append(Paragraph(
        f"Total Employees: {len(employees)}",
        ParagraphStyle('Info', fontName='Arial', fontSize=8, alignment=TA_CENTER, textColor=colors.grey)
    ))
    elements.append(Spacer(1, 3 * mm))

    data = [['S.No', 'Emp ID', 'Name', 'Department', 'Designation', 'DOJ', 'Phone', 'Status']]
    for i, emp in enumerate(employees):
        data.append([
            str(i + 1), emp.get('employee_id', ''), emp['name'], emp.get('department_name', ''),
            emp.get('designation', ''), emp.get('date_of_joining', ''), emp.get('phone', ''),
            'Active' if emp.get('is_active') else 'Inactive',
        ])

    table = Table(data, colWidths=[25, 45, 82, 65, 72, 55, 60, 40])
    style = make_table_style()
    style.add('ALIGN', (-1, 0), (-1, -1), 'CENTER')
    table.setStyle(style)
    elements.append(table)

    build_report_footer(elements, company, mm)
    doc.build(elements)
    if logo_path:
        os.unlink(logo_path)
    buf.seek(0)
    return Response(content=buf.read(), media_type="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="Employee_Directory.pdf"'})


# ============ EMPLOYEE DIRECTORY (EXCEL) ============

@router.get("/hrms/reports/employees/excel")
async def export_employees_excel(department_id: Optional[str] = None, status: Optional[str] = None, user: dict = Depends(get_current_user)):
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

    company = await get_company_info()
    query = {}
    if department_id and department_id != 'all':
        query['department_id'] = department_id
    if status == 'active':
        query['is_active'] = True
    elif status == 'inactive':
        query['is_active'] = False

    employees = []
    async for emp in db.hrms_employees.find(query, {'_id': 0}).sort('name', 1):
        dept = await db.hrms_departments.find_one({'id': emp.get('department_id')}, {'_id': 0, 'name': 1})
        emp['department_name'] = dept['name'] if dept else 'N/A'
        employees.append(emp)

    wb = Workbook()
    ws = wb.active
    ws.title = "Employees"
    hf = Font(name='Arial', size=14, bold=True)
    sf = Font(name='Arial', size=9, color='666666')
    cf = Font(name='Arial', size=10, bold=True, color='FFFFFF')
    nf = Font(name='Arial', size=9)
    hfill = PatternFill(start_color='264785', end_color='264785', fill_type='solid')
    border = Border(left=Side(style='thin', color='CCCCCC'), right=Side(style='thin', color='CCCCCC'),
                    top=Side(style='thin', color='CCCCCC'), bottom=Side(style='thin', color='CCCCCC'))

    ws.merge_cells('A1:J1')
    ws['A1'] = company['name']
    ws['A1'].font = hf
    ws['A1'].alignment = Alignment(horizontal='center')
    ws.merge_cells('A2:J2')
    ws['A2'] = f"{company.get('tagline', '')} | Employee Directory | {datetime.now().strftime('%d-%m-%Y')}"
    ws['A2'].font = sf
    ws['A2'].alignment = Alignment(horizontal='center')

    headers = ['S.No', 'Emp ID', 'Name', 'Department', 'Designation', 'DOJ', 'Phone', 'Email', 'PAN', 'Status']
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=4, column=col, value=h)
        cell.font = cf
        cell.fill = hfill
        cell.alignment = Alignment(horizontal='center')
        cell.border = border

    for i, emp in enumerate(employees):
        row = i + 5
        values = [i + 1, emp.get('employee_id', ''), emp['name'], emp.get('department_name', ''),
                  emp.get('designation', ''), emp.get('date_of_joining', ''), emp.get('phone', ''),
                  emp.get('email', ''), emp.get('pan_number', ''), 'Active' if emp.get('is_active') else 'Inactive']
        for col, val in enumerate(values, 1):
            cell = ws.cell(row=row, column=col, value=val)
            cell.font = nf
            cell.border = border

    for c, w in [('A', 6), ('B', 10), ('C', 20), ('D', 16), ('E', 18), ('F', 12), ('G', 14), ('H', 24), ('I', 12), ('J', 10)]:
        ws.column_dimensions[c].width = w

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return Response(content=buf.read(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": 'attachment; filename="Employee_Directory.xlsx"'})


# ============ ATTENDANCE REPORT (PDF) ============

@router.get("/hrms/reports/attendance/pdf")
async def export_attendance_pdf(month: str, department_id: Optional[str] = None, user: dict = Depends(get_current_user)):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, Paragraph, Spacer
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib.enums import TA_CENTER

    company = await get_company_info()
    parts = month.split('-')
    year_num, month_num = int(parts[0]), int(parts[1])
    month_name = calendar.month_name[month_num]

    emp_query = {'is_active': True}
    if department_id and department_id != 'all':
        emp_query['department_id'] = department_id

    summaries = []
    async for emp in db.hrms_employees.find(emp_query, {'_id': 0}).sort('name', 1):
        dept = await db.hrms_departments.find_one({'id': emp.get('department_id')}, {'_id': 0, 'name': 1})
        present = await db.hrms_attendance.count_documents({'employee_id': emp['id'], 'date': {'$regex': f'^{month}'}, 'status': 'present'})
        absent = await db.hrms_attendance.count_documents({'employee_id': emp['id'], 'date': {'$regex': f'^{month}'}, 'status': 'absent'})
        half_day = await db.hrms_attendance.count_documents({'employee_id': emp['id'], 'date': {'$regex': f'^{month}'}, 'status': 'half_day'})
        late = await db.hrms_attendance.count_documents({'employee_id': emp['id'], 'date': {'$regex': f'^{month}'}, 'status': 'late'})
        leave = await db.hrms_attendance.count_documents({'employee_id': emp['id'], 'date': {'$regex': f'^{month}'}, 'status': 'leave'})
        summaries.append({
            'code': emp.get('employee_id', ''), 'name': emp['name'],
            'dept': dept['name'] if dept else 'N/A', 'present': present,
            'absent': absent, 'half_day': half_day, 'late': late,
            'leave': leave, 'effective': present + late + (half_day * 0.5),
        })

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=12 * mm, rightMargin=12 * mm, topMargin=15 * mm, bottomMargin=15 * mm)
    elements = []
    logo_path = build_report_header(elements, company, f"ATTENDANCE REPORT - {month_name} {year_num}", mm)

    data = [['S.No', 'Emp ID', 'Name', 'Department', 'Present', 'Absent', 'Half Day', 'Late', 'Leave', 'Effective']]
    for i, s in enumerate(summaries):
        data.append([str(i + 1), s['code'], s['name'], s['dept'], str(s['present']), str(s['absent']),
                      str(s['half_day']), str(s['late']), str(s['leave']), str(s['effective'])])
    data.append(['', '', f'Total ({len(summaries)})', '', str(sum(s['present'] for s in summaries)),
                 str(sum(s['absent'] for s in summaries)), str(sum(s['half_day'] for s in summaries)),
                 str(sum(s['late'] for s in summaries)), str(sum(s['leave'] for s in summaries)),
                 str(sum(s['effective'] for s in summaries))])

    table = Table(data, colWidths=[25, 45, 90, 70, 45, 45, 45, 40, 40, 55])
    style = make_table_style()
    style.add('ALIGN', (4, 0), (-1, -1), 'CENTER')
    style.add('FONTNAME', (0, -1), (-1, -1), 'Arial-Bold')
    style.add('BACKGROUND', (0, -1), (-1, -1), colors.Color(0.9, 0.92, 0.95))
    table.setStyle(style)
    elements.append(table)

    build_report_footer(elements, company, mm)
    doc.build(elements)
    if logo_path:
        os.unlink(logo_path)
    buf.seek(0)
    return Response(content=buf.read(), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="Attendance_{month_name}_{year_num}.pdf"'})


# ============ ATTENDANCE REPORT (EXCEL) ============

@router.get("/hrms/reports/attendance/excel")
async def export_attendance_excel(month: str, department_id: Optional[str] = None, user: dict = Depends(get_current_user)):
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

    company = await get_company_info()
    parts = month.split('-')
    year_num, month_num = int(parts[0]), int(parts[1])
    month_name = calendar.month_name[month_num]

    emp_query = {'is_active': True}
    if department_id and department_id != 'all':
        emp_query['department_id'] = department_id

    summaries = []
    async for emp in db.hrms_employees.find(emp_query, {'_id': 0}).sort('name', 1):
        dept = await db.hrms_departments.find_one({'id': emp.get('department_id')}, {'_id': 0, 'name': 1})
        present = await db.hrms_attendance.count_documents({'employee_id': emp['id'], 'date': {'$regex': f'^{month}'}, 'status': 'present'})
        absent = await db.hrms_attendance.count_documents({'employee_id': emp['id'], 'date': {'$regex': f'^{month}'}, 'status': 'absent'})
        half_day = await db.hrms_attendance.count_documents({'employee_id': emp['id'], 'date': {'$regex': f'^{month}'}, 'status': 'half_day'})
        late = await db.hrms_attendance.count_documents({'employee_id': emp['id'], 'date': {'$regex': f'^{month}'}, 'status': 'late'})
        leave = await db.hrms_attendance.count_documents({'employee_id': emp['id'], 'date': {'$regex': f'^{month}'}, 'status': 'leave'})
        summaries.append({
            'code': emp.get('employee_id', ''), 'name': emp['name'],
            'dept': dept['name'] if dept else 'N/A',
            'present': present, 'absent': absent, 'half_day': half_day,
            'late': late, 'leave': leave, 'effective': present + late + (half_day * 0.5),
        })

    wb = Workbook()
    ws = wb.active
    ws.title = "Attendance"
    hf = Font(name='Arial', size=14, bold=True)
    sf = Font(name='Arial', size=9, color='666666')
    cf = Font(name='Arial', size=10, bold=True, color='FFFFFF')
    nf = Font(name='Arial', size=9)
    bf = Font(name='Arial', size=10, bold=True)
    hfill = PatternFill(start_color='264785', end_color='264785', fill_type='solid')
    tfill = PatternFill(start_color='E5EAF0', end_color='E5EAF0', fill_type='solid')
    border = Border(left=Side(style='thin', color='CCCCCC'), right=Side(style='thin', color='CCCCCC'),
                    top=Side(style='thin', color='CCCCCC'), bottom=Side(style='thin', color='CCCCCC'))

    ws.merge_cells('A1:J1')
    ws['A1'] = company['name']
    ws['A1'].font = hf
    ws['A1'].alignment = Alignment(horizontal='center')
    ws.merge_cells('A2:J2')
    ws['A2'] = f"Attendance Report - {month_name} {year_num}"
    ws['A2'].font = sf
    ws['A2'].alignment = Alignment(horizontal='center')

    headers = ['S.No', 'Emp ID', 'Name', 'Department', 'Present', 'Absent', 'Half Day', 'Late', 'Leave', 'Effective']
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=4, column=col, value=h)
        cell.font = cf
        cell.fill = hfill
        cell.alignment = Alignment(horizontal='center')
        cell.border = border

    for i, s in enumerate(summaries):
        row = i + 5
        values = [i + 1, s['code'], s['name'], s['dept'], s['present'], s['absent'], s['half_day'], s['late'], s['leave'], s['effective']]
        for col, val in enumerate(values, 1):
            cell = ws.cell(row=row, column=col, value=val)
            cell.font = nf
            cell.border = border
            if col >= 5:
                cell.alignment = Alignment(horizontal='center')

    total_row = len(summaries) + 5
    ws.cell(row=total_row, column=3, value='TOTAL').font = bf
    for col, key in [(5, 'present'), (6, 'absent'), (7, 'half_day'), (8, 'late'), (9, 'leave'), (10, 'effective')]:
        cell = ws.cell(row=total_row, column=col, value=sum(s[key] for s in summaries))
        cell.font = bf
        cell.fill = tfill
        cell.border = border
        cell.alignment = Alignment(horizontal='center')

    for c, w in [('A', 6), ('B', 10), ('C', 22), ('D', 16), ('E', 10), ('F', 10), ('G', 10), ('H', 8), ('I', 8), ('J', 10)]:
        ws.column_dimensions[c].width = w

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return Response(content=buf.read(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="Attendance_{month_name}_{year_num}.xlsx"'})


# ============ PAYROLL REPORT (PDF) ============

@router.get("/hrms/reports/payroll/{payroll_id}/pdf")
async def export_payroll_report_pdf(payroll_id: str, user: dict = Depends(get_current_user)):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, Paragraph, Spacer
    from reportlab.lib.units import mm
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.styles import ParagraphStyle

    payroll = await db.hrms_payroll.find_one({'id': payroll_id}, {'_id': 0})
    if not payroll:
        raise HTTPException(status_code=404, detail="Payroll not found")
    company = await get_company_info()
    month_name = calendar.month_name[payroll['month']]
    year = payroll['year']

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=10 * mm, rightMargin=10 * mm, topMargin=12 * mm, bottomMargin=12 * mm)
    elements = []
    logo_path = build_report_header(elements, company, f"PAYROLL REGISTER - {month_name} {year}", mm)

    data = [['S.No', 'Emp ID', 'Name', 'Dept', 'Days', 'Basic', 'HRA', 'DA', 'Other', 'Gross', 'PF', 'ESI', 'PT', 'TDS', 'Deductions', 'Net Pay']]
    for i, emp in enumerate(payroll.get('employees', [])):
        data.append([
            str(i + 1), emp.get('employee_code', ''), emp['name'][:18], emp.get('department', '')[:12],
            f"{emp['days_present']}/{emp['working_days']}",
            format_inr(emp['earned_basic']), format_inr(emp['earned_hra']), format_inr(emp['earned_da']),
            format_inr(emp['earned_other_allowances']), format_inr(emp['gross_salary']),
            format_inr(emp['pf_employee']), format_inr(emp['esi_employee']),
            format_inr(emp['professional_tax']), format_inr(emp['tds']),
            format_inr(emp['total_deductions']), format_inr(emp['net_pay']),
        ])
    data.append(['', '', f'TOTAL ({len(payroll.get("employees", []))})', '', '', '', '', '', '',
                 format_inr(payroll['total_gross']), '', '', '', '',
                 format_inr(payroll['total_deductions']), format_inr(payroll['total_net_pay'])])

    table = Table(data, colWidths=[22, 38, 68, 50, 30, 38, 35, 35, 35, 42, 35, 32, 28, 32, 42, 45])
    style = make_table_style(header_color=(0.12, 0.35, 0.55))
    style.add('ALIGN', (4, 0), (-1, -1), 'RIGHT')
    style.add('FONTNAME', (0, -1), (-1, -1), 'Arial-Bold')
    style.add('BACKGROUND', (0, -1), (-1, -1), colors.Color(0.88, 0.93, 0.88))
    table.setStyle(style)
    elements.append(table)

    build_report_footer(elements, company, mm)
    doc.build(elements)
    if logo_path:
        os.unlink(logo_path)
    buf.seek(0)
    return Response(content=buf.read(), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="Payroll_{month_name}_{year}.pdf"'})


# ============ PAYROLL REPORT (EXCEL) ============

@router.get("/hrms/reports/payroll/{payroll_id}/excel")
async def export_payroll_report_excel(payroll_id: str, user: dict = Depends(get_current_user)):
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

    payroll = await db.hrms_payroll.find_one({'id': payroll_id}, {'_id': 0})
    if not payroll:
        raise HTTPException(status_code=404, detail="Payroll not found")
    company = await get_company_info()
    month_name = calendar.month_name[payroll['month']]
    year = payroll['year']

    wb = Workbook()
    ws = wb.active
    ws.title = "Payroll"
    hf = Font(name='Arial', size=14, bold=True)
    sf = Font(name='Arial', size=9, color='666666')
    cf = Font(name='Arial', size=9, bold=True, color='FFFFFF')
    nf = Font(name='Arial', size=8)
    bf = Font(name='Arial', size=9, bold=True)
    hfill = PatternFill(start_color='1E5A8C', end_color='1E5A8C', fill_type='solid')
    tfill = PatternFill(start_color='E0EDDF', end_color='E0EDDF', fill_type='solid')
    border = Border(left=Side(style='thin', color='CCCCCC'), right=Side(style='thin', color='CCCCCC'),
                    top=Side(style='thin', color='CCCCCC'), bottom=Side(style='thin', color='CCCCCC'))

    cols = 16
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=cols)
    ws['A1'] = company['name']
    ws['A1'].font = hf
    ws['A1'].alignment = Alignment(horizontal='center')
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=cols)
    ws['A2'] = f"Payroll Register - {month_name} {year} | Status: {payroll['status'].upper()}"
    ws['A2'].font = sf
    ws['A2'].alignment = Alignment(horizontal='center')

    headers = ['S.No', 'Emp ID', 'Name', 'Dept', 'Days', 'Basic', 'HRA', 'DA', 'Other', 'Gross', 'PF', 'ESI', 'PT', 'TDS', 'Deductions', 'Net Pay']
    for col_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=4, column=col_idx, value=h)
        cell.font = cf
        cell.fill = hfill
        cell.alignment = Alignment(horizontal='center')
        cell.border = border

    for i, emp in enumerate(payroll.get('employees', [])):
        row = i + 5
        values = [i + 1, emp.get('employee_code', ''), emp['name'], emp.get('department', ''),
                  f"{emp['days_present']}/{emp['working_days']}",
                  emp['earned_basic'], emp['earned_hra'], emp['earned_da'], emp['earned_other_allowances'],
                  emp['gross_salary'], emp['pf_employee'], emp['esi_employee'], emp['professional_tax'],
                  emp['tds'], emp['total_deductions'], emp['net_pay']]
        for col_idx, val in enumerate(values, 1):
            cell = ws.cell(row=row, column=col_idx, value=val)
            cell.font = nf
            cell.border = border
            if col_idx >= 6:
                cell.number_format = '#,##0.00'

    total_row = len(payroll.get('employees', [])) + 5
    ws.cell(row=total_row, column=3, value='TOTAL').font = bf
    ws.cell(row=total_row, column=10, value=payroll['total_gross']).font = bf
    ws.cell(row=total_row, column=15, value=payroll['total_deductions']).font = bf
    ws.cell(row=total_row, column=16, value=payroll['total_net_pay']).font = bf
    for c in range(1, cols + 1):
        cell = ws.cell(row=total_row, column=c)
        cell.fill = tfill
        cell.border = border
        if c >= 6:
            cell.number_format = '#,##0.00'

    widths = [5, 8, 20, 14, 6, 8, 8, 7, 7, 10, 7, 7, 6, 7, 10, 10]
    for i, w in enumerate(widths):
        ws.column_dimensions[chr(65 + i)].width = w

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return Response(content=buf.read(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="Payroll_{month_name}_{year}.xlsx"'})


# ============ SALARY CERTIFICATE (PDF) ============

@router.get("/hrms/certificates/salary/{employee_id}/pdf")
async def generate_salary_certificate(employee_id: str, user: dict = Depends(get_current_user)):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY

    emp = await db.hrms_employees.find_one({'id': employee_id}, {'_id': 0})
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    dept = await db.hrms_departments.find_one({'id': emp.get('department_id')}, {'_id': 0, 'name': 1})
    company = await get_company_info()

    gross = emp.get('basic_salary', 0) + emp.get('hra', 0) + emp.get('da', 0) + emp.get('other_allowances', 0)
    annual = gross * 12
    today = datetime.now().strftime('%d-%m-%Y')

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=20 * mm, bottomMargin=20 * mm)
    elements = []

    logo_path = build_report_header(elements, company, "SALARY CERTIFICATE", mm)
    elements.append(Spacer(1, 4 * mm))

    # Subject - Center + Bold
    elements.append(Paragraph(
        f"<b>TO WHOM IT MAY CONCERN</b>",
        ParagraphStyle('Subject', fontName='Arial-Bold', fontSize=12, alignment=TA_CENTER, spaceAfter=6 * mm)
    ))

    # Body - Justified
    body_style = ParagraphStyle('Body', fontName='Arial', fontSize=10, alignment=TA_JUSTIFY, leading=16, spaceAfter=4 * mm)
    pronoun = 'her' if emp.get('gender') == 'female' else 'his'
    pronoun_cap = 'Her' if emp.get('gender') == 'female' else 'His'
    title = 'Ms.' if emp.get('gender') == 'female' else 'Mr.'

    elements.append(Paragraph(
        f"This is to certify that <b>{title} {emp['name']}</b> (Employee ID: <b>{emp.get('employee_id', '')}</b>) "
        f"is currently employed with <b>{company['name']}</b> as <b>{emp.get('designation', '')}</b> in the "
        f"<b>{dept['name'] if dept else 'N/A'}</b> department since <b>{emp.get('date_of_joining', 'N/A')}</b>.",
        body_style
    ))

    elements.append(Paragraph(
        f"{pronoun_cap} current salary details are as follows:",
        body_style
    ))

    # Salary Table
    sal_data = [
        ['Component', 'Monthly (Rs)', 'Annual (Rs)'],
        ['Basic Salary', format_inr(emp.get('basic_salary', 0)), format_inr(emp.get('basic_salary', 0) * 12)],
        ['HRA', format_inr(emp.get('hra', 0)), format_inr(emp.get('hra', 0) * 12)],
        ['DA', format_inr(emp.get('da', 0)), format_inr(emp.get('da', 0) * 12)],
        ['Other Allowances', format_inr(emp.get('other_allowances', 0)), format_inr(emp.get('other_allowances', 0) * 12)],
        ['Gross Salary', format_inr(gross), format_inr(annual)],
    ]
    sal_table = Table(sal_data, colWidths=[140, 100, 100])
    sal_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Arial'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTNAME', (0, 0), (-1, 0), 'Arial-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Arial-Bold'),
        ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.15, 0.3, 0.6)),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BACKGROUND', (0, -1), (-1, -1), colors.Color(0.92, 0.95, 0.92)),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.Color(0.8, 0.8, 0.8)),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(sal_table)
    elements.append(Spacer(1, 6 * mm))

    elements.append(Paragraph(
        f"This certificate is issued at the request of {title} {emp['name']} for {pronoun} personal use. "
        f"The information provided above is accurate to the best of our knowledge.",
        body_style
    ))

    elements.append(Spacer(1, 15 * mm))

    # Signature Block - Left aligned
    sig_style = ParagraphStyle('Sig', fontName='Arial', fontSize=10, alignment=TA_LEFT, spaceAfter=1 * mm)
    elements.append(Paragraph(f"Date: {today}", sig_style))
    elements.append(Spacer(1, 12 * mm))
    elements.append(Paragraph("_________________________", sig_style))
    elements.append(Paragraph("<b>Authorized Signatory</b>", sig_style))
    elements.append(Paragraph(company['name'], ParagraphStyle('SigCo', fontName='Arial', fontSize=9, alignment=TA_LEFT, textColor=colors.grey)))

    build_report_footer(elements, company, mm)
    doc.build(elements)
    if logo_path:
        os.unlink(logo_path)
    buf.seek(0)
    name = emp['name'].replace(' ', '_')
    return Response(content=buf.read(), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="Salary_Certificate_{name}.pdf"'})


# ============ EXPERIENCE LETTER (PDF) ============

@router.get("/hrms/certificates/experience/{employee_id}/pdf")
async def generate_experience_letter(employee_id: str, user: dict = Depends(get_current_user)):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY

    emp = await db.hrms_employees.find_one({'id': employee_id}, {'_id': 0})
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    dept = await db.hrms_departments.find_one({'id': emp.get('department_id')}, {'_id': 0, 'name': 1})
    company = await get_company_info()
    today = datetime.now().strftime('%d-%m-%Y')

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=20 * mm, bottomMargin=20 * mm)
    elements = []

    logo_path = build_report_header(elements, company, "EXPERIENCE CERTIFICATE", mm)
    elements.append(Spacer(1, 4 * mm))

    # Subject
    elements.append(Paragraph(
        "<b>TO WHOM IT MAY CONCERN</b>",
        ParagraphStyle('Subject', fontName='Arial-Bold', fontSize=12, alignment=TA_CENTER, spaceAfter=6 * mm)
    ))

    # Body - Justified
    body_style = ParagraphStyle('Body', fontName='Arial', fontSize=10, alignment=TA_JUSTIFY, leading=16, spaceAfter=4 * mm)
    pronoun = 'her' if emp.get('gender') == 'female' else 'his'
    pronoun_cap = 'She' if emp.get('gender') == 'female' else 'He'
    title = 'Ms.' if emp.get('gender') == 'female' else 'Mr.'

    elements.append(Paragraph(
        f"This is to certify that <b>{title} {emp['name']}</b> (Employee ID: <b>{emp.get('employee_id', '')}</b>) "
        f"has been employed with <b>{company['name']}</b> since <b>{emp.get('date_of_joining', 'N/A')}</b> as "
        f"<b>{emp.get('designation', '')}</b> in the <b>{dept['name'] if dept else 'N/A'}</b> department.",
        body_style
    ))

    elements.append(Paragraph(
        f"During {pronoun} tenure with our organization, {pronoun_cap.lower()} has demonstrated excellent professional "
        f"conduct, dedication, and a strong work ethic. {pronoun_cap} contributions to the team and the organization "
        f"have been highly valued.",
        body_style
    ))

    elements.append(Paragraph(
        f"We wish {title} {emp['name']} all the best in {pronoun} future endeavors.",
        body_style
    ))

    elements.append(Paragraph(
        f"This certificate is issued at the request of {title} {emp['name']} for {pronoun} records and future reference.",
        body_style
    ))

    elements.append(Spacer(1, 15 * mm))

    # Signature Block - Left
    sig_style = ParagraphStyle('Sig', fontName='Arial', fontSize=10, alignment=TA_LEFT, spaceAfter=1 * mm)
    elements.append(Paragraph(f"Date: {today}", sig_style))
    elements.append(Paragraph(f"Place: {company.get('address', '').split(',')[0] if company.get('address') else ''}", sig_style))
    elements.append(Spacer(1, 12 * mm))
    elements.append(Paragraph("_________________________", sig_style))
    elements.append(Paragraph("<b>Authorized Signatory</b>", sig_style))
    elements.append(Paragraph(company['name'], ParagraphStyle('SigCo', fontName='Arial', fontSize=9, alignment=TA_LEFT, textColor=colors.grey)))

    build_report_footer(elements, company, mm)
    doc.build(elements)
    if logo_path:
        os.unlink(logo_path)
    buf.seek(0)
    name = emp['name'].replace(' ', '_')
    return Response(content=buf.read(), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="Experience_Certificate_{name}.pdf"'})
