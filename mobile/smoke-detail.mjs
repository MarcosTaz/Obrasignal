import fs from 'node:fs';

const source = fs.readFileSync(new URL('./App.js', import.meta.url), 'utf8');

const checks = [
  ['detail receives selected opportunity', /<Detail\s+initialItem=\{selected\}/],
  ['detail owns local opportunity state', /function Detail\(\{ initialItem,/],
  ['workflow is rendered in detail', /<WorkflowPanel item=\{item\}/],
  ['official source action is rendered', /Abrir fonte oficial/],
];

const failures = checks.filter(([, pattern]) => !pattern.test(source));
if (failures.length) {
  for (const [name] of failures) console.error(`FAIL: ${name}`);
  process.exit(1);
}

for (const [name] of checks) console.log(`PASS: ${name}`);
