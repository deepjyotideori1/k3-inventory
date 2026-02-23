import React, { useState, useEffect } from 'react';
import Layout from '../components/Layout';
import { useAuth } from '../context/AuthContext';
import { 
  getMessagingSettings,
  updateMessagingSettings,
  getRecipientCount,
  sendBulkMessage,
  getMessageLogs,
  getMessageLogDetail,
  getWarehouses
} from '../lib/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogClose } from '../components/ui/dialog';
import { Alert, AlertDescription } from '../components/ui/alert';
import { 
  MessageSquare,
  Send,
  Loader2,
  Settings,
  History,
  Users,
  Phone,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  RefreshCw,
  Eye,
  Smartphone,
  MessageCircle,
  Building2,
  Home,
  Info
} from 'lucide-react';
import { formatDate } from '../lib/utils';
import { toast } from 'sonner';

const BulkMessaging = () => {
  const { user, isAdmin } = useAuth();
  const [activeTab, setActiveTab] = useState('compose');
  const [loading, setLoading] = useState(true);
  
  // Settings state
  const [settings, setSettings] = useState({
    provider: '',
    sms_api_key: '',
    sms_api_secret: '',
    sms_sender_id: '',
    whatsapp_api_key: '',
    whatsapp_api_secret: '',
    whatsapp_phone_number: '',
    whatsapp_business_id: ''
  });
  const [settingsLoaded, setSettingsLoaded] = useState({
    sms_configured: false,
    whatsapp_configured: false
  });
  
  // Compose state
  const [channel, setChannel] = useState('sms');
  const [message, setMessage] = useState('');
  const [recipientFilter, setRecipientFilter] = useState('all');
  const [selectedWarehouse, setSelectedWarehouse] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [recipientCount, setRecipientCount] = useState(0);
  const [recipientBreakdown, setRecipientBreakdown] = useState([]);
  const [warehouses, setWarehouses] = useState([]);
  const [sending, setSending] = useState(false);
  const [savingSettings, setSavingSettings] = useState(false);
  
  // Logs state
  const [logs, setLogs] = useState([]);
  const [selectedLog, setSelectedLog] = useState(null);
  const [logDetailOpen, setLogDetailOpen] = useState(false);

  useEffect(() => {
    if (isAdmin) {
      fetchData();
    }
  }, [isAdmin]);

  useEffect(() => {
    if (isAdmin) {
      fetchRecipientCount();
    }
  }, [recipientFilter, selectedWarehouse, selectedCategory]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [settingsRes, warehousesRes, logsRes] = await Promise.all([
        getMessagingSettings(),
        getWarehouses(),
        getMessageLogs(50)
      ]);
      
      setSettingsLoaded({
        provider: settingsRes.data.provider || '',
        sms_configured: settingsRes.data.sms_configured,
        whatsapp_configured: settingsRes.data.whatsapp_configured,
        sms_sender_id: settingsRes.data.sms_sender_id || '',
        whatsapp_phone_number: settingsRes.data.whatsapp_phone_number || ''
      });
      
      setWarehouses(warehousesRes.data.filter(w => !w.is_plant));
      setLogs(logsRes.data);
    } catch (error) {
      console.error('Failed to fetch data:', error);
      toast.error('Failed to load messaging data');
    } finally {
      setLoading(false);
    }
  };

  const fetchRecipientCount = async () => {
    try {
      const params = { recipient_filter: recipientFilter };
      if (recipientFilter === 'warehouse' && selectedWarehouse) {
        params.warehouse_id = selectedWarehouse;
      }
      if (recipientFilter === 'category' && selectedCategory) {
        params.category = selectedCategory;
      }
      
      const response = await getRecipientCount(params);
      setRecipientCount(response.data.total_recipients);
      setRecipientBreakdown(response.data.breakdown_by_warehouse || []);
    } catch (error) {
      console.error('Failed to get recipient count:', error);
    }
  };

  const handleSaveSettings = async () => {
    setSavingSettings(true);
    try {
      await updateMessagingSettings(settings);
      toast.success('Messaging settings saved successfully');
      
      // Refresh settings
      const response = await getMessagingSettings();
      setSettingsLoaded({
        provider: response.data.provider || '',
        sms_configured: response.data.sms_configured,
        whatsapp_configured: response.data.whatsapp_configured,
        sms_sender_id: response.data.sms_sender_id || '',
        whatsapp_phone_number: response.data.whatsapp_phone_number || ''
      });
      
      // Clear sensitive fields
      setSettings(prev => ({
        ...prev,
        sms_api_key: '',
        sms_api_secret: '',
        whatsapp_api_key: '',
        whatsapp_api_secret: ''
      }));
    } catch (error) {
      console.error('Failed to save settings:', error);
      toast.error(error.response?.data?.detail || 'Failed to save settings');
    } finally {
      setSavingSettings(false);
    }
  };

  const handleSendMessage = async () => {
    if (!message.trim()) {
      toast.error('Please enter a message');
      return;
    }
    
    if (recipientCount === 0) {
      toast.error('No recipients found');
      return;
    }
    
    setSending(true);
    try {
      const data = {
        channel,
        message: message.trim(),
        recipient_filter: recipientFilter
      };
      
      if (recipientFilter === 'warehouse' && selectedWarehouse) {
        data.warehouse_id = selectedWarehouse;
      }
      if (recipientFilter === 'category' && selectedCategory) {
        data.category = selectedCategory;
      }
      
      const response = await sendBulkMessage(data);
      
      if (response.data.simulated) {
        toast.info(`Message simulated for ${response.data.recipient_count} recipients. Configure API credentials in Settings to send real messages.`);
      } else {
        toast.success(`Message sent to ${response.data.successful_count} of ${response.data.recipient_count} recipients`);
      }
      
      setMessage('');
      
      // Refresh logs
      const logsRes = await getMessageLogs(50);
      setLogs(logsRes.data);
      
    } catch (error) {
      console.error('Failed to send message:', error);
      toast.error(error.response?.data?.detail || 'Failed to send message');
    } finally {
      setSending(false);
    }
  };

  const handleViewLogDetail = async (logId) => {
    try {
      const response = await getMessageLogDetail(logId);
      setSelectedLog(response.data);
      setLogDetailOpen(true);
    } catch (error) {
      console.error('Failed to get log detail:', error);
      toast.error('Failed to load message details');
    }
  };

  const getChannelIcon = (ch) => {
    switch(ch) {
      case 'sms': return <Phone className="w-4 h-4" />;
      case 'whatsapp': return <MessageCircle className="w-4 h-4" />;
      case 'both': return <MessageSquare className="w-4 h-4" />;
      default: return <MessageSquare className="w-4 h-4" />;
    }
  };

  const getChannelBadge = (ch) => {
    switch(ch) {
      case 'sms': return <Badge className="bg-blue-100 text-blue-800"><Phone className="w-3 h-3 mr-1" />SMS</Badge>;
      case 'whatsapp': return <Badge className="bg-green-100 text-green-800"><MessageCircle className="w-3 h-3 mr-1" />WhatsApp</Badge>;
      case 'both': return <Badge className="bg-purple-100 text-purple-800"><MessageSquare className="w-3 h-3 mr-1" />Both</Badge>;
      default: return <Badge variant="outline">{ch}</Badge>;
    }
  };

  if (!isAdmin) {
    return (
      <Layout>
        <div className="flex flex-col items-center justify-center h-64 text-center">
          <MessageSquare className="w-16 h-16 text-slate-300 mb-4" />
          <h2 className="text-2xl font-bold text-slate-700 mb-2">Access Denied</h2>
          <p className="text-slate-500">Bulk messaging is only available for administrators.</p>
        </div>
      </Layout>
    );
  }

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
      <div className="space-y-6" data-testid="bulk-messaging-page">
        {/* Header */}
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <h1 className="text-3xl font-bold text-slate-800">Bulk Messaging</h1>
            <p className="text-slate-500 mt-1">Send SMS and WhatsApp messages to customers</p>
          </div>
          <div className="flex gap-2">
            {settingsLoaded.sms_configured ? (
              <Badge className="bg-green-100 text-green-800"><CheckCircle2 className="w-3 h-3 mr-1" />SMS Configured</Badge>
            ) : (
              <Badge className="bg-amber-100 text-amber-800"><AlertTriangle className="w-3 h-3 mr-1" />SMS Not Configured</Badge>
            )}
            {settingsLoaded.whatsapp_configured ? (
              <Badge className="bg-green-100 text-green-800"><CheckCircle2 className="w-3 h-3 mr-1" />WhatsApp Configured</Badge>
            ) : (
              <Badge className="bg-amber-100 text-amber-800"><AlertTriangle className="w-3 h-3 mr-1" />WhatsApp Not Configured</Badge>
            )}
          </div>
        </div>

        {/* Alert if not configured */}
        {!settingsLoaded.sms_configured && !settingsLoaded.whatsapp_configured && (
          <Alert className="bg-amber-50 border-amber-200">
            <Info className="w-4 h-4 text-amber-600" />
            <AlertDescription className="text-amber-800">
              <strong>API credentials not configured.</strong> Messages will be simulated. Go to the Settings tab to add your SMS/WhatsApp API credentials.
            </AlertDescription>
          </Alert>
        )}

        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="bg-white border">
            <TabsTrigger value="compose" className="data-[state=active]:bg-green-100">
              <Send className="w-4 h-4 mr-2" />
              Compose Message
            </TabsTrigger>
            <TabsTrigger value="history" className="data-[state=active]:bg-green-100">
              <History className="w-4 h-4 mr-2" />
              Message History
            </TabsTrigger>
            <TabsTrigger value="settings" className="data-[state=active]:bg-green-100">
              <Settings className="w-4 h-4 mr-2" />
              API Settings
            </TabsTrigger>
          </TabsList>

          {/* Compose Tab */}
          <TabsContent value="compose" className="mt-4 space-y-4">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              {/* Message Composer */}
              <div className="lg:col-span-2">
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <MessageSquare className="w-5 h-5 text-green-700" />
                      Compose Message
                    </CardTitle>
                    <CardDescription>Write your message to send to customers</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div>
                      <Label>Message Channel *</Label>
                      <Select value={channel} onValueChange={setChannel}>
                        <SelectTrigger className="mt-1" data-testid="channel-select">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="sms">
                            <div className="flex items-center gap-2"><Phone className="w-4 h-4 text-blue-600" /> SMS Only</div>
                          </SelectItem>
                          <SelectItem value="whatsapp">
                            <div className="flex items-center gap-2"><MessageCircle className="w-4 h-4 text-green-600" /> WhatsApp Only</div>
                          </SelectItem>
                          <SelectItem value="both">
                            <div className="flex items-center gap-2"><MessageSquare className="w-4 h-4 text-purple-600" /> Both SMS & WhatsApp</div>
                          </SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    <div>
                      <Label>Message *</Label>
                      <Textarea 
                        value={message}
                        onChange={(e) => setMessage(e.target.value)}
                        placeholder="Type your message here..."
                        className="mt-1 min-h-[150px]"
                        data-testid="message-input"
                      />
                      <p className="text-xs text-slate-500 mt-1">{message.length} characters</p>
                    </div>

                    <Button 
                      onClick={handleSendMessage}
                      disabled={sending || !message.trim() || recipientCount === 0}
                      className="w-full bg-green-700 hover:bg-green-800"
                      data-testid="send-btn"
                    >
                      {sending ? (
                        <><Loader2 className="w-4 h-4 animate-spin mr-2" /> Sending...</>
                      ) : (
                        <><Send className="w-4 h-4 mr-2" /> Send to {recipientCount} Recipients</>
                      )}
                    </Button>
                  </CardContent>
                </Card>
              </div>

              {/* Recipient Selection */}
              <div>
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Users className="w-5 h-5 text-green-700" />
                      Recipients
                    </CardTitle>
                    <CardDescription>Select who receives the message</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div>
                      <Label>Filter Recipients</Label>
                      <Select value={recipientFilter} onValueChange={(v) => { setRecipientFilter(v); setSelectedWarehouse(''); setSelectedCategory(''); }}>
                        <SelectTrigger className="mt-1">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="all">All Customers</SelectItem>
                          <SelectItem value="warehouse">By Warehouse</SelectItem>
                          <SelectItem value="category">By Category</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    {recipientFilter === 'warehouse' && (
                      <div>
                        <Label>Select Warehouse</Label>
                        <Select value={selectedWarehouse} onValueChange={setSelectedWarehouse}>
                          <SelectTrigger className="mt-1">
                            <SelectValue placeholder="Choose warehouse" />
                          </SelectTrigger>
                          <SelectContent>
                            {warehouses.map(w => (
                              <SelectItem key={w.id} value={w.id}>{w.name}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    )}

                    {recipientFilter === 'category' && (
                      <div>
                        <Label>Select Category</Label>
                        <Select value={selectedCategory} onValueChange={setSelectedCategory}>
                          <SelectTrigger className="mt-1">
                            <SelectValue placeholder="Choose category" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="domestic">
                              <div className="flex items-center gap-2"><Home className="w-4 h-4" /> Domestic</div>
                            </SelectItem>
                            <SelectItem value="commercial">
                              <div className="flex items-center gap-2"><Building2 className="w-4 h-4" /> Commercial</div>
                            </SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    )}

                    <div className="p-4 bg-green-50 border border-green-200 rounded-lg text-center">
                      <Users className="w-8 h-8 text-green-600 mx-auto mb-2" />
                      <p className="text-2xl font-bold text-green-800">{recipientCount}</p>
                      <p className="text-sm text-green-700">Recipients with phone numbers</p>
                    </div>

                    {recipientBreakdown.length > 0 && (
                      <div className="space-y-2">
                        <Label className="text-xs">Breakdown by Warehouse</Label>
                        {recipientBreakdown.map((b, i) => (
                          <div key={i} className="flex justify-between text-sm p-2 bg-slate-50 rounded">
                            <span className="text-slate-600">{b.warehouse_name}</span>
                            <span className="font-medium">{b.count}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>
            </div>
          </TabsContent>

          {/* History Tab */}
          <TabsContent value="history" className="mt-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle>Message History</CardTitle>
                  <CardDescription>View past bulk messages sent</CardDescription>
                </div>
                <Button variant="outline" onClick={fetchData}>
                  <RefreshCw className="w-4 h-4 mr-2" /> Refresh
                </Button>
              </CardHeader>
              <CardContent>
                {logs.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Date</th>
                          <th>Channel</th>
                          <th>Message</th>
                          <th>Recipients</th>
                          <th>Success</th>
                          <th>Failed</th>
                          <th>Status</th>
                          <th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {logs.map((log) => (
                          <tr key={log.id}>
                            <td className="whitespace-nowrap">{formatDate(log.created_at)}</td>
                            <td>{getChannelBadge(log.channel)}</td>
                            <td className="max-w-[200px] truncate">{log.message}</td>
                            <td className="text-center">{log.recipient_count}</td>
                            <td className="text-center">
                              <span className="text-green-600 font-medium">{log.successful_count}</span>
                            </td>
                            <td className="text-center">
                              <span className="text-red-600 font-medium">{log.failed_count}</span>
                            </td>
                            <td>
                              {log.status === 'completed' ? (
                                <Badge className="bg-green-100 text-green-800">Completed</Badge>
                              ) : log.status === 'processing' ? (
                                <Badge className="bg-blue-100 text-blue-800">Processing</Badge>
                              ) : (
                                <Badge variant="outline">{log.status}</Badge>
                              )}
                            </td>
                            <td>
                              <Button 
                                variant="ghost" 
                                size="sm"
                                onClick={() => handleViewLogDetail(log.id)}
                              >
                                <Eye className="w-4 h-4" />
                              </Button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="text-center py-12">
                    <History className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                    <p className="text-slate-500">No messages sent yet</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Settings Tab */}
          <TabsContent value="settings" className="mt-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Settings className="w-5 h-5 text-green-700" />
                  API Configuration
                </CardTitle>
                <CardDescription>
                  Configure your SMS and WhatsApp API credentials. Supported providers: Twilio, MSG91, Meta WhatsApp Business API, etc.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div>
                  <Label>Provider Name</Label>
                  <Input 
                    value={settings.provider}
                    onChange={(e) => setSettings({ ...settings, provider: e.target.value })}
                    placeholder="e.g., twilio, msg91, meta"
                    className="mt-1"
                  />
                  <p className="text-xs text-slate-500 mt-1">Enter the name of your messaging provider</p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* SMS Settings */}
                  <div className="p-4 border rounded-lg space-y-4">
                    <div className="flex items-center gap-2 mb-2">
                      <Phone className="w-5 h-5 text-blue-600" />
                      <h3 className="font-semibold">SMS Configuration</h3>
                      {settingsLoaded.sms_configured && <Badge className="bg-green-100 text-green-800 text-xs">Configured</Badge>}
                    </div>
                    
                    <div>
                      <Label>SMS API Key</Label>
                      <Input 
                        type="password"
                        value={settings.sms_api_key}
                        onChange={(e) => setSettings({ ...settings, sms_api_key: e.target.value })}
                        placeholder={settingsLoaded.sms_configured ? "••••••••" : "Enter API key"}
                        className="mt-1"
                      />
                    </div>
                    
                    <div>
                      <Label>SMS API Secret</Label>
                      <Input 
                        type="password"
                        value={settings.sms_api_secret}
                        onChange={(e) => setSettings({ ...settings, sms_api_secret: e.target.value })}
                        placeholder="Enter API secret (if required)"
                        className="mt-1"
                      />
                    </div>
                    
                    <div>
                      <Label>Sender ID / From Number</Label>
                      <Input 
                        value={settings.sms_sender_id || settingsLoaded.sms_sender_id}
                        onChange={(e) => setSettings({ ...settings, sms_sender_id: e.target.value })}
                        placeholder="e.g., K3GAS or +1234567890"
                        className="mt-1"
                      />
                    </div>
                  </div>

                  {/* WhatsApp Settings */}
                  <div className="p-4 border rounded-lg space-y-4">
                    <div className="flex items-center gap-2 mb-2">
                      <MessageCircle className="w-5 h-5 text-green-600" />
                      <h3 className="font-semibold">WhatsApp Configuration</h3>
                      {settingsLoaded.whatsapp_configured && <Badge className="bg-green-100 text-green-800 text-xs">Configured</Badge>}
                    </div>
                    
                    <div>
                      <Label>WhatsApp API Key / Access Token</Label>
                      <Input 
                        type="password"
                        value={settings.whatsapp_api_key}
                        onChange={(e) => setSettings({ ...settings, whatsapp_api_key: e.target.value })}
                        placeholder={settingsLoaded.whatsapp_configured ? "••••••••" : "Enter API key"}
                        className="mt-1"
                      />
                    </div>
                    
                    <div>
                      <Label>WhatsApp API Secret</Label>
                      <Input 
                        type="password"
                        value={settings.whatsapp_api_secret}
                        onChange={(e) => setSettings({ ...settings, whatsapp_api_secret: e.target.value })}
                        placeholder="Enter API secret (if required)"
                        className="mt-1"
                      />
                    </div>
                    
                    <div>
                      <Label>WhatsApp Phone Number</Label>
                      <Input 
                        value={settings.whatsapp_phone_number || settingsLoaded.whatsapp_phone_number}
                        onChange={(e) => setSettings({ ...settings, whatsapp_phone_number: e.target.value })}
                        placeholder="e.g., +919876543210"
                        className="mt-1"
                      />
                    </div>
                    
                    <div>
                      <Label>WhatsApp Business ID (Meta)</Label>
                      <Input 
                        value={settings.whatsapp_business_id}
                        onChange={(e) => setSettings({ ...settings, whatsapp_business_id: e.target.value })}
                        placeholder="For Meta WhatsApp Business API"
                        className="mt-1"
                      />
                    </div>
                  </div>
                </div>

                <Alert className="bg-blue-50 border-blue-200">
                  <Info className="w-4 h-4 text-blue-600" />
                  <AlertDescription className="text-blue-800">
                    <strong>How to configure:</strong> Get API credentials from your messaging provider (Twilio, MSG91, Meta, etc.) and enter them here. 
                    The system will automatically use these credentials when sending messages.
                  </AlertDescription>
                </Alert>

                <div className="flex justify-end">
                  <Button 
                    onClick={handleSaveSettings}
                    disabled={savingSettings}
                    className="bg-green-700 hover:bg-green-800"
                  >
                    {savingSettings ? (
                      <><Loader2 className="w-4 h-4 animate-spin mr-2" /> Saving...</>
                    ) : (
                      <><Settings className="w-4 h-4 mr-2" /> Save Settings</>
                    )}
                  </Button>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* Log Detail Dialog */}
        <Dialog open={logDetailOpen} onOpenChange={setLogDetailOpen}>
          <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Message Details</DialogTitle>
              <DialogDescription>
                Sent on {selectedLog && formatDate(selectedLog.created_at)}
              </DialogDescription>
            </DialogHeader>
            {selectedLog && (
              <div className="space-y-4 py-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-slate-500">Channel</Label>
                    <p>{getChannelBadge(selectedLog.channel)}</p>
                  </div>
                  <div>
                    <Label className="text-slate-500">Status</Label>
                    <p>
                      {selectedLog.status === 'completed' ? (
                        <Badge className="bg-green-100 text-green-800">Completed</Badge>
                      ) : (
                        <Badge variant="outline">{selectedLog.status}</Badge>
                      )}
                    </p>
                  </div>
                  <div>
                    <Label className="text-slate-500">Total Recipients</Label>
                    <p className="font-medium">{selectedLog.recipient_count}</p>
                  </div>
                  <div>
                    <Label className="text-slate-500">Success / Failed</Label>
                    <p>
                      <span className="text-green-600 font-medium">{selectedLog.successful_count}</span>
                      {' / '}
                      <span className="text-red-600 font-medium">{selectedLog.failed_count}</span>
                    </p>
                  </div>
                </div>
                
                <div>
                  <Label className="text-slate-500">Message</Label>
                  <div className="p-3 bg-slate-50 rounded-lg mt-1 whitespace-pre-wrap">
                    {selectedLog.message}
                  </div>
                </div>

                {selectedLog.results && selectedLog.results.length > 0 && (
                  <div>
                    <Label className="text-slate-500">Delivery Results (First 100)</Label>
                    <div className="mt-2 max-h-[200px] overflow-y-auto border rounded">
                      <table className="w-full text-sm">
                        <thead className="bg-slate-50 sticky top-0">
                          <tr>
                            <th className="p-2 text-left">Recipient</th>
                            <th className="p-2 text-left">Phone</th>
                            <th className="p-2 text-center">SMS</th>
                            <th className="p-2 text-center">WhatsApp</th>
                          </tr>
                        </thead>
                        <tbody>
                          {selectedLog.results.map((r, i) => (
                            <tr key={i} className="border-t">
                              <td className="p-2">{r.recipient}</td>
                              <td className="p-2">{r.phone}</td>
                              <td className="p-2 text-center">
                                {r.sms ? (
                                  r.sms.success ? <CheckCircle2 className="w-4 h-4 text-green-600 mx-auto" /> : <XCircle className="w-4 h-4 text-red-600 mx-auto" />
                                ) : '-'}
                              </td>
                              <td className="p-2 text-center">
                                {r.whatsapp ? (
                                  r.whatsapp.success ? <CheckCircle2 className="w-4 h-4 text-green-600 mx-auto" /> : <XCircle className="w-4 h-4 text-red-600 mx-auto" />
                                ) : '-'}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}
            <DialogFooter>
              <DialogClose asChild>
                <Button variant="outline">Close</Button>
              </DialogClose>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </Layout>
  );
};

export default BulkMessaging;
