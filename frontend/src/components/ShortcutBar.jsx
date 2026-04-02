import React, { useState } from 'react';
import { Keyboard } from 'lucide-react';

const ShortcutBar = ({ shortcuts, onHelpOpen }) => {
  const [visible, setVisible] = useState(true);

  if (!visible) {
    return (
      <button
        onClick={() => setVisible(true)}
        className="fixed bottom-3 right-3 z-[999] bg-slate-800 text-white rounded-full p-2 shadow-lg hover:bg-slate-700 transition-colors"
        data-testid="shortcut-bar-toggle"
        title="Show shortcut bar"
      >
        <Keyboard className="w-4 h-4" />
      </button>
    );
  }

  return (
    <div
      className="fixed bottom-0 left-0 right-0 z-[998] bg-slate-900 text-slate-300 text-xs py-1.5 px-4 flex items-center justify-center gap-4 select-none"
      data-testid="shortcut-bar"
    >
      <button
        onClick={() => setVisible(false)}
        className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-white text-sm px-1"
        title="Hide shortcut bar"
      >
        &times;
      </button>
      {shortcuts.map((s, i) => (
        <span key={i} className="flex items-center gap-1">
          <kbd className="bg-slate-700 px-1.5 py-0.5 rounded text-[10px] font-mono font-bold text-slate-200 border border-slate-600">
            {s.key}
          </kbd>
          <span className="text-slate-400">{s.label}</span>
          {i < shortcuts.length - 1 && <span className="text-slate-600 ml-2">|</span>}
        </span>
      ))}
      <span className="text-slate-600 ml-1">|</span>
      <button
        onClick={onHelpOpen}
        className="flex items-center gap-1 text-blue-400 hover:text-blue-300 transition-colors cursor-pointer"
        data-testid="shortcut-help-trigger"
      >
        <kbd className="bg-slate-700 px-1.5 py-0.5 rounded text-[10px] font-mono font-bold text-slate-200 border border-slate-600">
          Shift+?
        </kbd>
        <span>All Shortcuts</span>
      </button>
    </div>
  );
};

export default ShortcutBar;
