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
import { formatDate } from '../lib/utils';
import {
  Target, Plus, Star, Edit, Trash2, Loader2, CheckCircle,
  FileText, TrendingUp, Award, ChevronDown, ChevronUp
} from 'lucide-react';

const RATING_LABELS = { 5: 'Excellent', 4: 'Good', 3: 'Average', 2: 'Below Average', 1: 'Poor' };
const RATING_COLORS = { 5: 'text-green-600', 4: 'text-blue-600', 3: 'text-amber-600', 2: 'text-orange-600', 1: 'text-red-600' };

const StarRating = ({ value, onChange, max = 5 }) => (
  <div className="flex gap-1">
    {Array.from({ length: max }, (_, i) => (
      <button key={i} type="button" onClick={() => onChange?.(i + 1)}
        className={`${i < value ? 'text-amber-400' : 'text-slate-200'} transition-colors hover:text-amber-300`}>
        <Star className="w-5 h-5 fill-current" />
      </button>
    ))}
  </div>
);

const PerformanceManagement = () => {
  const [activeTab, setActiveTab] = useState('cycles');
  const [cycles, setCycles] = useState([]);
  const [kpis, setKpis] = useState([]);
  const [reviews, setReviews] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedCycle, setSelectedCycle] = useState('');

  // Dialogs
  const [cycleDialog, setCycleDialog] = useState(false);
  const [kpiDialog, setKpiDialog] = useState(false);
  const [reviewDialog, setReviewDialog] = useState(false);
  const [cycleForm, setCycleForm] = useState({ name: '', start_date: '', end_date: '', description: '' });
  const [kpiForm, setKpiForm] = useState({ name: '', description: '', department_id: 'all', max_rating: 5, weightage: 1 });
  const [reviewForm, setReviewForm] = useState({ cycle_id: '', employee_id: '', ratings: [], manager_comments: '', goals: '' });
  const [saving, setSaving] = useState(false);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [cyclesRes, kpisRes, deptRes, empRes, statsRes] = await Promise.all([
        api.get('/hrms/appraisals/cycles'),
        api.get('/hrms/kpis'),
        api.get('/hrms/departments'),
        api.get('/hrms/employees?limit=200'),
        api.get('/hrms/performance/stats'),
      ]);
      setCycles(cyclesRes.data);
      setKpis(kpisRes.data);
      setDepartments(deptRes.data);
      setEmployees(empRes.data.employees || []);
      setStats(statsRes.data);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, []);

  const fetchReviews = useCallback(async () => {
    try {
      const params = {};
      if (selectedCycle) params.cycle_id = selectedCycle;
      const res = await api.get('/hrms/reviews', { params });
      setReviews(res.data);
    } catch (e) { console.error(e); }
  }, [selectedCycle]);

  useEffect(() => { fetchAll(); }, [fetchAll]);
  useEffect(() => { fetchReviews(); }, [fetchReviews]);

  const saveCycle = async () => {
    setSaving(true);
    try {
      await api.post('/hrms/appraisals/cycles', cycleForm);
      toast.success('Appraisal cycle created');
      setCycleDialog(false);
      setCycleForm({ name: '', start_date: '', end_date: '', description: '' });
      fetchAll();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
    setSaving(false);
  };

  const deleteCycle = async (id) => {
    if (!window.confirm('Delete this appraisal cycle?')) return;
    try {
      await api.delete(`/hrms/appraisals/cycles/${id}`);
      toast.success('Cycle deleted');
      fetchAll();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
  };

  const saveKpi = async () => {
    setSaving(true);
    try {
      await api.post('/hrms/kpis', kpiForm);
      toast.success('KPI created');
      setKpiDialog(false);
      setKpiForm({ name: '', description: '', department_id: 'all', max_rating: 5, weightage: 1 });
      fetchAll();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
    setSaving(false);
  };

  const deleteKpi = async (id) => {
    if (!window.confirm('Delete this KPI?')) return;
    try {
      await api.delete(`/hrms/kpis/${id}`);
      toast.success('KPI deleted');
      fetchAll();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
  };

  const openReviewDialog = () => {
    const defaultRatings = kpis.map(k => ({ kpi_id: k.id, kpi_name: k.name, rating: 0, weightage: k.weightage }));
    setReviewForm({ cycle_id: selectedCycle || (cycles[0]?.id || ''), employee_id: '', ratings: defaultRatings, manager_comments: '', goals: '' });
    setReviewDialog(true);
  };

  const updateReviewRating = (kpiIdx, rating) => {
    const updated = [...reviewForm.ratings];
    updated[kpiIdx].rating = rating;
    setReviewForm({ ...reviewForm, ratings: updated });
  };

  const saveReview = async () => {
    setSaving(true);
    try {
      await api.post('/hrms/reviews', reviewForm);
      toast.success('Review created');
      setReviewDialog(false);
      fetchReviews();
      fetchAll();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
    setSaving(false);
  };

  const deleteReview = async (id) => {
    if (!window.confirm('Delete this review?')) return;
    try {
      await api.delete(`/hrms/reviews/${id}`);
      toast.success('Review deleted');
      fetchReviews();
      fetchAll();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
  };

  const finalizeReview = async (id) => {
    try {
      await api.put(`/hrms/reviews/${id}`, { status: 'completed' });
      toast.success('Review finalized');
      fetchReviews();
      fetchAll();
    } catch (e) { toast.error('Failed to finalize'); }
  };

  const getRatingBadge = (rating) => {
    const rounded = Math.round(rating);
    const label = RATING_LABELS[rounded] || `${rating}`;
    const color = RATING_COLORS[rounded] || 'text-slate-600';
    return <span className={`font-semibold ${color}`}>{rating.toFixed(1)} - {label}</span>;
  };

  return (
    <HRMSLayout>
      <div className="space-y-6" data-testid="performance-management">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-slate-800">Performance Management</h1>
            <p className="text-slate-500 text-sm mt-1">KPIs, appraisals, and performance reviews</p>
          </div>
        </div>

        {/* Stats */}
        {stats && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <Card><CardContent className="p-4"><p className="text-xs text-slate-500 uppercase">Total Reviews</p><p className="text-2xl font-bold">{stats.total_reviews}</p></CardContent></Card>
            <Card><CardContent className="p-4"><p className="text-xs text-slate-500 uppercase">Completed</p><p className="text-2xl font-bold text-green-700">{stats.completed}</p></CardContent></Card>
            <Card><CardContent className="p-4"><p className="text-xs text-slate-500 uppercase">Avg Rating</p><p className="text-2xl font-bold text-blue-700">{stats.avg_rating ? stats.avg_rating.toFixed(1) : '-'}/5</p></CardContent></Card>
            <Card><CardContent className="p-4"><p className="text-xs text-slate-500 uppercase">Drafts</p><p className="text-2xl font-bold text-amber-600">{stats.drafts}</p></CardContent></Card>
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-1 bg-slate-100 p-1 rounded-lg w-fit">
          {['cycles', 'kpis', 'reviews'].map(tab => (
            <button key={tab} className={`px-4 py-2 rounded-md text-sm font-medium transition capitalize ${activeTab === tab ? 'bg-white shadow text-slate-800' : 'text-slate-500'}`}
              onClick={() => setActiveTab(tab)} data-testid={`tab-${tab}`}>
              {tab === 'cycles' ? 'Appraisal Cycles' : tab === 'kpis' ? 'KPIs' : 'Reviews'}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-blue-600" /></div>
        ) : (
          <>
            {/* CYCLES TAB */}
            {activeTab === 'cycles' && (
              <Card>
                <CardHeader className="pb-3 flex flex-row items-center justify-between">
                  <CardTitle className="text-base">Appraisal Cycles</CardTitle>
                  <Button size="sm" onClick={() => setCycleDialog(true)} data-testid="add-cycle-btn"><Plus className="w-4 h-4 mr-1" /> New Cycle</Button>
                </CardHeader>
                <CardContent>
                  {cycles.length === 0 ? (
                    <p className="text-slate-400 text-sm text-center py-8">No appraisal cycles created yet</p>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead><tr className="border-b text-left text-slate-500"><th className="pb-2 font-medium">Name</th><th className="pb-2 font-medium">Period</th><th className="pb-2 font-medium">Status</th><th className="pb-2 font-medium">Reviews</th><th className="pb-2 font-medium">Actions</th></tr></thead>
                        <tbody>
                          {cycles.map(c => (
                            <tr key={c.id} className="border-b hover:bg-slate-50" data-testid={`cycle-row-${c.id}`}>
                              <td className="py-3 font-medium">{c.name}</td>
                              <td className="py-3 text-slate-500 text-xs">{formatDate(c.start_date)} to {formatDate(c.end_date)}</td>
                              <td className="py-3"><span className={`px-2 py-0.5 rounded text-xs font-medium ${c.status === 'active' ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-600'}`}>{c.status}</span></td>
                              <td className="py-3">{c.review_count}</td>
                              <td className="py-3"><Button size="sm" variant="ghost" className="h-7 text-xs text-red-500" onClick={() => deleteCycle(c.id)}><Trash2 className="w-3 h-3" /></Button></td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            {/* KPIS TAB */}
            {activeTab === 'kpis' && (
              <Card>
                <CardHeader className="pb-3 flex flex-row items-center justify-between">
                  <CardTitle className="text-base">KPI Templates</CardTitle>
                  <Button size="sm" onClick={() => setKpiDialog(true)} data-testid="add-kpi-btn"><Plus className="w-4 h-4 mr-1" /> New KPI</Button>
                </CardHeader>
                <CardContent>
                  {kpis.length === 0 ? (
                    <p className="text-slate-400 text-sm text-center py-8">No KPIs defined yet</p>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead><tr className="border-b text-left text-slate-500"><th className="pb-2 font-medium">KPI</th><th className="pb-2 font-medium">Description</th><th className="pb-2 font-medium">Department</th><th className="pb-2 font-medium">Max Rating</th><th className="pb-2 font-medium">Weight</th><th className="pb-2 font-medium">Actions</th></tr></thead>
                        <tbody>
                          {kpis.map(k => (
                            <tr key={k.id} className="border-b hover:bg-slate-50" data-testid={`kpi-row-${k.id}`}>
                              <td className="py-3 font-medium">{k.name}</td>
                              <td className="py-3 text-slate-500 text-xs max-w-xs truncate">{k.description || '-'}</td>
                              <td className="py-3 text-xs">{k.department_id === 'all' ? 'All Depts' : departments.find(d => d.id === k.department_id)?.name || k.department_id}</td>
                              <td className="py-3">{k.max_rating}</td>
                              <td className="py-3">{k.weightage}x</td>
                              <td className="py-3"><Button size="sm" variant="ghost" className="h-7 text-xs text-red-500" onClick={() => deleteKpi(k.id)}><Trash2 className="w-3 h-3" /></Button></td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            {/* REVIEWS TAB */}
            {activeTab === 'reviews' && (
              <Card>
                <CardHeader className="pb-3 flex flex-row items-center justify-between">
                  <div className="flex items-center gap-3">
                    <CardTitle className="text-base">Performance Reviews</CardTitle>
                    <Select value={selectedCycle} onValueChange={setSelectedCycle}>
                      <SelectTrigger className="w-48 h-8 text-xs"><SelectValue placeholder="All Cycles" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="">All Cycles</SelectItem>
                        {cycles.map(c => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <Button size="sm" onClick={openReviewDialog} disabled={cycles.length === 0 || kpis.length === 0} data-testid="add-review-btn">
                    <Plus className="w-4 h-4 mr-1" /> New Review
                  </Button>
                </CardHeader>
                <CardContent>
                  {cycles.length === 0 || kpis.length === 0 ? (
                    <p className="text-slate-400 text-sm text-center py-8">Create appraisal cycles and KPIs first before adding reviews</p>
                  ) : reviews.length === 0 ? (
                    <p className="text-slate-400 text-sm text-center py-8">No reviews yet</p>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead><tr className="border-b text-left text-slate-500"><th className="pb-2 font-medium">Employee</th><th className="pb-2 font-medium">Dept</th><th className="pb-2 font-medium">Rating</th><th className="pb-2 font-medium">Status</th><th className="pb-2 font-medium">Reviewer</th><th className="pb-2 font-medium">Actions</th></tr></thead>
                        <tbody>
                          {reviews.map(r => (
                            <tr key={r.id} className="border-b hover:bg-slate-50" data-testid={`review-row-${r.id}`}>
                              <td className="py-3"><p className="font-medium">{r.employee_name}</p><p className="text-xs text-slate-400">{r.employee_code} - {r.designation}</p></td>
                              <td className="py-3 text-xs">{r.department}</td>
                              <td className="py-3">{getRatingBadge(r.overall_rating)}</td>
                              <td className="py-3"><span className={`px-2 py-0.5 rounded text-xs font-medium ${r.status === 'completed' ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'}`}>{r.status}</span></td>
                              <td className="py-3 text-xs text-slate-500">{r.reviewed_by}</td>
                              <td className="py-3">
                                <div className="flex gap-1">
                                  {r.status === 'draft' && <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => finalizeReview(r.id)}><CheckCircle className="w-3 h-3 mr-1" /> Complete</Button>}
                                  <Button size="sm" variant="ghost" className="h-7 text-xs text-red-500" onClick={() => deleteReview(r.id)}><Trash2 className="w-3 h-3" /></Button>
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

      {/* Cycle Dialog */}
      <Dialog open={cycleDialog} onOpenChange={setCycleDialog}>
        <DialogContent className="sm:max-w-md" data-testid="cycle-dialog">
          <DialogHeader><DialogTitle>New Appraisal Cycle</DialogTitle></DialogHeader>
          <div className="space-y-4 pt-2">
            <div><Label>Cycle Name</Label><Input value={cycleForm.name} onChange={e => setCycleForm({ ...cycleForm, name: e.target.value })} placeholder="e.g., Q1 2026 Review" data-testid="cycle-name" /></div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Start Date</Label><Input type="date" value={cycleForm.start_date} onChange={e => setCycleForm({ ...cycleForm, start_date: e.target.value })} /></div>
              <div><Label>End Date</Label><Input type="date" value={cycleForm.end_date} onChange={e => setCycleForm({ ...cycleForm, end_date: e.target.value })} /></div>
            </div>
            <div><Label>Description</Label><Input value={cycleForm.description} onChange={e => setCycleForm({ ...cycleForm, description: e.target.value })} placeholder="Optional description" /></div>
            <Button className="w-full" onClick={saveCycle} disabled={saving || !cycleForm.name || !cycleForm.start_date || !cycleForm.end_date} data-testid="save-cycle-btn">
              {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Plus className="w-4 h-4 mr-2" />} Create Cycle
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* KPI Dialog */}
      <Dialog open={kpiDialog} onOpenChange={setKpiDialog}>
        <DialogContent className="sm:max-w-md" data-testid="kpi-dialog">
          <DialogHeader><DialogTitle>New KPI</DialogTitle></DialogHeader>
          <div className="space-y-4 pt-2">
            <div><Label>KPI Name</Label><Input value={kpiForm.name} onChange={e => setKpiForm({ ...kpiForm, name: e.target.value })} placeholder="e.g., Communication Skills" data-testid="kpi-name" /></div>
            <div><Label>Description</Label><Input value={kpiForm.description} onChange={e => setKpiForm({ ...kpiForm, description: e.target.value })} placeholder="What does this KPI measure?" /></div>
            <div><Label>Department</Label>
              <Select value={kpiForm.department_id} onValueChange={v => setKpiForm({ ...kpiForm, department_id: v })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Departments</SelectItem>
                  {departments.map(d => <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Max Rating</Label><Input type="number" min={1} max={10} value={kpiForm.max_rating} onChange={e => setKpiForm({ ...kpiForm, max_rating: Number(e.target.value) })} /></div>
              <div><Label>Weightage</Label><Input type="number" step="0.1" min={0.1} value={kpiForm.weightage} onChange={e => setKpiForm({ ...kpiForm, weightage: Number(e.target.value) })} /></div>
            </div>
            <Button className="w-full" onClick={saveKpi} disabled={saving || !kpiForm.name} data-testid="save-kpi-btn">
              {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Plus className="w-4 h-4 mr-2" />} Create KPI
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Review Dialog */}
      <Dialog open={reviewDialog} onOpenChange={setReviewDialog}>
        <DialogContent className="sm:max-w-lg max-h-[80vh] overflow-y-auto" data-testid="review-dialog">
          <DialogHeader><DialogTitle>New Performance Review</DialogTitle></DialogHeader>
          <div className="space-y-4 pt-2">
            <div><Label>Appraisal Cycle</Label>
              <Select value={reviewForm.cycle_id} onValueChange={v => setReviewForm({ ...reviewForm, cycle_id: v })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{cycles.map(c => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div><Label>Employee</Label>
              <Select value={reviewForm.employee_id} onValueChange={v => setReviewForm({ ...reviewForm, employee_id: v })}>
                <SelectTrigger><SelectValue placeholder="Select employee" /></SelectTrigger>
                <SelectContent>{employees.map(e => <SelectItem key={e.id} value={e.id}>{e.employee_id} - {e.name}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="space-y-3 p-3 bg-slate-50 rounded-lg">
              <h4 className="font-semibold text-sm text-slate-700">KPI Ratings</h4>
              {reviewForm.ratings.map((r, i) => (
                <div key={i} className="flex items-center justify-between">
                  <span className="text-sm text-slate-600">{r.kpi_name} ({r.weightage}x)</span>
                  <StarRating value={r.rating} onChange={val => updateReviewRating(i, val)} />
                </div>
              ))}
            </div>
            <div><Label>Manager Comments</Label><textarea className="w-full border rounded-lg p-2 text-sm min-h-[60px]" value={reviewForm.manager_comments} onChange={e => setReviewForm({ ...reviewForm, manager_comments: e.target.value })} placeholder="Observations and feedback..." /></div>
            <div><Label>Goals for Next Period</Label><textarea className="w-full border rounded-lg p-2 text-sm min-h-[60px]" value={reviewForm.goals} onChange={e => setReviewForm({ ...reviewForm, goals: e.target.value })} placeholder="Key objectives..." /></div>
            <Button className="w-full" onClick={saveReview} disabled={saving || !reviewForm.cycle_id || !reviewForm.employee_id} data-testid="save-review-btn">
              {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Award className="w-4 h-4 mr-2" />} Save Review
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </HRMSLayout>
  );
};

export default PerformanceManagement;
