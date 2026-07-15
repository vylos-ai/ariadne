---
evidence_ids:
- evidence-email-warehouse-escalation
- evidence-interview-ops-lead
id: step-record-decision
properties:
  description: Warehouse records Approved/Denied and the resolution in the Returns
    Tracker.
  name: Record inspection decision
type: ProcessStep
---

# step-record-decision

## depends_on
- [[step-create-reship-order]]
- [[step-notify-denied]]
- [[step-process-refund]]

## owned_by
- [[role-warehouse]]

## requires
- [[system-returns-tracker]]

## triggers
- [[decision-inspection-outcome]]
- [[step-create-reship-order]]
- [[step-notify-denied]]
- [[step-process-refund]]
