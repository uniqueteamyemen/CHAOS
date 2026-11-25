import { FLEET_50_SERIES } from '../src/data/fleet50Series.ts';
import { computeFleetCalculus, DEFAULT_CALCULUS_PARAMS } from '../src/utils/humanImpactCalculus.ts';

const snap2008 = computeFleetCalculus({ ...DEFAULT_CALCULUS_PARAMS, targetYear: 2008 });
console.log('2008 Net Human Pulse:', snap2008.netHumanPulse);
console.log('2008 Total Turbulence Energy:', snap2008.totalTurbulenceEnergy);
console.log('2008 Layer Shares:');
console.log('  Nature:', snap2008.layerShares.naturePercentage + '%');
console.log('  Infrastructure:', snap2008.layerShares.infrastructurePercentage + '%');
console.log('  Human Decisions / Systems:', snap2008.layerShares.humanSystemPercentage + '%');
console.log('2008 Strain Distribution:');
console.log('  Positive (Enablers):', snap2008.strainDistribution.positiveCount);
console.log('  Negative (Strains):', snap2008.strainDistribution.negativeCount);
console.log('  Neutral:', snap2008.strainDistribution.neutralCount);

console.log('\nTop 5 Strains in 2008:');
const topStrains = [...snap2008.items].sort((a, b) => a.finalScore - b.finalScore).slice(0, 5);
topStrains.forEach(i => console.log(`- ${i.series.id}: Score = ${i.finalScore}, Raw Stress = ${i.rawStress}, gamma = ${i.gamma}, tau = ${i.tau}`));

console.log('\nTop 5 Enablers in 2008:');
const topEnablers = [...snap2008.items].sort((a, b) => b.finalScore - a.finalScore).slice(0, 5);
topEnablers.forEach(i => console.log(`- ${i.series.id}: Score = ${i.finalScore}, Raw Stress = ${i.rawStress}, gamma = ${i.gamma}, tau = ${i.tau}`));
