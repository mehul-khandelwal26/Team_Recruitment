import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  ShieldCheck,
  Scale,
  GitBranch,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { useRuleConfigs, useScoringConfigs } from '@/hooks/useConfigurations';
import { EligibilityTab } from './configurations/EligibilityTab';
import { ScoringTab } from './configurations/ScoringTab';
import { VersionHistoryTab } from './configurations/VersionHistoryTab';

type ActiveTab = 'rules' | 'scoring' | 'history';

export const ConfigurationsPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const tabParam = searchParams.get('tab') as ActiveTab | null;
  const [activeTab, setActiveTab] = useState<ActiveTab>(
    tabParam === 'scoring' || tabParam === 'history' || tabParam === 'rules' ? tabParam : 'rules'
  );

  useEffect(() => {
    if (tabParam && (tabParam === 'scoring' || tabParam === 'history' || tabParam === 'rules')) {
      setActiveTab(tabParam);
    }
  }, [tabParam]);

  const handleTabChange = (tab: ActiveTab) => {
    setActiveTab(tab);
    setSearchParams({ tab });
  };

  // Inspection state when jumping from history tab
  const [inspectedRule, setInspectedRule] = useState<{ id: string; version: number } | null>(null);
  const [inspectedScoring, setInspectedScoring] = useState<{ id: string; version: number } | null>(null);

  const handleInspectRuleConfig = (configId: string, version: number) => {
    setInspectedRule({ id: configId, version });
    handleTabChange('rules');
  };

  const handleInspectScoringConfig = (configId: string, version: number) => {
    setInspectedScoring({ id: configId, version });
    handleTabChange('scoring');
  };

  const ruleConfigsQuery = useRuleConfigs();
  const scoringConfigsQuery = useScoringConfigs();
  const ruleCount = ruleConfigsQuery.data?.length ?? 0;
  const scoringCount = scoringConfigsQuery.data?.length ?? 0;

  return (
    <div className="space-y-6">
      {/* Segmented Tab Controls & Quick Engine Status */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border pb-4">
        {/* Segmented Tab Buttons */}
        <div className="inline-flex items-center gap-1 p-1 rounded-lg bg-secondary/60 border border-border/70 overflow-x-auto max-w-full">
          <button
            type="button"
            onClick={() => handleTabChange('rules')}
            className={cn(
              'inline-flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium transition-all cursor-pointer whitespace-nowrap',
              activeTab === 'rules'
                ? 'bg-card text-foreground shadow-xs font-semibold'
                : 'text-muted-foreground hover:text-foreground hover:bg-card/50'
            )}
          >
            <ShieldCheck className={cn('h-3.5 w-3.5', activeTab === 'rules' ? 'text-forest-700' : 'text-muted-foreground')} />
            <span>Eligibility Rules</span>
            <span
              className={cn(
                'font-mono text-[10px] px-1.5 py-0.2 rounded-full',
                activeTab === 'rules'
                  ? 'bg-forest-50 text-forest-800 border border-forest-200/60 font-semibold'
                  : 'bg-muted text-muted-foreground'
              )}
            >
              {ruleCount}
            </span>
          </button>

          <button
            type="button"
            onClick={() => handleTabChange('scoring')}
            className={cn(
              'inline-flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium transition-all cursor-pointer whitespace-nowrap',
              activeTab === 'scoring'
                ? 'bg-card text-foreground shadow-xs font-semibold'
                : 'text-muted-foreground hover:text-foreground hover:bg-card/50'
            )}
          >
            <Scale className={cn('h-3.5 w-3.5', activeTab === 'scoring' ? 'text-forest-700' : 'text-muted-foreground')} />
            <span>Scoring Weights & Models</span>
            <span
              className={cn(
                'font-mono text-[10px] px-1.5 py-0.2 rounded-full',
                activeTab === 'scoring'
                  ? 'bg-forest-50 text-forest-800 border border-forest-200/60 font-semibold'
                  : 'bg-muted text-muted-foreground'
              )}
            >
              {scoringCount}
            </span>
          </button>

          <button
            type="button"
            onClick={() => handleTabChange('history')}
            className={cn(
              'inline-flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium transition-all cursor-pointer whitespace-nowrap',
              activeTab === 'history'
                ? 'bg-card text-foreground shadow-xs font-semibold'
                : 'text-muted-foreground hover:text-foreground hover:bg-card/50'
            )}
          >
            <GitBranch className={cn('h-3.5 w-3.5', activeTab === 'history' ? 'text-forest-700' : 'text-muted-foreground')} />
            <span>Version History & Audit</span>
          </button>
        </div>

        {/* Quick Audit Indicator */}
        <div className="hidden sm:flex items-center gap-2 text-xs text-muted-foreground">
          <Badge variant="outline" className="font-mono text-[10px] bg-card text-muted-foreground">
            Deterministic Engine
          </Badge>
          <span className="text-[11px]">All versions immutable & audit-backed</span>
        </div>
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
