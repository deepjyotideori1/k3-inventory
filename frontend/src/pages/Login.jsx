import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { login, getSettings } from '../lib/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { AlertCircle, Loader2, Eye, EyeOff, Wrench } from 'lucide-react';
import { toast } from 'sonner';

const Login = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [maintenanceMode, setMaintenanceMode] = useState(false);
  const [maintenanceMessage, setMaintenanceMessage] = useState('');
  
  const { loginUser, user } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (user) {
      navigate(user.role === 'admin' ? '/dashboard' : '/manager-dashboard');
    }
    checkMaintenance();
  }, [user, navigate]);

  const checkMaintenance = async () => {
    try {
      const res = await getSettings();
      setMaintenanceMode(res.data.maintenance_mode);
      setMaintenanceMessage(res.data.maintenance_message);
    } catch (err) {
      console.error('Failed to check maintenance mode');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await login(email, password);
      loginUser(response.data.user, response.data.token);
      toast.success('Login successful!');
      navigate(response.data.user.role === 'admin' ? '/dashboard' : '/manager-dashboard');
    } catch (err) {
      const message = err.response?.data?.detail || 'Login failed. Please try again.';
      setError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex" data-testid="login-page">
      {/* Left Panel - Form */}
      <div className="w-full lg:w-1/2 flex items-center justify-center p-8 lg:p-12 bg-white">
        <div className="w-full max-w-md">
          {/* Logo */}
          <div className="mb-8">
            <div className="flex items-center gap-3 mb-6">
              <img 
                src="https://customer-assets.emergentagent.com/job_gas-stock-master/artifacts/nww68qmn_customcolor_icon_customcolor_background.png" 
                alt="K3 Logo" 
                className="w-14 h-14 object-contain"
              />
              <div>
                <h1 className="logo-text text-2xl">K3 GAS SERVICE</h1>
                <p className="text-slate-500 text-sm">Khayal Hamesha</p>
              </div>
            </div>
          </div>

          {/* Maintenance Banner */}
          {maintenanceMode && (
            <div className="mb-6 p-4 bg-orange-50 border border-orange-200 rounded-lg flex items-start gap-3" data-testid="maintenance-notice">
              <Wrench className="w-5 h-5 text-orange-600 mt-0.5" />
              <div>
                <p className="text-orange-800 font-medium text-sm">Under Maintenance</p>
                <p className="text-orange-700 text-sm mt-1">{maintenanceMessage}</p>
                <p className="text-orange-600 text-xs mt-2">Admin login is still available.</p>
              </div>
            </div>
          )}

          <Card className="border-0 shadow-none">
            <CardHeader className="px-0 pt-0">
              <CardTitle className="text-2xl font-bold text-slate-800">Welcome back</CardTitle>
              <CardDescription className="text-slate-500">
                Sign in to access your inventory dashboard
              </CardDescription>
            </CardHeader>
            <CardContent className="px-0">
              <form onSubmit={handleSubmit} className="space-y-5">
                {error && (
                  <div className="p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-red-700 text-sm" data-testid="login-error">
                    <AlertCircle className="w-4 h-4" />
                    {error}
                  </div>
                )}

                <div className="space-y-2">
                  <Label htmlFor="email" className="text-slate-700 font-medium">Email</Label>
                  <Input
                    id="email"
                    type="email"
                    placeholder="Enter your email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    className="h-11"
                    data-testid="email-input"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="password" className="text-slate-700 font-medium">Password</Label>
                  <div className="relative">
                    <Input
                      id="password"
                      type={showPassword ? 'text' : 'password'}
                      placeholder="Enter your password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                      className="h-11 pr-10"
                      data-testid="password-input"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                    >
                      {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                <Button
                  type="submit"
                  className="w-full h-11 bg-green-700 hover:bg-green-800 text-white font-medium"
                  disabled={loading}
                  data-testid="login-submit-btn"
                >
                  {loading ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Signing in...
                    </>
                  ) : (
                    'Sign in'
                  )}
                </Button>
              </form>

              <div className="mt-8 pt-6 border-t border-slate-100">
                <p className="text-slate-500 text-sm text-center">
                  Contact admin if you need access credentials
                </p>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Right Panel - Image */}
      <div className="hidden lg:block lg:w-1/2 login-bg-image">
        <div className="relative z-10 h-full flex items-end p-12">
          <div className="text-white">
            <h2 className="text-4xl font-bold mb-4 drop-shadow-lg">
              Inventory Management
            </h2>
            <p className="text-xl text-white/90 drop-shadow-md">
              Streamline your LPG cylinder tracking across all warehouses
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Login;
