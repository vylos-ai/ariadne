---
evidence_ids:
- evidence-email-customer-complaint
- evidence-interview-ops-lead
id: step-send-label
properties:
  description: Support manually buys and emails a prepaid shipping label to the customer.
  name: Send shipping label
type: ProcessStep
---

# step-send-label

## owned_by
- [[role-support]]

## produces
- [[data-shipping-label]]

## triggers
- [[step-inspect-item]]
- [[step-open-rma]]
