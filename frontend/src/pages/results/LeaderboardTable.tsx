import React, { useState, useMemo } from 'react';
import {
  Search,
  ArrowUpDown,
  Eye,
  Filter,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
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
import type { RankingRunResponse } from '@/types';
import type { UnifiedLeaderboardRow } from './TeamDetailModal';
import { cn } from '@/lib/utils';

interface LeaderboardTableProps {
  rankingRun: RankingRunResponse;
  onInspectTeam: (team: UnifiedLeaderboardRow) => void;
}

type SortOption = 'rank_asc' | 'score_desc' | 'score_asc' | 'name_asc';
type FilterStatus = 'ALL' | 'SELECTED' | 'NEEDS_REVIEW' | 'NOT_SELECTED' | 'EXCLUDED';

export const LeaderboardTable: React.FC<LeaderboardTableProps> = ({
  rankingRun,
  onInspectTeam,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<FilterStatus>('ALL');
  const [sortBy, setSortBy] = useState<SortOption>('rank_asc');

  // Build unified list of teams from all sections of RankingRunResponse
  const allRows: UnifiedLeaderboardRow[] = useMemo(() => {
    const rows: UnifiedLeaderboardRow[] = [];
    const seenTeamIds = new Set<string>();
    const selectedIds = new Set((rankingRun.selected_teams || []).map((t) => t.team_id));

    // 1. Ranked teams (includes selected + below cutoff)
    for (const t of rankingRun.ranked_teams || []) {
      if (!seenTeamIds.has(t.team_id)) {
        seenTeamIds.add(t.team_id);
        const isShortlisted = selectedIds.has(t.team_id);
        rows.push({
          team_id: t.team_id,
          team_name: t.team_name,
          rank: t.rank,
          final_score: t.final_score,
          score_status: t.score_status,
          eligibility_status: t.eligibility_status || null,
          selection_status: isShortlisted ? 'SELECTED' : t.selection_status,
          is_tied: t.is_tied,
          tiebreak_score: t.tiebreak_score,
          explanation: t.explanation,
          is_shortlisted: isShortlisted,
          rawRanked: t,
        });
      }
    }

    // 2. Needs review candidates (if not already added in ranked_teams)
    for (const t of rankingRun.needs_review_teams || []) {
      if (!seenTeamIds.has(t.team_id)) {
        seenTeamIds.add(t.team_id);
        rows.push({
          team_id: t.team_id,
          team_name: t.team_name,
          rank: t.rank || null,
          final_score: t.final_score,
          score_status: t.score_status,
          eligibility_status: t.eligibility_status || 'NEEDS_REVIEW',
          selection_status: 'NEEDS_REVIEW',
          is_tied: t.is_tied,
          tiebreak_score: t.tiebreak_score,
          explanation: t.explanation,
          is_shortlisted: false,
          rawRanked: t,
        });
      }
    }

    // 3. Excluded teams
    for (const t of rankingRun.excluded_teams || []) {
      if (!seenTeamIds.has(t.team_id)) {
        seenTeamIds.add(t.team_id);
        const isUnresolved = t.reason_code === 'UNRESOLVED';
        rows.push({
          team_id: t.team_id,
          team_name: t.team_name,
          rank: null,
          final_score: t.final_score !== undefined && t.final_score !== null ? t.final_score : null,
          score_status: t.score_status || 'DISQUALIFIED',
          eligibility_status: t.eligibility_status || (t.reason_code === 'INELIGIBLE' ? 'INELIGIBLE' : null),
          selection_status: isUnresolved ? 'UNRESOLVED' : 'EXCLUDED',
          is_tied: false,
          explanation: t.explanation,
          reasons: t.eligibility_reasons,
          is_shortlisted: false,
          rawExcluded: t,
        });
      }
    }

    // 4. Unresolved teams
    for (const t of rankingRun.unresolved_teams || []) {
      if (!seenTeamIds.has(t.team_id)) {
        seenTeamIds.add(t.team_id);
        rows.push({
          team_id: t.team_id,
          team_name: t.team_name,
          rank: null,
          final_score: t.final_score !== undefined && t.final_score !== null ? t.final_score : null,
          score_status: t.score_status || 'DISQUALIFIED',
          eligibility_status: t.eligibility_status || (t.reason_code === 'NEEDS_REVIEW' ? 'NEEDS_REVIEW' : null),
          selection_status: 'UNRESOLVED',
          is_tied: false,
          explanation: t.explanation,
          reasons: t.eligibility_reasons,
          is_shortlisted: false,
          rawExcluded: t,
        });
      }
    }

    return rows;
  }, [rankingRun]);

  // Counts for filter pills
  const counts = useMemo(() => {
    return {
      all: allRows.length,
      selected: allRows.filter((r) => r.selection_status === 'SELECTED').length,
      needs_review: allRows.filter((r) => r.selection_status === 'NEEDS_REVIEW').length,
      not_selected: allRows.filter((r) => r.selection_status === 'NOT_SELECTED').length,
      excluded: allRows.filter((r) => r.selection_status === 'EXCLUDED' || r.selection_status === 'UNRESOLVED').length,
    };
  }, [allRows]);

  // Filter and sort rows
  const filteredAndSortedRows = useMemo(() => {
    let result = allRows;

    // Filter by search query
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      result = result.filter(
        (r) =>
          r.team_name.toLowerCase().includes(q) ||
          r.team_id.toLowerCase().includes(q)
      );
    }

    // Filter by status tab
    if (statusFilter !== 'ALL') {
      if (statusFilter === 'EXCLUDED') {
        result = result.filter(
          (r) => r.selection_status === 'EXCLUDED' || r.selection_status === 'UNRESOLVED'
        );
      } else {
        result = result.filter((r) => r.selection_status === statusFilter);
      }
    }

    // Sorting
    return [...result].sort((a, b) => {
      if (sortBy === 'rank_asc') {
        // Unranked placed at end
        if (a.rank === null && b.rank === null) return a.team_name.localeCompare(b.team_name);
        if (a.rank === null) return 1;
        if (b.rank === null) return -1;
        return a.rank - b.rank;
      }
      if (sortBy === 'score_desc') {
        if (a.final_score === null && b.final_score === null) return 0;
        if (a.final_score === null) return 1;
        if (b.final_score === null) return -1;
        return b.final_score - a.final_score;
      }
      if (sortBy === 'score_asc') {
        if (a.final_score === null && b.final_score === null) return 0;
        if (a.final_score === null) return 1;
        if (b.final_score === null) return -1;
        return a.final_score - b.final_score;
      }
      if (sortBy === 'name_asc') {
        return a.team_name.localeCompare(b.team_name);
      }
      return 0;
    });
  }, [allRows, searchQuery, statusFilter, sortBy]);

  const isCustomSort = sortBy !== 'rank_asc';

  return (
    <div className="space-y-4">
      {/* Controls Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
        {/* Search Input */}
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            placeholder="Search teams by name or ID..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-8 text-xs h-9 bg-card"
          />
        </div>

        {/* Filter Tabs */}
        <div className="inline-flex items-center gap-1 p-1 rounded-lg bg-secondary/60 border border-border/70 overflow-x-auto max-w-full">
          {[
            { id: 'ALL', label: 'All Candidates', count: counts.all },
            { id: 'SELECTED', label: 'Shortlisted', count: counts.selected },
            { id: 'NEEDS_REVIEW', label: 'Needs Review', count: counts.needs_review },
            { id: 'NOT_SELECTED', label: 'Below Cutoff', count: counts.not_selected },
            { id: 'EXCLUDED', label: 'Disqualified', count: counts.excluded },
          ].map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setStatusFilter(tab.id as FilterStatus)}
              className={cn(
                'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all cursor-pointer whitespace-nowrap',
                statusFilter === tab.id
                  ? 'bg-card text-foreground shadow-xs font-bold'
                  : 'text-muted-foreground hover:text-foreground hover:bg-card/50'
              )}
            >
              <span>{tab.label}</span>
              <span
                className={cn(
                  'font-mono text-[10px] px-1.5 py-0.2 rounded-full',
                  statusFilter === tab.id
                    ? 'bg-forest-50 text-forest-800 border border-forest-200/60 font-semibold'
                    : 'bg-muted text-muted-foreground'
                )}
              >
                {tab.count}
              </span>
            </button>
          ))}
        </div>

        {/* Sort Dropdown */}
        <div className="flex items-center gap-2 self-start md:self-auto">
          <ArrowUpDown className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as SortOption)}
            className="text-xs h-9 rounded-md border border-input bg-card px-2.5 shadow-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          >
            <option value="rank_asc">Canonical Rank (1 to N)</option>
            <option value="score_desc">Score: Highest First</option>
            <option value="score_asc">Score: Lowest First</option>
            <option value="name_asc">Team Name (A to Z)</option>
          </select>
        </div>
      </div>

      {/* Sorting Notice (when not rank_asc) */}
      {isCustomSort && (
        <div className="p-2.5 rounded-md border border-border bg-muted/20 text-muted-foreground text-xs flex items-center justify-between">
          <span className="flex items-center gap-1.5 text-[11px]">
            <Filter className="h-3.5 w-3.5 text-forest-700" />
            Showing client-sorted order. The official backend ranking position is preserved in the Rank column.
          </span>
          <button
            type="button"
            onClick={() => setSortBy('rank_asc')}
            className="text-forest-700 font-semibold underline text-[11px] hover:text-forest-900"
          >
            Reset to Canonical Rank
          </button>
        </div>
      )}

      {/* Table Container */}
      <div className="rounded-xl border border-border bg-card overflow-hidden shadow-sm">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/30 text-xs">
              <TableHead className="w-16 text-center">Rank</TableHead>
              <TableHead>Team Name & ID</TableHead>
              <TableHead className="text-right w-28">Final Score</TableHead>
              <TableHead className="w-32 text-center">Eligibility</TableHead>
              <TableHead className="w-32 text-center">Selection Status</TableHead>
              <TableHead className="w-28 text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredAndSortedRows.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center py-10 text-muted-foreground text-xs">
                  {searchQuery
                    ? `No candidates found matching "${searchQuery}".`
                    : 'No candidates in this status filter.'}
                </TableCell>
              </TableRow>
            ) : (
              filteredAndSortedRows.map((row) => {
                const isSelected = row.selection_status === 'SELECTED';
                const isReview = row.selection_status === 'NEEDS_REVIEW';
                const isExcluded = row.selection_status === 'EXCLUDED' || row.selection_status === 'UNRESOLVED';

                return (
                  <TableRow
                    key={row.team_id}
                    onClick={() => onInspectTeam(row)}
                    className={cn(
                      'cursor-pointer transition-colors text-xs',
                      isSelected
                        ? 'bg-forest-50/40 hover:bg-forest-50/70'
                        : isReview
                          ? 'bg-amber-50/30 hover:bg-amber-50/50'
                          : isExcluded
                            ? 'bg-muted/10 hover:bg-muted/20 opacity-80'
                            : 'hover:bg-muted/30'
                    )}
                  >
                    {/* Rank */}
                    <TableCell className="text-center font-mono">
                      {row.rank !== null ? (
                        row.rank === 1 ? (
                          <span className="inline-flex h-6.5 w-6.5 items-center justify-center rounded-full bg-amber-100 text-amber-950 border border-amber-300 font-bold text-xs shadow-2xs" title="Rank #1">
                            1
                          </span>
                        ) : row.rank === 2 ? (
                          <span className="inline-flex h-6.5 w-6.5 items-center justify-center rounded-full bg-slate-200 text-slate-900 border border-slate-300 font-bold text-xs shadow-2xs" title="Rank #2">
                            2
                          </span>
                        ) : row.rank === 3 ? (
                          <span className="inline-flex h-6.5 w-6.5 items-center justify-center rounded-full bg-amber-50 text-amber-900 border border-amber-200 font-bold text-xs shadow-2xs" title="Rank #3">
                            3
                          </span>
                        ) : (
                          <span
                            className={cn(
                              'inline-flex h-6 w-6 items-center justify-center rounded-full font-semibold text-xs',
                              isSelected
                                ? 'bg-forest-800 text-white shadow-2xs'
                                : 'bg-muted text-muted-foreground'
                            )}
                          >
                            {row.rank}
                          </span>
                        )
                      ) : (
                        <span className="text-muted-foreground font-mono">—</span>
                      )}
                    </TableCell>

                    {/* Team Name & ID */}
                    <TableCell>
                      <div className="space-y-0.5">
                        <div className="flex items-center gap-1.5">
                          <span className="font-semibold text-foreground">{row.team_name}</span>
                          {row.is_tied && (
                            <Badge variant="outline" className="text-[9px] px-1 py-0 font-mono text-muted-foreground">
                              Tied
                            </Badge>
                          )}
                        </div>
                        <div className="text-[11px] text-muted-foreground flex items-center gap-1">
                          <span>ID:</span>
                          <TruncatedId id={row.team_id} />
                        </div>
                      </div>
                    </TableCell>

                    {/* Final Score */}
                    <TableCell className="text-right">
                      {row.final_score !== null ? (
                        <div className="flex flex-col items-end">
                          <span
                            className={cn(
                              'font-mono font-bold text-sm',
                              isSelected
                                ? 'text-forest-950 font-bold'
                                : isReview
                                  ? 'text-amber-900'
                                  : 'text-foreground'
                            )}
                          >
                            {Number(row.final_score).toFixed(2)}
                          </span>
                          <div className="w-16 h-1.5 bg-muted rounded-full overflow-hidden mt-1 border border-border/40">
                            <div
                              className={cn(
                                'h-full rounded-full transition-all',
                                isSelected ? 'bg-forest-600' : 'bg-muted-foreground/40'
                              )}
                              style={{ width: `${Math.min(100, Math.max(0, Number(row.final_score)))}%` }}
                            />
                          </div>
                        </div>
                      ) : (
                        <span className="text-muted-foreground font-normal text-[11px]">No Score</span>
                      )}
                    </TableCell>

                    {/* Eligibility Status */}
                    <TableCell className="text-center">
                      {row.eligibility_status === 'ELIGIBLE' ? (
                        <Badge variant="success" className="text-[10px] font-medium">Eligible</Badge>
                      ) : row.eligibility_status === 'NEEDS_REVIEW' ? (
                        <Badge variant="warning" className="text-[10px] font-medium">Pending Review</Badge>
                      ) : row.eligibility_status === 'INELIGIBLE' ? (
                        <Badge variant="destructive" className="text-[10px] font-medium">Ineligible</Badge>
                      ) : (
                        <Badge variant="outline" className="text-[10px] font-medium">Unverified</Badge>
                      )}
                    </TableCell>

                    {/* Selection Status */}
                    <TableCell className="text-center">
                      {isSelected ? (
                        <Badge variant="forest" className="text-[10px] font-medium">
                          Shortlisted
                        </Badge>
                      ) : isReview ? (
                        <Badge variant="warning" className="text-[10px] font-medium">
                          Pending Review
                        </Badge>
                      ) : row.selection_status === 'NOT_SELECTED' ? (
                        <Badge variant="secondary" className="text-[10px] font-medium text-muted-foreground">
                          Below Cutoff
                        </Badge>
                      ) : row.selection_status === 'UNRESOLVED' ? (
                        <Badge variant="outline" className="text-[10px] font-medium border-purple-200 text-purple-700 bg-purple-50">
                          Identity Conflict
                        </Badge>
                      ) : (
                        <Badge variant="destructive" className="text-[10px] font-medium">
                          Disqualified
                        </Badge>
                      )}
                    </TableCell>

                    {/* Action Button */}
                    <TableCell className="text-right">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={(e) => {
                          e.stopPropagation();
                          onInspectTeam(row);
                        }}
                        className="h-7 px-2 text-xs gap-1 text-forest-700 hover:text-forest-900 hover:bg-forest-50"
                      >
                        <Eye className="h-3.5 w-3.5" />
                        Inspect
                      </Button>
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
};
