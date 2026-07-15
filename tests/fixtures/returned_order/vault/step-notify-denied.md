---
evidence_ids:
- evidence-email-warehouse-escalation
- evidence-interview-ops-lead
id: step-notify-denied
properties:
  description: Whoever is watching the tracker emails the customer explaining the
    denial and the final-sale policy.
  name: Notify customer of denial
type: ProcessStep
---

# step-notify-denied

## depends_on
- [[step-record-decision]]

## owned_by
- [[role-support]]

## triggers
- [[exception-denial-email-skipped]]
- [[step-record-decision]]
