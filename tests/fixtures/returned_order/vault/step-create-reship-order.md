---
evidence_ids:
- evidence-email-warehouse-escalation
- evidence-interview-ops-lead
id: step-create-reship-order
properties:
  description: Ops creates the replacement order in Order Mgmt System for an approved
    reship.
  name: Create replacement order
type: ProcessStep
---

# step-create-reship-order

## depends_on
- [[step-record-decision]]

## owned_by
- [[role-ops-lead]]

## produces
- [[data-replacement-order]]

## requires
- [[system-order-mgmt]]

## triggers
- [[exception-manual-reship-handoff]]
- [[step-record-decision]]
