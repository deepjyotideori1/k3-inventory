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
  const date = new Date(dateString);
  return date.toLocaleDateString('en-IN', {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  });
}

export function formatDateTime(dateString) {
  if (!dateString) return '-';
  const date = new Date(dateString);
  return date.toLocaleString('en-IN', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
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
