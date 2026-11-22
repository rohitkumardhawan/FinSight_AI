'use client';

import React, { useState, useEffect, Suspense } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { Sidebar } from '@/components/Sidebar';
import { Header } from '@/components/Header';
import { CompanyDashboardView } from '@/components/CompanyDashboardView';
import { FinancialStatementsView } from '@/components/FinancialStatementsView';
import { FinancialRatiosView } from '@/components/FinancialRatiosView';
import { DcfValuationView } from '@/components/DcfValuationView';
import { RiskIntelligenceView } from '@/components/RiskIntelligenceView';
import { ResearchReportsView } from '@/components/ResearchReportsView';
import { ModulePlaceholder } from '@/components/ModulePlaceholder';
import { CsvImportModal } from '@/components/CsvImportModal';

function CompanyDetailContent() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();

  const tabParam = searchParams?.get('tab') || 'overview';
  const rawSymbol = Array.isArray(params?.idOrSymbol) ? params.idOrSymbol[0] : (params?.idOrSymbol as string) || 'ASIANPAINT.NS';
  const symbol = decodeURIComponent(rawSymbol);

  const [activeSection, setActiveSection] = useState<string>(tabParam);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isCsvModalOpen, setIsCsvModalOpen] = useState(false);

  useEffect(() => {
    if (symbol) {
      try {
        localStorage.setItem('finsight_last_company', symbol);
      } catch {}
      if (typeof document !== 'undefined') {
        document.title = `${symbol} | FinSight AI`;
      }
    }
  }, [symbol]);

  useEffect(() => {
    if (tabParam && tabParam !== activeSection) {
      setActiveSection(tabParam);
    }
  }, [tabParam]);

  const handleSelectSection = (sec: string) => {
    setActiveSection(sec);
    router.push(`/company/${encodeURIComponent(symbol)}?tab=${sec}`);
  };

  const handleSelectTicker = (selectedTicker: string) => {
    try {
      localStorage.setItem('finsight_last_company', selectedTicker);
    } catch {}
    router.push(`/company/${encodeURIComponent(selectedTicker)}?tab=${activeSection}`);
  };

  return (
    <div className="flex h-screen bg-navy-950 text-slate-100 overflow-hidden font-sans">
      {/* Sidebar Navigation */}
      <Sidebar
        activeSection={activeSection}
        onSelectSection={handleSelectSection}
        isOpenOnMobile={isMobileMenuOpen}
        onCloseMobile={() => setIsMobileMenuOpen(false)}
      />

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Universal Header with Live Search & CSV Import */}
        <Header
          currentTicker={symbol}
          onSelectTicker={handleSelectTicker}
          onToggleMobileMenu={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
          isMobileMenuOpen={isMobileMenuOpen}
          onOpenImportCsv={() => setIsCsvModalOpen(true)}
        />

        {/* Dynamic Workspace Container */}
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 space-y-6">
          {activeSection === 'overview' || activeSection === 'company-analysis' || activeSection === 'ai-research' ? (
            <CompanyDashboardView
              symbolOrId={symbol}
              onSelectTicker={handleSelectTicker}
            />
          ) : activeSection === 'financial-statements' ? (
            <FinancialStatementsView
              ticker={symbol}
              onSelectTicker={handleSelectTicker}
            />
          ) : activeSection === 'financial-ratios' ? (
            <FinancialRatiosView
              ticker={symbol}
              onSelectTicker={handleSelectTicker}
            />
          ) : activeSection === 'dcf' || activeSection === 'dcf-valuation' ? (
            <DcfValuationView
              ticker={symbol}
              onSelectTicker={handleSelectTicker}
            />
          ) : activeSection === 'risk' || activeSection === 'risk-intelligence' ? (
            <RiskIntelligenceView
              ticker={symbol}
              onSelectTicker={handleSelectTicker}
            />
          ) : activeSection === 'reports' || activeSection === 'research-reports' ? (
            <ResearchReportsView
              ticker={symbol}
              onSelectTicker={handleSelectTicker}
            />
          ) : (
            <ModulePlaceholder
              sectionId={activeSection}
              ticker={symbol}
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
          companyTicker={symbol}
          companyName={symbol}
          onImportSuccess={() => {
            setIsCsvModalOpen(false);
            window.location.reload();
          }}
        />
      )}
    </div>
  );
}

export default function CompanyDetailPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-navy-950 flex items-center justify-center text-slate-400">Loading Company Intelligence...</div>}>
      <CompanyDetailContent />
    </Suspense>
  );
}
