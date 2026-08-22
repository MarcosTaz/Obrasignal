import threading


def record_sync_decisions(conn, rows, account_id=None):
    """Record only new or changed decisions for the applicable accounts.

    Keep imports local: this module is loaded before ``app`` at the production
    WSGI boundary so the worker can be gated before ``app`` starts it.
    Importing account-aware pipeline modules at module load time would import
    ``app`` too early and reintroduce that startup race.
    """
    from account_registry import list_active_accounts
    from auth_context import configured_identity
    from company_profile import load_profile
    from decision_log import latest_decision
    from funnel_integration import persist_and_classify
    from opportunity_match_pipeline import evaluate_row

    accounts = [account_id] if account_id else list_active_accounts(conn)
    if not accounts:
        accounts = [configured_identity().account_id]

    recorded = 0
    for current_account in accounts:
        profile = load_profile(current_account)
        for row in rows:
            item = dict(row)
            source = item.get("source", "")
            external_id = item.get("external_id", "")
            evaluation = evaluate_row(item, profile=profile)
            previous = latest_decision(
                conn, source, external_id, account_id=current_account
            )
            if previous and (
                previous.get("decision") == evaluation.get("decision")
                and previous.get("score") == evaluation.get("profile_score")
                and previous.get("reason") == evaluation.get("reason")
            ):
                continue
            persist_and_classify(
                conn,
                item,
                item.get("first_seen") == item.get("last_seen"),
                account_id=current_account,
            )
            recorded += 1
    return recorded


def install_thread_hook():
    """Ensure the production worker starts only after preload has finished wiring it.

    app.py starts its worker during module import. In production, cors_app imports
    this hook before api/preload/app. The worker thread can therefore race the
    remainder of preload.py and execute the base sync before the enriched
    account-scoped pipeline has replaced app.sync_once.

    Instead of globally wrapping sync_once (which preload can overwrite), gate
    only the worker target until preload has completed. The original worker then
    resolves app.sync_once at call time, so it uses the final production pipeline.
    """
    original_start = threading.Thread.start
    if getattr(original_start, "_obrasignal_preload_gate", False):
        return

    def start(thread, *args, **kwargs):
        target = getattr(thread, "_target", None)
        if getattr(target, "__name__", "") == "worker":
            original_target = target
            original_args = getattr(thread, "_args", ())
            original_kwargs = getattr(thread, "_kwargs", {})

            def gated_worker():
                # preload is already being imported by the main WSGI thread.
                # Importing it here blocks until that import completes, ensuring
                # app.sync_once points at sync_once_with_events before the worker
                # executes its first cycle.
                import preload  # noqa: F401
                return original_target(*original_args, **original_kwargs)

            thread._target = gated_worker
            thread._args = ()
            thread._kwargs = {}

        return original_start(thread, *args, **kwargs)

    start._obrasignal_preload_gate = True
    threading.Thread.start = start


install_thread_hook()
