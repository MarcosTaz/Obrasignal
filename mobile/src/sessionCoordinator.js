export function createSessionCoordinator(auth) {
  let state = { status: 'loading', session: null };
  let startPromise = null;
  let subscription = null;
  let authEvents = 0;
  const listeners = new Set();

  const publish = (session) => {
    state = { status: session?.access_token ? 'signed-in' : 'signed-out', session: session || null };
    listeners.forEach((listener) => listener(state));
  };

  const withTimeout = (promise, ms = 5000) => new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('Session recovery timed out')), ms);
    Promise.resolve(promise).then(
      (value) => { clearTimeout(timer); resolve(value); },
      (error) => { clearTimeout(timer); reject(error); },
    );
  });

  const start = () => {
    if (startPromise) return startPromise;

    // Subscribe before reading storage so a login/logout cannot fall into the
    // gap between getSession() and onAuthStateChange().
    const { data } = auth.onAuthStateChange((_, session) => {
      authEvents += 1;
      publish(session);
    });
    subscription = data?.subscription || null;
    const eventsBeforeRead = authEvents;
    // Browser storage/auth providers can occasionally leave getSession pending
    // forever (notably Safari after stale/corrupt persisted state). Startup must
    // always converge: after the bounded recovery window we fail closed to the
    // signed-out screen. A later Supabase auth event can still publish a valid
    // authenticated session normally.
    startPromise = withTimeout(auth.getSession())
      .then(({ data: result, error }) => {
        if (error) throw error;
        // An auth event observed while storage was loading is newer than the
        // storage snapshot and must not be overwritten by it.
        if (authEvents === eventsBeforeRead) publish(result?.session || null);
        return state;
      })
      .catch(() => {
        if (authEvents === eventsBeforeRead) publish(null);
        return state;
      });
    return startPromise;
  };

  return {
    start,
    getState: () => state,
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    async accessToken() {
      if (state.status === 'loading') await start();
      // Supabase remains the source of truth; no token is persisted separately.
      return state.session?.access_token || null;
    },
    async authorizationHeader() {
      const token = await this.accessToken();
      return token ? { Authorization: `Bearer ${token}` } : {};
    },
    async refresh() {
      const { data, error } = await auth.refreshSession();
      if (error) throw error;
      publish(data?.session || null);
      return state.session?.access_token || null;
    },
    stop() {
      subscription?.unsubscribe();
      subscription = null;
    },
  };
}
