import { clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs) {
  return twMerge(clsx(inputs))
}

/**
 * Format number in Indian Rupee format (₹XX,XX,XXX)
 * @param {number} amount - The amount to format
 * @param {boolean} showSymbol - Whether to show ₹ symbol (default: true)
 * @returns {string} Formatted amount string
 */
export function formatINR(amount, showSymbol = true) {
  if (amount === null || amount === undefined || isNaN(amount)) {
    return showSymbol ? '₹0' : '0';
  }
  
  const num = Number(amount);
  const formatted = num.toLocaleString('en-IN', {
    maximumFractionDigits: 2,
    minimumFractionDigits: 0
  });
  
  return showSymbol ? `₹${formatted}` : formatted;
}

export function formatDate(dateString) {
  if (!dateString) return '-';
  try {
    const date = new Date(dateString + (dateString.length === 10 ? 'T00:00:00' : ''));
    if (isNaN(date.getTime())) return dateString;
    const dd = String(date.getDate()).padStart(2, '0');
    const mm = String(date.getMonth() + 1).padStart(2, '0');
    const yyyy = date.getFullYear();
    return `${dd}-${mm}-${yyyy}`;
  } catch {
    return dateString;
  }
}

export function formatDateTime(dateString) {
  if (!dateString) return '-';
  try {
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return dateString;
    const dd = String(date.getDate()).padStart(2, '0');
    const mm = String(date.getMonth() + 1).padStart(2, '0');
    const yyyy = date.getFullYear();
    const hh = String(date.getHours()).padStart(2, '0');
    const min = String(date.getMinutes()).padStart(2, '0');
    return `${dd}-${mm}-${yyyy} ${hh}:${min}`;
  } catch {
    return dateString;
  }
}

export function getTodayDate() {
  return new Date().toISOString().split('T')[0];
}

export function getDateRange(period) {
  const today = new Date();
  let start, end;
  
  switch(period) {
    case 'daily':
      start = end = today.toISOString().split('T')[0];
      break;
    case 'weekly':
      const weekStart = new Date(today);
      weekStart.setDate(today.getDate() - 7);
      start = weekStart.toISOString().split('T')[0];
      end = today.toISOString().split('T')[0];
      break;
    case 'monthly':
      const monthStart = new Date(today.getFullYear(), today.getMonth(), 1);
      start = monthStart.toISOString().split('T')[0];
      end = today.toISOString().split('T')[0];
      break;
    case 'yearly':
      const yearStart = new Date(today.getFullYear(), 0, 1);
      start = yearStart.toISOString().split('T')[0];
      end = today.toISOString().split('T')[0];
      break;
    default:
      start = end = today.toISOString().split('T')[0];
  }
  
  return { start, end };
}
