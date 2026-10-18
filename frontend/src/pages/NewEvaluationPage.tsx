import React from 'react';
import {
  FolderUp,
  Cpu,
  ShieldCheck,
  Calculator,
  Trophy,
  Info,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

const PIPELINE_STEPS = [
  {
    step: '1',
    title: 'Registration Form Ingestion',
    icon: FolderUp,
    description:
      'Upload CSV or JSON candidate registrations. The engine dynamically maps custom organizer columns, autogenerates missing IDs, detects ambiguous duplicate team names, and isolates unmapped fields.',
    endpoint: 'POST /api/ingestion/upload',
    badge: 'Foundation',
  },
  {
    step: '2',
    title: 'Selective Signal Extraction',
    icon: Cpu,
    description:
      'Execute pluggable analyzers across Academic metrics (CGPA/CPI normalization), GitHub activity metrics (repositories, recent commit activity), and Resume parsing (PDF/DOCX documents).',
    endpoint: 'POST /api/signals/extract',
    badge: 'Analyzers',
  },
  {
    step: '3',
    title: 'Eligibility Rule Verification',
    icon: ShieldCheck,
    description:
      'Classify candidates into ELIGIBLE, INELIGIBLE, or NEEDS_REVIEW states against 10 spec-compliant evaluators (team sizes, required links, signal thresholds, email duplicates, track caps) with full audit trails.',
    endpoint: 'POST /api/rules/evaluate',
    badge: 'Rules Engine',
  },
  {
    step: '4',
    title: 'Multi-Criteria Weighted Scoring',
    icon: Calculator,
    description:
      'Calculate normalized candidate composite scores with configurable weights, criteria normalization (min-max, boolean, categorical), member-to-team aggregations, and missing-data policies.',
    endpoint: 'POST /api/scoring/evaluate',
    badge: 'Scoring Engine',
  },
  {
    step: '5',
    title: 'Top-X Shortlist & Explainability',
    icon: Trophy,
    description:
      'Rank candidates deterministically with tie-break criteria and cutoff boundary tie protection. Surface shortages, review suggestions, and generate formula-safe CSV exports.',
    endpoint: 'POST /api/ranking/evaluate',
    badge: 'Selection',
  },
];

export const NewEvaluationPage: React.FC = () => {
  return (
    <div className="space-y-6">
      {/* Intro Header */}
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <Badge variant="forest" className="font-mono text-xs">
            Multi-Step Pipeline Staging
          </Badge>
          <span className="text-xs text-muted-foreground">· Workflow Specification</span>
        </div>
        <h2 className="text-xl font-bold tracking-tight text-foreground">
          Candidate Evaluation Pipeline
        </h2>
        <p className="text-sm text-muted-foreground max-w-2xl leading-relaxed">
          The upcoming evaluation wizard guides organizers through the complete 5-stage pipeline, leveraging the backend's ID-only evaluation flow to eliminate repetitive payload re-transmissions.
        </p>
      </div>

      {/* Pipeline Stage Architecture Overview */}
      <div className="grid grid-cols-1 gap-3.5">
        {PIPELINE_STEPS.map((item) => {
          const Icon = item.icon;
          return (
            <Card key={item.step} className="border-border/80">
              <CardHeader className="p-4 sm:p-5">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-forest-50 text-forest-800 font-semibold text-xs border border-forest-200">
                      {item.step}
                    </div>
                    <div className="flex items-center gap-2">
                      <Icon className="h-4 w-4 text-forest-700 shrink-0" />
                      <CardTitle className="text-sm sm:text-base font-semibold">
                        {item.title}
                      </CardTitle>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 pl-11 sm:pl-0">
                    <Badge variant="secondary" className="text-[10px] font-mono">
                      {item.badge}
                    </Badge>
                    <code className="text-[10px] text-muted-foreground font-mono bg-muted px-1.5 py-0.5 rounded border border-border">
                      {item.endpoint}
                    </code>
                  </div>
                </div>
                <CardDescription className="text-xs text-muted-foreground mt-2 pl-11 sm:pl-11 leading-normal">
                  {item.description}
                </CardDescription>
              </CardHeader>
            </Card>
          );
        })}
      </div>

      {/* Information Banner */}
      <div className="flex items-start gap-3 rounded-lg border border-border bg-card p-4 text-xs text-muted-foreground">
        <Info className="h-4 w-4 text-forest-700 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <span className="font-semibold text-foreground">Stage 1 Architecture Complete:</span>
          <p className="leading-relaxed">
            Layout, routing, TanStack Query integration, and OpenAPI TypeScript types have been established.
            The interactive multi-step evaluation wizard UI will be implemented in subsequent prompts.
          </p>
        </div>
      </div>
    </div>
  );
};
