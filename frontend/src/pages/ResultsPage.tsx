import React, { useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import {
  Trophy,
  AlertCircle,
  RotateCw,
  PlusCircle,
  ArrowRight,
  Layers,
  Trash2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';

import { TruncatedId } from '@/components/common/TruncatedId';
import { DeleteConfirmModal } from '@/components/common/DeleteConfirmModal';
import { apiService } from '@/lib/api-services';
import type { RankingRunSummaryItem } from '@/types';
import {
  useRankingRun,
  useEligibilityRun,
  useRecentRankingRuns,
  useRerunRankingMutation,
} from '@/hooks/useResults';
import { ResultsSummaryHeader } from './results/ResultsSummaryHeader';
import { LeaderboardTable } from './results/LeaderboardTable';
import { TeamDetailModal, type UnifiedLeaderboardRow } from './results/TeamDetailModal';

export const ResultsPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const runId = searchParams.get('run_id');

  // Queries
  const {
    data: rankingRun,
    isLoading,
    isError,
    error,
    refetch,
  } = useRankingRun(runId);

  const { data: eligibilityRun } = useEligibilityRun(rankingRun?.eligibility_run_id);
  const { data: recentRuns, isLoading: isLoadingRecent, refetch: refetchRecent } = useRecentRankingRuns(10);

  // Run to delete in history view
  const [runToDelete, setRunToDelete] = useState<RankingRunSummaryItem | null>(null);

  // Stale state tracking (set when reviewer applies a manual eligibility override)
  const [isStale, setIsStale] = useState<boolean>(false);

  // Selected Team for Inspection Modal
  const [inspectedTeam, setInspectedTeam] = useState<UnifiedLeaderboardRow | null>(null);

  // Reranking Mutation
  const rerunRankingMutation = useRerunRankingMutation();

  const handleRerunRanking = async () => {
    if (!rankingRun || !rankingRun.scoring_run_id || !rankingRun.eligibility_run_id) {
      return;
    }

    try {
      const newRun = await rerunRankingMutation.mutateAsync({
        scoringRunId: rankingRun.scoring_run_id,
        eligibilityRunId: rankingRun.eligibility_run_id,
        topX: rankingRun.top_x,
        includeNeedsReview: rankingRun.include_needs_review,
      });

      setIsStale(false);
      navigate(`/results?run_id=${newRun.run_id}`);
    } catch (err) {
      // Error is captured by mutation state
    }
  };

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

  // Case 1: No run_id provided in URL
  if (!runId) {
    return (
      <div className="space-y-6 max-w-5xl mx-auto">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Badge variant="forest" className="font-mono text-xs">
              Leaderboard & Audit
            </Badge>
            <span className="text-xs text-muted-foreground">· Historical Results</span>
          </div>
          <h2 className="text-xl font-bold tracking-tight text-foreground">
            Evaluation Results & Leaderboards
          </h2>
          <p className="text-xs text-muted-foreground max-w-2xl leading-relaxed">
            Select a previous evaluation run from history below, or launch the Evaluation Wizard to generate a new candidate recruitment run.
          </p>
        </div>

        {/* Empty State Card */}
        <div className="text-center py-10 px-4 rounded-xl border border-dashed border-border bg-card">
          <Trophy className="h-10 w-10 text-muted-foreground/60 mx-auto mb-3" />
          <h3 className="text-sm font-semibold text-foreground">No Evaluation Run Selected</h3>
          <p className="text-xs text-muted-foreground max-w-md mx-auto mt-1 mb-5">
            To view detailed team rankings, score breakdowns, and manual overrides, specify a valid ranking run or choose one from recent runs below.
          </p>
          <Button onClick={() => navigate('/evaluate')} className="gap-2 shadow-sm">
            <PlusCircle className="h-4 w-4" />
            Start New Evaluation Wizard
          </Button>
        </div>

        {/* Recent Runs Table */}
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
            <Layers className="h-4 w-4 text-forest-700" />
            Recent Ranking Evaluation Runs
          </h3>

          {isLoadingRecent ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
            </div>
          ) : !recentRuns || recentRuns.length === 0 ? (
            <p className="text-xs text-muted-foreground italic">
              No previous evaluation runs recorded in the database.
            </p>
          ) : (
            <div className="rounded-lg border border-border bg-card overflow-hidden">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-muted/30 border-b border-border text-muted-foreground">
                    <th className="py-2.5 px-3 text-left font-semibold">Run ID</th>
                    <th className="py-2.5 px-3 text-left font-semibold">Evaluated At</th>
                    <th className="py-2.5 px-3 text-right font-semibold">Top-X</th>
                    <th className="py-2.5 px-3 text-right font-semibold">Selected</th>
                    <th className="py-2.5 px-3 text-right font-semibold">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {recentRuns.map((r) => (
                    <tr
                      key={r.run_id}
                      onClick={() => navigate(`/results?run_id=${r.run_id}`)}
                      className="hover:bg-muted/30 cursor-pointer transition-colors"
                    >
                      <td className="py-2.5 px-3 font-mono font-semibold text-foreground">
                        <TruncatedId id={r.run_id} />
                      </td>
                      <td className="py-2.5 px-3 text-muted-foreground">
                        {formatDate(r.evaluated_at)}
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono">{r.top_x}</td>
                      <td className="py-2.5 px-3 text-right font-mono font-bold text-forest-900">
                        {r.selected_teams_count || r.selected || 0}
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        <div className="flex items-center justify-end gap-1" onClick={(e) => e.stopPropagation()}>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7 px-2 text-xs gap-1 text-forest-700 hover:text-forest-900 hover:bg-forest-50"
                            onClick={() => navigate(`/results?run_id=${r.run_id}`)}
                          >
                            View
                            <ArrowRight className="h-3 w-3" />
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                            title={`Delete ranking run ${r.run_id}`}
                            onClick={() => setRunToDelete(r)}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Delete Modal for Recent Runs List */}
        {runToDelete && (
          <DeleteConfirmModal
            open={Boolean(runToDelete)}
            onOpenChange={(isOpen) => {
              if (!isOpen) setRunToDelete(null);
            }}
            itemType="ranking_run"
            itemId={runToDelete.run_id}
            itemTitle={runToDelete.dataset_filename ? `Ranking for ${runToDelete.dataset_filename}` : undefined}
            onDownloadBackup={async () => {
              const { blob, filename } = await apiService.exportRankingRunCsv(runToDelete.run_id);
              const blobUrl = window.URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = blobUrl;
              a.download = filename || `ranking_run_${runToDelete.run_id}.csv`;
              document.body.appendChild(a);
              a.click();
              window.URL.revokeObjectURL(blobUrl);
              document.body.removeChild(a);
            }}
            onSuccess={() => {
              queryClient.removeQueries({ queryKey: ['ranking', 'run', runToDelete.run_id] });
              queryClient.invalidateQueries({ queryKey: ['ranking'] });
              refetchRecent();
              setRunToDelete(null);
            }}
          />
        )}
      </div>
    );
  }

  // Case 2: Loading ranking run
  if (isLoading) {
    return (
      <div className="space-y-6 max-w-6xl mx-auto">
        <div className="space-y-2">
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-8 w-72" />
          <Skeleton className="h-4 w-96" />
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-6 gap-3">
          <Skeleton className="h-20" />
          <Skeleton className="h-20" />
          <Skeleton className="h-20" />
          <Skeleton className="h-20" />
          <Skeleton className="h-20" />
          <Skeleton className="h-20" />
        </div>
        <Skeleton className="h-80 w-full rounded-xl" />
      </div>
    );
  }

  // Case 3: Error fetching ranking run
  if (isError || !rankingRun) {
    return (
      <div className="space-y-6 max-w-2xl mx-auto pt-6">
        <div className="p-6 rounded-xl border border-destructive/30 bg-destructive/5 text-destructive space-y-4 text-center">
          <AlertCircle className="h-10 w-10 mx-auto text-destructive" />
          <div className="space-y-1">
            <h3 className="text-base font-bold text-foreground">
              Unable to Load Ranking Run
            </h3>
            <p className="text-xs text-muted-foreground">
              Run ID &ldquo;{runId}&rdquo; could not be retrieved from the server.
            </p>
            {error && (
              <code className="text-[11px] block bg-muted p-2 rounded text-destructive font-mono mt-2">
                {error.message}
              </code>
            )}
          </div>
          <div className="flex justify-center gap-2 pt-2">
            <Button size="sm" variant="outline" onClick={() => refetch()} className="gap-1.5">
              <RotateCw className="h-3.5 w-3.5" />
              Retry Request
            </Button>
            <Button size="sm" onClick={() => navigate('/results')} className="gap-1.5">
              View All Runs
            </Button>
          </div>
        </div>
      </div>
    );
  }

  // Case 4: Functional Leaderboard View
  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Summary Header & Metrics Grid */}
      <ResultsSummaryHeader
        rankingRun={rankingRun}
        isStale={isStale}
        onRerunRanking={handleRerunRanking}
        isRerunning={rerunRankingMutation.isPending}
      />

      {/* Leaderboard Table with Search, Filter & Sort */}
      <LeaderboardTable
        rankingRun={rankingRun}
        onInspectTeam={(team) => setInspectedTeam(team)}
      />

      {/* Team Details Inspection & Override Modal */}
      <TeamDetailModal
        open={Boolean(inspectedTeam)}
        onOpenChange={(isOpen) => {
          if (!isOpen) setInspectedTeam(null);
        }}
        team={inspectedTeam}
        eligibilityRun={eligibilityRun || null}
        eligibilityRunId={rankingRun.eligibility_run_id}
        onOverrideSuccess={() => {
          setIsStale(true);
        }}
      />
    </div>
  );
};
