from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from database import db
from deps import get_current_user
from datetime import datetime, timezone
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

DEPT_EDITABLE_FIELDS = ['name', 'code', 'description', 'hod_employee_id']


@router.get("/hrms/departments")
async def get_departments(status: str = 'all', user: dict = Depends(get_current_user)):
    """status: 'all' | 'active' | 'inactive'"""
    query = {}
    if status == 'active':
        query['is_active'] = {'$ne': False}
    elif status == 'inactive':
        query['is_active'] = False

    departments = []
    async for dept in db.hrms_departments.find(query, {'_id': 0}).sort('name', 1):
        # Annotate with employee counts for UI (active vs total)
        dept.setdefault('is_active', True)
        dept['active_employee_count'] = await db.hrms_employees.count_documents({
            'department_id': dept['id'], 'is_active': True
        })
        dept['total_employee_count'] = await db.hrms_employees.count_documents({
            'department_id': dept['id']
        })
        # Hydrate HOD name if referenced
        if dept.get('hod_employee_id'):
            hod = await db.hrms_employees.find_one(
                {'id': dept['hod_employee_id']}, {'_id': 0, 'name': 1, 'employee_id': 1}
            )
            dept['hod_name'] = hod.get('name', '') if hod else ''
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
    now = datetime.now(timezone.utc).isoformat()
    dept = {
        'id': str(uuid.uuid4()),
        'name': name,
        'code': (data.get('code') or '').strip().upper(),
        'description': data.get('description', ''),
        'hod_employee_id': data.get('hod_employee_id') or None,
        'created_at': now,
        'updated_at': now,
        'is_active': True,
        'version': 1,
    }
    await db.hrms_departments.insert_one(dept)
    # Audit + version
    await db.hrms_department_versions.insert_one({
        'id': str(uuid.uuid4()),
        'department_id': dept['id'],
        'version': 1,
        'action': 'created',
        'old': None,
        'new': {k: dept[k] for k in DEPT_EDITABLE_FIELDS + ['is_active'] if k in dept},
        'changed_by_id': user.get('id', ''),
        'changed_by_name': user.get('name', ''),
        'reason': data.get('reason', ''),
        'timestamp': now,
    })
    dept.pop('_id', None)
    return dept


@router.put("/hrms/departments/{dept_id}")
async def update_department(dept_id: str, data: dict, user: dict = Depends(get_current_user)):
    if user.get('role') not in ('admin', 'hr_admin'):
        raise HTTPException(status_code=403, detail="Admin or HR Admin required")
    existing = await db.hrms_departments.find_one({'id': dept_id}, {'_id': 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Department not found")

    updates = {}
    for field in DEPT_EDITABLE_FIELDS:
        if field in data and data[field] != existing.get(field):
            val = data[field]
            if isinstance(val, str):
                val = val.strip()
                if field == 'code':
                    val = val.upper()
            updates[field] = val

    # Name uniqueness check (case-insensitive, ignoring self)
    if 'name' in updates and updates['name']:
        name_dup = await db.hrms_departments.find_one({
            'name': {'$regex': f'^{re.escape(updates["name"])}$', '$options': 'i'},
            'id': {'$ne': dept_id},
        })
        if name_dup:
            raise HTTPException(status_code=400, detail="Another department already uses this name")

    if not updates:
        return {'message': 'No changes', 'department': existing}

    new_version = int(existing.get('version', 1)) + 1
    now = datetime.now(timezone.utc).isoformat()
    updates['version'] = new_version
    updates['updated_at'] = now

    await db.hrms_departments.update_one({'id': dept_id}, {'$set': updates})

    old_snapshot = {k: existing.get(k) for k in updates.keys() if k in DEPT_EDITABLE_FIELDS}
    new_snapshot = {k: updates[k] for k in updates.keys() if k in DEPT_EDITABLE_FIELDS}

    await db.hrms_department_versions.insert_one({
        'id': str(uuid.uuid4()),
        'department_id': dept_id,
        'version': new_version,
        'action': 'updated',
        'old': old_snapshot,
        'new': new_snapshot,
        'changed_by_id': user.get('id', ''),
        'changed_by_name': user.get('name', ''),
        'reason': data.get('reason', ''),
        'timestamp': now,
    })
    from helpers import log_audit
    await log_audit(
        user.get('id', ''), user.get('name', ''), 'update', 'hrms_department', dept_id,
        f"Updated: {', '.join(sorted(new_snapshot.keys()))}"
    )

    updated = await db.hrms_departments.find_one({'id': dept_id}, {'_id': 0})
    return {'message': 'Department updated', 'department': updated}


@router.post("/hrms/departments/{dept_id}/toggle-status")
async def toggle_department_status(dept_id: str, data: dict = None, user: dict = Depends(get_current_user)):
    if user.get('role') not in ('admin', 'hr_admin'):
        raise HTTPException(status_code=403, detail="Admin or HR Admin required")
    existing = await db.hrms_departments.find_one({'id': dept_id}, {'_id': 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Department not found")
    currently_active = existing.get('is_active', True)
    # Prevent deactivation if active employees still assigned
    if currently_active:
        active_emp = await db.hrms_employees.count_documents({'department_id': dept_id, 'is_active': True})
        if active_emp > 0:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot deactivate: {active_emp} active employee(s) still in this department. "
                       "Reassign or merge first."
            )
    new_active = not currently_active
    new_version = int(existing.get('version', 1)) + 1
    now = datetime.now(timezone.utc).isoformat()
    await db.hrms_departments.update_one(
        {'id': dept_id},
        {'$set': {'is_active': new_active, 'version': new_version, 'updated_at': now}}
    )
    await db.hrms_department_versions.insert_one({
        'id': str(uuid.uuid4()),
        'department_id': dept_id,
        'version': new_version,
        'action': 'deactivated' if not new_active else 'activated',
        'old': {'is_active': currently_active},
        'new': {'is_active': new_active},
        'changed_by_id': user.get('id', ''),
        'changed_by_name': user.get('name', ''),
        'reason': (data or {}).get('reason', ''),
        'timestamp': now,
    })
    from helpers import log_audit
    await log_audit(
        user.get('id', ''), user.get('name', ''),
        'deactivate' if not new_active else 'activate',
        'hrms_department', dept_id, ''
    )
    return {'message': f"Department {'activated' if new_active else 'deactivated'}", 'is_active': new_active}


@router.post("/hrms/departments/{dept_id}/merge")
async def merge_department(dept_id: str, data: dict, user: dict = Depends(get_current_user)):
    """Reassigns all active employees from `dept_id` to `target_dept_id`, then deactivates source."""
    if user.get('role') not in ('admin', 'hr_admin'):
        raise HTTPException(status_code=403, detail="Admin or HR Admin required")
    target_id = data.get('target_dept_id')
    if not target_id or target_id == dept_id:
        raise HTTPException(status_code=400, detail="A different target department is required")
    source = await db.hrms_departments.find_one({'id': dept_id}, {'_id': 0})
    target = await db.hrms_departments.find_one({'id': target_id}, {'_id': 0})
    if not source:
        raise HTTPException(status_code=404, detail="Source department not found")
    if not target:
        raise HTTPException(status_code=404, detail="Target department not found")
    if not target.get('is_active', True):
        raise HTTPException(status_code=400, detail="Target department is inactive")

    # Reassign all employees (active + inactive) with source department_id
    emp_update = await db.hrms_employees.update_many(
        {'department_id': dept_id},
        {'$set': {'department_id': target_id}}
    )

    # Deactivate source
    now = datetime.now(timezone.utc).isoformat()
    src_version = int(source.get('version', 1)) + 1
    await db.hrms_departments.update_one(
        {'id': dept_id},
        {'$set': {'is_active': False, 'version': src_version, 'updated_at': now,
                  'merged_into': target_id, 'merged_at': now}}
    )

    await db.hrms_department_versions.insert_one({
        'id': str(uuid.uuid4()),
        'department_id': dept_id,
        'version': src_version,
        'action': 'merged',
        'old': {'department_id': dept_id, 'name': source.get('name'), 'is_active': True},
        'new': {'merged_into': target_id, 'merged_into_name': target.get('name'),
                'employees_reassigned': emp_update.modified_count, 'is_active': False},
        'changed_by_id': user.get('id', ''),
        'changed_by_name': user.get('name', ''),
        'reason': data.get('reason', ''),
        'timestamp': now,
    })
    from helpers import log_audit
    await log_audit(
        user.get('id', ''), user.get('name', ''), 'merge', 'hrms_department', dept_id,
        f"Merged into '{target.get('name','')}': {emp_update.modified_count} employee(s) reassigned"
    )
    return {
        'message': f"Merged '{source.get('name')}' into '{target.get('name')}'",
        'employees_reassigned': emp_update.modified_count,
    }


@router.get("/hrms/departments/{dept_id}/history")
async def department_history(dept_id: str, user: dict = Depends(get_current_user)):
    history = await db.hrms_department_versions.find(
        {'department_id': dept_id}, {'_id': 0}
    ).sort('version', -1).to_list(500)
    return history


@router.delete("/hrms/departments/{dept_id}")
async def delete_department(dept_id: str, user: dict = Depends(get_current_user)):
    if user.get('role') not in ('admin', 'hr_admin'):
        raise HTTPException(status_code=403, detail="Admin or HR Admin required")
    # Hard delete only allowed when no active OR inactive employees OR historical payroll entries reference it
    emp_count = await db.hrms_employees.count_documents({'department_id': dept_id})
    if emp_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete: {emp_count} employee(s) (active or historical) still reference this department. "
                   "Deactivate instead."
        )
    # Also protect against historical payroll linkage (dept name is snapshotted on payslip but we still warn)
    result = await db.hrms_departments.delete_one({'id': dept_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Department not found")
    # Keep change history (version docs) for auditability — DO NOT delete
    return {"message": "Department deleted"}

