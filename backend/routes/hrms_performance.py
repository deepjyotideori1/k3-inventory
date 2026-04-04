from fastapi import APIRouter, HTTPException, Depends
from database import db
from deps import get_current_user
from helpers import log_audit
from datetime import datetime, timezone
from typing import Optional
import uuid

router = APIRouter()


# ============ KPI TEMPLATES ============

@router.get("/hrms/kpis")
async def get_kpis(department_id: Optional[str] = None, user: dict = Depends(get_current_user)):
    query = {}
    if department_id and department_id != 'all':
        query['$or'] = [{'department_id': department_id}, {'department_id': 'all'}]
    kpis = []
    async for kpi in db.hrms_kpis.find(query, {'_id': 0}).sort('name', 1):
        kpis.append(kpi)
    return kpis


@router.post("/hrms/kpis")
async def create_kpi(data: dict, user: dict = Depends(get_current_user)):
    if user.get('role') not in ('admin', 'hr_admin'):
        raise HTTPException(status_code=403, detail="Admin or HR Admin required")
    name = data.get('name', '').strip()
    if not name:
        raise HTTPException(status_code=400, detail="KPI name is required")
    kpi = {
        'id': str(uuid.uuid4()),
        'name': name,
        'description': data.get('description', ''),
        'department_id': data.get('department_id', 'all'),
        'max_rating': int(data.get('max_rating', 5)),
        'weightage': float(data.get('weightage', 1.0)),
        'created_at': datetime.now(timezone.utc).isoformat(),
    }
    await db.hrms_kpis.insert_one(kpi)
    return {k: v for k, v in kpi.items() if k != '_id'}


@router.put("/hrms/kpis/{kpi_id}")
async def update_kpi(kpi_id: str, data: dict, user: dict = Depends(get_current_user)):
    if user.get('role') not in ('admin', 'hr_admin'):
        raise HTTPException(status_code=403, detail="Admin or HR Admin required")
    allowed = ['name', 'description', 'department_id', 'max_rating', 'weightage']
    update = {k: v for k, v in data.items() if k in allowed}
    if 'max_rating' in update:
        update['max_rating'] = int(update['max_rating'])
    if 'weightage' in update:
        update['weightage'] = float(update['weightage'])
    result = await db.hrms_kpis.update_one({'id': kpi_id}, {'$set': update})
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="KPI not found")
    return {"message": "KPI updated"}


@router.delete("/hrms/kpis/{kpi_id}")
async def delete_kpi(kpi_id: str, user: dict = Depends(get_current_user)):
    if user.get('role') not in ('admin', 'hr_admin'):
        raise HTTPException(status_code=403, detail="Admin or HR Admin required")
    result = await db.hrms_kpis.delete_one({'id': kpi_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="KPI not found")
    return {"message": "KPI deleted"}


# ============ APPRAISAL CYCLES ============

@router.get("/hrms/appraisals/cycles")
async def get_appraisal_cycles(user: dict = Depends(get_current_user)):
    cycles = []
    async for c in db.hrms_appraisal_cycles.find({}, {'_id': 0}).sort('start_date', -1):
        c['review_count'] = await db.hrms_reviews.count_documents({'cycle_id': c['id']})
        cycles.append(c)
    return cycles


@router.post("/hrms/appraisals/cycles")
async def create_appraisal_cycle(data: dict, user: dict = Depends(get_current_user)):
    if user.get('role') not in ('admin', 'hr_admin'):
        raise HTTPException(status_code=403, detail="Admin or HR Admin required")
    required = ['name', 'start_date', 'end_date']
    for f in required:
        if not data.get(f):
            raise HTTPException(status_code=400, detail=f"{f} is required")
    cycle = {
        'id': str(uuid.uuid4()),
        'name': data['name'],
        'start_date': data['start_date'],
        'end_date': data['end_date'],
        'status': data.get('status', 'active'),
        'description': data.get('description', ''),
        'created_by': user.get('name', ''),
        'created_at': datetime.now(timezone.utc).isoformat(),
    }
    await db.hrms_appraisal_cycles.insert_one(cycle)
    return {k: v for k, v in cycle.items() if k != '_id'}


@router.put("/hrms/appraisals/cycles/{cycle_id}")
async def update_appraisal_cycle(cycle_id: str, data: dict, user: dict = Depends(get_current_user)):
    if user.get('role') not in ('admin', 'hr_admin'):
        raise HTTPException(status_code=403, detail="Admin or HR Admin required")
    allowed = ['name', 'start_date', 'end_date', 'status', 'description']
    update = {k: v for k, v in data.items() if k in allowed}
    result = await db.hrms_appraisal_cycles.update_one({'id': cycle_id}, {'$set': update})
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Cycle not found")
    return {"message": "Cycle updated"}


@router.delete("/hrms/appraisals/cycles/{cycle_id}")
async def delete_appraisal_cycle(cycle_id: str, user: dict = Depends(get_current_user)):
    if user.get('role') not in ('admin', 'hr_admin'):
        raise HTTPException(status_code=403, detail="Admin or HR Admin required")
    reviews = await db.hrms_reviews.count_documents({'cycle_id': cycle_id})
    if reviews > 0:
        raise HTTPException(status_code=400, detail=f"Cannot delete: {reviews} reviews exist for this cycle")
    result = await db.hrms_appraisal_cycles.delete_one({'id': cycle_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Cycle not found")
    return {"message": "Cycle deleted"}


# ============ PERFORMANCE REVIEWS ============

@router.get("/hrms/reviews")
async def get_reviews(
    cycle_id: Optional[str] = None,
    employee_id: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    query = {}
    if cycle_id:
        query['cycle_id'] = cycle_id
    if employee_id:
        query['employee_id'] = employee_id
    reviews = []
    async for r in db.hrms_reviews.find(query, {'_id': 0}).sort('created_at', -1):
        emp = await db.hrms_employees.find_one({'id': r['employee_id']}, {'_id': 0, 'name': 1, 'employee_id': 1, 'designation': 1, 'department_id': 1})
        if emp:
            r['employee_name'] = emp.get('name', '')
            r['employee_code'] = emp.get('employee_id', '')
            r['designation'] = emp.get('designation', '')
            dept = await db.hrms_departments.find_one({'id': emp.get('department_id')}, {'_id': 0, 'name': 1})
            r['department'] = dept['name'] if dept else 'N/A'
        reviews.append(r)
    return reviews


@router.post("/hrms/reviews")
async def create_review(data: dict, user: dict = Depends(get_current_user)):
    if user.get('role') not in ('admin', 'hr_admin'):
        raise HTTPException(status_code=403, detail="Admin or HR Admin required")
    required = ['cycle_id', 'employee_id']
    for f in required:
        if not data.get(f):
            raise HTTPException(status_code=400, detail=f"{f} is required")

    existing = await db.hrms_reviews.find_one({'cycle_id': data['cycle_id'], 'employee_id': data['employee_id']})
    if existing:
        raise HTTPException(status_code=400, detail="Review already exists for this employee in this cycle")

    ratings = data.get('ratings', [])
    total_weighted = 0
    total_weight = 0
    for r in ratings:
        w = float(r.get('weightage', 1))
        total_weighted += float(r.get('rating', 0)) * w
        total_weight += w
    overall = round(total_weighted / total_weight, 2) if total_weight > 0 else 0

    review = {
        'id': str(uuid.uuid4()),
        'cycle_id': data['cycle_id'],
        'employee_id': data['employee_id'],
        'ratings': ratings,
        'overall_rating': overall,
        'self_rating': float(data.get('self_rating', 0)),
        'manager_comments': data.get('manager_comments', ''),
        'employee_comments': data.get('employee_comments', ''),
        'goals': data.get('goals', ''),
        'status': data.get('status', 'draft'),
        'reviewed_by': user.get('name', ''),
        'created_at': datetime.now(timezone.utc).isoformat(),
        'updated_at': datetime.now(timezone.utc).isoformat(),
    }
    await db.hrms_reviews.insert_one(review)
    await log_audit(user.get('id', ''), user.get('name', ''), 'create', 'performance_review', review['id'], f"Review for employee {data['employee_id']}")
    return {k: v for k, v in review.items() if k != '_id'}


@router.put("/hrms/reviews/{review_id}")
async def update_review(review_id: str, data: dict, user: dict = Depends(get_current_user)):
    if user.get('role') not in ('admin', 'hr_admin'):
        raise HTTPException(status_code=403, detail="Admin or HR Admin required")
    allowed = ['ratings', 'self_rating', 'manager_comments', 'employee_comments', 'goals', 'status']
    update = {k: v for k, v in data.items() if k in allowed}

    if 'ratings' in update:
        total_weighted = 0
        total_weight = 0
        for r in update['ratings']:
            w = float(r.get('weightage', 1))
            total_weighted += float(r.get('rating', 0)) * w
            total_weight += w
        update['overall_rating'] = round(total_weighted / total_weight, 2) if total_weight > 0 else 0
    if 'self_rating' in update:
        update['self_rating'] = float(update['self_rating'])

    update['updated_at'] = datetime.now(timezone.utc).isoformat()
    result = await db.hrms_reviews.update_one({'id': review_id}, {'$set': update})
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Review not found")
    return {"message": "Review updated"}


@router.delete("/hrms/reviews/{review_id}")
async def delete_review(review_id: str, user: dict = Depends(get_current_user)):
    if user.get('role') not in ('admin', 'hr_admin'):
        raise HTTPException(status_code=403, detail="Admin or HR Admin required")
    result = await db.hrms_reviews.delete_one({'id': review_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Review not found")
    return {"message": "Review deleted"}


# ============ PERFORMANCE STATS ============

@router.get("/hrms/performance/stats")
async def get_performance_stats(cycle_id: Optional[str] = None, user: dict = Depends(get_current_user)):
    query = {}
    if cycle_id:
        query['cycle_id'] = cycle_id
    total_reviews = await db.hrms_reviews.count_documents(query)
    completed = await db.hrms_reviews.count_documents({**query, 'status': 'completed'})
    drafts = await db.hrms_reviews.count_documents({**query, 'status': 'draft'})

    pipeline = [
        {'$match': query},
        {'$group': {'_id': None, 'avg_rating': {'$avg': '$overall_rating'}}}
    ]
    agg = await db.hrms_reviews.aggregate(pipeline).to_list(1)
    avg_rating = round(agg[0]['avg_rating'], 2) if agg and agg[0].get('avg_rating') else 0

    rating_dist = {'excellent': 0, 'good': 0, 'average': 0, 'below_average': 0, 'poor': 0}
    async for r in db.hrms_reviews.find(query, {'_id': 0, 'overall_rating': 1}):
        rating = r.get('overall_rating', 0)
        if rating >= 4.5:
            rating_dist['excellent'] += 1
        elif rating >= 3.5:
            rating_dist['good'] += 1
        elif rating >= 2.5:
            rating_dist['average'] += 1
        elif rating >= 1.5:
            rating_dist['below_average'] += 1
        else:
            rating_dist['poor'] += 1

    return {
        'total_reviews': total_reviews,
        'completed': completed,
        'drafts': drafts,
        'avg_rating': avg_rating,
        'rating_distribution': rating_dist,
    }
