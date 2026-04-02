import { useEffect, useCallback } from 'react';
import { toast } from 'sonner';

const useKeyboardShortcuts = (actions = {}, { enabled = true, userRole = 'admin' } = {}) => {
  const hasAccess = useCallback((action) => {
    const permissions = {
      admin: ['delete', 'export', 'edit', 'save', 'new_connection', 'existing_customer', 'summary'],
      warehouse_manager: ['export', 'edit', 'save', 'new_connection', 'existing_customer', 'summary'],
      sales_executive: ['edit', 'save', 'new_connection', 'existing_customer'],
    };
    return permissions[userRole]?.includes(action) ?? false;
  }, [userRole]);

  useEffect(() => {
    if (!enabled) return;

    const handler = (e) => {
      // Don't trigger in input/textarea/select fields
      const tag = e.target.tagName.toLowerCase();
      const isInput = tag === 'input' || tag === 'textarea' || tag === 'select' || e.target.isContentEditable;

      // Shift + ? → Help modal (works even in inputs)
      if (e.shiftKey && e.key === '?') {
        e.preventDefault();
        actions.onHelp?.();
        return;
      }

      // Escape → Close modals
      if (e.key === 'Escape') {
        actions.onEscape?.();
        return;
      }

      // Skip shortcuts when typing in form fields
      if (isInput && !e.ctrlKey && !e.altKey) return;

      // Ctrl+Alt+Arrow → First/Last Page
      if (e.ctrlKey && e.altKey && e.key === 'ArrowRight') {
        e.preventDefault();
        if (actions.onLastPage) {
          actions.onLastPage();
          toast.info('Last Page');
        }
        return;
      }
      if (e.ctrlKey && e.altKey && e.key === 'ArrowLeft') {
        e.preventDefault();
        if (actions.onFirstPage) {
          actions.onFirstPage();
          toast.info('First Page');
        }
        return;
      }

      // Alt+Arrow → Next/Prev Page
      if (e.altKey && !e.ctrlKey && e.key === 'ArrowRight') {
        e.preventDefault();
        if (actions.onNextPage) {
          actions.onNextPage();
          toast.info('Next Page');
        }
        return;
      }
      if (e.altKey && !e.ctrlKey && e.key === 'ArrowLeft') {
        e.preventDefault();
        if (actions.onPrevPage) {
          actions.onPrevPage();
          toast.info('Previous Page');
        }
        return;
      }

      // Ctrl+S → Save
      if (e.ctrlKey && !e.shiftKey && e.key === 's') {
        e.preventDefault();
        if (hasAccess('save') && actions.onSave) {
          actions.onSave();
          toast.success('Saving...');
        }
        return;
      }

      // Ctrl+R → Refresh (prevent browser refresh)
      if (e.ctrlKey && !e.shiftKey && e.key === 'r') {
        e.preventDefault();
        if (actions.onRefresh) {
          actions.onRefresh();
          toast.info('Refreshing data...');
        }
        return;
      }

      // F1 → New Connection
      if (e.key === 'F1') {
        e.preventDefault();
        if (hasAccess('new_connection') && actions.onNewConnection) {
          actions.onNewConnection();
          toast.info('New Connection Entry');
        }
        return;
      }

      // F2 → Existing Customer
      if (e.key === 'F2') {
        e.preventDefault();
        if (hasAccess('existing_customer') && actions.onExistingCustomer) {
          actions.onExistingCustomer();
          toast.info('Existing Customer Entry');
        }
        return;
      }

      // F10 → Export Reports
      if (e.key === 'F10') {
        e.preventDefault();
        if (hasAccess('export') && actions.onExport) {
          actions.onExport();
          toast.info('Export Reports');
        }
        return;
      }

      // F11 → Summary Reports
      if (e.key === 'F11') {
        e.preventDefault();
        if (hasAccess('summary') && actions.onSummary) {
          actions.onSummary();
          toast.info('Summary Reports');
        }
        return;
      }

      // Ctrl+D → Delete (admin only)
      if (e.ctrlKey && e.key === 'd') {
        e.preventDefault();
        if (hasAccess('delete') && actions.onDelete) {
          actions.onDelete();
        }
        return;
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [enabled, actions, hasAccess]);

  return { hasAccess };
};

export default useKeyboardShortcuts;
