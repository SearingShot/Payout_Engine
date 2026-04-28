import { useState } from 'react';
import { createPayout } from '../api';

export default function PayoutForm({ merchant, bankAccounts, availableBalance, onSuccess }) {
  const [amount, setAmount] = useState('');
  const [bankAccountId, setBankAccountId] = useState(bankAccounts?.[0]?.id || '');
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState(null);

  const formatINR = (paise) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      minimumFractionDigits: 2,
    }).format(paise / 100);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setMessage(null);

    const amountRupees = parseFloat(amount);
    if (isNaN(amountRupees) || amountRupees <= 0) {
      setMessage({ type: 'error', text: 'Enter a valid amount' });
      return;
    }

    const amountPaise = Math.round(amountRupees * 100);
    if (amountPaise > availableBalance) {
      setMessage({ type: 'error', text: `Insufficient balance. Available: ${formatINR(availableBalance)}` });
      return;
    }

    // Generate a unique idempotency key
    const idempotencyKey = crypto.randomUUID();

    setSubmitting(true);
    try {
      const { data } = await createPayout(merchant.id, amountPaise, parseInt(bankAccountId), idempotencyKey);
      setMessage({
        type: 'success',
        text: `Payout of ${formatINR(amountPaise)} created successfully! ID: ${data.id.slice(0, 8)}...`,
      });
      setAmount('');
      onSuccess();
    } catch (err) {
      setMessage({ type: 'error', text: err.message });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="rounded-[2rem] bg-white dark:bg-surface-900 border border-black/5 dark:border-white/5 p-8 h-full flex flex-col justify-between transition-colors duration-300 shadow-sm dark:shadow-none">
      <div>
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 rounded-full bg-black/5 dark:bg-white/5 flex items-center justify-center transition-colors duration-300">
            <span className="material-symbols-outlined text-black dark:text-white transition-colors duration-300">bolt</span>
          </div>
          <h2 className="text-xl font-semibold text-black dark:text-white tracking-tight transition-colors duration-300">Request Payout</h2>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Amount */}
          <div>
            <label htmlFor="payout-amount" className="block text-[10px] font-semibold uppercase tracking-[0.15em] text-zinc-500 dark:text-surface-400 mb-2 transition-colors duration-300">
              Amount (INR)
            </label>
            <div className="relative">
              <span className="absolute left-4 top-1/2 -translate-y-1/2 text-black dark:text-white font-medium text-lg transition-colors duration-300">₹</span>
              <input
                id="payout-amount"
                type="number"
                step="0.01"
                min="1"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="0.00"
                className="w-full pl-10 pr-4 py-4 rounded-2xl bg-zinc-50 dark:bg-surface-800/60 border border-black/5 dark:border-white/5 text-black dark:text-white text-lg font-light placeholder-zinc-400 dark:placeholder-surface-600 focus:outline-none focus:border-black/20 dark:focus:border-white/20 focus:bg-white dark:focus:bg-surface-800 transition-all duration-300"
                required
              />
            </div>
            <p className="text-[11px] text-zinc-500 dark:text-surface-500 mt-2 font-medium transition-colors duration-300">
              Available: {formatINR(availableBalance)}
            </p>
          </div>

          {/* Bank Account */}
          <div>
            <label htmlFor="payout-bank-account" className="block text-[10px] font-semibold uppercase tracking-[0.15em] text-zinc-500 dark:text-surface-400 mb-2 transition-colors duration-300">
              Bank Account
            </label>
            <select
              id="payout-bank-account"
              value={bankAccountId}
              onChange={(e) => setBankAccountId(e.target.value)}
              className="w-full px-4 py-4 rounded-2xl bg-zinc-50 dark:bg-surface-800/60 border border-black/5 dark:border-white/5 text-black dark:text-white text-sm focus:outline-none focus:border-black/20 dark:focus:border-white/20 transition-all duration-300 appearance-none"
              required
            >
              {bankAccounts.map((ba) => (
                <option key={ba.id} value={ba.id} className="bg-white dark:bg-surface-900 text-black dark:text-white">
                  {ba.account_holder_name} — ****{ba.account_number.slice(-4)} ({ba.ifsc_code})
                </option>
              ))}
            </select>
          </div>

          {/* Message */}
          {message && (
            <div
              className={`p-4 rounded-2xl text-xs font-medium animate-fade-in transition-colors duration-300 ${
                message.type === 'success'
                  ? 'bg-zinc-100 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-300'
                  : 'bg-red-50 text-red-600 border border-red-200 dark:bg-red-950/30 dark:text-red-500 dark:border-red-500/20'
              }`}
            >
              {message.text}
            </div>
          )}
        </form>
      </div>

      {/* Submit */}
      <div className="mt-8">
        <button
          id="submit-payout"
          type="submit"
          onClick={handleSubmit}
          disabled={submitting}
          className="w-full py-5 rounded-[2rem] bg-black text-white dark:bg-white dark:text-black text-lg font-semibold hover:bg-zinc-800 dark:hover:bg-zinc-200 active:scale-[0.99] disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-300 flex items-center justify-center gap-3"
        >
          {submitting ? (
            <span className="flex items-center justify-center gap-2">
              <div className="w-5 h-5 border-2 border-white/30 border-t-white dark:border-black/30 dark:border-t-black rounded-full animate-spin" />
              Processing...
            </span>
          ) : (
            <>
              <span className="material-symbols-outlined text-xl" style={{ fontVariationSettings: "'FILL' 1" }}>bolt</span>
              Request Payout
            </>
          )}
        </button>
      </div>
    </div>
  );
}
