import React from 'react';
import {
  Calculator,
  CheckCircle2,
  AlertCircle,
  ArrowRight,
  ArrowLeft,
  Scale,
  GitBranch,
  RefreshCw,
  Info,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { useScoringConfigs } from '@/hooks/useEvaluationWizard';
import { formatAggregation } from '@/pages/configurations/configFormatters';
import type { ScoringConfiguration } from '@/types';
import { cn } from '@/lib/utils';

interface Step4ScoringProps {
  selectedScoringConfig: ScoringConfiguration | null;
  onSelectScoringConfig: (config: ScoringConfiguration) => void;
  onBack: () => void;
  onNext: () => void;
}

export const Step4Scoring: React.FC<Step4ScoringProps> = ({
  selectedScoringConfig,
  onSelectScoringConfig,
  onBack,
  onNext,
}) => {
  const {
    data: configs,
    isLoading,
    isError,
    error,
    refetch,
  } = useScoringConfigs();

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-4">
        <div>
          <h3 className="text-lg font-bold text-foreground tracking-tight">
            Step 4: Multi-Criteria Scoring Configuration
          </h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            Select a scoring model to calculate composite candidate scores. Configures relative weights, normalization ranges, and member-to-team aggregations.
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
      {selectedScoringConfig && (
        <div className="flex items-center justify-between p-3 rounded-lg border border-forest-200 bg-forest-50/60 text-xs">
          <div className="flex items-center gap-2">
            <Calculator className="h-4 w-4 text-forest-700" />
            <span className="font-semibold text-forest-950">Active Scoring Model:</span>
            <span className="font-bold text-foreground">{selectedScoringConfig.name}</span>
            <code className="bg-forest-100 text-forest-900 px-1 py-0.5 rounded font-mono text-[10px]">
              {selectedScoringConfig.config_id} (v{selectedScoringConfig.version || 1})
            </code>
          </div>
          <Badge variant="forest" className="text-[10px]">
            Scale Max: {selectedScoringConfig.scale_max || 100} pts
          </Badge>
        </div>
      )}

      {/* Content */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-40 w-full" />
        </div>
      ) : isError ? (
        <div className="p-4 rounded-lg border border-destructive/30 bg-destructive/5 text-destructive text-xs space-y-2">
          <div className="flex items-center gap-2 font-semibold">
            <AlertCircle className="h-4 w-4" />
            Failed to load scoring configurations
          </div>
          <p>{error?.message || 'Server error'}</p>
          <Button size="sm" variant="outline" onClick={() => refetch()}>
            Retry
          </Button>
        </div>
      ) : !configs || configs.length === 0 ? (
        <div className="text-center py-10 px-4 rounded-lg border border-dashed border-border bg-card">
          <Calculator className="h-9 w-9 text-muted-foreground/60 mx-auto mb-2" />
          <h4 className="text-sm font-semibold text-foreground">No Scoring Configurations Found</h4>
          <p className="text-xs text-muted-foreground max-w-md mx-auto mt-1 mb-4">
            No scoring models are currently registered in the database. Ensure backend seeds have run.
          </p>
          <Button size="sm" variant="outline" onClick={() => refetch()}>
            Check Again
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {configs.map((config) => {
            const isSelected = selectedScoringConfig?.config_id === config.config_id;
            const criteria = config.criteria || [];

            return (
              <Card
                key={config.config_id}
                onClick={() => onSelectScoringConfig(config)}
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
                        name="scoringConfigSelection"
                        checked={isSelected}
                        onChange={() => onSelectScoringConfig(config)}
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
                        Max {config.scale_max} pts
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
                    {config.description || 'Standard weighted recruitment scoring model.'}
                  </CardDescription>
                </CardHeader>

                <CardContent className="p-4 pt-0 pl-10 space-y-2.5">
                  {/* Criteria List */}
                  {criteria.length > 0 && (
                    <div className="space-y-1.5">
                      <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider block">
                        Evaluation Criteria ({criteria.length}):
                      </span>
                      <div className="space-y-1 bg-muted/30 p-2 rounded-md border border-border/60">
                        {criteria.map((crit) => (
                          <div
                            key={crit.criterion_id}
                            className="flex items-center justify-between text-[11px]"
                          >
                            <span
                              className="font-medium text-foreground truncate max-w-[160px] cursor-help"
                              title={crit.name}
                            >
                              {crit.name}
                            </span>
                            <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
                              <span className="text-forest-800 font-semibold bg-forest-50 px-1.5 py-0.5 rounded border border-forest-200/60 text-[10px]">
                                Weight: {crit.weight}
                              </span>
                              <span className="text-[10px] text-muted-foreground">
                                {formatAggregation(crit.aggregation)}
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="pt-2 border-t border-border/60 flex items-center gap-4 text-[11px] text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <Scale className="h-3 w-3 text-forest-700" />
                      {criteria.length} Criteria
                    </span>
                    <span className="flex items-center gap-1">
                      <GitBranch className="h-3 w-3 text-muted-foreground" />
                      Version {config.version || 1}
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
          The scoring engine evaluates criteria independently and automatically renormalizes weights if optional signals are missing, avoiding unfair zero-penalty exclusions.
        </p>
      </div>

      {/* Footer Navigation */}
      <div className="flex items-center justify-between border-t border-border pt-4">
        <Button variant="outline" onClick={onBack} className="gap-2">
          <ArrowLeft className="h-4 w-4" />
          Back to Eligibility
        </Button>

        <div className="flex items-center gap-3">
          <span className="text-xs text-muted-foreground hidden sm:inline">
            {selectedScoringConfig
              ? `Scoring model "${selectedScoringConfig.name}" selected`
              : 'Select a scoring model to proceed'}
          </span>
          <Button
            onClick={onNext}
            disabled={!selectedScoringConfig}
            className="gap-2 shadow-sm"
          >
            Next: Review & Run Pipeline
            <ArrowRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
};
