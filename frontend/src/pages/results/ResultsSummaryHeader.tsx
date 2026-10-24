import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import {
  Trophy,
  Download,
  RotateCw,
  AlertTriangle,
  AlertCircle,
  PlusCircle,
  Calendar,
  History,
  Trash2,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { TruncatedId } from '@/components/common/TruncatedId';
import { DeleteConfirmModal } from '@/components/common/DeleteConfirmModal';
import { apiService } from '@/lib/api-services';
import type { RankingRunResponse } from '@/types';

interface ResultsSummaryHeaderProps {
  rankingRun: RankingRunResponse;
  isStale: boolean;
  onRerunRanking: () => void;
  isRerunning?: boolean;
}

export const ResultsSummaryHeader: React.FC<ResultsSummaryHeaderProps> = ({
  rankingRun,
  isStale,
  onRerunRanking,
  isRerunning = false,
}) => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [isExporting, setIsExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [showDeleteModal, setShowDeleteModal] = useState(false);

  const handleExportCsv = async () => {
    setIsExporting(true);
    setExportError(null);
    try {
      const { blob, filename } = await apiService.exportRankingRunCsv(rankingRun.run_id);
      const blobUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = filename || `ranking_run_${rankingRun.run_id}.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(blobUrl);
      document.body.removeChild(a);
    } catch (err: any) {
      setExportError(err.message || 'Failed to download CSV export from server.');
    } finally {
      setIsExporting(false);
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

  const summary = rankingRun.summary;

  return (
    <div className="space-y-4">
      {/* Top Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Badge variant="forest" className="font-mono text-xs">
              Shortlist Leaderboard
            </Badge>
            <span className="text-xs text-muted-foreground flex items-center gap-1">
              <Calendar className="h-3 w-3" />
              {formatDate(rankingRun.evaluated_at)}
            </span>
          </div>
          <h2 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <Trophy className="h-5 w-5 text-forest-700" />
            Recruitment Ranking & Shortlist Leaderboard
          </h2>
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground pt-1">
            <span className="inline-flex items-center gap-1.5 font-mono bg-muted/80 px-2 py-0.5 rounded border border-border/70 text-foreground font-semibold">
              <span className="font-sans font-medium text-muted-foreground text-[11px]">Run:</span>
              <TruncatedId id={rankingRun.run_id} />
            </span>
            {rankingRun.eligibility_run_id && (
              <span className="inline-flex items-center gap-1 font-mono bg-muted/50 px-2 py-0.5 rounded border border-border/60 text-muted-foreground">
                <span className="font-sans font-medium text-[11px]">Eligibility:</span>
                <TruncatedId id={rankingRun.eligibility_run_id} />
              </span>
            )}
            {rankingRun.scoring_run_id && (
              <span className="inline-flex items-center gap-1 font-mono bg-muted/50 px-2 py-0.5 rounded border border-border/60 text-muted-foreground">
                <span className="font-sans font-medium text-[11px]">Scoring:</span>
                <TruncatedId id={rankingRun.scoring_run_id} />
              </span>
            )}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigate('/results')}
            className="text-xs gap-1.5 shadow-sm"
            title="Browse all historical ranking evaluation runs"
          >
            <History className="h-3.5 w-3.5 text-forest-700" />
            All Runs
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={handleExportCsv}
            disabled={isExporting}
            className="text-xs gap-1.5 shadow-sm"
          >
            {isExporting ? (
              <>
                <RotateCw className="h-3.5 w-3.5 animate-spin" />
                Exporting CSV...
              </>
            ) : (
              <>
                <Download className="h-3.5 w-3.5 text-forest-700" />
                Export CSV
              </>
            )}
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={() => navigate('/evaluate')}
            className="text-xs gap-1.5 shadow-sm"
          >
            <PlusCircle className="h-3.5 w-3.5 text-forest-700" />
            New Evaluation
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowDeleteModal(true)}
            className="text-xs gap-1.5 shadow-sm text-muted-foreground hover:text-destructive hover:border-destructive/30 hover:bg-destructive/10"
            title="Delete this ranking run"
          >
            <Trash2 className="h-3.5 w-3.5" />
            Delete Run
          </Button>
        </div>
      </div>

      {/* Delete Run Confirmation Modal */}
      {showDeleteModal && (
        <DeleteConfirmModal
          open={showDeleteModal}
          onOpenChange={setShowDeleteModal}
          itemType="ranking_run"
          itemId={rankingRun.run_id}
          itemTitle={`Ranking Shortlist (${rankingRun.summary?.selected_teams_count || 0} selected)`}
          onDownloadBackup={handleExportCsv}
          onSuccess={() => {
            // Evict single run cache immediately & invalidate all ranking lists
            queryClient.removeQueries({ queryKey: ['ranking', 'run', rankingRun.run_id] });
            queryClient.invalidateQueries({ queryKey: ['ranking'] });
            navigate('/results');
          }}
        />
      )}

      {/* Export Error Alert */}
      {exportError && (
        <div className="p-3 rounded-lg border border-destructive/30 bg-destructive/10 text-destructive text-xs flex items-center gap-2">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{exportError}</span>
        </div>
      )}

      {/* Stale Ranking Warning Banner (When manual override was performed) */}
      {isStale && (
        <div className="p-4 rounded-xl border border-amber-300 bg-amber-50/80 text-amber-950 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-sm animate-in fade-in">
          <div className="flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 text-amber-700 shrink-0 mt-0.5" />
            <div className="space-y-0.5">
              <span className="font-bold text-sm block">
                Upstream Eligibility Changed — Current Ranking is Stale
              </span>
              <p className="text-amber-900 leading-relaxed">
                A reviewer manual override was recorded for an upstream team. The leaderboard below reflects the previous ranking snapshot. Rerun ranking to calculate the updated Top-X shortlist.
              </p>
            </div>
          </div>
          <Button
            size="sm"
            onClick={onRerunRanking}
            disabled={isRerunning}
            className="bg-amber-800 hover:bg-amber-900 text-white shrink-0 gap-1.5 shadow-sm font-semibold"
          >
            <RotateCw className={`h-3.5 w-3.5 ${isRerunning ? 'animate-spin' : ''}`} />
            {isRerunning ? 'Rerunning Ranking...' : 'Rerun Ranking with Overrides'}
          </Button>
        </div>
      )}

      {/* Summary Metrics Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {/* Total Evaluated */}
        <div className="p-3.5 bg-card rounded-xl border border-border/80 shadow-2xs space-y-1">
          <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider block">
            Evaluated
          </span>
          <span className="text-xl font-bold font-mono text-foreground block">
            {summary?.total_teams_evaluated || 0}
          </span>
          <span className="text-[10px] text-muted-foreground block truncate">
            {summary?.qualifying_teams_count || 0} qualifying
          </span>
        </div>

        {/* Selected / Shortlist */}
        <div className="p-3.5 bg-forest-50/50 rounded-xl border border-forest-200/80 shadow-2xs space-y-1">
          <span className="text-[10px] font-bold text-forest-900 uppercase tracking-wider block">
            Shortlisted (Top-X)
          </span>
          <span className="text-xl font-bold font-mono text-forest-950 block">
            {summary?.selected_teams_count || 0}{' '}
            <span className="text-xs font-normal text-muted-foreground">
              / {summary?.requested_top_x || rankingRun.top_x}
            </span>
          </span>
          <span className="text-[10px] text-forest-800 font-semibold block truncate">
            {summary?.shortage && summary.shortage > 0
              ? `Shortage of ${summary.shortage}`
              : 'Quota satisfied'}
          </span>
        </div>

        {/* Cutoff Score */}
        <div className="p-3.5 bg-card rounded-xl border border-border/80 shadow-2xs space-y-1">
          <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider block">
            Cutoff Score
          </span>
          <span className="text-xl font-bold font-mono text-foreground block">
            {summary?.cutoff_score !== null && summary?.cutoff_score !== undefined
              ? Number(summary.cutoff_score).toFixed(2)
              : '—'}
          </span>
          <span className="text-[10px] text-muted-foreground block truncate">
            {summary?.tie_at_cutoff ? 'Tie at cutoff boundary' : 'Clean cutoff boundary'}
          </span>
        </div>

        {/* Needs Review */}
        <div className="p-3.5 bg-card rounded-xl border border-border/80 shadow-2xs space-y-1">
          <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider block">
            Needs Review
          </span>
          <span className="text-xl font-bold font-mono text-amber-800 block">
            {summary?.needs_review_count || 0}
          </span>
          <span className="text-[10px] text-muted-foreground block truncate">
            {summary?.needs_review_count && summary.needs_review_count > 0
              ? 'Organizer action required'
              : 'All reviews clear'}
          </span>
        </div>

        {/* Excluded */}
        <div className="p-3.5 bg-card rounded-xl border border-border/80 shadow-2xs space-y-1">
          <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider block">
            Disqualified
          </span>
          <span className="text-xl font-bold font-mono text-muted-foreground block">
            {summary?.excluded_count || 0}
          </span>
          <span className="text-[10px] text-muted-foreground block truncate">
            {summary?.excluded_count && summary.excluded_count > 0
              ? 'Did not meet criteria'
              : 'Zero disqualified'}
          </span>
        </div>

        {/* Unresolved */}
        <div className="p-3.5 bg-card rounded-xl border border-border/80 shadow-2xs space-y-1">
          <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider block">
            Identity Conflicts
          </span>
          <span className="text-xl font-bold font-mono text-muted-foreground block">
            {summary?.unresolved_count || 0}
          </span>
          <span className="text-[10px] text-muted-foreground block truncate">
            {summary?.unresolved_count && summary.unresolved_count > 0
              ? 'Profile resolution required'
              : 'No identity conflicts'}
          </span>
        </div>
      </div>

      {/* Shortage Advisory Banner */}
      {(summary?.shortage ?? 0) > 0 &&
        (rankingRun.recommended_review_candidates?.length ?? 0) > 0 && (
          <div className="p-4 rounded-xl border border-amber-300 bg-amber-50/70 text-amber-950 space-y-2.5 shadow-2xs">
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-amber-700 shrink-0" />
                <span className="font-bold text-xs">
                  Shortlist Shortage Advisory ({summary?.shortage} unfulfilled slot{summary?.shortage === 1 ? '' : 's'}):
                </span>
              </div>
              <Badge variant="warning" className="text-[10px] font-mono">
                Action Required
              </Badge>
            </div>
            <p className="text-xs text-amber-900 leading-relaxed">
              Only <strong>{summary?.selected_teams_count || 0}</strong> of the requested{' '}
              <strong>{rankingRun.top_x}</strong> teams qualified automatically. Below are top-scoring candidates pending manual review that can fulfill remaining slots:
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2 pt-1">
              {(rankingRun.recommended_review_candidates || []).map((cand) => (
                <div
                  key={cand.team_id}
                  className="p-2.5 rounded-lg border border-amber-200 bg-white/90 text-xs flex items-center justify-between"
                >
                  <div className="min-w-0 pr-2">
                    <span className="font-bold text-foreground block truncate">{cand.team_name}</span>
                    <span className="text-[10px] text-muted-foreground font-mono">
                      ID: <TruncatedId id={cand.team_id} />
                    </span>
                  </div>
                  <div className="text-right shrink-0">
                    <span className="font-mono font-bold text-forest-900 text-xs block">
                      {cand.final_score !== null && cand.final_score !== undefined
                        ? Number(cand.final_score).toFixed(2)
                        : '—'} pts
                    </span>
                    <Badge variant="warning" className="text-[9px] px-1 py-0 uppercase font-mono">
                      Needs Review
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
    </div>
  );
};
