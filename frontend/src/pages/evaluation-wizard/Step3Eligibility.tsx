import React from 'react';
import {
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  ArrowRight,
  ArrowLeft,
  Layers,
  GitBranch,
  RefreshCw,
  Info,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { useRuleConfigs } from '@/hooks/useEvaluationWizard';
import type { RuleConfiguration } from '@/types';
import { cn } from '@/lib/utils';

interface Step3EligibilityProps {
  selectedRuleConfig: RuleConfiguration | null;
  onSelectRuleConfig: (config: RuleConfiguration) => void;
  onBack: () => void;
  onNext: () => void;
}

export const Step3Eligibility: React.FC<Step3EligibilityProps> = ({
  selectedRuleConfig,
  onSelectRuleConfig,
  onBack,
  onNext,
}) => {
  const {
    data: configs,
    isLoading,
    isError,
    error,
    refetch,
  } = useRuleConfigs();

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-4">
        <div>
          <h3 className="text-lg font-bold text-foreground tracking-tight">
            Step 3: Eligibility Rule Configuration
          </h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            Select an immutable rule configuration snapshot. Evaluates team sizes, technical profile presence, and academic thresholds with human-readable audit explanations.
          </p>
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={() => refetch()}
          disabled={isLoading}
          className="text-xs h-8 gap-1.5 self-start sm:self-auto"
        >
          <RefreshCw className={cn('h-3.5 w-3.5', isLoading && 'animate-spin')} />
          Refresh Presets
        </Button>
      </div>

      {/* Selected Config Info Pill */}
      {selectedRuleConfig && (
        <div className="flex items-center justify-between p-3 rounded-lg border border-forest-200 bg-forest-50/60 text-xs">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-forest-700" />
            <span className="font-semibold text-forest-950">Active Rule Config:</span>
            <span className="font-bold text-foreground">{selectedRuleConfig.name}</span>
            <code className="bg-forest-100 text-forest-900 px-1 py-0.5 rounded font-mono text-[10px]">
              {selectedRuleConfig.config_id} (v{selectedRuleConfig.version})
            </code>
          </div>
          <Badge variant="forest" className="text-[10px]">
            {selectedRuleConfig.rules?.length || 0} Rules Active
          </Badge>
        </div>
      )}

      {/* Content */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-40 w-full" />
        </div>
      ) : isError ? (
        <div className="p-4 rounded-lg border border-destructive/30 bg-destructive/5 text-destructive text-xs space-y-2">
          <div className="flex items-center gap-2 font-semibold">
            <AlertCircle className="h-4 w-4" />
            Failed to load rule configurations
          </div>
          <p>{error?.message || 'Server error'}</p>
          <Button size="sm" variant="outline" onClick={() => refetch()}>
            Retry
          </Button>
        </div>
      ) : !configs || configs.length === 0 ? (
        <div className="text-center py-10 px-4 rounded-lg border border-dashed border-border bg-card">
          <ShieldCheck className="h-9 w-9 text-muted-foreground/60 mx-auto mb-2" />
          <h4 className="text-sm font-semibold text-foreground">No Rule Configurations Found</h4>
          <p className="text-xs text-muted-foreground max-w-md mx-auto mt-1 mb-4">
            No rule configurations are currently registered in the database. Ensure backend seeds have run.
          </p>
          <Button size="sm" variant="outline" onClick={() => refetch()}>
            Check Again
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {configs.map((config) => {
            const isSelected = selectedRuleConfig?.config_id === config.config_id;
            const rules = config.rules || [];

            return (
              <Card
                key={config.config_id}
                onClick={() => onSelectRuleConfig(config)}
                className={cn(
                  'cursor-pointer transition-all border flex flex-col justify-between',
                  isSelected
                    ? 'border-forest-600 bg-forest-50/40 shadow-sm ring-1 ring-forest-500/20'
                    : 'border-border/80 hover:border-forest-300 hover:bg-muted/20'
                )}
              >
                <CardHeader className="p-4 pb-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <input
                        type="radio"
                        name="ruleConfigSelection"
                        checked={isSelected}
                        onChange={() => onSelectRuleConfig(config)}
                        onClick={(e) => e.stopPropagation()}
                        className="h-4 w-4 text-forest-700 focus:ring-forest-600 border-border mt-0.5"
                      />
                      <div>
                        <CardTitle className="text-sm font-semibold text-foreground">
                          {config.name}
                        </CardTitle>
                        <code className="text-[10px] font-mono text-muted-foreground">
                          {config.config_id}
                        </code>
                      </div>
                    </div>

                    <div className="flex items-center gap-1.5">
                      <Badge variant="outline" className="text-[10px] font-mono">
                        v{config.version}
                      </Badge>
                      {isSelected && (
                        <Badge variant="forest" className="gap-1 text-[10px]">
                          <CheckCircle2 className="h-3 w-3" />
                          Selected
                        </Badge>
                      )}
                    </div>
                  </div>

                  <CardDescription className="text-xs text-muted-foreground leading-normal mt-2 pl-6">
                    {config.description || 'Standard recruitment eligibility configuration.'}
                  </CardDescription>
                </CardHeader>

                <CardContent className="p-4 pt-0 pl-10 space-y-2.5">
                  {/* Evaluator Rules Breakdown */}
                  {rules.length > 0 && (
                    <div className="space-y-1.5">
                      <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider block">
                        Included Rules ({rules.length}):
                      </span>
                      <div className="flex flex-wrap gap-1">
                        {rules.map((r) => (
                          <span
                            key={r.rule_id}
                            className={cn(
                              'text-[10px] px-1.5 py-0.5 rounded border font-mono flex items-center gap-1',
                              r.severity === 'hard'
                                ? 'bg-card text-foreground border-border'
                                : 'bg-muted/40 text-muted-foreground border-border/60'
                            )}
                            title={`${r.name}: ${r.description}`}
                          >
                            <span>{r.rule_type}</span>
                            <span
                              className={cn(
                                'text-[9px] uppercase font-bold',
                                r.severity === 'hard' ? 'text-forest-800' : 'text-muted-foreground'
                              )}
                            >
                              ({r.severity})
                            </span>
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="pt-2 border-t border-border/60 flex items-center gap-4 text-[11px] text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <Layers className="h-3 w-3 text-forest-700" />
                      {rules.length} Evaluators
                    </span>
                    <span className="flex items-center gap-1">
                      <GitBranch className="h-3 w-3 text-muted-foreground" />
                      Immutable Version {config.version}
                    </span>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Advisory Notice */}
      <div className="flex items-start gap-2.5 p-3 rounded-lg border border-border bg-card text-xs text-muted-foreground">
        <Info className="h-4 w-4 text-forest-700 shrink-0 mt-0.5" />
        <p className="leading-relaxed">
          Rule configurations in the recruitment tool are versioned and immutable. Evaluation runs record the exact snapshot version used, ensuring complete reproducibility of decisions and audit trails.
        </p>
      </div>

      {/* Footer Navigation */}
      <div className="flex items-center justify-between border-t border-border pt-4">
        <Button variant="outline" onClick={onBack} className="gap-2">
          <ArrowLeft className="h-4 w-4" />
          Back to Signals
        </Button>

        <div className="flex items-center gap-3">
          <span className="text-xs text-muted-foreground hidden sm:inline">
            {selectedRuleConfig
              ? `Rule config "${selectedRuleConfig.name}" selected`
              : 'Select a rule configuration to proceed'}
          </span>
          <Button
            onClick={onNext}
            disabled={!selectedRuleConfig}
            className="gap-2 shadow-sm"
          >
            Next: Scoring Model
            <ArrowRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
};
