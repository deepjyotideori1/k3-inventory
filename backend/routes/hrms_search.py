from fastapi import APIRouter, Depends
from database import db
from deps import get_current_user

router = APIRouter()


# ============ HRMS SMART SEARCH ============

@router.get("/hrms/search")
async def hrms_smart_search(q: str = '', user: dict = Depends(get_current_user)):
    if not q or len(q.strip()) < 1:
        return {'results': [], 'total': 0, 'query': q}

    query = q.strip()
    rgx = {'$regex': query, '$options': 'i'}
    results = []

    # 1. Search Employees
    emp_query = {'$or': [
        {'name': rgx}, {'employee_id': rgx}, {'email': rgx},
        {'phone': rgx}, {'designation': rgx}, {'pan_number': rgx},
        {'aadhar_number': rgx},
    ]}
    async for emp in db.hrms_employees.find(emp_query, {'_id': 0}).limit(15):
        dept = await db.hrms_departments.find_one({'id': emp.get('department_id')}, {'_id': 0, 'name': 1})
        results.append({
            'module': 'Employees',
            'id': emp['id'],
            'title': emp.get('name', ''),
            'subtitle': f"{emp.get('employee_id', '')} | {emp.get('designation', '')}",
            'meta': dept['name'] if dept else '',
            'status': 'Active' if emp.get('is_active') else 'Inactive',
            'link': "/hrms/employees",
        })

    # 2. Search Departments
    dept_query = {'name': rgx}
    async for dept in db.hrms_departments.find(dept_query, {'_id': 0}).limit(10):
        emp_count = await db.hrms_employees.count_documents({'department_id': dept['id'], 'is_active': True})
        results.append({
            'module': 'Departments',
            'id': dept['id'],
            'title': dept.get('name', ''),
            'subtitle': f"Head: {dept.get('head_name', 'N/A')}",
            'meta': f"{emp_count} employees",
            'link': "/hrms/departments",
        })

    # 3. Search Payroll (by employee name or month)
    matching_emp_ids = []
    async for emp in db.hrms_employees.find({'name': rgx}, {'_id': 0, 'id': 1, 'name': 1, 'employee_id': 1}):
        matching_emp_ids.append(emp)

    payroll_query_parts = [{'month': rgx}, {'status': rgx}]
    if matching_emp_ids:
        payroll_query_parts.append({'employee_id': {'$in': [e['id'] for e in matching_emp_ids]}})
    async for pay in db.hrms_payroll.find({'$or': payroll_query_parts}, {'_id': 0}).sort('month', -1).limit(10):
        emp = await db.hrms_employees.find_one({'id': pay.get('employee_id')}, {'_id': 0, 'name': 1, 'employee_id': 1})
        emp_name = emp['name'] if emp else 'Unknown'
        emp_code = emp.get('employee_id', '') if emp else ''
        results.append({
            'module': 'Payroll',
            'id': pay.get('id', ''),
            'title': f"{emp_name} ({emp_code})",
            'subtitle': f"Month: {pay.get('month', '')} | Net: Rs.{pay.get('net_salary', 0):,.0f}",
            'meta': pay.get('status', '').capitalize(),
            'link': "/hrms/payroll",
        })

    # 4. Search Hiring (candidates)
    hire_query = {'$or': [{'candidate_name': rgx}, {'position': rgx}, {'status': rgx}, {'email': rgx}]}
    async for hire in db.hrms_hiring.find(hire_query, {'_id': 0}).sort('applied_date', -1).limit(10):
        results.append({
            'module': 'Hiring',
            'id': hire.get('id', ''),
            'title': hire.get('candidate_name', ''),
            'subtitle': f"Position: {hire.get('position', '')}",
            'meta': hire.get('status', '').replace('_', ' ').capitalize(),
            'link': "/hrms/hiring",
        })

    # 5. Search Performance (reviews by employee name)
    if matching_emp_ids:
        async for review in db.hrms_performance.find(
            {'employee_id': {'$in': [e['id'] for e in matching_emp_ids]}}, {'_id': 0}
        ).sort('review_date', -1).limit(8):
            emp = await db.hrms_employees.find_one({'id': review.get('employee_id')}, {'_id': 0, 'name': 1, 'employee_id': 1})
            emp_name = emp['name'] if emp else 'Unknown'
            results.append({
                'module': 'Performance',
                'id': review.get('id', ''),
                'title': emp_name,
                'subtitle': f"Rating: {review.get('overall_rating', 'N/A')} | Period: {review.get('review_period', '')}",
                'meta': review.get('status', '').capitalize(),
                'link': "/hrms/performance",
            })

    # Group by module for counts
    module_counts = {}
    for r in results:
        module_counts[r['module']] = module_counts.get(r['module'], 0) + 1

    return {
        'results': results,
        'total': len(results),
        'query': query,
        'module_counts': module_counts,
    }
