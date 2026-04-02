import React from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { Badge } from './ui/badge';

const shortcuts = [
  {
    group: 'Navigation',
    items: [
      { keys: ['Alt', '→'], desc: 'Next Page' },
      { keys: ['Alt', '←'], desc: 'Previous Page' },
      { keys: ['Ctrl', 'Alt', '→'], desc: 'Last Page' },
      { keys: ['Ctrl', 'Alt', '←'], desc: 'First Page' },
    ]
  },
  {
    group: 'Forms',
    items: [
      { keys: ['F1'], desc: 'New Connection Entry' },
      { keys: ['F2'], desc: 'Existing Customer Entry' },
      { keys: ['Ctrl', 'S'], desc: 'Save Active Form' },
      { keys: ['Esc'], desc: 'Close Dialog / Cancel' },
    ]
  },
  {
    group: 'Reports',
    items: [
      { keys: ['F10'], desc: 'Export Reports' },
      { keys: ['F11'], desc: 'Summary Reports' },
    ]
  },
  {
    group: 'General',
    items: [
      { keys: ['Shift', '?'], desc: 'Show This Help' },
      { keys: ['Ctrl', 'R'], desc: 'Refresh Data' },
    ]
  },
];

const KeyBadge = ({ children }) => (
  <kbd className="inline-flex items-center justify-center min-w-[28px] h-7 px-1.5 text-xs font-mono font-semibold bg-slate-100 border border-slate-300 rounded shadow-sm text-slate-700">
    {children}
  </kbd>
);

const ShortcutHelpModal = ({ open, onOpenChange }) => {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg" data-testid="shortcut-help-modal">
        <DialogHeader>
          <DialogTitle className="text-lg font-bold text-slate-800">Keyboard Shortcuts</DialogTitle>
        </DialogHeader>
        <div className="space-y-5 py-2 max-h-[60vh] overflow-y-auto">
          {shortcuts.map((section) => (
            <div key={section.group}>
              <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">{section.group}</h3>
              <div className="space-y-1.5">
                {section.items.map((item, i) => (
                  <div key={i} className="flex items-center justify-between py-1.5 px-2 rounded hover:bg-slate-50">
                    <span className="text-sm text-slate-600">{item.desc}</span>
                    <div className="flex items-center gap-1">
                      {item.keys.map((k, ki) => (
                        <React.Fragment key={ki}>
                          {ki > 0 && <span className="text-slate-300 text-xs">+</span>}
                          <KeyBadge>{k}</KeyBadge>
                        </React.Fragment>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
        <div className="pt-2 border-t text-center">
          <Badge variant="outline" className="text-xs text-slate-400">Press <KeyBadge>Esc</KeyBadge> to close</Badge>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default ShortcutHelpModal;
