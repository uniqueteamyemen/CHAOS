import { evaluateCausalCircuitBreaker } from '../src/utils/causalCircuitBreaker.ts';
import { REAL_TIME_SERIES_LIBRARY } from '../src/data/timeSeriesLibrary.ts';

console.log('Testing Causal Circuit-Breaker on observational transitions:');

const sA = REAL_TIME_SERIES_LIBRARY[0]; // Inflation
const sB = REAL_TIME_SERIES_LIBRARY[2]; // Oil

const res1 = evaluateCausalCircuitBreaker(
  'TRANSITION_TEST_CAUSAL',
  'CAUSAL_ASSERTION',
  { id: sA.id, source: sA.source, code: sA.indicatorCode, data: sA.points.map(p => p.value) },
  { id: sB.id, source: sB.source, code: sB.indicatorCode, data: sB.points.map(p => p.value) }
);

console.log('1. Causal Assertion Test:');
console.log('   Admitted:', res1.admitted);
console.log('   Status:', res1.status);
console.log('   Reason:', res1.reason);
console.log('   Quarantine:', res1.quarantineRequired);

const res2 = evaluateCausalCircuitBreaker(
  'TRANSITION_TEST_CORR',
  'CORRELATION_ANALYSIS',
  { id: sA.id, source: sA.source, code: sA.indicatorCode, data: sA.points.map(p => p.value) },
  { id: sB.id, source: sB.source, code: sB.indicatorCode, data: sB.points.map(p => p.value) }
);

console.log('\n2. Observational Correlation Test:');
console.log('   Admitted:', res2.admitted);
console.log('   Status:', res2.status);
console.log('   Reason:', res2.reason);
console.log('   Quarantine:', res2.quarantineRequired);
