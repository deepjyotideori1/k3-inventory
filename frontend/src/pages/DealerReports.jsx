import React, { useState, useEffect } from 'react';
import Layout from '../components/Layout';
import { useAuth } from '../context/AuthContext';
import { 
  getDealers, 
  createDealer, 
  deleteDealer,
  getDealerEntries, 
  createDealerEntry,
  getDealerSummary,
  exportDealerPDF,
  exportDealerExcel
} from '../lib/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogTrigger, DialogFooter, DialogClose } from '../components/ui/dialog';
import { 
  Users,
  Plus,
  Loader2,
  FileText,
  Download,
  Trash2,
  Calendar,
  Package,
  RefreshCw,
  FileSpreadsheet,
  Save,
  Search,
  TrendingUp
} from 'lucide-react';
import { getTodayDate, formatDate, getDateRange } from '../lib/utils';
import { toast } from 'sonner';

const DealerReports = () => {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [dealers, setDealers] = useState([]);
  const [dealerTotals, setDealerTotals] = useState({});
  const [entries, setEntries] = useState([]);
  const [summary, setSummary] = useState({ dealers: [], grand_totals: {} });
  const [activeTab, setActiveTab] = useState('entry');
  
  // Entry form state
  const [selectedDealer, setSelectedDealer] = useState('');
  const [entryDate, setEntryDate] = useState(getTodayDate());
  const [entryForm, setEntryForm] = useState({
    issued_15kg: 0,
    issued_21kg: 0,
    refilled_15kg: 0,
    refilled_21kg: 0,
    remarks: ''
  });
  const [submitting, setSubmitting] = useState(false);
  
  // New dealer form
  const [newDealer, setNewDealer] = useState({ name: '', contact: '', address: '' });
  const [addingDealer, setAddingDealer] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  
  // Filters
  const [filterDealer, setFilterDealer] = useState('all');
  const [dateRange, setDateRange] = useState('weekly');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [exporting, setExporting] = useState(false);
  
  // Search
  const [searchQuery, setSearchQuery] = useState('');
  const [searchDate, setSearchDate] = useState('');

  useEffect(() => {
    fetchDealers();
    fetchAllTimeTotals();
    const range = getDateRange('weekly');
    setStartDate(range.start);
    setEndDate(range.end);
  }, []);

  useEffect(() => {
    if (startDate && endDate) {
      fetchEntries();
      fetchSummary();
    }
  }, [startDate, endDate, filterDealer]);

  const fetchDealers = async () => {
    try {
      const response = await getDealers();
      setDealers(response.data);
    } catch (error) {
      console.error('Failed to fetch dealers:', error);
      toast.error('Failed to load dealers');
    } finally {
      setLoading(false);
    }
  };

  const fetchAllTimeTotals = async () => {
    try {
      // Fetch all-time summary (no date filter)
      const response = await getDealerSummary({});
      const totals = {};
      response.data.dealers?.forEach(d => {
        totals[d.dealer_id] = {
          total_issued_15kg: d.total_issued_15kg,
          total_issued_21kg: d.total_issued_21kg,
          total_refilled_15kg: d.total_refilled_15kg,
          total_refilled_21kg: d.total_refilled_21kg
        };
      });
      setDealerTotals(totals);
    } catch (error) {
      console.error('Failed to fetch all-time totals:', error);
    }
  };

  const fetchEntries = async () => {
    try {
      const params = { start_date: startDate, end_date: endDate };
      if (filterDealer !== 'all') params.dealer_id = filterDealer;
      const response = await getDealerEntries(params);
      setEntries(response.data);
    } catch (error) {
      console.error('Failed to fetch entries:', error);
    }
  };

  const fetchSummary = async () => {
    try {
      const params = { start_date: startDate, end_date: endDate };
      const response = await getDealerSummary(params);
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

  const handleAddDealer = async () => {
    if (!newDealer.name.trim()) {
      toast.error('Dealer name is required');
      return;
    }
    
    setAddingDealer(true);
    try {
      await createDealer(newDealer);
      toast.success('Dealer added successfully');
      setNewDealer({ name: '', contact: '', address: '' });
      setDialogOpen(false);
      fetchDealers();
      fetchAllTimeTotals();
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
      await deleteDealer(dealerId);
      toast.success('Dealer deleted');
      fetchDealers();
      fetchAllTimeTotals();
    } catch (error) {
      console.error('Failed to delete dealer:', error);
      toast.error('Failed to delete dealer');
    }
  };

  const handleEntrySubmit = async (e) => {
    e.preventDefault();
    if (!selectedDealer) {
      toast.error('Please select a dealer');
      return;
    }
    
    setSubmitting(true);
    try {
      await createDealerEntry({
        dealer_id: selectedDealer,
        date: entryDate,
        ...entryForm
      });
      toast.success('Entry submitted successfully');
      setEntryForm({ issued_15kg: 0, issued_21kg: 0, refilled_15kg: 0, refilled_21kg: 0, remarks: '' });
      fetchEntries();
      fetchSummary();
      fetchAllTimeTotals();
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
      if (filterDealer !== 'all') params.dealer_id = filterDealer;
      await exportDealerPDF(params);
      toast.success('PDF exported successfully');
    } catch (error) {
      console.error('PDF export error:', error);
      toast.error('Failed to export PDF');
    } finally {
      setExporting(false);
    }
  };

  const handleExportExcel = async () => {
    setExporting(true);
    try {
      const params = { start_date: startDate, end_date: endDate };
      if (filterDealer !== 'all') params.dealer_id = filterDealer;
      await exportDealerExcel(params);
      toast.success('Excel exported successfully');
    } catch (error) {
      console.error('Excel export error:', error);
      toast.error('Failed to export Excel');
    } finally {
      setExporting(false);
    }
  };

  const handleExportAllTimePDF = async () => {
    setExporting(true);
    try {
      // Export without date filters for all-time data
      await exportDealerPDF({});
      toast.success('All-time PDF exported successfully');
    } catch (error) {
      console.error('PDF export error:', error);
      toast.error('Failed to export PDF');
    } finally {
      setExporting(false);
    }
  };

  const handleExportAllTimeExcel = async () => {
    setExporting(true);
    try {
      // Export without date filters for all-time data
      await exportDealerExcel({});
      toast.success('All-time Excel exported successfully');
    } catch (error) {
      console.error('Excel export error:', error);
      toast.error('Failed to export Excel');
    } finally {
      setExporting(false);
    }
  };

  // Search/filter entries
  const filteredEntries = entries.filter(entry => {
    const matchesSearch = searchQuery === '' || 
      entry.dealer_name?.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesDate = searchDate === '' || entry.date === searchDate;
    return matchesSearch && matchesDate;
  });

  // Filter dealers for display
  const filteredDealers = dealers.filter(dealer => 
    searchQuery === '' || dealer.name?.toLowerCase().includes(searchQuery.toLowerCase())
  );

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
      <div className="space-y-6" data-testid="dealer-reports-page">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-slate-800">Dealer Reports</h1>
            <p className="text-slate-500 mt-1">Plant Hollongi - Manage dealers and track cylinder issuance</p>
          </div>
          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger asChild>
              <Button className="bg-green-700 hover:bg-green-800" data-testid="add-dealer-btn">
                <Plus className="w-4 h-4 mr-2" />
                Add Dealer
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Add New Dealer</DialogTitle>
                <DialogDescription>Enter dealer information below to add a new dealer to the system.</DialogDescription>
              </DialogHeader>
              <div className="space-y-4 py-4">
                <div>
                  <Label>Dealer Name *</Label>
                  <Input
                    value={newDealer.name}
                    onChange={(e) => setNewDealer({ ...newDealer, name: e.target.value })}
                    placeholder="Enter dealer name"
                    data-testid="dealer-name-input"
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
                  className="bg-green-700 hover:bg-green-800"
                  data-testid="save-dealer-btn"
                >
                  {addingDealer ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Save className="w-4 h-4 mr-2" />}
                  Save Dealer
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="bg-white border">
            <TabsTrigger value="entry" className="data-[state=active]:bg-green-100">
              <Package className="w-4 h-4 mr-2" />
              Daily Entry
            </TabsTrigger>
            <TabsTrigger value="dealers" className="data-[state=active]:bg-green-100">
              <Users className="w-4 h-4 mr-2" />
              Dealers
            </TabsTrigger>
            <TabsTrigger value="search" className="data-[state=active]:bg-green-100">
              <Search className="w-4 h-4 mr-2" />
              Search
            </TabsTrigger>
            <TabsTrigger value="reports" className="data-[state=active]:bg-green-100">
              <FileText className="w-4 h-4 mr-2" />
              Reports
            </TabsTrigger>
          </TabsList>

          {/* Daily Entry Tab */}
          <TabsContent value="entry" className="mt-4">
            <Card data-testid="dealer-entry-card">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Package className="w-5 h-5 text-green-700" />
                  Dealer Daily Entry
                </CardTitle>
                <CardDescription>Record cylinder issuance and refilling for dealers</CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleEntrySubmit} className="space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <Label>Select Dealer *</Label>
                      <Select value={selectedDealer} onValueChange={setSelectedDealer}>
                        <SelectTrigger data-testid="select-dealer">
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
                        data-testid="entry-date"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div>
                      <Label className="text-green-700">15kg Issued</Label>
                      <Input 
                        type="number" 
                        value={entryForm.issued_15kg}
                        onChange={(e) => setEntryForm({ ...entryForm, issued_15kg: parseInt(e.target.value) || 0 })}
                        className="mt-1"
                        data-testid="issued-15kg"
                      />
                    </div>
                    <div>
                      <Label className="text-green-700">21kg Issued</Label>
                      <Input 
                        type="number" 
                        value={entryForm.issued_21kg}
                        onChange={(e) => setEntryForm({ ...entryForm, issued_21kg: parseInt(e.target.value) || 0 })}
                        className="mt-1"
                        data-testid="issued-21kg"
                      />
                    </div>
                    <div>
                      <Label className="text-blue-700">15kg Refilled</Label>
                      <Input 
                        type="number" 
                        value={entryForm.refilled_15kg}
                        onChange={(e) => setEntryForm({ ...entryForm, refilled_15kg: parseInt(e.target.value) || 0 })}
                        className="mt-1"
                        data-testid="refilled-15kg"
                      />
                    </div>
                    <div>
                      <Label className="text-blue-700">21kg Refilled</Label>
                      <Input 
                        type="number" 
                        value={entryForm.refilled_21kg}
                        onChange={(e) => setEntryForm({ ...entryForm, refilled_21kg: parseInt(e.target.value) || 0 })}
                        className="mt-1"
                        data-testid="refilled-21kg"
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
                      className="bg-green-700 hover:bg-green-800"
                      data-testid="submit-entry-btn"
                    >
                      {submitting ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Save className="w-4 h-4 mr-2" />}
                      Submit Entry
                    </Button>
                  </div>
                </form>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Dealers Tab - Updated with Total Issued Till Date */}
          <TabsContent value="dealers" className="mt-4 space-y-4">
            {/* Export All-Time Report */}
            <Card className="bg-gradient-to-r from-green-50 to-emerald-50 border-green-200">
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <TrendingUp className="w-6 h-6 text-green-700" />
                    <div>
                      <h3 className="font-semibold text-green-800">Total Issued Report (All Time)</h3>
                      <p className="text-sm text-green-600">Download complete issuance history for all dealers</p>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button 
                      variant="outline" 
                      onClick={handleExportAllTimePDF}
                      disabled={exporting}
                      className="border-red-300 text-red-700 hover:bg-red-50"
                      data-testid="export-alltime-pdf-btn"
                    >
                      {exporting ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Download className="w-4 h-4 mr-2" />}
                      PDF
                    </Button>
                    <Button 
                      variant="outline" 
                      onClick={handleExportAllTimeExcel}
                      disabled={exporting}
                      className="border-green-300 text-green-700 hover:bg-green-50"
                      data-testid="export-alltime-excel-btn"
                    >
                      {exporting ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <FileSpreadsheet className="w-4 h-4 mr-2" />}
                      Excel
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card data-testid="dealers-list-card">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Users className="w-5 h-5 text-green-700" />
                  Registered Dealers with Total Issued Till Date
                </CardTitle>
                <CardDescription>Manage dealer information and view total issued quantities</CardDescription>
              </CardHeader>
              <CardContent>
                {dealers.length > 0 ? (
                  <div className="space-y-4">
                    {dealers.map((dealer) => {
                      const totals = dealerTotals[dealer.id] || {};
                      return (
                        <div 
                          key={dealer.id} 
                          className="p-4 border rounded-lg bg-slate-50 hover:bg-slate-100 transition-colors"
                          data-testid={`dealer-card-${dealer.id}`}
                        >
                          <div className="flex items-start justify-between">
                            <div className="flex-1">
                              <div className="flex items-center gap-3">
                                <h3 className="font-semibold text-slate-800 text-lg">{dealer.name}</h3>
                                {dealer.contact && (
                                  <span className="text-sm text-slate-500">| {dealer.contact}</span>
                                )}
                              </div>
                              {dealer.address && (
                                <p className="text-sm text-slate-500 mt-1">{dealer.address}</p>
                              )}
                              
                              {/* Total Issued Till Date */}
                              <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-3">
                                <div className="bg-green-100 rounded-lg p-2 text-center">
                                  <p className="text-xs text-green-600 font-medium">15kg Issued</p>
                                  <p className="text-lg font-bold text-green-800">{totals.total_issued_15kg || 0}</p>
                                </div>
                                <div className="bg-green-100 rounded-lg p-2 text-center">
                                  <p className="text-xs text-green-600 font-medium">21kg Issued</p>
                                  <p className="text-lg font-bold text-green-800">{totals.total_issued_21kg || 0}</p>
                                </div>
                                <div className="bg-blue-100 rounded-lg p-2 text-center">
                                  <p className="text-xs text-blue-600 font-medium">15kg Refilled</p>
                                  <p className="text-lg font-bold text-blue-800">{totals.total_refilled_15kg || 0}</p>
                                </div>
                                <div className="bg-blue-100 rounded-lg p-2 text-center">
                                  <p className="text-xs text-blue-600 font-medium">21kg Refilled</p>
                                  <p className="text-lg font-bold text-blue-800">{totals.total_refilled_21kg || 0}</p>
                                </div>
                              </div>
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
                      );
                    })}
                  </div>
                ) : (
                  <div className="text-center py-12">
                    <Users className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                    <p className="text-slate-500">No dealers added yet</p>
                    <Button 
                      className="mt-4 bg-green-700 hover:bg-green-800"
                      onClick={() => setDialogOpen(true)}
                    >
                      <Plus className="w-4 h-4 mr-2" />
                      Add First Dealer
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Search Tab */}
          <TabsContent value="search" className="mt-4 space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Search className="w-5 h-5 text-green-700" />
                  Search Entries
                </CardTitle>
                <CardDescription>Search dealer entries by name or date</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-4 mb-6">
                  <div className="flex-1 min-w-[200px]">
                    <Label>Search by Dealer Name</Label>
                    <div className="flex gap-2 mt-1">
                      <div className="relative flex-1">
                        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-slate-400" />
                        <Input 
                          type="text"
                          value={searchQuery}
                          onChange={(e) => setSearchQuery(e.target.value)}
                          placeholder="Type dealer name..."
                          className="pl-10"
                          data-testid="search-dealer-input"
                        />
                      </div>
                    </div>
                  </div>
                  <div className="w-48">
                    <Label>Search by Date</Label>
                    <Input 
                      type="date"
                      value={searchDate}
                      onChange={(e) => setSearchDate(e.target.value)}
                      className="mt-1"
                      data-testid="search-date-input"
                    />
                  </div>
                  <div className="flex items-end gap-2">
                    <Button 
                      className="bg-green-700 hover:bg-green-800"
                      onClick={fetchEntries}
                      data-testid="search-btn"
                    >
                      <Search className="w-4 h-4 mr-2" />
                      Search
                    </Button>
                    <Button 
                      variant="outline"
                      onClick={() => { setSearchQuery(''); setSearchDate(''); }}
                    >
                      Clear
                    </Button>
                  </div>
                </div>

                {/* Search Results */}
                {filteredEntries.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Date</th>
                          <th>Dealer</th>
                          <th>15kg Issued</th>
                          <th>21kg Issued</th>
                          <th>15kg Refilled</th>
                          <th>21kg Refilled</th>
                          <th>Remarks</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredEntries.map((e) => (
                          <tr key={e.id}>
                            <td>{formatDate(e.date)}</td>
                            <td className="font-medium">{e.dealer_name}</td>
                            <td>{e.issued_15kg}</td>
                            <td>{e.issued_21kg}</td>
                            <td>{e.refilled_15kg}</td>
                            <td>{e.refilled_21kg}</td>
                            <td className="text-sm text-slate-600">{e.remarks || '-'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="text-center py-8">
                    <Search className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                    <p className="text-slate-500">
                      {searchQuery || searchDate ? 'No entries found matching your search' : 'Enter search criteria to find entries'}
                    </p>
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
                      data-testid="export-pdf-btn"
                    >
                      {exporting ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Download className="w-4 h-4 mr-2" />}
                      PDF
                    </Button>
                    <Button 
                      variant="outline" 
                      onClick={handleExportExcel}
                      disabled={exporting}
                      className="border-green-300 text-green-700 hover:bg-green-50"
                      data-testid="export-excel-btn"
                    >
                      {exporting ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <FileSpreadsheet className="w-4 h-4 mr-2" />}
                      Excel
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Summary Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <Card className="bg-green-50 border-green-200">
                <CardContent className="p-4 text-center">
                  <p className="text-sm text-green-700 font-medium">Total 15kg Issued</p>
                  <p className="text-3xl font-bold text-green-800">{summary.grand_totals.total_issued_15kg || 0}</p>
                </CardContent>
              </Card>
              <Card className="bg-green-50 border-green-200">
                <CardContent className="p-4 text-center">
                  <p className="text-sm text-green-700 font-medium">Total 21kg Issued</p>
                  <p className="text-3xl font-bold text-green-800">{summary.grand_totals.total_issued_21kg || 0}</p>
                </CardContent>
              </Card>
              <Card className="bg-blue-50 border-blue-200">
                <CardContent className="p-4 text-center">
                  <p className="text-sm text-blue-700 font-medium">Total 15kg Refilled</p>
                  <p className="text-3xl font-bold text-blue-800">{summary.grand_totals.total_refilled_15kg || 0}</p>
                </CardContent>
              </Card>
              <Card className="bg-blue-50 border-blue-200">
                <CardContent className="p-4 text-center">
                  <p className="text-sm text-blue-700 font-medium">Total 21kg Refilled</p>
                  <p className="text-3xl font-bold text-blue-800">{summary.grand_totals.total_refilled_21kg || 0}</p>
                </CardContent>
              </Card>
            </div>

            {/* Dealer-wise Summary */}
            <Card>
              <CardHeader>
                <CardTitle>Dealer-wise Summary</CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                {summary.dealers.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Dealer</th>
                          <th>15kg Issued</th>
                          <th>21kg Issued</th>
                          <th>15kg Refilled</th>
                          <th>21kg Refilled</th>
                          <th>Entries</th>
                        </tr>
                      </thead>
                      <tbody>
                        {summary.dealers.map((d) => (
                          <tr key={d.dealer_id}>
                            <td className="font-medium">{d.dealer_name}</td>
                            <td>{d.total_issued_15kg}</td>
                            <td>{d.total_issued_21kg}</td>
                            <td>{d.total_refilled_15kg}</td>
                            <td>{d.total_refilled_21kg}</td>
                            <td>
                              <Badge variant="outline">{d.entries_count}</Badge>
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
                          <th>Dealer</th>
                          <th>15kg Issued</th>
                          <th>21kg Issued</th>
                          <th>15kg Refilled</th>
                          <th>21kg Refilled</th>
                          <th>Remarks</th>
                        </tr>
                      </thead>
                      <tbody>
                        {entries.map((e) => (
                          <tr key={e.id}>
                            <td>{formatDate(e.date)}</td>
                            <td className="font-medium">{e.dealer_name}</td>
                            <td>{e.issued_15kg}</td>
                            <td>{e.issued_21kg}</td>
                            <td>{e.refilled_15kg}</td>
                            <td>{e.refilled_21kg}</td>
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

export default DealerReports;
