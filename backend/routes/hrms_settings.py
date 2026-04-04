from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from database import db
from deps import get_current_user
from datetime import datetime, timezone
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
