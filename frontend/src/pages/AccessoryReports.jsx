import React, { useState, useEffect } from 'react';
import Layout from '../components/Layout';
import { useAuth } from '../context/AuthContext';
import { 
  getAccessories, 
  createAccessory, 
  deleteAccessory,
  getAccessoryDealers,
  createAccessoryDealer,
  deleteAccessoryDealer,
  getAccessoryEntries, 
  createAccessoryEntry,
  getAccessorySummary,
  exportAccessoryPDF,
  exportAccessoryExcel
} from '../lib/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter, DialogClose } from '../components/ui/dialog';
import { 
  Package,
  Plus,
  Loader2,
  FileText,
  Download,
  Trash2,
  Calendar,
  RefreshCw,
  FileSpreadsheet,
  Save,
  Users,
  Boxes,
  ShoppingCart
} from 'lucide-react';
import { getTodayDate, formatDate, getDateRange } from '../lib/utils';
import { toast } from 'sonner';

const AccessoryReports = () => {
  const { user, isAdmin } = useAuth();
  const [loading, setLoading] = useState(true);
  const [accessories, setAccessories] = useState([]);
  const [dealers, setDealers] = useState([]);
  const [entries, setEntries] = useState([]);
  const [summary, setSummary] = useState({ summary: [], grand_totals: {} });
  const [activeTab, setActiveTab] = useState('entry');
  
  // Entry form state
  const [selectedAccessory, setSelectedAccessory] = useState('');
  const [selectedDealer, setSelectedDealer] = useState('');
  const [entryDate, setEntryDate] = useState(getTodayDate());
  const [entryForm, setEntryForm] = useState({
    total_issued: 0,
    total_sold: 0,
    remarks: ''
  });
  const [submitting, setSubmitting] = useState(false);
  
  // System calculated remaining
  const calculatedRemaining = entryForm.total_issued - entryForm.total_sold;
  
  // New accessory form
  const [newAccessory, setNewAccessory] = useState({ name: '', description: '', unit: 'pcs' });
  const [addingAccessory, setAddingAccessory] = useState(false);
  const [accessoryDialogOpen, setAccessoryDialogOpen] = useState(false);
  
  // New dealer form
  const [newDealer, setNewDealer] = useState({ name: '', contact: '', address: '' });
  const [addingDealer, setAddingDealer] = useState(false);
  const [dealerDialogOpen, setDealerDialogOpen] = useState(false);
  
  // Filters
  const [filterAccessory, setFilterAccessory] = useState('all');
  const [filterDealer, setFilterDealer] = useState('all');
  const [dateRange, setDateRange] = useState('weekly');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    fetchAccessories();
    fetchDealers();
    const range = getDateRange('weekly');
    setStartDate(range.start);
    setEndDate(range.end);
  }, []);

  useEffect(() => {
    if (startDate && endDate) {
      fetchEntries();
      fetchSummary();
    }
  }, [startDate, endDate, filterAccessory, filterDealer]);

  const fetchAccessories = async () => {
    try {
      const response = await getAccessories();
      setAccessories(response.data);
    } catch (error) {
      console.error('Failed to fetch accessories:', error);
      toast.error('Failed to load accessories');
    } finally {
      setLoading(false);
    }
  };

  const fetchDealers = async () => {
    try {
      const response = await getAccessoryDealers();
      setDealers(response.data);
    } catch (error) {
      console.error('Failed to fetch dealers:', error);
    }
  };

  const fetchEntries = async () => {
    try {
      const params = { start_date: startDate, end_date: endDate };
      if (filterAccessory !== 'all') params.accessory_id = filterAccessory;
      if (filterDealer !== 'all') params.dealer_id = filterDealer;
      const response = await getAccessoryEntries(params);
      setEntries(response.data);
    } catch (error) {
      console.error('Failed to fetch entries:', error);
    }
  };

  const fetchSummary = async () => {
    try {
      const params = { start_date: startDate, end_date: endDate };
      if (filterAccessory !== 'all') params.accessory_id = filterAccessory;
      const response = await getAccessorySummary(params);
      setSummary(response.data);
    } catch (error) {
      console.error('Failed to fetch summary:', error);
    }
  };

  const handleDateRangeChange = (value) => {
    setDateRange(value);
    const range = getDateRange(value);
    setStartDate(range.start);
    setEndDate(range.end);
  };

  const handleAddAccessory = async () => {
    if (!newAccessory.name.trim()) {
      toast.error('Accessory name is required');
      return;
    }
    
    setAddingAccessory(true);
    try {
      await createAccessory(newAccessory);
      toast.success('Accessory added successfully');
      setNewAccessory({ name: '', description: '', unit: 'pcs' });
      setAccessoryDialogOpen(false);
      fetchAccessories();
    } catch (error) {
      console.error('Failed to add accessory:', error);
      toast.error('Failed to add accessory');
    } finally {
      setAddingAccessory(false);
    }
  };

  const handleDeleteAccessory = async (accessoryId) => {
    if (!window.confirm('Are you sure you want to delete this accessory?')) return;
    
    try {
      await deleteAccessory(accessoryId);
      toast.success('Accessory deleted');
      fetchAccessories();
    } catch (error) {
      console.error('Failed to delete accessory:', error);
      toast.error('Failed to delete accessory');
    }
  };

  const handleAddDealer = async () => {
    if (!newDealer.name.trim()) {
      toast.error('Dealer name is required');
      return;
    }
    
    setAddingDealer(true);
    try {
      await createAccessoryDealer(newDealer);
      toast.success('Dealer added successfully');
      setNewDealer({ name: '', contact: '', address: '' });
      setDealerDialogOpen(false);
      fetchDealers();
    } catch (error) {
      console.error('Failed to add dealer:', error);
      toast.error('Failed to add dealer');
    } finally {
      setAddingDealer(false);
    }
  };

  const handleDeleteDealer = async (dealerId) => {
    if (!window.confirm('Are you sure you want to delete this dealer?')) return;
    
    try {
      await deleteAccessoryDealer(dealerId);
      toast.success('Dealer deleted');
      fetchDealers();
    } catch (error) {
      console.error('Failed to delete dealer:', error);
      toast.error('Failed to delete dealer');
    }
  };

  const handleEntrySubmit = async (e) => {
    e.preventDefault();
    if (!selectedAccessory) {
      toast.error('Please select an accessory');
      return;
    }
    if (!selectedDealer) {
      toast.error('Please select a dealer');
      return;
    }
    
    setSubmitting(true);
    try {
      await createAccessoryEntry({
        accessory_id: selectedAccessory,
        dealer_id: selectedDealer,
        date: entryDate,
        ...entryForm
      });
      toast.success('Entry submitted successfully');
      setEntryForm({ total_issued: 0, total_sold: 0, total_remaining: 0, remarks: '' });
      fetchEntries();
      fetchSummary();
    } catch (error) {
      console.error('Failed to submit entry:', error);
      toast.error('Failed to submit entry');
    } finally {
      setSubmitting(false);
    }
  };

  const handleExportPDF = async () => {
    setExporting(true);
    try {
      const params = { start_date: startDate, end_date: endDate };
      if (filterAccessory !== 'all') params.accessory_id = filterAccessory;
      if (filterDealer !== 'all') params.dealer_id = filterDealer;
      await exportAccessoryPDF(params);
      toast.success('PDF exported successfully');
    } catch (error) {
      toast.error('Failed to export PDF');
    } finally {
      setExporting(false);
    }
  };

  const handleExportExcel = async () => {
    setExporting(true);
    try {
      const params = { start_date: startDate, end_date: endDate };
      if (filterAccessory !== 'all') params.accessory_id = filterAccessory;
      if (filterDealer !== 'all') params.dealer_id = filterDealer;
      await exportAccessoryExcel(params);
      toast.success('Excel exported successfully');
    } catch (error) {
      toast.error('Failed to export Excel');
    } finally {
      setExporting(false);
    }
  };

  if (!isAdmin) {
    return (
      <Layout>
        <div className="text-center py-12">
          <p className="text-slate-500">Admin access required</p>
        </div>
      </Layout>
    );
  }

  if (loading) {
    return (
      <Layout>
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 animate-spin text-purple-700" />
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="space-y-6" data-testid="accessory-reports-page">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-slate-800">LPG Accessories</h1>
            <p className="text-slate-500 mt-1">Manage accessories, dealers and track inventory</p>
          </div>
          <div className="flex gap-2">
            <Dialog open={accessoryDialogOpen} onOpenChange={setAccessoryDialogOpen}>
              <DialogTrigger asChild>
                <Button className="bg-purple-700 hover:bg-purple-800" data-testid="add-accessory-btn">
                  <Plus className="w-4 h-4 mr-2" />
                  Add Accessory
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Add New Accessory</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 py-4">
                  <div>
                    <Label>Accessory Name *</Label>
                    <Input
                      value={newAccessory.name}
                      onChange={(e) => setNewAccessory({ ...newAccessory, name: e.target.value })}
                      placeholder="e.g., Regulator, Pipe, Burner"
                      data-testid="accessory-name-input"
                    />
                  </div>
                  <div>
                    <Label>Description</Label>
                    <Textarea
                      value={newAccessory.description}
                      onChange={(e) => setNewAccessory({ ...newAccessory, description: e.target.value })}
                      placeholder="Enter description"
                    />
                  </div>
                  <div>
                    <Label>Unit</Label>
                    <Select value={newAccessory.unit} onValueChange={(v) => setNewAccessory({ ...newAccessory, unit: v })}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="pcs">Pieces (pcs)</SelectItem>
                        <SelectItem value="set">Set</SelectItem>
                        <SelectItem value="mtr">Meters (mtr)</SelectItem>
                        <SelectItem value="kg">Kilograms (kg)</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <DialogFooter>
                  <DialogClose asChild>
                    <Button variant="outline">Cancel</Button>
                  </DialogClose>
                  <Button 
                    onClick={handleAddAccessory} 
                    disabled={addingAccessory}
                    className="bg-purple-700 hover:bg-purple-800"
                    data-testid="save-accessory-btn"
                  >
                    {addingAccessory ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Save className="w-4 h-4 mr-2" />}
                    Save Accessory
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
            
            <Dialog open={dealerDialogOpen} onOpenChange={setDealerDialogOpen}>
              <DialogTrigger asChild>
                <Button variant="outline" className="border-purple-300 text-purple-700" data-testid="add-acc-dealer-btn">
                  <Plus className="w-4 h-4 mr-2" />
                  Add Dealer
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Add New Dealer</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 py-4">
                  <div>
                    <Label>Dealer Name *</Label>
                    <Input
                      value={newDealer.name}
                      onChange={(e) => setNewDealer({ ...newDealer, name: e.target.value })}
                      placeholder="Enter dealer name"
                      data-testid="acc-dealer-name-input"
                    />
                  </div>
                  <div>
                    <Label>Contact Number</Label>
                    <Input
                      value={newDealer.contact}
                      onChange={(e) => setNewDealer({ ...newDealer, contact: e.target.value })}
                      placeholder="Enter contact number"
                    />
                  </div>
                  <div>
                    <Label>Address</Label>
                    <Textarea
                      value={newDealer.address}
                      onChange={(e) => setNewDealer({ ...newDealer, address: e.target.value })}
                      placeholder="Enter address"
                    />
                  </div>
                </div>
                <DialogFooter>
                  <DialogClose asChild>
                    <Button variant="outline">Cancel</Button>
                  </DialogClose>
                  <Button 
                    onClick={handleAddDealer} 
                    disabled={addingDealer}
                    className="bg-purple-700 hover:bg-purple-800"
                    data-testid="save-acc-dealer-btn"
                  >
                    {addingDealer ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Save className="w-4 h-4 mr-2" />}
                    Save Dealer
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="bg-white border">
            <TabsTrigger value="entry" className="data-[state=active]:bg-purple-100">
              <ShoppingCart className="w-4 h-4 mr-2" />
              Daily Entry
            </TabsTrigger>
            <TabsTrigger value="accessories" className="data-[state=active]:bg-purple-100">
              <Boxes className="w-4 h-4 mr-2" />
              Accessories
            </TabsTrigger>
            <TabsTrigger value="dealers" className="data-[state=active]:bg-purple-100">
              <Users className="w-4 h-4 mr-2" />
              Dealers
            </TabsTrigger>
            <TabsTrigger value="reports" className="data-[state=active]:bg-purple-100">
              <FileText className="w-4 h-4 mr-2" />
              Reports
            </TabsTrigger>
          </TabsList>

          {/* Daily Entry Tab */}
          <TabsContent value="entry" className="mt-4">
            <Card data-testid="accessory-entry-card">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <ShoppingCart className="w-5 h-5 text-purple-700" />
                  Accessory Daily Entry
                </CardTitle>
                <CardDescription>Record accessory issued, sold and remaining quantities</CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleEntrySubmit} className="space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                      <Label>Select Accessory *</Label>
                      <Select value={selectedAccessory} onValueChange={setSelectedAccessory}>
                        <SelectTrigger data-testid="select-accessory">
                          <SelectValue placeholder="Choose an accessory" />
                        </SelectTrigger>
                        <SelectContent>
                          {accessories.map((a) => (
                            <SelectItem key={a.id} value={a.id}>{a.name}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label>Select Dealer *</Label>
                      <Select value={selectedDealer} onValueChange={setSelectedDealer}>
                        <SelectTrigger data-testid="select-acc-dealer">
                          <SelectValue placeholder="Choose a dealer" />
                        </SelectTrigger>
                        <SelectContent>
                          {dealers.map((d) => (
                            <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label>Date</Label>
                      <Input 
                        type="date" 
                        value={entryDate}
                        onChange={(e) => setEntryDate(e.target.value)}
                        data-testid="acc-entry-date"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-4">
                    <div>
                      <Label className="text-purple-700">Total Issued</Label>
                      <Input 
                        type="number" 
                        value={entryForm.total_issued}
                        onChange={(e) => setEntryForm({ ...entryForm, total_issued: parseInt(e.target.value) || 0 })}
                        className="mt-1"
                        data-testid="acc-total-issued"
                      />
                    </div>
                    <div>
                      <Label className="text-orange-700">Total Sold</Label>
                      <Input 
                        type="number" 
                        value={entryForm.total_sold}
                        onChange={(e) => setEntryForm({ ...entryForm, total_sold: parseInt(e.target.value) || 0 })}
                        className="mt-1"
                        data-testid="acc-total-sold"
                      />
                    </div>
                    <div>
                      <Label className="text-green-700">Total Remaining</Label>
                      <Input 
                        type="number" 
                        value={entryForm.total_remaining}
                        onChange={(e) => setEntryForm({ ...entryForm, total_remaining: parseInt(e.target.value) || 0 })}
                        className="mt-1"
                        data-testid="acc-total-remaining"
                      />
                    </div>
                  </div>

                  <div>
                    <Label>Remarks</Label>
                    <Textarea 
                      value={entryForm.remarks}
                      onChange={(e) => setEntryForm({ ...entryForm, remarks: e.target.value })}
                      placeholder="Optional remarks..."
                      className="mt-1"
                    />
                  </div>

                  <div className="flex justify-end">
                    <Button 
                      type="submit" 
                      disabled={submitting}
                      className="bg-purple-700 hover:bg-purple-800"
                      data-testid="submit-acc-entry-btn"
                    >
                      {submitting ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Save className="w-4 h-4 mr-2" />}
                      Submit Entry
                    </Button>
                  </div>
                </form>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Accessories Tab */}
          <TabsContent value="accessories" className="mt-4">
            <Card data-testid="accessories-list-card">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Boxes className="w-5 h-5 text-purple-700" />
                  LPG Accessories
                </CardTitle>
                <CardDescription>Manage accessory items</CardDescription>
              </CardHeader>
              <CardContent>
                {accessories.length > 0 ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {accessories.map((acc) => (
                      <div 
                        key={acc.id} 
                        className="p-4 border rounded-lg bg-purple-50 hover:bg-purple-100 transition-colors"
                        data-testid={`accessory-card-${acc.id}`}
                      >
                        <div className="flex items-start justify-between">
                          <div>
                            <h3 className="font-semibold text-slate-800">{acc.name}</h3>
                            {acc.description && (
                              <p className="text-sm text-slate-600 mt-1">{acc.description}</p>
                            )}
                            <Badge variant="outline" className="mt-2">{acc.unit}</Badge>
                          </div>
                          <Button 
                            variant="ghost" 
                            size="sm" 
                            onClick={() => handleDeleteAccessory(acc.id)}
                            className="text-red-600 hover:text-red-800 hover:bg-red-50"
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-12">
                    <Boxes className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                    <p className="text-slate-500">No accessories added yet</p>
                    <Button 
                      className="mt-4 bg-purple-700 hover:bg-purple-800"
                      onClick={() => setAccessoryDialogOpen(true)}
                    >
                      <Plus className="w-4 h-4 mr-2" />
                      Add First Accessory
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Dealers Tab */}
          <TabsContent value="dealers" className="mt-4">
            <Card data-testid="acc-dealers-list-card">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Users className="w-5 h-5 text-purple-700" />
                  Accessory Dealers
                </CardTitle>
                <CardDescription>Manage dealer information</CardDescription>
              </CardHeader>
              <CardContent>
                {dealers.length > 0 ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {dealers.map((dealer) => (
                      <div 
                        key={dealer.id} 
                        className="p-4 border rounded-lg bg-slate-50 hover:bg-slate-100 transition-colors"
                        data-testid={`acc-dealer-card-${dealer.id}`}
                      >
                        <div className="flex items-start justify-between">
                          <div>
                            <h3 className="font-semibold text-slate-800">{dealer.name}</h3>
                            {dealer.contact && (
                              <p className="text-sm text-slate-600 mt-1">{dealer.contact}</p>
                            )}
                            {dealer.address && (
                              <p className="text-sm text-slate-500 mt-1">{dealer.address}</p>
                            )}
                          </div>
                          <Button 
                            variant="ghost" 
                            size="sm" 
                            onClick={() => handleDeleteDealer(dealer.id)}
                            className="text-red-600 hover:text-red-800 hover:bg-red-50"
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-12">
                    <Users className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                    <p className="text-slate-500">No dealers added yet</p>
                    <Button 
                      className="mt-4 bg-purple-700 hover:bg-purple-800"
                      onClick={() => setDealerDialogOpen(true)}
                    >
                      <Plus className="w-4 h-4 mr-2" />
                      Add First Dealer
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Reports Tab */}
          <TabsContent value="reports" className="mt-4 space-y-4">
            {/* Filters */}
            <Card>
              <CardContent className="p-4">
                <div className="flex flex-wrap items-end gap-4">
                  <div>
                    <Label>Period</Label>
                    <Select value={dateRange} onValueChange={handleDateRangeChange}>
                      <SelectTrigger className="w-32">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="weekly">Weekly</SelectItem>
                        <SelectItem value="monthly">Monthly</SelectItem>
                        <SelectItem value="yearly">Yearly</SelectItem>
                        <SelectItem value="custom">Custom</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label>Accessory</Label>
                    <Select value={filterAccessory} onValueChange={setFilterAccessory}>
                      <SelectTrigger className="w-40">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All Accessories</SelectItem>
                        {accessories.map((a) => (
                          <SelectItem key={a.id} value={a.id}>{a.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label>Dealer</Label>
                    <Select value={filterDealer} onValueChange={setFilterDealer}>
                      <SelectTrigger className="w-40">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All Dealers</SelectItem>
                        {dealers.map((d) => (
                          <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label>Start Date</Label>
                    <Input 
                      type="date" 
                      value={startDate}
                      onChange={(e) => { setStartDate(e.target.value); setDateRange('custom'); }}
                      className="w-40"
                    />
                  </div>
                  <div>
                    <Label>End Date</Label>
                    <Input 
                      type="date" 
                      value={endDate}
                      onChange={(e) => { setEndDate(e.target.value); setDateRange('custom'); }}
                      className="w-40"
                    />
                  </div>
                  <Button variant="outline" onClick={() => { fetchEntries(); fetchSummary(); }}>
                    <RefreshCw className="w-4 h-4 mr-2" />
                    Refresh
                  </Button>
                  <div className="flex gap-2 ml-auto">
                    <Button 
                      variant="outline" 
                      onClick={handleExportPDF}
                      disabled={exporting}
                      className="border-red-300 text-red-700 hover:bg-red-50"
                      data-testid="export-acc-pdf-btn"
                    >
                      {exporting ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Download className="w-4 h-4 mr-2" />}
                      PDF
                    </Button>
                    <Button 
                      variant="outline" 
                      onClick={handleExportExcel}
                      disabled={exporting}
                      className="border-green-300 text-green-700 hover:bg-green-50"
                      data-testid="export-acc-excel-btn"
                    >
                      {exporting ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <FileSpreadsheet className="w-4 h-4 mr-2" />}
                      Excel
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Summary Cards */}
            <div className="grid grid-cols-2 gap-4">
              <Card className="bg-purple-50 border-purple-200">
                <CardContent className="p-4 text-center">
                  <p className="text-sm text-purple-700 font-medium">Total Issued</p>
                  <p className="text-3xl font-bold text-purple-800">{summary.grand_totals.total_issued || 0}</p>
                </CardContent>
              </Card>
              <Card className="bg-orange-50 border-orange-200">
                <CardContent className="p-4 text-center">
                  <p className="text-sm text-orange-700 font-medium">Total Sold</p>
                  <p className="text-3xl font-bold text-orange-800">{summary.grand_totals.total_sold || 0}</p>
                </CardContent>
              </Card>
            </div>

            {/* Summary Table */}
            <Card>
              <CardHeader>
                <CardTitle>Accessory-wise Dealer Summary</CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                {summary.summary.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Accessory</th>
                          <th>Dealer</th>
                          <th>Total Issued</th>
                          <th>Total Sold</th>
                          <th>Latest Remaining</th>
                          <th>Entries</th>
                        </tr>
                      </thead>
                      <tbody>
                        {summary.summary.map((s, idx) => (
                          <tr key={idx}>
                            <td className="font-medium">{s.accessory_name}</td>
                            <td>{s.dealer_name}</td>
                            <td>{s.total_issued}</td>
                            <td>{s.total_sold}</td>
                            <td>{s.latest_remaining}</td>
                            <td>
                              <Badge variant="outline">{s.entries_count}</Badge>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="text-center py-8">
                    <p className="text-slate-500">No data for selected period</p>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Detailed Entries */}
            <Card>
              <CardHeader>
                <CardTitle>Detailed Entries</CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                {entries.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Date</th>
                          <th>Accessory</th>
                          <th>Dealer</th>
                          <th>Issued</th>
                          <th>Sold</th>
                          <th>Remaining</th>
                          <th>Remarks</th>
                        </tr>
                      </thead>
                      <tbody>
                        {entries.map((e) => (
                          <tr key={e.id}>
                            <td>{formatDate(e.date)}</td>
                            <td className="font-medium">{e.accessory_name}</td>
                            <td>{e.dealer_name}</td>
                            <td>{e.total_issued}</td>
                            <td>{e.total_sold}</td>
                            <td>{e.total_remaining}</td>
                            <td className="text-sm text-slate-600">{e.remarks || '-'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="text-center py-8">
                    <Calendar className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                    <p className="text-slate-500">No entries for selected period</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </Layout>
  );
};

export default AccessoryReports;
