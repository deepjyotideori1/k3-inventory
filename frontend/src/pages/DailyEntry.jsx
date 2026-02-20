import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Layout from '../components/Layout';
import { useAuth } from '../context/AuthContext';
import { getLatestClosing, createDailyReport } from '../lib/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Separator } from '../components/ui/separator';
import { 
  Save,
  Loader2,
  AlertTriangle,
  Package,
  ArrowRight
} from 'lucide-react';
import { getTodayDate, formatDate } from '../lib/utils';
import { toast } from 'sonner';

const DailyEntry = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
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
    fetchOpeningStock();
  }, [user]);

  useEffect(() => {
    calculateDiscrepancies();
  }, [formData]);

  const fetchOpeningStock = async () => {
    if (!user?.warehouse_id) return;
    
    try {
      const response = await getLatestClosing(user.warehouse_id);
      setFormData(prev => ({
        ...prev,
        opening_15kg_filled: response.data.opening_15kg_filled || 0,
        opening_21kg_filled: response.data.opening_21kg_filled || 0,
        opening_15kg_empty: response.data.opening_15kg_empty || 0,
        opening_21kg_empty: response.data.opening_21kg_empty || 0
      }));
    } catch (error) {
      console.error('Failed to fetch opening stock:', error);
    } finally {
      setLoading(false);
    }
  };

  const calculateDiscrepancies = () => {
    // System-calculated expected closing stock
    // Formula: Opening + Received - Sold - Sent for refilling
    // For Filled: Opening - Sold + Refilling (local) + Refilling (from plant)
    // For Empty: Opening + Sold - Refilling (local) - Refilling (to plant)
    const expected15kgFilled = formData.opening_15kg_filled - formData.sold_15kg_filled + formData.refilling_15kg + formData.refilling_plant_15kg;
    const expected21kgFilled = formData.opening_21kg_filled - formData.sold_21kg_filled + formData.refilling_21kg + formData.refilling_plant_21kg;
    const expected15kgEmpty = formData.opening_15kg_empty + formData.sold_15kg_filled - formData.refilling_15kg - formData.refilling_plant_15kg;
    const expected21kgEmpty = formData.opening_21kg_empty + formData.sold_21kg_filled - formData.refilling_21kg - formData.refilling_plant_21kg;

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
      await createDailyReport({
        warehouse_id: user.warehouse_id,
        ...formData
      });
      toast.success('Daily report submitted successfully!');
      navigate('/manager-dashboard');
    } catch (error) {
      console.error('Failed to submit report:', error);
      toast.error('Failed to submit report. Please try again.');
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
      <div className="max-w-4xl mx-auto space-y-6" data-testid="daily-entry-page">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-slate-800">Daily Stock Entry</h1>
          <p className="text-slate-500 mt-1">{user?.warehouse_name} - {formatDate(formData.date)}</p>
        </div>

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

          {/* Closing Stock */}
          <Card className="mb-6" data-testid="closing-stock-section">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Package className="w-5 h-5 text-orange-700" />
                Closing Stock (Actual Count)
              </CardTitle>
              <CardDescription>Enter the actual physical count at end of day</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div>
                  <Label className="text-slate-600">15kg Filled Closing</Label>
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
                  <Label className="text-slate-600">21kg Filled Closing</Label>
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
                  <Label className="text-slate-600">15kg Empty Closing</Label>
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
                  <Label className="text-slate-600">21kg Empty Closing</Label>
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
                    <p className="text-sm text-orange-700">The actual closing stock differs from the calculated expected stock. Please verify the counts or add a remark explaining the difference.</p>
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
            <Button 
              type="submit" 
              className="bg-green-700 hover:bg-green-800"
              disabled={submitting}
              data-testid="submit-report-btn"
            >
              {submitting ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Submitting...
                </>
              ) : (
                <>
                  <Save className="w-4 h-4 mr-2" />
                  Submit Report
                </>
              )}
            </Button>
          </div>
        </form>
      </div>
    </Layout>
  );
};

export default DailyEntry;
