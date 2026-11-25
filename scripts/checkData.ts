import { FLEET_50_SERIES } from '../src/data/fleet50Series.ts';
import { FLEET_2013_TRANSITION_DATA } from '../src/data/transition2013Data.ts';

console.log('Total series count:', FLEET_50_SERIES.length);
const missing2013 = FLEET_50_SERIES.filter(s => !FLEET_2013_TRANSITION_DATA[s.id]);
console.log('Missing 2013 data count:', missing2013.length);

const years = [1973, 1980, 1990, 2001, 2008, 2020, 2024];
for (const y of years) {
  const missing = FLEET_50_SERIES.filter(s => !s.benchmarks.some(b => b.year === y));
  console.log(`Missing year ${y}:`, missing.length);
}
