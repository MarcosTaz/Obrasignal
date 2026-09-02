import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const trust = readFileSync(new URL('./components/SecurityTrustBar.js', import.meta.url), 'utf8')

assert.match(trust, /CSA STAR Level 1/)
assert.match(trust, /Self-assessment em preparação — ainda não certificado/)
assert.doesNotMatch(trust, /CSA STAR(?: Level 1)? (?:certificado|certified)/i)
assert.match(trust, /HTTPS \/ TLS/)
assert.match(trust, /Privacidade/)
assert.match(trust, /Testes de produção/)

console.log('Trust claims regression: truthful public security posture preserved.')
