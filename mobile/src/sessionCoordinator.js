export function createSessionCoordinator(auth) {
  let state = { status: 'loading', session: null, event: null };
  let startPromise = null;
  let subscription = null;
  let authEvents = 0;
  const listeners = new Set();

  const publish = (session, event = null) => {
    const status = event === 'PASSWORD_RECOVERY'
      ? 'password-recovery'
      : session?.access_token
        ? 'signed-in'
        : 'signed-out';
    state = { status, session: session || null, event };
    listeners.forEach((listener) => listener(state));
  };

  const start = () => {
    if (startPromise) return startPromise;

    // Subscribe before reading storage so a login/logout/recovery event cannot
    // fall into the gap between getSession() and onAuthStateChange().
    const { data } = auth.onAuthStateChange((event, session) => {
      authEvents += 1;
      publish(session, event || null);
    });
    subscription = data?.subscription || null;
    const eventsBeforeRead = authEvents;
    startPromise = auth.getSession()
      .then(({ data: result, error }) => {
        if (error) throw error;
        // An auth event observed while storage was loading is newer than the
        // storage snapshot and must not be overwritten by it.
        if (authEvents === eventsBeforeRead) publish(result?.session || null, 'INITIAL_SESSION');
        return state;
      })
      .catch(() => {
        if (authEvents === eventsBeforeRead) publish(null, 'INITIAL_SESSION');
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
      // A password-recovery session is authenticated at the provider but is not
      // ordinary application authority. It exists only to update the password.
      if (state.status === 'password-recovery') return null;
      return state.session?.access_token || null;
    },
    async authorizationHeader() {
      const token = await this.accessToken();
      return token ? { Authorization: `Bearer ${token}` } : {};
    },
    async refresh() {
      if (state.status === 'password-recovery') return null;
      const { data, error } = await auth.refreshSession();
      if (error) throw error;
      publish(data?.session || null, 'TOKEN_REFRESHED');
      return state.session?.access_token || null;
    },
    stop() {
      subscription?.unsubscribe();
      subscription = null;
    },
  };
}
