export default function LedgerTable({ entries }) {
  const formatINR = (paise) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      minimumFractionDigits: 2,
    }).format(paise / 100);
  };

  const formatTime = (iso) => {
    const d = new Date(iso);
    return d.toLocaleString('en-IN', {
      day: 'numeric',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const typeConfig = {
    credit: {
      sign: '+',
      text: 'text-black dark:text-white',
      bg: 'bg-black/5 dark:bg-white/10',
      icon: 'south_west',
    },
    debit: {
      sign: '-',
      text: 'text-black dark:text-white',
      bg: 'bg-black/5 dark:bg-white/10',
      icon: 'north_east',
    },
  };

  const refLabels = {
    customer_payment: 'Customer Payment',
    payout_hold: 'Payout Hold',
    payout_reversal: 'Payout Reversal',
    payout_completed: 'Payout Completed',
  };

  return (
    <div className="rounded-[2rem] bg-white dark:bg-surface-900 border border-black/5 dark:border-white/5 p-6 h-full flex flex-col mt-6 transition-colors duration-300 shadow-sm dark:shadow-none">
      <div className="flex items-center gap-2 mb-5">
        <h2 className="text-xl font-semibold text-black dark:text-white tracking-tight transition-colors duration-300">Ledger</h2>
        <span className="ml-auto text-[10px] font-bold uppercase tracking-[0.1em] text-zinc-400 dark:text-surface-400 hover:text-black dark:hover:text-white transition-colors cursor-pointer">
          Last {entries.length} entries
        </span>
      </div>

      {entries.length === 0 ? (
        <div className="text-center py-10 text-zinc-500 dark:text-surface-500 text-sm transition-colors duration-300">
          <p className="text-3xl mb-2">📋</p>
          No ledger entries yet
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left border-separate border-spacing-y-2" id="ledger-table">
            <thead>
              <tr className="text-zinc-400 dark:text-surface-400 transition-colors duration-300">
                <th className="px-4 pb-2 font-inter text-[10px] uppercase tracking-[0.2em] font-semibold">Type</th>
                <th className="px-4 pb-2 font-inter text-[10px] uppercase tracking-[0.2em] font-semibold">Amount</th>
                <th className="px-4 pb-2 font-inter text-[10px] uppercase tracking-[0.2em] font-semibold">Reference</th>
                <th className="px-4 pb-2 font-inter text-[10px] uppercase tracking-[0.2em] font-semibold">Description</th>
                <th className="px-4 pb-2 font-inter text-[10px] uppercase tracking-[0.2em] font-semibold">Date</th>
              </tr>
            </thead>
            <tbody className="stagger-children">
              {entries.map((entry) => {
                const tc = typeConfig[entry.entry_type] || typeConfig.credit;
                return (
                  <tr
                    key={entry.id}
                    className="bg-zinc-50 dark:bg-surface-900 group hover:bg-zinc-100 dark:hover:bg-surface-800 transition-all duration-300"
                  >
                    <td className="px-4 py-4 rounded-l-2xl">
                      <div className="flex items-center gap-2">
                        <span className="material-symbols-outlined text-base text-zinc-500 dark:text-surface-400 transition-colors duration-300">{tc.icon}</span>
                        <span className="text-sm font-medium text-black dark:text-white transition-colors duration-300">{entry.entry_type === 'credit' ? 'Deposit' : 'Payout'}</span>
                      </div>
                    </td>
                    <td className={`px-4 py-4 font-semibold text-sm transition-colors duration-300 ${tc.text}`}>
                      {tc.sign}{formatINR(entry.amount_paise)}
                    </td>
                    <td className="px-4 py-4 text-zinc-500 dark:text-surface-400 text-xs transition-colors duration-300">
                      {refLabels[entry.reference_type] || entry.reference_type}
                    </td>
                    <td className="px-4 py-4 text-zinc-500 dark:text-surface-400 text-xs max-w-[200px] truncate transition-colors duration-300" title={entry.description}>
                      {entry.description || '—'}
                    </td>
                    <td className="px-4 py-4 rounded-r-2xl text-zinc-500 dark:text-surface-400 text-xs whitespace-nowrap transition-colors duration-300">
                      {formatTime(entry.created_at)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
