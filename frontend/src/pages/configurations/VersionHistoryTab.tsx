import React, { useState, useEffect } from 'react';
import {
  ShieldCheck,
  Scale,
  ArrowRight,
  History,
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  useRuleConfigs,
  useScoringConfigs,
  useRuleConfigVersions,
  useScoringConfigVersions,
} from '@/hooks/useConfigurations';

interface VersionHistoryTabProps {
  onInspectRuleConfig: (configId: string, version: number) => void;
  onInspectScoringConfig: (configId: string, version: number) => void;
}

export const VersionHistoryTab: React.FC<VersionHistoryTabProps> = ({
  onInspectRuleConfig,
  onInspectScoringConfig,
}) => {
  const [configType, setConfigType] = useState<'rules' | 'scoring'>('rules');

  const ruleConfigsQuery = useRuleConfigs();
  const scoringConfigsQuery = useScoringConfigs();

  const ruleConfigs = ruleConfigsQuery.data || [];
  const scoringConfigs = scoringConfigsQuery.data || [];

  const [selectedRuleId, setSelectedRuleId] = useState<string>(
    ruleConfigs[0]?.config_id || 'demo_mixed_review'
  );
  const [selectedScoringId, setSelectedScoringId] = useState<string>(
    scoringConfigs[0]?.config_id || 'balanced'
  );

  useEffect(() => {
    if (ruleConfigs.length > 0 && !ruleConfigs.some((c) => c.config_id === selectedRuleId)) {
      setSelectedRuleId(ruleConfigs[0].config_id);
    }
  }, [ruleConfigs, selectedRuleId]);

  useEffect(() => {
    if (scoringConfigs.length > 0 && !scoringConfigs.some((c) => c.config_id === selectedScoringId)) {
      setSelectedScoringId(scoringConfigs[0].config_id);
    }
  }, [scoringConfigs, selectedScoringId]);

  // Versions query
  const ruleVersionsQuery = useRuleConfigVersions(
    configType === 'rules' ? selectedRuleId : null
  );
  const scoringVersionsQuery = useScoringConfigVersions(
    configType === 'scoring' ? selectedScoringId : null
  );

  const versions =
    configType === 'rules'
      ? ruleVersionsQuery.data || [1]
      : scoringVersionsQuery.data || [1];

  const sortedVersions = [...versions].sort((a, b) => b - a);
  const latestVersion = sortedVersions[0] || 1;

  return (
    <div className="space-y-6">
      {/* Top Controls: Type & Configuration Selector */}
      <Card className="border-border">
        <CardContent className="p-4 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            {/* Type Switcher */}
            <div className="flex items-center gap-1.5 p-1 bg-muted rounded-lg border border-border/70 self-start">
              <button
                type="button"
                onClick={() => setConfigType('rules')}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-md transition-colors ${
                  configType === 'rules'
                    ? 'bg-card text-foreground shadow-xs'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                <ShieldCheck className="h-3.5 w-3.5 text-forest-700" />
                Eligibility Rule Configurations
              </button>
              <button
                type="button"
                onClick={() => setConfigType('scoring')}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-md transition-colors ${
                  configType === 'scoring'
                    ? 'bg-card text-foreground shadow-xs'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                <Scale className="h-3.5 w-3.5 text-forest-700" />
                Scoring Models
              </button>
            </div>

            {/* Target Config Dropdown */}
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground font-semibold">Select Configuration:</span>
              {configType === 'rules' ? (
                <select
                  value={selectedRuleId}
                  onChange={(e) => setSelectedRuleId(e.target.value)}
                  className="h-8 text-xs font-medium rounded-md border border-border bg-card px-2.5 text-foreground focus:ring-1 focus:ring-forest-600 shadow-xs"
                >
                  {ruleConfigs.map((c) => (
                    <option key={c.config_id} value={c.config_id}>
                      {c.name} ({c.config_id})
                    </option>
                  ))}
                </select>
              ) : (
                <select
                  value={selectedScoringId}
                  onChange={(e) => setSelectedScoringId(e.target.value)}
                  className="h-8 text-xs font-medium rounded-md border border-border bg-card px-2.5 text-foreground focus:ring-1 focus:ring-forest-600 shadow-xs"
                >
                  {scoringConfigs.map((c) => (
                    <option key={c.config_id} value={c.config_id}>
                      {c.name} ({c.config_id})
                    </option>
                  ))}
                </select>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Audit & Immutability Context Banner */}
      <div className="flex items-center gap-2.5 px-3.5 py-2.5 rounded-lg bg-forest-50/80 border border-forest-200/70 text-forest-950 text-xs shadow-2xs">
        <ShieldCheck className="h-4 w-4 shrink-0 text-forest-700" />
        <p className="text-xs text-forest-900">
          <span className="font-semibold">Immutable Version Guarantee:</span> Every evaluation run records the exact configuration ID and revision snapshot. Historical shortlists remain 100% reproducible.
        </p>
      </div>

      {/* Version History Timeline */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h4 className="text-xs font-bold text-foreground flex items-center gap-1.5">
            <History className="h-3.5 w-3.5 text-forest-700" />
            Recorded Versions for{' '}
            <code className="bg-muted px-1.5 py-0.5 rounded font-mono text-xs">
              {configType === 'rules' ? selectedRuleId : selectedScoringId}
            </code>{' '}
            ({sortedVersions.length} {sortedVersions.length === 1 ? 'version' : 'versions'})
          </h4>
        </div>

        <div className="space-y-3">
          {sortedVersions.map((v) => {
            const isLatest = v === latestVersion;

            return (
              <Card
                key={v}
                className={`border transition-all ${
                  isLatest
                    ? 'border-forest-700/60 bg-forest-50/20'
                    : 'border-border/80 bg-card'
                }`}
              >
                <CardContent className="p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                  <div className="flex items-start gap-3">
                    <div className="mt-0.5">
                      <div
                        className={`h-7 w-7 rounded-full flex items-center justify-center font-mono font-bold text-xs ${
                          isLatest
                            ? 'bg-forest-700 text-white'
                            : 'bg-muted text-muted-foreground border border-border'
                        }`}
                      >
                        v{v}
                      </div>
                    </div>
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-foreground">
                          Version {v}
                        </span>
                        {isLatest ? (
                          <Badge variant="forest" className="font-mono text-[10px]">
                            Current Active
                          </Badge>
                        ) : (
                          <Badge variant="outline" className="font-mono text-[10px] text-muted-foreground">
                            Historical Snapshot
                          </Badge>
                        )}
                      </div>
                      <p className="text-[11px] text-muted-foreground leading-relaxed">
                        {isLatest
                          ? `Currently applied to new evaluation runs using ${
                              configType === 'rules' ? selectedRuleId : selectedScoringId
                            }.`
                          : `Preserved immutable snapshot. Used for reproducible review of historical evaluations.`}
                      </p>
                    </div>
                  </div>

                  <div className="shrink-0 flex items-center gap-2">
                    <Button
                      variant={isLatest ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => {
                        if (configType === 'rules') {
                          onInspectRuleConfig(selectedRuleId, v);
                        } else {
                          onInspectScoringConfig(selectedScoringId, v);
                        }
                      }}
                      className="gap-1.5 text-xs"
                    >
                      <span>Inspect Snapshot v{v}</span>
                      <ArrowRight className="h-3 w-3" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>
    </div>
  );
};
