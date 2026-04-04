from fastapi import APIRouter, HTTPException, Depends
from database import db
from deps import get_current_user
from helpers import log_audit
from datetime import datetime, timezone
from typing import Optional
import uuid

router = APIRouter()

HIRING_STAGES = ['applied', 'screening', 'interview', 'assessment', 'offer', 'hired', 'rejected', 'withdrawn']


# ============ JOB OPENINGS ============

@router.get("/hrms/jobs")
async def get_jobs(status: Optional[str] = None, user: dict = Depends(get_current_user)):
    query = {}
    if status and status != 'all':
        query['status'] = status
    jobs = []
    async for j in db.hrms_jobs.find(query, {'_id': 0}).sort('created_at', 1):
        j['candidate_count'] = await db.hrms_candidates.count_documents({'job_id': j['id']})
        j['hired_count'] = await db.hrms_candidates.count_documents({'job_id': j['id'], 'stage': 'hired'})
        dept = await db.hrms_departments.find_one({'id': j.get('department_id')}, {'_id': 0, 'name': 1})
        j['department_name'] = dept['name'] if dept else 'N/A'
        jobs.append(j)
    return jobs


@router.post("/hrms/jobs")
async def create_job(data: dict, user: dict = Depends(get_current_user)):
    if user.get('role') not in ('admin', 'hr_admin'):
        raise HTTPException(status_code=403, detail="Admin or HR Admin required")
    required = ['title', 'department_id']
    for f in required:
        if not data.get(f):
            raise HTTPException(status_code=400, detail=f"{f} is required")
    job = {
        'id': str(uuid.uuid4()),
        'title': data['title'],
        'department_id': data['department_id'],
        'location': data.get('location', ''),
        'employment_type': data.get('employment_type', 'full_time'),
        'experience_required': data.get('experience_required', ''),
        'salary_range': data.get('salary_range', ''),
        'description': data.get('description', ''),
        'requirements': data.get('requirements', ''),
        'vacancies': int(data.get('vacancies', 1)),
        'status': 'open',
        'posted_by': user.get('name', ''),
        'created_at': datetime.now(timezone.utc).isoformat(),
    }
    await db.hrms_jobs.insert_one(job)
    return {k: v for k, v in job.items() if k != '_id'}


@router.put("/hrms/jobs/{job_id}")
async def update_job(job_id: str, data: dict, user: dict = Depends(get_current_user)):
    if user.get('role') not in ('admin', 'hr_admin'):
        raise HTTPException(status_code=403, detail="Admin or HR Admin required")
    allowed = ['title', 'department_id', 'location', 'employment_type', 'experience_required',
               'salary_range', 'description', 'requirements', 'vacancies', 'status']
    update = {k: v for k, v in data.items() if k in allowed}
    if 'vacancies' in update:
        update['vacancies'] = int(update['vacancies'])
    update['updated_at'] = datetime.now(timezone.utc).isoformat()
    result = await db.hrms_jobs.update_one({'id': job_id}, {'$set': update})
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"message": "Job updated"}


@router.delete("/hrms/jobs/{job_id}")
async def delete_job(job_id: str, user: dict = Depends(get_current_user)):
    if user.get('role') not in ('admin', 'hr_admin'):
        raise HTTPException(status_code=403, detail="Admin or HR Admin required")
    candidates = await db.hrms_candidates.count_documents({'job_id': job_id})
    if candidates > 0:
        raise HTTPException(status_code=400, detail=f"Cannot delete: {candidates} candidates linked")
    result = await db.hrms_jobs.delete_one({'id': job_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"message": "Job deleted"}


# ============ CANDIDATES ============

@router.get("/hrms/candidates")
async def get_candidates(
    job_id: Optional[str] = None,
    stage: Optional[str] = None,
    search: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    query = {}
    if job_id and job_id != 'all':
        query['job_id'] = job_id
    if stage and stage != 'all':
        query['stage'] = stage
    if search:
        query['$or'] = [
            {'name': {'$regex': search, '$options': 'i'}},
            {'email': {'$regex': search, '$options': 'i'}},
            {'phone': {'$regex': search, '$options': 'i'}},
        ]
    candidates = []
    async for c in db.hrms_candidates.find(query, {'_id': 0}).sort('created_at', 1):
        job = await db.hrms_jobs.find_one({'id': c.get('job_id')}, {'_id': 0, 'title': 1})
        c['job_title'] = job['title'] if job else 'N/A'
        candidates.append(c)
    return candidates


@router.post("/hrms/candidates")
async def create_candidate(data: dict, user: dict = Depends(get_current_user)):
    if user.get('role') not in ('admin', 'hr_admin'):
        raise HTTPException(status_code=403, detail="Admin or HR Admin required")
    required = ['name', 'email', 'job_id']
    for f in required:
        if not data.get(f):
            raise HTTPException(status_code=400, detail=f"{f} is required")

    candidate = {
        'id': str(uuid.uuid4()),
        'name': data['name'],
        'email': data['email'],
        'phone': data.get('phone', ''),
        'job_id': data['job_id'],
        'stage': data.get('stage', 'applied'),
        'experience': data.get('experience', ''),
        'current_company': data.get('current_company', ''),
        'expected_salary': data.get('expected_salary', ''),
        'resume_notes': data.get('resume_notes', ''),
        'interview_notes': data.get('interview_notes', ''),
        'rating': int(data.get('rating', 0)),
        'source': data.get('source', 'direct'),
        'stage_history': [{'stage': 'applied', 'date': datetime.now(timezone.utc).isoformat(), 'by': user.get('name', '')}],
        'created_at': datetime.now(timezone.utc).isoformat(),
    }
    await db.hrms_candidates.insert_one(candidate)
    return {k: v for k, v in candidate.items() if k != '_id'}


@router.put("/hrms/candidates/{candidate_id}")
async def update_candidate(candidate_id: str, data: dict, user: dict = Depends(get_current_user)):
    if user.get('role') not in ('admin', 'hr_admin'):
        raise HTTPException(status_code=403, detail="Admin or HR Admin required")

    cand = await db.hrms_candidates.find_one({'id': candidate_id}, {'_id': 0})
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found")

    allowed = ['name', 'email', 'phone', 'stage', 'experience', 'current_company',
               'expected_salary', 'resume_notes', 'interview_notes', 'rating', 'source']
    update = {k: v for k, v in data.items() if k in allowed}
    if 'rating' in update:
        update['rating'] = int(update['rating'])

    # Track stage changes
    if 'stage' in update and update['stage'] != cand.get('stage'):
        history_entry = {'stage': update['stage'], 'date': datetime.now(timezone.utc).isoformat(), 'by': user.get('name', '')}
        await db.hrms_candidates.update_one(
            {'id': candidate_id},
            {'$push': {'stage_history': history_entry}}
        )

    update['updated_at'] = datetime.now(timezone.utc).isoformat()
    await db.hrms_candidates.update_one({'id': candidate_id}, {'$set': update})
    return {"message": "Candidate updated"}


@router.delete("/hrms/candidates/{candidate_id}")
async def delete_candidate(candidate_id: str, user: dict = Depends(get_current_user)):
    if user.get('role') not in ('admin', 'hr_admin'):
        raise HTTPException(status_code=403, detail="Admin or HR Admin required")
    result = await db.hrms_candidates.delete_one({'id': candidate_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return {"message": "Candidate deleted"}


# ============ HIRING ANALYTICS ============

@router.get("/hrms/hiring/stats")
async def get_hiring_stats(user: dict = Depends(get_current_user)):
    total_jobs = await db.hrms_jobs.count_documents({})
    open_jobs = await db.hrms_jobs.count_documents({'status': 'open'})
    closed_jobs = await db.hrms_jobs.count_documents({'status': 'closed'})
    total_candidates = await db.hrms_candidates.count_documents({})
    hired = await db.hrms_candidates.count_documents({'stage': 'hired'})
    rejected = await db.hrms_candidates.count_documents({'stage': 'rejected'})
    in_pipeline = await db.hrms_candidates.count_documents({'stage': {'$nin': ['hired', 'rejected', 'withdrawn']}})

    pipeline_breakdown = {}
    for stage in HIRING_STAGES:
        pipeline_breakdown[stage] = await db.hrms_candidates.count_documents({'stage': stage})

    # Source breakdown
    source_pipeline = [
        {'$group': {'_id': '$source', 'count': {'$sum': 1}}}
    ]
    source_data = await db.hrms_candidates.aggregate(source_pipeline).to_list(20)
    source_breakdown = {s['_id']: s['count'] for s in source_data if s['_id']}

    return {
        'total_jobs': total_jobs,
        'open_jobs': open_jobs,
        'closed_jobs': closed_jobs,
        'total_candidates': total_candidates,
        'hired': hired,
        'rejected': rejected,
        'in_pipeline': in_pipeline,
        'pipeline_breakdown': pipeline_breakdown,
        'source_breakdown': source_breakdown,
    }
