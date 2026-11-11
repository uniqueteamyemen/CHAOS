# Vendure Observed Behaviors

This file records what was actually observed during the Vendure integration run.

## Runtime Boot

Observed:

- Vendure server started successfully
- PayLock bootstrap initialized
- GraphQL shop/admin routes mapped
- dashboard and asset routes exposed

Evidence:

- `evidence/screenshots/vendure-runtime-log-bootstrap-signal.png`

## Order Transition Telemetry

Observed:

- order transition captured from `Created` to `AddingItems`
- PayLock labeled the transition as `order`
- signal persistence succeeded in the database

Evidence:

- `evidence/screenshots/vendure-runtime-log-bootstrap-signal.png`
- `evidence/Paylock Vendure Runtime Evidence Artifact V1.pdf`

## Shop API Execution

Observed:

- `addItemToOrder` mutation executed successfully
- Vendure returned an `Order`
- order state was `AddingItems`

Evidence:

- `evidence/screenshots/vendure-shop-additem-mutation.png`
- `evidence/screenshots/vendure-shop-additem-response.png`

## Provider-Side Signal Recording

Observed:

- a local webhook endpoint recorded a provider-side signal for `ORDER-001`
- PowerShell output showed `SIGNAL_RECORDED`

Evidence:

- `evidence/screenshots/vendure-paylock-webhook-unlock-h1.png`

## Unlock and H1 Issuance

Observed:

- PayLock received `unlock` for the same `h0`
- response status was `UNLOCKED`
- the response included an `h1`

Evidence:

- `evidence/screenshots/vendure-paylock-webhook-unlock-h1.png`

## Live Runtime Context

Observed:

- live Vendure dashboard product catalog
- live product detail page with variants and assets
- live customer profile page

Evidence:

- `evidence/screenshots/vendure-dashboard-products.png`
- `evidence/screenshots/vendure-dashboard-product-detail.png`
- `evidence/screenshots/vendure-dashboard-customer-detail.png`
- `evidence/screenshots/vendure-dashboard-order-context.png`

## Current Strength of Proof

Observed strength:

- runtime integration proof
- event capture proof
- persistence proof
- webhook-driven signal proof
- unlock/H1 proof

Not yet observed in this package:

- explicit Vendure-side guarded denial before proof
- explicit Vendure-side guarded allow after proof
- replay pressure tests
- duplicate webhook stress results
