---
evidence_ids:
- evidence-email-warehouse-escalation
- evidence-interview-ops-lead
id: exception-manual-reship-handoff
properties:
  description: Warehouse cannot create the replacement order itself; every approved
    reship has to be escalated to ops to create it in Order Mgmt System, sometimes
    delaying reships by a day.
  name: Manual reship handoff bottleneck
type: Exception
---

# exception-manual-reship-handoff

## triggers
- [[step-create-reship-order]]
