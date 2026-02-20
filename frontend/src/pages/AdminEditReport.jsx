import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import Layout from '../components/Layout';
import { useAuth } from '../context/AuthContext';
import { getDailyReports, updateDailyReport, getWarehouseReceivedFromPlant } from '../lib/api';
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
  ArrowLeft,
  Shield
} from 'lucide-react';
import { formatDate } from '../lib/utils';
import { toast } from 'sonner';

const AdminEditReport = () => {
  const { reportId } = useParams();
  const { user, isAdmin } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [report, setReport] = useState(null);
  const [formData, setFormData] = useState({
    date: '',
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

  const [calculatedClosing, setCalculatedClosing] = useState({
    closing_15kg_filled: 0,
    closing_21kg_filled: 0,
    closing_15kg_empty: 0,
    closing_21kg_empty: 0
  });

  const [discrepancies, setDiscrepancies] = useState({
    closing_15kg_filled: 0,
    closing_21kg_filled: 0,
    closing_15kg_empty: 0,
    closing_21kg_empty: 0
  });

  useEffect(() => {
    if (!isAdmin) {
      navigate('/dashboard');
      return;
    }
    fetchReport();
  }, [reportId, isAdmin]);

  useEffect(() => {
    calculateDiscrepancies();
  }, [formData]);

  const fetchReport = async () => {
    try {
      // Fetch all reports and find the one we need
      const response = await getDailyReports({});
      const foundReport = response.data.find(r => r.id === reportId);
      
      if (!foundReport) {
        toast.error('Report not found');
        navigate('/reports');
        return;
      }
      
      setReport(foundReport);
      setFormData({
        date: foundReport.date,
        opening_15kg_filled: foundReport.opening_15kg_filled || 0,
        opening_21kg_filled: foundReport.opening_21kg_filled || 0,
        opening_15kg_empty: foundReport.opening_15kg_empty || 0,
        opening_21kg_empty: foundReport.opening_21kg_empty || 0,
        sold_15kg_filled: foundReport.sold_15kg_filled || 0,
        sold_21kg_filled: foundReport.sold_21kg_filled || 0,
        refilling_15kg: foundReport.refilling_15kg || 0,
        refilling_21kg: foundReport.refilling_21kg || 0,
        refilling_plant_15kg: foundReport.refilling_plant_15kg || 0,
        refilling_plant_21kg: foundReport.refilling_plant_21kg || 0,
        received_from_plant_15kg: foundReport.received_from_plant_15kg || 0,
        received_from_plant_21kg: foundReport.received_from_plant_21kg || 0,
        closing_15kg_filled: foundReport.closing_15kg_filled || 0,
        closing_21kg_filled: foundReport.closing_21kg_filled || 0,
        closing_15kg_empty: foundReport.closing_15kg_empty || 0,
        closing_21kg_empty: foundReport.closing_21kg_empty || 0,
        remarks: foundReport.remarks || ''
      });
    } catch (error) {
      console.error('Failed to fetch report:', error);
      toast.error('Failed to load report');
      navigate('/reports');
    } finally {
      setLoading(false);
    }
  };

  const calculateDiscrepancies = () => {
    // Formula: Filled = Opening - Sold - Refilling (local) + Received from Plant
    // Formula: Empty = Opening + Refilling (Local) - Refilling at Plant Hollongi
    const expected15kgFilled = formData.opening_15kg_filled - formData.sold_15kg_filled - formData.refilling_15kg + formData.received_from_plant_15kg;
    const expected21kgFilled = formData.opening_21kg_filled - formData.sold_21kg_filled - formData.refilling_21kg + formData.received_from_plant_21kg;
    const expected15kgEmpty = formData.opening_15kg_empty + formData.refilling_15kg - formData.refilling_plant_15kg;
    const expected21kgEmpty = formData.opening_21kg_empty + formData.refilling_21kg - formData.refilling_plant_21kg;

    setCalculatedClosing({
      closing_15kg_filled: expected15kgFilled,
      closing_21kg_filled: expected21kgFilled,
      closing_15kg_empty: expected15kgEmpty,
      closing_21kg_empty: expected21kgEmpty
    });

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
      await updateDailyReport(reportId, {
        warehouse_id: report.warehouse_id,
        ...formData,
        status: 'submitted'
      });
      toast.success('Report updated successfully!');
      navigate('/reports');
    } catch (error) {
      console.error('Failed to update report:', error);
      toast.error('Failed to update report. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const hasDiscrepancy = Object.values(discrepancies).some(d => d !== 0);

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
      <div className="max-w-4xl mx-auto space-y-6" data-testid="admin-edit-report-page">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <Button
              variant="ghost"
              onClick={() => navigate('/reports')}
              className="mb-2 -ml-2"
            >
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back to Reports
            </Button>
            <h1 className="text-3xl font-bold text-slate-800 flex items-center gap-2">
              <Shield className="w-8 h-8 text-blue-700" />
              Admin Edit Report
            </h1>
            <p className="text-slate-500 mt-1">{report?.warehouse_name} - {formatDate(formData.date)}</p>
          </div>
          <Badge className="bg-blue-100 text-blue-700 border-blue-300">
            <Shield className="w-3 h-3 mr-1" />
            Admin Edit Mode
          </Badge>
        </div>

        {/* Admin Notice */}
        <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg flex items-center gap-3">
          <Shield className="w-5 h-5 text-blue-600" />
          <div>
            <p className="font-medium text-blue-800">Admin Override</p>
            <p className="text-sm text-blue-700">You are editing this report as an administrator. Changes will be logged.</p>
          </div>
        </div>

        <form onSubmit={handleSubmit}>
          {/* Opening Stock */}
          <Card className="mb-6">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Package className="w-5 h-5 text-green-700" />
                Opening Stock
              </CardTitle>
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
                  />
                </div>
                <div>
                  <Label className="text-slate-600">21kg Filled</Label>
                  <Input 
                    type="number" 
                    value={formData.opening_21kg_filled}
                    onChange={(e) => handleChange('opening_21kg_filled', e.target.value)}
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label className="text-slate-600">15kg Empty</Label>
                  <Input 
                    type="number" 
                    value={formData.opening_15kg_empty}
                    onChange={(e) => handleChange('opening_15kg_empty', e.target.value)}
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label className="text-slate-600">21kg Empty</Label>
                  <Input 
                    type="number" 
                    value={formData.opening_21kg_empty}
                    onChange={(e) => handleChange('opening_21kg_empty', e.target.value)}
                    className="mt-1"
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Day Activity */}
          <Card className="mb-6">
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
                    />
                  </div>
                  <div>
                    <Label className="text-slate-600">21kg Sold</Label>
                    <Input 
                      type="number" 
                      value={formData.sold_21kg_filled}
                      onChange={(e) => handleChange('sold_21kg_filled', e.target.value)}
                      className="mt-1"
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
                    />
                  </div>
                  <div>
                    <Label className="text-slate-600">21kg Refilling</Label>
                    <Input 
                      type="number" 
                      value={formData.refilling_21kg}
                      onChange={(e) => handleChange('refilling_21kg', e.target.value)}
                      className="mt-1"
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
                    />
                  </div>
                  <div>
                    <Label className="text-slate-600">21kg at Plant</Label>
                    <Input 
                      type="number" 
                      value={formData.refilling_plant_21kg}
                      onChange={(e) => handleChange('refilling_plant_21kg', e.target.value)}
                      className="mt-1"
                    />
                  </div>
                </div>
              </div>

              <Separator />

              <div>
                <h4 className="font-medium text-slate-700 mb-3">Received from Plant (Filled)</h4>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-slate-600">15kg Received</Label>
                    <Input 
                      type="number" 
                      value={formData.received_from_plant_15kg}
                      onChange={(e) => handleChange('received_from_plant_15kg', e.target.value)}
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <Label className="text-slate-600">21kg Received</Label>
                    <Input 
                      type="number" 
                      value={formData.received_from_plant_21kg}
                      onChange={(e) => handleChange('received_from_plant_21kg', e.target.value)}
                      className="mt-1"
                    />
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* System Calculated Closing Stock */}
          <Card className="mb-6">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Calculator className="w-5 h-5 text-blue-700" />
                System Calculated Closing Stock
              </CardTitle>
              <CardDescription>Auto-calculated based on formula (read-only)</CardDescription>
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
                  />
                </div>
                <div>
                  <Label className="text-slate-600">21kg Filled</Label>
                  <Input 
                    type="number" 
                    value={calculatedClosing.closing_21kg_filled}
                    readOnly
                    className="mt-1 bg-blue-50 font-semibold text-blue-900"
                  />
                </div>
                <div>
                  <Label className="text-slate-600">15kg Empty</Label>
                  <Input 
                    type="number" 
                    value={calculatedClosing.closing_15kg_empty}
                    readOnly
                    className="mt-1 bg-blue-50 font-semibold text-blue-900"
                  />
                </div>
                <div>
                  <Label className="text-slate-600">21kg Empty</Label>
                  <Input 
                    type="number" 
                    value={calculatedClosing.closing_21kg_empty}
                    readOnly
                    className="mt-1 bg-blue-50 font-semibold text-blue-900"
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Actual Closing Stock */}
          <Card className="mb-6">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Package className="w-5 h-5 text-orange-700" />
                Actual Closing Stock (Physical Count)
              </CardTitle>
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
                  />
                  {discrepancies.closing_21kg_empty !== 0 && (
                    <p className={`text-xs mt-1 font-medium ${discrepancies.closing_21kg_empty > 0 ? 'text-green-600' : 'text-red-600'}`}>
                      Diff: {discrepancies.closing_21kg_empty > 0 ? '+' : ''}{discrepancies.closing_21kg_empty}
                    </p>
                  )}
                </div>
              </div>

              {hasDiscrepancy && (
                <div className="mt-4 p-4 bg-orange-50 border border-orange-200 rounded-lg flex items-start gap-3">
                  <AlertTriangle className="w-5 h-5 text-orange-600 mt-0.5" />
                  <div>
                    <p className="font-medium text-orange-800">Stock Discrepancy Detected</p>
                    <p className="text-sm text-orange-700">The actual closing stock differs from the system calculated stock.</p>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Remarks */}
          <Card className="mb-6">
            <CardHeader>
              <CardTitle className="text-lg">Remarks</CardTitle>
            </CardHeader>
            <CardContent>
              <Textarea 
                value={formData.remarks}
                onChange={(e) => handleChange('remarks', e.target.value)}
                placeholder="Enter any remarks..."
                className="min-h-[120px]"
                maxLength={2500}
              />
              <p className="text-xs text-slate-500 mt-2">{formData.remarks.length}/2500 characters</p>
            </CardContent>
          </Card>

          {/* Submit Button */}
          <div className="flex justify-end gap-4">
            <Button 
              type="button" 
              variant="outline"
              onClick={() => navigate('/reports')}
            >
              Cancel
            </Button>
            <Button 
              type="submit" 
              className="bg-blue-700 hover:bg-blue-800"
              disabled={submitting}
              data-testid="save-changes-btn"
            >
              {submitting ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="w-4 h-4 mr-2" />
                  Save Changes
                </>
              )}
            </Button>
          </div>
        </form>
      </div>
    </Layout>
  );
};

export default AdminEditReport;
