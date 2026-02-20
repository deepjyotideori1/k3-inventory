import { clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs) {
  return twMerge(clsx(inputs))
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
  let startDate, endDate;
  
  switch(period) {
    case 'daily':
      startDate = endDate = today.toISOString().split('T')[0];
      break;
    case 'weekly':
      const weekStart = new Date(today);
      weekStart.setDate(today.getDate() - 7);
      startDate = weekStart.toISOString().split('T')[0];
      endDate = today.toISOString().split('T')[0];
      break;
    case 'monthly':
      const monthStart = new Date(today.getFullYear(), today.getMonth(), 1);
      startDate = monthStart.toISOString().split('T')[0];
      endDate = today.toISOString().split('T')[0];
      break;
    case 'yearly':
      const yearStart = new Date(today.getFullYear(), 0, 1);
      startDate = yearStart.toISOString().split('T')[0];
      endDate = today.toISOString().split('T')[0];
      break;
    default:
      startDate = endDate = today.toISOString().split('T')[0];
  }
  
  return { startDate, endDate };
}
