import React, { useState, useEffect, useRef } from 'react';
import { Search, X, ChevronDown, Check, Loader2 } from 'lucide-react';
import { cn } from '../lib/utils';
import { HighlightMatch } from './SearchBar';

/**
 * Searchable Select/Dropdown Component
 * @param {Object} props
 * @param {Array} props.options - Array of options [{id, name, ...}, ...]
 * @param {string} props.value - Selected value (id)
 * @param {Function} props.onChange - Callback when selection changes
 * @param {string} props.placeholder - Placeholder text
 * @param {string} props.labelField - Field to display as label
 * @param {string} props.valueField - Field to use as value
 * @param {Array} props.searchFields - Fields to search in
 * @param {string} props.className - Additional CSS classes
 * @param {boolean} props.disabled - Disable the select
 * @param {string} props.emptyMessage - Message when no results found
 */
const SearchableSelect = ({
  options = [],
  value,
  onChange,
  placeholder = 'Select...',
  labelField = 'name',
  valueField = 'id',
  searchFields = ['name'],
  className = '',
  disabled = false,
  emptyMessage = 'No results found'
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [filteredOptions, setFilteredOptions] = useState(options);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const containerRef = useRef(null);
  const inputRef = useRef(null);

  // Get selected option
  const selectedOption = options.find(opt => opt[valueField] === value);

  // Filter options when query changes
  useEffect(() => {
    if (!query.trim()) {
      setFilteredOptions(options);
      return;
    }

    const normalizedQuery = query.toLowerCase().trim();
    const filtered = options.filter(opt => {
      return searchFields.some(field => {
        const val = String(opt[field] || '').toLowerCase();
        return val.includes(normalizedQuery);
      });
    });

    // Sort by relevance
    filtered.sort((a, b) => {
      const aName = String(a[labelField] || '').toLowerCase();
      const bName = String(b[labelField] || '').toLowerCase();
      
      // Exact match first
      if (aName === normalizedQuery) return -1;
      if (bName === normalizedQuery) return 1;
      
      // Starts with query
      if (aName.startsWith(normalizedQuery) && !bName.startsWith(normalizedQuery)) return -1;
      if (bName.startsWith(normalizedQuery) && !aName.startsWith(normalizedQuery)) return 1;
      
      return 0;
    });

    setFilteredOptions(filtered);
    setHighlightedIndex(filtered.length > 0 ? 0 : -1);
  }, [query, options, searchFields, labelField]);

  // Reset filtered options when options change
  useEffect(() => {
    setFilteredOptions(options);
  }, [options]);

  // Close on outside click
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setIsOpen(false);
        setQuery('');
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Keyboard navigation
  const handleKeyDown = (e) => {
    if (!isOpen) {
      if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') {
        e.preventDefault();
        setIsOpen(true);
      }
      return;
    }

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setHighlightedIndex(prev => 
          prev < filteredOptions.length - 1 ? prev + 1 : 0
        );
        break;
      case 'ArrowUp':
        e.preventDefault();
        setHighlightedIndex(prev => 
          prev > 0 ? prev - 1 : filteredOptions.length - 1
        );
        break;
      case 'Enter':
        e.preventDefault();
        if (highlightedIndex >= 0 && filteredOptions[highlightedIndex]) {
          handleSelect(filteredOptions[highlightedIndex]);
        }
        break;
      case 'Escape':
        setIsOpen(false);
        setQuery('');
        break;
    }
  };

  const handleSelect = (option) => {
    onChange(option[valueField]);
    setIsOpen(false);
    setQuery('');
    setHighlightedIndex(-1);
  };

  const clearSelection = (e) => {
    e.stopPropagation();
    onChange('');
    setQuery('');
  };

  return (
    <div ref={containerRef} className={cn('relative', className)}>
      {/* Trigger Button */}
      <button
        type="button"
        onClick={() => !disabled && setIsOpen(!isOpen)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        className={cn(
          'w-full flex items-center justify-between px-3 py-2 text-left bg-white border rounded-md transition-colors',
          'focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-green-500',
          disabled ? 'bg-slate-100 cursor-not-allowed opacity-60' : 'hover:border-slate-400',
          isOpen ? 'border-green-500 ring-2 ring-green-500' : 'border-slate-200'
        )}
        data-testid="searchable-select-trigger"
      >
        <span className={cn(
          'truncate',
          selectedOption ? 'text-slate-900' : 'text-slate-500'
        )}>
          {selectedOption ? selectedOption[labelField] : placeholder}
        </span>
        <div className="flex items-center gap-1">
          {value && !disabled && (
            <span
              onClick={clearSelection}
              className="p-1 hover:bg-slate-100 rounded"
            >
              <X className="w-3 h-3 text-slate-400" />
            </span>
          )}
          <ChevronDown className={cn(
            'w-4 h-4 text-slate-400 transition-transform',
            isOpen && 'transform rotate-180'
          )} />
        </div>
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute z-50 w-full mt-1 bg-white border border-slate-200 rounded-lg shadow-lg overflow-hidden">
          {/* Search Input */}
          <div className="p-2 border-b border-slate-100">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input
                ref={inputRef}
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Type to search..."
                className="w-full pl-9 pr-8 py-2 text-sm border border-slate-200 rounded-md focus:outline-none focus:border-green-500"
                autoFocus
                data-testid="searchable-select-input"
              />
              {query && (
                <button
                  onClick={() => setQuery('')}
                  className="absolute right-2 top-1/2 transform -translate-y-1/2 p-1 hover:bg-slate-100 rounded"
                >
                  <X className="w-3 h-3 text-slate-400" />
                </button>
              )}
            </div>
          </div>

          {/* Options List */}
          <div className="max-h-60 overflow-y-auto">
            {filteredOptions.length > 0 ? (
              filteredOptions.map((option, index) => (
                <div
                  key={option[valueField]}
                  onClick={() => handleSelect(option)}
                  className={cn(
                    'px-3 py-2 cursor-pointer flex items-center justify-between transition-colors',
                    highlightedIndex === index ? 'bg-green-50' : 'hover:bg-slate-50',
                    option[valueField] === value && 'bg-green-50'
                  )}
                >
                  <div>
                    <div className="font-medium text-sm">
                      <HighlightMatch text={option[labelField]} query={query} />
                    </div>
                    {/* Show additional search fields */}
                    {searchFields.length > 1 && query && (
                      <div className="text-xs text-slate-500">
                        {searchFields
                          .filter(f => f !== labelField && option[f])
                          .map(f => (
                            <span key={f} className="mr-2">
                              <HighlightMatch text={option[f]} query={query} />
                            </span>
                          ))
                        }
                      </div>
                    )}
                  </div>
                  {option[valueField] === value && (
                    <Check className="w-4 h-4 text-green-600" />
                  )}
                </div>
              ))
            ) : (
              <div className="px-3 py-8 text-center text-slate-500 text-sm">
                {emptyMessage}
              </div>
            )}
          </div>

          {/* Results count */}
          {query && (
            <div className="px-3 py-2 border-t border-slate-100 text-xs text-slate-500 bg-slate-50">
              {filteredOptions.length} result{filteredOptions.length !== 1 ? 's' : ''} found
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default SearchableSelect;
