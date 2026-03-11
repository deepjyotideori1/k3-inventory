import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Layout from '../components/Layout';
import { useAuth } from '../context/AuthContext';
import { getLatestClosing, createDailyReport, getWarehouseReceivedFromPlant, getTodayReport, updateDailyReport } from '../lib/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Separator } from '../components/ui/separator';
import { Badge } from '../components/ui/badge';
import { 
  Save,
  Loader2,
  AlertTriangle,
  Package,
  ArrowRight,
  Calculator,
  Truck,
  RefreshCw,
  CheckCircle,
  FileEdit,
  Send,
  FileText
} from 'lucide-react';
import { getTodayDate, formatDate } from '../lib/utils';
import { toast } from 'sonner';

const DailyEntry = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [savingDraft, setSavingDraft] = useState(false);
  const [loadingPlantDelivery, setLoadingPlantDelivery] = useState(false);
  const [plantDeliverySync, setPlantDeliverySync] = useState({ synced: false, date: null });
  const [existingReport, setExistingReport] = useState(null);
  const [isEditMode, setIsEditMode] = useState(false);
  const [formData, setFormData] = useState({
    date: getTodayDate(),
    opening_15kg_filled: 0,
    opening_21kg_filled: 0,
    opening_15kg_empty: 0,
    opening_21kg_empty: 0,
    sold_15kg_filled: 0,
    sold_21kg_filled: 0,
    refilling_15kg: 0,
    refilling_21kg: 0,
    refilling_plant_15kg: 0,
    refilling_plant_21kg: 0,
    received_from_plant_15kg: 0,
    received_from_plant_21kg: 0,
    closing_15kg_filled: 0,
    closing_21kg_filled: 0,
    closing_15kg_empty: 0,
    closing_21kg_empty: 0,
    remarks: ''
  });

  const [discrepancies, setDiscrepancies] = useState({
    closing_15kg_filled: 0,
    closing_21kg_filled: 0,
    closing_15kg_empty: 0,
    closing_21kg_empty: 0
  });

  // System-calculated closing stock (read-only)
  const [calculatedClosing, setCalculatedClosing] = useState({
    closing_15kg_filled: 0,
    closing_21kg_filled: 0,
    closing_15kg_empty: 0,
    closing_21kg_empty: 0
  });

  useEffect(() => {
    fetchInitialData();
  }, [user]);

  useEffect(() => {
    if (user?.warehouse_id && formData.date) {
      fetchPlantDeliveries(formData.date);
    }
  }, [user, formData.date]);

  useEffect(() => {
    calculateDiscrepancies();
  }, [formData]);

  const fetchInitialData = async () => {
    if (!user?.warehouse_id) return;
    
    try {
      // First check if there's an existing report for today
      const todayReportRes = await getTodayReport(user.warehouse_id, getTodayDate());
      
      if (todayReportRes.data) {
        // Existing report found - load it
        const report = todayReportRes.data;
        setExistingReport(report);
        setFormData({
          date: report.date,
          opening_15kg_filled: report.opening_15kg_filled || 0,
          opening_21kg_filled: report.opening_21kg_filled || 0,
          opening_15kg_empty: report.opening_15kg_empty || 0,
          opening_21kg_empty: report.opening_21kg_empty || 0,
          sold_15kg_filled: report.sold_15kg_filled || 0,
          sold_21kg_filled: report.sold_21kg_filled || 0,
          refilling_15kg: report.refilling_15kg || 0,
          refilling_21kg: report.refilling_21kg || 0,
          refilling_plant_15kg: report.refilling_plant_15kg || 0,
          refilling_plant_21kg: report.refilling_plant_21kg || 0,
          received_from_plant_15kg: report.received_from_plant_15kg || 0,
          received_from_plant_21kg: report.received_from_plant_21kg || 0,
          closing_15kg_filled: report.closing_15kg_filled || 0,
          closing_21kg_filled: report.closing_21kg_filled || 0,
          closing_15kg_empty: report.closing_15kg_empty || 0,
          closing_21kg_empty: report.closing_21kg_empty || 0,
          remarks: report.remarks || ''
        });
        
        // If it's a draft, enable edit mode
        if (report.status === 'draft') {
          setIsEditMode(true);
        }
      } else {
        // No existing report - fetch opening stock from previous day
        const openingRes = await getLatestClosing(user.warehouse_id);
        setFormData(prev => ({
          ...prev,
          opening_15kg_filled: openingRes.data.opening_15kg_filled || 0,
          opening_21kg_filled: openingRes.data.opening_21kg_filled || 0,
          opening_15kg_empty: openingRes.data.opening_15kg_empty || 0,
          opening_21kg_empty: openingRes.data.opening_21kg_empty || 0
        }));
      }
    } catch (error) {
      console.error('Failed to fetch initial data:', error);
      // Fallback to opening stock
      try {
        const response = await getLatestClosing(user.warehouse_id);
        setFormData(prev => ({
          ...prev,
          opening_15kg_filled: response.data.opening_15kg_filled || 0,
          opening_21kg_filled: response.data.opening_21kg_filled || 0,
          opening_15kg_empty: response.data.opening_15kg_empty || 0,
          opening_21kg_empty: response.data.opening_21kg_empty || 0
        }));
      } catch (err) {
        console.error('Failed to fetch opening stock:', err);
      }
    } finally {
      setLoading(false);
    }
  };

  const fetchPlantDeliveries = async (date) => {
    if (!user?.warehouse_id) return;
    
    setLoadingPlantDelivery(true);
    try {
      const response = await getWarehouseReceivedFromPlant(user.warehouse_id, date);
      const data = response.data;
      
      // Only update if not editing existing report's plant delivery data
      if (!existingReport || existingReport.received_from_plant_15kg === 0) {
        setFormData(prev => ({
          ...prev,
          received_from_plant_15kg: data.received_15kg_filled || 0,
          received_from_plant_21kg: data.received_21kg_filled || 0
        }));
      }
      
      setPlantDeliverySync({
        synced: data.synced_from_plant,
        date: date
      });
    } catch (error) {
      console.error('Failed to fetch plant deliveries:', error);
    } finally {
      setLoadingPlantDelivery(false);
    }
  };

  const calculateDiscrepancies = () => {
    // System-calculated expected closing stock
    // Formula for Filled: Opening - Sold - Refilling (local) + Received from Plant
    // Formula for Empty: Opening + Refilling (Local) - Refilling at Plant Hollongi
    const expected15kgFilled = formData.opening_15kg_filled - formData.sold_15kg_filled - formData.refilling_15kg + formData.received_from_plant_15kg;
    const expected21kgFilled = formData.opening_21kg_filled - formData.sold_21kg_filled - formData.refilling_21kg + formData.received_from_plant_21kg;
    const expected15kgEmpty = formData.opening_15kg_empty + formData.refilling_15kg - formData.refilling_plant_15kg;
    const expected21kgEmpty = formData.opening_21kg_empty + formData.refilling_21kg - formData.refilling_plant_21kg;

    // Update calculated closing stock (system-generated, read-only display)
    setCalculatedClosing({
      closing_15kg_filled: expected15kgFilled,
      closing_21kg_filled: expected21kgFilled,
      closing_15kg_empty: expected15kgEmpty,
      closing_21kg_empty: expected21kgEmpty
    });

    // Calculate discrepancies between actual and calculated
    setDiscrepancies({
      closing_15kg_filled: formData.closing_15kg_filled - expected15kgFilled,
      closing_21kg_filled: formData.closing_21kg_filled - expected21kgFilled,
      closing_15kg_empty: formData.closing_15kg_empty - expected15kgEmpty,
      closing_21kg_empty: formData.closing_21kg_empty - expected21kgEmpty
    });
  };

  const handleChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      [field]: field === 'remarks' ? value : parseInt(value) || 0
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);

    try {
      const reportData = {
        warehouse_id: user.warehouse_id,
        ...formData,
        status: 'submitted'
      };
      
      if (existingReport) {
        await updateDailyReport(existingReport.id, reportData);
      } else {
        await createDailyReport(reportData);
      }
      toast.success('Daily report submitted successfully!');
      navigate('/manager-dashboard');
    } catch (error) {
      console.error('Failed to submit report:', error);
      toast.error('Failed to submit report. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleSaveDraft = async () => {
    setSavingDraft(true);

    try {
      const reportData = {
        warehouse_id: user.warehouse_id,
        ...formData,
        status: 'draft'
      };
      
      if (existingReport) {
        await updateDailyReport(existingReport.id, reportData);
        setExistingReport({ ...existingReport, ...reportData, id: existingReport.id });
      } else {
        const response = await createDailyReport(reportData);
        setExistingReport(response.data);
      }
      setIsEditMode(true);
      toast.success('Report saved as draft!');
    } catch (error) {
      console.error('Failed to save draft:', error);
      toast.error('Failed to save draft. Please try again.');
    } finally {
      setSavingDraft(false);
    }
  };

  const handleEnableEdit = () => {
    setIsEditMode(true);
  };

  const hasDiscrepancy = Object.values(discrepancies).some(d => d !== 0);
  const isDraft = existingReport?.status === 'draft';
  const isSubmitted = existingReport?.status === 'submitted';

  if (loading) {
    return (
      <Layout>
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 animate-spin text-green-700" />
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="max-w-4xl mx-auto space-y-6" data-testid="daily-entry-page">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-slate-800">Daily Stock Entry</h1>
            <p className="text-slate-500 mt-1">{user?.warehouse_name} - {formatDate(formData.date)}</p>
          </div>
          {existingReport && (
            <div className="flex items-center gap-2">
              {isDraft && (
                <Badge className="bg-amber-100 text-amber-700 border-amber-300">
                  <FileText className="w-3 h-3 mr-1" />
                  Draft
                </Badge>
              )}
              {isSubmitted && (
                <Badge className="bg-green-100 text-green-700 border-green-300">
                  <CheckCircle className="w-3 h-3 mr-1" />
                  Submitted
                </Badge>
              )}
            </div>
          )}
        </div>

        {/* Submitted Report Notice */}
        {isSubmitted && !isEditMode && (
          <div className="p-4 bg-green-50 border border-green-200 rounded-lg flex items-center justify-between">
            <div className="flex items-center gap-3">
              <CheckCircle className="w-5 h-5 text-green-600" />
              <div>
                <p className="font-medium text-green-800">Report Already Submitted</p>
                <p className="text-sm text-green-700">Submitted by {existingReport?.submitted_by} at {new Date(existingReport?.submitted_at).toLocaleString()}</p>
              </div>
            </div>
            <Button 
              type="button"
              variant="outline"
              onClick={handleEnableEdit}
              className="border-green-300 text-green-700 hover:bg-green-100"
              data-testid="edit-submitted-btn"
            >
              <FileEdit className="w-4 h-4 mr-2" />
              Edit Report
            </Button>
          </div>
        )}

        {/* Draft Notice */}
        {isDraft && (
          <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg flex items-center gap-3">
            <FileText className="w-5 h-5 text-amber-600" />
            <div>
              <p className="font-medium text-amber-800">Draft Report</p>
              <p className="text-sm text-amber-700">This report is saved as draft. Complete the form and submit to finalize.</p>
            </div>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          {/* Opening Stock */}
          <Card className="mb-6" data-testid="opening-stock-section">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Package className="w-5 h-5 text-green-700" />
                Opening Stock (Day Start)
              </CardTitle>
              <CardDescription>Auto-filled from previous day's closing stock</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div>
                  <Label className="text-slate-600">15kg Filled</Label>
                  <Input 
                    type="number" 
                    value={formData.opening_15kg_filled}
                    onChange={(e) => handleChange('opening_15kg_filled', e.target.value)}
                    className="mt-1"
                    data-testid="opening-15kg-filled"
                  />
                </div>
                <div>
                  <Label className="text-slate-600">21kg Filled</Label>
                  <Input 
                    type="number" 
                    value={formData.opening_21kg_filled}
                    onChange={(e) => handleChange('opening_21kg_filled', e.target.value)}
                    className="mt-1"
                    data-testid="opening-21kg-filled"
                  />
                </div>
                <div>
                  <Label className="text-slate-600">15kg Empty</Label>
                  <Input 
                    type="number" 
                    value={formData.opening_15kg_empty}
                    onChange={(e) => handleChange('opening_15kg_empty', e.target.value)}
                    className="mt-1"
                    data-testid="opening-15kg-empty"
                  />
                </div>
                <div>
                  <Label className="text-slate-600">21kg Empty</Label>
                  <Input 
                    type="number" 
                    value={formData.opening_21kg_empty}
                    onChange={(e) => handleChange('opening_21kg_empty', e.target.value)}
                    className="mt-1"
                    data-testid="opening-21kg-empty"
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Day Activity */}
          <Card className="mb-6" data-testid="day-activity-section">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <ArrowRight className="w-5 h-5 text-blue-700" />
                Day Activity
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div>
                <h4 className="font-medium text-slate-700 mb-3">Sold Out (Filled Cylinders)</h4>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-slate-600">15kg Sold</Label>
                    <Input 
                      type="number" 
                      value={formData.sold_15kg_filled}
                      onChange={(e) => handleChange('sold_15kg_filled', e.target.value)}
                      className="mt-1"
                      data-testid="sold-15kg"
                    />
                  </div>
                  <div>
                    <Label className="text-slate-600">21kg Sold</Label>
                    <Input 
                      type="number" 
                      value={formData.sold_21kg_filled}
                      onChange={(e) => handleChange('sold_21kg_filled', e.target.value)}
                      className="mt-1"
                      data-testid="sold-21kg"
                    />
                  </div>
                </div>
              </div>

              <Separator />

              <div>
                <h4 className="font-medium text-slate-700 mb-3">Refilling (Local)</h4>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-slate-600">15kg Refilling</Label>
                    <Input 
                      type="number" 
                      value={formData.refilling_15kg}
                      onChange={(e) => handleChange('refilling_15kg', e.target.value)}
                      className="mt-1"
                      data-testid="refilling-15kg"
                    />
                  </div>
                  <div>
                    <Label className="text-slate-600">21kg Refilling</Label>
                    <Input 
                      type="number" 
                      value={formData.refilling_21kg}
                      onChange={(e) => handleChange('refilling_21kg', e.target.value)}
                      className="mt-1"
                      data-testid="refilling-21kg"
                    />
                  </div>
                </div>
              </div>

              <Separator />

              <div>
                <h4 className="font-medium text-slate-700 mb-3">Refilling at Plant Hollongi</h4>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-slate-600">15kg at Plant</Label>
                    <Input 
                      type="number" 
                      value={formData.refilling_plant_15kg}
                      onChange={(e) => handleChange('refilling_plant_15kg', e.target.value)}
                      className="mt-1"
                      data-testid="refilling-plant-15kg"
                    />
                  </div>
                  <div>
                    <Label className="text-slate-600">21kg at Plant</Label>
                    <Input 
                      type="number" 
                      value={formData.refilling_plant_21kg}
                      onChange={(e) => handleChange('refilling_plant_21kg', e.target.value)}
                      className="mt-1"
                      data-testid="refilling-plant-21kg"
                    />
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Delivery Received from Plant */}
          <Card className="mb-6 border-2 border-green-200 bg-green-50" data-testid="delivery-received-section">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-lg flex items-center gap-2">
                    <Truck className="w-5 h-5 text-green-700" />
                    Delivery Received from Plant (Filled Cylinders)
                  </CardTitle>
                  <CardDescription className="text-green-700">
                    Auto-synced from Plant Hollongi's "Delivery to Warehouses" entries
                  </CardDescription>
                </div>
                <Button 
                  type="button" 
                  variant="outline" 
                  size="sm"
                  onClick={() => fetchPlantDeliveries(formData.date)}
                  disabled={loadingPlantDelivery}
                  className="border-green-300 text-green-700"
                >
                  {loadingPlantDelivery ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                  <span className="ml-1">Refresh</span>
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {plantDeliverySync.synced && (formData.received_from_plant_15kg > 0 || formData.received_from_plant_21kg > 0) && (
                <div className="flex items-center gap-2 mb-4 p-2 bg-white rounded-lg border border-green-200">
                  <CheckCircle className="w-5 h-5 text-green-600" />
                  <span className="text-sm text-green-700">Synced from Plant Hollongi Report</span>
                </div>
              )}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label className="text-slate-600">15kg Filled Received</Label>
                  <Input 
                    type="number" 
                    value={formData.received_from_plant_15kg}
                    readOnly
                    className="mt-1 bg-green-100 font-semibold text-green-900"
                    data-testid="received-from-plant-15kg"
                  />
                </div>
                <div>
                  <Label className="text-slate-600">21kg Filled Received</Label>
                  <Input 
                    type="number" 
                    value={formData.received_from_plant_21kg}
                    readOnly
                    className="mt-1 bg-green-100 font-semibold text-green-900"
                    data-testid="received-from-plant-21kg"
                  />
                </div>
              </div>
              {!plantDeliverySync.synced && (
                <p className="text-xs text-slate-500 mt-3 italic">
                  No delivery data found. Plant Hollongi needs to submit their daily report with deliveries to this warehouse.
                </p>
              )}
            </CardContent>
          </Card>

          {/* System Calculated Closing Stock */}
          <Card className="mb-6" data-testid="calculated-closing-section">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Calculator className="w-5 h-5 text-blue-700" />
                System Calculated Closing Stock
              </CardTitle>
              <CardDescription>Auto-calculated based on opening stock and day activities (read-only)</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div>
                  <Label className="text-slate-600">15kg Filled</Label>
                  <Input 
                    type="number" 
                    value={calculatedClosing.closing_15kg_filled}
                    readOnly
                    className="mt-1 bg-blue-50 font-semibold text-blue-900"
                    data-testid="calculated-15kg-filled"
                  />
                </div>
                <div>
                  <Label className="text-slate-600">21kg Filled</Label>
                  <Input 
                    type="number" 
                    value={calculatedClosing.closing_21kg_filled}
                    readOnly
                    className="mt-1 bg-blue-50 font-semibold text-blue-900"
                    data-testid="calculated-21kg-filled"
                  />
                </div>
                <div>
                  <Label className="text-slate-600">15kg Empty</Label>
                  <Input 
                    type="number" 
                    value={calculatedClosing.closing_15kg_empty}
                    readOnly
                    className="mt-1 bg-blue-50 font-semibold text-blue-900"
                    data-testid="calculated-15kg-empty"
                  />
                </div>
                <div>
                  <Label className="text-slate-600">21kg Empty</Label>
                  <Input 
                    type="number" 
                    value={calculatedClosing.closing_21kg_empty}
                    readOnly
                    className="mt-1 bg-blue-50 font-semibold text-blue-900"
                    data-testid="calculated-21kg-empty"
                  />
                </div>
              </div>
              <p className="text-xs text-slate-500 mt-3 italic">
                Formula: Filled = Opening - Sold - Refilling (Local) + Received from Plant | Empty = Opening + Refilling (Local) - Refilling at Plant
              </p>
            </CardContent>
          </Card>

          {/* Actual Closing Stock */}
          <Card className="mb-6" data-testid="closing-stock-section">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Package className="w-5 h-5 text-orange-700" />
                Actual Closing Stock (Physical Count)
              </CardTitle>
              <CardDescription>Enter the actual physical count at end of day</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div>
                  <Label className="text-slate-600">15kg Filled</Label>
                  <Input 
                    type="number" 
                    value={formData.closing_15kg_filled}
                    onChange={(e) => handleChange('closing_15kg_filled', e.target.value)}
                    className="mt-1"
                    data-testid="closing-15kg-filled"
                  />
                  {discrepancies.closing_15kg_filled !== 0 && (
                    <p className={`text-xs mt-1 font-medium ${discrepancies.closing_15kg_filled > 0 ? 'text-green-600' : 'text-red-600'}`}>
                      Diff: {discrepancies.closing_15kg_filled > 0 ? '+' : ''}{discrepancies.closing_15kg_filled}
                    </p>
                  )}
                </div>
                <div>
                  <Label className="text-slate-600">21kg Filled</Label>
                  <Input 
                    type="number" 
                    value={formData.closing_21kg_filled}
                    onChange={(e) => handleChange('closing_21kg_filled', e.target.value)}
                    className="mt-1"
                    data-testid="closing-21kg-filled"
                  />
                  {discrepancies.closing_21kg_filled !== 0 && (
                    <p className={`text-xs mt-1 font-medium ${discrepancies.closing_21kg_filled > 0 ? 'text-green-600' : 'text-red-600'}`}>
                      Diff: {discrepancies.closing_21kg_filled > 0 ? '+' : ''}{discrepancies.closing_21kg_filled}
                    </p>
                  )}
                </div>
                <div>
                  <Label className="text-slate-600">15kg Empty</Label>
                  <Input 
                    type="number" 
                    value={formData.closing_15kg_empty}
                    onChange={(e) => handleChange('closing_15kg_empty', e.target.value)}
                    className="mt-1"
                    data-testid="closing-15kg-empty"
                  />
                  {discrepancies.closing_15kg_empty !== 0 && (
                    <p className={`text-xs mt-1 font-medium ${discrepancies.closing_15kg_empty > 0 ? 'text-green-600' : 'text-red-600'}`}>
                      Diff: {discrepancies.closing_15kg_empty > 0 ? '+' : ''}{discrepancies.closing_15kg_empty}
                    </p>
                  )}
                </div>
                <div>
                  <Label className="text-slate-600">21kg Empty</Label>
                  <Input 
                    type="number" 
                    value={formData.closing_21kg_empty}
                    onChange={(e) => handleChange('closing_21kg_empty', e.target.value)}
                    className="mt-1"
                    data-testid="closing-21kg-empty"
                  />
                  {discrepancies.closing_21kg_empty !== 0 && (
                    <p className={`text-xs mt-1 font-medium ${discrepancies.closing_21kg_empty > 0 ? 'text-green-600' : 'text-red-600'}`}>
                      Diff: {discrepancies.closing_21kg_empty > 0 ? '+' : ''}{discrepancies.closing_21kg_empty}
                    </p>
                  )}
                </div>
              </div>

              {hasDiscrepancy && (
                <div className="mt-4 p-4 bg-orange-50 border border-orange-200 rounded-lg flex items-start gap-3" data-testid="discrepancy-warning">
                  <AlertTriangle className="w-5 h-5 text-orange-600 mt-0.5" />
                  <div>
                    <p className="font-medium text-orange-800">Stock Discrepancy Detected</p>
                    <p className="text-sm text-orange-700">The actual closing stock differs from the system calculated stock. Please verify the counts or add a remark explaining the difference.</p>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Remarks */}
          <Card className="mb-6" data-testid="remarks-section">
            <CardHeader>
              <CardTitle className="text-lg">Remarks</CardTitle>
              <CardDescription>Add any notes or explanations (max 500 words)</CardDescription>
            </CardHeader>
            <CardContent>
              <Textarea 
                value={formData.remarks}
                onChange={(e) => handleChange('remarks', e.target.value)}
                placeholder="Enter any remarks or explanations for discrepancies..."
                className="min-h-[120px]"
                maxLength={2500}
                data-testid="remarks-input"
              />
              <p className="text-xs text-slate-500 mt-2">{formData.remarks.length}/2500 characters</p>
            </CardContent>
          </Card>

          {/* Submit Button */}
          <div className="flex justify-end gap-4">
            <Button 
              type="button" 
              variant="outline"
              onClick={() => navigate('/manager-dashboard')}
            >
              Cancel
            </Button>
            
            {/* Save as Draft Button - show when no report exists or report is draft */}
            {(!existingReport || isDraft) && (
              <Button 
                type="button"
                variant="outline"
                onClick={handleSaveDraft}
                disabled={savingDraft || submitting}
                className="border-amber-300 text-amber-700 hover:bg-amber-50"
                data-testid="save-draft-btn"
              >
                {savingDraft ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Saving...
                  </>
                ) : (
                  <>
                    <FileText className="w-4 h-4 mr-2" />
                    Save as Draft
                  </>
                )}
              </Button>
            )}
            
            {/* Submit Button - always show except when submitted and not in edit mode */}
            {(!isSubmitted || isEditMode) && (
              <Button 
                type="submit" 
                className="bg-green-700 hover:bg-green-800"
                disabled={submitting || savingDraft}
                data-testid="submit-report-btn"
              >
                {submitting ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Submitting...
                  </>
                ) : (
                  <>
                    <Send className="w-4 h-4 mr-2" />
                    {isSubmitted ? 'Update & Submit' : 'Submit Report'}
                  </>
                )}
              </Button>
            )}
          </div>
        </form>
      </div>
    </Layout>
  );
};

export default DailyEntry;
