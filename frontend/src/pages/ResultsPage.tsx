import React from 'react';
import {
  FileSpreadsheet,
  CheckCircle2,
  AlertTriangle,
  ShieldAlert,
  ArrowUpDown,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

const RESULT_CATEGORIES = [
  {
    status: 'SELECTED',
    badge: 'success',
    icon: CheckCircle2,
    title: 'Top-X Shortlisted Candidates',
    description:
      'Teams that satisfy all hard mandatory eligibility rules, achieved calculable composite scores, and placed within the requested Top-X cutoff.',
  },
  {
    status: 'NEEDS_REVIEW',
    badge: 'warning',
    icon: AlertTriangle,
    title: 'Review Candidates (Organizer Action Required)',
    description:
      'Candidates flagged by manual review fallback rules (e.g. missing team lead role designation). Organizers can apply audited status overrides directly.',
  },
  {
    status: 'NOT_SELECTED',
    badge: 'secondary',
    icon: ArrowUpDown,
    title: 'Below Cutoff Boundary',
    description:
      'Eligible, scored candidates ranking below the Top-X cutoff threshold. Evaluated with boundary tie detection to prevent silent unfair exclusions.',
  },
  {
    status: 'UNRESOLVED',
    badge: 'info',
    icon: ShieldAlert,
    title: 'Ambiguous & Duplicate Registrations',
    description:
      'Teams with colliding duplicate names assigned temporary IDs (temp_team_...) or cross-team member identity collisions requiring verification.',
  },
  {
    status: 'EXCLUDED',
    badge: 'destructive',
    icon: ShieldAlert,
    title: 'Disqualified / Ineligible Teams',
    description:
      'Candidates failing mandatory hard eligibility criteria (e.g. team size constraints, missing technical profile links) with human-readable audit explanations.',
  },
];

export const ResultsPage: React.FC = () => {
  return (
    <div className="space-y-6">
      {/* Intro Header */}
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <Badge variant="forest" className="font-mono text-xs">
            Results & Leaderboard Staging
          </Badge>
          <span className="text-xs text-muted-foreground">· Explainable Output</span>
        </div>
        <h2 className="text-xl font-bold tracking-tight text-foreground">
          Evaluation Results & Shortlists
        </h2>
        <p className="text-sm text-muted-foreground max-w-2xl leading-relaxed">
          The Results module presents ranked leaderboards, full multi-criteria score breakdowns, cutoff tie warnings, and reviewer manual overrides backed by UTF-8 BOM CSV exports.
        </p>
      </div>

      {/* Category Breakdown Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {RESULT_CATEGORIES.map((cat) => {
          const Icon = cat.icon;
          return (
            <Card key={cat.status} className="border-border/80">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <Badge variant={cat.badge as any} className="font-mono text-[10px]">
                    {cat.status}
                  </Badge>
                  <Icon className="h-4 w-4 text-muted-foreground" />
                </div>
                <CardTitle className="text-sm font-semibold mt-2">{cat.title}</CardTitle>
                <CardDescription className="text-xs text-muted-foreground leading-normal">
                  {cat.description}
                </CardDescription>
              </CardHeader>
            </Card>
          );
        })}

        {/* CSV Export Feature Card */}
        <Card className="border-border/80 bg-forest-50/30">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <Badge variant="forest" className="font-mono text-[10px]">
                RFC 4180 COMPLIANT
              </Badge>
              <FileSpreadsheet className="h-4 w-4 text-forest-700" />
            </div>
            <CardTitle className="text-sm font-semibold mt-2">
              Formula-Safe Spreadsheet Export
            </CardTitle>
            <CardDescription className="text-xs text-muted-foreground leading-normal">
              One-click download of Top-X shortlists via <code className="font-mono bg-forest-100/60 px-1 py-0.5 rounded text-forest-900">GET /api/ranking/runs/&#123;id&#125;/export</code> with UTF-8 BOM encoding and injection neutralization.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    </div>
  );
};
