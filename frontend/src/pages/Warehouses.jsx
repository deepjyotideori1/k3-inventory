import React, { useState, useEffect } from 'react';
import Layout from '../components/Layout';
import { getWarehouses, createWarehouse, updateWarehouse, deleteWarehouse, updateStock, updatePlantStock, getDailyReports, getLatestPlantClosing } from '../lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Switch } from '../components/ui/switch';
import { Badge } from '../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { 
  Warehouse,
  Plus,
  Edit,
  Trash2,
  Loader2,
  Package,
  MapPin,
  Factory,
  AlertTriangle,
  Fuel
} from 'lucide-react';
import { formatDate } from '../lib/utils';
import { toast } from 'sonner';

const Warehouses = () => {
  const [warehouses, setWarehouses] = useState([]);
  const [plantStock, setPlantStock] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [showStockDialog, setShowStockDialog] = useState(false);
  const [showPlantStockDialog, setShowPlantStockDialog] = useState(false);
  const [selectedWarehouse, setSelectedWarehouse] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const [formData, setFormData] = useState({
    name: '',
    location: '',
    is_plant: false,
    is_active: true
  });

  const [stockForm, setStockForm] = useState({
    stock_15kg_filled: 0,
    stock_21kg_filled: 0,
    stock_15kg_empty: 0,
    stock_21kg_empty: 0,
    reason: ''
  });

  const [plantStockForm, setPlantStockForm] = useState({
    bullet_tank_kg: 0,
    stock_15kg_filled: 0,
    stock_21kg_filled: 0,
    stock_15kg_empty: 0,
    stock_21kg_empty: 0,
    reason: ''
  });

  useEffect(() => {
    fetchWarehouses();
  }, []);

  const fetchWarehouses = async () => {
    try {
      const response = await getWarehouses();
      
      // Get latest stock for each non-plant warehouse
      const warehousesWithStock = await Promise.all(
        response.data.map(async (w) => {
          if (w.is_plant) {
            // For plant, get plant stock separately
            return { ...w, current_stock: null };
          }
          try {
            const reportsRes = await getDailyReports({ warehouse_id: w.id });
            const latestReport = reportsRes.data[0];
            return {
              ...w,
              current_stock: latestReport ? {
                closing_15kg_filled: latestReport.closing_15kg_filled,
                closing_21kg_filled: latestReport.closing_21kg_filled,
                closing_15kg_empty: latestReport.closing_15kg_empty,
                closing_21kg_empty: latestReport.closing_21kg_empty,
                has_discrepancy: latestReport.has_discrepancy,
                last_report_date: latestReport.date
              } : null
            };
          } catch {
            return { ...w, current_stock: null };
          }
        })
      );
      
      // Get plant stock
      try {
        const plantRes = await getLatestPlantClosing();
        setPlantStock(plantRes.data);
      } catch {
        setPlantStock(null);
      }
      
      setWarehouses(warehousesWithStock);
    } catch (error) {
      console.error('Failed to fetch warehouses:', error);
      toast.error('Failed to load warehouses');
    } finally {
      setLoading(false);
    }
  };

  const handleAdd = async () => {
    setSubmitting(true);
    try {
      await createWarehouse(formData);
      toast.success('Warehouse added successfully');
      setShowAddDialog(false);
      setFormData({ name: '', location: '', is_plant: false, is_active: true });
      fetchWarehouses();
    } catch (error) {
      console.error('Failed to add warehouse:', error);
      toast.error('Failed to add warehouse');
    } finally {
      setSubmitting(false);
    }
  };

  const handleEdit = async () => {
    if (!selectedWarehouse) return;
    setSubmitting(true);
    try {
      await updateWarehouse(selectedWarehouse.id, formData);
      toast.success('Warehouse updated successfully');
      setShowEditDialog(false);
      setSelectedWarehouse(null);
      fetchWarehouses();
    } catch (error) {
      console.error('Failed to update warehouse:', error);
      toast.error('Failed to update warehouse');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (warehouse) => {
    if (!window.confirm(`Are you sure you want to delete ${warehouse.name}?`)) return;
    try {
      await deleteWarehouse(warehouse.id);
      toast.success('Warehouse deleted successfully');
      fetchWarehouses();
    } catch (error) {
      console.error('Failed to delete warehouse:', error);
      toast.error('Failed to delete warehouse');
    }
  };

  const handleUpdateStock = async () => {
    if (!selectedWarehouse) return;
    setSubmitting(true);
    try {
      await updateStock({
        warehouse_id: selectedWarehouse.id,
        ...stockForm
      });
      toast.success('Stock updated successfully');
      setShowStockDialog(false);
      setSelectedWarehouse(null);
      setStockForm({ stock_15kg_filled: 0, stock_21kg_filled: 0, stock_15kg_empty: 0, stock_21kg_empty: 0, reason: '' });
      fetchWarehouses();
    } catch (error) {
      console.error('Failed to update stock:', error);
      toast.error('Failed to update stock');
    } finally {
      setSubmitting(false);
    }
  };

  const handleUpdatePlantStock = async () => {
    setSubmitting(true);
    try {
      await updatePlantStock(plantStockForm);
      toast.success('Plant Hollongi stock updated successfully');
      setShowPlantStockDialog(false);
      setPlantStockForm({ bullet_tank_kg: 0, stock_15kg_filled: 0, stock_21kg_filled: 0, stock_15kg_empty: 0, stock_21kg_empty: 0, reason: '' });
      fetchWarehouses();
    } catch (error) {
      console.error('Failed to update plant stock:', error);
      toast.error('Failed to update plant stock');
    } finally {
      setSubmitting(false);
    }
  };

  const openEditDialog = (warehouse) => {
    setSelectedWarehouse(warehouse);
    setFormData({
      name: warehouse.name,
      location: warehouse.location,
      is_plant: warehouse.is_plant,
      is_active: warehouse.is_active
    });
    setShowEditDialog(true);
  };

  const openStockDialog = (warehouse) => {
    setSelectedWarehouse(warehouse);
    if (warehouse.current_stock) {
      setStockForm({
        stock_15kg_filled: warehouse.current_stock.closing_15kg_filled || 0,
        stock_21kg_filled: warehouse.current_stock.closing_21kg_filled || 0,
        stock_15kg_empty: warehouse.current_stock.closing_15kg_empty || 0,
        stock_21kg_empty: warehouse.current_stock.closing_21kg_empty || 0,
        reason: ''
      });
    }
    setShowStockDialog(true);
  };

  const openPlantStockDialog = () => {
    if (plantStock && plantStock.last_date) {
      setPlantStockForm({
        bullet_tank_kg: plantStock.opening_bullet_tank_kg || 0,
        stock_15kg_filled: plantStock.opening_15kg_filled || 0,
        stock_21kg_filled: plantStock.opening_21kg_filled || 0,
        stock_15kg_empty: plantStock.opening_15kg_empty || 0,
        stock_21kg_empty: plantStock.opening_21kg_empty || 0,
        reason: ''
      });
    }
    setShowPlantStockDialog(true);
  };

  // Separate plant and regular warehouses
  const regularWarehouses = warehouses.filter(w => !w.is_plant);
  const plantWarehouse = warehouses.find(w => w.is_plant);

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
      <div className="space-y-6" data-testid="warehouses-page">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold text-slate-800 flex items-center gap-2">
              <Warehouse className="w-8 h-8 text-green-700" />
              Warehouses
            </h1>
            <p className="text-slate-500 mt-1">Manage your warehouse locations</p>
          </div>
          <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
            <DialogTrigger asChild>
              <Button className="bg-green-700 hover:bg-green-800 gap-2" data-testid="add-warehouse-btn">
                <Plus className="w-4 h-4" />
                Add Warehouse
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Add New Warehouse</DialogTitle>
              </DialogHeader>
              <div className="space-y-4 py-4">
                <div>
                  <Label>Name</Label>
                  <Input 
                    value={formData.name}
                    onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                    placeholder="Enter warehouse name"
                    className="mt-1"
                    data-testid="warehouse-name-input"
                  />
                </div>
                <div>
                  <Label>Location</Label>
                  <Input 
                    value={formData.location}
                    onChange={(e) => setFormData(prev => ({ ...prev, location: e.target.value }))}
                    placeholder="Enter location"
                    className="mt-1"
                    data-testid="warehouse-location-input"
                  />
                </div>
                <div className="flex items-center gap-2">
                  <Switch 
                    checked={formData.is_plant}
                    onCheckedChange={(checked) => setFormData(prev => ({ ...prev, is_plant: checked }))}
                  />
                  <Label>Is Plant (Has Bullet Tank)</Label>
                </div>
                <div className="flex justify-end gap-2">
                  <Button variant="outline" onClick={() => setShowAddDialog(false)}>Cancel</Button>
                  <Button onClick={handleAdd} disabled={submitting} className="bg-green-700 hover:bg-green-800" data-testid="save-warehouse-btn">
                    {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Save'}
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
        </div>

        {/* Plant Hollongi Section */}
        {plantWarehouse && (
          <Card className="border-2 border-amber-200 bg-amber-50" data-testid="plant-hollongi-card">
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-14 h-14 rounded-xl bg-amber-100 flex items-center justify-center">
                    <Factory className="w-7 h-7 text-amber-700" />
                  </div>
                  <div>
                    <CardTitle className="text-xl text-amber-800">{plantWarehouse.name}</CardTitle>
                    <div className="flex items-center gap-1 text-sm text-amber-600 mt-0.5">
                      <MapPin className="w-3 h-3" />
                      {plantWarehouse.location}
                    </div>
                  </div>
                </div>
                <div className="flex gap-1">
                  <Button variant="ghost" size="icon" onClick={() => openEditDialog(plantWarehouse)}>
                    <Edit className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {plantStock && plantStock.last_date ? (
                <>
                  {/* Bullet Tank - Prominent Display */}
                  <div className="p-4 bg-amber-100 rounded-lg mb-4">
                    <div className="flex items-center gap-3">
                      <div className="w-12 h-12 rounded-full bg-amber-200 flex items-center justify-center">
                        <Fuel className="w-6 h-6 text-amber-700" />
                      </div>
                      <div>
                        <p className="text-sm text-amber-700 font-medium">Bullet Tank Stock</p>
                        <p className="text-3xl font-bold text-amber-800">{plantStock.opening_bullet_tank_kg} <span className="text-lg">kg</span></p>
                      </div>
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
                    <div className="p-3 bg-white rounded-lg text-center border border-amber-200">
                      <p className="text-xs text-slate-500">15kg Filled</p>
                      <p className="font-bold text-slate-800 text-lg">{plantStock.opening_15kg_filled}</p>
                    </div>
                    <div className="p-3 bg-white rounded-lg text-center border border-amber-200">
                      <p className="text-xs text-slate-500">21kg Filled</p>
                      <p className="font-bold text-slate-800 text-lg">{plantStock.opening_21kg_filled}</p>
                    </div>
                    <div className="p-3 bg-white rounded-lg text-center border border-amber-200">
                      <p className="text-xs text-slate-500">15kg Empty</p>
                      <p className="font-bold text-slate-800 text-lg">{plantStock.opening_15kg_empty}</p>
                    </div>
                    <div className="p-3 bg-white rounded-lg text-center border border-amber-200">
                      <p className="text-xs text-slate-500">21kg Empty</p>
                      <p className="font-bold text-slate-800 text-lg">{plantStock.opening_21kg_empty}</p>
                    </div>
                  </div>
                  
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-amber-600">
                      Last update: {formatDate(plantStock.last_date)}
                    </span>
                    <Button 
                      variant="outline" 
                      size="sm" 
                      className="border-amber-300 text-amber-700 hover:bg-amber-100"
                      onClick={openPlantStockDialog}
                      data-testid="update-plant-stock-btn"
                    >
                      <Package className="w-3 h-3 mr-1" />
                      Update Stock
                    </Button>
                  </div>
                </>
              ) : (
                <div className="text-center py-6">
                  <div className="w-16 h-16 rounded-full bg-amber-100 flex items-center justify-center mx-auto mb-3">
                    <Fuel className="w-8 h-8 text-amber-600" />
                  </div>
                  <p className="text-amber-700 font-medium">No stock data available</p>
                  <p className="text-amber-600 text-sm mt-1">Set initial stock for Plant Hollongi including Bullet Tank</p>
                  <Button 
                    className="mt-4 bg-amber-600 hover:bg-amber-700"
                    onClick={openPlantStockDialog}
                    data-testid="set-initial-plant-stock-btn"
                  >
                    <Package className="w-4 h-4 mr-2" />
                    Set Initial Stock
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Regular Warehouses Grid */}
        <div>
          <h2 className="text-lg font-semibold text-slate-700 mb-4">Distribution Warehouses</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {regularWarehouses.map((warehouse) => (
              <Card key={warehouse.id} className="card-hover" data-testid={`warehouse-card-${warehouse.id}`}>
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-12 h-12 rounded-xl bg-green-100 flex items-center justify-center">
                        <Warehouse className="w-6 h-6 text-green-700" />
                      </div>
                      <div>
                        <CardTitle className="text-lg">{warehouse.name}</CardTitle>
                        <div className="flex items-center gap-1 text-sm text-slate-500 mt-0.5">
                          <MapPin className="w-3 h-3" />
                          {warehouse.location}
                        </div>
                      </div>
                    </div>
                    <div className="flex gap-1">
                      <Button variant="ghost" size="icon" onClick={() => openEditDialog(warehouse)}>
                        <Edit className="w-4 h-4" />
                      </Button>
                      <Button variant="ghost" size="icon" onClick={() => handleDelete(warehouse)}>
                        <Trash2 className="w-4 h-4 text-red-500" />
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  {warehouse.current_stock ? (
                    <>
                      <div className="grid grid-cols-2 gap-3 mb-3">
                        <div className="p-3 bg-slate-50 rounded-lg text-center">
                          <p className="text-xs text-slate-500">15kg Filled</p>
                          <p className="font-bold text-slate-800">{warehouse.current_stock.closing_15kg_filled}</p>
                        </div>
                        <div className="p-3 bg-slate-50 rounded-lg text-center">
                          <p className="text-xs text-slate-500">21kg Filled</p>
                          <p className="font-bold text-slate-800">{warehouse.current_stock.closing_21kg_filled}</p>
                        </div>
                        <div className="p-3 bg-slate-50 rounded-lg text-center">
                          <p className="text-xs text-slate-500">15kg Empty</p>
                          <p className="font-bold text-slate-800">{warehouse.current_stock.closing_15kg_empty}</p>
                        </div>
                        <div className="p-3 bg-slate-50 rounded-lg text-center">
                          <p className="text-xs text-slate-500">21kg Empty</p>
                          <p className="font-bold text-slate-800">{warehouse.current_stock.closing_21kg_empty}</p>
                        </div>
                      </div>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          {warehouse.current_stock.has_discrepancy && (
                            <Badge variant="destructive" className="bg-red-100 text-red-700 text-xs">
                              <AlertTriangle className="w-3 h-3 mr-1" />
                              Discrepancy
                            </Badge>
                          )}
                          <span className="text-xs text-slate-500">
                            Last: {formatDate(warehouse.current_stock.last_report_date)}
                          </span>
                        </div>
                        <Button variant="outline" size="sm" onClick={() => openStockDialog(warehouse)} data-testid={`update-stock-${warehouse.id}`}>
                          <Package className="w-3 h-3 mr-1" />
                          Update Stock
                        </Button>
                      </div>
                    </>
                  ) : (
                    <div className="text-center py-4">
                      <p className="text-slate-500 text-sm">No stock data available</p>
                      <Button variant="outline" size="sm" className="mt-2" onClick={() => openStockDialog(warehouse)}>
                        <Package className="w-3 h-3 mr-1" />
                        Set Initial Stock
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* Edit Dialog */}
        <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Edit Warehouse</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div>
                <Label>Name</Label>
                <Input 
                  value={formData.name}
                  onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                  className="mt-1"
                />
              </div>
              <div>
                <Label>Location</Label>
                <Input 
                  value={formData.location}
                  onChange={(e) => setFormData(prev => ({ ...prev, location: e.target.value }))}
                  className="mt-1"
                />
              </div>
              <div className="flex items-center gap-2">
                <Switch 
                  checked={formData.is_plant}
                  onCheckedChange={(checked) => setFormData(prev => ({ ...prev, is_plant: checked }))}
                />
                <Label>Is Plant</Label>
              </div>
              <div className="flex items-center gap-2">
                <Switch 
                  checked={formData.is_active}
                  onCheckedChange={(checked) => setFormData(prev => ({ ...prev, is_active: checked }))}
                />
                <Label>Active</Label>
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setShowEditDialog(false)}>Cancel</Button>
                <Button onClick={handleEdit} disabled={submitting} className="bg-green-700 hover:bg-green-800">
                  {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Update'}
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>

        {/* Update Stock Dialog (Regular Warehouses) */}
        <Dialog open={showStockDialog} onOpenChange={setShowStockDialog}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Update Stock - {selectedWarehouse?.name}</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>15kg Filled</Label>
                  <Input 
                    type="number"
                    value={stockForm.stock_15kg_filled}
                    onChange={(e) => setStockForm(prev => ({ ...prev, stock_15kg_filled: parseInt(e.target.value) || 0 }))}
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label>21kg Filled</Label>
                  <Input 
                    type="number"
                    value={stockForm.stock_21kg_filled}
                    onChange={(e) => setStockForm(prev => ({ ...prev, stock_21kg_filled: parseInt(e.target.value) || 0 }))}
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label>15kg Empty</Label>
                  <Input 
                    type="number"
                    value={stockForm.stock_15kg_empty}
                    onChange={(e) => setStockForm(prev => ({ ...prev, stock_15kg_empty: parseInt(e.target.value) || 0 }))}
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label>21kg Empty</Label>
                  <Input 
                    type="number"
                    value={stockForm.stock_21kg_empty}
                    onChange={(e) => setStockForm(prev => ({ ...prev, stock_21kg_empty: parseInt(e.target.value) || 0 }))}
                    className="mt-1"
                  />
                </div>
              </div>
              <div>
                <Label>Reason for Update</Label>
                <Textarea 
                  value={stockForm.reason}
                  onChange={(e) => setStockForm(prev => ({ ...prev, reason: e.target.value }))}
                  placeholder="Enter reason for stock update..."
                  className="mt-1"
                />
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setShowStockDialog(false)}>Cancel</Button>
                <Button onClick={handleUpdateStock} disabled={submitting} className="bg-green-700 hover:bg-green-800">
                  {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Update Stock'}
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>

        {/* Update Plant Stock Dialog */}
        <Dialog open={showPlantStockDialog} onOpenChange={setShowPlantStockDialog}>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Factory className="w-5 h-5 text-amber-600" />
                Update Plant Hollongi Stock
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              {/* Bullet Tank - Prominent */}
              <div className="p-4 bg-amber-50 rounded-lg border border-amber-200">
                <Label className="text-amber-800 font-semibold flex items-center gap-2">
                  <Fuel className="w-4 h-4" />
                  Bullet Tank Stock (kg)
                </Label>
                <Input 
                  type="number"
                  step="0.01"
                  value={plantStockForm.bullet_tank_kg}
                  onChange={(e) => setPlantStockForm(prev => ({ ...prev, bullet_tank_kg: parseFloat(e.target.value) || 0 }))}
                  className="mt-2 text-lg font-semibold"
                  data-testid="bullet-tank-input"
                />
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>15kg Filled</Label>
                  <Input 
                    type="number"
                    value={plantStockForm.stock_15kg_filled}
                    onChange={(e) => setPlantStockForm(prev => ({ ...prev, stock_15kg_filled: parseInt(e.target.value) || 0 }))}
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label>21kg Filled</Label>
                  <Input 
                    type="number"
                    value={plantStockForm.stock_21kg_filled}
                    onChange={(e) => setPlantStockForm(prev => ({ ...prev, stock_21kg_filled: parseInt(e.target.value) || 0 }))}
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label>15kg Empty</Label>
                  <Input 
                    type="number"
                    value={plantStockForm.stock_15kg_empty}
                    onChange={(e) => setPlantStockForm(prev => ({ ...prev, stock_15kg_empty: parseInt(e.target.value) || 0 }))}
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label>21kg Empty</Label>
                  <Input 
                    type="number"
                    value={plantStockForm.stock_21kg_empty}
                    onChange={(e) => setPlantStockForm(prev => ({ ...prev, stock_21kg_empty: parseInt(e.target.value) || 0 }))}
                    className="mt-1"
                  />
                </div>
              </div>
              <div>
                <Label>Reason for Update</Label>
                <Textarea 
                  value={plantStockForm.reason}
                  onChange={(e) => setPlantStockForm(prev => ({ ...prev, reason: e.target.value }))}
                  placeholder="Enter reason for stock update (e.g., Initial stock setup, Physical count adjustment)..."
                  className="mt-1"
                />
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setShowPlantStockDialog(false)}>Cancel</Button>
                <Button 
                  onClick={handleUpdatePlantStock} 
                  disabled={submitting} 
                  className="bg-amber-600 hover:bg-amber-700"
                  data-testid="save-plant-stock-btn"
                >
                  {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Update Plant Stock'}
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </Layout>
  );
};

export default Warehouses;
