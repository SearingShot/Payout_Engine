export default function PayoutHistory({ payouts }) {
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

  const statusConfig = {
    pending: {
      label: 'Pending',
      bg: 'bg-zinc-100 dark:bg-zinc-900/50',
      text: 'text-zinc-600 dark:text-zinc-600',
      dot: 'hidden',
      pulse: false,
    },
    processing: {
      label: 'Processing',
      bg: 'border border-black/20 dark:border-white/20',
      text: 'text-black/60 dark:text-white/60',
      dot: 'hidden',
      pulse: true,
    },
    completed: {
      label: 'Completed',
      bg: 'bg-zinc-800 dark:bg-zinc-800',
      text: 'text-zinc-100 dark:text-zinc-300',
      dot: 'hidden',
      pulse: false,
    },
    failed: {
      label: 'Failed',
      bg: 'bg-red-50 dark:bg-red-950/30',
      text: 'text-red-600 dark:text-red-500',
      dot: 'hidden',
      pulse: false,
    },
  };

  return (
    <div className="rounded-[2rem] bg-white dark:bg-surface-900 border border-black/5 dark:border-white/5 p-6 h-full flex flex-col transition-colors duration-300 shadow-sm dark:shadow-none">
      <div className="flex items-center gap-2 mb-5">
        <h2 className="text-xl font-semibold text-black dark:text-white tracking-tight transition-colors duration-300">Recent Activity</h2>
        <span className="ml-auto text-[10px] font-bold uppercase tracking-[0.1em] text-zinc-400 dark:text-surface-400 hover:text-black dark:hover:text-white transition-colors cursor-pointer">
          Live • 3s
        </span>
      </div>

      {payouts.length === 0 ? (
        <div className="text-center py-10 text-zinc-500 dark:text-surface-500 text-sm transition-colors duration-300">
          <p className="text-3xl mb-2">📭</p>
          No payouts yet
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left border-separate border-spacing-y-2" id="payout-history-table">
            <thead>
              <tr className="text-zinc-400 dark:text-surface-400 transition-colors duration-300">
                <th className="px-4 pb-2 font-inter text-[10px] uppercase tracking-[0.2em] font-semibold">ID</th>
                <th className="px-4 pb-2 font-inter text-[10px] uppercase tracking-[0.2em] font-semibold">Amount</th>
                <th className="px-4 pb-2 font-inter text-[10px] uppercase tracking-[0.2em] font-semibold">Status</th>
                <th className="px-4 pb-2 font-inter text-[10px] uppercase tracking-[0.2em] font-semibold">Created</th>
              </tr>
            </thead>
            <tbody className="stagger-children">
              {payouts.map((p) => {
                const sc = statusConfig[p.status] || statusConfig.pending;
                return (
                  <tr
                    key={p.id}
                    className="bg-zinc-50 dark:bg-surface-900 group hover:bg-zinc-100 dark:hover:bg-surface-800 transition-all duration-300"
                  >
                    <td className="px-4 py-4 rounded-l-2xl">
                      <span className="font-mono text-xs text-zinc-500 dark:text-surface-400 transition-colors duration-300">{p.id.slice(0, 8)}...</span>
                    </td>
                    <td className="px-4 py-4 font-semibold text-black dark:text-white text-sm transition-colors duration-300">
                      {formatINR(p.amount_paise)}
                    </td>
                    <td className="px-4 py-4 text-right sm:text-left">
                      <span className={`inline-flex items-center justify-center px-4 py-1.5 rounded-full text-[10px] font-bold tracking-widest uppercase transition-colors duration-300 ${sc.bg} ${sc.text} ${sc.pulse ? 'animate-pulse' : ''}`}>
                        {sc.label}
                      </span>
                    </td>
                    <td className="px-4 py-4 rounded-r-2xl text-zinc-500 dark:text-surface-400 text-xs transition-colors duration-300">
                      {formatTime(p.created_at)}
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
