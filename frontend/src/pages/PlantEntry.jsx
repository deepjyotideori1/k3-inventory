import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Layout from '../components/Layout';
import { useAuth } from '../context/AuthContext';
import { getLatestPlantClosing, createPlantReport, getWarehouses, getPlantReceivedFromWarehouses, getWarehousesReceivedSummary } from '../lib/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Separator } from '../components/ui/separator';
import { Badge } from '../components/ui/badge';
import { 
  Save,
  Loader2,
  Factory,
  Package,
  Truck,
  ArrowDownToLine,
  Plus,
  Trash2,
  RefreshCw,
  AlertCircle,
  CheckCircle
} from 'lucide-react';
import { getTodayDate, formatDate } from '../lib/utils';
import { toast } from 'sonner';

const PlantEntry = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [warehouses, setWarehouses] = useState([]);
  const [warehouseReceived, setWarehouseReceived] = useState(null);
  const [warehousesReceivedSummary, setWarehousesReceivedSummary] = useState(null);
  const [loadingReceived, setLoadingReceived] = useState(false);
  const [loadingReceivedSummary, setLoadingReceivedSummary] = useState(false);
  
  const [formData, setFormData] = useState({
    date: getTodayDate(),
    opening_bullet_tank_kg: 0,
    opening_15kg_filled: 0,
    opening_21kg_filled: 0,
    opening_15kg_empty: 0,
    opening_21kg_empty: 0,
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

  useEffect(() => {
    if (formData.date) {
      fetchWarehouseReceived(formData.date);
      fetchWarehousesReceivedSummary(formData.date);
    }
  }, [formData.date]);

  const fetchData = async () => {
    try {
      const [openingRes, warehousesRes] = await Promise.all([
        getLatestPlantClosing(),
        getWarehouses()
      ]);
      
      const nonPlantWarehouses = warehousesRes.data.filter(w => !w.is_plant);
      setWarehouses(nonPlantWarehouses);
      
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

  const fetchWarehouseReceived = async (date) => {
    setLoadingReceived(true);
    try {
      const response = await getPlantReceivedFromWarehouses(date);
      setWarehouseReceived(response.data);
      
      // Auto-populate received empties from warehouse reports
      if (response.data) {
        setFormData(prev => ({
          ...prev,
          received_empty_15kg: response.data.received_15kg.map(r => ({
            warehouse_id: r.warehouse_id,
            warehouse_name: r.warehouse_name,
            quantity: r.quantity
          })),
          received_empty_21kg: response.data.received_21kg.map(r => ({
            warehouse_id: r.warehouse_id,
            warehouse_name: r.warehouse_name,
            quantity: r.quantity
          }))
        }));
      }
    } catch (error) {
      console.error('Failed to fetch warehouse received:', error);
    } finally {
      setLoadingReceived(false);
    }
  };

  // Fetch what warehouses recorded as received from plant (notification only)
  const fetchWarehousesReceivedSummary = async (date) => {
    setLoadingReceivedSummary(true);
    try {
      const response = await getWarehousesReceivedSummary(date);
      setWarehousesReceivedSummary(response.data);
    } catch (error) {
      console.error('Failed to fetch warehouses received summary:', error);
    } finally {
      setLoadingReceivedSummary(false);
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

          {/* Empty Received from Warehouses - AUTO SYNCED */}
          <Card className="mb-6 border-2 border-amber-200 bg-amber-50" data-testid="received-section">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-lg flex items-center gap-2">
                    <ArrowDownToLine className="w-5 h-5 text-amber-700" />
                    Empty Received from Warehouses
                  </CardTitle>
                  <CardDescription className="text-amber-700">
                    Auto-synced from warehouse "Refilling at Plant Hollongi" entries
                  </CardDescription>
                </div>
                <Button 
                  type="button" 
                  variant="outline" 
                  size="sm"
                  onClick={() => fetchWarehouseReceived(formData.date)}
                  disabled={loadingReceived}
                  className="border-amber-300 text-amber-700"
                >
                  {loadingReceived ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                  <span className="ml-1">Refresh</span>
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Warehouse Received Summary */}
              {warehouseReceived && (warehouseReceived.total_15kg > 0 || warehouseReceived.total_21kg > 0) && (
                <div className="p-4 bg-white rounded-lg border border-amber-200">
                  <div className="flex items-center gap-2 mb-3">
                    <CheckCircle className="w-5 h-5 text-green-600" />
                    <span className="font-medium text-slate-700">Synced from Warehouse Reports</span>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="p-3 bg-amber-50 rounded-lg text-center">
                      <p className="text-xs text-amber-700">Total 15kg Empty Received</p>
                      <p className="text-2xl font-bold text-amber-800">{warehouseReceived.total_15kg}</p>
                    </div>
                    <div className="p-3 bg-amber-50 rounded-lg text-center">
                      <p className="text-xs text-amber-700">Total 21kg Empty Received</p>
                      <p className="text-2xl font-bold text-amber-800">{warehouseReceived.total_21kg}</p>
                    </div>
                  </div>
                </div>
              )}

              {/* 15kg Received Details */}
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h4 className="font-medium text-slate-700">15kg Empty Received</h4>
                  <Button type="button" variant="outline" size="sm" onClick={() => addReceived('15kg')}>
                    <Plus className="w-4 h-4 mr-1" /> Add Manual Entry
                  </Button>
                </div>
                {formData.received_empty_15kg.length === 0 ? (
                  <div className="p-4 bg-slate-50 rounded-lg text-center">
                    <AlertCircle className="w-6 h-6 text-slate-400 mx-auto mb-2" />
                    <p className="text-slate-500 text-sm">No 15kg empties received from warehouses today</p>
                    <p className="text-slate-400 text-xs mt-1">Click "Add Manual Entry" to add received empties</p>
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
                    <Plus className="w-4 h-4 mr-1" /> Add Manual Entry
                  </Button>
                </div>
                {formData.received_empty_21kg.length === 0 ? (
                  <div className="p-4 bg-slate-50 rounded-lg text-center">
                    <AlertCircle className="w-6 h-6 text-slate-400 mx-auto mb-2" />
                    <p className="text-slate-500 text-sm">No 21kg empties received from warehouses today</p>
                    <p className="text-slate-400 text-xs mt-1">Click "Add Manual Entry" to add received empties</p>
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

          {/* Notification: What Warehouses Recorded as Received */}
          {warehousesReceivedSummary && (warehousesReceivedSummary.total_15kg > 0 || warehousesReceivedSummary.total_21kg > 0) && (
            <Card className="mb-6 border-2 border-blue-200 bg-blue-50" data-testid="warehouse-received-notification">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-lg flex items-center gap-2">
                      <AlertCircle className="w-5 h-5 text-blue-700" />
                      Warehouses Recorded Receipt (Reference)
                    </CardTitle>
                    <CardDescription className="text-blue-700">
                      What warehouses recorded as received from Plant for {formData.date}
                    </CardDescription>
                  </div>
                  <Button 
                    type="button" 
                    variant="outline" 
                    size="sm"
                    onClick={() => fetchWarehousesReceivedSummary(formData.date)}
                    disabled={loadingReceivedSummary}
                    className="border-blue-300 text-blue-700"
                  >
                    {loadingReceivedSummary ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* 15kg Received Summary */}
                  <div className="bg-white p-3 rounded-lg border border-blue-200">
                    <h4 className="font-medium text-blue-800 mb-2">15kg Filled Received by Warehouses</h4>
                    {warehousesReceivedSummary.received_15kg.length === 0 ? (
                      <p className="text-sm text-slate-500 italic">No records</p>
                    ) : (
                      <div className="space-y-1">
                        {warehousesReceivedSummary.received_15kg.map((item, idx) => (
                          <div key={idx} className="flex justify-between text-sm">
                            <span className="text-slate-700">{item.warehouse_name}</span>
                            <span className="font-semibold text-blue-700">{item.quantity} units</span>
                          </div>
                        ))}
                        <Separator className="my-2" />
                        <div className="flex justify-between font-semibold">
                          <span className="text-slate-800">Total</span>
                          <span className="text-blue-800">{warehousesReceivedSummary.total_15kg} units</span>
                        </div>
                      </div>
                    )}
                  </div>
                  
                  {/* 21kg Received Summary */}
                  <div className="bg-white p-3 rounded-lg border border-blue-200">
                    <h4 className="font-medium text-blue-800 mb-2">21kg Filled Received by Warehouses</h4>
                    {warehousesReceivedSummary.received_21kg.length === 0 ? (
                      <p className="text-sm text-slate-500 italic">No records</p>
                    ) : (
                      <div className="space-y-1">
                        {warehousesReceivedSummary.received_21kg.map((item, idx) => (
                          <div key={idx} className="flex justify-between text-sm">
                            <span className="text-slate-700">{item.warehouse_name}</span>
                            <span className="font-semibold text-blue-700">{item.quantity} units</span>
                          </div>
                        ))}
                        <Separator className="my-2" />
                        <div className="flex justify-between font-semibold">
                          <span className="text-slate-800">Total</span>
                          <span className="text-blue-800">{warehousesReceivedSummary.total_21kg} units</span>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
                <p className="text-xs text-blue-600 mt-3 italic">
                  This is what warehouses have recorded as received from Plant. Compare with your "Delivery to Warehouses" entries above.
                </p>
              </CardContent>
            </Card>
          )}

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
      </div>
    </Layout>
  );
};

export default PlantEntry;
