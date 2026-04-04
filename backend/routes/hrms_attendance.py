from fastapi import APIRouter, HTTPException, Depends
from database import db
from deps import get_current_user
from helpers import log_audit
from datetime import datetime, timezone
from typing import Optional
import uuid
import calendar

router = APIRouter()


# ============ LEAVE CONFIGURATION ============

DEFAULT_LEAVE_TYPES = [
    {'id': 'casual', 'name': 'Casual Leave', 'annual_quota': 12, 'carry_forward': False},
    {'id': 'sick', 'name': 'Sick Leave', 'annual_quota': 10, 'carry_forward': False},
    {'id': 'earned', 'name': 'Earned Leave', 'annual_quota': 15, 'carry_forward': True},
    {'id': 'unpaid', 'name': 'Unpaid Leave', 'annual_quota': 0, 'carry_forward': False},
]


@router.get("/hrms/leave/config")
async def get_leave_config(user: dict = Depends(get_current_user)):
    config = await db.hrms_leave_config.find_one({'key': 'leave_types'}, {'_id': 0})
    if not config:
        doc = {'key': 'leave_types', 'leave_types': DEFAULT_LEAVE_TYPES}
        await db.hrms_leave_config.insert_one(doc)
        return {'leave_types': DEFAULT_LEAVE_TYPES}
    return {'leave_types': config.get('leave_types', [])}


@router.put("/hrms/leave/config")
async def update_leave_config(data: dict, user: dict = Depends(get_current_user)):
    if user.get('role') not in ('admin', 'hr_admin'):
        raise HTTPException(status_code=403, detail="Admin or HR Admin required")
    leave_types = data.get('leave_types', [])
    await db.hrms_leave_config.update_one(
        {'key': 'leave_types'},
        {'$set': {'leave_types': leave_types}},
        upsert=True
    )
    return {"message": "Leave configuration updated"}


# ============ ATTENDANCE MARKING ============

@router.post("/hrms/attendance/mark")
async def mark_attendance(data: dict, user: dict = Depends(get_current_user)):
    if user.get('role') not in ('admin', 'hr_admin'):
        raise HTTPException(status_code=403, detail="Admin or HR Admin required")

    records = data.get('records', [])
    date = data.get('date', '')
    if not date:
        raise HTTPException(status_code=400, detail="Date is required")
    if not records:
        raise HTTPException(status_code=400, detail="At least one attendance record is required")

    created = 0
    updated = 0
    for rec in records:
        emp_id = rec.get('employee_id')
        status = rec.get('status', 'present')
        if status not in ('present', 'absent', 'half_day', 'late', 'leave', 'holiday', 'week_off'):
            continue

        existing = await db.hrms_attendance.find_one({'employee_id': emp_id, 'date': date})
        if existing:
            await db.hrms_attendance.update_one(
                {'employee_id': emp_id, 'date': date},
                {'$set': {
                    'status': status,
                    'leave_type': rec.get('leave_type', ''),
                    'check_in': rec.get('check_in', ''),
                    'check_out': rec.get('check_out', ''),
                    'overtime_hours': float(rec.get('overtime_hours', 0)),
                    'remarks': rec.get('remarks', ''),
                    'updated_by': user.get('name', ''),
                    'updated_at': datetime.now(timezone.utc).isoformat(),
                }}
            )
            updated += 1
        else:
            att = {
                'id': str(uuid.uuid4()),
                'employee_id': emp_id,
                'date': date,
                'status': status,
                'leave_type': rec.get('leave_type', ''),
                'check_in': rec.get('check_in', ''),
                'check_out': rec.get('check_out', ''),
                'overtime_hours': float(rec.get('overtime_hours', 0)),
                'remarks': rec.get('remarks', ''),
                'marked_by': user.get('name', ''),
                'created_at': datetime.now(timezone.utc).isoformat(),
            }
            await db.hrms_attendance.insert_one(att)
            created += 1

    return {"message": f"Attendance marked: {created} new, {updated} updated", "created": created, "updated": updated}


@router.get("/hrms/attendance")
async def get_attendance(
    date: Optional[str] = None,
    employee_id: Optional[str] = None,
    month: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
    user: dict = Depends(get_current_user)
):
    query = {}
    if date:
        query['date'] = date
    if employee_id:
        query['employee_id'] = employee_id
    if month:
        query['date'] = {'$regex': f'^{month}'}

    total = await db.hrms_attendance.count_documents(query)
    skip = (page - 1) * limit
    records = []
    async for rec in db.hrms_attendance.find(query, {'_id': 0}).sort('date', -1).skip(skip).limit(limit):
        emp = await db.hrms_employees.find_one({'id': rec['employee_id']}, {'_id': 0, 'name': 1, 'employee_id': 1, 'department_id': 1, 'designation': 1})
        if emp:
            rec['employee_name'] = emp.get('name', '')
            rec['employee_code'] = emp.get('employee_id', '')
            dept = await db.hrms_departments.find_one({'id': emp.get('department_id')}, {'_id': 0, 'name': 1})
            rec['department'] = dept['name'] if dept else 'Unassigned'
        records.append(rec)

    return {
        'records': records,
        'total': total,
        'page': page,
        'total_pages': max(1, (total + limit - 1) // limit)
    }


@router.put("/hrms/attendance/{record_id}")
async def update_attendance(record_id: str, data: dict, user: dict = Depends(get_current_user)):
    if user.get('role') not in ('admin', 'hr_admin'):
        raise HTTPException(status_code=403, detail="Admin or HR Admin required")
    allowed = ['status', 'leave_type', 'check_in', 'check_out', 'overtime_hours', 'remarks']
    update_fields = {k: v for k, v in data.items() if k in allowed}
    if 'overtime_hours' in update_fields:
        update_fields['overtime_hours'] = float(update_fields['overtime_hours'])
    update_fields['updated_by'] = user.get('name', '')
    update_fields['updated_at'] = datetime.now(timezone.utc).isoformat()

    result = await db.hrms_attendance.update_one({'id': record_id}, {'$set': update_fields})
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    return {"message": "Attendance updated"}


# ============ MONTHLY ATTENDANCE SUMMARY ============

@router.get("/hrms/attendance/monthly-summary")
async def get_monthly_attendance_summary(
    month: str,
    department_id: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """month format: YYYY-MM"""
    emp_query = {'is_active': True}
    if department_id and department_id != 'all':
        emp_query['department_id'] = department_id

    parts = month.split('-')
    year_num = int(parts[0])
    month_num = int(parts[1])
    _, total_days = calendar.monthrange(year_num, month_num)

    summaries = []
    async for emp in db.hrms_employees.find(emp_query, {'_id': 0}).sort('name', 1):
        dept = await db.hrms_departments.find_one({'id': emp.get('department_id')}, {'_id': 0, 'name': 1})

        present = await db.hrms_attendance.count_documents({
            'employee_id': emp['id'], 'date': {'$regex': f'^{month}'}, 'status': 'present'
        })
        absent = await db.hrms_attendance.count_documents({
            'employee_id': emp['id'], 'date': {'$regex': f'^{month}'}, 'status': 'absent'
        })
        half_day = await db.hrms_attendance.count_documents({
            'employee_id': emp['id'], 'date': {'$regex': f'^{month}'}, 'status': 'half_day'
        })
        late = await db.hrms_attendance.count_documents({
            'employee_id': emp['id'], 'date': {'$regex': f'^{month}'}, 'status': 'late'
        })
        leave = await db.hrms_attendance.count_documents({
            'employee_id': emp['id'], 'date': {'$regex': f'^{month}'}, 'status': 'leave'
        })
        holiday = await db.hrms_attendance.count_documents({
            'employee_id': emp['id'], 'date': {'$regex': f'^{month}'}, 'status': 'holiday'
        })
        week_off = await db.hrms_attendance.count_documents({
            'employee_id': emp['id'], 'date': {'$regex': f'^{month}'}, 'status': 'week_off'
        })

        pipeline = [
            {'$match': {'employee_id': emp['id'], 'date': {'$regex': f'^{month}'}}},
            {'$group': {'_id': None, 'total_ot': {'$sum': '$overtime_hours'}}}
        ]
        ot_result = await db.hrms_attendance.aggregate(pipeline).to_list(1)
        total_ot = ot_result[0]['total_ot'] if ot_result else 0

        effective_present = present + late + (half_day * 0.5)

        summaries.append({
            'employee_id': emp['id'],
            'employee_code': emp.get('employee_id', ''),
            'name': emp['name'],
            'department': dept['name'] if dept else 'Unassigned',
            'designation': emp.get('designation', ''),
            'total_days': total_days,
            'present': present,
            'absent': absent,
            'half_day': half_day,
            'late': late,
            'leave': leave,
            'holiday': holiday,
            'week_off': week_off,
            'overtime_hours': round(total_ot, 1),
            'effective_present': effective_present,
        })

    return {
        'month': month,
        'total_days': total_days,
        'summaries': summaries,
    }


# ============ LEAVE BALANCE ============

@router.get("/hrms/leave/balance/{employee_id}")
async def get_leave_balance(employee_id: str, year: Optional[int] = None, user: dict = Depends(get_current_user)):
    if not year:
        year = datetime.now().year

    emp = await db.hrms_employees.find_one({'id': employee_id}, {'_id': 0})
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    config = await db.hrms_leave_config.find_one({'key': 'leave_types'}, {'_id': 0})
    leave_types = config.get('leave_types', DEFAULT_LEAVE_TYPES) if config else DEFAULT_LEAVE_TYPES

    year_str = str(year)
    balances = []
    for lt in leave_types:
        taken = await db.hrms_attendance.count_documents({
            'employee_id': employee_id,
            'date': {'$regex': f'^{year_str}'},
            'status': 'leave',
            'leave_type': lt['id']
        })
        balances.append({
            'leave_type_id': lt['id'],
            'leave_type_name': lt['name'],
            'annual_quota': lt['annual_quota'],
            'taken': taken,
            'remaining': max(0, lt['annual_quota'] - taken) if lt['annual_quota'] > 0 else 'N/A',
        })

    return {
        'employee_id': employee_id,
        'employee_name': emp.get('name', ''),
        'year': year,
        'balances': balances
    }


# ============ DAILY ATTENDANCE LIST FOR A DATE ============

@router.get("/hrms/attendance/daily")
async def get_daily_attendance(
    date: str,
    department_id: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Get all employees with their attendance for a specific date"""
    emp_query = {'is_active': True}
    if department_id and department_id != 'all':
        emp_query['department_id'] = department_id

    result = []
    async for emp in db.hrms_employees.find(emp_query, {'_id': 0}).sort('name', 1):
        dept = await db.hrms_departments.find_one({'id': emp.get('department_id')}, {'_id': 0, 'name': 1})
        att = await db.hrms_attendance.find_one({'employee_id': emp['id'], 'date': date}, {'_id': 0})
        result.append({
            'employee_id': emp['id'],
            'employee_code': emp.get('employee_id', ''),
            'name': emp['name'],
            'department': dept['name'] if dept else 'Unassigned',
            'designation': emp.get('designation', ''),
            'status': att.get('status', '') if att else '',
            'check_in': att.get('check_in', '') if att else '',
            'check_out': att.get('check_out', '') if att else '',
            'overtime_hours': att.get('overtime_hours', 0) if att else 0,
            'leave_type': att.get('leave_type', '') if att else '',
            'remarks': att.get('remarks', '') if att else '',
            'record_id': att.get('id', '') if att else '',
        })

    return {'date': date, 'employees': result}
