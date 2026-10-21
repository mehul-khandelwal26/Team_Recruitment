import React from 'react';
import { Link } from 'react-router-dom';
import {
  FolderPlus,
  PlayCircle,
  SlidersHorizontal,
  ArrowRight,
  ShieldCheck,
  FileSpreadsheet,
  AlertCircle,
  RefreshCw,
  Cpu,
  Trophy,
  Database,
  CheckCircle2,
  AlertTriangle,
  Trash2,
} from 'lucide-react';
import { DeleteConfirmModal } from '@/components/common/DeleteConfirmModal';
import { apiService } from '@/lib/api-services';
import type { DatasetSummary, ExtractionRunSummary, RankingRunSummaryItem } from '@/types';
import {
  useDatasetSummaries,
  useExtractionRunSummaries,
  useRankingRunSummaries,
} from '@/hooks/useDashboard';
import { formatDateTime } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { TruncatedId } from '@/components/common/TruncatedId';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table';

export const DashboardPage: React.FC = () => {
  // TanStack Query hooks fetching lightweight summary list endpoints
  const datasetsQuery = useDatasetSummaries(10);
  const extractionsQuery = useExtractionRunSummaries(10);
  const rankingsQuery = useRankingRunSummaries(10);

  const datasets = datasetsQuery.data || [];
  const extractions = extractionsQuery.data || [];
  const rankingRuns = rankingsQuery.data || [];

  const [datasetToDelete, setDatasetToDelete] = React.useState<DatasetSummary | null>(null);
  const [rankingRunToDelete, setRankingRunToDelete] = React.useState<RankingRunSummaryItem | null>(null);
  const [extractionToDelete, setExtractionToDelete] = React.useState<ExtractionRunSummary | null>(null);

  return (
    <div className="space-y-8">
      {/* Top Banner / Welcome */}
      <div className="rounded-lg border border-border bg-card p-6 shadow-xs">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-bold tracking-tight text-foreground">
                Recruitment Automation Workspace
              </h2>
            </div>
            <p className="text-sm text-muted-foreground leading-relaxed max-w-2xl">
              Deterministic, explainable candidate shortlisting engine for hackathons and academic recruitment.
              Configured with 10 eligibility rule evaluators, multi-criteria weighted scoring, and tie-protected Top-X ranking.
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Button asChild variant="default" className="gap-2">
              <Link to="/evaluate">
                <PlayCircle className="h-4 w-4" />
                Start Evaluation
              </Link>
            </Button>
            <Button asChild variant="outline" className="gap-2">
              <Link to="/configurations">
                <SlidersHorizontal className="h-4 w-4" />
                View Presets
              </Link>
            </Button>
          </div>
        </div>
      </div>

      {/* Section A: Overview Metrics Cards */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-foreground uppercase tracking-wider">
              Summary Overview
            </h3>
            <p className="text-xs text-muted-foreground">
              Overview of active candidate datasets, signal extractions, and evaluated ranking shortlists.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Datasets Count Card */}
          <Card className="border-border">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-muted-foreground">
                  Recent Datasets Loaded
                </span>
                <Database className="h-4 w-4 text-forest-700" />
              </div>
            </CardHeader>
            <CardContent>
              {datasetsQuery.isLoading ? (
                <Skeleton className="h-8 w-16 my-1" />
              ) : datasetsQuery.isError ? (
                <div className="flex items-center gap-2 text-destructive text-sm font-medium">
                  <AlertCircle className="h-4 w-4" />
                  <span>Failed to load</span>
                </div>
              ) : (
                <div className="flex items-baseline justify-between">
                  <span className="text-2xl font-bold font-mono tracking-tight text-foreground">
                    {datasets.length}
                  </span>
                </div>
              )}
              <p className="text-xs text-muted-foreground mt-1">
                Candidate registrations ready for pipeline evaluation
              </p>
            </CardContent>
          </Card>

          {/* Extraction Runs Count Card */}
          <Card className="border-border">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-muted-foreground">
                  Recent Extractions Loaded
                </span>
                <Cpu className="h-4 w-4 text-forest-700" />
              </div>
            </CardHeader>
            <CardContent>
              {extractionsQuery.isLoading ? (
                <Skeleton className="h-8 w-16 my-1" />
              ) : extractionsQuery.isError ? (
                <div className="flex items-center gap-2 text-destructive text-sm font-medium">
                  <AlertCircle className="h-4 w-4" />
                  <span>Failed to load</span>
                </div>
              ) : (
                <div className="flex items-baseline justify-between">
                  <span className="text-2xl font-bold font-mono tracking-tight text-foreground">
                    {extractions.length}
                  </span>
                </div>
              )}
              <p className="text-xs text-muted-foreground mt-1">
                GitHub, academic, & technical signal extraction runs
              </p>
            </CardContent>
          </Card>

          {/* Ranking Runs Count Card */}
          <Card className="border-border">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-muted-foreground">
                  Recent Ranking Runs Loaded
                </span>
                <Trophy className="h-4 w-4 text-forest-700" />
              </div>
            </CardHeader>
            <CardContent>
              {rankingsQuery.isLoading ? (
                <Skeleton className="h-8 w-16 my-1" />
              ) : rankingsQuery.isError ? (
                <div className="flex items-center gap-2 text-destructive text-sm font-medium">
                  <AlertCircle className="h-4 w-4" />
                  <span>Failed to load</span>
                </div>
              ) : (
                <div className="flex items-baseline justify-between">
                  <span className="text-2xl font-bold font-mono tracking-tight text-foreground">
                    {rankingRuns.length}
                  </span>
                </div>
              )}
              <p className="text-xs text-muted-foreground mt-1">
                Top-X shortlists evaluated with tie-break cutoffs
              </p>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Quick Action Navigation Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="hover:border-forest-600/40 transition-colors">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div className="flex h-9 w-9 items-center justify-center rounded-md bg-forest-50 text-forest-800 border border-forest-200">
                <FolderPlus className="h-4 w-4" />
              </div>
              <Badge variant="outline" className="text-[10px]">Step 1</Badge>
            </div>
            <CardTitle className="text-base mt-2">Registration Ingestion</CardTitle>
            <CardDescription>
              Upload CSV or JSON registration forms with automatic schema discovery and missing ID generation.
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-0">
            <Button asChild variant="link" className="p-0 h-auto text-xs font-semibold gap-1 text-forest-800">
              <Link to="/evaluate">
                Launch Evaluation Flow <ArrowRight className="h-3 w-3" />
              </Link>
            </Button>
          </CardContent>
        </Card>

        <Card className="hover:border-forest-600/40 transition-colors">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div className="flex h-9 w-9 items-center justify-center rounded-md bg-amber-50 text-amber-800 border border-amber-200">
                <ShieldCheck className="h-4 w-4" />
              </div>
              <Badge variant="outline" className="text-[10px]">Built-in</Badge>
            </div>
            <CardTitle className="text-base mt-2">Rule Presets & Overrides</CardTitle>
            <CardDescription>
              Inspect 4 built-in rule presets including the seeded Demo: Lead Academic Review and audit logs.
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-0">
            <Button asChild variant="link" className="p-0 h-auto text-xs font-semibold gap-1 text-forest-800">
              <Link to="/configurations">
                Explore Configurations <ArrowRight className="h-3 w-3" />
              </Link>
            </Button>
          </CardContent>
        </Card>

        <Card className="hover:border-forest-600/40 transition-colors">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div className="flex h-9 w-9 items-center justify-center rounded-md bg-sky-50 text-sky-800 border border-sky-200">
                <FileSpreadsheet className="h-4 w-4" />
              </div>
              <Badge variant="outline" className="text-[10px]">Shortlists</Badge>
            </div>
            <CardTitle className="text-base mt-2">Top-X Leaderboard & CSV</CardTitle>
            <CardDescription>
              View shortlisted teams, cutoff boundaries, score breakdowns, and download formula-safe CSV exports.
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-0">
            <Button asChild variant="link" className="p-0 h-auto text-xs font-semibold gap-1 text-forest-800">
              <Link to="/results">
                View Shortlist Viewer <ArrowRight className="h-3 w-3" />
              </Link>
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Section B: Recent Datasets */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <h3 className="text-base font-semibold text-foreground tracking-tight flex items-center gap-2">
              <Database className="h-4 w-4 text-forest-700" />
              Recent Datasets
            </h3>
            <p className="text-xs text-muted-foreground">
              Candidate registration datasets uploaded to backend storage
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => datasetsQuery.refetch()}
              disabled={datasetsQuery.isFetching}
              className="h-8 gap-1.5 text-xs"
              title="Refresh datasets"
            >
              <RefreshCw className={datasetsQuery.isFetching ? 'h-3.5 w-3.5 animate-spin' : 'h-3.5 w-3.5'} />
              <span>Refresh</span>
            </Button>
          </div>
        </div>

        {/* Datasets Error State */}
        {datasetsQuery.isError && (
          <div className="flex items-center justify-between rounded-md border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
            <div className="flex items-center gap-2.5">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <div>
                <p className="font-medium text-xs">Failed to load dataset summaries</p>
                <p className="text-[11px] text-muted-foreground mt-0.5">
                  {datasetsQuery.error?.message || 'Check network connection or backend status'}
                </p>
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => datasetsQuery.refetch()}
              className="h-7 text-xs gap-1 border-destructive/30 text-destructive hover:bg-destructive/10"
            >
              Retry
            </Button>
          </div>
        )}

        {/* Datasets Loading State */}
        {datasetsQuery.isLoading && (
          <div className="rounded-md border border-border bg-card p-4 space-y-3">
            <Skeleton className="h-5 w-48" />
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          </div>
        )}

        {/* Datasets Empty State */}
        {!datasetsQuery.isLoading && !datasetsQuery.isError && datasets.length === 0 && (
          <div className="rounded-lg border border-dashed border-border bg-card p-8 text-center">
            <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-secondary text-muted-foreground mb-3">
              <FileSpreadsheet className="h-5 w-5 text-muted-foreground" />
            </div>
            <h4 className="text-sm font-medium text-foreground mb-1">
              No Datasets Uploaded Yet
            </h4>
            <p className="text-xs text-muted-foreground max-w-sm mx-auto mb-4">
              Upload candidate CSV or JSON registration rosters to begin signal extraction and shortlist evaluations.
            </p>
            <Button asChild variant="default" size="sm" className="gap-2">
              <Link to="/evaluate?tab=upload">
                <FolderPlus className="h-3.5 w-3.5" />
                Upload First Dataset
              </Link>
            </Button>
          </div>
        )}

        {/* Datasets Table */}
        {!datasetsQuery.isLoading && !datasetsQuery.isError && datasets.length > 0 && (
          <div className="rounded-md border border-border bg-card overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[180px]">Dataset ID</TableHead>
                  <TableHead>Filename</TableHead>
                  <TableHead className="w-[100px]">Format</TableHead>
                  <TableHead className="w-[100px] text-right">Teams</TableHead>
                  <TableHead className="w-[100px] text-right">Members</TableHead>
                  <TableHead className="w-[140px]">Warnings</TableHead>
                  <TableHead className="w-[190px]">Uploaded At</TableHead>
                  <TableHead className="w-[120px] text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {datasets.map((ds) => (
                  <TableRow key={ds.dataset_id}>
                    <TableCell>
                      <TruncatedId id={ds.dataset_id} />
                    </TableCell>
                    <TableCell className="font-medium text-xs text-foreground max-w-[240px] truncate" title={ds.filename}>
                      {ds.filename}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className="text-[10px] uppercase font-mono">
                        {ds.file_type}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs font-mono text-right">{ds.teams_count}</TableCell>
                    <TableCell className="text-xs font-mono text-right">{ds.members_count}</TableCell>
                    <TableCell>
                      {ds.warnings_count > 0 ? (
                        <Badge variant="warning" className="text-[10px] gap-1">
                          <AlertTriangle className="h-2.5 w-2.5" />
                          {ds.warnings_count} {ds.warnings_count === 1 ? 'warning' : 'warnings'}
                        </Badge>
                      ) : (
                        <Badge variant="success" className="text-[10px] gap-1">
                          <CheckCircle2 className="h-2.5 w-2.5" />
                          Clean
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                      {formatDateTime(ds.uploaded_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Button asChild size="sm" variant="ghost" className="h-7 px-2 text-xs gap-1 text-forest-700 hover:text-forest-900 hover:bg-forest-50">
                          <Link to={`/evaluate?dataset_id=${ds.dataset_id}`}>
                            Evaluate <ArrowRight className="h-3 w-3" />
                          </Link>
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                          title={`Delete dataset ${ds.filename}`}
                          onClick={() => setDatasetToDelete(ds)}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>

      {/* Section C: Recent Ranking Runs */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <h3 className="text-base font-semibold text-foreground tracking-tight flex items-center gap-2">
              <Trophy className="h-4 w-4 text-forest-700" />
              Recent Ranking Runs
            </h3>
            <p className="text-xs text-muted-foreground">
              Top-X candidate selections, cutoff diagnostics, and review shortages
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => rankingsQuery.refetch()}
              disabled={rankingsQuery.isFetching}
              className="h-8 gap-1.5 text-xs"
              title="Refresh ranking runs"
            >
              <RefreshCw className={rankingsQuery.isFetching ? 'h-3.5 w-3.5 animate-spin' : 'h-3.5 w-3.5'} />
              <span>Refresh</span>
            </Button>
          </div>
        </div>

        {/* Ranking Runs Error State */}
        {rankingsQuery.isError && (
          <div className="flex items-center justify-between rounded-md border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
            <div className="flex items-center gap-2.5">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <div>
                <p className="font-medium text-xs">Failed to load ranking run summaries</p>
                <p className="text-[11px] text-muted-foreground mt-0.5">
                  {rankingsQuery.error?.message || 'Check network connection or backend status'}
                </p>
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => rankingsQuery.refetch()}
              className="h-7 text-xs gap-1 border-destructive/30 text-destructive hover:bg-destructive/10"
            >
              Retry
            </Button>
          </div>
        )}

        {/* Ranking Runs Loading State */}
        {rankingsQuery.isLoading && (
          <div className="rounded-md border border-border bg-card p-4 space-y-3">
            <Skeleton className="h-5 w-48" />
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          </div>
        )}

        {/* Ranking Runs Empty State */}
        {!rankingsQuery.isLoading && !rankingsQuery.isError && rankingRuns.length === 0 && (
          <div className="rounded-lg border border-dashed border-border bg-card p-8 text-center">
            <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-secondary text-muted-foreground mb-3">
              <Trophy className="h-5 w-5 text-muted-foreground" />
            </div>
            <h4 className="text-sm font-medium text-foreground mb-1">
              No Ranking Runs Evaluated Yet
            </h4>
            <p className="text-xs text-muted-foreground max-w-sm mx-auto mb-4">
              Run an evaluation pipeline to compute multi-criteria scores, verify rules, and shortlist Top-X teams.
            </p>
            <Button asChild variant="default" size="sm" className="gap-2">
              <Link to="/evaluate">
                <PlayCircle className="h-3.5 w-3.5" />
                Launch Evaluation
              </Link>
            </Button>
          </div>
        )}

        {/* Ranking Runs Table */}
        {!rankingsQuery.isLoading && !rankingsQuery.isError && rankingRuns.length > 0 && (
          <div className="rounded-md border border-border bg-card overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[180px]">Run ID</TableHead>
                  <TableHead className="w-[190px]">Evaluated At</TableHead>
                  <TableHead>Dataset Source</TableHead>
                  <TableHead className="w-[130px]">Configurations</TableHead>
                  <TableHead className="w-[90px] text-right">Top-X</TableHead>
                  <TableHead className="w-[110px] text-right">Selected</TableHead>
                  <TableHead className="w-[120px] text-right">Needs Review</TableHead>
                  <TableHead className="w-[120px]">Cutoff Status</TableHead>
                  <TableHead className="w-[100px] text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rankingRuns.map((r) => {
                  const selectedCount = r.selected_teams_count ?? r.selected ?? 0;
                  const needsReviewCount = r.needs_review_count ?? r.needs_review ?? 0;
                  return (
                    <TableRow key={r.run_id}>
                      <TableCell>
                        <TruncatedId id={r.run_id} />
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                        {formatDateTime(r.evaluated_at)}
                      </TableCell>
                      <TableCell className="text-xs max-w-[200px] truncate" title={r.dataset_filename || r.dataset_id || '—'}>
                        {r.dataset_filename ? (
                          <span className="font-medium text-foreground">{r.dataset_filename}</span>
                        ) : r.dataset_id ? (
                          <TruncatedId id={r.dataset_id} />
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-col gap-1">
                          <span className="text-[11px] text-muted-foreground truncate" title={`Rules: ${r.eligibility_config_id || 'custom'}`}>
                            Rules: <span className="font-mono text-foreground">{r.eligibility_config_id || 'custom'}</span>
                          </span>
                          <span className="text-[11px] text-muted-foreground truncate" title={`Scoring: ${r.scoring_config_id || 'custom'}`}>
                            Score: <span className="font-mono text-foreground">{r.scoring_config_id || 'custom'}</span>
                          </span>
                        </div>
                      </TableCell>
                      <TableCell className="text-xs font-mono font-medium text-right">
                        {r.top_x}
                      </TableCell>
                      <TableCell className="text-xs font-mono font-semibold text-right text-forest-800">
                        {selectedCount}
                      </TableCell>
                      <TableCell className="text-xs font-mono text-right">
                        {needsReviewCount > 0 ? (
                          <Badge variant="warning" className="text-[10px]">
                            {needsReviewCount}
                          </Badge>
                        ) : (
                          <span className="text-muted-foreground">0</span>
                        )}
                      </TableCell>
                      <TableCell>
                        {r.tie_at_cutoff ? (
                          <Badge variant="warning" className="text-[10px]">
                            Tie at Cutoff
                          </Badge>
                        ) : r.shortage > 0 ? (
                          <Badge variant="outline" className="text-[10px] text-amber-700 border-amber-300">
                            Shortage ({r.shortage})
                          </Badge>
                        ) : (
                          <Badge variant="success" className="text-[10px]">
                            Resolved
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1">
                          <Button asChild size="sm" variant="ghost" className="h-7 px-2 text-xs gap-1 text-forest-700 hover:text-forest-900 hover:bg-forest-50">
                            <Link to={`/results?run_id=${r.run_id}`}>
                              View <ArrowRight className="h-3 w-3" />
                            </Link>
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                            title={`Delete ranking run ${r.run_id}`}
                            onClick={() => setRankingRunToDelete(r)}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        )}
      </div>

      {/* Section D: Recent Extraction Runs */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <h3 className="text-base font-semibold text-foreground tracking-tight flex items-center gap-2">
              <Cpu className="h-4 w-4 text-forest-700" />
              Recent Signal Extraction Runs
            </h3>
            <p className="text-xs text-muted-foreground">
              Candidate attribute analyzers, GitHub metrics, and academic profile extractions
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => extractionsQuery.refetch()}
              disabled={extractionsQuery.isFetching}
              className="h-8 gap-1.5 text-xs"
              title="Refresh extraction runs"
            >
              <RefreshCw className={extractionsQuery.isFetching ? 'h-3.5 w-3.5 animate-spin' : 'h-3.5 w-3.5'} />
              <span>Refresh</span>
            </Button>
          </div>
        </div>

        {/* Extraction Runs Error State */}
        {extractionsQuery.isError && (
          <div className="flex items-center justify-between rounded-md border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
            <div className="flex items-center gap-2.5">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <div>
                <p className="font-medium text-xs">Failed to load extraction run summaries</p>
                <p className="text-[11px] text-muted-foreground mt-0.5">
                  {extractionsQuery.error?.message || 'Check network connection or backend status'}
                </p>
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => extractionsQuery.refetch()}
              className="h-7 text-xs gap-1 border-destructive/30 text-destructive hover:bg-destructive/10"
            >
              Retry
            </Button>
          </div>
        )}

        {/* Extraction Runs Loading State */}
        {extractionsQuery.isLoading && (
          <div className="rounded-md border border-border bg-card p-4 space-y-3">
            <Skeleton className="h-5 w-48" />
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          </div>
        )}

        {/* Extraction Runs Empty State */}
        {!extractionsQuery.isLoading && !extractionsQuery.isError && extractions.length === 0 && (
          <div className="rounded-lg border border-dashed border-border bg-card p-8 text-center">
            <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-secondary text-muted-foreground mb-3">
              <Cpu className="h-5 w-5 text-muted-foreground" />
            </div>
            <h4 className="text-sm font-medium text-foreground mb-1">
              No Signal Extractions Executed Yet
            </h4>
            <p className="text-xs text-muted-foreground max-w-sm mx-auto mb-4">
              Extract candidate signals from uploaded datasets to analyze GitHub activity, academic records, and portfolio links.
            </p>
            <Button asChild variant="default" size="sm" className="gap-2">
              <Link to="/evaluate">
                <PlayCircle className="h-3.5 w-3.5" />
                Run Signal Extraction
              </Link>
            </Button>
          </div>
        )}

        {/* Extraction Runs Table */}
        {!extractionsQuery.isLoading && !extractionsQuery.isError && extractions.length > 0 && (
          <div className="rounded-md border border-border bg-card overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[180px]">Run ID</TableHead>
                  <TableHead className="w-[160px]">Dataset ID</TableHead>
                  <TableHead className="w-[190px]">Created At</TableHead>
                  <TableHead>Selected Signals</TableHead>
                  <TableHead className="w-[90px] text-right">Teams</TableHead>
                  <TableHead className="w-[110px]">Warnings</TableHead>
                  <TableHead className="w-[100px]">Errors</TableHead>
                  <TableHead className="w-[110px] text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {extractions.map((ex) => (
                  <TableRow key={ex.run_id}>
                    <TableCell>
                      <TruncatedId id={ex.run_id} />
                    </TableCell>
                    <TableCell>
                      <TruncatedId id={ex.dataset_id} fallback="None (inline)" />
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                      {formatDateTime(ex.created_at)}
                    </TableCell>
                    <TableCell>
                      {ex.selected_signals && ex.selected_signals.length > 0 ? (
                        <div className="flex flex-wrap gap-1 max-w-[280px]">
                          {ex.selected_signals.slice(0, 3).map((sig) => (
                            <Badge key={sig} variant="secondary" className="font-mono text-[10px] py-0 px-1.5">
                              {sig}
                            </Badge>
                          ))}
                          {ex.selected_signals.length > 3 && (
                            <Badge variant="outline" className="font-mono text-[10px] py-0 px-1.5 text-muted-foreground">
                              +{ex.selected_signals.length - 3} more
                            </Badge>
                          )}
                        </div>
                      ) : (
                        <span className="text-xs text-muted-foreground italic">All signals</span>
                      )}
                    </TableCell>
                    <TableCell className="text-xs font-mono text-right">{ex.total_teams}</TableCell>
                    <TableCell>
                      {ex.warnings_count > 0 ? (
                        <Badge variant="warning" className="text-[10px]">
                          {ex.warnings_count}
                        </Badge>
                      ) : (
                        <span className="text-xs text-muted-foreground font-mono">0</span>
                      )}
                    </TableCell>
                    <TableCell>
                      {ex.errors_count > 0 ? (
                        <Badge variant="destructive" className="text-[10px]">
                          {ex.errors_count}
                        </Badge>
                      ) : (
                        <span className="text-xs text-muted-foreground font-mono">0</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Button asChild size="sm" variant="ghost" className="h-7 px-2 text-xs gap-1 text-forest-700 hover:text-forest-900 hover:bg-forest-50">
                          <Link to={`/evaluate?${ex.dataset_id ? `dataset_id=${ex.dataset_id}&` : ''}extraction_run_id=${ex.run_id}`}>
                            Evaluate <ArrowRight className="h-3 w-3" />
                          </Link>
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                          title={`Delete extraction run ${ex.run_id}`}
                          onClick={() => setExtractionToDelete(ex)}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>

      {/* Dataset Delete Modal */}
      {datasetToDelete && (
        <DeleteConfirmModal
          open={Boolean(datasetToDelete)}
          onOpenChange={(isOpen) => {
            if (!isOpen) setDatasetToDelete(null);
          }}
          itemType="dataset"
          itemId={datasetToDelete.dataset_id}
          itemTitle={datasetToDelete.filename}
          onSuccess={() => {
            datasetsQuery.refetch();
            rankingsQuery.refetch();
            extractionsQuery.refetch();
            setDatasetToDelete(null);
          }}
        />
      )}

      {/* Ranking Run Delete Modal */}
      {rankingRunToDelete && (
        <DeleteConfirmModal
          open={Boolean(rankingRunToDelete)}
          onOpenChange={(isOpen) => {
            if (!isOpen) setRankingRunToDelete(null);
          }}
          itemType="ranking_run"
          itemId={rankingRunToDelete.run_id}
          itemTitle={rankingRunToDelete.dataset_filename ? `Ranking for ${rankingRunToDelete.dataset_filename}` : undefined}
          onDownloadBackup={async () => {
            const { blob, filename } = await apiService.exportRankingRunCsv(rankingRunToDelete.run_id);
            const blobUrl = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = blobUrl;
            a.download = filename || `ranking_run_${rankingRunToDelete.run_id}.csv`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(blobUrl);
            document.body.removeChild(a);
          }}
          onSuccess={() => {
            rankingsQuery.refetch();
            setRankingRunToDelete(null);
          }}
        />
      )}

      {/* Extraction Run Delete Modal */}
      {extractionToDelete && (
        <DeleteConfirmModal
          open={Boolean(extractionToDelete)}
          onOpenChange={(isOpen) => {
            if (!isOpen) setExtractionToDelete(null);
          }}
          itemType="extraction_run"
          itemId={extractionToDelete.run_id}
          itemTitle={`Extraction Run (${extractionToDelete.total_teams} teams)`}
          onSuccess={() => {
            extractionsQuery.refetch();
            rankingsQuery.refetch();
            setExtractionToDelete(null);
          }}
        />
      )}
    </div>
  );
};
