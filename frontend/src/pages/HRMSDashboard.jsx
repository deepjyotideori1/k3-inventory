import React, { useState, useEffect } from 'react';
import HRMSLayout from '../components/HRMSLayout';
import api from '../lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Users, Building2, DollarSign, UserMinus, UserPlus, TrendingUp } from 'lucide-react';
import { formatINR } from '../lib/utils';

const StatCard = ({ title, value, subtitle, icon: Icon, color }) => (
  <Card data-testid={`stat-${title.toLowerCase().replace(/\s/g, '-')}`}>
    <CardContent className="p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs text-slate-500 font-medium uppercase tracking-wider">{title}</p>
          <p className="text-2xl font-bold text-slate-800 mt-1">{value}</p>
          {subtitle && <p className="text-xs text-slate-400 mt-1">{subtitle}</p>}
        </div>
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${color}`}>
          <Icon className="w-5 h-5" />
        </div>
      </div>
    </CardContent>
  </Card>
);

const HRMSDashboard = () => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const res = await api.get('/hrms/dashboard/stats');
      setStats(res.data);
    } catch (e) {
      console.error('Failed to fetch HRMS stats:', e);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <HRMSLayout>
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full" />
        </div>
      </HRMSLayout>
    );
  }

  return (
    <HRMSLayout>
      <div className="space-y-6" data-testid="hrms-dashboard">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">HRMS Dashboard</h1>
          <p className="text-slate-500 text-sm mt-1">Human Resource Management Overview</p>
        </div>

        {/* Stat Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            title="Total Employees"
            value={stats?.total_employees || 0}
            subtitle={`${stats?.total_inactive || 0} inactive`}
            icon={Users}
            color="bg-blue-50 text-blue-600"
          />
          <StatCard
            title="Departments"
            value={stats?.total_departments || 0}
            icon={Building2}
            color="bg-purple-50 text-purple-600"
          />
          <StatCard
            title="Monthly Payroll"
            value={formatINR ? formatINR(stats?.total_monthly_payroll || 0) : `Rs.${stats?.total_monthly_payroll || 0}`}
            subtitle="Gross salary"
            icon={DollarSign}
            color="bg-green-50 text-green-600"
          />
          <StatCard
            title="Gender Ratio"
            value={`${stats?.gender_breakdown?.male || 0}M / ${stats?.gender_breakdown?.female || 0}F`}
            subtitle={stats?.gender_breakdown?.other > 0 ? `${stats.gender_breakdown.other} others` : ''}
            icon={TrendingUp}
            color="bg-amber-50 text-amber-600"
          />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Department Breakdown */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold text-slate-700">Department Breakdown</CardTitle>
            </CardHeader>
            <CardContent>
              {stats?.department_breakdown?.length > 0 ? (
                <div className="space-y-3">
                  {stats.department_breakdown.map((dept, i) => (
                    <div key={i} className="flex items-center justify-between">
                      <span className="text-sm text-slate-600">{dept.name}</span>
                      <div className="flex items-center gap-3">
                        <div className="w-32 h-2 bg-slate-100 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-blue-500 rounded-full transition-all"
                            style={{ width: `${stats.total_employees > 0 ? (dept.count / stats.total_employees) * 100 : 0}%` }}
                          />
                        </div>
                        <span className="text-sm font-semibold text-slate-700 w-8 text-right">{dept.count}</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-slate-400 text-sm py-4 text-center">No departments created yet</p>
              )}
            </CardContent>
          </Card>

          {/* Recent Employees */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold text-slate-700">Recently Joined</CardTitle>
            </CardHeader>
            <CardContent>
              {stats?.recent_employees?.length > 0 ? (
                <div className="space-y-3">
                  {stats.recent_employees.map((emp, i) => (
                    <div key={i} className="flex items-center gap-3 py-1">
                      <div className="w-9 h-9 rounded-full bg-blue-100 flex items-center justify-center text-sm font-bold text-blue-700 overflow-hidden flex-shrink-0">
                        {emp.photo_url ? (
                          <img src={emp.photo_url} alt="" className="w-full h-full object-cover" />
                        ) : (
                          emp.name?.charAt(0) || '?'
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-slate-700 truncate">{emp.name}</p>
                        <p className="text-xs text-slate-400 truncate">{emp.designation} &middot; {emp.department_name}</p>
                      </div>
                      <span className="text-xs text-slate-400 flex-shrink-0">{emp.date_of_joining}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-slate-400 text-sm py-4 text-center">No employees added yet</p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </HRMSLayout>
  );
};

export default HRMSDashboard;
