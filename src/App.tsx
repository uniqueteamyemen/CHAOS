import React, { useState } from 'react';
import { Header } from './components/Header';
import { HumanFleetEngineView } from './components/HumanFleetEngineView';
import { ChaosRuntimeView } from './components/ChaosRuntimeView';
import { DiscoveryEngineView } from './components/DiscoveryEngineView';
import { SupervisorGateView } from './components/SupervisorGateView';
import { ContractsView } from './components/ContractsView';
import { GovernanceKernelView } from './components/GovernanceKernelView';
import { ModelBenchmarksView } from './components/ModelBenchmarksView';
import { DataCatalogView } from './components/DataCatalogView';
import { GuardrailsView } from './components/GuardrailsView';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string>('fleet50');

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col selection:bg-cyan-500/20 selection:text-cyan-200">
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        status="active"
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {activeTab === 'fleet50' && <HumanFleetEngineView />}
        {activeTab === 'runtime' && <ChaosRuntimeView />}
        {activeTab === 'discovery' && <DiscoveryEngineView />}
        {activeTab === 'gate' && <SupervisorGateView />}
        {activeTab === 'contracts' && <ContractsView />}
        {activeTab === 'governance' && <GovernanceKernelView />}
        {activeTab === 'benchmarks' && <ModelBenchmarksView />}
        {activeTab === 'catalog' && <DataCatalogView />}
        {activeTab === 'guardrails' && <GuardrailsView />}
      </main>

      <footer className="border-t border-slate-900 bg-slate-950 py-6 text-xs text-slate-500 font-mono">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div>
            <span>CHAOS Platform • Imported from </span>
            <span className="text-slate-400">uniqueteamyemen/CHAOS</span>
          </div>
          <div className="flex items-center space-x-4">
            <span>Commit: 4a1a75fe</span>
            <span>•</span>
            <span>Snapshot: V3</span>
            <span>•</span>
            <span className="text-cyan-400/80">Governed Evidence Kernel</span>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default App;
