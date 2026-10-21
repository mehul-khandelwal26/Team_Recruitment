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
        {/* Context Header Bar */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border pb-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Badge variant="forest" className="font-mono text-xs">
                Evaluation Archive
              </Badge>
              <span className="text-xs text-muted-foreground">
                Historical candidate shortlists and explainability audit trails
              </span>
            </div>
          </div>
          <Button
            onClick={() => navigate('/evaluate')}
            size="sm"
            className="gap-2 shadow-xs text-xs self-start sm:self-auto"
          >
            <PlusCircle className="h-4 w-4" />
            New Evaluation Run
          </Button>
        </div>

        {/* Recent Runs List or Empty State */}
        {isLoadingRecent ? (
          <div className="space-y-2">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </div>
        ) : !recentRuns || recentRuns.length === 0 ? (
          <div className="text-center py-12 px-4 rounded-xl border border-dashed border-border/80 bg-card/60">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-muted/80 text-muted-foreground mx-auto mb-3">
              <Trophy className="h-6 w-6" />
            </div>
            <h3 className="text-sm font-bold text-foreground">No Evaluation Runs Recorded</h3>
            <p className="text-xs text-muted-foreground max-w-md mx-auto mt-1 mb-5">
              Run the Candidate Evaluation Wizard to ingest candidate datasets, evaluate eligibility criteria, and compute your Top-X shortlisted teams.
            </p>
            <Button onClick={() => navigate('/evaluate')} className="gap-2 shadow-xs text-xs">
              <PlusCircle className="h-4 w-4" />
              Launch Evaluation Flow
            </Button>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-foreground flex items-center gap-2 tracking-tight">
                <Layers className="h-4 w-4 text-forest-700" />
                Recorded Evaluation Runs ({recentRuns.length})
              </h3>
              <span className="text-xs text-muted-foreground font-mono">
                Deterministic Top-X Shortlists
              </span>
            </div>

            <div className="rounded-xl border border-border/80 bg-card overflow-hidden shadow-2xs">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-muted/50 border-b border-border text-muted-foreground font-medium text-[11px]">
                    <th className="py-3 px-4 text-left">Ranking Run ID</th>
                    <th className="py-3 px-4 text-left">Evaluated At</th>
                    <th className="py-3 px-4 text-center">Quota</th>
                    <th className="py-3 px-4 text-center">Shortlisted</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60">
                  {recentRuns.map((r) => (
                    <tr
                      key={r.run_id}
                      onClick={() => navigate(`/results?run_id=${r.run_id}`)}
                      className="hover:bg-muted/20 cursor-pointer transition-colors"
                    >
                      <td className="py-3 px-4 font-mono font-semibold text-foreground">
                        <div className="flex items-center gap-2">
                          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-forest-50 text-forest-800 border border-forest-200/60 shadow-2xs">
                            <Trophy className="h-3.5 w-3.5" />
                          </div>
                          <TruncatedId id={r.run_id} />
                        </div>
                      </td>
                      <td className="py-3 px-4 text-muted-foreground">
                        {formatDate(r.evaluated_at)}
                      </td>
                      <td className="py-3 px-4 text-center">
                        <span className="font-mono text-[11px] bg-muted/80 px-2 py-0.5 rounded border border-border/80 text-foreground font-medium">
                          Top {r.top_x}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-center">
                        <span className="font-mono text-xs font-bold text-forest-800 bg-forest-50 px-2.5 py-0.5 rounded-full border border-forest-200/80">
                          {r.selected_teams_count || r.selected || 0} teams
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right">
                        <div className="flex items-center justify-end gap-1.5" onClick={(e) => e.stopPropagation()}>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7 px-2.5 text-xs gap-1 font-semibold text-forest-800 hover:text-forest-900 hover:bg-forest-50"
                            onClick={() => navigate(`/results?run_id=${r.run_id}`)}
                          >
                            View Leaderboard
                            <ArrowRight className="h-3.5 w-3.5" />
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
          </div>
        )}

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
