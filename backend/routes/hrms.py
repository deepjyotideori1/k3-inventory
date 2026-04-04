from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Response
from database import db
from deps import get_current_user, require_admin
from helpers import format_inr, log_audit, hash_password
from datetime import datetime, timezone
from typing import Optional, List
from io import BytesIO
from bson import Binary
import uuid
import base64

router = APIRouter()


# ============ HRMS COMPANY SETTINGS ============

@router.get("/hrms/company-settings")
async def get_hrms_company_settings(user: dict = Depends(get_current_user)):
    settings = await db.hrms_settings.find_one({'key': 'company_info'}, {'_id': 0})
    if not settings:
        default = {
            'key': 'company_info',
            'company_name': 'K3 GAS SERVICE',
            'tagline': 'Khayal Hamesha',
            'address': 'K3 Tower Building, Gohpur Tiniali, Near SBI Gohpur, Itanagar, Arunachal Pradesh - 791111',
            'email': 'ita@k3gasservice.com',
            'helpline': '+91 6009222322',
            'logo_url': '',
        }
        await db.hrms_settings.insert_one(default)
        del default['key']
        return default
    result = {k: v for k, v in settings.items() if k != 'key'}
    return result


@router.put("/hrms/company-settings")
async def update_hrms_company_settings(data: dict, user: dict = Depends(get_current_user)):
    if user.get('role') not in ('admin', 'hr_admin'):
        raise HTTPException(status_code=403, detail="Only Admin or HR Admin can update company settings")
    update_fields = {}
    for field in ['company_name', 'tagline', 'address', 'email', 'helpline', 'logo_url']:
        if field in data:
            update_fields[field] = data[field]
    if not update_fields:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    await db.hrms_settings.update_one(
        {'key': 'company_info'},
        {'$set': update_fields},
        upsert=True
    )
    return {"message": "Company settings updated successfully"}


@router.post("/hrms/company-logo")
async def upload_company_logo(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    if user.get('role') not in ('admin', 'hr_admin'):
        raise HTTPException(status_code=403, detail="Only Admin or HR Admin can upload logo")
    content = await file.read()
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size must be under 2MB")
    encoded = base64.b64encode(content).decode('utf-8')
    content_type = file.content_type or 'image/png'
    data_uri = f"data:{content_type};base64,{encoded}"
    await db.hrms_settings.update_one(
        {'key': 'company_info'},
        {'$set': {'logo_url': data_uri}},
        upsert=True
    )
    return {"message": "Logo uploaded successfully", "logo_url": data_uri}


# ============ DEPARTMENTS ============

@router.get("/hrms/departments")
async def get_departments(user: dict = Depends(get_current_user)):
    departments = []
    async for dept in db.hrms_departments.find({}, {'_id': 0}).sort('name', 1):
        departments.append(dept)
    return departments


@router.post("/hrms/departments")
async def create_department(data: dict, user: dict = Depends(get_current_user)):
    if user.get('role') not in ('admin', 'hr_admin'):
        raise HTTPException(status_code=403, detail="Admin or HR Admin required")
    name = data.get('name', '').strip()
    if not name:
        raise HTTPException(status_code=400, detail="Department name is required")
    existing = await db.hrms_departments.find_one({'name': {'$regex': f'^{name}$', '$options': 'i'}})
    if existing:
        raise HTTPException(status_code=400, detail="Department already exists")
    dept = {
        'id': str(uuid.uuid4()),
        'name': name,
        'description': data.get('description', ''),
        'created_at': datetime.now(timezone.utc).isoformat(),
        'is_active': True
    }
    await db.hrms_departments.insert_one(dept)
    return {'id': dept['id'], 'name': dept['name'], 'description': dept['description'], 'is_active': True, 'created_at': dept['created_at']}


@router.delete("/hrms/departments/{dept_id}")
async def delete_department(dept_id: str, user: dict = Depends(get_current_user)):
    if user.get('role') not in ('admin', 'hr_admin'):
        raise HTTPException(status_code=403, detail="Admin or HR Admin required")
    emp_count = await db.hrms_employees.count_documents({'department_id': dept_id, 'is_active': True})
    if emp_count > 0:
        raise HTTPException(status_code=400, detail=f"Cannot delete: {emp_count} active employees in this department")
    result = await db.hrms_departments.delete_one({'id': dept_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Department not found")
    return {"message": "Department deleted"}


# ============ EMPLOYEES ============

@router.get("/hrms/employees")
async def get_employees(
    search: Optional[str] = None,
    department_id: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    user: dict = Depends(get_current_user)
):
    query = {}
    if search:
        query['$or'] = [
            {'name': {'$regex': search, '$options': 'i'}},
            {'employee_id': {'$regex': search, '$options': 'i'}},
            {'email': {'$regex': search, '$options': 'i'}},
            {'phone': {'$regex': search, '$options': 'i'}},
        ]
    if department_id and department_id != 'all':
        query['department_id'] = department_id
    if status and status != 'all':
        query['is_active'] = status == 'active'

    total = await db.hrms_employees.count_documents(query)
    skip = (page - 1) * limit
    employees = []
    async for emp in db.hrms_employees.find(query, {'_id': 0}).sort('name', 1).skip(skip).limit(limit):
        dept = await db.hrms_departments.find_one({'id': emp.get('department_id')}, {'_id': 0})
        emp['department_name'] = dept['name'] if dept else 'Unassigned'
        employees.append(emp)

    return {
        'employees': employees,
        'total': total,
        'page': page,
        'total_pages': max(1, (total + limit - 1) // limit)
    }


@router.get("/hrms/employees/{employee_id}")
async def get_employee(employee_id: str, user: dict = Depends(get_current_user)):
    emp = await db.hrms_employees.find_one({'id': employee_id}, {'_id': 0})
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    dept = await db.hrms_departments.find_one({'id': emp.get('department_id')}, {'_id': 0})
    emp['department_name'] = dept['name'] if dept else 'Unassigned'
    return emp


@router.post("/hrms/employees")
async def create_employee(data: dict, user: dict = Depends(get_current_user)):
    if user.get('role') not in ('admin', 'hr_admin'):
        raise HTTPException(status_code=403, detail="Admin or HR Admin required")
    
    required = ['name', 'email', 'phone', 'department_id', 'designation', 'date_of_joining']
    for field in required:
        if not data.get(field):
            raise HTTPException(status_code=400, detail=f"{field} is required")

    existing = await db.hrms_employees.find_one({'email': data['email']})
    if existing:
        raise HTTPException(status_code=400, detail="Employee with this email already exists")

    # Generate employee ID
    count = await db.hrms_employees.count_documents({})
    emp_id_num = f"K3-{count + 1:04d}"

    employee = {
        'id': str(uuid.uuid4()),
        'employee_id': emp_id_num,
        'name': data['name'],
        'email': data['email'],
        'phone': data['phone'],
        'date_of_birth': data.get('date_of_birth', ''),
        'gender': data.get('gender', ''),
        'address': data.get('address', ''),
        'department_id': data['department_id'],
        'designation': data['designation'],
        'date_of_joining': data['date_of_joining'],
        'employment_type': data.get('employment_type', 'full_time'),
        'basic_salary': float(data.get('basic_salary', 0)),
        'hra': float(data.get('hra', 0)),
        'da': float(data.get('da', 0)),
        'other_allowances': float(data.get('other_allowances', 0)),
        'pf_number': data.get('pf_number', ''),
        'esi_number': data.get('esi_number', ''),
        'pan_number': data.get('pan_number', ''),
        'aadhar_number': data.get('aadhar_number', ''),
        'bank_name': data.get('bank_name', ''),
        'bank_account_no': data.get('bank_account_no', ''),
        'ifsc_code': data.get('ifsc_code', ''),
        'photo_url': data.get('photo_url', ''),
        'emergency_contact_name': data.get('emergency_contact_name', ''),
        'emergency_contact_phone': data.get('emergency_contact_phone', ''),
        'is_active': True,
        'status': 'active',
        'increment_history': [],
        'created_by': user.get('id', ''),
        'created_at': datetime.now(timezone.utc).isoformat(),
        'updated_at': datetime.now(timezone.utc).isoformat(),
    }
    await db.hrms_employees.insert_one(employee)
    await log_audit(user.get('id', ''), user.get('name', ''), 'create', 'employee', employee['id'], f"Created employee: {employee['name']}")
    
    dept = await db.hrms_departments.find_one({'id': employee['department_id']}, {'_id': 0})
    employee['department_name'] = dept['name'] if dept else 'Unassigned'
    return {k: v for k, v in employee.items() if k != '_id'}


@router.put("/hrms/employees/{employee_id}")
async def update_employee(employee_id: str, data: dict, user: dict = Depends(get_current_user)):
    if user.get('role') not in ('admin', 'hr_admin'):
        raise HTTPException(status_code=403, detail="Admin or HR Admin required")
    emp = await db.hrms_employees.find_one({'id': employee_id})
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    updatable = [
        'name', 'email', 'phone', 'date_of_birth', 'gender', 'address',
        'department_id', 'designation', 'date_of_joining', 'employment_type',
        'basic_salary', 'hra', 'da', 'other_allowances',
        'pf_number', 'esi_number', 'pan_number', 'aadhar_number',
        'bank_name', 'bank_account_no', 'ifsc_code',
        'emergency_contact_name', 'emergency_contact_phone',
        'is_active', 'status', 'photo_url'
    ]
    update_fields = {}
    for field in updatable:
        if field in data:
            if field in ('basic_salary', 'hra', 'da', 'other_allowances'):
                update_fields[field] = float(data[field])
            else:
                update_fields[field] = data[field]
    
    if not update_fields:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    
    update_fields['updated_at'] = datetime.now(timezone.utc).isoformat()
    await db.hrms_employees.update_one({'id': employee_id}, {'$set': update_fields})
    await log_audit(user.get('id', ''), user.get('name', ''), 'update', 'employee', employee_id, f"Updated employee fields: {list(update_fields.keys())}")
    
    updated = await db.hrms_employees.find_one({'id': employee_id}, {'_id': 0})
    dept = await db.hrms_departments.find_one({'id': updated.get('department_id')}, {'_id': 0})
    updated['department_name'] = dept['name'] if dept else 'Unassigned'
    return updated


@router.delete("/hrms/employees/{employee_id}")
async def delete_employee(employee_id: str, user: dict = Depends(get_current_user)):
    if user.get('role') not in ('admin', 'hr_admin'):
        raise HTTPException(status_code=403, detail="Admin or HR Admin required")
    result = await db.hrms_employees.update_one(
        {'id': employee_id},
        {'$set': {'is_active': False, 'status': 'inactive', 'updated_at': datetime.now(timezone.utc).isoformat()}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Employee not found")
    await log_audit(user.get('id', ''), user.get('name', ''), 'delete', 'employee', employee_id, "Deactivated employee")
    return {"message": "Employee deactivated"}


@router.post("/hrms/employees/{employee_id}/photo")
async def upload_employee_photo(employee_id: str, file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    if user.get('role') not in ('admin', 'hr_admin'):
        raise HTTPException(status_code=403, detail="Admin or HR Admin required")
    emp = await db.hrms_employees.find_one({'id': employee_id})
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    content = await file.read()
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File must be under 2MB")
    encoded = base64.b64encode(content).decode('utf-8')
    content_type = file.content_type or 'image/png'
    data_uri = f"data:{content_type};base64,{encoded}"
    await db.hrms_employees.update_one(
        {'id': employee_id},
        {'$set': {'photo_url': data_uri, 'updated_at': datetime.now(timezone.utc).isoformat()}}
    )
    return {"message": "Photo uploaded", "photo_url": data_uri}


# ============ INCREMENT HISTORY ============

@router.post("/hrms/employees/{employee_id}/increment")
async def add_increment(employee_id: str, data: dict, user: dict = Depends(get_current_user)):
    if user.get('role') not in ('admin', 'hr_admin'):
        raise HTTPException(status_code=403, detail="Admin or HR Admin required")
    emp = await db.hrms_employees.find_one({'id': employee_id})
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    increment = {
        'id': str(uuid.uuid4()),
        'date': data.get('date', datetime.now(timezone.utc).strftime('%Y-%m-%d')),
        'previous_salary': emp.get('basic_salary', 0),
        'new_salary': float(data.get('new_salary', 0)),
        'increment_amount': float(data.get('new_salary', 0)) - emp.get('basic_salary', 0),
        'reason': data.get('reason', ''),
        'approved_by': user.get('name', ''),
        'created_at': datetime.now(timezone.utc).isoformat()
    }

    await db.hrms_employees.update_one(
        {'id': employee_id},
        {
            '$push': {'increment_history': increment},
            '$set': {
                'basic_salary': float(data.get('new_salary', 0)),
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
        }
    )
    return {"message": "Increment added", "increment": increment}


# ============ DASHBOARD STATS ============

@router.get("/hrms/dashboard/stats")
async def get_hrms_dashboard_stats(user: dict = Depends(get_current_user)):
    total_employees = await db.hrms_employees.count_documents({'is_active': True})
    total_inactive = await db.hrms_employees.count_documents({'is_active': False})
    total_departments = await db.hrms_departments.count_documents({})

    # Department-wise breakdown
    dept_breakdown = []
    async for dept in db.hrms_departments.find({}, {'_id': 0}).sort('name', 1):
        count = await db.hrms_employees.count_documents({'department_id': dept['id'], 'is_active': True})
        dept_breakdown.append({'name': dept['name'], 'count': count})

    # Recent employees (last 5 joined)
    recent = []
    async for emp in db.hrms_employees.find({'is_active': True}, {'_id': 0, 'name': 1, 'designation': 1, 'department_id': 1, 'date_of_joining': 1, 'photo_url': 1}).sort('date_of_joining', -1).limit(5):
        dept = await db.hrms_departments.find_one({'id': emp.get('department_id')}, {'_id': 0})
        emp['department_name'] = dept['name'] if dept else 'N/A'
        recent.append(emp)

    # Total payroll
    total_salary = 0
    async for emp in db.hrms_employees.find({'is_active': True}, {'_id': 0, 'basic_salary': 1, 'hra': 1, 'da': 1, 'other_allowances': 1}):
        total_salary += emp.get('basic_salary', 0) + emp.get('hra', 0) + emp.get('da', 0) + emp.get('other_allowances', 0)

    # Gender breakdown
    male = await db.hrms_employees.count_documents({'is_active': True, 'gender': 'male'})
    female = await db.hrms_employees.count_documents({'is_active': True, 'gender': 'female'})
    other_gender = total_employees - male - female

    return {
        'total_employees': total_employees,
        'total_inactive': total_inactive,
        'total_departments': total_departments,
        'department_breakdown': dept_breakdown,
        'recent_employees': recent,
        'total_monthly_payroll': total_salary,
        'gender_breakdown': {'male': male, 'female': female, 'other': other_gender},
    }


# ============ DASHBOARD PREFERENCE ============

@router.post("/auth/set-dashboard")
async def set_dashboard_preference(data: dict, user: dict = Depends(get_current_user)):
    dashboard = data.get('dashboard')
    if dashboard not in ('inventory', 'hrms'):
        raise HTTPException(status_code=400, detail="Invalid dashboard. Use 'inventory' or 'hrms'")
    await db.users.update_one(
        {'id': user['id']},
        {'$set': {'active_dashboard': dashboard}}
    )
    return {"message": f"Dashboard set to {dashboard}", "active_dashboard": dashboard}


@router.get("/auth/dashboard-preference")
async def get_dashboard_preference(user: dict = Depends(get_current_user)):
    return {"active_dashboard": user.get('active_dashboard', None)}
