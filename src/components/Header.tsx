import React from 'react';
import { ShieldCheck, Lock, Activity, Database, GitFork, AlertTriangle, Sparkles, Play, Globe2, ArrowRightLeft } from 'lucide-react';

interface HeaderProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  status: string;
}

export const Header: React.FC<HeaderProps> = ({ activeTab, setActiveTab }) => {
  const navItems = [
    { id: 'fleet50', label: 'أسطول الـ 50 والأثر البشري (Fleet 50)', icon: Globe2 },
    { id: 'forecast', label: 'محرك الاستشراف المستقبلي (2025 ← 2030)', icon: Activity },
    { id: 'transition', label: 'اختبار الصمود والانتقال (2008 ← 2013)', icon: ArrowRightLeft },
    { id: 'runtime', label: 'CHAOS Runtime V1 (واجهة التشغيل)', icon: Play },
    { id: 'discovery', label: 'مختبر استكشاف البنية الزمنية (Discovery Engine)', icon: Sparkles },
    { id: 'gate', label: 'Supervisor Gate', icon: ShieldCheck },
    { id: 'contracts', label: 'Experimental Contracts', icon: Lock },
    { id: 'governance', label: 'Governance Kernel MVP', icon: GitFork },
    { id: 'benchmarks', label: 'ميثاق النزاهة وحظر المحاكاة (Audit)', icon: ShieldCheck },
    { id: 'catalog', label: 'Data Readiness & Catalog', icon: Database },
    { id: 'guardrails', label: 'Scientific Guardrails', icon: AlertTriangle }
  ];

  return (
    <header className="border-b border-slate-800 bg-slate-900/90 backdrop-blur sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-lg bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400 font-mono font-bold text-lg">
              Ψ
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-lg text-slate-100 tracking-tight">CHAOS</span>
                <span className="text-xs px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono">
                  ACTIVE GOVERNANCE
                </span>
                <span className="text-xs px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20 font-mono hidden sm:inline-block">
                  REVIEW-ONLY (NO DEPLOY)
                </span>
              </div>
              <p className="text-xs text-slate-400 truncate max-w-xs sm:max-w-md">
                Governed Historical Data Layer & Readiness Gates
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-4">
            <div className="hidden lg:flex items-center space-x-2 text-xs font-mono text-slate-400 border border-slate-800 rounded-md px-3 py-1 bg-slate-950/60">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span>GATE: PASS (2 Admitted / 31 Quarantined)</span>
            </div>
          </div>
        </div>

        {/* Tab Navigation */}
        <nav className="flex space-x-1 overflow-x-auto py-2 scrollbar-none border-t border-slate-800/60">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                id={`tab-${item.id}`}
                onClick={() => setActiveTab(item.id)}
                className={`flex items-center space-x-2 px-3.5 py-2 rounded-lg text-sm font-medium transition-colors whitespace-nowrap ${
                  isActive
                    ? 'bg-cyan-500/10 text-cyan-300 border border-cyan-500/30 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-cyan-400' : 'text-slate-500'}`} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      </div>
    </header>
  );
};
