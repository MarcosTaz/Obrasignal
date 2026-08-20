import threading


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
