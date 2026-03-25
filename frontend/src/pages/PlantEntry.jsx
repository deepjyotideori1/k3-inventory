import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import Layout from '../components/Layout';
import { useAuth } from '../context/AuthContext';
import { getLatestPlantClosing, createPlantReport, getWarehouses, getDealers, issueCylindersToDealer, getPlantIssuanceHistory, getPlantAvailableStock } from '../lib/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Separator } from '../components/ui/separator';
import { Badge } from '../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogClose } from '../components/ui/dialog';
import { 
  Save,
  Loader2,
  Factory,
  Package,
  Truck,
  ArrowDownToLine,
  Plus,
  Trash2,
  AlertCircle,
  Send,
  Search,
  CheckCircle2,
  BarChart3
} from 'lucide-react';
import { getTodayDate, formatDate } from '../lib/utils';
import { toast } from 'sonner';

const PlantEntry = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [warehouses, setWarehouses] = useState([]);
  const [activeSection, setActiveSection] = useState(searchParams.get('tab') === 'issuance' ? 'issuance' : 'report');
  
  // Issuance state
  const [dealers, setDealers] = useState([]);
  const [dealerSearch, setDealerSearch] = useState('');
  const [availableStock, setAvailableStock] = useState({ available_15kg: 0, available_21kg: 0 });
  const [issuanceForm, setIssuanceForm] = useState({
    date: getTodayDate(),
    dealer_id: '',
    qty_15kg: 0,
    qty_21kg: 0,
    remarks: ''
  });
  const [issuanceHistory, setIssuanceHistory] = useState([]);
  const [issuingLoading, setIssuingLoading] = useState(false);
  const [successDialogOpen, setSuccessDialogOpen] = useState(false);
  const [lastIssuance, setLastIssuance] = useState(null);
  
  const [formData, setFormData] = useState({
    date: getTodayDate(),
    opening_bullet_tank_kg: 0,
    opening_15kg_filled: 0,
    opening_21kg_filled: 0,
    opening_15kg_empty: 0,
    opening_21kg_empty: 0,
    day_reloading_kg: 0,
    day_refilled_15kg: 0,
    day_refilled_21kg: 0,
    delivery_15kg: [],
    delivery_21kg: [],
    received_empty_15kg: [],
    received_empty_21kg: [],
    closing_bullet_tank_kg: 0,
    closing_15kg_filled: 0,
    closing_21kg_filled: 0,
    closing_15kg_empty: 0,
    closing_21kg_empty: 0,
    remarks: ''
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [openingRes, warehousesRes, dealersRes, stockRes, historyRes] = await Promise.all([
        getLatestPlantClosing(),
        getWarehouses(),
        getDealers(),
        getPlantAvailableStock(getTodayDate()),
        getPlantIssuanceHistory({ start_date: getTodayDate(), end_date: getTodayDate() })
      ]);
      
      const nonPlantWarehouses = warehousesRes.data.filter(w => !w.is_plant);
      setWarehouses(nonPlantWarehouses);
      setDealers(dealersRes.data || []);
      setAvailableStock(stockRes.data || { available_15kg: 0, available_21kg: 0 });
      setIssuanceHistory(historyRes.data || []);
      
      setFormData(prev => ({
        ...prev,
        opening_bullet_tank_kg: openingRes.data.opening_bullet_tank_kg || 0,
        opening_15kg_filled: openingRes.data.opening_15kg_filled || 0,
        opening_21kg_filled: openingRes.data.opening_21kg_filled || 0,
        opening_15kg_empty: openingRes.data.opening_15kg_empty || 0,
        opening_21kg_empty: openingRes.data.opening_21kg_empty || 0
      }));
    } catch (error) {
      console.error('Failed to fetch data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      [field]: field === 'remarks' ? value : parseFloat(value) || 0
    }));
  };

  const addDelivery = (type) => {
    const field = type === '15kg' ? 'delivery_15kg' : 'delivery_21kg';
    setFormData(prev => ({
      ...prev,
      [field]: [...prev[field], { warehouse_id: '', warehouse_name: '', quantity: 0 }]
    }));
  };

  const removeDelivery = (type, index) => {
    const field = type === '15kg' ? 'delivery_15kg' : 'delivery_21kg';
    setFormData(prev => ({
      ...prev,
      [field]: prev[field].filter((_, i) => i !== index)
    }));
  };

  const updateDelivery = (type, index, key, value) => {
    const field = type === '15kg' ? 'delivery_15kg' : 'delivery_21kg';
    setFormData(prev => {
      const updated = [...prev[field]];
      if (key === 'warehouse_id') {
        const warehouse = warehouses.find(w => w.id === value);
        updated[index] = { ...updated[index], warehouse_id: value, warehouse_name: warehouse?.name || '' };
      } else {
        updated[index] = { ...updated[index], [key]: parseInt(value) || 0 };
      }
      return { ...prev, [field]: updated };
    });
  };

  const addReceived = (type) => {
    const field = type === '15kg' ? 'received_empty_15kg' : 'received_empty_21kg';
    setFormData(prev => ({
      ...prev,
      [field]: [...prev[field], { warehouse_id: '', warehouse_name: '', quantity: 0 }]
    }));
  };

  const removeReceived = (type, index) => {
    const field = type === '15kg' ? 'received_empty_15kg' : 'received_empty_21kg';
    setFormData(prev => ({
      ...prev,
      [field]: prev[field].filter((_, i) => i !== index)
    }));
  };

  const updateReceived = (type, index, key, value) => {
    const field = type === '15kg' ? 'received_empty_15kg' : 'received_empty_21kg';
    setFormData(prev => {
      const updated = [...prev[field]];
      if (key === 'warehouse_id') {
        const warehouse = warehouses.find(w => w.id === value);
        updated[index] = { ...updated[index], warehouse_id: value, warehouse_name: warehouse?.name || '' };
      } else {
        updated[index] = { ...updated[index], [key]: parseInt(value) || 0 };
      }
      return { ...prev, [field]: updated };
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);

    try {
      await createPlantReport(formData);
      toast.success('Plant report submitted successfully!');
      navigate('/manager-dashboard');
    } catch (error) {
      console.error('Failed to submit report:', error);
      toast.error('Failed to submit report. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleIssuanceSubmit = async (e) => {
    e.preventDefault();
    if (!issuanceForm.dealer_id) {
      toast.error('Please select a dealer');
      return;
    }
    if (issuanceForm.qty_15kg <= 0 && issuanceForm.qty_21kg <= 0) {
      toast.error('Enter at least one cylinder quantity');
      return;
    }
    if (issuanceForm.qty_15kg > availableStock.available_15kg) {
      toast.error(`Insufficient 15kg stock. Available: ${availableStock.available_15kg}`);
      return;
    }
    if (issuanceForm.qty_21kg > availableStock.available_21kg) {
      toast.error(`Insufficient 21kg stock. Available: ${availableStock.available_21kg}`);
      return;
    }
    
    setIssuingLoading(true);
    try {
      const res = await issueCylindersToDealer(issuanceForm);
      setLastIssuance(res.data);
      setSuccessDialogOpen(true);
      
      // Refresh stock and history
      const [stockRes, historyRes] = await Promise.all([
        getPlantAvailableStock(issuanceForm.date),
        getPlantIssuanceHistory({ start_date: issuanceForm.date, end_date: issuanceForm.date })
      ]);
      setAvailableStock(stockRes.data);
      setIssuanceHistory(historyRes.data || []);
      
      // Reset form
      setIssuanceForm(prev => ({ ...prev, dealer_id: '', qty_15kg: 0, qty_21kg: 0, remarks: '' }));
      setDealerSearch('');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to issue cylinders');
    } finally {
      setIssuingLoading(false);
    }
  };

  const refreshIssuanceData = async (date) => {
    try {
      const [stockRes, historyRes] = await Promise.all([
        getPlantAvailableStock(date),
        getPlantIssuanceHistory({ start_date: date, end_date: date })
      ]);
      setAvailableStock(stockRes.data);
      setIssuanceHistory(historyRes.data || []);
    } catch {}
  };

  const filteredDealers = dealers.filter(d => 
    d.name.toLowerCase().includes(dealerSearch.toLowerCase()) ||
    d.contact?.toLowerCase().includes(dealerSearch.toLowerCase())
  );

  const selectedDealer = dealers.find(d => d.id === issuanceForm.dealer_id);

  // Calculate totals from warehouse received
  const totalReceivedFromWarehouses = {
    '15kg': formData.received_empty_15kg.reduce((sum, r) => sum + (r.quantity || 0), 0),
    '21kg': formData.received_empty_21kg.reduce((sum, r) => sum + (r.quantity || 0), 0)
  };

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
      <div className="max-w-4xl mx-auto space-y-6" data-testid="plant-entry-page">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-slate-800 flex items-center gap-3">
              <Factory className="w-8 h-8 text-green-700" />
              Plant Hollongi Entry
            </h1>
            <p className="text-slate-500 mt-1">{formatDate(formData.date)}</p>
          </div>
          <div>
            <Label className="text-slate-600 text-sm">Report Date</Label>
            <Input 
              type="date" 
              value={formData.date}
              onChange={(e) => setFormData(prev => ({ ...prev, date: e.target.value }))}
              className="mt-1 w-40"
            />
          </div>
        </div>

        {/* Section Tabs */}
        <div className="flex gap-2 border-b border-slate-200 pb-1">
          <Button
            variant={activeSection === 'report' ? 'default' : 'ghost'}
            size="sm"
            className={activeSection === 'report' ? 'bg-green-700 hover:bg-green-800' : ''}
            onClick={() => setActiveSection('report')}
            data-testid="tab-daily-report"
          >
            <BarChart3 className="w-4 h-4 mr-1.5" />
            Daily Report
          </Button>
          <Button
            variant={activeSection === 'issuance' ? 'default' : 'ghost'}
            size="sm"
            className={activeSection === 'issuance' ? 'bg-blue-700 hover:bg-blue-800' : ''}
            onClick={() => setActiveSection('issuance')}
            data-testid="tab-cylinder-issuance"
          >
            <Send className="w-4 h-4 mr-1.5" />
            Cylinder Issuance (Filled)
          </Button>
        </div>

        {/* =========== CYLINDER ISSUANCE SECTION =========== */}
        {activeSection === 'issuance' && (
          <div className="space-y-6" data-testid="issuance-section">
            {/* Available Stock Reference */}
            <Card className="border-2 border-blue-200 bg-blue-50">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg flex items-center gap-2">
                  <Package className="w-5 h-5 text-blue-700" />
                  Current Available Filled Stock
                </CardTitle>
                <CardDescription className="text-blue-600">
                  Reference stock available for issuance (as of latest report)
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-3 bg-white rounded-lg border border-blue-200 text-center" data-testid="stock-15kg">
                    <p className="text-sm text-slate-500">15 Kg Filled</p>
                    <p className="text-3xl font-bold text-blue-800">{availableStock.available_15kg}</p>
                    {availableStock.issued_today_15kg > 0 && (
                      <p className="text-xs text-amber-600 mt-1">Issued today: {availableStock.issued_today_15kg}</p>
                    )}
                  </div>
                  <div className="p-3 bg-white rounded-lg border border-blue-200 text-center" data-testid="stock-21kg">
                    <p className="text-sm text-slate-500">21 Kg Filled</p>
                    <p className="text-3xl font-bold text-blue-800">{availableStock.available_21kg}</p>
                    {availableStock.issued_today_21kg > 0 && (
                      <p className="text-xs text-amber-600 mt-1">Issued today: {availableStock.issued_today_21kg}</p>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Issuance Form */}
            <Card className="border-2 border-green-200">
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Send className="w-5 h-5 text-green-700" />
                  New Cylinder Issuance (Filled)
                </CardTitle>
                <CardDescription>Issue filled LPG cylinders to dealers</CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleIssuanceSubmit} className="space-y-5">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label>Date</Label>
                      <Input
                        type="date"
                        value={issuanceForm.date}
                        onChange={(e) => {
                          setIssuanceForm(prev => ({ ...prev, date: e.target.value }));
                          refreshIssuanceData(e.target.value);
                        }}
                        className="mt-1"
                        data-testid="issuance-date"
                      />
                    </div>
                    <div>
                      <Label>Select Dealer *</Label>
                      <div className="relative mt-1">
                        <div className="flex items-center border rounded-md bg-white px-3">
                          <Search className="w-4 h-4 text-slate-400 shrink-0" />
                          <input
                            type="text"
                            placeholder="Search dealer..."
                            value={selectedDealer ? selectedDealer.name : dealerSearch}
                            onChange={(e) => {
                              setDealerSearch(e.target.value);
                              if (issuanceForm.dealer_id) {
                                setIssuanceForm(prev => ({ ...prev, dealer_id: '' }));
                              }
                            }}
                            onFocus={() => {
                              if (selectedDealer) {
                                setDealerSearch(selectedDealer.name);
                                setIssuanceForm(prev => ({ ...prev, dealer_id: '' }));
                              }
                            }}
                            className="w-full py-2 px-2 text-sm outline-none bg-transparent"
                            data-testid="dealer-search-input"
                          />
                        </div>
                        {dealerSearch && !issuanceForm.dealer_id && (
                          <div className="absolute z-10 w-full mt-1 bg-white border rounded-md shadow-lg max-h-48 overflow-y-auto">
                            {filteredDealers.length > 0 ? filteredDealers.map(d => (
                              <button
                                key={d.id}
                                type="button"
                                className="w-full text-left px-3 py-2 hover:bg-slate-100 text-sm border-b last:border-b-0"
                                onClick={() => {
                                  setIssuanceForm(prev => ({ ...prev, dealer_id: d.id }));
                                  setDealerSearch('');
                                }}
                                data-testid={`dealer-option-${d.id}`}
                              >
                                <span className="font-medium">{d.name}</span>
                                {d.contact && <span className="text-slate-400 ml-2">{d.contact}</span>}
                              </button>
                            )) : (
                              <p className="px-3 py-2 text-sm text-slate-500">No dealers found</p>
                            )}
                          </div>
                        )}
                      </div>
                      {selectedDealer && (
                        <Badge variant="outline" className="mt-1.5 text-green-700 border-green-300 bg-green-50">
                          <CheckCircle2 className="w-3 h-3 mr-1" />{selectedDealer.name}
                        </Badge>
                      )}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label>15 Kg Cylinders</Label>
                      <Input
                        type="number"
                        min="0"
                        value={issuanceForm.qty_15kg}
                        onChange={(e) => setIssuanceForm(prev => ({ ...prev, qty_15kg: parseInt(e.target.value) || 0 }))}
                        className="mt-1"
                        data-testid="issuance-qty-15kg"
                      />
                      <p className="text-xs text-slate-400 mt-1">Available: {availableStock.available_15kg}</p>
                    </div>
                    <div>
                      <Label>21 Kg Cylinders</Label>
                      <Input
                        type="number"
                        min="0"
                        value={issuanceForm.qty_21kg}
                        onChange={(e) => setIssuanceForm(prev => ({ ...prev, qty_21kg: parseInt(e.target.value) || 0 }))}
                        className="mt-1"
                        data-testid="issuance-qty-21kg"
                      />
                      <p className="text-xs text-slate-400 mt-1">Available: {availableStock.available_21kg}</p>
                    </div>
                  </div>

                  <div>
                    <Label>Remarks</Label>
                    <Input
                      value={issuanceForm.remarks}
                      onChange={(e) => setIssuanceForm(prev => ({ ...prev, remarks: e.target.value }))}
                      placeholder="Optional remarks..."
                      className="mt-1"
                      data-testid="issuance-remarks"
                    />
                  </div>

                  <Button
                    type="submit"
                    className="w-full bg-green-700 hover:bg-green-800"
                    disabled={issuingLoading || !issuanceForm.dealer_id}
                    data-testid="submit-issuance-btn"
                  >
                    {issuingLoading ? (
                      <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Issuing...</>
                    ) : (
                      <><Send className="w-4 h-4 mr-2" />Issue Cylinders to Dealer</>
                    )}
                  </Button>
                </form>
              </CardContent>
            </Card>

            {/* Today's Issuance History */}
            <Card data-testid="issuance-history-card">
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Truck className="w-5 h-5 text-slate-600" />
                  Today's Issuance History
                </CardTitle>
              </CardHeader>
              <CardContent>
                {issuanceHistory.length === 0 ? (
                  <div className="text-center py-6">
                    <AlertCircle className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                    <p className="text-slate-400 text-sm">No issuances recorded today</p>
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b bg-slate-50">
                          <th className="text-left p-2 font-medium text-slate-600">Dealer</th>
                          <th className="text-center p-2 font-medium text-slate-600">15 Kg</th>
                          <th className="text-center p-2 font-medium text-slate-600">21 Kg</th>
                          <th className="text-left p-2 font-medium text-slate-600">Remarks</th>
                          <th className="text-left p-2 font-medium text-slate-600">By</th>
                        </tr>
                      </thead>
                      <tbody>
                        {issuanceHistory.map(entry => (
                          <tr key={entry.id} className="border-b hover:bg-slate-50">
                            <td className="p-2 font-medium">{entry.dealer_name}</td>
                            <td className="p-2 text-center">{entry.qty_15kg}</td>
                            <td className="p-2 text-center">{entry.qty_21kg}</td>
                            <td className="p-2 text-slate-500">{entry.remarks || '-'}</td>
                            <td className="p-2 text-slate-500">{entry.submitted_by}</td>
                          </tr>
                        ))}
                        <tr className="bg-slate-100 font-semibold">
                          <td className="p-2">Total</td>
                          <td className="p-2 text-center">{issuanceHistory.reduce((s, e) => s + e.qty_15kg, 0)}</td>
                          <td className="p-2 text-center">{issuanceHistory.reduce((s, e) => s + e.qty_21kg, 0)}</td>
                          <td className="p-2" colSpan={2}></td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Success Dialog */}
            <Dialog open={successDialogOpen} onOpenChange={setSuccessDialogOpen}>
              <DialogContent className="max-w-sm">
                <DialogHeader>
                  <DialogTitle className="flex items-center gap-2 text-green-700">
                    <CheckCircle2 className="w-5 h-5" />
                    Cylinders Issued Successfully
                  </DialogTitle>
                  <DialogDescription>
                    Entry has been created for the dealer automatically.
                  </DialogDescription>
                </DialogHeader>
                {lastIssuance && (
                  <div className="py-3 space-y-2 text-sm">
                    <p><strong>Dealer:</strong> {lastIssuance.dealer_name}</p>
                    <p><strong>Date:</strong> {formatDate(lastIssuance.date)}</p>
                    {lastIssuance.qty_15kg > 0 && <p><strong>15 Kg:</strong> {lastIssuance.qty_15kg} cylinders</p>}
                    {lastIssuance.qty_21kg > 0 && <p><strong>21 Kg:</strong> {lastIssuance.qty_21kg} cylinders</p>}
                  </div>
                )}
                <DialogFooter>
                  <DialogClose asChild>
                    <Button className="bg-green-700 hover:bg-green-800" data-testid="close-success-dialog">OK</Button>
                  </DialogClose>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        )}

        {/* =========== DAILY REPORT SECTION =========== */}
        {activeSection === 'report' && (
        <form onSubmit={handleSubmit}>
          {/* Opening Stock */}
          <Card className="mb-6" data-testid="plant-opening-section">
            <CardHeader>
              <CardTitle className="text-lg">Opening Stock</CardTitle>
              <CardDescription>Auto-filled from previous day's closing</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="mb-4">
                <Label className="text-slate-600">Bullet Tank Stock (kg)</Label>
                <Input 
                  type="number" 
                  step="0.01"
                  value={formData.opening_bullet_tank_kg}
                  onChange={(e) => handleChange('opening_bullet_tank_kg', e.target.value)}
                  className="mt-1 max-w-xs"
                  data-testid="opening-bullet-tank"
                />
              </div>
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

          {/* Day Refilling */}
          <Card className="mb-6" data-testid="day-refilling-section">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Package className="w-5 h-5 text-blue-700" />
                Day Refilling at Plant
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label className="text-slate-600">15kg Refilled</Label>
                  <Input 
                    type="number" 
                    value={formData.day_refilled_15kg}
                    onChange={(e) => handleChange('day_refilled_15kg', e.target.value)}
                    className="mt-1"
                    data-testid="day-refilled-15kg"
                  />
                </div>
                <div>
                  <Label className="text-slate-600">21kg Refilled</Label>
                  <Input 
                    type="number" 
                    value={formData.day_refilled_21kg}
                    onChange={(e) => handleChange('day_refilled_21kg', e.target.value)}
                    className="mt-1"
                    data-testid="day-refilled-21kg"
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Day Reloading */}
          <Card className="mb-6 border-2 border-cyan-200 bg-cyan-50" data-testid="day-reloading-section">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Factory className="w-5 h-5 text-cyan-700" />
                Day Reloading
              </CardTitle>
              <CardDescription className="text-cyan-700">
                Enter the amount of gas reloaded into the bullet tank
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="max-w-xs">
                <Label className="text-slate-600">Reloading Quantity (kg)</Label>
                <Input 
                  type="number" 
                  step="0.01"
                  value={formData.day_reloading_kg}
                  onChange={(e) => handleChange('day_reloading_kg', e.target.value)}
                  className="mt-1"
                  placeholder="Enter kg"
                  data-testid="day-reloading-kg"
                />
              </div>
            </CardContent>
          </Card>

          {/* Empty Received from Warehouses */}
          <Card className="mb-6 border-2 border-amber-200 bg-amber-50" data-testid="received-section">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <ArrowDownToLine className="w-5 h-5 text-amber-700" />
                Empty Received from Warehouses
              </CardTitle>
              <CardDescription className="text-amber-700">
                Enter empty cylinders received from warehouses
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* 15kg Received Details */}
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h4 className="font-medium text-slate-700">15kg Empty Received</h4>
                  <Button type="button" variant="outline" size="sm" onClick={() => addReceived('15kg')}>
                    <Plus className="w-4 h-4 mr-1" /> Add Entry
                  </Button>
                </div>
                {formData.received_empty_15kg.length === 0 ? (
                  <div className="p-4 bg-slate-50 rounded-lg text-center">
                    <AlertCircle className="w-6 h-6 text-slate-400 mx-auto mb-2" />
                    <p className="text-slate-500 text-sm">No 15kg empties added</p>
                    <p className="text-slate-400 text-xs mt-1">Click "Add Entry" to add received empties</p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {formData.received_empty_15kg.map((item, idx) => (
                      <div key={idx} className="flex items-center gap-2 p-2 bg-white rounded-lg border border-amber-200">
                        <Select 
                          value={item.warehouse_id} 
                          onValueChange={(val) => updateReceived('15kg', idx, 'warehouse_id', val)}
                        >
                          <SelectTrigger className="w-40">
                            <SelectValue placeholder="Select warehouse" />
                          </SelectTrigger>
                          <SelectContent>
                            {warehouses.map(w => (
                              <SelectItem key={w.id} value={w.id}>{w.name}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <Input 
                          type="number" 
                          placeholder="Qty"
                          value={item.quantity}
                          onChange={(e) => updateReceived('15kg', idx, 'quantity', e.target.value)}
                          className="w-24"
                        />
                        <span className="text-sm text-slate-500">units</span>
                        <Button type="button" variant="ghost" size="icon" onClick={() => removeReceived('15kg', idx)}>
                          <Trash2 className="w-4 h-4 text-red-500" />
                        </Button>
                      </div>
                    ))}
                    <div className="flex justify-end pt-2 border-t border-amber-200">
                      <span className="font-semibold text-amber-800">Total: {totalReceivedFromWarehouses['15kg']} units</span>
                    </div>
                  </div>
                )}
              </div>

              <Separator className="bg-amber-200" />

              {/* 21kg Received Details */}
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h4 className="font-medium text-slate-700">21kg Empty Received</h4>
                  <Button type="button" variant="outline" size="sm" onClick={() => addReceived('21kg')}>
                    <Plus className="w-4 h-4 mr-1" /> Add Entry
                  </Button>
                </div>
                {formData.received_empty_21kg.length === 0 ? (
                  <div className="p-4 bg-slate-50 rounded-lg text-center">
                    <AlertCircle className="w-6 h-6 text-slate-400 mx-auto mb-2" />
                    <p className="text-slate-500 text-sm">No 21kg empties added</p>
                    <p className="text-slate-400 text-xs mt-1">Click "Add Entry" to add received empties</p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {formData.received_empty_21kg.map((item, idx) => (
                      <div key={idx} className="flex items-center gap-2 p-2 bg-white rounded-lg border border-amber-200">
                        <Select 
                          value={item.warehouse_id} 
                          onValueChange={(val) => updateReceived('21kg', idx, 'warehouse_id', val)}
                        >
                          <SelectTrigger className="w-40">
                            <SelectValue placeholder="Select warehouse" />
                          </SelectTrigger>
                          <SelectContent>
                            {warehouses.map(w => (
                              <SelectItem key={w.id} value={w.id}>{w.name}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <Input 
                          type="number" 
                          placeholder="Qty"
                          value={item.quantity}
                          onChange={(e) => updateReceived('21kg', idx, 'quantity', e.target.value)}
                          className="w-24"
                        />
                        <span className="text-sm text-slate-500">units</span>
                        <Button type="button" variant="ghost" size="icon" onClick={() => removeReceived('21kg', idx)}>
                          <Trash2 className="w-4 h-4 text-red-500" />
                        </Button>
                      </div>
                    ))}
                    <div className="flex justify-end pt-2 border-t border-amber-200">
                      <span className="font-semibold text-amber-800">Total: {totalReceivedFromWarehouses['21kg']} units</span>
                    </div>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Delivery to Warehouses */}
          <Card className="mb-6" data-testid="delivery-section">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Truck className="w-5 h-5 text-green-700" />
                Delivery to Warehouses (Filled Cylinders)
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* 15kg Deliveries */}
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h4 className="font-medium text-slate-700">15kg Delivery</h4>
                  <Button type="button" variant="outline" size="sm" onClick={() => addDelivery('15kg')}>
                    <Plus className="w-4 h-4 mr-1" /> Add
                  </Button>
                </div>
                {formData.delivery_15kg.length === 0 ? (
                  <p className="text-slate-500 text-sm">No 15kg deliveries added</p>
                ) : (
                  <div className="space-y-2">
                    {formData.delivery_15kg.map((item, idx) => (
                      <div key={idx} className="flex items-center gap-2">
                        <Select 
                          value={item.warehouse_id} 
                          onValueChange={(val) => updateDelivery('15kg', idx, 'warehouse_id', val)}
                        >
                          <SelectTrigger className="w-48">
                            <SelectValue placeholder="Select warehouse" />
                          </SelectTrigger>
                          <SelectContent>
                            {warehouses.map(w => (
                              <SelectItem key={w.id} value={w.id}>{w.name}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <Input 
                          type="number" 
                          placeholder="Qty"
                          value={item.quantity}
                          onChange={(e) => updateDelivery('15kg', idx, 'quantity', e.target.value)}
                          className="w-24"
                        />
                        <Button type="button" variant="ghost" size="icon" onClick={() => removeDelivery('15kg', idx)}>
                          <Trash2 className="w-4 h-4 text-red-500" />
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <Separator />

              {/* 21kg Deliveries */}
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h4 className="font-medium text-slate-700">21kg Delivery</h4>
                  <Button type="button" variant="outline" size="sm" onClick={() => addDelivery('21kg')}>
                    <Plus className="w-4 h-4 mr-1" /> Add
                  </Button>
                </div>
                {formData.delivery_21kg.length === 0 ? (
                  <p className="text-slate-500 text-sm">No 21kg deliveries added</p>
                ) : (
                  <div className="space-y-2">
                    {formData.delivery_21kg.map((item, idx) => (
                      <div key={idx} className="flex items-center gap-2">
                        <Select 
                          value={item.warehouse_id} 
                          onValueChange={(val) => updateDelivery('21kg', idx, 'warehouse_id', val)}
                        >
                          <SelectTrigger className="w-48">
                            <SelectValue placeholder="Select warehouse" />
                          </SelectTrigger>
                          <SelectContent>
                            {warehouses.map(w => (
                              <SelectItem key={w.id} value={w.id}>{w.name}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <Input 
                          type="number" 
                          placeholder="Qty"
                          value={item.quantity}
                          onChange={(e) => updateDelivery('21kg', idx, 'quantity', e.target.value)}
                          className="w-24"
                        />
                        <Button type="button" variant="ghost" size="icon" onClick={() => removeDelivery('21kg', idx)}>
                          <Trash2 className="w-4 h-4 text-red-500" />
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Closing Stock */}
          <Card className="mb-6" data-testid="plant-closing-section">
            <CardHeader>
              <CardTitle className="text-lg">Closing Stock</CardTitle>
              <CardDescription>Enter actual closing stock (will be opening for next day)</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="mb-4">
                <Label className="text-slate-600">Closing Bullet Tank Stock (kg)</Label>
                <Input 
                  type="number" 
                  step="0.01"
                  value={formData.closing_bullet_tank_kg}
                  onChange={(e) => handleChange('closing_bullet_tank_kg', e.target.value)}
                  className="mt-1 max-w-xs"
                  data-testid="closing-bullet-tank"
                />
              </div>
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
                </div>
              </div>
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
                className="min-h-[100px]"
                maxLength={2500}
                data-testid="remarks-input"
              />
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
              data-testid="submit-plant-report-btn"
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
        )}
      </div>
    </Layout>
  );
};

export default PlantEntry;
