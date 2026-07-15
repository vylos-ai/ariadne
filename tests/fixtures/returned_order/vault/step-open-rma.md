---
evidence_ids:
- evidence-email-customer-complaint
- evidence-interview-ops-lead
id: step-open-rma
properties:
  description: Customer emails support; support logs a return request as a row in
    the Returns Tracker.
  name: Open RMA
type: ProcessStep
---

# step-open-rma

## owned_by
- [[role-support]]

## produces
- [[data-return-request]]

## requires
- [[system-returns-tracker]]

## triggers
- [[step-send-label]]
