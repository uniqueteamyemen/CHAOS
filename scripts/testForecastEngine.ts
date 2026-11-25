import { runFutureForecastEngine } from '../src/utils/futureForecastEngine.ts';

console.log('Testing Future Forecast Engine:');
const result = runFutureForecastEngine('baseline', 500);

console.log('Base Year:', result.baseYear);
console.log('Target Years:', result.targetYears);
console.log('Macro Fragility Score:', result.macroFragilityScore);
console.log('Bifurcation Risk:', result.bifurcationRisk);
console.log('Fleet Snapshots:');
console.table(result.fleetSnapshots);

console.log('\nSample Series Projections (Debt vs Solar vs Telecom):');
const sampleSeries = result.seriesResults.filter(s =>
  ['s38-global-debt-gdp', 's26-solar-wind-generation', 's29-mobile-cellular'].includes(s.seriesId)
);
for (const s of sampleSeries) {
  console.log(`\n${s.seriesId} (${s.nameAr}):`);
  console.log('  2024 Base:', s.baseScore2024);
  console.log('  Dominant Driver:', s.dominantDriver);
  console.log('  Fragility Index:', s.fragilityIndex);
  console.log('  2030 Proj: Expected =', s.projections[s.projections.length - 1].expectedScore,
              '| P10 =', s.projections[s.projections.length - 1].p10Score,
              '| P90 =', s.projections[s.projections.length - 1].p90Score);
}
