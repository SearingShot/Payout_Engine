export default function BalanceCards({ dashboard }) {
  const formatINR = (paise) => {
    const rupees = paise / 100;
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      minimumFractionDigits: 2,
    }).format(rupees);
  };

  const cards = [
    {
      label: 'Available Balance',
      value: dashboard.available_balance,
      icon: 'account_balance_wallet',
    },
    {
      label: 'Held Balance',
      value: dashboard.held_balance,
      icon: 'lock',
    },
    {
      label: 'Total Credits',
      value: dashboard.total_credits,
      icon: 'south_west',
    },
    {
      label: 'Total Debits',
      value: dashboard.total_debits,
      icon: 'north_east',
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 stagger-children">
      {cards.map((card) => (
        <div
          key={card.label}
          className="relative overflow-hidden rounded-[2rem] bg-white dark:bg-surface-900 border border-black/5 dark:border-white/5 p-6 transition-all duration-300 hover:bg-zinc-50 dark:hover:bg-surface-800 shadow-sm dark:shadow-none"
        >
          <div className="flex items-start justify-between mb-8">
            <span className="material-symbols-outlined text-black dark:text-white bg-black/5 dark:bg-white/5 p-3 rounded-2xl transition-colors duration-300">
              {card.icon}
            </span>
          </div>
          <div>
            <p className="font-inter text-[10px] uppercase tracking-[0.15em] font-semibold text-zinc-500 dark:text-surface-400 mb-2 transition-colors duration-300">
              {card.label}
            </p>
            <p className="text-3xl font-light tracking-tight text-black dark:text-white animate-count-up transition-colors duration-300">
              {formatINR(card.value)}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}
