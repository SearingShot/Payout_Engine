import { useState, useEffect, useCallback } from 'react';
import { fetchMerchants, fetchDashboard } from './api';
import MerchantSelector from './components/MerchantSelector';
import BalanceCards from './components/BalanceCards';
import PayoutForm from './components/PayoutForm';
import PayoutHistory from './components/PayoutHistory';
import LedgerTable from './components/LedgerTable';

function App() {
  const [merchants, setMerchants] = useState([]);
  const [selectedMerchant, setSelectedMerchant] = useState(null);
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [isDark, setIsDark] = useState(true);

  // Apply dark mode class to html element
  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [isDark]);

  // Load merchants on mount
  useEffect(() => {
    fetchMerchants()
      .then((data) => {
        setMerchants(data);
        if (data.length > 0) setSelectedMerchant(data[0]);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  // Load dashboard when merchant changes or data refreshes
  const loadDashboard = useCallback(() => {
    if (!selectedMerchant) return;
    fetchDashboard(selectedMerchant.id)
      .then(setDashboard)
      .catch((err) => setError(err.message));
  }, [selectedMerchant]);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard, refreshKey]);

  // Auto-refresh every 3 seconds for live status updates
  useEffect(() => {
    if (!selectedMerchant) return;
    const interval = setInterval(() => {
      setRefreshKey((k) => k + 1);
    }, 3000);
    return () => clearInterval(interval);
  }, [selectedMerchant]);

  const handlePayoutSuccess = () => {
    setRefreshKey((k) => k + 1);
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-primary-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-surface-400 text-sm">Loading Playto Pay...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="bg-red-500/10 border border-red-500/30 rounded-2xl p-8 max-w-md text-center">
          <div className="text-4xl mb-4">⚠️</div>
          <h2 className="text-xl font-semibold text-red-400 mb-2">Connection Error</h2>
          <p className="text-surface-400 text-sm mb-4">{error}</p>
          <p className="text-surface-500 text-xs">Make sure the Django backend is running on port 8000</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-black text-black dark:text-white transition-colors duration-300 font-sans pb-12 selection:bg-black selection:text-white dark:selection:bg-white dark:selection:text-black">
      {/* Header */}
      <header className="sticky top-0 z-50 w-full bg-white/80 dark:bg-black/80 backdrop-blur-md border-b border-black/5 dark:border-white/5 transition-colors duration-300">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full overflow-hidden bg-zinc-200 dark:bg-surface-800 flex items-center justify-center grayscale">
              <span className="text-xl font-bold">P</span>
            </div>
            <div>
              <h1 className="text-lg font-bold text-black dark:text-white tracking-tight">Playto Pay</h1>
              <p className="text-[11px] text-zinc-500 dark:text-surface-500 -mt-0.5 uppercase tracking-widest font-semibold">Minimalist Engine</p>
            </div>
          </div>
          <div className="flex items-center gap-6">
            <MerchantSelector
              merchants={merchants}
              selected={selectedMerchant}
              onSelect={(m) => {
                setSelectedMerchant(m);
                setDashboard(null);
              }}
            />
            <button
              onClick={() => setIsDark(!isDark)}
              className="material-symbols-outlined text-zinc-500 hover:text-black dark:text-surface-400 dark:hover:text-white transition-colors p-2 active:scale-95 duration-200"
            >
              {isDark ? 'light_mode' : 'dark_mode'}
            </button>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        {dashboard ? (
          <div className="space-y-8 animate-fade-in">
            {/* Balance cards */}
            <BalanceCards dashboard={dashboard} />

            {/* Payout form + Payout history */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="lg:col-span-1">
                <PayoutForm
                  merchant={selectedMerchant}
                  bankAccounts={dashboard.bank_accounts}
                  availableBalance={dashboard.available_balance}
                  onSuccess={handlePayoutSuccess}
                />
              </div>
              <div className="lg:col-span-2">
                <PayoutHistory payouts={dashboard.recent_payouts} />
              </div>
            </div>

            {/* Ledger */}
            <LedgerTable entries={dashboard.recent_entries} />
          </div>
        ) : (
          <div className="flex items-center justify-center h-64">
            <div className="w-8 h-8 border-4 border-primary-500 border-t-transparent rounded-full animate-spin" />
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-surface-800/50 mt-12">
        <div className="max-w-7xl mx-auto px-6 py-6 text-center text-surface-600 text-xs">
          Playto Payout Engine — Built for the Founding Engineer Challenge 2026
        </div>
      </footer>
    </div>
  );
}

export default App;
