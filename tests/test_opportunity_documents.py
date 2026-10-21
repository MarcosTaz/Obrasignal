import sqlite3

import pytest

from opportunity_documents import (
    build_document_inventory,
    classify_document_type,
    content_fingerprint,
    ensure_document_tables,
    get_document_inventory,
    ingest_document_references,
    normalize_document_reference,
    normalize_document_references,
    safe_external_url,
)


def ref(**overrides):
    base = {
        "opportunity_source": "TED",
        "opportunity_external_id": "OPP-1",
        "source": "TED",
        "title": "Technical Specifications.pdf",
        "external_id": "doc-1",
        "status": "CURRENT",
        "availability_status": "REFERENCE_ONLY",
        "required_for_submission": "UNKNOWN",
        "metadata": {"native_label": "technical specs"},
    }
    base.update(overrides)
    return base


def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_document_tables(conn)
    return conn


def test_single_document_and_unknown_requirement():
    inventory = build_document_inventory([ref()])
    assert len(inventory.current_documents) == 1
    assert inventory.current_documents[0].document_type == "TECHNICAL_SPECIFICATION"
    assert inventory.current_documents[0].classification_basis == "INFERRED"
    assert inventory.current_documents[0].required_for_submission == "UNKNOWN"


def test_multiple_documents_and_unknown_type():
    docs = normalize_document_references([ref(), ref(external_id="mystery", title="x7_payload.dat")])
    assert len(docs) == 2
    assert {item.document_type for item in docs} == {"TECHNICAL_SPECIFICATION", "UNKNOWN"}


@pytest.mark.parametrize("title,expected", [
    ("Bill of Quantities.xlsx", "BOQ"),
    ("Technical Specification.pdf", "TECHNICAL_SPECIFICATION"),
    ("Pricing Schedule.xlsx", "PRICING_SCHEDULE"),
    ("Price Schedule.xlsx", "PRICING_SCHEDULE"),
    ("Draft Contract.docx", "CONTRACT_DRAFT"),
    ("Clarifications 02.pdf", "CLARIFICATION"),
    ("Amendment No 3.pdf", "AMENDMENT"),
    ("random-file.bin", "UNKNOWN"),
])
def test_deterministic_classification(title, expected):
    assert classify_document_type(title)[0] == expected


def test_source_classification_wins_and_guidance_false_positive_is_unknown():
    assert classify_document_type("BOQ-looking-file.pdf", "APPENDIX") == ("APPENDIX", "SOURCE")
    assert classify_document_type("Guidance_on_BOQ_examples.pdf") == ("UNKNOWN", "UNKNOWN")
    assert classify_document_type("Price index methodology.pdf") == ("UNKNOWN", "UNKNOWN")


def test_duplicate_source_reference_is_deduped():
    docs = normalize_document_references([ref(), ref(source_url="https://one.test/a"), ref(source_url="https://two.test/a")])
    assert len(docs) == 1


def test_same_filename_different_content_hash_is_distinct_identity():
    first = ref(external_id="same-native", version=None, title="spec.pdf", content_fingerprint="a" * 64, fingerprint_kind="CONTENT")
    second = ref(external_id="same-native", version=None, title="spec.pdf", content_fingerprint="b" * 64, fingerprint_kind="CONTENT")
    docs = normalize_document_references([first, second])
    assert len(docs) == 2
    assert docs[0].document_id != docs[1].document_id


def test_content_hash_requires_bytes_and_supplied_content_digest_is_validated():
    assert content_fingerprint(b"abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    with pytest.raises(TypeError):
        content_fingerprint("abc")
    with pytest.raises(ValueError):
        normalize_document_reference(ref(content_fingerprint="not-a-sha256", fingerprint_kind="CONTENT"))


def test_explicit_supersession_preserves_both_versions():
    v1 = ref(external_id="spec-v1", version="1", title="Technical Specification v1.pdf")
    v2 = ref(external_id="spec-v2", version="2", title="Technical Specification v2.pdf", supersedes_external_id="spec-v1")
    docs = normalize_document_references([v2, v1])
    by_external = {item.external_id: item for item in docs}
    assert by_external["spec-v1"].status == "SUPERSEDED"
    assert by_external["spec-v2"].status == "CURRENT"
    assert by_external["spec-v2"].relationships[0].target_document_id == by_external["spec-v1"].document_id


def test_relationships_never_cross_opportunity_boundary():
    other = ref(opportunity_external_id="OPP-2", external_id="shared", version="1")
    other_id = normalize_document_reference(other).document_id
    revision = ref(external_id="new", version="2", supersedes_external_id="shared", related_document_id=other_id, relationship_type="RELATED_TO")
    docs = normalize_document_references([other, revision])
    by_external = {(item.opportunity_external_id, item.external_id): item for item in docs}
    assert by_external[("OPP-1", "new")].relationships == ()
    assert by_external[("OPP-2", "shared")].status == "CURRENT"


def test_incremental_supersession_resolves_previously_persisted_target():
    conn = db()
    v1 = ref(external_id="spec-v1", version="1", title="Technical Specification v1.pdf")
    v2 = ref(external_id="spec-v2", version="2", title="Technical Specification v2.pdf", supersedes_external_id="spec-v1")
    ingest_document_references(conn, [v1], observed_at="2026-08-24T10:00:00Z")
    ingest_document_references(conn, [v2], observed_at="2026-08-25T10:00:00Z")

    inventory = get_document_inventory(conn, "TED", "OPP-1")
    assert [item.external_id for item in inventory.current_documents] == ["spec-v2"]
    assert [item.external_id for item in inventory.superseded_documents] == ["spec-v1"]
    assert inventory.current_documents[0].relationships[0].target_document_id == inventory.superseded_documents[0].document_id


def test_stale_replay_does_not_resurrect_superseded_document():
    conn = db()
    v1 = ref(external_id="spec-v1", version="1", title="Technical Specification v1.pdf")
    v2 = ref(external_id="spec-v2", version="2", title="Technical Specification v2.pdf", supersedes_external_id="spec-v1")
    ingest_document_references(conn, [v1])
    ingest_document_references(conn, [v2])
    ingest_document_references(conn, [v1])

    inventory = get_document_inventory(conn, "TED", "OPP-1")
    assert [item.external_id for item in inventory.current_documents] == ["spec-v2"]
    assert [item.external_id for item in inventory.superseded_documents] == ["spec-v1"]


def test_ambiguous_native_target_never_creates_supersession():
    conn = db()
    first = ref(external_id="shared", version="1", content_fingerprint="a" * 64, fingerprint_kind="CONTENT")
    second = ref(external_id="shared", version="2", content_fingerprint="b" * 64, fingerprint_kind="CONTENT")
    ingest_document_references(conn, [first, second])
    revision = ref(external_id="new", version="3", supersedes_external_id="shared")
    ingest_document_references(conn, [revision])

    relations = conn.execute("SELECT COUNT(*) FROM opportunity_document_relationships WHERE source_document_id=(SELECT document_id FROM opportunity_documents WHERE external_id='new')").fetchone()[0]
    assert relations == 0


def test_unknown_version_never_guesses_supersession():
    docs = normalize_document_references([
        ref(external_id="a", title="Technical Specification.pdf", version=None),
        ref(external_id="b", title="Technical Specification revised.pdf", version=None),
    ])
    assert len(docs) == 2
    assert all(item.status == "CURRENT" and not item.relationships for item in docs)


def test_amendment_is_not_assumed_to_replace_pack():
    docs = normalize_document_references([ref(external_id="amd-1", title="Amendment 1.pdf")])
    assert docs[0].document_type == "AMENDMENT"
    assert docs[0].relationships == ()


def test_unavailable_and_restricted_references_are_preserved():
    unavailable = build_document_inventory([ref(availability_status="UNAVAILABLE")]).missing_or_unavailable[0]
    restricted = build_document_inventory([ref(availability_status="ACCESS_RESTRICTED")]).missing_or_unavailable[0]
    assert unavailable.availability_status == "UNAVAILABLE"
    assert restricted.availability_status == "ACCESS_RESTRICTED"
    assert restricted.status == "CURRENT"


def test_missing_source_metadata_fails_closed():
    with pytest.raises(ValueError):
        normalize_document_reference({"title": "BOQ.xlsx"})


def test_unsafe_external_urls_are_rejected_without_embedding_payloads():
    colon = chr(58)
    slash = chr(47)
    unsafe = [
        "java" + "script" + colon + "x",
        "data" + colon + "text/plain,x",
        "file" + colon + slash * 3 + "tmp/x",
        "https" + colon + slash * 2 + "user:pass@example.test/a.pdf",
        slash * 2 + "example.test/no-scheme",
    ]
    assert all(safe_external_url(value) is None for value in unsafe)
    assert safe_external_url("https://example.test/a.pdf") == "https://example.test/a.pdf"


def test_unsafe_url_does_not_become_available():
    bad = "java" + "script" + chr(58) + "x"
    item = normalize_document_reference(ref(source_url=bad, availability_status="AVAILABLE"))
    assert item.source_url is None
    assert item.availability_status == "REFERENCE_ONLY"
    assert item.raw_metadata["unsafe_source_url_rejected"] is True


def test_hostile_title_is_preserved_as_data_and_not_identity_path():
    title = "<" + "script>text</script> .." + chr(47) + ".." + chr(47) + "file"
    item = normalize_document_reference(ref(title=title, external_id="hostile-title"))
    assert item.title == title
    assert item.document_type == "UNKNOWN"
    assert "file" not in item.document_id


def test_oversized_metadata_and_invalid_file_size_are_rejected():
    with pytest.raises(ValueError):
        normalize_document_reference(ref(metadata={"blob": "x" * 70000}))
    with pytest.raises(ValueError):
        normalize_document_reference(ref(file_size=-1))


def test_order_independent_and_repeated_ingestion_is_idempotent():
    refs = [ref(external_id="a", title="BOQ.xlsx"), ref(external_id="b", title="Contract Draft.pdf")]
    assert [d.document_id for d in normalize_document_references(refs)] == [d.document_id for d in normalize_document_references(list(reversed(refs)))]
    conn = db()
    assert ingest_document_references(conn, refs) == 2
    assert ingest_document_references(conn, refs + [refs[1]]) == 2
    assert conn.execute("SELECT COUNT(*) FROM opportunity_documents").fetchone()[0] == 2


def test_raw_metadata_preserved_and_documents_are_public_shared():
    conn = db()
    ingest_document_references(conn, [ref(metadata={"source_field": "native-value"})])
    inventory = get_document_inventory(conn, "TED", "OPP-1")
    assert inventory.current_documents[0].raw_metadata == {"source_field": "native-value"}
    columns = {row[1] for row in conn.execute("PRAGMA table_info(opportunity_documents)")}
    assert "account_id" not in columns and "tenant_id" not in columns


def test_inventory_listing_requires_no_network_download(monkeypatch):
    conn = db()
    ingest_document_references(conn, [ref(source_url="https://example.test/spec.pdf")])
    monkeypatch.setattr("urllib.request.urlopen", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("download attempted")))
    assert len(get_document_inventory(conn, "TED", "OPP-1").current_documents) == 1


def test_inventory_does_not_mutate_opportunity_source_state():
    conn = db()
    conn.execute("CREATE TABLE tenders(source TEXT, external_id TEXT, title TEXT)")
    conn.execute("INSERT INTO tenders VALUES('TED','OPP-1','Original')")
    before = tuple(conn.execute("SELECT * FROM tenders").fetchone())
    ingest_document_references(conn, [ref()])
    after = tuple(conn.execute("SELECT * FROM tenders").fetchone())
    assert after == before


def test_status_availability_required_and_purpose_are_independent():
    item = normalize_document_reference(ref(status="CURRENT", availability_status="ACCESS_RESTRICTED", purpose="FOR_SUBMISSION"))
    assert item.status == "CURRENT"
    assert item.availability_status == "ACCESS_RESTRICTED"
    assert item.purpose == "FOR_SUBMISSION"
    assert item.required_for_submission == "UNKNOWN"
    explicit = normalize_document_reference(ref(external_id="required", required_for_submission="REQUIRED"))
    assert explicit.required_for_submission == "REQUIRED"
