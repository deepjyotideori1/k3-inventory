from fastapi import APIRouter, HTTPException, Depends, Response
from database import db
from deps import get_current_user
from helpers import format_inr, log_audit
from datetime import datetime, timezone
from typing import Optional
from io import BytesIO
import uuid
import calendar

router = APIRouter()


# ============ PAYROLL CONFIGURATION ============

DEFAULT_PAYROLL_CONFIG = {
    'key': 'payroll_config',
    'pf_employee_rate': 12.0,
    'pf_employer_rate': 12.0,
    'pf_wage_ceiling': 15000,
    'esi_employee_rate': 0.75,
    'esi_employer_rate': 3.25,
    'esi_wage_ceiling': 21000,
    'professional_tax_slabs': [
        {'min': 0, 'max': 15000, 'tax': 0},
        {'min': 15001, 'max': 20000, 'tax': 150},
        {'min': 20001, 'max': 999999999, 'tax': 200},
    ],
    'tds_slabs': [
        {'min': 0, 'max': 300000, 'rate': 0},
        {'min': 300001, 'max': 700000, 'rate': 5},
        {'min': 700001, 'max': 1000000, 'rate': 10},
        {'min': 1000001, 'max': 1200000, 'rate': 15},
        {'min': 1200001, 'max': 1500000, 'rate': 20},
        {'min': 1500001, 'max': 999999999, 'rate': 30},
    ],
}


@router.get("/hrms/payroll/config")
async def get_payroll_config(user: dict = Depends(get_current_user)):
    config = await db.hrms_payroll_config.find_one({'key': 'payroll_config'}, {'_id': 0})
    if not config:
        await db.hrms_payroll_config.insert_one(DEFAULT_PAYROLL_CONFIG.copy())
        result = {k: v for k, v in DEFAULT_PAYROLL_CONFIG.items() if k != 'key'}
        return result
    return {k: v for k, v in config.items() if k != 'key'}


@router.put("/hrms/payroll/config")
async def update_payroll_config(data: dict, user: dict = Depends(get_current_user)):
    if user.get('role') not in ('admin', 'hr_admin'):
        raise HTTPException(status_code=403, detail="Admin or HR Admin required")
    allowed = [
        'pf_employee_rate', 'pf_employer_rate', 'pf_wage_ceiling',
        'esi_employee_rate', 'esi_employer_rate', 'esi_wage_ceiling',
        'professional_tax_slabs', 'tds_slabs'
    ]
    update_fields = {k: v for k, v in data.items() if k in allowed}
    if not update_fields:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    await db.hrms_payroll_config.update_one(
        {'key': 'payroll_config'}, {'$set': update_fields}, upsert=True
    )
    return {"message": "Payroll configuration updated"}


# ============ PAYROLL CALCULATION HELPERS ============

def calc_pf(basic_da, config):
    applicable = min(basic_da, config.get('pf_wage_ceiling', 15000))
    emp = round(applicable * config.get('pf_employee_rate', 12) / 100, 2)
    emplr = round(applicable * config.get('pf_employer_rate', 12) / 100, 2)
    return emp, emplr


def calc_esi(gross, config):
    if gross > config.get('esi_wage_ceiling', 21000):
        return 0, 0
    emp = round(gross * config.get('esi_employee_rate', 0.75) / 100, 2)
    emplr = round(gross * config.get('esi_employer_rate', 3.25) / 100, 2)
    return emp, emplr


def calc_professional_tax(gross, config):
    slabs = config.get('professional_tax_slabs', [])
    for slab in slabs:
        if slab['min'] <= gross <= slab['max']:
            return slab['tax']
    return 0


def calc_tds_monthly(annual_gross, config):
    slabs = config.get('tds_slabs', [])
    total_tax = 0
    remaining = annual_gross
    for slab in slabs:
        if remaining <= 0:
            break
        slab_range = slab['max'] - slab['min'] + 1
        taxable = min(remaining, slab_range)
        total_tax += taxable * slab['rate'] / 100
        remaining -= taxable
    return round(total_tax / 12, 2)


def compute_employee_payroll(emp, config, working_days, days_present):
    basic = emp.get('basic_salary', 0)
    hra = emp.get('hra', 0)
    da = emp.get('da', 0)
    other = emp.get('other_allowances', 0)

    # Pro-rate based on attendance
    ratio = days_present / working_days if working_days > 0 else 1
    earned_basic = round(basic * ratio, 2)
    earned_hra = round(hra * ratio, 2)
    earned_da = round(da * ratio, 2)
    earned_other = round(other * ratio, 2)

    gross = earned_basic + earned_hra + earned_da + earned_other
    basic_da = earned_basic + earned_da

    pf_emp, pf_emplr = calc_pf(basic_da, config)
    esi_emp, esi_emplr = calc_esi(gross, config)
    pt = calc_professional_tax(gross, config)

    annual_gross = (basic + hra + da + other) * 12
    tds = calc_tds_monthly(annual_gross, config)

    total_deductions = pf_emp + esi_emp + pt + tds
    net_pay = round(gross - total_deductions, 2)

    return {
        'earned_basic': earned_basic,
        'earned_hra': earned_hra,
        'earned_da': earned_da,
        'earned_other_allowances': earned_other,
        'gross_salary': round(gross, 2),
        'pf_employee': pf_emp,
        'pf_employer': pf_emplr,
        'esi_employee': esi_emp,
        'esi_employer': esi_emplr,
        'professional_tax': pt,
        'tds': tds,
        'total_deductions': round(total_deductions, 2),
        'net_pay': net_pay,
    }


# ============ PAYROLL RUN ============

@router.post("/hrms/payroll/run")
async def run_payroll(data: dict, user: dict = Depends(get_current_user)):
    if user.get('role') not in ('admin', 'hr_admin'):
        raise HTTPException(status_code=403, detail="Admin or HR Admin required")

    month = int(data.get('month', datetime.now().month))
    year = int(data.get('year', datetime.now().year))
    period = f"{year}-{month:02d}"

    existing = await db.hrms_payroll.find_one({'period': period, 'status': 'finalized'})
    if existing:
        raise HTTPException(status_code=400, detail=f"Payroll for {period} is already finalized")

    # Delete previous drafts for same period
    await db.hrms_payroll.delete_many({'period': period, 'status': 'draft'})

    config_doc = await db.hrms_payroll_config.find_one({'key': 'payroll_config'}, {'_id': 0})
    if not config_doc:
        config_doc = DEFAULT_PAYROLL_CONFIG

    working_days = int(data.get('working_days', 26))
    _, total_days_in_month = calendar.monthrange(year, month)

    employees = []
    async for emp in db.hrms_employees.find({'is_active': True}, {'_id': 0}):
        # Get attendance for this employee for this month
        att_count = await db.hrms_attendance.count_documents({
            'employee_id': emp['id'],
            'date': {'$regex': f'^{period}'},
            'status': {'$in': ['present', 'half_day', 'late']}
        })
        half_days = await db.hrms_attendance.count_documents({
            'employee_id': emp['id'],
            'date': {'$regex': f'^{period}'},
            'status': 'half_day'
        })
        days_present = att_count - (half_days * 0.5)
        if days_present == 0:
            days_present = working_days  # If no attendance data, assume full

        dept = await db.hrms_departments.find_one({'id': emp.get('department_id')}, {'_id': 0})
        payroll_data = compute_employee_payroll(emp, config_doc, working_days, days_present)

        employees.append({
            'employee_id': emp['id'],
            'employee_code': emp.get('employee_id', ''),
            'name': emp['name'],
            'department': dept['name'] if dept else 'Unassigned',
            'designation': emp.get('designation', ''),
            'bank_account_no': emp.get('bank_account_no', ''),
            'ifsc_code': emp.get('ifsc_code', ''),
            'bank_name': emp.get('bank_name', ''),
            'working_days': working_days,
            'days_present': days_present,
            'basic_salary': emp.get('basic_salary', 0),
            'hra': emp.get('hra', 0),
            'da': emp.get('da', 0),
            'other_allowances': emp.get('other_allowances', 0),
            **payroll_data
        })

    payroll_run = {
        'id': str(uuid.uuid4()),
        'period': period,
        'month': month,
        'year': year,
        'working_days': working_days,
        'total_employees': len(employees),
        'employees': employees,
        'total_gross': round(sum(e['gross_salary'] for e in employees), 2),
        'total_deductions': round(sum(e['total_deductions'] for e in employees), 2),
        'total_net_pay': round(sum(e['net_pay'] for e in employees), 2),
        'total_pf_employer': round(sum(e['pf_employer'] for e in employees), 2),
        'total_esi_employer': round(sum(e['esi_employer'] for e in employees), 2),
        'status': 'draft',
        'created_by': user.get('name', ''),
        'created_at': datetime.now(timezone.utc).isoformat(),
    }

    await db.hrms_payroll.insert_one(payroll_run)
    await log_audit(user.get('id', ''), user.get('name', ''), 'create', 'payroll', payroll_run['id'], f"Payroll run for {period}")

    return {k: v for k, v in payroll_run.items() if k != '_id'}


@router.post("/hrms/payroll/{payroll_id}/finalize")
async def finalize_payroll(payroll_id: str, user: dict = Depends(get_current_user)):
    if user.get('role') not in ('admin', 'hr_admin'):
        raise HTTPException(status_code=403, detail="Admin or HR Admin required")
    result = await db.hrms_payroll.update_one(
        {'id': payroll_id, 'status': 'draft'},
        {'$set': {'status': 'finalized', 'finalized_at': datetime.now(timezone.utc).isoformat(), 'finalized_by': user.get('name', '')}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Payroll not found or already finalized")
    return {"message": "Payroll finalized"}


# ============ PAYROLL HISTORY ============

@router.get("/hrms/payroll/history")
async def get_payroll_history(
    year: Optional[int] = None,
    user: dict = Depends(get_current_user)
):
    query = {}
    if year:
        query['year'] = year
    payrolls = []
    async for p in db.hrms_payroll.find(query, {'_id': 0, 'employees': 0}).sort([('year', -1), ('month', -1)]):
        payrolls.append(p)
    return payrolls


@router.get("/hrms/payroll/{payroll_id}")
async def get_payroll_detail(payroll_id: str, user: dict = Depends(get_current_user)):
    payroll = await db.hrms_payroll.find_one({'id': payroll_id}, {'_id': 0})
    if not payroll:
        raise HTTPException(status_code=404, detail="Payroll record not found")
    return payroll


@router.delete("/hrms/payroll/{payroll_id}")
async def delete_payroll(payroll_id: str, user: dict = Depends(get_current_user)):
    if user.get('role') not in ('admin', 'hr_admin'):
        raise HTTPException(status_code=403, detail="Admin or HR Admin required")
    result = await db.hrms_payroll.delete_one({'id': payroll_id, 'status': 'draft'})
    if result.deleted_count == 0:
        raise HTTPException(status_code=400, detail="Cannot delete finalized payroll or not found")
    return {"message": "Payroll draft deleted"}


# ============ PAYSLIP PDF ============

@router.get("/hrms/payroll/{payroll_id}/payslip/{employee_id}/pdf")
async def download_payslip_pdf(payroll_id: str, employee_id: str, user: dict = Depends(get_current_user)):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

    payroll = await db.hrms_payroll.find_one({'id': payroll_id}, {'_id': 0})
    if not payroll:
        raise HTTPException(status_code=404, detail="Payroll not found")

    emp_data = None
    for e in payroll.get('employees', []):
        if e['employee_id'] == employee_id:
            emp_data = e
            break
    if not emp_data:
        raise HTTPException(status_code=404, detail="Employee not found in this payroll")

    settings = await db.hrms_settings.find_one({'key': 'company_info'}, {'_id': 0})
    company_name = settings.get('company_name', 'K3 GAS SERVICE') if settings else 'K3 GAS SERVICE'
    company_address = settings.get('address', '') if settings else ''
    month_name = calendar.month_name[payroll['month']]

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15*mm, rightMargin=15*mm, topMargin=15*mm, bottomMargin=15*mm)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', fontName='Helvetica-Bold', fontSize=14, alignment=TA_CENTER, spaceAfter=2*mm)
    subtitle_style = ParagraphStyle('Subtitle', fontName='Helvetica', fontSize=9, alignment=TA_CENTER, spaceAfter=4*mm, textColor=colors.grey)
    section_style = ParagraphStyle('Section', fontName='Helvetica-Bold', fontSize=10, spaceAfter=2*mm, spaceBefore=4*mm)
    normal_style = ParagraphStyle('Normal2', fontName='Helvetica', fontSize=9)

    elements = []
    elements.append(Paragraph(company_name, title_style))
    elements.append(Paragraph(company_address, subtitle_style))
    elements.append(Paragraph(f"PAYSLIP - {month_name} {payroll['year']}", ParagraphStyle('PS', fontName='Helvetica-Bold', fontSize=12, alignment=TA_CENTER, spaceAfter=6*mm)))

    # Employee Info Table
    info_data = [
        ['Employee Name', emp_data['name'], 'Employee ID', emp_data['employee_code']],
        ['Department', emp_data['department'], 'Designation', emp_data['designation']],
        ['Working Days', str(emp_data['working_days']), 'Days Present', str(emp_data['days_present'])],
        ['Bank', emp_data.get('bank_name', 'N/A'), 'A/C No', emp_data.get('bank_account_no', 'N/A')],
    ]
    info_table = Table(info_data, colWidths=[80, 140, 80, 140])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.grey),
        ('TEXTCOLOR', (2, 0), (2, -1), colors.grey),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('BACKGROUND', (0, 0), (-1, -1), colors.Color(0.97, 0.97, 0.97)),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 6*mm))

    # Earnings & Deductions side-by-side
    earnings = [
        ['EARNINGS', 'Amount (Rs)'],
        ['Basic Salary', format_inr(emp_data['earned_basic'])],
        ['HRA', format_inr(emp_data['earned_hra'])],
        ['DA', format_inr(emp_data['earned_da'])],
        ['Other Allowances', format_inr(emp_data['earned_other_allowances'])],
        ['', ''],
        ['Gross Salary', format_inr(emp_data['gross_salary'])],
    ]
    deductions = [
        ['DEDUCTIONS', 'Amount (Rs)'],
        ['PF (Employee)', format_inr(emp_data['pf_employee'])],
        ['ESI (Employee)', format_inr(emp_data['esi_employee'])],
        ['Professional Tax', format_inr(emp_data['professional_tax'])],
        ['TDS', format_inr(emp_data['tds'])],
        ['', ''],
        ['Total Deductions', format_inr(emp_data['total_deductions'])],
    ]

    combined = []
    for i in range(len(earnings)):
        combined.append([earnings[i][0], earnings[i][1], deductions[i][0], deductions[i][1]])

    pay_table = Table(combined, colWidths=[110, 90, 110, 90])
    pay_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.2, 0.4, 0.7)),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BACKGROUND', (0, -1), (1, -1), colors.Color(0.9, 0.95, 0.9)),
        ('BACKGROUND', (2, -1), (3, -1), colors.Color(0.95, 0.9, 0.9)),
    ]))
    elements.append(pay_table)
    elements.append(Spacer(1, 6*mm))

    # Net Pay
    net_data = [['NET PAY', format_inr(emp_data['net_pay'])]]
    net_table = Table(net_data, colWidths=[310, 90])
    net_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('BACKGROUND', (0, 0), (-1, -1), colors.Color(0.15, 0.55, 0.3)),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(net_table)

    elements.append(Spacer(1, 10*mm))
    elements.append(Paragraph("This is a system-generated payslip.", ParagraphStyle('Footer', fontName='Helvetica', fontSize=7, alignment=TA_CENTER, textColor=colors.grey)))

    doc.build(elements)
    buf.seek(0)
    filename = f"Payslip_{emp_data['name'].replace(' ', '_')}_{month_name}_{payroll['year']}.pdf"
    return Response(
        content=buf.read(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
