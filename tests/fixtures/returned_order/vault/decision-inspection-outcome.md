---
evidence_ids:
- evidence-email-warehouse-escalation
- evidence-interview-ops-lead
id: decision-inspection-outcome
properties:
  condition: Tags still on AND item unworn/undamaged -> approved; otherwise -> denied
  name: Inspection outcome
type: Decision
---

# decision-inspection-outcome

## requires
- [[policy-final-sale-if-worn]]

## triggers
- [[step-inspect-item]]
- [[step-record-decision]]
