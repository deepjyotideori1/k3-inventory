from fastapi import APIRouter, Depends
from database import db
from deps import get_current_user, require_hrms_access

router = APIRouter()


# ============ DASHBOARD STATS ============

@router.get("/hrms/dashboard/stats")
async def get_hrms_dashboard_stats(user: dict = Depends(require_hrms_access)):
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
    from fastapi import HTTPException
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
