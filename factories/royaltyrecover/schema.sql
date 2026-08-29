PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS organizations (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS licensors (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    legal_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS licensees (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    legal_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agreements (
    id TEXT PRIMARY KEY,
    licensor_id TEXT NOT NULL REFERENCES licensors(id),
    licensee_id TEXT NOT NULL REFERENCES licensees(id),
    title TEXT NOT NULL,
    governing_law TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE'
);

CREATE TABLE IF NOT EXISTS agreement_versions (
    id TEXT PRIMARY KEY,
    agreement_id TEXT NOT NULL REFERENCES agreements(id),
    version_label TEXT NOT NULL,
    effective_from TEXT,
    effective_to TEXT,
    document_sha256 TEXT NOT NULL,
    source_uri TEXT,
    UNIQUE(agreement_id, version_label)
);

CREATE TABLE IF NOT EXISTS clauses (
    id TEXT PRIMARY KEY,
    agreement_version_id TEXT NOT NULL REFERENCES agreement_versions(id),
    clause_ref TEXT NOT NULL,
    clause_type TEXT NOT NULL,
    text_excerpt TEXT,
    evidence_id TEXT,
    review_status TEXT NOT NULL DEFAULT 'UNREVIEWED'
);

CREATE TABLE IF NOT EXISTS audit_rights (
    id TEXT PRIMARY KEY,
    agreement_version_id TEXT NOT NULL REFERENCES agreement_versions(id),
    clause_id TEXT NOT NULL REFERENCES clauses(id),
    auditor_requirement TEXT,
    notice_days INTEGER,
    max_audits_per_year INTEGER,
    lookback_months INTEGER,
    fee_shift_threshold_bps INTEGER,
    interest_rule_text TEXT,
    status TEXT NOT NULL DEFAULT 'EXTRACTED'
);

CREATE TABLE IF NOT EXISTS royalty_rules (
    id TEXT PRIMARY KEY,
    agreement_version_id TEXT NOT NULL REFERENCES agreement_versions(id),
    clause_id TEXT NOT NULL REFERENCES clauses(id),
    basis TEXT NOT NULL,
    rate_decimal TEXT,
    per_unit_decimal TEXT,
    minimum_guarantee_decimal TEXT,
    cap_decimal TEXT,
    floor_decimal TEXT,
    currency TEXT NOT NULL,
    effective_from TEXT,
    effective_to TEXT,
    review_status TEXT NOT NULL DEFAULT 'UNREVIEWED'
);

CREATE TABLE IF NOT EXISTS royalty_tiers (
    id TEXT PRIMARY KEY,
    royalty_rule_id TEXT NOT NULL REFERENCES royalty_rules(id),
    lower_bound_decimal TEXT NOT NULL,
    upper_bound_decimal TEXT,
    rate_decimal TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    UNIQUE(royalty_rule_id, ordinal)
);

CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS skus (
    id TEXT PRIMARY KEY,
    product_id TEXT NOT NULL REFERENCES products(id),
    sku TEXT NOT NULL,
    UNIQUE(product_id, sku)
);

CREATE TABLE IF NOT EXISTS territories (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS channels (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sublicenses (
    id TEXT PRIMARY KEY,
    agreement_id TEXT NOT NULL REFERENCES agreements(id),
    sublicensee_name TEXT NOT NULL,
    effective_from TEXT,
    effective_to TEXT,
    evidence_id TEXT
);

CREATE TABLE IF NOT EXISTS sales_records (
    id TEXT PRIMARY KEY,
    agreement_id TEXT NOT NULL REFERENCES agreements(id),
    source_dataset_id TEXT NOT NULL,
    source_row_key TEXT NOT NULL,
    transaction_date TEXT NOT NULL,
    sku_id TEXT REFERENCES skus(id),
    territory_id TEXT REFERENCES territories(id),
    channel_id TEXT REFERENCES channels(id),
    gross_amount_decimal TEXT,
    units_decimal TEXT,
    currency TEXT,
    row_sha256 TEXT NOT NULL,
    UNIQUE(source_dataset_id, source_row_key)
);

CREATE TABLE IF NOT EXISTS deductions (
    id TEXT PRIMARY KEY,
    sales_record_id TEXT NOT NULL REFERENCES sales_records(id),
    deduction_type TEXT NOT NULL,
    amount_decimal TEXT NOT NULL,
    permitted_status TEXT NOT NULL DEFAULT 'UNKNOWN',
    source_clause_id TEXT REFERENCES clauses(id)
);

CREATE TABLE IF NOT EXISTS fx_rates (
    id TEXT PRIMARY KEY,
    rate_date TEXT NOT NULL,
    base_currency TEXT NOT NULL,
    quote_currency TEXT NOT NULL,
    rate_decimal TEXT NOT NULL,
    source_name TEXT NOT NULL,
    evidence_id TEXT NOT NULL,
    UNIQUE(rate_date, base_currency, quote_currency, source_name)
);

CREATE TABLE IF NOT EXISTS royalty_statements (
    id TEXT PRIMARY KEY,
    agreement_id TEXT NOT NULL REFERENCES agreements(id),
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    currency TEXT NOT NULL,
    reported_royalty_decimal TEXT,
    document_sha256 TEXT NOT NULL,
    UNIQUE(agreement_id, period_start, period_end, document_sha256)
);

CREATE TABLE IF NOT EXISTS payments (
    id TEXT PRIMARY KEY,
    agreement_id TEXT NOT NULL REFERENCES agreements(id),
    payment_date TEXT NOT NULL,
    currency TEXT NOT NULL,
    amount_decimal TEXT NOT NULL,
    payment_reference TEXT,
    evidence_id TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS calculation_runs (
    id TEXT PRIMARY KEY,
    agreement_id TEXT NOT NULL REFERENCES agreements(id),
    agreement_version_id TEXT NOT NULL REFERENCES agreement_versions(id),
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    engine_version TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS expected_royalties (
    id TEXT PRIMARY KEY,
    calculation_run_id TEXT NOT NULL REFERENCES calculation_runs(id),
    royalty_rule_id TEXT NOT NULL REFERENCES royalty_rules(id),
    amount_decimal TEXT,
    currency TEXT NOT NULL,
    status TEXT NOT NULL,
    formula_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS variances (
    id TEXT PRIMARY KEY,
    calculation_run_id TEXT NOT NULL REFERENCES calculation_runs(id),
    expected_royalty_id TEXT REFERENCES expected_royalties(id),
    royalty_statement_id TEXT REFERENCES royalty_statements(id),
    expected_vs_reported_decimal TEXT,
    reported_vs_paid_decimal TEXT,
    expected_vs_paid_decimal TEXT,
    currency TEXT NOT NULL,
    state TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    evidence_type TEXT NOT NULL,
    source_uri TEXT,
    source_sha256 TEXT,
    captured_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS findings (
    id TEXT PRIMARY KEY,
    agreement_id TEXT NOT NULL REFERENCES agreements(id),
    variance_id TEXT REFERENCES variances(id),
    finding_type TEXT NOT NULL,
    state TEXT NOT NULL,
    confidence TEXT NOT NULL,
    amount_decimal TEXT,
    currency TEXT,
    source_clause_id TEXT REFERENCES clauses(id),
    created_at TEXT NOT NULL,
    review_status TEXT NOT NULL DEFAULT 'PENDING'
);

CREATE TABLE IF NOT EXISTS finding_evidence (
    finding_id TEXT NOT NULL REFERENCES findings(id),
    evidence_id TEXT NOT NULL REFERENCES evidence(id),
    role TEXT NOT NULL,
    PRIMARY KEY(finding_id, evidence_id, role)
);

CREATE TABLE IF NOT EXISTS deadlines (
    id TEXT PRIMARY KEY,
    agreement_id TEXT NOT NULL REFERENCES agreements(id),
    clause_id TEXT REFERENCES clauses(id),
    deadline_type TEXT NOT NULL,
    deadline_date TEXT,
    status TEXT NOT NULL DEFAULT 'UNKNOWN',
    evidence_id TEXT REFERENCES evidence(id)
);

CREATE TABLE IF NOT EXISTS information_requests (
    id TEXT PRIMARY KEY,
    agreement_id TEXT NOT NULL REFERENCES agreements(id),
    finding_id TEXT REFERENCES findings(id),
    requested_item TEXT NOT NULL,
    rationale TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'DRAFT'
);

CREATE TABLE IF NOT EXISTS reviews (
    id TEXT PRIMARY KEY,
    finding_id TEXT NOT NULL REFERENCES findings(id),
    reviewer_role TEXT NOT NULL,
    decision TEXT NOT NULL,
    rationale TEXT,
    reviewed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS recovery_actions (
    id TEXT PRIMARY KEY,
    finding_id TEXT NOT NULL REFERENCES findings(id),
    action_type TEXT NOT NULL,
    status TEXT NOT NULL,
    owner_role TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS claims (
    id TEXT PRIMARY KEY,
    finding_id TEXT NOT NULL REFERENCES findings(id),
    status TEXT NOT NULL,
    asserted_amount_decimal TEXT,
    currency TEXT,
    professional_review_required INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS outcomes (
    id TEXT PRIMARY KEY,
    claim_id TEXT REFERENCES claims(id),
    finding_id TEXT NOT NULL REFERENCES findings(id),
    outcome_type TEXT NOT NULL,
    resolved_at TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS recovered_amounts (
    id TEXT PRIMARY KEY,
    outcome_id TEXT NOT NULL REFERENCES outcomes(id),
    payment_id TEXT REFERENCES payments(id),
    amount_decimal TEXT NOT NULL,
    currency TEXT NOT NULL,
    incremental_status TEXT NOT NULL DEFAULT 'UNVERIFIED',
    evidence_id TEXT NOT NULL REFERENCES evidence(id)
);

CREATE TABLE IF NOT EXISTS audit_events (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    actor_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    event_at TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_agreement_versions_effective ON agreement_versions(agreement_id, effective_from, effective_to);
CREATE INDEX IF NOT EXISTS idx_sales_agreement_date ON sales_records(agreement_id, transaction_date);
CREATE INDEX IF NOT EXISTS idx_findings_agreement_state ON findings(agreement_id, state);
CREATE INDEX IF NOT EXISTS idx_deadlines_agreement_date ON deadlines(agreement_id, deadline_date);
CREATE INDEX IF NOT EXISTS idx_audit_events_entity ON audit_events(entity_type, entity_id, event_at);
