import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const trust = readFileSync(new URL('./components/SecurityTrustBar.js', import.meta.url), 'utf8')

assert.match(trust, /CSA STAR Level 1/)
assert.match(trust, /Self-assessment in preparation — certification not claimed/)
assert.doesNotMatch(trust, /CSA STAR(?: Level 1)? (?:certificado|certified)/i)
assert.match(trust, /HTTPS \/ TLS/)
assert.match(trust, /Privacy/)
assert.match(trust, /Production validation/)

console.log('Trust claims regression: truthful public security posture preserved.')
