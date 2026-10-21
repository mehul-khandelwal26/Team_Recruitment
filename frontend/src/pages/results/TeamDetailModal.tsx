import React, { useState } from 'react';
import {
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  RotateCw,
  History,
  Send,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import {
  Table,
  TableHeader,
  TableRow,
  TableHead,
  TableBody,
  TableCell,
} from '@/components/ui/table';
import { TruncatedId } from '@/components/common/TruncatedId';
import { useApplyOverrideMutation } from '@/hooks/useResults';
import type {
  EligibilityRunResponse,
  RankedTeamResult,
  ExcludedTeamResult,
} from '@/types';
import { cn } from '@/lib/utils';

export interface UnifiedLeaderboardRow {
  team_id: string;
  team_name: string;
  rank: number | null;
  final_score: number | null;
  score_status: string;
  eligibility_status: string | null;
  selection_status: 'SELECTED' | 'NOT_SELECTED' | 'NEEDS_REVIEW' | 'EXCLUDED' | 'UNRESOLVED';
  is_tied: boolean;
  tiebreak_score?: number | null;
  explanation: string;
  reasons?: string[];
  is_shortlisted: boolean;
  rawRanked?: RankedTeamResult;
  rawExcluded?: ExcludedTeamResult;
}

interface TeamDetailModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  team: UnifiedLeaderboardRow | null;
  eligibilityRun: EligibilityRunResponse | null;
  eligibilityRunId?: string | null;
  onOverrideSuccess: () => void;
}

export const TeamDetailModal: React.FC<TeamDetailModalProps> = ({
  open,
  onOpenChange,
  team,
  eligibilityRun,
  eligibilityRunId,
  onOverrideSuccess,
}) => {
  const [activeTab, setActiveTab] = useState<'overview' | 'criteria' | 'rules' | 'override'>(
    'overview'
  );

  // Override Form States
  const [overrideStatus, setOverrideStatus] = useState<'ELIGIBLE' | 'INELIGIBLE' | 'NEEDS_REVIEW'>(
    'ELIGIBLE'
  );
  const [overrideReason, setOverrideReason] = useState<string>('');
  const [reviewerName, setReviewerName] = useState<string>('organizer');
  const [confirmOverride, setConfirmOverride] = useState<boolean>(false);
  const [overrideSuccessMsg, setOverrideSuccessMsg] = useState<string | null>(null);

  const applyOverrideMutation = useApplyOverrideMutation();

  if (!team) return null;

  // Find corresponding team in the eligibility run
  const eligTeam = eligibilityRun?.teams?.find((t) => t.team_id === team.team_id);
  const ruleResults = eligTeam?.rule_results || [];
  const existingOverride = eligTeam?.override;

  const criteriaBreakdowns = team.rawRanked?.criteria_breakdowns || [];

  const handleApplyOverride = async () => {
    if (!eligibilityRunId) {
      return;
    }
    const cleanReason = overrideReason.trim();
    if (!cleanReason) {
      return;
    }

    try {
      await applyOverrideMutation.mutateAsync({
        eligibilityRunId,
        teamId: team.team_id,
        payload: {
          override_status: overrideStatus,
          reason: cleanReason,
          overridden_by: reviewerName.trim() || 'organizer',
        },
      });

      setOverrideSuccessMsg(
        `Manual override committed for team "${team.team_name}". Eligibility status changed to ${overrideStatus}.`
      );
      setConfirmOverride(false);
      onOverrideSuccess();
    } catch (err) {
      // Error is captured by mutation state
    }
  };

  const isReasonValid = overrideReason.trim().length >= 3;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent onClose={() => onOpenChange(false)} className="max-w-3xl">
        <DialogHeader>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pr-8">
            <div>
              <div className="flex items-center gap-2">
                <DialogTitle className="text-base font-bold text-foreground">
                  {team.team_name}
                </DialogTitle>
                <Badge
                  variant={
                    team.selection_status === 'SELECTED'
                      ? 'success'
                      : team.selection_status === 'NEEDS_REVIEW'
                        ? 'warning'
                        : team.selection_status === 'EXCLUDED' || team.selection_status === 'UNRESOLVED'
                          ? 'destructive'
                          : 'secondary'
                  }
                  className="text-[10px] font-medium"
                >
                  {team.selection_status === 'SELECTED'
                    ? 'Shortlisted'
                    : team.selection_status === 'NEEDS_REVIEW'
                      ? 'Pending Review'
                      : team.selection_status === 'NOT_SELECTED'
                        ? 'Below Cutoff'
                        : team.selection_status === 'UNRESOLVED'
                          ? 'Identity Conflict'
                          : 'Disqualified'}
                </Badge>
              </div>
              <DialogDescription className="mt-0.5">
                Team ID: <TruncatedId id={team.team_id} className="text-foreground" />
                {team.rank !== null && ` · Rank: #${team.rank}`}
                {team.final_score !== null && ` · Final Score: ${Number(team.final_score).toFixed(2)}`}
              </DialogDescription>
            </div>

            {/* Quick Metrics */}
            <div className="flex items-center gap-2 text-right">
              {team.final_score !== null ? (
                <div className="px-3 py-1.5 rounded-lg bg-forest-50 border border-forest-200">
                  <span className="text-[10px] text-muted-foreground block uppercase font-bold">
                    Score
                  </span>
                  <span className="font-mono text-base font-bold text-forest-900">
                    {Number(team.final_score).toFixed(2)}
                  </span>
                </div>
              ) : (
                <Badge variant="outline" className="text-xs">
                  No Score
                </Badge>
              )}
            </div>
          </div>

          {/* Sub-Tabs */}
          <div className="flex items-center gap-1 pt-3 border-t border-border/80">
            {[
              { id: 'overview', label: 'Audit Overview' },
              { id: 'criteria', label: `Scoring Criteria (${criteriaBreakdowns.length})` },
              { id: 'rules', label: `Eligibility Rules (${ruleResults.length})` },
              { id: 'override', label: 'Reviewer Override' },
            ].map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => {
                  setActiveTab(tab.id as any);
                  setOverrideSuccessMsg(null);
                }}
                className={cn(
                  'px-3 py-1 text-xs font-semibold rounded-md transition-colors',
                  activeTab === tab.id
                    ? 'bg-muted text-foreground'
                    : 'text-muted-foreground hover:text-foreground'
                )}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </DialogHeader>

        {/* Modal Scrollable Body */}
        <div className="py-4 space-y-4 overflow-y-auto max-h-[55vh] pr-1">
          {/* TAB 1: AUDIT OVERVIEW */}
          {activeTab === 'overview' && (
            <div className="space-y-4">
              {/* Decision Explanation Box */}
              <div className="p-3.5 rounded-lg border border-border bg-muted/20 space-y-1.5 text-xs">
                <span className="font-bold text-foreground block">
                  Evaluation Outcome & Explanation:
                </span>
                <p className="text-muted-foreground leading-relaxed">
                  {team.explanation || 'No detailed narrative explanation recorded.'}
                </p>
                {team.reasons && team.reasons.length > 0 && (
                  <div className="pt-2 border-t border-border/60 space-y-1">
                    <span className="font-bold text-foreground block">Failure Reasons:</span>
                    <ul className="list-disc list-inside text-muted-foreground space-y-0.5">
                      {team.reasons.map((r, idx) => (
                        <li key={idx}>{r}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>

              {/* Status Details Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-xs">
                <div className="p-2.5 rounded-md border border-border bg-card">
                  <span className="text-[10px] text-muted-foreground font-bold block uppercase">
                    Eligibility Status
                  </span>
                  <span className="font-semibold text-foreground mt-0.5 block">
                    {team.eligibility_status || 'UNVERIFIED'}
                  </span>
                </div>
                <div className="p-2.5 rounded-md border border-border bg-card">
                  <span className="text-[10px] text-muted-foreground font-bold block uppercase">
                    Score Status
                  </span>
                  <span className="font-semibold text-foreground mt-0.5 block">
                    {team.score_status || '—'}
                  </span>
                </div>
                <div className="p-2.5 rounded-md border border-border bg-card">
                  <span className="text-[10px] text-muted-foreground font-bold block uppercase">
                    Score Tie
                  </span>
                  <span className="font-semibold text-foreground mt-0.5 block">
                    {team.is_tied ? 'Tied at Score' : 'None'}
                  </span>
                </div>
                <div className="p-2.5 rounded-md border border-border bg-card">
                  <span className="text-[10px] text-muted-foreground font-bold block uppercase">
                    Shortlisted Quota
                  </span>
                  <span className="font-semibold text-foreground mt-0.5 block">
                    {team.is_shortlisted ? 'Yes (Shortlisted)' : 'No'}
                  </span>
                </div>
              </div>

              {/* Existing Override Notice */}
              {existingOverride && (
                <div className="p-3.5 rounded-lg border border-sky-300 bg-sky-50/70 text-sky-950 text-xs space-y-1">
                  <div className="flex items-center gap-2 font-bold text-sky-900">
                    <History className="h-4 w-4 text-sky-700" />
                    Audited Manual Override Applied
                  </div>
                  <p>
                    Status overridden from <strong>{existingOverride.original_status}</strong> to{' '}
                    <strong>{existingOverride.override_status}</strong> by{' '}
                    <em>{existingOverride.overridden_by}</em>.
                  </p>
                  <p className="text-[11px] text-sky-800 italic">
                    Reason: &ldquo;{existingOverride.reason}&rdquo;
                  </p>
                </div>
              )}
            </div>
          )}

          {/* TAB 2: CRITERIA BREAKDOWN */}
          {activeTab === 'criteria' && (
            <div className="space-y-3">
              {team.rawRanked?.weight_renormalized && (
                <div className="p-2.5 rounded-md border border-amber-200 bg-amber-50/60 text-amber-900 text-xs flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 text-amber-700 shrink-0" />
                  <span>
                    Weights were renormalized for this candidate due to missing optional signals.
                  </span>
                </div>
              )}

              {criteriaBreakdowns.length === 0 ? (
                <p className="text-xs text-muted-foreground py-4 text-center">
                  No criteria breakdowns recorded for this candidate.
                </p>
              ) : (
                <div className="rounded-md border border-border overflow-hidden">
                  <Table>
                    <TableHeader>
                      <TableRow className="bg-muted/30 text-xs">
                        <TableHead>Criterion</TableHead>
                        <TableHead className="w-24">Target Signal</TableHead>
                        <TableHead className="text-right w-20">Weight</TableHead>
                        <TableHead className="w-24">Aggregation</TableHead>
                        <TableHead className="text-right w-24">Team Score</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {criteriaBreakdowns.map((crit) => (
                        <TableRow key={crit.criterion_id} className="text-xs">
                          <TableCell className="font-semibold text-foreground">
                            {crit.name}
                          </TableCell>
                          <TableCell className="font-mono text-[10px] text-muted-foreground">
                            {crit.target_signal_key}
                          </TableCell>
                          <TableCell className="text-right font-mono text-[11px]">
                            {crit.configured_weight}
                          </TableCell>
                          <TableCell className="uppercase font-mono text-[10px] text-muted-foreground">
                            {crit.aggregation_method}
                          </TableCell>
                          <TableCell className="text-right font-mono font-bold text-forest-900">
                            {crit.team_criterion_score !== null &&
                            crit.team_criterion_score !== undefined
                              ? Number(crit.team_criterion_score).toFixed(2)
                              : '—'}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </div>
          )}

          {/* TAB 3: ELIGIBILITY RULES */}
          {activeTab === 'rules' && (
            <div className="space-y-3">
              {ruleResults.length === 0 ? (
                <p className="text-xs text-muted-foreground py-4 text-center">
                  No detailed rule evaluator results recorded or eligibility run not linked.
                </p>
              ) : (
                <div className="space-y-2">
                  {ruleResults.map((r) => {
                    const isPass = r.status === 'PASSED';
                    const isReview = r.status === 'NEEDS_REVIEW';
                    return (
                      <div
                        key={r.rule_id}
                        className={cn(
                          'p-3 rounded-lg border text-xs space-y-1',
                          isPass
                            ? 'border-emerald-200 bg-emerald-50/30'
                            : isReview
                              ? 'border-amber-200 bg-amber-50/40'
                              : 'border-destructive/30 bg-destructive/5'
                        )}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-foreground">{r.name}</span>
                            <code className="text-[10px] font-mono text-muted-foreground">
                              {r.rule_type}
                            </code>
                          </div>
                          <div className="flex items-center gap-1.5">
                            <Badge
                              variant={r.severity === 'hard' ? 'destructive' : 'secondary'}
                              className="text-[9px] uppercase font-mono"
                            >
                              {r.severity}
                            </Badge>
                            <Badge
                              variant={isPass ? 'success' : isReview ? 'warning' : 'destructive'}
                              className="text-[10px] font-mono uppercase"
                            >
                              {r.status}
                            </Badge>
                          </div>
                        </div>
                        <p className="text-muted-foreground leading-relaxed text-[11px]">
                          {r.explanation}
                        </p>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* TAB 4: REVIEWER OVERRIDE FORM */}
          {activeTab === 'override' && (
            <div className="space-y-4">
              {!eligibilityRunId ? (
                <div className="p-3 rounded-lg border border-destructive/30 bg-destructive/10 text-destructive text-xs">
                  No upstream eligibility run is associated with this ranking run. Overrides require an eligibility run reference.
                </div>
              ) : (
                <>
                  <div className="space-y-1 text-xs">
                    <span className="font-bold text-foreground block">
                      Manual Eligibility Override
                    </span>
                    <p className="text-muted-foreground leading-relaxed">
                      Apply an organizer override to change this candidate&apos;s eligibility status. The original evaluation record remains immutable, and an auditable override record is stored.
                    </p>
                  </div>

                  {overrideSuccessMsg && (
                    <div className="p-3.5 rounded-lg border border-emerald-300 bg-emerald-50 text-emerald-950 text-xs flex items-center gap-2">
                      <CheckCircle2 className="h-4 w-4 text-emerald-700 shrink-0" />
                      <span>{overrideSuccessMsg}</span>
                    </div>
                  )}

                  {applyOverrideMutation.isError && (
                    <div className="p-3 rounded-lg border border-destructive/30 bg-destructive/10 text-destructive text-xs flex items-center gap-2">
                      <AlertCircle className="h-4 w-4 shrink-0" />
                      <span>{applyOverrideMutation.error?.message || 'Override request failed.'}</span>
                    </div>
                  )}

                  <div className="space-y-3 pt-2">
                    {/* Override Target Status */}
                    <div className="space-y-1.5">
                      <label className="text-xs font-bold text-foreground block">
                        New Eligibility Status
                      </label>
                      <div className="grid grid-cols-3 gap-2">
                        {(['ELIGIBLE', 'NEEDS_REVIEW', 'INELIGIBLE'] as const).map((status) => (
                          <button
                            key={status}
                            type="button"
                            onClick={() => setOverrideStatus(status)}
                            className={cn(
                              'p-2 text-xs font-bold rounded-lg border text-center transition-all',
                              overrideStatus === status
                                ? status === 'ELIGIBLE'
                                  ? 'border-emerald-600 bg-emerald-50 text-emerald-950 ring-1 ring-emerald-500'
                                  : status === 'NEEDS_REVIEW'
                                    ? 'border-amber-600 bg-amber-50 text-amber-950 ring-1 ring-amber-500'
                                    : 'border-destructive bg-destructive/10 text-destructive ring-1 ring-destructive'
                                : 'border-border bg-card text-muted-foreground hover:text-foreground'
                            )}
                          >
                            {status}
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Reason Textarea */}
                    <div className="space-y-1.5">
                      <label className="text-xs font-bold text-foreground block">
                        Justification Reason <span className="text-destructive">*</span>
                      </label>
                      <textarea
                        rows={3}
                        value={overrideReason}
                        onChange={(e) => setOverrideReason(e.target.value)}
                        placeholder="Provide clear reason for manual override (e.g., 'Lead CGPA transcript verified manually by committee')..."
                        className="w-full text-xs rounded-md border border-input bg-card p-2.5 shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
                      />
                      {!isReasonValid && overrideReason.length > 0 && (
                        <p className="text-[11px] text-destructive">
                          Reason is required and must be at least 3 characters.
                        </p>
                      )}
                    </div>

                    {/* Reviewer Identifier */}
                    <div className="space-y-1.5">
                      <label className="text-xs font-bold text-foreground block">
                        Reviewer Identifier
                      </label>
                      <Input
                        value={reviewerName}
                        onChange={(e) => setReviewerName(e.target.value)}
                        placeholder="organizer / committee_chair"
                        className="text-xs h-8"
                      />
                    </div>

                    {/* Confirmation Checkbox */}
                    <div className="flex items-start gap-2 pt-1">
                      <input
                        type="checkbox"
                        id="confirmOverrideCheck"
                        checked={confirmOverride}
                        onChange={(e) => setConfirmOverride(e.target.checked)}
                        className="h-4 w-4 rounded text-forest-700 focus:ring-forest-600 border-border mt-0.5"
                      />
                      <label
                        htmlFor="confirmOverrideCheck"
                        className="text-xs text-muted-foreground cursor-pointer select-none"
                      >
                        I confirm this eligibility override. I acknowledge that the current ranking run will become stale and will require reranking to update the shortlist.
                      </label>
                    </div>

                    {/* Submit Button */}
                    <div className="pt-2 flex justify-end">
                      <Button
                        size="sm"
                        onClick={handleApplyOverride}
                        disabled={
                          !isReasonValid ||
                          !confirmOverride ||
                          applyOverrideMutation.isPending
                        }
                        className="gap-1.5 shadow-sm"
                      >
                        {applyOverrideMutation.isPending ? (
                          <>
                            <RotateCw className="h-3.5 w-3.5 animate-spin" />
                            Submitting Override...
                          </>
                        ) : (
                          <>
                            <Send className="h-3.5 w-3.5" />
                            Apply Eligibility Override
                          </>
                        )}
                      </Button>
                    </div>
                  </div>
                </>
              )}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" size="sm" onClick={() => onOpenChange(false)}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
