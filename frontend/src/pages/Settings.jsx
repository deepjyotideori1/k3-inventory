import React, { useState, useEffect } from 'react';
import Layout from '../components/Layout';
import { useAuth } from '../context/AuthContext';
import { getSettings, updateSettings, getInventoryItems, createInventoryItem } from '../lib/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Switch } from '../components/ui/switch';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Separator } from '../components/ui/separator';
import { 
  Settings,
  Wrench,
  Package,
  Plus,
  Loader2,
  AlertTriangle,
  Info
} from 'lucide-react';
import { toast } from 'sonner';

const SettingsPage = () => {
  const { refreshSettings } = useAuth();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showItemDialog, setShowItemDialog] = useState(false);
  
  const [settings, setSettingsState] = useState({
    maintenance_mode: false,
    maintenance_message: '',
    app_version: '1.0.0'
  });

  const [inventoryItems, setInventoryItems] = useState([]);
  
  const [newItem, setNewItem] = useState({
    name: '',
    unit: 'units',
    category: 'LPG Cylinder'
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [settingsRes, itemsRes] = await Promise.all([
        getSettings(),
        getInventoryItems()
      ]);
      setSettingsState(settingsRes.data);
      setInventoryItems(itemsRes.data);
    } catch (error) {
      console.error('Failed to fetch data:', error);
      toast.error('Failed to load settings');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveSettings = async () => {
    setSaving(true);
    try {
      await updateSettings({
        maintenance_mode: settings.maintenance_mode,
        maintenance_message: settings.maintenance_message
      });
      toast.success('Settings saved successfully');
      refreshSettings();
    } catch (error) {
      console.error('Failed to save settings:', error);
      toast.error('Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  const handleAddItem = async () => {
    if (!newItem.name) {
      toast.error('Please enter item name');
      return;
    }
    
    setSaving(true);
    try {
      await createInventoryItem(newItem);
      toast.success('Inventory item added successfully');
      setShowItemDialog(false);
      setNewItem({ name: '', unit: 'units', category: 'LPG Cylinder' });
      fetchData();
    } catch (error) {
      console.error('Failed to add item:', error);
      toast.error('Failed to add inventory item');
    } finally {
      setSaving(false);
    }
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
      <div className="max-w-4xl mx-auto space-y-6" data-testid="settings-page">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-slate-800 flex items-center gap-2">
            <Settings className="w-8 h-8 text-green-700" />
            Settings
          </h1>
          <p className="text-slate-500 mt-1">Manage application settings</p>
        </div>

        {/* Maintenance Mode */}
        <Card data-testid="maintenance-settings-card">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Wrench className="w-5 h-5 text-orange-600" />
              Maintenance Mode
            </CardTitle>
            <CardDescription>
              When enabled, only admin users can access the system
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between p-4 bg-slate-50 rounded-lg">
              <div>
                <p className="font-medium text-slate-800">Enable Maintenance Mode</p>
                <p className="text-sm text-slate-500">Warehouse managers will see the maintenance message</p>
              </div>
              <Switch 
                checked={settings.maintenance_mode}
                onCheckedChange={(checked) => setSettingsState(prev => ({ ...prev, maintenance_mode: checked }))}
                data-testid="maintenance-mode-switch"
              />
            </div>

            {settings.maintenance_mode && (
              <div className="p-4 bg-orange-50 border border-orange-200 rounded-lg flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 text-orange-600 mt-0.5" />
                <div>
                  <p className="font-medium text-orange-800">Maintenance Mode is Active</p>
                  <p className="text-sm text-orange-700">Non-admin users cannot access the system</p>
                </div>
              </div>
            )}

            <div>
              <Label>Maintenance Message</Label>
              <Textarea 
                value={settings.maintenance_message}
                onChange={(e) => setSettingsState(prev => ({ ...prev, maintenance_message: e.target.value }))}
                placeholder="Enter message to display during maintenance..."
                className="mt-1"
                data-testid="maintenance-message-input"
              />
            </div>

            <div className="flex justify-end">
              <Button 
                onClick={handleSaveSettings} 
                disabled={saving}
                className="bg-green-700 hover:bg-green-800"
                data-testid="save-settings-btn"
              >
                {saving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
                Save Settings
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Inventory Items */}
        <Card data-testid="inventory-items-card">
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle className="text-lg flex items-center gap-2">
                <Package className="w-5 h-5 text-blue-600" />
                Inventory Items
              </CardTitle>
              <CardDescription>
                Manage inventory item types for all warehouses
              </CardDescription>
            </div>
            <Dialog open={showItemDialog} onOpenChange={setShowItemDialog}>
              <DialogTrigger asChild>
                <Button className="bg-green-700 hover:bg-green-800 gap-2" data-testid="add-item-btn">
                  <Plus className="w-4 h-4" />
                  Add Item
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Add Inventory Item</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 py-4">
                  <div>
                    <Label>Item Name *</Label>
                    <Input 
                      value={newItem.name}
                      onChange={(e) => setNewItem(prev => ({ ...prev, name: e.target.value }))}
                      placeholder="e.g., 5kg Cylinder"
                      className="mt-1"
                      data-testid="item-name-input"
                    />
                  </div>
                  <div>
                    <Label>Unit</Label>
                    <Input 
                      value={newItem.unit}
                      onChange={(e) => setNewItem(prev => ({ ...prev, unit: e.target.value }))}
                      placeholder="e.g., units, kg, liters"
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <Label>Category</Label>
                    <Input 
                      value={newItem.category}
                      onChange={(e) => setNewItem(prev => ({ ...prev, category: e.target.value }))}
                      placeholder="e.g., LPG Cylinder"
                      className="mt-1"
                    />
                  </div>
                  <div className="flex justify-end gap-2">
                    <Button variant="outline" onClick={() => setShowItemDialog(false)}>Cancel</Button>
                    <Button onClick={handleAddItem} disabled={saving} className="bg-green-700 hover:bg-green-800" data-testid="save-item-btn">
                      {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Add Item'}
                    </Button>
                  </div>
                </div>
              </DialogContent>
            </Dialog>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {inventoryItems.map((item) => (
                <div key={item.id} className="flex items-center justify-between p-4 bg-slate-50 rounded-lg" data-testid={`item-${item.id}`}>
                  <div>
                    <p className="font-medium text-slate-800">{item.name}</p>
                    <p className="text-sm text-slate-500">{item.category} · {item.unit}</p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* App Info */}
        <Card data-testid="app-info-card">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Info className="w-5 h-5 text-slate-600" />
              Application Info
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4">
              <div className="p-4 bg-slate-50 rounded-lg">
                <p className="text-sm text-slate-500">Application</p>
                <p className="font-semibold text-slate-800">K3 GAS SERVICE</p>
              </div>
              <div className="p-4 bg-slate-50 rounded-lg">
                <p className="text-sm text-slate-500">Version</p>
                <p className="font-semibold text-slate-800">{settings.app_version}</p>
              </div>
              <div className="p-4 bg-slate-50 rounded-lg">
                <p className="text-sm text-slate-500">Tagline</p>
                <p className="font-semibold text-slate-800">Khayal Hamesha</p>
              </div>
              <div className="p-4 bg-slate-50 rounded-lg">
                <p className="text-sm text-slate-500">Status</p>
                <p className="font-semibold text-green-700">Active</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </Layout>
  );
};

export default SettingsPage;
