import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Search, X, Loader2 } from 'lucide-react';
import { Input } from './ui/input';
import { cn } from '../lib/utils';

/**
 * Dynamic SearchBar Component with autocomplete and highlighting
 * @param {Object} props
 * @param {Array} props.data - Array of objects to search through
 * @param {Array} props.searchFields - Fields to search in (e.g., ['name', 'phone', 'address'])
 * @param {Function} props.onFilter - Callback with filtered results
 * @param {string} props.placeholder - Placeholder text
 * @param {string} props.className - Additional CSS classes
 * @param {boolean} props.showSuggestions - Show autocomplete suggestions dropdown
 * @param {number} props.maxSuggestions - Max number of suggestions to show
 * @param {Function} props.onSelect - Callback when suggestion is selected
 * @param {string} props.suggestionLabelField - Field to display in suggestions
 */
const SearchBar = ({
  data = [],
  searchFields = [],
  onFilter,
  onQueryChange,
  placeholder = 'Search...',
  className = '',
  showSuggestions = false,
  maxSuggestions = 8,
  onSelect,
  suggestionLabelField = 'name',
  disabled = false
}) => {
  const [query, setQuery] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [suggestions, setSuggestions] = useState([]);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const inputRef = useRef(null);
  const dropdownRef = useRef(null);

  // Debounced search
  useEffect(() => {
    if (!query.trim()) {
      onFilter?.(data);
      setSuggestions([]);
      setIsOpen(false);
      return;
    }

    setIsSearching(true);
    const timer = setTimeout(() => {
      const results = performSearch(query, data, searchFields);
      onFilter?.(results);
      
      if (showSuggestions && results.length > 0) {
        setSuggestions(results.slice(0, maxSuggestions));
        setIsOpen(true);
      }
      setIsSearching(false);
    }, 350);

    return () => clearTimeout(timer);
  }, [query, data, searchFields]);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target) &&
          inputRef.current && !inputRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Keyboard navigation
  const handleKeyDown = (e) => {
    if (!isOpen || suggestions.length === 0) return;

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setSelectedIndex(prev => (prev < suggestions.length - 1 ? prev + 1 : 0));
        break;
      case 'ArrowUp':
        e.preventDefault();
        setSelectedIndex(prev => (prev > 0 ? prev - 1 : suggestions.length - 1));
        break;
      case 'Enter':
        e.preventDefault();
        if (selectedIndex >= 0 && suggestions[selectedIndex]) {
          handleSelect(suggestions[selectedIndex]);
        }
        break;
      case 'Escape':
        setIsOpen(false);
        setSelectedIndex(-1);
        break;
    }
  };

  const handleSelect = (item) => {
    const label = getNestedValue(item, suggestionLabelField) || '';
    setQuery(label);
    setIsOpen(false);
    setSelectedIndex(-1);
    onSelect?.(item);
  };

  const clearSearch = () => {
    setQuery('');
    setSuggestions([]);
    setIsOpen(false);
    setSelectedIndex(-1);
    onFilter?.(data);
    onQueryChange?.('');
    inputRef.current?.focus();
  };

  return (
    <div className={cn('relative w-full', className)}>
      <div className="relative">
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-slate-400" />
        <Input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => { setQuery(e.target.value); onQueryChange?.(e.target.value); }}
          onKeyDown={handleKeyDown}
          onFocus={() => showSuggestions && suggestions.length > 0 && setIsOpen(true)}
          placeholder={placeholder}
          disabled={disabled}
          className="pl-10 pr-10 h-10 bg-white border-slate-200 focus:border-green-500 focus:ring-green-500"
          data-testid="search-input"
        />
        {isSearching ? (
          <Loader2 className="absolute right-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-slate-400 animate-spin" />
        ) : query && (
          <button
            onClick={clearSearch}
            className="absolute right-3 top-1/2 transform -translate-y-1/2 p-1 rounded-full hover:bg-slate-100 transition-colors"
            data-testid="clear-search"
          >
            <X className="w-4 h-4 text-slate-400 hover:text-slate-600" />
          </button>
        )}
      </div>

      {/* Live search indicator */}
      {query && (
        <div className="absolute -bottom-5 left-0 text-xs text-slate-500">
          Showing results for "<span className="font-medium text-green-600">{query}</span>"
        </div>
      )}

      {/* Suggestions Dropdown */}
      {showSuggestions && isOpen && suggestions.length > 0 && (
        <div
          ref={dropdownRef}
          className="absolute z-50 w-full mt-1 bg-white border border-slate-200 rounded-lg shadow-lg max-h-64 overflow-y-auto"
        >
          {suggestions.map((item, index) => (
            <SuggestionItem
              key={item.id || index}
              item={item}
              query={query}
              searchFields={searchFields}
              labelField={suggestionLabelField}
              isSelected={index === selectedIndex}
              onClick={() => handleSelect(item)}
            />
          ))}
        </div>
      )}
    </div>
  );
};

// Suggestion Item with highlighting
const SuggestionItem = ({ item, query, searchFields, labelField, isSelected, onClick }) => {
  const label = getNestedValue(item, labelField) || '';
  const secondaryInfo = searchFields
    .filter(f => f !== labelField)
    .map(f => getNestedValue(item, f))
    .filter(Boolean)
    .slice(0, 2)
    .join(' • ');

  return (
    <div
      onClick={onClick}
      className={cn(
        'px-4 py-2 cursor-pointer transition-colors border-b border-slate-100 last:border-0',
        isSelected ? 'bg-green-50' : 'hover:bg-slate-50'
      )}
    >
      <div className="font-medium text-slate-800">
        <HighlightMatch text={label} query={query} />
      </div>
      {secondaryInfo && (
        <div className="text-xs text-slate-500 mt-0.5">
          <HighlightMatch text={secondaryInfo} query={query} />
        </div>
      )}
    </div>
  );
};

// Highlight matched text
export const HighlightMatch = ({ text, query }) => {
  if (!query || !text) return <span>{text}</span>;

  const parts = String(text).split(new RegExp(`(${escapeRegex(query)})`, 'gi'));
  
  return (
    <span>
      {parts.map((part, i) => 
        part.toLowerCase() === query.toLowerCase() ? (
          <mark key={i} className="bg-yellow-200 text-yellow-900 px-0.5 rounded">
            {part}
          </mark>
        ) : (
          <span key={i}>{part}</span>
        )
      )}
    </span>
  );
};

// Search algorithm with ranking
const performSearch = (query, data, fields) => {
  if (!query || !data || data.length === 0) return data;

  const normalizedQuery = query.toLowerCase().trim();
  const queryWords = normalizedQuery.split(/\s+/);

  const scored = data.map(item => {
    let score = 0;
    let matchedFields = [];

    fields.forEach(field => {
      const value = String(getNestedValue(item, field) || '').toLowerCase();
      if (!value) return;

      // Exact match (highest score)
      if (value === normalizedQuery) {
        score += 100;
        matchedFields.push(field);
        return;
      }

      // Starts with query (high score)
      if (value.startsWith(normalizedQuery)) {
        score += 75;
        matchedFields.push(field);
        return;
      }

      // Contains exact query (medium-high score)
      if (value.includes(normalizedQuery)) {
        score += 50;
        matchedFields.push(field);
        return;
      }

      // Word match (medium score)
      const valueWords = value.split(/\s+/);
      const wordMatches = queryWords.filter(qw => 
        valueWords.some(vw => vw.startsWith(qw) || vw.includes(qw))
      );
      if (wordMatches.length > 0) {
        score += 25 * (wordMatches.length / queryWords.length);
        matchedFields.push(field);
      }
    });

    return { item, score, matchedFields };
  });

  // Filter and sort by score (descending)
  return scored
    .filter(s => s.score > 0)
    .sort((a, b) => b.score - a.score)
    .map(s => s.item);
};

// Utility functions
const getNestedValue = (obj, path) => {
  if (!obj || !path) return null;
  return path.split('.').reduce((o, k) => (o || {})[k], obj);
};

const escapeRegex = (string) => {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
};

export default SearchBar;
