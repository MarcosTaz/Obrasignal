/** Safe, deliberately non-authorizing customer feedback for authentication outages.
 * Never echo upstream error text, URLs, credentials or identity/provider details.
 */
const NET = /failed to fetch|fetch failed|network request failed|networkerror|load failed|could not connect|connection refused|name not resolved|dns error|econnreset|enotfound|timeout|timed out/i;
const WRONG_CREDENTIALS = new Set(['invalid_credentials','invalid_grant','invalid_login_credentials']);
const RATE_LIMIT = new Set(['over_request_rate_limit','over_email_send_rate_limit','too_many_requests']);

export function classifyAuthFailure(error, action='login') {
  const code=String(error?.code || '').toLowerCase();
  const status=Number(error?.status || 0);
  const message=typeof error?.message==='string'?error.message:'';
  const isNetwork=NET.test(message) || (status===0 && (error?.name==='TypeError'||error?.name==='AuthRetryableFetchError'));
  if(isNetwork) return {
    category:'network_unavailable', retryable:true,
    message:'Não foi possível contactar o serviço de autenticação. O acesso está temporariamente indisponível; este erro não confirma que a palavra-passe esteja incorreta. Volta a tentar mais tarde.',
  };
  if(status===429 || RATE_LIMIT.has(code)) return {
    category:'rate_limited',retryable:true,
    message:'Foram efetuadas demasiadas tentativas. Aguarda algum tempo antes de voltar a tentar.',
  };
  if(action==='login' && (WRONG_CREDENTIALS.has(code) || /invalid login credentials/i.test(message))) return {
    category:'invalid_credentials',retryable:false,
    message:'O email ou a palavra-passe não foram reconhecidos. Confirma os dados de acesso.',
  };
  if(action==='login' && (code==='email_not_confirmed'||/email not confirmed/i.test(message))) return {
    category:'email_unconfirmed',retryable:false,
    message:'Esta conta ainda precisa de confirmação de email. Consulta as instruções recebidas anteriormente.',
  };
  return {
    category:'unavailable',retryable:false,
    message:action==='recovery'
      ? 'Não foi possível confirmar o pedido de recuperação. Nenhum envio está confirmado. Volta a tentar mais tarde.'
      : 'Não foi possível concluir o acesso neste momento. Volta a tentar mais tarde ou contacta o suporte.',
  };
}
