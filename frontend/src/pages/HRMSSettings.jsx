import React, { useState, useEffect } from 'react';
import HRMSLayout from '../components/HRMSLayout';
import api from '../lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Upload, Save, Building2 } from 'lucide-react';
import { toast } from 'sonner';

const HRMSSettings = () => {
  const [settings, setSettings] = useState({
    company_name: '', tagline: '', address: '', email: '', helpline: '', logo_url: ''
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => { fetchSettings(); }, []);

  const fetchSettings = async () => {
    try {
      const res = await api.get('/hrms/company-settings');
      setSettings(res.data);
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.put('/hrms/company-settings', settings);
      toast.success('Company settings updated');
    } catch (e) { toast.error('Failed to update settings'); }
    setSaving(false);
  };

  const handleLogoUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append('file', file);
    try {
      const res = await api.post('/hrms/company-logo', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      setSettings(s => ({ ...s, logo_url: res.data.logo_url }));
      toast.success('Logo uploaded');
    } catch (e) { toast.error('Failed to upload logo'); }
  };

  if (loading) {
    return <HRMSLayout><div className="flex items-center justify-center h-64"><div className="animate-spin w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full" /></div></HRMSLayout>;
  }

  return (
    <HRMSLayout>
      <div className="space-y-6 max-w-2xl" data-testid="hrms-settings">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Company Settings</h1>
          <p className="text-slate-500 text-sm">Manage company information displayed on reports and documents</p>
        </div>

        {/* Logo */}
        <Card>
          <CardHeader className="pb-3"><CardTitle className="text-base">Company Logo</CardTitle></CardHeader>
          <CardContent>
            <div className="flex items-center gap-6">
              <div className="w-24 h-24 rounded-xl border-2 border-dashed border-slate-200 flex items-center justify-center overflow-hidden bg-slate-50">
                {settings.logo_url ? (
                  <img src={settings.logo_url} alt="Logo" className="w-full h-full object-contain" />
                ) : (
                  <Building2 className="w-8 h-8 text-slate-300" />
                )}
              </div>
              <div>
                <label className="cursor-pointer">
                  <input type="file" accept="image/*" className="hidden" onChange={handleLogoUpload} />
                  <Button variant="outline" className="gap-2" asChild><span><Upload className="w-4 h-4" /> Upload Logo</span></Button>
                </label>
                <p className="text-xs text-slate-400 mt-2">Max 2MB. PNG, JPG, or SVG</p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Company Details */}
        <Card>
          <CardHeader className="pb-3"><CardTitle className="text-base">Company Details</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div><Label>Company Name</Label><Input value={settings.company_name} onChange={e => setSettings(s => ({ ...s, company_name: e.target.value }))} data-testid="company-name" /></div>
            <div><Label>Tagline</Label><Input value={settings.tagline} onChange={e => setSettings(s => ({ ...s, tagline: e.target.value }))} data-testid="company-tagline" /></div>
            <div><Label>Address</Label><Input value={settings.address} onChange={e => setSettings(s => ({ ...s, address: e.target.value }))} data-testid="company-address" /></div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div><Label>Email</Label><Input type="email" value={settings.email} onChange={e => setSettings(s => ({ ...s, email: e.target.value }))} data-testid="company-email" /></div>
              <div><Label>Helpline</Label><Input value={settings.helpline} onChange={e => setSettings(s => ({ ...s, helpline: e.target.value }))} data-testid="company-helpline" /></div>
            </div>
          </CardContent>
        </Card>

        {/* Preview */}
        <Card>
          <CardHeader className="pb-3"><CardTitle className="text-base">Report Header Preview</CardTitle></CardHeader>
          <CardContent>
            <div className="text-center p-6 border rounded-lg bg-white">
              {settings.logo_url && <img src={settings.logo_url} alt="Logo" className="w-16 h-16 mx-auto mb-2 object-contain" />}
              <h2 className="text-lg font-bold text-slate-800">{settings.company_name || 'Company Name'}</h2>
              <p className="text-sm text-slate-500 italic">{settings.tagline || 'Tagline'}</p>
              <p className="text-xs text-slate-400 mt-1">{settings.address || 'Address'}</p>
              <p className="text-xs text-slate-400">{settings.email} | {settings.helpline}</p>
            </div>
          </CardContent>
        </Card>

        <div className="flex justify-end">
          <Button onClick={handleSave} disabled={saving} className="gap-2 bg-blue-600 hover:bg-blue-700" data-testid="save-settings-btn">
            <Save className="w-4 h-4" /> {saving ? 'Saving...' : 'Save Settings'}
          </Button>
        </div>
      </div>
    </HRMSLayout>
  );
};

export default HRMSSettings;
