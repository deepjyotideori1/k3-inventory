from fastapi import APIRouter, HTTPException, Depends
from database import db
from deps import require_hrms_admin
from helpers import hash_password, log_audit
from datetime import datetime, timezone
import uuid

router = APIRouter()


# ============ HRMS USER MANAGEMENT ============

@router.get("/hrms/users")
async def list_hrms_users(user: dict = Depends(require_hrms_admin)):
    users = []
    async for u in db.users.find(
        {'role': {'$in': ['hr_admin', 'hrms_employee']}},
        {'_id': 0}
    ).sort('created_at', -1):
        linked_name = ''
        linked_code = ''
        if u.get('linked_employee_id'):
            emp = await db.hrms_employees.find_one(
                {'id': u['linked_employee_id']},
                {'_id': 0, 'name': 1, 'employee_id': 1}
            )
            if emp:
                linked_name = emp.get('name', '')
                linked_code = emp.get('employee_id', '')
        users.append({
            'id': u['id'],
            'email': u['email'],
            'name': u['name'],
            'role': u['role'],
            'linked_employee_id': u.get('linked_employee_id', ''),
            'linked_employee_name': linked_name,
            'linked_employee_code': linked_code,
            'visible_password': u.get('visible_password', ''),
            'is_active': u.get('is_active', True),
            'created_at': u.get('created_at', ''),
        })
    return users


@router.post("/hrms/users")
async def create_hrms_user(data: dict, user: dict = Depends(require_hrms_admin)):
    email = data.get('email', '').strip().lower()
    password = data.get('password', '').strip()
    name = data.get('name', '').strip()
    role = data.get('role', '').strip()
    linked_employee_id = data.get('linked_employee_id', '').strip()

    if not all([email, password, name, role]):
        raise HTTPException(status_code=400, detail="Email, password, name, and role are required")
    if role not in ('hr_admin', 'hrms_employee'):
        raise HTTPException(status_code=400, detail="Role must be 'hr_admin' or 'hrms_employee'")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    existing = await db.users.find_one({'email': email})
    if existing:
        raise HTTPException(status_code=400, detail=f"User with email {email} already exists")

    new_user = {
        'id': str(uuid.uuid4()),
        'email': email,
        'password': hash_password(password),
        'visible_password': password,
        'name': name,
        'role': role,
        'warehouse_id': None,
        'allowed_dashboards': ['hrms'],
        'linked_employee_id': linked_employee_id,
        'is_active': True,
        'created_at': datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(new_user)
    await log_audit(
        user.get('id', ''), user.get('name', ''),
        'create', 'hrms_user', new_user['id'],
        f"Created HRMS user: {name} ({email}) as {role}"
    )
    return {'message': f'User {name} created successfully', 'id': new_user['id']}


@router.put("/hrms/users/{user_id}")
async def update_hrms_user(user_id: str, data: dict, user: dict = Depends(require_hrms_admin)):
    target = await db.users.find_one({'id': user_id, 'role': {'$in': ['hr_admin', 'hrms_employee']}})
    if not target:
        raise HTTPException(status_code=404, detail="HRMS user not found")

    update_fields = {}
    if 'name' in data and data['name'].strip():
        update_fields['name'] = data['name'].strip()
    if 'role' in data and data['role'] in ('hr_admin', 'hrms_employee'):
        update_fields['role'] = data['role']
    if 'email' in data and data['email'].strip():
        new_email = data['email'].strip().lower()
        if new_email != target['email']:
            existing = await db.users.find_one({'email': new_email})
            if existing:
                raise HTTPException(status_code=400, detail=f"Email {new_email} already in use")
            update_fields['email'] = new_email
    if 'linked_employee_id' in data:
        update_fields['linked_employee_id'] = data['linked_employee_id']

    if not update_fields:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    await db.users.update_one({'id': user_id}, {'$set': update_fields})
    await log_audit(
        user.get('id', ''), user.get('name', ''),
        'update', 'hrms_user', user_id,
        f"Updated HRMS user: {update_fields}"
    )
    return {'message': f"User {target.get('name', '')} updated"}


@router.post("/hrms/users/{user_id}/reset-password")
async def reset_hrms_user_password(user_id: str, data: dict, user: dict = Depends(require_hrms_admin)):
    target = await db.users.find_one({'id': user_id, 'role': {'$in': ['hr_admin', 'hrms_employee']}})
    if not target:
        raise HTTPException(status_code=404, detail="HRMS user not found")

    password = data.get('password', '').strip()
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    await db.users.update_one(
        {'id': user_id},
        {'$set': {'password': hash_password(password), 'visible_password': password}}
    )
    await log_audit(
        user.get('id', ''), user.get('name', ''),
        'update', 'hrms_user', user_id,
        f"Reset password for: {target.get('name', '')}"
    )
    return {'message': f"Password reset for {target.get('name', '')}"}


@router.delete("/hrms/users/{user_id}")
async def delete_hrms_user(user_id: str, user: dict = Depends(require_hrms_admin)):
    if user_id == user.get('id'):
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")

    target = await db.users.find_one({'id': user_id, 'role': {'$in': ['hr_admin', 'hrms_employee']}})
    if not target:
        raise HTTPException(status_code=404, detail="HRMS user not found")

    await db.users.update_one({'id': user_id}, {'$set': {'is_active': False}})
    await log_audit(
        user.get('id', ''), user.get('name', ''),
        'delete', 'hrms_user', user_id,
        f"Deactivated HRMS user: {target.get('name', '')}"
    )
    return {'message': f"User {target.get('name', '')} deactivated"}
