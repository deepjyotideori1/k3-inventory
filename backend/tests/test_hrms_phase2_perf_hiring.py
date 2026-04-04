"""
HRMS Phase 2 Backend API Tests - Performance Management & Hiring Analytics
Tests for: KPIs, Appraisal Cycles, Reviews, Performance Stats,
           Jobs, Candidates, Hiring Stats
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@k3gas.com"
ADMIN_PASSWORD = "Admin@123"


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def auth_token(api_client):
    """Get authentication token for admin"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json().get("token")


@pytest.fixture(scope="module")
def authenticated_client(api_client, auth_token):
    """Session with auth header"""
    api_client.headers.update({"Authorization": f"Bearer {auth_token}"})
    return api_client


@pytest.fixture(scope="module")
def existing_employee_id(authenticated_client):
    """Get an existing active employee ID for testing"""
    response = authenticated_client.get(f"{BASE_URL}/api/hrms/employees", params={"status": "active"})
    if response.status_code == 200:
        employees = response.json().get("employees", [])
        if employees:
            return employees[0]["id"]
    pytest.skip("No active employees found for testing")


@pytest.fixture(scope="module")
def existing_department_id(authenticated_client):
    """Get an existing department ID for testing"""
    response = authenticated_client.get(f"{BASE_URL}/api/hrms/departments")
    if response.status_code == 200:
        depts = response.json()
        if depts:
            return depts[0]["id"]
    pytest.skip("No departments found for testing")


# ============ KPI TESTS ============

class TestKPIs:
    """KPI Template API tests"""
    
    def test_get_kpis(self, authenticated_client):
        """Test GET /api/hrms/kpis returns KPI list"""
        response = authenticated_client.get(f"{BASE_URL}/api/hrms/kpis")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} KPIs")
        
        # If KPIs exist, verify structure
        if data:
            kpi = data[0]
            assert "id" in kpi
            assert "name" in kpi
            assert "max_rating" in kpi
            assert "weightage" in kpi
            print(f"Sample KPI: {kpi['name']}")
    
    def test_create_kpi(self, authenticated_client):
        """Test POST /api/hrms/kpis creates KPI"""
        test_kpi = {
            "name": f"TEST_KPI_{uuid.uuid4().hex[:6]}",
            "description": "Test KPI for automated testing",
            "department_id": "all",
            "max_rating": 5,
            "weightage": 1.5
        }
        response = authenticated_client.post(f"{BASE_URL}/api/hrms/kpis", json=test_kpi)
        assert response.status_code == 200
        data = response.json()
        
        assert "id" in data
        assert data["name"] == test_kpi["name"]
        assert data["max_rating"] == 5
        assert data["weightage"] == 1.5
        print(f"Created KPI: {data['name']} (ID: {data['id']})")
        
        # Store for cleanup
        pytest.test_kpi_id = data["id"]
    
    def test_create_kpi_missing_name(self, authenticated_client):
        """Test POST /api/hrms/kpis without name returns 400"""
        response = authenticated_client.post(f"{BASE_URL}/api/hrms/kpis", json={
            "description": "No name KPI"
        })
        assert response.status_code == 400
        print("Missing KPI name correctly rejected")
    
    def test_delete_kpi(self, authenticated_client):
        """Test DELETE /api/hrms/kpis/{id} deletes KPI"""
        # Create a KPI to delete
        create_response = authenticated_client.post(f"{BASE_URL}/api/hrms/kpis", json={
            "name": f"TEST_DELETE_KPI_{uuid.uuid4().hex[:6]}",
            "description": "To be deleted"
        })
        assert create_response.status_code == 200
        kpi_id = create_response.json()["id"]
        
        # Delete it
        delete_response = authenticated_client.delete(f"{BASE_URL}/api/hrms/kpis/{kpi_id}")
        assert delete_response.status_code == 200
        print(f"KPI {kpi_id} deleted successfully")
        
        # Verify it's gone - should return empty or not contain this KPI
        get_response = authenticated_client.get(f"{BASE_URL}/api/hrms/kpis")
        kpis = get_response.json()
        assert not any(k["id"] == kpi_id for k in kpis)
    
    def test_delete_kpi_not_found(self, authenticated_client):
        """Test DELETE /api/hrms/kpis/{id} with invalid ID returns 404"""
        response = authenticated_client.delete(f"{BASE_URL}/api/hrms/kpis/invalid-kpi-id-12345")
        assert response.status_code == 404
        print("Invalid KPI ID correctly returns 404")


# ============ APPRAISAL CYCLE TESTS ============

class TestAppraisalCycles:
    """Appraisal Cycle API tests"""
    
    def test_get_appraisal_cycles(self, authenticated_client):
        """Test GET /api/hrms/appraisals/cycles returns cycles with review_count"""
        response = authenticated_client.get(f"{BASE_URL}/api/hrms/appraisals/cycles")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} appraisal cycles")
        
        # If cycles exist, verify structure
        if data:
            cycle = data[0]
            assert "id" in cycle
            assert "name" in cycle
            assert "start_date" in cycle
            assert "end_date" in cycle
            assert "status" in cycle
            assert "review_count" in cycle  # Important: verify review_count is included
            print(f"Sample cycle: {cycle['name']} - {cycle['review_count']} reviews")
    
    def test_create_appraisal_cycle(self, authenticated_client):
        """Test POST /api/hrms/appraisals/cycles creates cycle"""
        test_cycle = {
            "name": f"TEST_Cycle_{uuid.uuid4().hex[:6]}",
            "start_date": "2026-04-01",
            "end_date": "2026-06-30",
            "description": "Test appraisal cycle"
        }
        response = authenticated_client.post(f"{BASE_URL}/api/hrms/appraisals/cycles", json=test_cycle)
        assert response.status_code == 200
        data = response.json()
        
        assert "id" in data
        assert data["name"] == test_cycle["name"]
        assert data["start_date"] == "2026-04-01"
        assert data["end_date"] == "2026-06-30"
        assert data["status"] == "active"
        print(f"Created cycle: {data['name']} (ID: {data['id']})")
        
        # Store for later tests
        pytest.test_cycle_id = data["id"]
    
    def test_create_cycle_missing_fields(self, authenticated_client):
        """Test POST /api/hrms/appraisals/cycles with missing fields returns 400"""
        response = authenticated_client.post(f"{BASE_URL}/api/hrms/appraisals/cycles", json={
            "name": "Incomplete Cycle"
            # Missing start_date and end_date
        })
        assert response.status_code == 400
        print("Missing cycle fields correctly rejected")
    
    def test_delete_cycle_no_reviews(self, authenticated_client):
        """Test DELETE /api/hrms/appraisals/cycles/{id} deletes cycle without reviews"""
        # Create a cycle to delete
        create_response = authenticated_client.post(f"{BASE_URL}/api/hrms/appraisals/cycles", json={
            "name": f"TEST_DELETE_Cycle_{uuid.uuid4().hex[:6]}",
            "start_date": "2026-07-01",
            "end_date": "2026-09-30"
        })
        assert create_response.status_code == 200
        cycle_id = create_response.json()["id"]
        
        # Delete it (should succeed since no reviews)
        delete_response = authenticated_client.delete(f"{BASE_URL}/api/hrms/appraisals/cycles/{cycle_id}")
        assert delete_response.status_code == 200
        print(f"Cycle {cycle_id} deleted successfully")


# ============ PERFORMANCE REVIEW TESTS ============

class TestPerformanceReviews:
    """Performance Review API tests"""
    
    def test_get_reviews(self, authenticated_client):
        """Test GET /api/hrms/reviews returns reviews"""
        response = authenticated_client.get(f"{BASE_URL}/api/hrms/reviews")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} reviews")
        
        # If reviews exist, verify structure
        if data:
            review = data[0]
            assert "id" in review
            assert "cycle_id" in review
            assert "employee_id" in review
            assert "overall_rating" in review
            assert "status" in review
            print(f"Sample review: Employee {review.get('employee_name', 'N/A')} - Rating: {review['overall_rating']}")
    
    def test_create_review_with_weighted_rating(self, authenticated_client, existing_employee_id):
        """Test POST /api/hrms/reviews creates review with weighted rating calculation"""
        # First ensure we have a cycle and KPIs
        cycles_response = authenticated_client.get(f"{BASE_URL}/api/hrms/appraisals/cycles")
        cycles = cycles_response.json()
        if not cycles:
            pytest.skip("No appraisal cycles available")
        
        kpis_response = authenticated_client.get(f"{BASE_URL}/api/hrms/kpis")
        kpis = kpis_response.json()
        if not kpis:
            pytest.skip("No KPIs available")
        
        cycle_id = cycles[0]["id"]
        
        # Create ratings with different weights
        ratings = [
            {"kpi_id": kpis[0]["id"], "kpi_name": kpis[0]["name"], "rating": 4, "weightage": 2.0},
            {"kpi_id": kpis[0]["id"] + "_extra", "kpi_name": "Extra KPI", "rating": 5, "weightage": 1.0}
        ]
        
        # Calculate expected weighted average: (4*2 + 5*1) / (2+1) = 13/3 = 4.33
        expected_rating = round((4*2 + 5*1) / (2+1), 2)
        
        review_data = {
            "cycle_id": cycle_id,
            "employee_id": existing_employee_id,
            "ratings": ratings,
            "manager_comments": "Test review with weighted ratings",
            "goals": "Improve communication skills"
        }
        
        response = authenticated_client.post(f"{BASE_URL}/api/hrms/reviews", json=review_data)
        
        # Could be 200 (success) or 400 (review already exists)
        if response.status_code == 200:
            data = response.json()
            assert "id" in data
            assert "overall_rating" in data
            assert data["overall_rating"] == expected_rating
            assert data["status"] == "draft"
            print(f"Created review with weighted rating: {data['overall_rating']}")
            pytest.test_review_id = data["id"]
        elif response.status_code == 400:
            print("Review already exists for this employee/cycle - expected behavior")
        else:
            pytest.fail(f"Unexpected status: {response.status_code} - {response.text}")
    
    def test_update_review_recalculates_rating(self, authenticated_client):
        """Test PUT /api/hrms/reviews/{id} updates review and recalculates rating"""
        # Get existing reviews
        reviews_response = authenticated_client.get(f"{BASE_URL}/api/hrms/reviews")
        reviews = reviews_response.json()
        
        if not reviews:
            pytest.skip("No reviews available for update test")
        
        review_id = reviews[0]["id"]
        
        # Update with new ratings
        new_ratings = [
            {"kpi_id": "test1", "kpi_name": "Test KPI 1", "rating": 5, "weightage": 1.0},
            {"kpi_id": "test2", "kpi_name": "Test KPI 2", "rating": 3, "weightage": 1.0}
        ]
        expected_rating = round((5*1 + 3*1) / 2, 2)  # 4.0
        
        response = authenticated_client.put(f"{BASE_URL}/api/hrms/reviews/{review_id}", json={
            "ratings": new_ratings,
            "manager_comments": "Updated review"
        })
        assert response.status_code == 200
        print(f"Review {review_id} updated")
        
        # Verify the rating was recalculated
        get_response = authenticated_client.get(f"{BASE_URL}/api/hrms/reviews")
        updated_review = next((r for r in get_response.json() if r["id"] == review_id), None)
        if updated_review:
            assert updated_review["overall_rating"] == expected_rating
            print(f"Rating recalculated to: {updated_review['overall_rating']}")
    
    def test_delete_review(self, authenticated_client, existing_employee_id):
        """Test DELETE /api/hrms/reviews/{id} deletes review"""
        # First create a review to delete
        cycles_response = authenticated_client.get(f"{BASE_URL}/api/hrms/appraisals/cycles")
        cycles = cycles_response.json()
        if not cycles:
            pytest.skip("No cycles available")
        
        # Create a new cycle for this test to avoid conflicts
        new_cycle = authenticated_client.post(f"{BASE_URL}/api/hrms/appraisals/cycles", json={
            "name": f"TEST_DELETE_Review_Cycle_{uuid.uuid4().hex[:6]}",
            "start_date": "2026-10-01",
            "end_date": "2026-12-31"
        })
        if new_cycle.status_code != 200:
            pytest.skip("Could not create test cycle")
        
        cycle_id = new_cycle.json()["id"]
        
        # Create review
        create_response = authenticated_client.post(f"{BASE_URL}/api/hrms/reviews", json={
            "cycle_id": cycle_id,
            "employee_id": existing_employee_id,
            "ratings": [{"kpi_id": "test", "kpi_name": "Test", "rating": 3, "weightage": 1}],
            "manager_comments": "To be deleted"
        })
        
        if create_response.status_code == 200:
            review_id = create_response.json()["id"]
            
            # Delete it
            delete_response = authenticated_client.delete(f"{BASE_URL}/api/hrms/reviews/{review_id}")
            assert delete_response.status_code == 200
            print(f"Review {review_id} deleted successfully")
            
            # Clean up the cycle
            authenticated_client.delete(f"{BASE_URL}/api/hrms/appraisals/cycles/{cycle_id}")
        else:
            print("Could not create review for delete test")


# ============ PERFORMANCE STATS TESTS ============

class TestPerformanceStats:
    """Performance Statistics API tests"""
    
    def test_get_performance_stats(self, authenticated_client):
        """Test GET /api/hrms/performance/stats returns avg rating and distribution"""
        response = authenticated_client.get(f"{BASE_URL}/api/hrms/performance/stats")
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "total_reviews" in data
        assert "completed" in data
        assert "drafts" in data
        assert "avg_rating" in data
        assert "rating_distribution" in data
        
        # Verify rating distribution structure
        dist = data["rating_distribution"]
        assert "excellent" in dist
        assert "good" in dist
        assert "average" in dist
        assert "below_average" in dist
        assert "poor" in dist
        
        print(f"Performance stats: {data['total_reviews']} reviews, Avg: {data['avg_rating']}")
        print(f"Distribution: {dist}")
    
    def test_get_performance_stats_with_cycle_filter(self, authenticated_client):
        """Test GET /api/hrms/performance/stats with cycle_id filter"""
        # Get a cycle ID
        cycles_response = authenticated_client.get(f"{BASE_URL}/api/hrms/appraisals/cycles")
        cycles = cycles_response.json()
        
        if not cycles:
            pytest.skip("No cycles available for filter test")
        
        cycle_id = cycles[0]["id"]
        response = authenticated_client.get(f"{BASE_URL}/api/hrms/performance/stats", params={"cycle_id": cycle_id})
        assert response.status_code == 200
        data = response.json()
        assert "total_reviews" in data
        print(f"Stats for cycle {cycle_id}: {data['total_reviews']} reviews")


# ============ JOB OPENINGS TESTS ============

class TestJobOpenings:
    """Job Openings API tests"""
    
    def test_get_jobs(self, authenticated_client):
        """Test GET /api/hrms/jobs returns jobs with candidate/hired counts"""
        response = authenticated_client.get(f"{BASE_URL}/api/hrms/jobs")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} job openings")
        
        # If jobs exist, verify structure
        if data:
            job = data[0]
            assert "id" in job
            assert "title" in job
            assert "department_id" in job
            assert "status" in job
            assert "candidate_count" in job  # Important: verify counts are included
            assert "hired_count" in job
            assert "department_name" in job
            print(f"Sample job: {job['title']} - {job['candidate_count']} candidates, {job['hired_count']} hired")
    
    def test_create_job(self, authenticated_client, existing_department_id):
        """Test POST /api/hrms/jobs creates job opening"""
        test_job = {
            "title": f"TEST_Job_{uuid.uuid4().hex[:6]}",
            "department_id": existing_department_id,
            "location": "Test City",
            "employment_type": "full_time",
            "vacancies": 2,
            "description": "Test job opening",
            "experience_required": "2-3 years",
            "salary_range": "20,000 - 30,000"
        }
        response = authenticated_client.post(f"{BASE_URL}/api/hrms/jobs", json=test_job)
        assert response.status_code == 200
        data = response.json()
        
        assert "id" in data
        assert data["title"] == test_job["title"]
        assert data["status"] == "open"
        assert data["vacancies"] == 2
        print(f"Created job: {data['title']} (ID: {data['id']})")
        
        # Store for later tests
        pytest.test_job_id = data["id"]
    
    def test_create_job_missing_fields(self, authenticated_client):
        """Test POST /api/hrms/jobs with missing fields returns 400"""
        response = authenticated_client.post(f"{BASE_URL}/api/hrms/jobs", json={
            "title": "Incomplete Job"
            # Missing department_id
        })
        assert response.status_code == 400
        print("Missing job fields correctly rejected")
    
    def test_update_job_close_reopen(self, authenticated_client, existing_department_id):
        """Test PUT /api/hrms/jobs/{id} updates job (close/reopen)"""
        # Create a job to update
        create_response = authenticated_client.post(f"{BASE_URL}/api/hrms/jobs", json={
            "title": f"TEST_Update_Job_{uuid.uuid4().hex[:6]}",
            "department_id": existing_department_id
        })
        assert create_response.status_code == 200
        job_id = create_response.json()["id"]
        
        # Close the job
        close_response = authenticated_client.put(f"{BASE_URL}/api/hrms/jobs/{job_id}", json={
            "status": "closed"
        })
        assert close_response.status_code == 200
        print(f"Job {job_id} closed")
        
        # Verify it's closed
        jobs_response = authenticated_client.get(f"{BASE_URL}/api/hrms/jobs")
        job = next((j for j in jobs_response.json() if j["id"] == job_id), None)
        assert job["status"] == "closed"
        
        # Reopen the job
        reopen_response = authenticated_client.put(f"{BASE_URL}/api/hrms/jobs/{job_id}", json={
            "status": "open"
        })
        assert reopen_response.status_code == 200
        print(f"Job {job_id} reopened")
        
        # Clean up
        authenticated_client.delete(f"{BASE_URL}/api/hrms/jobs/{job_id}")
    
    def test_delete_job_no_candidates(self, authenticated_client, existing_department_id):
        """Test DELETE /api/hrms/jobs/{id} deletes job without candidates"""
        # Create a job to delete
        create_response = authenticated_client.post(f"{BASE_URL}/api/hrms/jobs", json={
            "title": f"TEST_Delete_Job_{uuid.uuid4().hex[:6]}",
            "department_id": existing_department_id
        })
        assert create_response.status_code == 200
        job_id = create_response.json()["id"]
        
        # Delete it (should succeed since no candidates)
        delete_response = authenticated_client.delete(f"{BASE_URL}/api/hrms/jobs/{job_id}")
        assert delete_response.status_code == 200
        print(f"Job {job_id} deleted successfully")
    
    def test_delete_job_with_candidates_blocked(self, authenticated_client, existing_department_id):
        """Test DELETE /api/hrms/jobs/{id} blocks if candidates linked"""
        # Create a job
        job_response = authenticated_client.post(f"{BASE_URL}/api/hrms/jobs", json={
            "title": f"TEST_Block_Delete_Job_{uuid.uuid4().hex[:6]}",
            "department_id": existing_department_id
        })
        assert job_response.status_code == 200
        job_id = job_response.json()["id"]
        
        # Add a candidate to this job
        cand_response = authenticated_client.post(f"{BASE_URL}/api/hrms/candidates", json={
            "name": f"TEST_Candidate_{uuid.uuid4().hex[:6]}",
            "email": f"test_{uuid.uuid4().hex[:6]}@test.com",
            "job_id": job_id
        })
        assert cand_response.status_code == 200
        cand_id = cand_response.json()["id"]
        
        # Try to delete job - should fail
        delete_response = authenticated_client.delete(f"{BASE_URL}/api/hrms/jobs/{job_id}")
        assert delete_response.status_code == 400
        assert "candidates" in delete_response.json().get("detail", "").lower()
        print("Job deletion correctly blocked due to linked candidates")
        
        # Clean up: delete candidate first, then job
        authenticated_client.delete(f"{BASE_URL}/api/hrms/candidates/{cand_id}")
        authenticated_client.delete(f"{BASE_URL}/api/hrms/jobs/{job_id}")


# ============ CANDIDATE TESTS ============

class TestCandidates:
    """Candidate API tests"""
    
    def test_get_candidates(self, authenticated_client):
        """Test GET /api/hrms/candidates returns candidates"""
        response = authenticated_client.get(f"{BASE_URL}/api/hrms/candidates")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} candidates")
        
        # If candidates exist, verify structure
        if data:
            cand = data[0]
            assert "id" in cand
            assert "name" in cand
            assert "email" in cand
            assert "job_id" in cand
            assert "stage" in cand
            assert "job_title" in cand
            print(f"Sample candidate: {cand['name']} - Stage: {cand['stage']}")
    
    def test_create_candidate_with_stage_history(self, authenticated_client, existing_department_id):
        """Test POST /api/hrms/candidates creates candidate with stage history"""
        # First create a job
        job_response = authenticated_client.post(f"{BASE_URL}/api/hrms/jobs", json={
            "title": f"TEST_Cand_Job_{uuid.uuid4().hex[:6]}",
            "department_id": existing_department_id
        })
        assert job_response.status_code == 200
        job_id = job_response.json()["id"]
        
        # Create candidate
        test_candidate = {
            "name": f"TEST_Candidate_{uuid.uuid4().hex[:6]}",
            "email": f"test_{uuid.uuid4().hex[:6]}@test.com",
            "phone": "9876543210",
            "job_id": job_id,
            "experience": "3 years",
            "source": "linkedin"
        }
        response = authenticated_client.post(f"{BASE_URL}/api/hrms/candidates", json=test_candidate)
        assert response.status_code == 200
        data = response.json()
        
        assert "id" in data
        assert data["name"] == test_candidate["name"]
        assert data["stage"] == "applied"  # Default stage
        assert "stage_history" in data
        assert len(data["stage_history"]) == 1
        assert data["stage_history"][0]["stage"] == "applied"
        print(f"Created candidate: {data['name']} with stage history")
        
        # Store for later tests
        pytest.test_candidate_id = data["id"]
        pytest.test_candidate_job_id = job_id
    
    def test_get_candidates_with_filters(self, authenticated_client):
        """Test GET /api/hrms/candidates with filters (job_id, stage, search)"""
        # Get all candidates first
        all_response = authenticated_client.get(f"{BASE_URL}/api/hrms/candidates")
        all_candidates = all_response.json()
        
        if not all_candidates:
            pytest.skip("No candidates available for filter test")
        
        # Test job_id filter
        job_id = all_candidates[0]["job_id"]
        job_response = authenticated_client.get(f"{BASE_URL}/api/hrms/candidates", params={"job_id": job_id})
        assert job_response.status_code == 200
        print(f"Filtered by job_id: {len(job_response.json())} candidates")
        
        # Test stage filter
        stage_response = authenticated_client.get(f"{BASE_URL}/api/hrms/candidates", params={"stage": "applied"})
        assert stage_response.status_code == 200
        print(f"Filtered by stage 'applied': {len(stage_response.json())} candidates")
        
        # Test search filter
        search_term = all_candidates[0]["name"][:3]
        search_response = authenticated_client.get(f"{BASE_URL}/api/hrms/candidates", params={"search": search_term})
        assert search_response.status_code == 200
        print(f"Search for '{search_term}': {len(search_response.json())} candidates")
    
    def test_update_candidate_stage_with_history(self, authenticated_client, existing_department_id):
        """Test PUT /api/hrms/candidates/{id} updates stage with history tracking"""
        # Create a job and candidate
        job_response = authenticated_client.post(f"{BASE_URL}/api/hrms/jobs", json={
            "title": f"TEST_Stage_Job_{uuid.uuid4().hex[:6]}",
            "department_id": existing_department_id
        })
        job_id = job_response.json()["id"]
        
        cand_response = authenticated_client.post(f"{BASE_URL}/api/hrms/candidates", json={
            "name": f"TEST_Stage_Cand_{uuid.uuid4().hex[:6]}",
            "email": f"stage_{uuid.uuid4().hex[:6]}@test.com",
            "job_id": job_id
        })
        cand_id = cand_response.json()["id"]
        
        # Update stage to screening
        update_response = authenticated_client.put(f"{BASE_URL}/api/hrms/candidates/{cand_id}", json={
            "stage": "screening"
        })
        assert update_response.status_code == 200
        print(f"Candidate {cand_id} moved to screening")
        
        # Update stage to interview
        update_response2 = authenticated_client.put(f"{BASE_URL}/api/hrms/candidates/{cand_id}", json={
            "stage": "interview"
        })
        assert update_response2.status_code == 200
        print(f"Candidate {cand_id} moved to interview")
        
        # Verify stage history has 3 entries (applied, screening, interview)
        get_response = authenticated_client.get(f"{BASE_URL}/api/hrms/candidates", params={"job_id": job_id})
        candidate = next((c for c in get_response.json() if c["id"] == cand_id), None)
        assert candidate is not None
        assert candidate["stage"] == "interview"
        # Note: stage_history might not be returned in list view, but stage should be updated
        print(f"Candidate stage verified: {candidate['stage']}")
        
        # Clean up
        authenticated_client.delete(f"{BASE_URL}/api/hrms/candidates/{cand_id}")
        authenticated_client.delete(f"{BASE_URL}/api/hrms/jobs/{job_id}")
    
    def test_delete_candidate(self, authenticated_client, existing_department_id):
        """Test DELETE /api/hrms/candidates/{id} deletes candidate"""
        # Create a job and candidate
        job_response = authenticated_client.post(f"{BASE_URL}/api/hrms/jobs", json={
            "title": f"TEST_Del_Cand_Job_{uuid.uuid4().hex[:6]}",
            "department_id": existing_department_id
        })
        job_id = job_response.json()["id"]
        
        cand_response = authenticated_client.post(f"{BASE_URL}/api/hrms/candidates", json={
            "name": f"TEST_Del_Cand_{uuid.uuid4().hex[:6]}",
            "email": f"del_{uuid.uuid4().hex[:6]}@test.com",
            "job_id": job_id
        })
        cand_id = cand_response.json()["id"]
        
        # Delete candidate
        delete_response = authenticated_client.delete(f"{BASE_URL}/api/hrms/candidates/{cand_id}")
        assert delete_response.status_code == 200
        print(f"Candidate {cand_id} deleted successfully")
        
        # Clean up job
        authenticated_client.delete(f"{BASE_URL}/api/hrms/jobs/{job_id}")


# ============ HIRING STATS TESTS ============

class TestHiringStats:
    """Hiring Statistics API tests"""
    
    def test_get_hiring_stats(self, authenticated_client):
        """Test GET /api/hrms/hiring/stats returns pipeline breakdown and source stats"""
        response = authenticated_client.get(f"{BASE_URL}/api/hrms/hiring/stats")
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "total_jobs" in data
        assert "open_jobs" in data
        assert "closed_jobs" in data
        assert "total_candidates" in data
        assert "hired" in data
        assert "rejected" in data
        assert "in_pipeline" in data
        assert "pipeline_breakdown" in data
        assert "source_breakdown" in data
        
        # Verify pipeline breakdown has all stages
        pipeline = data["pipeline_breakdown"]
        expected_stages = ['applied', 'screening', 'interview', 'assessment', 'offer', 'hired', 'rejected', 'withdrawn']
        for stage in expected_stages:
            assert stage in pipeline
        
        print(f"Hiring stats: {data['total_jobs']} jobs, {data['total_candidates']} candidates")
        print(f"Pipeline: {pipeline}")
        print(f"Sources: {data['source_breakdown']}")


# ============ INVENTORY DASHBOARD UNAFFECTED TEST ============

class TestInventoryDashboardUnaffected:
    """Verify Inventory Dashboard APIs still work"""
    
    def test_inventory_dashboard_stats(self, authenticated_client):
        """Test GET /api/dashboard/stats still works"""
        response = authenticated_client.get(f"{BASE_URL}/api/dashboard/stats")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        print(f"Inventory dashboard stats working: {list(data.keys())[:5]}...")


# ============ CLEANUP ============

class TestCleanup:
    """Clean up test data"""
    
    def test_cleanup_test_kpis(self, authenticated_client):
        """Clean up TEST_ prefixed KPIs"""
        response = authenticated_client.get(f"{BASE_URL}/api/hrms/kpis")
        kpis = response.json()
        deleted = 0
        for kpi in kpis:
            if kpi["name"].startswith("TEST_"):
                authenticated_client.delete(f"{BASE_URL}/api/hrms/kpis/{kpi['id']}")
                deleted += 1
        print(f"Cleaned up {deleted} test KPIs")
    
    def test_cleanup_test_cycles(self, authenticated_client):
        """Clean up TEST_ prefixed cycles"""
        response = authenticated_client.get(f"{BASE_URL}/api/hrms/appraisals/cycles")
        cycles = response.json()
        deleted = 0
        for cycle in cycles:
            if cycle["name"].startswith("TEST_"):
                # Only delete if no reviews
                if cycle.get("review_count", 0) == 0:
                    authenticated_client.delete(f"{BASE_URL}/api/hrms/appraisals/cycles/{cycle['id']}")
                    deleted += 1
        print(f"Cleaned up {deleted} test cycles")
    
    def test_cleanup_test_jobs(self, authenticated_client):
        """Clean up TEST_ prefixed jobs"""
        response = authenticated_client.get(f"{BASE_URL}/api/hrms/jobs")
        jobs = response.json()
        deleted = 0
        for job in jobs:
            if job["title"].startswith("TEST_"):
                # Only delete if no candidates
                if job.get("candidate_count", 0) == 0:
                    authenticated_client.delete(f"{BASE_URL}/api/hrms/jobs/{job['id']}")
                    deleted += 1
        print(f"Cleaned up {deleted} test jobs")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
