# DebitProof — Minimum Pilot Data Request

## Purpose
Request only the information required to test a bounded supplier-side warranty/customer-debit diagnostic. This is an assisted-local workflow, not a public upload portal.

## Before any data transfer
1. Pilot scope must be agreed and recorded.
2. Terms/privacy versions and acceptance evidence must be recorded.
3. Allowed data classes must be explicitly authorized.
4. The transfer channel must be agreed by both parties.

## Minimum useful inputs
- Applicable warranty agreement / CSR / commercial warranty terms and amendments, with effective dates where known.
- Customer/OEM debit export for the bounded scope: debit ID, customer, amount, currency, failure/claim date, part/program/asset mapping fields available, and case/invoice identifiers where available.
- Part/program/customer mapping needed to interpret the debit lines.
- Root-cause / responsibility evidence used internally for the selected cases.
- Cost-category support where the debit includes labour, parts, admin, logistics or other cost classes.
- Prior credits and prior payment evidence where relevant.
- Debit receipt / notification dates needed to assess notice windows.

## Prefer pseudonymized values
VINs, internal case IDs, names and other identifiers should be pseudonymized when the real value is not necessary to determine contractual responsibility or economics. Keep the mapping outside DebitProof where feasible.

## Do not send
- passwords, API keys or account credentials;
- payment-card data;
- government IDs;
- health data;
- unrelated employee/customer personal data;
- entire mailboxes or broad file shares when a bounded export is sufficient.

## Format
- Debits: CSV, maximum pilot bound currently 500 rows / 2 MB per import.
- Contracts: native text/Markdown where available; PDF and DOCX are accepted only through human-reviewed extracted text plus source-file hash in the current assisted workflow.
- Evidence: bounded files/records with an evidence register and hash.

## Truth boundary
Supplying a document or debit does not establish liability, invalidity, recoverability or value. Missing/ambiguous material evidence remains `UNKNOWN / NEEDS REVIEW`.
