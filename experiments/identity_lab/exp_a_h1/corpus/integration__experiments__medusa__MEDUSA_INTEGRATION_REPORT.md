# PayLock x Medusa Operational Integration Report

## Status

Status: Successfully verified

This report captures the operational integration of PayLock Core with a live Medusa runtime using an external PayLock Core deployment over Railway.

The integration has now demonstrated a complete progression lifecycle inside a real Medusa operational path.

Canonical operational proof achieved:

`DENY BEFORE PROOF`

`ALLOW AFTER PROOF`

## Verified Operational Behaviors

The following behaviors were verified during runtime testing:

- H0 session creation via PayLock Core
- H0 injection into Medusa order metadata
- Middleware interception inside the Medusa fulfillment lifecycle
- Fulfillment denial before progression proof completeness
- Provider acknowledgment progression
- Unlock progression
- Resolve progression
- H0 to H1 lifecycle transition
- `EXECUTION_PROVEN` resolution state
- Fulfillment transition success after proof completeness
- External PayLock Core integration over Railway
- Deterministic execution gating behavior

## Canonical Architectural Position

PayLock is not:

- A payment processor
- A PSP
- A settlement rail
- A banking layer
- A custody layer
- A money movement system

PayLock is:

- An execution progression protocol
- A provider approval witness
- A deterministic orchestration layer
- An operational progression observer
- An execution authorization layer

Canonical short framing:

`User wants.`

`Provider approves.`

`PayLock observes.`

## Integration Policy

Provider approval is an operational event.

It is not a financial event.

Examples of acceptable provider approval sources:

- Create Shipment
- Create Fulfillment
- Provision Resource
- Activate License
- Approve Delivery
- Enable Access

Non-required concepts:

- Settlement verification
- Payment custody
- Bank confirmation
- Amount disclosure

Canonical separation:

`The provider owns payment truth.`

`PayLock owns execution progression truth.`

## Current Medusa Mapping

### Recommended provider_ack source

Recommended mapping:

`Create Shipment -> provider_ack`

Reason:

- Explicit provider operational approval
- Works with cash on delivery
- Works with subscriptions
- Works with free goods
- Works with gifts
- Works with non-financial execution
- Works with digital provisioning

### Mark as Delivered

Recommended role:

`Guarded by H1 proof`

It is not recommended as the primary `provider_ack` source because it occurs too late in the lifecycle.

## Important Clarification About Current Demo State

Provider approval was validated operationally during this integration, but in the current Medusa demo it is still manually or externally invoked.

It is therefore ready to be automated from a provider-side operational event such as:

- Create Shipment
- Create Fulfillment

This distinction matters:

- The protocol semantics are validated.
- Full provider-event automation remains the next integration hardening step.

## Canonical Source Files Modified During Integration

The canonical source files modified for the Medusa integration are:

- `apps/backend/src/api/store/custom/route.ts`
- `apps/backend/src/api/middlewares.ts`
- `apps/backend/src/subscribers/fulfillment-created.ts`

## Runtime and Generated Proof Artifacts

The following runtime-generated or local proof artifacts were also used during validation:

- `apps/backend/.medusa/server/src/api/store/custom/route.js`
- `apps/backend/.medusa/server/src/api/middlewares.js`
- `apps/backend/.medusa/server/src/subscribers/fulfillment-created.js`

These files are useful as operational proof artifacts, but they are not the canonical source of the integration.

## Required Environment Variables

Operational runtime requires:

```env
PAYLOCK_URL=https://paylock-core-production.up.railway.app
PAYLOCK_API_KEY=test-key
```

## Operational Lifecycle Used During Validation

### 1. Session Creation

Endpoint:

```text
POST /v1/session
```

Result:

- H0 generated successfully
- Session persisted inside PayLock Core

### 2. H0 Injection Into Medusa

Endpoint:

```text
POST /store/custom
```

Behavior:

- H0 attached to order metadata
- Runtime verification succeeded

### 3. Provider Approval

Endpoint:

```text
POST /v1/signal
```

Signal:

```text
provider_ack
```

### 4. Unlock

Endpoint:

```text
POST /v1/unlock
```

Result:

```text
UNLOCKED
```

### 5. Resolve

Endpoint:

```text
POST /v1/resolve
```

Result:

```text
EXECUTION_PROVEN
```

### 6. Fulfillment Transition

Observed success result:

```text
Fulfillment marked as delivered successfully
```

## Failure States Successfully Reproduced

The following failure states were intentionally reproduced and validated:

### Missing H0

```text
PAYLOCK_MISSING_H0
```

Expected behavior:

- Fulfillment blocked

### Missing Runtime Configuration

```text
PAYLOCK_NOT_CONFIGURED
```

Expected behavior:

- Runtime refusal
- External verification unavailable

### Session Not Found

```text
PAYLOCK_RESOLVE_REJECTED - Session not found
```

Expected behavior:

- Invalid or nonexistent lifecycle rejected

### Missing Required Signals

```text
PAYLOCK_RESOLVE_REJECTED - Missing required signals
```

Expected behavior:

- Fulfillment progression denied before proof completeness

## Canonical Before/After Evidence

### Before proof completeness

Observed result:

```text
POST /admin/orders/:id/fulfillments/:fulfillment_id/mark-as-delivered -> 400
```

Observed reason:

```text
PAYLOCK_RESOLVE_REJECTED - Missing required signals
```

### After proof completeness

Observed result:

```text
POST /admin/orders/:id/fulfillments/:fulfillment_id/mark-as-delivered -> success
```

Observed UI confirmation:

```text
Fulfillment marked as delivered successfully
```

This is the core operational proof:

`The same fulfillment transition class was denied before proof completeness and allowed after proof completeness.`

## Operational Discoveries

One of the most important discoveries during runtime testing was execution progression consistency under concurrent and asynchronous operational pressure.

Observed relevance includes:

- Duplicate requests
- Retry storms
- Double execution
- Webhook duplication
- Replay attempts
- Delayed callbacks
- Fulfillment duplication
- Asynchronous orchestration races

This positions PayLock beyond payment-adjacent flows and into broader execution consistency orchestration.

## Immediate Next Steps

### 1. Commit source changes

Required:

- Preserve middleware logic
- Preserve H0 binding route
- Preserve subscriber updates

### 2. Reduce temporary debug logging

Recommended:

- Remove excess console logs
- Keep canonical operational logs only

### 3. Automate provider_ack

Target:

Automatically emit `provider_ack` from a provider-side operational event such as:

- Create Shipment
- Create Fulfillment

instead of manual terminal invocation

### 4. Preserve evidence corpus

Keep together:

- This report
- `EVIDENCE_BRIEF.md`
- `AUDIT_APPENDIX.md`
- `paylock-enforcement-audit.json`
- Relevant screenshots or terminal outputs

## Canonical Demonstration Statement

User requests execution.

Provider approves progression.

PayLock observes progression.

Execution becomes authorized.

## Canonical Identity

User wants.

Provider approves.

PayLock observes.
