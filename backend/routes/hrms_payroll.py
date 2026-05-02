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


# ---- TDS (versioned, regime-aware, effective-date gated) ----
DEFAULT_TDS_SLABS_NEW = [
    {'min': 0, 'max': 300000, 'rate': 0},
    {'min': 300001, 'max': 700000, 'rate': 5},
    {'min': 700001, 'max': 1000000, 'rate': 10},
    {'min': 1000001, 'max': 1200000, 'rate': 15},
    {'min': 1200001, 'max': 1500000, 'rate': 20},
    {'min': 1500001, 'max': 999999999, 'rate': 30},
]
DEFAULT_TDS_SLABS_OLD = [
    {'min': 0, 'max': 250000, 'rate': 0},
    {'min': 250001, 'max': 500000, 'rate': 5},
    {'min': 500001, 'max': 1000000, 'rate': 20},
    {'min': 1000001, 'max': 999999999, 'rate': 30},
]


async def _get_latest_tds_version(effective_on: Optional[str] = None) -> dict:
    """Return the TDS config version whose effective_date <= effective_on (or today)."""
    if effective_on is None:
        effective_on = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    doc = await db.hrms_tds_config_versions.find_one(
        {'effective_date': {'$lte': effective_on}},
        {'_id': 0},
        sort=[('effective_date', -1), ('version', -1)],
    )
    if not doc:
        # Seed a first version with defaults
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            'id': str(uuid.uuid4()),
            'version': 1,
            'tds_slabs_new': DEFAULT_TDS_SLABS_NEW,
            'tds_slabs_old': DEFAULT_TDS_SLABS_OLD,
            'default_regime': 'new',
            'cess_percent': 4.0,
            'surcharge_percent': 0.0,
            'effective_date': '2020-04-01',
            'reason': 'Auto-seeded initial TDS configuration',
            'created_by_id': 'system',
            'created_by_name': 'System',
            'created_at': now,
        }
        await db.hrms_tds_config_versions.insert_one(doc.copy())
    return doc


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


# ============ TDS CONFIGURATION (versioned) ============

@router.get("/hrms/payroll/tds-config")
async def get_tds_config(effective_on: Optional[str] = None, user: dict = Depends(get_current_user)):
    """Returns the TDS config active as of `effective_on` (default: today)."""
    doc = await _get_latest_tds_version(effective_on)
    return doc


@router.put("/hrms/payroll/tds-config")
async def update_tds_config(data: dict, user: dict = Depends(get_current_user)):
    """Saves a NEW version row (never mutates an existing one). Requires admin/hr_admin.
    Body: tds_slabs_new, tds_slabs_old, default_regime, cess_percent, surcharge_percent,
          effective_date (YYYY-MM-DD), reason.
    Rejects effective dates that fall inside a finalized payroll period.
    """
    if user.get('role') not in ('admin', 'hr_admin'):
        raise HTTPException(status_code=403, detail="Only Admin / HR Admin can modify TDS rules")

    effective_date = (data.get('effective_date') or '').strip()
    if not effective_date or len(effective_date) != 10:
        raise HTTPException(status_code=400, detail="effective_date (YYYY-MM-DD) is required")
    reason = (data.get('reason') or '').strip()
    if not reason:
        raise HTTPException(status_code=400, detail="A change reason is required")

    # Block effective dates that land in or before an already-finalized payroll period
    period = effective_date[:7]  # YYYY-MM
    finalized = await db.hrms_payroll.find_one(
        {'status': 'finalized', 'period': {'$gte': period}},
        {'_id': 0, 'period': 1}
    )
    if finalized:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot set effective_date {effective_date}: payroll for {finalized['period']} "
                   "is already finalized. Pick a future effective_date beyond all finalized periods."
        )

    # Build new version
    prev = await db.hrms_tds_config_versions.find_one({}, sort=[('version', -1)])
    new_version = int(prev.get('version', 0)) + 1 if prev else 1
    now = datetime.now(timezone.utc).isoformat()

    def _clean_slabs(raw, default):
        if not isinstance(raw, list) or not raw:
            return default
        cleaned = []
        for s in raw:
            try:
                cleaned.append({
                    'min': int(s.get('min', 0)),
                    'max': int(s.get('max', 0)),
                    'rate': float(s.get('rate', 0)),
                })
            except (TypeError, ValueError):
                continue
        return cleaned or default

    default_regime = (data.get('default_regime') or 'new').lower()
    if default_regime not in ('new', 'old'):
        raise HTTPException(status_code=400, detail="default_regime must be 'new' or 'old'")

    doc = {
        'id': str(uuid.uuid4()),
        'version': new_version,
        'tds_slabs_new': _clean_slabs(data.get('tds_slabs_new'), DEFAULT_TDS_SLABS_NEW),
        'tds_slabs_old': _clean_slabs(data.get('tds_slabs_old'), DEFAULT_TDS_SLABS_OLD),
        'default_regime': default_regime,
        'cess_percent': float(data.get('cess_percent', 4.0) or 0),
        'surcharge_percent': float(data.get('surcharge_percent', 0) or 0),
        'effective_date': effective_date,
        'reason': reason,
        'created_by_id': user.get('id', ''),
        'created_by_name': user.get('name', ''),
        'created_at': now,
    }
    await db.hrms_tds_config_versions.insert_one(doc.copy())
    await log_audit(
        user.get('id', ''), user.get('name', ''), 'update', 'hrms_tds_config', doc['id'],
        f"TDS v{new_version} effective {effective_date}: {reason}"
    )
    doc.pop('_id', None)
    return doc


@router.get("/hrms/payroll/tds-config/history")
async def tds_config_history(user: dict = Depends(get_current_user)):
    history = await db.hrms_tds_config_versions.find({}, {'_id': 0}).sort('version', -1).to_list(200)
    return history


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


def calc_tds_monthly(annual_gross, tds_config, regime='new'):
    """Progressive slab calc + cess + optional surcharge, divided by 12 months.
    tds_config: dict with keys tds_slabs_new / tds_slabs_old / cess_percent / surcharge_percent.
    """
    slabs = tds_config.get('tds_slabs_new' if regime == 'new' else 'tds_slabs_old', [])
    if not slabs:
        return 0.0
    total_tax = 0.0
    for slab in slabs:
        slab_min = int(slab.get('min', 0))
        slab_max = int(slab.get('max', 0))
        rate = float(slab.get('rate', 0)) / 100.0
        if annual_gross <= slab_min:
            break
        taxable = min(annual_gross, slab_max) - slab_min + 1
        if taxable <= 0:
            continue
        total_tax += taxable * rate
    # Surcharge (flat % on total_tax)
    surcharge = total_tax * float(tds_config.get('surcharge_percent', 0) or 0) / 100.0
    # Cess (% on total_tax + surcharge)
    cess = (total_tax + surcharge) * float(tds_config.get('cess_percent', 0) or 0) / 100.0
    return round((total_tax + surcharge + cess) / 12, 2)


def compute_employee_payroll(emp, config, working_days, days_present, tds_config=None):
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
    # TDS is OPT-IN per employee. Only calculate when `emp.tds_applicable` is explicitly True.
    # Default behaviour: no TDS deducted.
    tds_applicable = bool(emp.get('tds_applicable', False))
    regime = (emp.get('tax_regime') or (tds_config.get('default_regime', 'new') if tds_config else 'new')).lower()
    if regime not in ('new', 'old'):
        regime = 'new'

    if not tds_applicable:
        tds = 0.0
    elif tds_config:
        tds = calc_tds_monthly(annual_gross, tds_config, regime)
    else:
        # Legacy path — treat payroll_config.tds_slabs as new regime with no surcharge/cess
        legacy_cfg = {'tds_slabs_new': config.get('tds_slabs', []), 'tds_slabs_old': [],
                      'cess_percent': 0, 'surcharge_percent': 0}
        tds = calc_tds_monthly(annual_gross, legacy_cfg, 'new')

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
        'tds_applicable': tds_applicable,
        'tax_regime': regime,
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

    # Versioned TDS config: pick the version effective on the 1st of the payroll month
    period_start = f"{year}-{month:02d}-01"
    tds_config = await _get_latest_tds_version(period_start)

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
        payroll_data = compute_employee_payroll(emp, config_doc, working_days, days_present, tds_config=tds_config)

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
            'adjustments': [],
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
        'tds_config_version': tds_config.get('version'),
        'tds_effective_date': tds_config.get('effective_date'),
        'default_regime_used': tds_config.get('default_regime', 'new'),
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
    payroll = await db.hrms_payroll.find_one({'id': payroll_id, 'status': 'draft'})
    if not payroll:
        raise HTTPException(status_code=400, detail="Payroll not found or already finalized")
    # Recalculate final totals including adjustments
    total_net = 0
    total_gross = 0
    total_deductions = 0
    for emp in payroll.get('employees', []):
        adj_total = sum(
            a['amount'] if a['type'] == 'earning' else -a['amount']
            for a in emp.get('adjustments', [])
        )
        final_net = emp.get('net_pay', 0) + adj_total
        total_net += final_net
        total_gross += emp.get('gross_salary', 0)
        total_deductions += emp.get('total_deductions', 0)
    await db.hrms_payroll.update_one(
        {'id': payroll_id},
        {'$set': {
            'status': 'finalized',
            'total_net_pay': round(total_net, 2),
            'finalized_at': datetime.now(timezone.utc).isoformat(),
            'finalized_by': user.get('name', ''),
        }}
    )
    await log_audit(user.get('id', ''), user.get('name', ''), 'finalize', 'payroll', payroll_id, f"Finalized payroll {payroll.get('period')}")
    return {"message": "Payroll finalized"}


# ============ POST-PAYROLL ADJUSTMENTS ============

@router.get("/hrms/payroll/{payroll_id}/review")
async def review_payroll(payroll_id: str, user: dict = Depends(get_current_user)):
    """Get payroll with adjustment summary for review before finalization"""
    payroll = await db.hrms_payroll.find_one({'id': payroll_id}, {'_id': 0})
    if not payroll:
        raise HTTPException(status_code=404, detail="Payroll not found")
    # Compute per-employee adjustment totals
    review_employees = []
    total_adjustments = 0
    for emp in payroll.get('employees', []):
        adjustments = emp.get('adjustments', [])
        adj_earnings = sum(a['amount'] for a in adjustments if a['type'] == 'earning')
        adj_deductions = sum(a['amount'] for a in adjustments if a['type'] == 'deduction')
        adj_net = adj_earnings - adj_deductions
        final_net = round(emp.get('net_pay', 0) + adj_net, 2)
        total_adjustments += adj_net
        review_employees.append({
            **emp,
            'adjustment_earnings': round(adj_earnings, 2),
            'adjustment_deductions': round(adj_deductions, 2),
            'adjustment_net': round(adj_net, 2),
            'final_net_pay': final_net,
            'is_modified': len(adjustments) > 0,
        })
    return {
        **{k: v for k, v in payroll.items() if k != 'employees'},
        'employees': review_employees,
        'total_adjustments': round(total_adjustments, 2),
        'total_final_net_pay': round(payroll.get('total_net_pay', 0) + total_adjustments, 2),
    }


@router.post("/hrms/payroll/{payroll_id}/adjustments")
async def add_adjustment(payroll_id: str, data: dict, user: dict = Depends(get_current_user)):
    """Add a custom deduction or earning for an employee in a draft payroll"""
    if user.get('role') not in ('admin', 'hr_admin'):
        raise HTTPException(status_code=403, detail="Admin or HR Admin required")

    payroll = await db.hrms_payroll.find_one({'id': payroll_id})
    if not payroll:
        raise HTTPException(status_code=404, detail="Payroll not found")
    if payroll.get('status') == 'finalized':
        raise HTTPException(status_code=400, detail="Cannot modify finalized payroll")

    employee_id = data.get('employee_id', '').strip()
    adj_name = data.get('name', '').strip()
    adj_type = data.get('type', '').strip()
    amount = data.get('amount')
    reason = data.get('reason', '').strip()

    if not all([employee_id, adj_name, adj_type, reason]):
        raise HTTPException(status_code=400, detail="Name, type, amount, and reason are required")
    if adj_type not in ('earning', 'deduction'):
        raise HTTPException(status_code=400, detail="Type must be 'earning' or 'deduction'")
    try:
        amount = round(float(amount), 2)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Amount must be a valid number")
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    # Check employee exists in payroll
    emp_found = False
    emp_net_pay = 0
    for emp in payroll.get('employees', []):
        if emp['employee_id'] == employee_id:
            emp_found = True
            emp_net_pay = emp.get('net_pay', 0)
            break
    if not emp_found:
        raise HTTPException(status_code=404, detail="Employee not found in this payroll")

    # Check if deduction would make net salary negative
    if adj_type == 'deduction':
        existing_adjs = []
        for emp in payroll.get('employees', []):
            if emp['employee_id'] == employee_id:
                existing_adjs = emp.get('adjustments', [])
                break
        current_adj_total = sum(
            a['amount'] if a['type'] == 'earning' else -a['amount']
            for a in existing_adjs
        )
        projected_net = emp_net_pay + current_adj_total - amount
        if projected_net < 0:
            raise HTTPException(status_code=400, detail=f"This deduction would result in negative net salary (Rs.{projected_net:,.2f}). Reduce the amount or add approval.")

    adjustment = {
        'id': str(uuid.uuid4()),
        'name': adj_name,
        'type': adj_type,
        'amount': amount,
        'reason': reason,
        'created_by': user.get('name', ''),
        'created_by_id': user.get('id', ''),
        'created_at': datetime.now(timezone.utc).isoformat(),
    }

    await db.hrms_payroll.update_one(
        {'id': payroll_id, 'employees.employee_id': employee_id},
        {'$push': {'employees.$.adjustments': adjustment}}
    )
    await log_audit(
        user.get('id', ''), user.get('name', ''), 'create', 'payroll_adjustment',
        payroll_id, f"{adj_type.capitalize()} '{adj_name}' Rs.{amount} for employee {employee_id}: {reason}"
    )
    return {'message': 'Adjustment added', 'adjustment': adjustment}


@router.put("/hrms/payroll/{payroll_id}/adjustments/{adjustment_id}")
async def update_adjustment(payroll_id: str, adjustment_id: str, data: dict, user: dict = Depends(get_current_user)):
    if user.get('role') not in ('admin', 'hr_admin'):
        raise HTTPException(status_code=403, detail="Admin or HR Admin required")
    payroll = await db.hrms_payroll.find_one({'id': payroll_id})
    if not payroll or payroll.get('status') == 'finalized':
        raise HTTPException(status_code=400, detail="Payroll not found or already finalized")

    # Find and update the adjustment
    updated = False
    for emp in payroll.get('employees', []):
        for i, adj in enumerate(emp.get('adjustments', [])):
            if adj['id'] == adjustment_id:
                if 'name' in data and data['name'].strip():
                    adj['name'] = data['name'].strip()
                if 'type' in data and data['type'] in ('earning', 'deduction'):
                    adj['type'] = data['type']
                if 'amount' in data:
                    try:
                        adj['amount'] = round(float(data['amount']), 2)
                    except (ValueError, TypeError):
                        raise HTTPException(status_code=400, detail="Invalid amount")
                if 'reason' in data and data['reason'].strip():
                    adj['reason'] = data['reason'].strip()
                adj['updated_by'] = user.get('name', '')
                adj['updated_at'] = datetime.now(timezone.utc).isoformat()
                emp['adjustments'][i] = adj

                await db.hrms_payroll.update_one(
                    {'id': payroll_id, 'employees.employee_id': emp['employee_id']},
                    {'$set': {'employees.$.adjustments': emp['adjustments']}}
                )
                updated = True
                break
        if updated:
            break

    if not updated:
        raise HTTPException(status_code=404, detail="Adjustment not found")
    await log_audit(user.get('id', ''), user.get('name', ''), 'update', 'payroll_adjustment', payroll_id, f"Updated adjustment {adjustment_id}")
    return {'message': 'Adjustment updated'}


@router.delete("/hrms/payroll/{payroll_id}/adjustments/{adjustment_id}")
async def delete_adjustment(payroll_id: str, adjustment_id: str, user: dict = Depends(get_current_user)):
    if user.get('role') not in ('admin', 'hr_admin'):
        raise HTTPException(status_code=403, detail="Admin or HR Admin required")
    payroll = await db.hrms_payroll.find_one({'id': payroll_id})
    if not payroll or payroll.get('status') == 'finalized':
        raise HTTPException(status_code=400, detail="Payroll not found or already finalized")

    deleted = False
    for emp in payroll.get('employees', []):
        original_len = len(emp.get('adjustments', []))
        emp['adjustments'] = [a for a in emp.get('adjustments', []) if a['id'] != adjustment_id]
        if len(emp['adjustments']) < original_len:
            await db.hrms_payroll.update_one(
                {'id': payroll_id, 'employees.employee_id': emp['employee_id']},
                {'$set': {'employees.$.adjustments': emp['adjustments']}}
            )
            deleted = True
            break

    if not deleted:
        raise HTTPException(status_code=404, detail="Adjustment not found")
    await log_audit(user.get('id', ''), user.get('name', ''), 'delete', 'payroll_adjustment', payroll_id, f"Deleted adjustment {adjustment_id}")
    return {'message': 'Adjustment removed'}


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
    async for p in db.hrms_payroll.find(query, {'_id': 0, 'employees': 0}).sort([('year', 1), ('month', 1)]):
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

    title_style = ParagraphStyle('Title', fontName='Helvetica-Bold', fontSize=14, alignment=TA_CENTER, spaceAfter=2*mm)
    subtitle_style = ParagraphStyle('Subtitle', fontName='Helvetica', fontSize=9, alignment=TA_CENTER, spaceAfter=4*mm, textColor=colors.grey)

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
    ]
    # Add earning adjustments
    for adj in emp_data.get('adjustments', []):
        if adj['type'] == 'earning':
            earnings.append([adj['name'], format_inr(adj['amount'])])
    adj_earnings_total = sum(a['amount'] for a in emp_data.get('adjustments', []) if a['type'] == 'earning')
    gross_with_adj = emp_data['gross_salary'] + adj_earnings_total
    earnings.append(['', ''])
    earnings.append(['Gross + Earnings', format_inr(gross_with_adj)])

    deductions = [
        ['DEDUCTIONS', 'Amount (Rs)'],
        ['PF (Employee)', format_inr(emp_data['pf_employee'])],
        ['ESI (Employee)', format_inr(emp_data['esi_employee'])],
        ['Professional Tax', format_inr(emp_data['professional_tax'])],
        ['TDS', format_inr(emp_data['tds'])],
    ]
    # Add deduction adjustments
    for adj in emp_data.get('adjustments', []):
        if adj['type'] == 'deduction':
            deductions.append([adj['name'], format_inr(adj['amount'])])
    adj_deductions_total = sum(a['amount'] for a in emp_data.get('adjustments', []) if a['type'] == 'deduction')
    total_ded = emp_data['total_deductions'] + adj_deductions_total
    deductions.append(['', ''])
    deductions.append(['Total Deductions', format_inr(total_ded)])

    # Pad to equal length
    while len(earnings) < len(deductions):
        earnings.append(['', ''])
    while len(deductions) < len(earnings):
        deductions.append(['', ''])

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

    # Net Pay (including adjustments)
    adj_net = adj_earnings_total - adj_deductions_total
    final_net = round(emp_data['net_pay'] + adj_net, 2)
    net_data = [['NET PAY', format_inr(final_net)]]
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
