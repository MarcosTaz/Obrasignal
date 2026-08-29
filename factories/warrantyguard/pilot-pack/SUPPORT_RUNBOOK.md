# Support Runbook — Assisted Pilot

## Boundary
This runbook supports the assisted-local pilot only. It does not promise a contractual SLA and it does not authorize external customer communications automatically.

## Intake
Record tenant, case/workspace id if applicable, category, severity, concise observation, time observed and reporter. Never paste unrelated customer data into another tenant's ticket.

## Severity
- P0: suspected cross-tenant exposure, unauthorized document access, destructive corruption, leaked secret, or evidence that product truth may be unsafe across cases.
- P1: material analysis/data-integrity defect that can affect a case but is isolated and reversible.
- P2: workflow/product issue with a safe workaround.
- P3: question, usability issue, or non-critical improvement.

## P0 action
ISOLATE AFFECTED PROCESS → BLOCK SHARED/PUBLIC USE → PRESERVE EVIDENCE → REPRODUCE → REPAIR → RETEST → INDEPENDENTLY VERIFY → ONLY THEN RESOLVE.

P0 Security/Data Integrity resolution requires an evidence hash. A status change alone is not proof.

## Customer-facing truth
Do not tell a customer that a defect, warranty right, recovery, payment, deadline, or data incident is resolved until the evidence supports that exact statement. When uncertainty remains, say NEEDS REVIEW / UNKNOWN.

## Closure
Preserve resolution text, reviewer, reviewed time, evidence hash where required, and audit chain. A later regression reopens the ticket rather than creating a false historical GREEN.
