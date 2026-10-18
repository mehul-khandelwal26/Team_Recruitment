import React from 'react';
import {
  ShieldCheck,
  Scale,
  Layers,
  GitBranch,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

const RULE_PRESETS = [
  {
    id: 'demo_mixed_review',
    name: 'Demo: Lead Academic Review',
    tag: 'Seeded Demo Preset',
    badgeVariant: 'forest',
    description:
      'Evaluates team size (>= 2, hard), technical profile presence (any member GitHub, hard), and designated team lead academic standing (CGPA >= 7.0, hard) with manual review on missing lead designation.',
    rulesCount: 3,
  },
  {
    id: 'basic',
    name: 'Basic Hackathon Eligibility',
    tag: 'Standard Preset',
    badgeVariant: 'secondary',
    description:
      'Balanced default eligibility: enforces team sizing (2-4 members, hard), technical profile presence (at least 1 member with GitHub link, hard), and academic advisory (CGPA >= 6.0, soft).',
    rulesCount: 3,
  },
  {
    id: 'strict',
    name: 'Strict Hackathon Eligibility',
    tag: 'Rigorous Preset',
    badgeVariant: 'outline',
    description:
      'Rigorous multi-member standard: team size 2-4 (hard), all members must provide GitHub profile (hard), all members CGPA >= 7.0 (hard), active public repository presence (hard), and resume link advisory (soft).',
    rulesCount: 6,
  },
  {
    id: 'open_solo',
    name: 'Open to Solos and Teams',
    tag: 'Flexible Preset',
    badgeVariant: 'outline',
    description:
      'Accommodates solo participants (1 member) up to squads of 4, requiring at least 1 GitHub link and recommending minimum academic baseline.',
    rulesCount: 4,
  },
];

const SCORING_PRESETS = [
  {
    id: 'balanced',
    name: 'Balanced Multi-Criteria',
    description:
      'Default multi-signal scoring model with equal weighting across technical capabilities, repository activity, academic standing, and education year.',
  },
  {
    id: 'technical_heavy',
    name: 'Technical & Project Heavy',
    description:
      'Emphasizes verified public repository counts, GitHub commit recency, and technical link presence over academic GPA metrics.',
  },
  {
    id: 'academic_heavy',
    name: 'Academic Standing Focus',
    description:
      'Prioritizes normalized academic CGPA/CPI and graduation batch progression for merit-based academic recruitment.',
  },
];

export const ConfigurationsPage: React.FC = () => {
  return (
    <div className="space-y-8">
      {/* Intro Header */}
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <Badge variant="forest" className="font-mono text-xs">
            Configuration Management Staging
          </Badge>
          <span className="text-xs text-muted-foreground">· Immutable Versioning</span>
        </div>
        <h2 className="text-xl font-bold tracking-tight text-foreground">
          Eligibility Rules & Scoring Configurations
        </h2>
        <p className="text-sm text-muted-foreground max-w-2xl leading-relaxed">
          The engine stores versioned configuration snapshots ensuring historical evaluations remain 100% reproducible even after rules or weights are modified.
        </p>
      </div>

      {/* Built-in Rule Presets Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <h3 className="text-base font-semibold text-foreground tracking-tight flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-forest-700" />
              Built-in Eligibility Rule Presets
            </h3>
            <p className="text-xs text-muted-foreground">
              Seeded automatically during server startup across in-memory and PostgreSQL backends.
            </p>
          </div>
          <Badge variant="forest" className="font-mono text-xs">
            4 Presets Registered
          </Badge>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {RULE_PRESETS.map((preset) => (
            <Card key={preset.id} className="border-border/80">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <Badge variant={preset.badgeVariant as any} className="font-mono text-[10px]">
                    {preset.tag}
                  </Badge>
                  <code className="text-[11px] font-mono text-muted-foreground bg-muted px-1.5 py-0.5 rounded border border-border">
                    {preset.id}
                  </code>
                </div>
                <CardTitle className="text-sm font-semibold mt-2">{preset.name}</CardTitle>
                <CardDescription className="text-xs text-muted-foreground leading-normal">
                  {preset.description}
                </CardDescription>
              </CardHeader>
              <CardContent className="pt-0 text-[11px] text-muted-foreground flex items-center gap-3">
                <span className="flex items-center gap-1">
                  <Layers className="h-3 w-3 text-forest-700" />
                  {preset.rulesCount} Evaluator Rules
                </span>
                <span className="flex items-center gap-1">
                  <GitBranch className="h-3 w-3 text-muted-foreground" />
                  Version 1 (Immutable)
                </span>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {/* Built-in Scoring Presets Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <h3 className="text-base font-semibold text-foreground tracking-tight flex items-center gap-2">
              <Scale className="h-4 w-4 text-forest-700" />
              Standard Scoring Presets
            </h3>
            <p className="text-xs text-muted-foreground">
              Pre-configured multi-criteria relative weighting and team aggregation models.
            </p>
          </div>
          <Badge variant="secondary" className="font-mono text-xs">
            3 Models Seeded
          </Badge>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {SCORING_PRESETS.map((preset) => (
            <Card key={preset.id} className="border-border/80">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <Badge variant="outline" className="font-mono text-[10px]">
                    Scoring Model
                  </Badge>
                  <code className="text-[11px] font-mono text-muted-foreground bg-muted px-1.5 py-0.5 rounded border border-border">
                    {preset.id}
                  </code>
                </div>
                <CardTitle className="text-sm font-semibold mt-2">{preset.name}</CardTitle>
                <CardDescription className="text-xs text-muted-foreground leading-normal">
                  {preset.description}
                </CardDescription>
              </CardHeader>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
};
