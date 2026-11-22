'use client';

import React, { useState, useEffect, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { Sidebar } from '@/components/Sidebar';
import { Header } from '@/components/Header';
import { CompanyCompareView } from '@/components/CompanyCompareView';
import { CsvImportModal } from '@/components/CsvImportModal';

function ComparePageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const paramA = searchParams?.get('a') || 'ASIANPAINT.NS';
  const paramB = searchParams?.get('b') || 'BERGEPAINT.NS';

  const [activeSection, setActiveSection] = useState<string>('compare');
  const [currentTicker, setCurrentTicker] = useState<string>(paramA);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState<boolean>(false);
  const [isCsvModalOpen, setIsCsvModalOpen] = useState<boolean>(false);

  useEffect(() => {
    if (typeof document !== 'undefined') {
      document.title = `Compare: ${paramA} vs ${paramB} | FinSight AI`;
    }
  }, [paramA, paramB]);

  const handleSelectSection = (sectionId: string) => {
    setActiveSection(sectionId);
    if (sectionId !== 'compare') {
      router.push(`/company/${encodeURIComponent(currentTicker)}?tab=${sectionId}`);
    }
  };

  const handleSelectTicker = (ticker: string) => {
    setCurrentTicker(ticker);
    try {
      localStorage.setItem('finsight_last_company', ticker);
    } catch {}
    router.push(`/company/${encodeURIComponent(ticker)}?tab=overview`);
  };

  return (
    <div className="flex h-screen bg-navy-950 text-slate-100 overflow-hidden font-sans">
      {/* Sidebar Navigation */}
      <Sidebar
        activeSection="compare"
        onSelectSection={handleSelectSection}
        currentTicker={currentTicker}
        isOpenOnMobile={isMobileMenuOpen}
        onCloseMobile={() => setIsMobileMenuOpen(false)}
        onSelectTicker={handleSelectTicker}
      />

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Universal Header */}
        <Header
          currentTicker={currentTicker}
          onSelectTicker={handleSelectTicker}
          onToggleMobileMenu={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
          isMobileMenuOpen={isMobileMenuOpen}
          onOpenImportCsv={() => setIsCsvModalOpen(true)}
        />

        {/* Dynamic Workspace Container */}
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto space-y-6">
          <CompanyCompareView
            initialA={paramA}
            initialB={paramB}
            onSelectTicker={handleSelectTicker}
          />
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

export default function ComparePage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-navy-950 flex items-center justify-center text-slate-400">
          Loading Side-by-Side Equities Comparison...
        </div>
      }
    >
      <ComparePageContent />
    </Suspense>
  );
}
