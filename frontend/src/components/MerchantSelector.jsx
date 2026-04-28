import { useState } from 'react';

export default function MerchantSelector({ merchants, selected, onSelect }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="relative">
      <button
        id="merchant-selector"
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-4 py-2 rounded-xl bg-surface-800/60 border border-surface-700/50 hover:border-primary-500/50 transition-all duration-200 text-sm"
      >
        <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-primary-400 to-primary-600 flex items-center justify-center text-white text-xs font-bold">
          {selected?.name?.charAt(0) || '?'}
        </div>
        <span className="text-surface-200 font-medium max-w-[150px] truncate">
          {selected?.name || 'Select Merchant'}
        </span>
        <svg className={`w-4 h-4 text-surface-400 transition-transform ${open ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-64 rounded-xl bg-surface-800 border border-surface-700/50 shadow-2xl shadow-black/40 overflow-hidden z-50 animate-fade-in">
          <div className="p-2">
            <p className="px-3 py-1.5 text-[10px] font-semibold text-surface-500 uppercase tracking-wider">Switch Merchant</p>
            {merchants.map((m) => (
              <button
                key={m.id}
                onClick={() => { onSelect(m); setOpen(false); }}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-all duration-150 ${
                  selected?.id === m.id
                    ? 'bg-primary-500/15 text-primary-300'
                    : 'text-surface-300 hover:bg-surface-700/50'
                }`}
              >
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold ${
                  selected?.id === m.id
                    ? 'bg-primary-500/30 text-primary-300'
                    : 'bg-surface-700 text-surface-400'
                }`}>
                  {m.name.charAt(0)}
                </div>
                <div>
                  <p className="text-sm font-medium">{m.name}</p>
                  <p className="text-[11px] text-surface-500">{m.email}</p>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
