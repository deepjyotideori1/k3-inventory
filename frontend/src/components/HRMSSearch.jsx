import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../lib/api';
import { Search, X, Users, Building2, DollarSign, Briefcase, Target, Loader2 } from 'lucide-react';

const MODULE_ICONS = {
  Employees: Users,
  Departments: Building2,
  Payroll: DollarSign,
  Hiring: Briefcase,
  Performance: Target,
};

const MODULE_COLORS = {
  Employees: 'bg-blue-100 text-blue-700',
  Departments: 'bg-emerald-100 text-emerald-700',
  Payroll: 'bg-violet-100 text-violet-700',
  Hiring: 'bg-amber-100 text-amber-700',
  Performance: 'bg-rose-100 text-rose-700',
};

const highlightText = (text, query) => {
  if (!query || !text) return text;
  const parts = String(text).split(new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi'));
  return parts.map((part, i) =>
    part.toLowerCase() === query.toLowerCase()
      ? <mark key={i} className="bg-yellow-200 text-yellow-900 rounded-sm px-0.5">{part}</mark>
      : part
  );
};

const HRMSSearch = () => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [moduleCounts, setModuleCounts] = useState({});
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [activeModule, setActiveModule] = useState('all');
  const inputRef = useRef(null);
  const containerRef = useRef(null);
  const navigate = useNavigate();

  const search = useCallback(async (q) => {
    if (!q || q.length < 1) {
      setResults([]); setTotal(0); setModuleCounts({}); setOpen(false);
      return;
    }
    setLoading(true);
    try {
      const res = await api.get('/hrms/search', { params: { q } });
      setResults(res.data.results || []);
      setTotal(res.data.total || 0);
      setModuleCounts(res.data.module_counts || {});
      setOpen(true);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => search(query), 300);
    return () => clearTimeout(timer);
  }, [query, search]);

  // Close on click outside
  useEffect(() => {
    const handler = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  // Keyboard shortcut: Ctrl+K
  useEffect(() => {
    const handler = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        inputRef.current?.focus();
      }
      if (e.key === 'Escape') { setOpen(false); inputRef.current?.blur(); }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, []);

  const handleResultClick = (result) => {
    setOpen(false);
    setQuery('');
    navigate(result.link);
  };

  const filtered = activeModule === 'all' ? results : results.filter(r => r.module === activeModule);
  const modules = Object.keys(moduleCounts);

  return (
    <div ref={containerRef} className="relative flex-1 max-w-xl" data-testid="hrms-search-container">
      {/* Search Input */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={e => setQuery(e.target.value)}
          onFocus={() => { if (results.length > 0) setOpen(true); }}
          placeholder="Search employees, departments, payroll..."
          className="w-full pl-9 pr-20 py-2 text-sm border border-slate-200 rounded-lg bg-slate-50 focus:bg-white focus:border-blue-400 focus:ring-1 focus:ring-blue-100 outline-none transition"
          data-testid="hrms-search-input"
        />
        <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
          {loading && <Loader2 className="w-4 h-4 animate-spin text-blue-500" />}
          {query && !loading && (
            <button onClick={() => { setQuery(''); setResults([]); setOpen(false); }} className="p-0.5 hover:bg-slate-200 rounded" data-testid="hrms-search-clear">
              <X className="w-3.5 h-3.5 text-slate-400" />
            </button>
          )}
          <kbd className="hidden sm:inline text-[10px] text-slate-400 border border-slate-200 px-1.5 py-0.5 rounded">Ctrl+K</kbd>
        </div>
      </div>

      {/* Results Dropdown */}
      {open && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-slate-200 rounded-lg shadow-xl z-50 max-h-[480px] overflow-hidden" data-testid="hrms-search-results">
          {/* Header */}
          <div className="px-3 py-2 border-b border-slate-100 flex items-center justify-between">
            <span className="text-xs text-slate-500">
              {total > 0 ? (
                <>Found <strong className="text-slate-700" data-testid="hrms-search-total">{total}</strong> result{total !== 1 ? 's' : ''} for "<strong className="text-blue-600">{query}</strong>"</>
              ) : (
                <>No results for "<strong className="text-slate-700">{query}</strong>"</>
              )}
            </span>
          </div>

          {total > 0 && (
            <>
              {/* Module filter tabs */}
              {modules.length > 1 && (
                <div className="flex gap-1 px-3 py-2 border-b border-slate-100 overflow-x-auto">
                  <button
                    onClick={() => setActiveModule('all')}
                    className={`px-2 py-1 rounded text-[11px] font-medium whitespace-nowrap transition ${activeModule === 'all' ? 'bg-blue-100 text-blue-700' : 'text-slate-500 hover:bg-slate-100'}`}
                    data-testid="search-filter-all"
                  >
                    All ({total})
                  </button>
                  {modules.map(mod => (
                    <button
                      key={mod}
                      onClick={() => setActiveModule(mod)}
                      className={`px-2 py-1 rounded text-[11px] font-medium whitespace-nowrap transition ${activeModule === mod ? 'bg-blue-100 text-blue-700' : 'text-slate-500 hover:bg-slate-100'}`}
                      data-testid={`search-filter-${mod.toLowerCase()}`}
                    >
                      {mod} ({moduleCounts[mod]})
                    </button>
                  ))}
                </div>
              )}

              {/* Results list */}
              <div className="overflow-y-auto max-h-[380px]">
                {filtered.map((r, i) => {
                  const Icon = MODULE_ICONS[r.module] || Users;
                  const colorClass = MODULE_COLORS[r.module] || 'bg-slate-100 text-slate-600';
                  return (
                    <button
                      key={`${r.module}-${r.id}-${i}`}
                      onClick={() => handleResultClick(r)}
                      className="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-blue-50 transition text-left border-b border-slate-50 last:border-0"
                      data-testid={`search-result-${i}`}
                    >
                      <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${colorClass}`}>
                        <Icon className="w-4 h-4" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-slate-800 truncate">
                          {highlightText(r.title, query)}
                        </p>
                        <p className="text-xs text-slate-500 truncate">
                          {highlightText(r.subtitle, query)}
                        </p>
                      </div>
                      <div className="flex-shrink-0 text-right">
                        {r.meta && <p className="text-[10px] text-slate-400">{highlightText(r.meta, query)}</p>}
                        {r.status && (
                          <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                            r.status === 'Active' ? 'bg-green-100 text-green-700' :
                            r.status === 'Inactive' ? 'bg-red-100 text-red-700' :
                            'bg-slate-100 text-slate-600'
                          }`}>
                            {r.status}
                          </span>
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>
            </>
          )}

          {total === 0 && !loading && (
            <div className="px-4 py-8 text-center">
              <Search className="w-8 h-8 text-slate-200 mx-auto mb-2" />
              <p className="text-sm text-slate-400">No matches found</p>
              <p className="text-xs text-slate-300 mt-1">Try different keywords or check spelling</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default HRMSSearch;
