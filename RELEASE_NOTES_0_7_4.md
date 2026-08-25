# MRP Django 0.7.4

## Commercial ATP/CTP and Promise Management

- Sales-order-line ATP/CTP evaluation and proposed promise date.
- Persistent promise history with PENDING/APPROVED/REJECTED/SUPERSEDED lifecycle.
- Recovery-derived promise proposals using exact 0.7.3 commercial pegging.
- Approval/rejection workflow that preserves the prior approved promise.
- Commercial service queue for impacted orders.
- DRF endpoints and Django UI for promise review.
- Management command `evaluate_sales_order_promises`.
- Migration `0015_commercial_promising_074.py`.

The proposed date is the later constraint between material availability (ATP) and capacity availability (CTP). CTP errors are preserved in the proposal payload and do not get silently converted into a capacity promise.
