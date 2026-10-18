import React, { useState } from 'react';
import {
  ShieldCheck,
  Scale,
  GitBranch,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { EligibilityTab } from './configurations/EligibilityTab';
import { ScoringTab } from './configurations/ScoringTab';
import { VersionHistoryTab } from './configurations/VersionHistoryTab';

type ActiveTab = 'rules' | 'scoring' | 'history';

export const ConfigurationsPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<ActiveTab>('rules');

  // Inspection state when jumping from history tab
  const [inspectedRule, setInspectedRule] = useState<{ id: string; version: number } | null>(null);
  const [inspectedScoring, setInspectedScoring] = useState<{ id: string; version: number } | null>(null);

  const handleInspectRuleConfig = (configId: string, version: number) => {
    setInspectedRule({ id: configId, version });
    setActiveTab('rules');
  };

  const handleInspectScoringConfig = (configId: string, version: number) => {
    setInspectedScoring({ id: configId, version });
    setActiveTab('scoring');
  };

  return (
    <div className="space-y-6">
      {/* Editorial Header */}
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <Badge variant="forest" className="font-mono text-xs">
            Configuration Management
          </Badge>
          <span className="text-xs text-muted-foreground">· Immutable Versioning Active</span>
        </div>
        <h2 className="text-xl font-bold tracking-tight text-foreground">
          Eligibility Rules & Scoring Configurations
        </h2>
        <p className="text-sm text-muted-foreground max-w-3xl leading-relaxed">
          Manage deterministic eligibility criteria, configure relative scoring weights, and inspect
          versioned snapshots ensuring all historical recruitment evaluations remain 100% reproducible.
        </p>
      </div>

      {/* Primary Navigation Tabs */}
      <div className="border-b border-border">
        <nav className="flex space-x-6" aria-label="Configuration Sections">
          <button
            type="button"
            onClick={() => setActiveTab('rules')}
            className={`flex items-center gap-2 pb-3 text-xs font-semibold border-b-2 transition-colors cursor-pointer ${
              activeTab === 'rules'
                ? 'border-forest-700 text-forest-700'
                : 'border-transparent text-muted-foreground hover:text-foreground hover:border-border'
            }`}
          >
            <ShieldCheck className="h-4 w-4" />
            Eligibility Rules
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('scoring')}
            className={`flex items-center gap-2 pb-3 text-xs font-semibold border-b-2 transition-colors cursor-pointer ${
              activeTab === 'scoring'
                ? 'border-forest-700 text-forest-700'
                : 'border-transparent text-muted-foreground hover:text-foreground hover:border-border'
            }`}
          >
            <Scale className="h-4 w-4" />
            Scoring Weights & Models
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('history')}
            className={`flex items-center gap-2 pb-3 text-xs font-semibold border-b-2 transition-colors cursor-pointer ${
              activeTab === 'history'
                ? 'border-forest-700 text-forest-700'
                : 'border-transparent text-muted-foreground hover:text-foreground hover:border-border'
            }`}
          >
            <GitBranch className="h-4 w-4" />
            Version History & Audit
          </button>
        </nav>
      </div>

      {/* Tab Panels */}
      {activeTab === 'rules' && (
        <EligibilityTab
          key={`rules-${inspectedRule?.id}-${inspectedRule?.version}`}
          initialConfigId={inspectedRule?.id}
          initialVersion={inspectedRule?.version}
        />
      )}

      {activeTab === 'scoring' && (
        <ScoringTab
          key={`scoring-${inspectedScoring?.id}-${inspectedScoring?.version}`}
          initialConfigId={inspectedScoring?.id}
          initialVersion={inspectedScoring?.version}
        />
      )}

      {activeTab === 'history' && (
        <VersionHistoryTab
          onInspectRuleConfig={handleInspectRuleConfig}
          onInspectScoringConfig={handleInspectScoringConfig}
        />
      )}
    </div>
  );
};
