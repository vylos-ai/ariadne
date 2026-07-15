---
evidence_ids:
- evidence-email-warehouse-escalation
- evidence-interview-ops-lead
id: step-inspect-item
properties:
  description: Warehouse checks the returned item for tags and signs of wear/damage.
  name: Inspect returned item
type: ProcessStep
---

# step-inspect-item

## owned_by
- [[role-warehouse]]

## produces
- [[data-inspection-result]]

## triggers
- [[decision-inspection-outcome]]
- [[step-send-label]]
