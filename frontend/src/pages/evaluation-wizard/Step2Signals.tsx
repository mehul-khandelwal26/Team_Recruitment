import React from 'react';
import {
  Cpu,
  GraduationCap,
  Github,
  CheckCircle2,
  ArrowRight,
  ArrowLeft,
  RotateCcw,
  Sparkles,
  Info,
  TableProperties,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';

import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { TruncatedId } from '@/components/common/TruncatedId';
import { useWizardExtractions, useDatasetRecord } from '@/hooks/useEvaluationWizard';
import type { DatasetSummary, ExtractionRunSummary } from '@/types';
import { cn } from '@/lib/utils';

export interface SignalOption {
  key: string;
  name: string;
  category: 'academic' | 'github';
  description: string;
  isRecommended?: boolean;
}

export const SUPPORTED_SIGNALS: SignalOption[] = [
  // Academic Signals
  {
    key: 'academic_cgpa',
    name: 'Academic CGPA / CPI',
    category: 'academic',
    description: 'Extracts original declared CGPA or percentage marks from candidate registration record.',
    isRecommended: true,
  },
  {
    key: 'academic_year',
    name: 'Academic Year / Batch',
    category: 'academic',
    description: 'Resolves current student year of study or expected graduation batch year.',
    isRecommended: true,
  },
  {
    key: 'normalized_cgpa_10_scale',
    name: 'Normalized CGPA (10.0 Scale)',
    category: 'academic',
    description: 'Standardizes varied grading scales (4.0, 5.0, 100%, letter grades) onto a uniform 10.0 scale.',
    isRecommended: true,
  },
  // Technical / GitHub Signals
  {
    key: 'github_public_repo_count',
    name: 'GitHub Public Repository Count',
    category: 'github',
    description: 'Queries verified public repository count for candidate profile.',
  },
  {
    key: 'github_repo_metadata',
    name: 'Repository Languages & Metadata',
    category: 'github',
    description: 'Analyzes primary coding languages, repository stars, and fork counts.',
  },
  {
    key: 'github_recent_activity',
    name: 'Recent Activity & Commit Recency',
    category: 'github',
    description: 'Measures recent public activity, commit velocity, and event timestamps within 90 days.',
  },
  {
    key: 'github_profile_verified',
    name: 'Profile Authenticity & Verification',
    category: 'github',
    description: 'Validates GitHub username existence, public biography, and account longevity.',
  },
];

interface Step2SignalsProps {
  selectedDataset: DatasetSummary;
  signalMode: 'configure' | 'reuse';
  onSignalModeChange: (mode: 'configure' | 'reuse') => void;
  selectedSignals: string[];
  onSelectedSignalsChange: (signals: string[]) => void;
  selectedExtractionRun: ExtractionRunSummary | null;
  onSelectExtractionRun: (run: ExtractionRunSummary | null) => void;
  onBack: () => void;
  onNext: () => void;
}

export const Step2Signals: React.FC<Step2SignalsProps> = ({
  selectedDataset,
  signalMode,
  onSignalModeChange,
  selectedSignals,
  onSelectedSignalsChange,
  selectedExtractionRun,
  onSelectExtractionRun,
  onBack,
  onNext,
}) => {
  const {
    data: existingRuns,
    isLoading: isLoadingRuns,
    isError: isRunsError,
    refetch: refetchRuns,
  } = useWizardExtractions(selectedDataset.dataset_id);

  const { data: activeDatasetRecord } = useDatasetRecord(selectedDataset.dataset_id);
  const activeMapping: Record<string, string> = React.useMemo(() => {
    return (
      (selectedDataset.mapping as Record<string, string>) ||
      (activeDatasetRecord?.mapping as Record<string, string>) ||
      {}
    );
  }, [selectedDataset, activeDatasetRecord]);

  const mappedAcademicCols = React.useMemo(() => {
    return Object.entries(activeMapping).filter(([_, tgt]) =>
      ['cgpa', 'academic_year'].includes(tgt.toLowerCase())
    );
  }, [activeMapping]);

  const mappedGithubCols = React.useMemo(() => {
    return Object.entries(activeMapping).filter(([_, tgt]) =>
      tgt.toLowerCase() === 'github_url'
    );
  }, [activeMapping]);

  const toggleSignal = (key: string) => {
    if (selectedSignals.includes(key)) {
      onSelectedSignalsChange(selectedSignals.filter((k) => k !== key));
    } else {
      onSelectedSignalsChange([...selectedSignals, key]);
    }
  };

  const selectAllAcademic = () => {
    const academicKeys = SUPPORTED_SIGNALS.filter((s) => s.category === 'academic').map((s) => s.key);
    const nonAcademic = selectedSignals.filter((k) => !academicKeys.includes(k));
    onSelectedSignalsChange([...nonAcademic, ...academicKeys]);
  };

  const selectAllGithub = () => {
    const githubKeys = SUPPORTED_SIGNALS.filter((s) => s.category === 'github').map((s) => s.key);
    const nonGithub = selectedSignals.filter((k) => !githubKeys.includes(k));
    onSelectedSignalsChange([...nonGithub, ...githubKeys]);
  };

  const clearGithub = () => {
    const githubKeys = SUPPORTED_SIGNALS.filter((s) => s.category === 'github').map((s) => s.key);
    onSelectedSignalsChange(selectedSignals.filter((k) => !githubKeys.includes(k)));
  };

  const academicSignals = SUPPORTED_SIGNALS.filter((s) => s.category === 'academic');
  const githubSignals = SUPPORTED_SIGNALS.filter((s) => s.category === 'github');

  const isValid =
    signalMode === 'reuse'
      ? selectedExtractionRun !== null
      : selectedSignals.length > 0;

  const formatDate = (isoString?: string | null) => {
    if (!isoString) return '—';
    try {
      return new Date(isoString).toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return isoString;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header & Mode Switcher */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-4">
        <div>
          <h3 className="text-lg font-bold text-foreground tracking-tight">
            Step 2: Signal Extraction Configuration
          </h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            Configure pluggable academic and technical analyzers or select a previously recorded extraction run.
          </p>
        </div>

        {/* Mode Selector */}
        <div className="inline-flex rounded-lg border border-border p-1 bg-muted/40">
          <button
            type="button"
            onClick={() => {
              onSignalModeChange('configure');
              onSelectExtractionRun(null);
            }}
            className={cn(
              'flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded-md transition-all',
              signalMode === 'configure'
                ? 'bg-card text-foreground shadow-sm font-semibold'
                : 'text-muted-foreground hover:text-foreground'
            )}
          >
            <Sparkles className="h-3.5 w-3.5 text-forest-700" />
            Configure Signals
            <Badge variant="secondary" className="text-[10px] h-4 px-1">
              {selectedSignals.length}
            </Badge>
          </button>
          <button
            type="button"
            onClick={() => onSignalModeChange('reuse')}
            className={cn(
              'flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded-md transition-all',
              signalMode === 'reuse'
                ? 'bg-card text-foreground shadow-sm font-semibold'
                : 'text-muted-foreground hover:text-foreground'
            )}
          >
            <RotateCcw className="h-3.5 w-3.5" />
            Reuse Previous Run
            {existingRuns && existingRuns.length > 0 && (
              <Badge variant="forest" className="text-[10px] h-4 px-1">
                {existingRuns.length}
              </Badge>
            )}
          </button>
        </div>
      </div>

      {/* Dataset Context Bar */}
      <div className="p-3 rounded-lg border border-border bg-card text-xs space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-muted-foreground">
            <span>Active Dataset:</span>
            <strong className="text-foreground">{selectedDataset.filename}</strong>
            <span>·</span>
            <span>
              ID: <TruncatedId id={selectedDataset.dataset_id} />
            </span>
            <span>·</span>
            <span>{selectedDataset.teams_count} teams</span>
          </div>
          <Badge variant="outline" className="font-mono text-[10px] uppercase">
            {selectedDataset.file_type}
          </Badge>
        </div>

        {/* Active Applied Column Mappings */}
        {Object.keys(activeMapping).length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 pt-2 border-t border-border/60">
            <div className="flex items-center gap-1 text-[10px] font-semibold text-forest-800 uppercase tracking-wider">
              <TableProperties className="h-3 w-3 text-forest-700" />
              <span>Applied Ingestion Field Mappings:</span>
            </div>
            {Object.entries(activeMapping).map(([orig, tgt]) => (
              <span
                key={orig}
                className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-forest-50 border border-forest-200 font-mono text-[10px] text-forest-950"
              >
                <span className="font-semibold">{orig}</span>
                <span className="text-forest-600">→</span>
                <span className="font-bold text-forest-900">{tgt}</span>
              </span>
            ))}
          </div>
        )}
      </div>

      {/* MODE 1: CONFIGURE SIGNALS */}
      {signalMode === 'configure' && (
        <div className="space-y-6">
          {/* Academic Signals Section */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="h-6 w-6 rounded bg-forest-100 flex items-center justify-center text-forest-800">
                  <GraduationCap className="h-3.5 w-3.5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h4 className="text-sm font-semibold text-foreground">
                      Academic Performance Signals
                    </h4>
                    {mappedAcademicCols.map(([orig, tgt]) => (
                      <Badge key={orig} variant="forest" className="text-[9px] font-mono py-0">
                        Mapped: "{orig}" → {tgt}
                      </Badge>
                    ))}
                  </div>
                  <p className="text-[11px] text-muted-foreground">
                    Extracted deterministically from registration metadata. Zero external network calls.
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="success" className="text-[10px]">
                  Fast / Local In-Memory
                </Badge>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={selectAllAcademic}
                  className="text-[11px] h-7 px-2"
                >
                  Select All
                </Button>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {academicSignals.map((signal) => {
                const isSelected = selectedSignals.includes(signal.key);
                return (
                  <Card
                    key={signal.key}
                    onClick={() => toggleSignal(signal.key)}
                    className={cn(
                      'cursor-pointer transition-all border',
                      isSelected
                        ? 'border-forest-600 bg-forest-50/40 shadow-sm ring-1 ring-forest-500/20'
                        : 'border-border/80 hover:border-forest-300 hover:bg-muted/20'
                    )}
                  >
                    <CardHeader className="p-3.5 space-y-1.5">
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => toggleSignal(signal.key)}
                            onClick={(e) => e.stopPropagation()}
                            className="h-4 w-4 rounded text-forest-700 focus:ring-forest-600 border-border"
                          />
                          <CardTitle className="text-xs font-semibold">
                            {signal.name}
                          </CardTitle>
                        </div>
                        {signal.isRecommended && (
                          <Badge variant="forest" className="text-[9px] px-1 py-0 font-mono">
                            Recommended
                          </Badge>
                        )}
                      </div>
                      <CardDescription className="text-[11px] leading-relaxed">
                        {signal.description}
                      </CardDescription>
                      <code className="text-[10px] font-mono text-muted-foreground block pt-1">
                        {signal.key}
                      </code>
                    </CardHeader>
                  </Card>
                );
              })}
            </div>
          </div>

          {/* GitHub Technical Signals Section */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="h-6 w-6 rounded bg-muted flex items-center justify-center text-foreground">
                  <Github className="h-3.5 w-3.5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h4 className="text-sm font-semibold text-foreground">
                      GitHub Technical & Activity Signals
                    </h4>
                    {mappedGithubCols.map(([orig, tgt]) => (
                      <Badge key={orig} variant="forest" className="text-[9px] font-mono py-0">
                        Mapped: "{orig}" → {tgt}
                      </Badge>
                    ))}
                  </div>
                  <p className="text-[11px] text-muted-foreground">
                    Optional candidate developer metrics gathered via GitHub API.
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="warning" className="text-[10px]">
                  External API / Rate-Limited
                </Badge>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={selectAllGithub}
                  className="text-[11px] h-7 px-2"
                >
                  Select All
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={clearGithub}
                  className="text-[11px] h-7 px-2 text-muted-foreground"
                >
                  Clear
                </Button>
              </div>
            </div>

            {/* GitHub Info Alert */}
            <div className="flex items-start gap-2.5 p-3 rounded-lg border border-amber-200/80 bg-amber-50/50 text-amber-900 text-xs">
              <Info className="h-4 w-4 text-amber-700 shrink-0 mt-0.5" />
              <p className="leading-relaxed text-[11px]">
                <strong>Notice:</strong> When GitHub signals are selected, the analyzer connects to the GitHub API. If you exceed unauthenticated GitHub rate limits, the pipeline automatically falls back to graceful degradation without crashing.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {githubSignals.map((signal) => {
                const isSelected = selectedSignals.includes(signal.key);
                return (
                  <Card
                    key={signal.key}
                    onClick={() => toggleSignal(signal.key)}
                    className={cn(
                      'cursor-pointer transition-all border',
                      isSelected
                        ? 'border-forest-600 bg-forest-50/40 shadow-sm ring-1 ring-forest-500/20'
                        : 'border-border/80 hover:border-forest-300 hover:bg-muted/20'
                    )}
                  >
                    <CardHeader className="p-3.5 space-y-1.5">
                      <div className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleSignal(signal.key)}
                          onClick={(e) => e.stopPropagation()}
                          className="h-4 w-4 rounded text-forest-700 focus:ring-forest-600 border-border"
                        />
                        <CardTitle className="text-xs font-semibold">
                          {signal.name}
                        </CardTitle>
                      </div>
                      <CardDescription className="text-[11px] leading-relaxed">
                        {signal.description}
                      </CardDescription>
                      <code className="text-[10px] font-mono text-muted-foreground block pt-1">
                        {signal.key}
                      </code>
                    </CardHeader>
                  </Card>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* MODE 2: REUSE EXISTING EXTRACTION RUN */}
      {signalMode === 'reuse' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-xs text-muted-foreground">
              Select an earlier extraction run executed against this dataset to reuse its pre-computed signals.
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => refetchRuns()}
              disabled={isLoadingRuns}
              className="text-xs h-7 gap-1"
            >
              Refresh Runs
            </Button>
          </div>

          {isLoadingRuns ? (
            <div className="space-y-2">
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
            </div>
          ) : isRunsError ? (
            <div className="p-4 rounded-lg border border-destructive/30 bg-destructive/5 text-destructive text-xs">
              Failed to load existing extraction runs for this dataset.
            </div>
          ) : !existingRuns || existingRuns.length === 0 ? (
            <div className="text-center py-8 px-4 rounded-lg border border-dashed border-border bg-card">
              <Cpu className="h-8 w-8 text-muted-foreground/60 mx-auto mb-2" />
              <h4 className="text-xs font-semibold text-foreground">No Recorded Extraction Runs</h4>
              <p className="text-[11px] text-muted-foreground max-w-sm mx-auto mt-1 mb-3">
                No signals have been extracted for dataset{' '}
                <strong className="text-foreground">{selectedDataset.filename}</strong> yet.
              </p>
              <Button
                size="sm"
                variant="outline"
                onClick={() => onSignalModeChange('configure')}
                className="gap-1.5 text-xs"
              >
                <Sparkles className="h-3.5 w-3.5 text-forest-700" />
                Configure Signals Now
              </Button>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-2.5">
              {existingRuns.map((run) => {
                const isSelected = selectedExtractionRun?.run_id === run.run_id;
                return (
                  <Card
                    key={run.run_id}
                    onClick={() => onSelectExtractionRun(run)}
                    className={cn(
                      'cursor-pointer transition-all border',
                      isSelected
                        ? 'border-forest-600 bg-forest-50/50 shadow-sm ring-1 ring-forest-500/20'
                        : 'border-border hover:border-forest-300 hover:bg-muted/30'
                    )}
                  >
                    <CardHeader className="p-3.5">
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2.5">
                          <input
                            type="radio"
                            name="extractionRunRadio"
                            checked={isSelected}
                            onChange={() => onSelectExtractionRun(run)}
                            className="h-4 w-4 text-forest-700 focus:ring-forest-600 border-border"
                          />
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="font-mono text-xs font-semibold text-foreground">
                                <TruncatedId id={run.run_id} />
                              </span>
                              <Badge variant="outline" className="text-[10px]">
                                {run.total_teams} teams · {run.total_members} members
                              </Badge>
                            </div>
                            <span className="text-[11px] text-muted-foreground">
                              Executed: {formatDate(run.created_at)}
                            </span>
                          </div>
                        </div>

                        {isSelected && (
                          <Badge variant="forest" className="gap-1 text-[10px]">
                            <CheckCircle2 className="h-3 w-3" />
                            Selected
                          </Badge>
                        )}
                      </div>

                      {run.selected_signals && run.selected_signals.length > 0 && (
                        <div className="flex flex-wrap gap-1 pt-2 pl-6">
                          {run.selected_signals.map((sig) => (
                            <code
                              key={sig}
                              className="text-[9px] bg-muted px-1.5 py-0.5 rounded border border-border text-muted-foreground"
                            >
                              {sig}
                            </code>
                          ))}
                        </div>
                      )}
                    </CardHeader>
                  </Card>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Footer Navigation */}
      <div className="flex items-center justify-between border-t border-border pt-4">
        <Button variant="outline" onClick={onBack} className="gap-2">
          <ArrowLeft className="h-4 w-4" />
          Back to Dataset
        </Button>

        <div className="flex items-center gap-3">
          <span className="text-xs text-muted-foreground hidden sm:inline">
            {signalMode === 'reuse'
              ? selectedExtractionRun
                ? 'Extraction run chosen'
                : 'Select an extraction run'
              : `${selectedSignals.length} signal${selectedSignals.length === 1 ? '' : 's'} selected`}
          </span>
          <Button
            onClick={onNext}
            disabled={!isValid}
            className="gap-2 shadow-sm"
          >
            Next: Eligibility Rules
            <ArrowRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
};
