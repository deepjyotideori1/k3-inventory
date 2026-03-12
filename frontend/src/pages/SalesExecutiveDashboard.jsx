import React, { useState, useEffect } from 'react';
import Layout from '../components/Layout';
import { useAuth } from '../context/AuthContext';
import { getCustomers, getOrders } from '../lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Link } from 'react-router-dom';
import {
  Users,
  ShoppingCart,
  MessageSquare,
  TrendingUp,
  Clock,
  CheckCircle,
  XCircle,
  Loader2,
  ArrowRight,
  Phone,
  Calendar
} from 'lucide-react';
import { formatDate } from '../lib/utils';

const SalesExecutiveDashboard = () => {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({
    totalCustomers: 0,
    totalOrders: 0,
    pendingOrders: 0,
    completedOrders: 0,
    todayOrders: 0
  });
  const [recentOrders, setRecentOrders] = useState([]);
  const [recentCustomers, setRecentCustomers] = useState([]);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      const [customersRes, ordersRes] = await Promise.all([
        getCustomers(),
        getOrders()
      ]);

      const customers = customersRes.data;
      const orders = ordersRes.data;

      // Calculate stats
      const today = new Date().toISOString().split('T')[0];
      const pendingOrders = orders.filter(o => o.status === 'pending').length;
      const completedOrders = orders.filter(o => o.status === 'delivered').length;
      const todayOrders = orders.filter(o => o.order_date === today).length;

      setStats({
        totalCustomers: customers.length,
        totalOrders: orders.length,
        pendingOrders,
        completedOrders,
        todayOrders
      });

      // Recent orders (last 5)
      setRecentOrders(orders.slice(0, 5));
      // Recent customers (last 5)
      setRecentCustomers(customers.slice(0, 5));

    } catch (error) {
      console.error('Failed to fetch dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status) => {
    const statusConfig = {
      pending: { color: 'bg-amber-100 text-amber-700', icon: Clock },
      confirmed: { color: 'bg-blue-100 text-blue-700', icon: CheckCircle },
      processing: { color: 'bg-purple-100 text-purple-700', icon: TrendingUp },
      delivered: { color: 'bg-green-100 text-green-700', icon: CheckCircle },
      cancelled: { color: 'bg-red-100 text-red-700', icon: XCircle }
    };
    const config = statusConfig[status] || statusConfig.pending;
    const Icon = config.icon;
    return (
      <Badge className={`${config.color} gap-1`}>
        <Icon className="w-3 h-3" />
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </Badge>
    );
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
      <div className="space-y-6" data-testid="sales-dashboard">
        {/* Welcome Header */}
        <div className="bg-gradient-to-r from-green-700 to-green-600 rounded-2xl p-6 text-white">
          <h1 className="text-2xl font-bold">Welcome back, {user?.name}!</h1>
          <p className="text-green-100 mt-1">Sales Executive Dashboard - Manage customers, orders, and messaging</p>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
          <Card className="bg-gradient-to-br from-blue-50 to-blue-100 border-blue-200">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-blue-600 font-medium">Total Customers</p>
                  <p className="text-3xl font-bold text-blue-800">{stats.totalCustomers}</p>
                </div>
                <div className="p-3 bg-blue-500 rounded-xl">
                  <Users className="w-6 h-6 text-white" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-gradient-to-br from-purple-50 to-purple-100 border-purple-200">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-purple-600 font-medium">Total Orders</p>
                  <p className="text-3xl font-bold text-purple-800">{stats.totalOrders}</p>
                </div>
                <div className="p-3 bg-purple-500 rounded-xl">
                  <ShoppingCart className="w-6 h-6 text-white" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-gradient-to-br from-amber-50 to-amber-100 border-amber-200">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-amber-600 font-medium">Pending Orders</p>
                  <p className="text-3xl font-bold text-amber-800">{stats.pendingOrders}</p>
                </div>
                <div className="p-3 bg-amber-500 rounded-xl">
                  <Clock className="w-6 h-6 text-white" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-gradient-to-br from-green-50 to-green-100 border-green-200">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-green-600 font-medium">Completed</p>
                  <p className="text-3xl font-bold text-green-800">{stats.completedOrders}</p>
                </div>
                <div className="p-3 bg-green-500 rounded-xl">
                  <CheckCircle className="w-6 h-6 text-white" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-gradient-to-br from-rose-50 to-rose-100 border-rose-200">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-rose-600 font-medium">Today's Orders</p>
                  <p className="text-3xl font-bold text-rose-800">{stats.todayOrders}</p>
                </div>
                <div className="p-3 bg-rose-500 rounded-xl">
                  <Calendar className="w-6 h-6 text-white" />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Quick Actions */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Link to="/customers">
            <Card className="cursor-pointer hover:shadow-lg transition-shadow border-2 border-transparent hover:border-blue-300">
              <CardContent className="p-6 flex items-center gap-4">
                <div className="p-4 bg-blue-100 rounded-xl">
                  <Users className="w-8 h-8 text-blue-600" />
                </div>
                <div className="flex-1">
                  <h3 className="font-semibold text-lg">Manage Customers</h3>
                  <p className="text-slate-500 text-sm">Add, edit, view customers</p>
                </div>
                <ArrowRight className="w-5 h-5 text-slate-400" />
              </CardContent>
            </Card>
          </Link>

          <Link to="/orders">
            <Card className="cursor-pointer hover:shadow-lg transition-shadow border-2 border-transparent hover:border-purple-300">
              <CardContent className="p-6 flex items-center gap-4">
                <div className="p-4 bg-purple-100 rounded-xl">
                  <ShoppingCart className="w-8 h-8 text-purple-600" />
                </div>
                <div className="flex-1">
                  <h3 className="font-semibold text-lg">Manage Orders</h3>
                  <p className="text-slate-500 text-sm">Create and track orders</p>
                </div>
                <ArrowRight className="w-5 h-5 text-slate-400" />
              </CardContent>
            </Card>
          </Link>

          <Link to="/bulk-messaging">
            <Card className="cursor-pointer hover:shadow-lg transition-shadow border-2 border-transparent hover:border-green-300">
              <CardContent className="p-6 flex items-center gap-4">
                <div className="p-4 bg-green-100 rounded-xl">
                  <MessageSquare className="w-8 h-8 text-green-600" />
                </div>
                <div className="flex-1">
                  <h3 className="font-semibold text-lg">Bulk Messaging</h3>
                  <p className="text-slate-500 text-sm">Send messages to customers</p>
                </div>
                <ArrowRight className="w-5 h-5 text-slate-400" />
              </CardContent>
            </Card>
          </Link>
        </div>

        {/* Recent Activity */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Recent Orders */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-lg flex items-center justify-between">
                <span className="flex items-center gap-2">
                  <ShoppingCart className="w-5 h-5 text-purple-600" />
                  Recent Orders
                </span>
                <Link to="/orders">
                  <Button variant="ghost" size="sm" className="text-purple-600 hover:text-purple-700">
                    View All <ArrowRight className="w-4 h-4 ml-1" />
                  </Button>
                </Link>
              </CardTitle>
            </CardHeader>
            <CardContent>
              {recentOrders.length === 0 ? (
                <p className="text-slate-500 text-center py-8">No orders yet</p>
              ) : (
                <div className="space-y-3">
                  {recentOrders.map((order) => (
                    <div key={order.id} className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
                      <div>
                        <p className="font-medium">{order.order_no}</p>
                        <p className="text-sm text-slate-500">{order.customer_name}</p>
                      </div>
                      <div className="text-right">
                        {getStatusBadge(order.status)}
                        <p className="text-xs text-slate-400 mt-1">{formatDate(order.order_date)}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Recent Customers */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-lg flex items-center justify-between">
                <span className="flex items-center gap-2">
                  <Users className="w-5 h-5 text-blue-600" />
                  Recent Customers
                </span>
                <Link to="/customers">
                  <Button variant="ghost" size="sm" className="text-blue-600 hover:text-blue-700">
                    View All <ArrowRight className="w-4 h-4 ml-1" />
                  </Button>
                </Link>
              </CardTitle>
            </CardHeader>
            <CardContent>
              {recentCustomers.length === 0 ? (
                <p className="text-slate-500 text-center py-8">No customers yet</p>
              ) : (
                <div className="space-y-3">
                  {recentCustomers.map((customer) => (
                    <div key={customer.id} className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
                      <div>
                        <p className="font-medium">{customer.name}</p>
                        <p className="text-sm text-slate-500 flex items-center gap-1">
                          <Phone className="w-3 h-3" /> {customer.phone}
                        </p>
                      </div>
                      <Badge className="bg-slate-100 text-slate-600">
                        {customer.category}
                      </Badge>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </Layout>
  );
};

export default SalesExecutiveDashboard;
