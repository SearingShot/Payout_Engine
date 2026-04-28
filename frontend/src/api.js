const API_BASE = '/api/v1';

export async function fetchMerchants() {
  const res = await fetch(`${API_BASE}/merchants/`);
  if (!res.ok) throw new Error('Failed to fetch merchants');
  return res.json();
}

export async function fetchDashboard(merchantId) {
  const res = await fetch(`${API_BASE}/merchants/${merchantId}/dashboard/`);
  if (!res.ok) throw new Error('Failed to fetch dashboard');
  return res.json();
}

export async function fetchLedger(merchantId) {
  const res = await fetch(`${API_BASE}/merchants/${merchantId}/ledger/`);
  if (!res.ok) throw new Error('Failed to fetch ledger');
  return res.json();
}

export async function fetchPayouts(merchantId) {
  const res = await fetch(`${API_BASE}/merchants/${merchantId}/payouts/`);
  if (!res.ok) throw new Error('Failed to fetch payouts');
  return res.json();
}

export async function createPayout(merchantId, amountPaise, bankAccountId, idempotencyKey) {
  const res = await fetch(`${API_BASE}/payouts/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Idempotency-Key': idempotencyKey,
      'X-Merchant-Id': String(merchantId),
    },
    body: JSON.stringify({
      amount_paise: amountPaise,
      bank_account_id: bankAccountId,
    }),
  });

  const data = await res.json();
  if (!res.ok && res.status !== 201) {
    throw new Error(data.error || 'Failed to create payout');
  }
  return { data, status: res.status };
}
