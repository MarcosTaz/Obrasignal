from opportunity_funnel import record_funnel_decision


def persist_and_classify(conn, item, is_new):
    """Persist one funnel decision alongside the existing tender pipeline.

    The caller owns the tender INSERT/UPDATE transaction; this helper only records
    the auditable decision and returns it, so integration can be transactional.
    """
    return record_funnel_decision(conn, item, is_new)
