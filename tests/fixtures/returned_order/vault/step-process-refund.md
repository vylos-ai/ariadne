---
evidence_ids:
- evidence-email-customer-complaint
- evidence-interview-ops-lead
id: step-process-refund
properties:
  description: A refund is issued for an approved return where the customer asked
    for money back.
  name: Process refund
type: ProcessStep
---

# step-process-refund

## depends_on
- [[step-record-decision]]

## produces
- [[data-refund]]

## triggers
- [[step-record-decision]]
