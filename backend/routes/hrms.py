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
import re

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


# Upload logs endpoint - must be before {employee_id} route to avoid path conflict
@router.get("/hrms/employees/upload-logs")
async def get_upload_logs(user: dict = Depends(get_current_user)):
    if user.get('role') not in ('admin', 'hr_admin'):
        raise HTTPException(status_code=403, detail="Admin or HR Admin required")
    logs = []
    async for log in db.hrms_upload_logs.find({}, {'_id': 0}).sort('created_at', -1).limit(20):
        logs.append(log)
    return logs


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


# ============ EMPLOYEE BULK UPLOAD ============

BULK_TEMPLATE_HEADERS = [
    'Employee_ID', 'Full_Name', 'Gender', 'Date_of_Birth', 'Phone', 'Email',
    'Address', 'Department', 'Designation', 'Date_of_Joining', 'Employment_Type',
    'Basic_Salary', 'HRA', 'Allowances', 'Bank_Account_Number', 'IFSC_Code',
    'PAN_Number', 'Aadhaar_Number', 'PF_Applicable', 'ESI_Applicable'
]


def _parse_date_ddmmyyyy(val):
    """Parse DD-MM-YYYY or DD/MM/YYYY to YYYY-MM-DD"""
    if not val:
        return ''
    s = str(val).strip()
    for fmt in ('%d-%m-%Y', '%d/%m/%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(s, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    return None


def _validate_pan(pan):
    if not pan:
        return True
    return bool(re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]$', str(pan).strip().upper()))


def _validate_aadhaar(aadhaar):
    if not aadhaar:
        return True
    cleaned = re.sub(r'\s', '', str(aadhaar).strip())
    return bool(re.match(r'^\d{12}$', cleaned))


def _capitalize_name(name):
    if not name:
        return ''
    return ' '.join(w.capitalize() for w in str(name).strip().split())


@router.get("/hrms/employees/bulk-upload/template")
async def download_bulk_template(user: dict = Depends(get_current_user)):
    if user.get('role') not in ('admin', 'hr_admin'):
        raise HTTPException(status_code=403, detail="Admin or HR Admin required")
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

    wb = Workbook()
    ws = wb.active
    ws.title = "Employee Upload"

    hf = Font(name='Arial', size=10, bold=True, color='FFFFFF')
    hfill = PatternFill(start_color='264785', end_color='264785', fill_type='solid')
    border = Border(
        left=Side(style='thin', color='CCCCCC'), right=Side(style='thin', color='CCCCCC'),
        top=Side(style='thin', color='CCCCCC'), bottom=Side(style='thin', color='CCCCCC')
    )

    # Title
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(BULK_TEMPLATE_HEADERS))
    ws['A1'] = 'Employee Bulk Upload Template'
    ws['A1'].font = Font(name='Arial', size=14, bold=True)
    ws['A1'].alignment = Alignment(horizontal='center')

    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(BULK_TEMPLATE_HEADERS))
    ws['A2'] = 'Fill in employee data below. Date format: DD-MM-YYYY. Required fields: Employee_ID, Full_Name, Date_of_Joining, Basic_Salary'
    ws['A2'].font = Font(name='Arial', size=8, color='666666')
    ws['A2'].alignment = Alignment(horizontal='center')

    # Headers
    for col, h in enumerate(BULK_TEMPLATE_HEADERS, 1):
        cell = ws.cell(row=4, column=col, value=h)
        cell.font = hf
        cell.fill = hfill
        cell.alignment = Alignment(horizontal='center')
        cell.border = border

    # Sample row
    sample = ['K3-EMP-001', 'Rahul Kumar', 'Male', '15-06-1990', '9876543210', 'rahul@example.com',
              'Itanagar, Arunachal Pradesh', 'Operations', 'Manager', '01-01-2024', 'Full-time',
              25000, 5000, 3000, '1234567890', 'SBIN0001234',
              'ABCDE1234F', '123456789012', 'Yes', 'Yes']
    for col, val in enumerate(sample, 1):
        cell = ws.cell(row=5, column=col, value=val)
        cell.font = Font(name='Arial', size=9, color='888888', italic=True)
        cell.border = border

    widths = [14, 20, 8, 14, 14, 22, 28, 16, 16, 14, 12, 12, 8, 10, 18, 14, 14, 14, 12, 12]
    for i, w in enumerate(widths):
        ws.column_dimensions[chr(65 + i) if i < 26 else 'A' + chr(65 + i - 26)].width = w

    # Instructions sheet
    instr = wb.create_sheet("Instructions")
    instructions = [
        ['Field', 'Required', 'Format / Notes'],
        ['Employee_ID', 'Yes', 'Unique ID for the employee (e.g., K3-EMP-001). No duplicates allowed.'],
        ['Full_Name', 'Yes', 'Full name. Will be auto-capitalized.'],
        ['Gender', 'No', 'Male / Female / Other'],
        ['Date_of_Birth', 'No', 'DD-MM-YYYY format'],
        ['Phone', 'No', 'Mobile number (10 digits)'],
        ['Email', 'No', 'Valid email address'],
        ['Address', 'No', 'Full address text'],
        ['Department', 'No', 'Department name (must exist in system or will use default)'],
        ['Designation', 'No', 'Job role / title'],
        ['Date_of_Joining', 'Yes', 'DD-MM-YYYY format'],
        ['Employment_Type', 'No', 'Full-time / Contract / Part-time / Intern'],
        ['Basic_Salary', 'Yes', 'Numeric value (monthly basic salary)'],
        ['HRA', 'No', 'Numeric value'],
        ['Allowances', 'No', 'Numeric value (other allowances)'],
        ['Bank_Account_Number', 'No', 'Bank account number'],
        ['IFSC_Code', 'No', 'Bank IFSC code'],
        ['PAN_Number', 'No', 'PAN in format: ABCDE1234F'],
        ['Aadhaar_Number', 'No', '12-digit Aadhaar number'],
        ['PF_Applicable', 'No', 'Yes / No'],
        ['ESI_Applicable', 'No', 'Yes / No'],
    ]
    for r, row in enumerate(instructions, 1):
        for c, val in enumerate(row, 1):
            cell = instr.cell(row=r, column=c, value=val)
            if r == 1:
                cell.font = Font(name='Arial', size=10, bold=True, color='FFFFFF')
                cell.fill = PatternFill(start_color='264785', end_color='264785', fill_type='solid')
            else:
                cell.font = Font(name='Arial', size=9)
    instr.column_dimensions['A'].width = 20
    instr.column_dimensions['B'].width = 10
    instr.column_dimensions['C'].width = 60

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return Response(content=buf.read(),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": 'attachment; filename="Employee_Upload_Template.xlsx"'})


@router.post("/hrms/employees/bulk-upload/validate")
async def validate_bulk_upload(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    if user.get('role') not in ('admin', 'hr_admin'):
        raise HTTPException(status_code=403, detail="Admin or HR Admin required")
    if not file.filename.endswith('.xlsx'):
        raise HTTPException(status_code=400, detail="Only .xlsx files are accepted")

    from openpyxl import load_workbook

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")

    try:
        wb = load_workbook(BytesIO(content), data_only=True)
        ws = wb.active
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Excel file")

    # Find header row
    header_row = None
    for row_idx in range(1, min(10, ws.max_row + 1)):
        vals = [str(ws.cell(row=row_idx, column=c).value or '').strip() for c in range(1, ws.max_column + 1)]
        if 'Employee_ID' in vals and 'Full_Name' in vals:
            header_row = row_idx
            break
    if not header_row:
        raise HTTPException(status_code=400, detail="Could not find headers. Ensure 'Employee_ID' and 'Full_Name' columns exist.")

    headers = [str(ws.cell(row=header_row, column=c).value or '').strip() for c in range(1, ws.max_column + 1)]
    col_map = {}
    for i, h in enumerate(headers):
        for tmpl in BULK_TEMPLATE_HEADERS:
            if h.lower().replace(' ', '_') == tmpl.lower().replace(' ', '_') or h.lower() == tmpl.lower():
                col_map[tmpl] = i
                break

    # Load departments for name matching
    depts = {}
    async for dept in db.hrms_departments.find({}, {'_id': 0}):
        depts[dept['name'].lower().strip()] = dept['id']

    # Load existing employee IDs for duplicate check
    existing_emp_ids = set()
    async for emp in db.hrms_employees.find({}, {'_id': 0, 'employee_id': 1}):
        existing_emp_ids.add(emp.get('employee_id', '').strip().upper())

    validated_rows = []
    errors = []
    seen_ids = set()

    for row_idx in range(header_row + 1, ws.max_row + 1):
        row_vals = [ws.cell(row=row_idx, column=c + 1).value for c in range(len(headers))]
        # Skip empty rows
        if all(v is None or str(v).strip() == '' for v in row_vals):
            continue

        def get_val(col_name):
            idx = col_map.get(col_name)
            if idx is None:
                return ''
            val = row_vals[idx]
            return str(val).strip() if val is not None else ''

        row_num = row_idx
        row_errors = []

        emp_id = get_val('Employee_ID').strip()
        full_name = get_val('Full_Name').strip()
        doj_raw = get_val('Date_of_Joining')
        salary_raw = get_val('Basic_Salary')

        # Required field checks
        if not emp_id:
            row_errors.append('Employee_ID is required')
        if not full_name:
            row_errors.append('Full_Name is required')
        if not doj_raw:
            row_errors.append('Date_of_Joining is required')
        if not salary_raw:
            row_errors.append('Basic_Salary is required')

        # Duplicate ID in file
        if emp_id:
            if emp_id.upper() in seen_ids:
                row_errors.append(f'Duplicate Employee_ID in file: {emp_id}')
            seen_ids.add(emp_id.upper())

        # Check if exists in DB
        is_existing = emp_id.upper() in existing_emp_ids if emp_id else False

        # Parse dates
        doj = _parse_date_ddmmyyyy(doj_raw) if doj_raw else ''
        if doj_raw and doj is None:
            row_errors.append(f'Invalid Date_of_Joining format: {doj_raw} (use DD-MM-YYYY)')
            doj = ''

        dob_raw = get_val('Date_of_Birth')
        dob = _parse_date_ddmmyyyy(dob_raw) if dob_raw else ''
        if dob_raw and dob is None:
            row_errors.append(f'Invalid Date_of_Birth format: {dob_raw} (use DD-MM-YYYY)')
            dob = ''

        # Parse salary
        try:
            basic_salary = float(salary_raw) if salary_raw else 0
        except (ValueError, TypeError):
            row_errors.append(f'Invalid Basic_Salary: {salary_raw}')
            basic_salary = 0

        try:
            hra = float(get_val('HRA')) if get_val('HRA') else 0
        except (ValueError, TypeError):
            row_errors.append('Invalid HRA value')
            hra = 0

        try:
            allowances = float(get_val('Allowances')) if get_val('Allowances') else 0
        except (ValueError, TypeError):
            row_errors.append('Invalid Allowances value')
            allowances = 0

        # Validate PAN
        pan = get_val('PAN_Number').upper()
        if pan and not _validate_pan(pan):
            row_errors.append(f'Invalid PAN format: {pan} (expected: ABCDE1234F)')

        # Validate Aadhaar
        aadhaar = re.sub(r'\s', '', get_val('Aadhaar_Number'))
        if aadhaar and not _validate_aadhaar(aadhaar):
            row_errors.append(f'Invalid Aadhaar: {aadhaar} (expected 12 digits)')

        # Resolve department
        dept_name = get_val('Department').strip()
        dept_id = ''
        if dept_name:
            dept_id = depts.get(dept_name.lower(), '')
            if not dept_id:
                row_errors.append(f'Department not found: "{dept_name}". Create it first or leave blank.')

        # Employment type
        emp_type_raw = get_val('Employment_Type').strip().lower().replace('-', '_').replace(' ', '_')
        emp_type_map = {'full_time': 'full_time', 'fulltime': 'full_time', 'contract': 'contract',
                        'part_time': 'part_time', 'parttime': 'part_time', 'intern': 'intern'}
        employment_type = emp_type_map.get(emp_type_raw, 'full_time')

        gender_raw = get_val('Gender').strip().lower()
        gender = gender_raw if gender_raw in ('male', 'female', 'other') else ''

        pf_applicable = get_val('PF_Applicable').strip().lower() in ('yes', 'y', 'true', '1')
        esi_applicable = get_val('ESI_Applicable').strip().lower() in ('yes', 'y', 'true', '1')

        row_data = {
            'row_num': row_num,
            'employee_id': emp_id,
            'name': _capitalize_name(full_name),
            'gender': gender,
            'date_of_birth': dob,
            'phone': get_val('Phone'),
            'email': get_val('Email').strip().lower(),
            'address': get_val('Address'),
            'department': dept_name,
            'department_id': dept_id,
            'designation': get_val('Designation'),
            'date_of_joining': doj,
            'employment_type': employment_type,
            'basic_salary': basic_salary,
            'hra': hra,
            'other_allowances': allowances,
            'bank_account_no': get_val('Bank_Account_Number'),
            'ifsc_code': get_val('IFSC_Code').upper(),
            'pan_number': pan,
            'aadhar_number': aadhaar,
            'pf_applicable': pf_applicable,
            'esi_applicable': esi_applicable,
            'is_existing': is_existing,
            'errors': row_errors,
            'has_errors': len(row_errors) > 0,
        }
        validated_rows.append(row_data)
        if row_errors:
            errors.append({'row': row_num, 'employee_id': emp_id, 'name': full_name, 'errors': row_errors})

    total = len(validated_rows)
    valid_count = sum(1 for r in validated_rows if not r['has_errors'])
    error_count = sum(1 for r in validated_rows if r['has_errors'])
    new_count = sum(1 for r in validated_rows if not r['has_errors'] and not r['is_existing'])
    update_count = sum(1 for r in validated_rows if not r['has_errors'] and r['is_existing'])

    return {
        'total_rows': total,
        'valid_count': valid_count,
        'error_count': error_count,
        'new_count': new_count,
        'update_count': update_count,
        'rows': validated_rows,
        'errors': errors,
        'departments_available': list(depts.keys()),
    }


@router.post("/hrms/employees/bulk-upload/confirm")
async def confirm_bulk_upload(data: dict, user: dict = Depends(get_current_user)):
    if user.get('role') not in ('admin', 'hr_admin'):
        raise HTTPException(status_code=403, detail="Admin or HR Admin required")

    rows = data.get('rows', [])
    mode = data.get('mode', 'skip')  # 'skip' or 'overwrite'

    if not rows:
        raise HTTPException(status_code=400, detail="No rows to import")

    created = 0
    updated = 0
    skipped = 0

    for row in rows:
        if row.get('has_errors'):
            skipped += 1
            continue

        emp_id = row.get('employee_id', '').strip()
        if not emp_id:
            skipped += 1
            continue

        existing = await db.hrms_employees.find_one({'employee_id': emp_id})

        if existing:
            if mode == 'skip':
                skipped += 1
                continue
            # Overwrite mode: update existing
            update_fields = {
                'name': row.get('name', existing.get('name', '')),
                'gender': row.get('gender', '') or existing.get('gender', ''),
                'date_of_birth': row.get('date_of_birth', '') or existing.get('date_of_birth', ''),
                'phone': row.get('phone', '') or existing.get('phone', ''),
                'email': row.get('email', '') or existing.get('email', ''),
                'address': row.get('address', '') or existing.get('address', ''),
                'designation': row.get('designation', '') or existing.get('designation', ''),
                'date_of_joining': row.get('date_of_joining', '') or existing.get('date_of_joining', ''),
                'employment_type': row.get('employment_type', 'full_time'),
                'basic_salary': float(row.get('basic_salary', 0)),
                'hra': float(row.get('hra', 0)),
                'other_allowances': float(row.get('other_allowances', 0)),
                'bank_account_no': row.get('bank_account_no', '') or existing.get('bank_account_no', ''),
                'ifsc_code': row.get('ifsc_code', '') or existing.get('ifsc_code', ''),
                'pan_number': row.get('pan_number', '') or existing.get('pan_number', ''),
                'aadhar_number': row.get('aadhar_number', '') or existing.get('aadhar_number', ''),
                'updated_at': datetime.now(timezone.utc).isoformat(),
            }
            if row.get('department_id'):
                update_fields['department_id'] = row['department_id']
            await db.hrms_employees.update_one({'employee_id': emp_id}, {'$set': update_fields})
            updated += 1
        else:
            # Create new
            employee = {
                'id': str(uuid.uuid4()),
                'employee_id': emp_id,
                'name': row.get('name', ''),
                'email': row.get('email', ''),
                'phone': row.get('phone', ''),
                'date_of_birth': row.get('date_of_birth', ''),
                'gender': row.get('gender', ''),
                'address': row.get('address', ''),
                'department_id': row.get('department_id', ''),
                'designation': row.get('designation', ''),
                'date_of_joining': row.get('date_of_joining', ''),
                'employment_type': row.get('employment_type', 'full_time'),
                'basic_salary': float(row.get('basic_salary', 0)),
                'hra': float(row.get('hra', 0)),
                'da': 0,
                'other_allowances': float(row.get('other_allowances', 0)),
                'pf_number': '',
                'esi_number': '',
                'pan_number': row.get('pan_number', ''),
                'aadhar_number': row.get('aadhar_number', ''),
                'bank_name': '',
                'bank_account_no': row.get('bank_account_no', ''),
                'ifsc_code': row.get('ifsc_code', ''),
                'photo_url': '',
                'emergency_contact_name': '',
                'emergency_contact_phone': '',
                'is_active': True,
                'status': 'active',
                'increment_history': [],
                'created_by': user.get('id', ''),
                'created_at': datetime.now(timezone.utc).isoformat(),
                'updated_at': datetime.now(timezone.utc).isoformat(),
            }
            await db.hrms_employees.insert_one(employee)
            created += 1

    # Log upload
    log = {
        'id': str(uuid.uuid4()),
        'uploaded_by': user.get('name', ''),
        'uploaded_by_id': user.get('id', ''),
        'mode': mode,
        'total_rows': len(rows),
        'created': created,
        'updated': updated,
        'skipped': skipped,
        'created_at': datetime.now(timezone.utc).isoformat(),
    }
    await db.hrms_upload_logs.insert_one(log)
    await log_audit(user.get('id', ''), user.get('name', ''), 'bulk_upload', 'employee', log['id'],
                    f"Bulk upload: {created} created, {updated} updated, {skipped} skipped")

    return {
        "message": f"Import complete: {created} created, {updated} updated, {skipped} skipped",
        "created": created,
        "updated": updated,
        "skipped": skipped,
    }


@router.post("/hrms/employees/bulk-upload/error-report")
async def download_error_report(data: dict, user: dict = Depends(get_current_user)):
    """Generate downloadable Excel with error details"""
    if user.get('role') not in ('admin', 'hr_admin'):
        raise HTTPException(status_code=403, detail="Admin or HR Admin required")
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

    errors = data.get('errors', [])
    wb = Workbook()
    ws = wb.active
    ws.title = "Error Report"

    hf = Font(name='Arial', size=10, bold=True, color='FFFFFF')
    ef = Font(name='Arial', size=9, color='CC0000')
    nf = Font(name='Arial', size=9)
    hfill = PatternFill(start_color='CC3333', end_color='CC3333', fill_type='solid')
    border = Border(left=Side(style='thin', color='CCCCCC'), right=Side(style='thin', color='CCCCCC'),
                    top=Side(style='thin', color='CCCCCC'), bottom=Side(style='thin', color='CCCCCC'))

    ws.merge_cells('A1:D1')
    ws['A1'] = 'Employee Bulk Upload - Error Report'
    ws['A1'].font = Font(name='Arial', size=14, bold=True, color='CC0000')
    ws['A1'].alignment = Alignment(horizontal='center')

    headers = ['Row #', 'Employee ID', 'Name', 'Errors']
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=3, column=col, value=h)
        cell.font = hf
        cell.fill = hfill
        cell.border = border

    for i, err in enumerate(errors):
        row = i + 4
        ws.cell(row=row, column=1, value=err.get('row', '')).font = nf
        ws.cell(row=row, column=2, value=err.get('employee_id', '')).font = nf
        ws.cell(row=row, column=3, value=err.get('name', '')).font = nf
        ws.cell(row=row, column=4, value='; '.join(err.get('errors', []))).font = ef
        for c in range(1, 5):
            ws.cell(row=row, column=c).border = border

    ws.column_dimensions['A'].width = 8
    ws.column_dimensions['B'].width = 16
    ws.column_dimensions['C'].width = 24
    ws.column_dimensions['D'].width = 60

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return Response(content=buf.read(),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": 'attachment; filename="Upload_Error_Report.xlsx"'})


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
