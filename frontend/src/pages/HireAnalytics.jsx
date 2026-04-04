import React, { useState, useEffect, useCallback } from 'react';
import HRMSLayout from '../components/HRMSLayout';
import api from '../lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { toast } from 'sonner';
import {
  Briefcase, Plus, Users, Trash2, Loader2, Search,
  TrendingUp, UserPlus, CheckCircle, XCircle, ArrowRight, Edit
} from 'lucide-react';

const STAGES = [
  { value: 'applied', label: 'Applied', color: 'bg-slate-100 text-slate-700' },
  { value: 'screening', label: 'Screening', color: 'bg-blue-100 text-blue-700' },
  { value: 'interview', label: 'Interview', color: 'bg-purple-100 text-purple-700' },
  { value: 'assessment', label: 'Assessment', color: 'bg-indigo-100 text-indigo-700' },
  { value: 'offer', label: 'Offer', color: 'bg-amber-100 text-amber-700' },
  { value: 'hired', label: 'Hired', color: 'bg-green-100 text-green-700' },
  { value: 'rejected', label: 'Rejected', color: 'bg-red-100 text-red-700' },
  { value: 'withdrawn', label: 'Withdrawn', color: 'bg-gray-100 text-gray-600' },
];

const SOURCES = ['direct', 'referral', 'job_portal', 'linkedin', 'campus', 'walk_in', 'agency', 'other'];

const getStageBadge = (stage) => {
  const s = STAGES.find(st => st.value === stage);
  return <span className={`px-2 py-0.5 rounded text-xs font-medium ${s?.color || 'bg-slate-100'}`}>{s?.label || stage}</span>;
};

const HireAnalytics = () => {
  const [activeTab, setActiveTab] = useState('pipeline');
  const [jobs, setJobs] = useState([]);
  const [candidates, setCandidates] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedJob, setSelectedJob] = useState('all');
  const [selectedStage, setSelectedStage] = useState('all');
  const [search, setSearch] = useState('');

  // Dialogs
  const [jobDialog, setJobDialog] = useState(false);
  const [candidateDialog, setCandidateDialog] = useState(false);
  const [jobForm, setJobForm] = useState({ title: '', department_id: '', location: '', employment_type: 'full_time', vacancies: 1, description: '', requirements: '', salary_range: '', experience_required: '' });
  const [candForm, setCandForm] = useState({ name: '', email: '', phone: '', job_id: '', experience: '', current_company: '', expected_salary: '', source: 'direct', resume_notes: '' });
  const [saving, setSaving] = useState(false);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [jobsRes, deptRes, statsRes] = await Promise.all([
        api.get('/hrms/jobs'),
        api.get('/hrms/departments'),
        api.get('/hrms/hiring/stats'),
      ]);
      setJobs(jobsRes.data);
      setDepartments(deptRes.data);
      setStats(statsRes.data);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, []);

  const fetchCandidates = useCallback(async () => {
    try {
      const params = {};
      if (selectedJob !== 'all') params.job_id = selectedJob;
      if (selectedStage !== 'all') params.stage = selectedStage;
      if (search) params.search = search;
      const res = await api.get('/hrms/candidates', { params });
      setCandidates(res.data);
    } catch (e) { console.error(e); }
  }, [selectedJob, selectedStage, search]);

  useEffect(() => { fetchAll(); }, [fetchAll]);
  useEffect(() => { fetchCandidates(); }, [fetchCandidates]);

  const saveJob = async () => {
    setSaving(true);
    try {
      await api.post('/hrms/jobs', jobForm);
      toast.success('Job opening created');
      setJobDialog(false);
      setJobForm({ title: '', department_id: '', location: '', employment_type: 'full_time', vacancies: 1, description: '', requirements: '', salary_range: '', experience_required: '' });
      fetchAll();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
    setSaving(false);
  };

  const deleteJob = async (id) => {
    if (!window.confirm('Delete this job opening?')) return;
    try {
      await api.delete(`/hrms/jobs/${id}`);
      toast.success('Job deleted');
      fetchAll();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
  };

  const toggleJobStatus = async (job) => {
    const newStatus = job.status === 'open' ? 'closed' : 'open';
    try {
      await api.put(`/hrms/jobs/${job.id}`, { status: newStatus });
      toast.success(`Job ${newStatus === 'open' ? 'reopened' : 'closed'}`);
      fetchAll();
    } catch (e) { toast.error('Failed'); }
  };

  const saveCandidate = async () => {
    setSaving(true);
    try {
      await api.post('/hrms/candidates', candForm);
      toast.success('Candidate added');
      setCandidateDialog(false);
      setCandForm({ name: '', email: '', phone: '', job_id: '', experience: '', current_company: '', expected_salary: '', source: 'direct', resume_notes: '' });
      fetchCandidates();
      fetchAll();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
    setSaving(false);
  };

  const updateCandidateStage = async (candidateId, newStage) => {
    try {
      await api.put(`/hrms/candidates/${candidateId}`, { stage: newStage });
      toast.success(`Stage updated to ${newStage}`);
      fetchCandidates();
      fetchAll();
    } catch (e) { toast.error('Failed to update stage'); }
  };

  const deleteCandidate = async (id) => {
    if (!window.confirm('Delete this candidate?')) return;
    try {
      await api.delete(`/hrms/candidates/${id}`);
      toast.success('Candidate removed');
      fetchCandidates();
      fetchAll();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
  };

  const pipelineStages = ['applied', 'screening', 'interview', 'assessment', 'offer'];

  return (
    <HRMSLayout>
      <div className="space-y-6" data-testid="hire-analytics">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-slate-800">Hire Analytics</h1>
            <p className="text-slate-500 text-sm mt-1">Recruitment pipeline and hiring management</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => setJobDialog(true)} data-testid="add-job-btn"><Briefcase className="w-4 h-4 mr-1" /> New Job</Button>
            <Button size="sm" className="bg-blue-700 hover:bg-blue-800" onClick={() => setCandidateDialog(true)} data-testid="add-candidate-btn"><UserPlus className="w-4 h-4 mr-1" /> Add Candidate</Button>
          </div>
        </div>

        {/* Stats */}
        {stats && (
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
            <Card><CardContent className="p-3 text-center"><p className="text-[10px] text-slate-500 uppercase">Open Jobs</p><p className="text-xl font-bold text-blue-700">{stats.open_jobs}</p></CardContent></Card>
            <Card><CardContent className="p-3 text-center"><p className="text-[10px] text-slate-500 uppercase">Closed</p><p className="text-xl font-bold text-slate-500">{stats.closed_jobs}</p></CardContent></Card>
            <Card><CardContent className="p-3 text-center"><p className="text-[10px] text-slate-500 uppercase">Total Candidates</p><p className="text-xl font-bold">{stats.total_candidates}</p></CardContent></Card>
            <Card><CardContent className="p-3 text-center"><p className="text-[10px] text-slate-500 uppercase">In Pipeline</p><p className="text-xl font-bold text-amber-600">{stats.in_pipeline}</p></CardContent></Card>
            <Card><CardContent className="p-3 text-center"><p className="text-[10px] text-slate-500 uppercase">Hired</p><p className="text-xl font-bold text-green-700">{stats.hired}</p></CardContent></Card>
            <Card><CardContent className="p-3 text-center"><p className="text-[10px] text-slate-500 uppercase">Rejected</p><p className="text-xl font-bold text-red-600">{stats.rejected}</p></CardContent></Card>
            <Card><CardContent className="p-3 text-center"><p className="text-[10px] text-slate-500 uppercase">Conversion</p><p className="text-xl font-bold text-green-700">{stats.total_candidates > 0 ? ((stats.hired / stats.total_candidates) * 100).toFixed(0) : 0}%</p></CardContent></Card>
          </div>
        )}

        {/* Pipeline Funnel */}
        {stats && (
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-base">Hiring Pipeline</CardTitle></CardHeader>
            <CardContent>
              <div className="flex items-center gap-2 overflow-x-auto pb-2">
                {pipelineStages.map((stage, i) => {
                  const count = stats.pipeline_breakdown?.[stage] || 0;
                  const s = STAGES.find(st => st.value === stage);
                  return (
                    <React.Fragment key={stage}>
                      <div className={`flex-1 min-w-[100px] text-center p-3 rounded-lg ${s?.color || 'bg-slate-100'}`} data-testid={`pipeline-${stage}`}>
                        <p className="text-2xl font-bold">{count}</p>
                        <p className="text-xs font-medium">{s?.label}</p>
                      </div>
                      {i < pipelineStages.length - 1 && <ArrowRight className="w-4 h-4 text-slate-300 flex-shrink-0" />}
                    </React.Fragment>
                  );
                })}
                <ArrowRight className="w-4 h-4 text-slate-300 flex-shrink-0" />
                <div className="flex-1 min-w-[100px] text-center p-3 rounded-lg bg-green-100 text-green-700">
                  <p className="text-2xl font-bold">{stats.pipeline_breakdown?.hired || 0}</p>
                  <p className="text-xs font-medium">Hired</p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Tabs */}
        <div className="flex gap-1 bg-slate-100 p-1 rounded-lg w-fit">
          {['pipeline', 'jobs'].map(tab => (
            <button key={tab} className={`px-4 py-2 rounded-md text-sm font-medium transition capitalize ${activeTab === tab ? 'bg-white shadow text-slate-800' : 'text-slate-500'}`}
              onClick={() => setActiveTab(tab)} data-testid={`tab-${tab}`}>
              {tab === 'pipeline' ? 'Candidates' : 'Job Openings'}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-blue-600" /></div>
        ) : (
          <>
            {/* CANDIDATES TAB */}
            {activeTab === 'pipeline' && (
              <Card>
                <CardHeader className="pb-3">
                  <div className="flex flex-wrap items-center gap-3">
                    <CardTitle className="text-base">Candidates</CardTitle>
                    <Select value={selectedJob} onValueChange={setSelectedJob}>
                      <SelectTrigger className="w-44 h-8 text-xs"><SelectValue placeholder="All Jobs" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All Jobs</SelectItem>
                        {jobs.map(j => <SelectItem key={j.id} value={j.id}>{j.title}</SelectItem>)}
                      </SelectContent>
                    </Select>
                    <Select value={selectedStage} onValueChange={setSelectedStage}>
                      <SelectTrigger className="w-36 h-8 text-xs"><SelectValue placeholder="All Stages" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All Stages</SelectItem>
                        {STAGES.map(s => <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>)}
                      </SelectContent>
                    </Select>
                    <div className="relative">
                      <Search className="w-3 h-3 absolute left-2 top-1/2 -translate-y-1/2 text-slate-400" />
                      <Input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search..." className="w-40 h-8 text-xs pl-7" data-testid="candidate-search" />
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  {candidates.length === 0 ? (
                    <p className="text-slate-400 text-sm text-center py-8">No candidates found</p>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead><tr className="border-b text-left text-slate-500 text-xs"><th className="pb-2 font-medium">Candidate</th><th className="pb-2 font-medium">Job</th><th className="pb-2 font-medium">Stage</th><th className="pb-2 font-medium">Source</th><th className="pb-2 font-medium">Experience</th><th className="pb-2 font-medium">Actions</th></tr></thead>
                        <tbody>
                          {candidates.map(c => (
                            <tr key={c.id} className="border-b hover:bg-slate-50" data-testid={`candidate-row-${c.id}`}>
                              <td className="py-3"><p className="font-medium">{c.name}</p><p className="text-xs text-slate-400">{c.email}</p></td>
                              <td className="py-3 text-xs">{c.job_title}</td>
                              <td className="py-3">
                                <Select value={c.stage} onValueChange={v => updateCandidateStage(c.id, v)}>
                                  <SelectTrigger className="w-28 h-7 text-xs border-0 p-0">{getStageBadge(c.stage)}</SelectTrigger>
                                  <SelectContent>
                                    {STAGES.map(s => <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>)}
                                  </SelectContent>
                                </Select>
                              </td>
                              <td className="py-3 text-xs capitalize">{c.source?.replace('_', ' ')}</td>
                              <td className="py-3 text-xs">{c.experience || '-'}</td>
                              <td className="py-3">
                                <Button size="sm" variant="ghost" className="h-7 text-xs text-red-500" onClick={() => deleteCandidate(c.id)}><Trash2 className="w-3 h-3" /></Button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            {/* JOBS TAB */}
            {activeTab === 'jobs' && (
              <Card>
                <CardHeader className="pb-3"><CardTitle className="text-base">Job Openings</CardTitle></CardHeader>
                <CardContent>
                  {jobs.length === 0 ? (
                    <p className="text-slate-400 text-sm text-center py-8">No job openings yet</p>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead><tr className="border-b text-left text-slate-500 text-xs"><th className="pb-2 font-medium">Title</th><th className="pb-2 font-medium">Department</th><th className="pb-2 font-medium">Type</th><th className="pb-2 font-medium">Vacancies</th><th className="pb-2 font-medium">Candidates</th><th className="pb-2 font-medium">Hired</th><th className="pb-2 font-medium">Status</th><th className="pb-2 font-medium">Actions</th></tr></thead>
                        <tbody>
                          {jobs.map(j => (
                            <tr key={j.id} className="border-b hover:bg-slate-50" data-testid={`job-row-${j.id}`}>
                              <td className="py-3 font-medium">{j.title}</td>
                              <td className="py-3 text-xs">{j.department_name}</td>
                              <td className="py-3 text-xs capitalize">{j.employment_type?.replace('_', ' ')}</td>
                              <td className="py-3">{j.vacancies}</td>
                              <td className="py-3">{j.candidate_count}</td>
                              <td className="py-3 text-green-700 font-medium">{j.hired_count}</td>
                              <td className="py-3">
                                <span className={`px-2 py-0.5 rounded text-xs font-medium ${j.status === 'open' ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-600'}`}>{j.status}</span>
                              </td>
                              <td className="py-3">
                                <div className="flex gap-1">
                                  <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => toggleJobStatus(j)}>
                                    {j.status === 'open' ? 'Close' : 'Reopen'}
                                  </Button>
                                  <Button size="sm" variant="ghost" className="h-7 text-xs text-red-500" onClick={() => deleteJob(j.id)}><Trash2 className="w-3 h-3" /></Button>
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}
          </>
        )}
      </div>

      {/* Job Dialog */}
      <Dialog open={jobDialog} onOpenChange={setJobDialog}>
        <DialogContent className="sm:max-w-lg max-h-[80vh] overflow-y-auto" data-testid="job-dialog">
          <DialogHeader><DialogTitle>New Job Opening</DialogTitle></DialogHeader>
          <div className="space-y-4 pt-2">
            <div><Label>Job Title</Label><Input value={jobForm.title} onChange={e => setJobForm({ ...jobForm, title: e.target.value })} placeholder="e.g., Warehouse Supervisor" data-testid="job-title" /></div>
            <div><Label>Department</Label>
              <Select value={jobForm.department_id} onValueChange={v => setJobForm({ ...jobForm, department_id: v })}>
                <SelectTrigger><SelectValue placeholder="Select department" /></SelectTrigger>
                <SelectContent>{departments.map(d => <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Location</Label><Input value={jobForm.location} onChange={e => setJobForm({ ...jobForm, location: e.target.value })} placeholder="City" /></div>
              <div><Label>Vacancies</Label><Input type="number" min={1} value={jobForm.vacancies} onChange={e => setJobForm({ ...jobForm, vacancies: Number(e.target.value) })} /></div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Employment Type</Label>
                <Select value={jobForm.employment_type} onValueChange={v => setJobForm({ ...jobForm, employment_type: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="full_time">Full Time</SelectItem>
                    <SelectItem value="part_time">Part Time</SelectItem>
                    <SelectItem value="contract">Contract</SelectItem>
                    <SelectItem value="intern">Intern</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div><Label>Experience Required</Label><Input value={jobForm.experience_required} onChange={e => setJobForm({ ...jobForm, experience_required: e.target.value })} placeholder="e.g., 2-3 years" /></div>
            </div>
            <div><Label>Salary Range</Label><Input value={jobForm.salary_range} onChange={e => setJobForm({ ...jobForm, salary_range: e.target.value })} placeholder="e.g., 15,000 - 25,000" /></div>
            <div><Label>Description</Label><textarea className="w-full border rounded-lg p-2 text-sm min-h-[60px]" value={jobForm.description} onChange={e => setJobForm({ ...jobForm, description: e.target.value })} placeholder="Job description..." /></div>
            <Button className="w-full" onClick={saveJob} disabled={saving || !jobForm.title || !jobForm.department_id} data-testid="save-job-btn">
              {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Briefcase className="w-4 h-4 mr-2" />} Create Job
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Candidate Dialog */}
      <Dialog open={candidateDialog} onOpenChange={setCandidateDialog}>
        <DialogContent className="sm:max-w-lg max-h-[80vh] overflow-y-auto" data-testid="candidate-dialog">
          <DialogHeader><DialogTitle>Add Candidate</DialogTitle></DialogHeader>
          <div className="space-y-4 pt-2">
            <div><Label>Full Name</Label><Input value={candForm.name} onChange={e => setCandForm({ ...candForm, name: e.target.value })} placeholder="Candidate name" data-testid="candidate-name" /></div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Email</Label><Input type="email" value={candForm.email} onChange={e => setCandForm({ ...candForm, email: e.target.value })} placeholder="Email" /></div>
              <div><Label>Phone</Label><Input value={candForm.phone} onChange={e => setCandForm({ ...candForm, phone: e.target.value })} placeholder="Phone" /></div>
            </div>
            <div><Label>Job Position</Label>
              <Select value={candForm.job_id} onValueChange={v => setCandForm({ ...candForm, job_id: v })}>
                <SelectTrigger><SelectValue placeholder="Select job" /></SelectTrigger>
                <SelectContent>{jobs.filter(j => j.status === 'open').map(j => <SelectItem key={j.id} value={j.id}>{j.title}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Experience</Label><Input value={candForm.experience} onChange={e => setCandForm({ ...candForm, experience: e.target.value })} placeholder="e.g., 3 years" /></div>
              <div><Label>Source</Label>
                <Select value={candForm.source} onValueChange={v => setCandForm({ ...candForm, source: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>{SOURCES.map(s => <SelectItem key={s} value={s}>{s.replace('_', ' ')}</SelectItem>)}</SelectContent>
                </Select>
              </div>
            </div>
            <div><Label>Current Company</Label><Input value={candForm.current_company} onChange={e => setCandForm({ ...candForm, current_company: e.target.value })} placeholder="Current employer" /></div>
            <div><Label>Expected Salary</Label><Input value={candForm.expected_salary} onChange={e => setCandForm({ ...candForm, expected_salary: e.target.value })} placeholder="Expected CTC" /></div>
            <div><Label>Notes</Label><textarea className="w-full border rounded-lg p-2 text-sm min-h-[60px]" value={candForm.resume_notes} onChange={e => setCandForm({ ...candForm, resume_notes: e.target.value })} placeholder="Resume highlights, notes..." /></div>
            <Button className="w-full" onClick={saveCandidate} disabled={saving || !candForm.name || !candForm.email || !candForm.job_id} data-testid="save-candidate-btn">
              {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <UserPlus className="w-4 h-4 mr-2" />} Add Candidate
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </HRMSLayout>
  );
};

export default HireAnalytics;
