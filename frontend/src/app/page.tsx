'use client';

import React, { useState, useEffect, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { Sidebar } from '@/components/Sidebar';
import { Header } from '@/components/Header';
import { ModulePlaceholder } from '@/components/ModulePlaceholder';
import { FinancialStatementsView } from '@/components/FinancialStatementsView';
import { FinancialRatiosView } from '@/components/FinancialRatiosView';
import { CompanyDashboardView } from '@/components/CompanyDashboardView';
import { DcfValuationView } from '@/components/DcfValuationView';
import { RiskIntelligenceView } from '@/components/RiskIntelligenceView';
import { ResearchReportsView } from '@/components/ResearchReportsView';
import { CsvImportModal } from '@/components/CsvImportModal';
import { API_BASE, API_BASE_URL } from '@/lib/api';

function MainDashboardContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const tabParam = searchParams?.get('tab') || 'overview';
  const symbolParam = searchParams?.get('symbol') || searchParams?.get('ticker');

  const [activeSection, setActiveSection] = useState<string>(tabParam);
  const [currentTicker, setCurrentTicker] = useState<string>('ASIANPAINT.NS');
  const [backendConnected, setBackendConnected] = useState<boolean>(true);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState<boolean>(false);
  const [isCsvModalOpen, setIsCsvModalOpen] = useState<boolean>(false);
  const [connectionNotice, setConnectionNotice] = useState<string>('Live API · Online');
  const [neonStatus, setNeonStatus] = useState<{ connected: boolean; text: string }>({
    connected: false,
    text: 'Connecting to Neon...',
  });

  // 1. Initial Company Discovery & Persistence
  useEffect(() => {
    if (symbolParam) {
      setCurrentTicker(symbolParam);
      try {
        localStorage.setItem('finsight_last_company', symbolParam);
      } catch {}
      return;
    }

    try {
      const saved = localStorage.getItem('finsight_last_company');
      if (saved && saved.trim()) {
        setCurrentTicker(saved.trim());
      } else {
        setCurrentTicker('ASIANPAINT.NS');
      }
    } catch {
      setCurrentTicker('ASIANPAINT.NS');
    }
  }, [symbolParam]);

  useEffect(() => {
    if (tabParam && tabParam !== activeSection) {
      setActiveSection(tabParam);
    }
  }, [tabParam]);

  // Dynamic Document Title
  useEffect(() => {
    if (typeof document !== 'undefined' && currentTicker) {
      document.title = `${currentTicker} | FinSight AI`;
    }
  }, [currentTicker]);

  const handleSelectTicker = (ticker: string) => {
    setCurrentTicker(ticker);
    try {
      localStorage.setItem('finsight_last_company', ticker);
    } catch {}
    router.push(`/company/${encodeURIComponent(ticker)}?tab=${activeSection}`);
  };

  const handleSelectSection = (sectionId: string) => {
    setActiveSection(sectionId);
    router.push(`/company/${encodeURIComponent(currentTicker)}?tab=${sectionId}`);
  };

  // 2. Fetch Neon Lakebase Postgres Health Live
  useEffect(() => {
    let isMounted = true;

    async function checkNeon() {
      try {
        const res = await fetch('/api/neon-health');
        if (!isMounted) return;

        if (res.ok) {
          const data = await res.json();
          setNeonStatus({
            connected: true,
            text: `Neon Postgres: Connected (${data.branch || 'production'} • ${data.latency_ms || 12}ms)`,
          });
          setBackendConnected(true);
        } else {
          setNeonStatus({
            connected: false,
            text: 'Neon Postgres: Standalone Cache',
          });
        }
      } catch {
        if (isMounted) {
          setNeonStatus({
            connected: false,
            text: 'Neon Postgres: Unreachable',
          });
        }
      }
    }

    checkNeon();

    // 3. Live Backend FastAPI Health Polling
    async function checkBackend() {
      try {
        const res = await fetch(`${API_BASE_URL}/health`);
        if (!isMounted) return;
        if (res.ok) {
          setBackendConnected(true);
          setConnectionNotice('Live API · Online');
        } else {
          setBackendConnected(false);
          setConnectionNotice('Live API · Standby');
        }
      } catch {
        if (isMounted) {
          setBackendConnected(false);
          setConnectionNotice('Live API · Standby');
        }
      }
    }

    checkBackend();
    const bInterval = setInterval(checkBackend, 30000);

    return () => {
      isMounted = false;
      clearInterval(bInterval);
    };
  }, []);

  return (
    <div className="flex min-h-screen bg-navy-950 text-slate-100 font-sans">
      {/* 1. Left Institutional Sidebar (8 Modules + Mobile Responsiveness) */}
      <Sidebar
        activeSection={activeSection}
        onSelectSection={handleSelectSection}
        isOpenOnMobile={isMobileMenuOpen}
        onCloseMobile={() => setIsMobileMenuOpen(false)}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        {/* 2. Top Header Bar */}
        <Header
          currentTicker={currentTicker}
          onSelectTicker={handleSelectTicker}
          onToggleMobileMenu={() => setIsMobileMenuOpen((prev) => !prev)}
          isMobileMenuOpen={isMobileMenuOpen}
          onOpenImportCsv={() => setIsCsvModalOpen(true)}
        />

        {/* Global Live Engine Connectivity Banner */}
        <div className="bg-navy-900/60 border-b border-navy-800 px-4 sm:px-6 py-2 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs text-slate-300">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse flex-shrink-0"></span>
            <span className="font-semibold text-emerald-400 tracking-wide">[PHASE 4 ACTIVE]</span>
            <span className="text-slate-400 hidden lg:inline">
              — Universal equity search, deterministic financial analysis, and pgvector RAG intelligence.
            </span>
          </div>

          <div className="flex items-center gap-4 text-[11px] font-mono flex-wrap">
            {/* Neon Status */}
            <div className="flex items-center gap-1.5">
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  neonStatus.connected ? 'bg-cyan-400 animate-pulse' : 'bg-slate-500'
                }`}
              />
              <span className={neonStatus.connected ? 'text-cyan-300 font-medium' : 'text-slate-400'}>
                {neonStatus.text}
              </span>
            </div>

            {/* FastAPI Status */}
            <div className="flex items-center gap-1.5 border-l border-navy-800 pl-3">
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  backendConnected ? 'bg-emerald-400' : 'bg-amber-400'
                }`}
              />
              <span className={backendConnected ? 'text-emerald-400' : 'text-amber-300'}>
                {connectionNotice}
              </span>
            </div>
          </div>
        </div>

        {/* Dynamic Workspace Container */}
        <main className="p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto space-y-6">
          {activeSection === 'overview' || activeSection === 'company-analysis' || activeSection === 'ai-research' ? (
            <CompanyDashboardView
              symbolOrId={currentTicker}
              onRefresh={() => setCurrentTicker((t) => t)}
              onSelectTicker={handleSelectTicker}
            />
          ) : activeSection === 'financial-statements' ? (
            /* Financial Statements Module with CSV Import */
            <FinancialStatementsView
              ticker={currentTicker}
              onSelectTicker={handleSelectTicker}
            />
          ) : activeSection === 'financial-ratios' ? (
            /* Financial Ratio Engine */
            <FinancialRatiosView
              ticker={currentTicker}
              onSelectTicker={handleSelectTicker}
            />
          ) : activeSection === 'dcf' || activeSection === 'dcf-valuation' ? (
            /* Institutional DCF Valuation Engine */
            <DcfValuationView
              ticker={currentTicker}
              onSelectTicker={handleSelectTicker}
            />
          ) : activeSection === 'risk' || activeSection === 'risk-intelligence' ? (
            /* 4-Pillar Risk Intelligence Scorecard */
            <RiskIntelligenceView
              ticker={currentTicker}
              onSelectTicker={handleSelectTicker}
            />
          ) : activeSection === 'reports' || activeSection === 'research-reports' ? (
            /* Institutional Research Reports & PDF Generator */
            <ResearchReportsView
              ticker={currentTicker}
              onSelectTicker={handleSelectTicker}
            />
          ) : (
            /* Professional Placeholder Pages for Unreleased Modules */
            <ModulePlaceholder
              sectionId={activeSection}
              ticker={currentTicker}
              onBackToOverview={() => handleSelectSection('overview')}
            />
          )}
        </main>
      </div>

      {/* CSV Import Modal */}
      {isCsvModalOpen && (
        <CsvImportModal
          isOpen={isCsvModalOpen}
          onClose={() => setIsCsvModalOpen(false)}
          companyId={0}
          companyTicker={currentTicker}
          companyName={currentTicker}
          onImportSuccess={() => {
            setIsCsvModalOpen(false);
            window.location.reload();
          }}
        />
      )}
    </div>
  );
}

export default function Home() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-navy-950 flex items-center justify-center text-slate-400">Loading FinSight AI...</div>}>
      <MainDashboardContent />
    </Suspense>
  );
}
