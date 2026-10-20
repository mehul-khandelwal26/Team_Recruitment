import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import {
  Trophy,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  Play,
  RotateCw,
  Cpu,
  ShieldCheck,
  Calculator,
  FolderUp,
  ExternalLink,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
  Table,
  TableHeader,
  TableRow,
  TableHead,
  TableBody,
  TableCell,
} from '@/components/ui/table';
import { TruncatedId } from '@/components/common/TruncatedId';
import { apiService } from '@/lib/api-services';
import type {
  DatasetSummary,
  ExtractionRunSummary,
  RuleConfiguration,
  ScoringConfiguration,
  RankingRunResponse,
} from '@/types';
import { cn } from '@/lib/utils';

interface Step5ReviewAndRunProps {
  selectedDataset: DatasetSummary;
  signalMode: 'configure' | 'reuse';
  selectedSignals: string[];
  selectedExtractionRun: ExtractionRunSummary | null;
  selectedRuleConfig: RuleConfiguration;
  selectedScoringConfig: ScoringConfiguration;
  topX: number;
  onTopXChange: (val: number) => void;
  includeNeedsReview: boolean;
  onIncludeNeedsReviewChange: (val: boolean) => void;
  onBack: () => void;
  onReset: () => void;
}

export type PipelineStage = 'signals' | 'eligibility' | 'scoring' | 'ranking';

export const Step5ReviewAndRun: React.FC<Step5ReviewAndRunProps> = ({
  selectedDataset,
  signalMode,
  selectedSignals,
  selectedExtractionRun,
  selectedRuleConfig,
  selectedScoringConfig,
  topX,
  onTopXChange,
  includeNeedsReview,
  onIncludeNeedsReviewChange,
  onBack,
  onReset,
}) => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // Execution States
  const [isExecuting, setIsExecuting] = useState(false);
  const [currentStage, setCurrentStage] = useState<PipelineStage | null>(null);
  const [completedStages, setCompletedStages] = useState<Set<PipelineStage>>(new Set());
  const [pipelineError, setPipelineError] = useState<{
    stage: PipelineStage;
    title: string;
    message: string;
  } | null>(null);

  // Success Results
  const [rankingResult, setRankingResult] = useState<RankingRunResponse | null>(null);

  // Local TopX state for controlled, bug-free typing
  const [localTopX, setLocalTopX] = useState<number | string>(topX);

  useEffect(() => {
    if (topX > 0) {
      setLocalTopX(topX);
    }
  }, [topX]);

  // Pipeline Execution Routine
  const handleExecutePipeline = async () => {
    setIsExecuting(true);
    setPipelineError(null);
    setCompletedStages(new Set());
    setRankingResult(null);

    let extractionRunId: string;
    let eligibilityRunId: string;
    let scoringRunId: string;

    try {
      // 1. SIGNAL EXTRACTION
      setCurrentStage('signals');
      if (signalMode === 'reuse' && selectedExtractionRun) {
        extractionRunId = selectedExtractionRun.run_id;
      } else {
        const extractionRes = await apiService.extractSignals(
          selectedDataset.dataset_id,
          selectedSignals
        );
        extractionRunId = extractionRes.run_id;
      }
      setCompletedStages((prev) => new Set([...prev, 'signals']));

      // 2. ELIGIBILITY EVALUATION
      setCurrentStage('eligibility');
      const eligibilityRes = await apiService.evaluateEligibility(
        selectedDataset.dataset_id,
        extractionRunId,
        selectedRuleConfig.config_id,
        selectedRuleConfig.version
      );
      eligibilityRunId = eligibilityRes.run_id;
      setCompletedStages((prev) => new Set([...prev, 'eligibility']));

      // 3. MULTI-CRITERIA SCORING
      setCurrentStage('scoring');
      const scoringRes = await apiService.evaluateScoring(
        eligibilityRunId,
        selectedScoringConfig.config_id,
        selectedScoringConfig.version
      );
      scoringRunId = scoringRes.run_id;
      setCompletedStages((prev) => new Set([...prev, 'scoring']));

      // 4. TOP-X RANKING & SELECTION
      setCurrentStage('ranking');
      const rankingRes = await apiService.evaluateRanking(
        scoringRunId,
        eligibilityRunId,
        topX,
        includeNeedsReview
      );
      // Seed newly created run into cache & invalidate lists so Results and Dashboard reflect it immediately
      queryClient.setQueryData(['ranking', 'run', rankingRes.run_id], rankingRes);
      queryClient.invalidateQueries({ queryKey: ['ranking'] });
      queryClient.invalidateQueries({ queryKey: ['signals'] });
      queryClient.invalidateQueries({ queryKey: ['wizard', 'extractions'] });

      setCompletedStages((prev) => new Set([...prev, 'ranking']));
      setRankingResult(rankingRes);
      setCurrentStage(null);
    } catch (err: any) {
      const stageName = currentStage || 'signals';
      setPipelineError({
        stage: stageName,
        title: `Error during ${stageName.toUpperCase()} evaluation`,
        message: err.message || 'An unexpected error occurred during pipeline execution.',
      });
    } finally {
      setIsExecuting(false);
    }
  };

  const isTopXValid = Number.isInteger(topX) && topX >= 1;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-4">
        <div>
          <h3 className="text-lg font-bold text-foreground tracking-tight">
            Step 5: Review & Pipeline Execution
          </h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            Review all configured stages, configure Top-X shortlist cutoff, and execute the automated recruitment pipeline.
          </p>
        </div>
      </div>

      {/* PIPELINE SUCCESS STATE */}
      {rankingResult && (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
          <div className="p-5 rounded-xl border border-emerald-300 bg-emerald-50/70 text-emerald-950 space-y-4 shadow-sm">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-full bg-emerald-200/80 flex items-center justify-center text-emerald-900 shrink-0">
                  <CheckCircle2 className="h-6 w-6 stroke-[2.5]" />
                </div>
                <div>
                  <h4 className="text-base font-bold text-emerald-950 tracking-tight">
                    Evaluation Pipeline Completed Successfully!
                  </h4>
                  <div className="flex items-center gap-2 text-xs text-emerald-800 mt-0.5">
                    <span>Ranking Run ID:</span>
                    <TruncatedId id={rankingResult.run_id} className="text-emerald-950 font-bold" />
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  onClick={() => navigate(`/results?run_id=${rankingResult.run_id}`)}
                  className="bg-emerald-800 hover:bg-emerald-900 text-white gap-1.5 shadow-sm"
                >
                  View Full Results & Leaderboard
                  <ExternalLink className="h-3.5 w-3.5" />
                </Button>
                <Button size="sm" variant="outline" onClick={onReset} className="border-emerald-300 bg-white/80">
                  New Evaluation
                </Button>
              </div>
            </div>

            {/* Diagnostic Metrics Cards */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-3 border-t border-emerald-200">
              <div className="p-3 bg-white/80 rounded-lg border border-emerald-200/80">
                <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider block">
                  Shortlisted Teams
                </span>
                <span className="text-xl font-bold font-mono text-emerald-900">
                  {rankingResult.summary?.selected_teams_count || 0}{' '}
                  <span className="text-xs font-normal text-muted-foreground">
                    / {rankingResult.summary?.requested_top_x || topX}
                  </span>
                </span>
              </div>

              <div className="p-3 bg-white/80 rounded-lg border border-emerald-200/80">
                <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider block">
                  Cutoff Score
                </span>
                <span className="text-xl font-bold font-mono text-emerald-900">
                  {rankingResult.summary?.cutoff_score !== null &&
                  rankingResult.summary?.cutoff_score !== undefined
                    ? Number(rankingResult.summary.cutoff_score).toFixed(2)
                    : '—'}
                </span>
              </div>

              <div className="p-3 bg-white/80 rounded-lg border border-emerald-200/80">
                <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider block">
                  Needs Review
                </span>
                <span className="text-xl font-bold font-mono text-amber-900">
                  {rankingResult.summary?.needs_review_count || 0}
                </span>
              </div>

              <div className="p-3 bg-white/80 rounded-lg border border-emerald-200/80">
                <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider block">
                  Excluded
                </span>
                <span className="text-xl font-bold font-mono text-muted-foreground">
                  {rankingResult.summary?.excluded_count || 0}
                </span>
              </div>
            </div>

            {/* Warnings or Boundary Ties */}
            {rankingResult.summary?.shortage !== undefined && rankingResult.summary.shortage > 0 && (
              <div className="flex items-center gap-2 p-2.5 rounded bg-amber-100/80 border border-amber-300 text-amber-900 text-xs">
                <AlertTriangle className="h-4 w-4 shrink-0 text-amber-700" />
                <span>
                  <strong>Shortage Warning:</strong> Only {rankingResult.summary.selected_teams_count} teams qualified for the requested Top-{rankingResult.summary.requested_top_x} shortlist (shortage of {rankingResult.summary.shortage}). Review manual candidates to fill remaining slots.
                </span>
              </div>
            )}

            {rankingResult.summary?.tie_at_cutoff && (
              <div className="flex items-center gap-2 p-2.5 rounded bg-sky-100/80 border border-sky-300 text-sky-900 text-xs">
                <AlertCircle className="h-4 w-4 shrink-0 text-sky-700" />
                <span>
                  <strong>Boundary Tie Detected:</strong> A tie occurred at the cutoff boundary score. The configured tiebreak criterion deterministically resolved rank ordering.
                </span>
              </div>
            )}
          </div>

          {/* Top Shortlisted Teams Preview Table */}
          {rankingResult.selected_teams && rankingResult.selected_teams.length > 0 && (
            <Card className="border-border/80">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <CardTitle className="text-sm font-semibold flex items-center gap-2">
                      <Trophy className="h-4 w-4 text-forest-700" />
                      Top-{rankingResult.selected_teams.length} Shortlisted Candidates
                    </CardTitle>
                    <CardDescription className="text-xs">
                      Candidate teams qualified and selected under the Top-X recruitment quota.
                    </CardDescription>
                  </div>
                  <Badge variant="forest" className="font-mono text-xs">
                    {rankingResult.selected_teams.length} Selected
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="rounded-md border border-border overflow-hidden">
                  <Table>
                    <TableHeader>
                      <TableRow className="bg-muted/30">
                        <TableHead className="w-16 text-center">Rank</TableHead>
                        <TableHead>Team Name & ID</TableHead>
                        <TableHead className="text-right">Final Score</TableHead>
                        <TableHead className="w-28 text-center">Status</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {rankingResult.selected_teams.map((team) => (
                        <TableRow key={team.team_id} className="text-xs">
                          <TableCell className="text-center font-bold font-mono">
                            <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-forest-100 text-forest-900 font-bold text-xs">
                              {team.rank}
                            </span>
                          </TableCell>
                          <TableCell>
                            <div>
                              <span className="font-semibold text-foreground block">
                                {team.team_name}
                              </span>
                              <TruncatedId id={team.team_id} className="text-[11px] text-muted-foreground" />
                            </div>
                          </TableCell>
                          <TableCell className="text-right font-mono font-bold text-forest-900">
                            {team.final_score !== null && team.final_score !== undefined
                              ? Number(team.final_score).toFixed(2)
                              : '—'}
                          </TableCell>
                          <TableCell className="text-center">
                            <Badge variant="success" className="font-mono text-[10px]">
                              {team.selection_status}
                            </Badge>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* PIPELINE CONFIGURATION & EXECUTION (When not completed yet) */}
      {!rankingResult && (
        <div className="space-y-6">
          {/* Review Summary Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Stage 1: Dataset */}
            <Card className="border-border/80">
              <CardHeader className="p-4 pb-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <FolderUp className="h-4 w-4 text-forest-700" />
                    <CardTitle className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                      1. Dataset Snapshot
                    </CardTitle>
                  </div>
                  <Badge variant="outline" className="font-mono text-[10px] uppercase">
                    {selectedDataset.file_type}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="p-4 pt-1 space-y-1 text-xs">
                <p className="font-semibold text-foreground truncate">{selectedDataset.filename}</p>
                <div className="flex items-center gap-2 text-muted-foreground text-[11px]">
                  <span>ID: <TruncatedId id={selectedDataset.dataset_id} /></span>
                  <span>·</span>
                  <span>{selectedDataset.teams_count} teams</span>
                  <span>·</span>
                  <span>{selectedDataset.members_count} members</span>
                </div>
              </CardContent>
            </Card>

            {/* Stage 2: Signals */}
            <Card className="border-border/80">
              <CardHeader className="p-4 pb-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Cpu className="h-4 w-4 text-forest-700" />
                    <CardTitle className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                      2. Signal Extraction
                    </CardTitle>
                  </div>
                  <Badge variant="secondary" className="text-[10px]">
                    {signalMode === 'reuse' ? 'Reusing Run' : `${selectedSignals.length} Signals`}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="p-4 pt-1 text-xs">
                {signalMode === 'reuse' && selectedExtractionRun ? (
                  <div className="space-y-1">
                    <span className="text-muted-foreground">Existing Run ID:</span>
                    <TruncatedId id={selectedExtractionRun.run_id} className="block font-semibold" />
                  </div>
                ) : (
                  <div className="flex flex-wrap gap-1">
                    {selectedSignals.map((sig) => (
                      <code
                        key={sig}
                        className="text-[10px] bg-muted px-1.5 py-0.5 rounded border border-border text-foreground font-mono"
                      >
                        {sig}
                      </code>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Stage 3: Eligibility Rules */}
            <Card className="border-border/80">
              <CardHeader className="p-4 pb-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <ShieldCheck className="h-4 w-4 text-forest-700" />
                    <CardTitle className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                      3. Eligibility Configuration
                    </CardTitle>
                  </div>
                  <Badge variant="outline" className="font-mono text-[10px]">
                    v{selectedRuleConfig.version}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="p-4 pt-1 space-y-1 text-xs">
                <p className="font-semibold text-foreground">{selectedRuleConfig.name}</p>
                <div className="flex items-center gap-2 text-muted-foreground text-[11px]">
                  <span>ID: <code className="font-mono">{selectedRuleConfig.config_id}</code></span>
                  <span>·</span>
                  <span>{selectedRuleConfig.rules?.length || 0} active rules</span>
                </div>
              </CardContent>
            </Card>

            {/* Stage 4: Scoring Model */}
            <Card className="border-border/80">
              <CardHeader className="p-4 pb-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Calculator className="h-4 w-4 text-forest-700" />
                    <CardTitle className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                      4. Scoring Configuration
                    </CardTitle>
                  </div>
                  <Badge variant="outline" className="font-mono text-[10px]">
                    Scale: {selectedScoringConfig.scale_max} pts
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="p-4 pt-1 space-y-1 text-xs">
                <p className="font-semibold text-foreground">{selectedScoringConfig.name}</p>
                <div className="flex items-center gap-2 text-muted-foreground text-[11px]">
                  <span>ID: <code className="font-mono">{selectedScoringConfig.config_id}</code></span>
                  <span>·</span>
                  <span>{selectedScoringConfig.criteria?.length || 0} weighted criteria</span>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Execution Settings Form */}
          <Card className="border-border/80 bg-card">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <Trophy className="h-4 w-4 text-forest-700" />
                Top-X Selection Settings
              </CardTitle>
              <CardDescription className="text-xs">
                Configure candidate shortlist quota and manual review participation policies.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* Top-X Cutoff input */}
                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-foreground block">
                    Shortlist Cutoff (Top-X Teams) <span className="text-destructive">*</span>
                  </label>
                  <Input
                    type="number"
                    min={1}
                    max={500}
                    value={localTopX}
                    disabled={isExecuting}
                    onChange={(e) => {
                      const raw = e.target.value;
                      if (raw === '') {
                        setLocalTopX('');
                        onTopXChange(0);
                        return;
                      }
                      const clean = raw.replace(/^0+(?=\d)/, '');
                      if (clean !== raw) {
                        e.target.value = clean;
                      }
                      setLocalTopX(clean);
                      const parsed = parseInt(clean, 10);
                      onTopXChange(isNaN(parsed) ? 0 : parsed);
                    }}
                    onBlur={() => {
                      if (localTopX === '' || Number(localTopX) < 1) {
                        setLocalTopX(5);
                        onTopXChange(5);
                      } else {
                        const clamped = Math.min(500, Math.max(1, Math.round(Number(localTopX))));
                        setLocalTopX(clamped);
                        onTopXChange(clamped);
                      }
                    }}
                    className={cn(
                      'font-mono text-sm h-9',
                      !isTopXValid && 'border-destructive focus-visible:ring-destructive'
                    )}
                  />
                  {!isTopXValid ? (
                    <p className="text-[11px] text-destructive font-medium">
                      Top-X must be a positive integer greater than or equal to 1.
                    </p>
                  ) : (
                    <p className="text-[11px] text-muted-foreground">
                      Mandatory positive integer specifying number of top teams to shortlist. Default: 5.
                    </p>
                  )}
                </div>

                {/* Include Needs Review checkbox */}
                <div className="space-y-1.5 pt-1">
                  <label className="text-xs font-bold text-foreground block">
                    Review Status Participation
                  </label>
                  <div className="flex items-start gap-2.5 p-2.5 rounded-md border border-border bg-muted/20">
                    <input
                      type="checkbox"
                      id="includeNeedsReview"
                      checked={includeNeedsReview}
                      disabled={isExecuting}
                      onChange={(e) => onIncludeNeedsReviewChange(e.target.checked)}
                      className="h-4 w-4 rounded text-forest-700 focus:ring-forest-600 border-border mt-0.5"
                    />
                    <label htmlFor="includeNeedsReview" className="text-xs leading-normal cursor-pointer select-none">
                      <span className="font-semibold text-foreground block">
                        Include NEEDS_REVIEW teams in selection
                      </span>
                      <span className="text-[11px] text-muted-foreground block mt-0.5">
                        When enabled, candidates requiring manual review compete directly for Top-X slots. Default: disabled (reserved for organizer review).
                      </span>
                    </label>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Pipeline Error Banner */}
          {pipelineError && (
            <div className="p-4 rounded-lg border border-destructive/30 bg-destructive/10 text-destructive text-xs space-y-2">
              <div className="flex items-center gap-2 font-bold text-sm">
                <AlertCircle className="h-4 w-4" />
                {pipelineError.title}
              </div>
              <p className="leading-relaxed font-mono bg-white/60 p-2.5 rounded border border-destructive/20 text-[11px]">
                {pipelineError.message}
              </p>
              <div className="flex justify-end pt-1">
                <Button size="sm" variant="outline" onClick={handleExecutePipeline} className="gap-1.5">
                  <RotateCw className="h-3.5 w-3.5" />
                  Retry Pipeline Execution
                </Button>
              </div>
            </div>
          )}

          {/* Live Pipeline Execution Progress */}
          {isExecuting && (
            <div className="p-4 rounded-lg border border-forest-200 bg-forest-50/50 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-forest-950 flex items-center gap-2">
                  <RotateCw className="h-3.5 w-3.5 animate-spin text-forest-800" />
                  Executing Evaluation Pipeline...
                </span>
                <span className="text-[11px] text-muted-foreground font-mono">
                  {completedStages.size} / 4 stages complete
                </span>
              </div>

              {/* Sequential Steps Tracker */}
              <div className="space-y-2">
                {[
                  {
                    stage: 'signals' as PipelineStage,
                    label: signalMode === 'reuse' ? 'Linking Pre-extracted Signals' : 'Extracting Selected Signals (POST /api/signals/extract)',
                  },
                  {
                    stage: 'eligibility' as PipelineStage,
                    label: 'Evaluating Eligibility Rules (POST /api/rules/evaluate)',
                  },
                  {
                    stage: 'scoring' as PipelineStage,
                    label: 'Calculating Multi-Criteria Scores (POST /api/scoring/evaluate)',
                  },
                  {
                    stage: 'ranking' as PipelineStage,
                    label: 'Executing Top-X Ranking & Selection (POST /api/ranking/evaluate)',
                  },
                ].map((s) => {
                  const isDone = completedStages.has(s.stage);
                  const isCurrent = currentStage === s.stage;

                  return (
                    <div
                      key={s.stage}
                      className={cn(
                        'flex items-center gap-2.5 p-2 rounded text-xs transition-colors',
                        isDone && 'bg-emerald-100/70 text-emerald-950 font-medium',
                        isCurrent && 'bg-forest-100 text-forest-950 font-bold animate-pulse',
                        !isDone && !isCurrent && 'text-muted-foreground opacity-60'
                      )}
                    >
                      {isDone ? (
                        <CheckCircle2 className="h-4 w-4 text-emerald-700 shrink-0 stroke-[2.5]" />
                      ) : isCurrent ? (
                        <RotateCw className="h-4 w-4 text-forest-800 animate-spin shrink-0" />
                      ) : (
                        <div className="h-4 w-4 rounded-full border border-border shrink-0" />
                      )}
                      <span className="truncate">{s.label}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Action Trigger */}
          <div className="p-4 rounded-xl border border-forest-600/30 bg-gradient-to-r from-forest-50/60 to-forest-50/20 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="space-y-0.5">
              <span className="text-sm font-bold text-foreground">
                Ready to Initiate Evaluation Pipeline
              </span>
              <p className="text-xs text-muted-foreground">
                Orchestrates signal extraction, eligibility checks, scoring, and ranking sequentially via the backend ID-only flow.
              </p>
            </div>

            <Button
              size="lg"
              onClick={handleExecutePipeline}
              disabled={isExecuting || !isTopXValid}
              className="bg-forest-800 hover:bg-forest-900 text-white gap-2 font-semibold shadow-md shrink-0"
            >
              {isExecuting ? (
                <>
                  <RotateCw className="h-4 w-4 animate-spin" />
                  Running Pipeline...
                </>
              ) : (
                <>
                  <Play className="h-4 w-4 fill-current" />
                  Start Evaluation Pipeline
                </>
              )}
            </Button>
          </div>
        </div>
      )}

      {/* Footer Navigation */}
      {!rankingResult && (
        <div className="flex items-center justify-between border-t border-border pt-4">
          <Button
            variant="outline"
            onClick={onBack}
            disabled={isExecuting}
            className="gap-2"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Scoring Model
          </Button>

          <span className="text-xs text-muted-foreground">
            Pipeline parameters are validated. Click &quot;Start Evaluation Pipeline&quot; above.
          </span>
        </div>
      )}
    </div>
  );
};
