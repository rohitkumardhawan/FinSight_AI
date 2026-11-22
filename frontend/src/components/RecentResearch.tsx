'use client';

import React from 'react';
import { FileText, ArrowUpRight, ShieldCheck, UserCheck } from 'lucide-react';

interface ResearchNoteItem {
  id: string;
  title: string;
  ticker: string;
  analyst: string;
  date: string;
  sentiment: string;
  target_price: string;
  summary: string;
}

interface RecentResearchProps {
  notes: ResearchNoteItem[];
}

export const RecentResearch: React.FC<RecentResearchProps> = ({ notes }) => {
  return (
    <div className="bg-navy-900 border border-navy-800 rounded-xl p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-sm text-white">Institutional Research Coverage</h3>
            <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
              Live Synthesis
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">Analyst consensus briefs and fundamental theses</p>
        </div>
        <button className="text-xs text-gold-400 hover:text-gold-300 font-medium flex items-center gap-1 transition-colors">
          <span>View All Dispatches</span>
          <ArrowUpRight className="h-3.5 w-3.5" />
        </button>
      </div>

      <div className="space-y-3">
        {notes.map((note) => (
          <div
            key={note.id}
            className="p-3.5 rounded-lg bg-navy-950/60 border border-navy-800/80 hover:border-gold-500/30 transition-all hover:bg-navy-950 group"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-bold text-white group-hover:text-gold-400 transition-colors">
                    {note.title}
                  </span>
                  <span
                    className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                      note.sentiment === 'Bullish'
                        ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                        : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                    }`}
                  >
                    {note.sentiment}
                  </span>
                </div>
                <p className="text-xs text-slate-400 leading-relaxed">{note.summary}</p>
                <div className="flex items-center gap-4 mt-2.5 text-[11px] text-slate-500">
                  <span className="text-slate-400">{note.analyst}</span>
                  <span>•</span>
                  <span>{note.date}</span>
                </div>
              </div>
              <div className="text-right flex-shrink-0">
                <div className="text-[10px] uppercase text-slate-500">Target</div>
                <div className="text-sm font-bold text-gold-400">{note.target_price}</div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
