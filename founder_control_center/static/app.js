(() => {
  const csrfMeta = document.querySelector('meta[name="csrf-token"]');
  const csrf = csrfMeta ? csrfMeta.content : '';

  const registerForm = document.getElementById('registerCompany');
  if (registerForm) {
    registerForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      const out = document.getElementById('registerResult');
      const data = Object.fromEntries(new FormData(registerForm).entries());
      if (out) out.textContent = 'Registering…';
      try {
        const response = await fetch('/api/companies/register', {
          method: 'POST',
          headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf},
          body: JSON.stringify(data),
        });
        const body = await response.json();
        if (out) out.textContent = JSON.stringify(body, null, 2);
        if (response.ok) window.setTimeout(() => window.location.reload(), 400);
      } catch (error) {
        if (out) out.textContent = `DEGRADED: ${error.message}`;
      }
    });
  }

  const stateForm = document.getElementById('stateUpdateForm');
  if (stateForm) {
    stateForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      const out = document.getElementById('stateUpdateResult');
      const payload = Object.fromEntries(new FormData(stateForm).entries());
      if (out) out.textContent = 'Updating internal state…';
      try {
        const response = await fetch('/api/actions/update_factory_state/execute', {
          method: 'POST',
          headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf},
          body: JSON.stringify({company_id: stateForm.dataset.company, payload}),
        });
        const body = await response.json();
        if (out) out.textContent = JSON.stringify(body, null, 2);
        if (response.ok) window.setTimeout(() => window.location.reload(), 400);
      } catch (error) {
        if (out) out.textContent = `DEGRADED: ${error.message}`;
      }
    });
  }

  document.querySelectorAll('.action[data-action][data-company]').forEach((button) => {
    button.addEventListener('click', async () => {
      const out = document.getElementById('actionResult');
      if (out) out.textContent = 'Checking action authority…';
      try {
        const response = await fetch(`/api/actions/${encodeURIComponent(button.dataset.action)}/execute`, {
          method: 'POST',
          headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf},
          body: JSON.stringify({company_id: button.dataset.company, payload: {}}),
        });
        const body = await response.json();
        if (out) out.textContent = JSON.stringify(body, null, 2);
        if (response.ok && button.dataset.action === 'refresh_diagnostics') {
          window.setTimeout(() => window.location.reload(), 500);
        }
      } catch (error) {
        if (out) out.textContent = `DEGRADED: ${error.message}`;
      }
    });
  });
})();
