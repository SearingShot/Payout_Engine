# Submission

Hosted deployment:

```text
https://payout-engine-pehx.onrender.com/
```

API health check used before submission:

```text
GET https://payout-engine-pehx.onrender.com/api/v1/merchants/
```

Expected result: HTTP 200 with seeded merchants.

## Form Note

I am most proud of the payout creation path: the ledger is append-only, balances are calculated with database aggregation in paise, and payout requests for the same merchant are serialized with PostgreSQL row-level locking. I also tightened idempotency so an in-flight duplicate waits for the first request to commit and then returns the cached response instead of creating a second payout.
