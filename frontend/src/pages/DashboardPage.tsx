import React from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  FolderPlus,
  PlayCircle,
  SlidersHorizontal,
  Clock,
  Layers,
  ArrowRight,
  ShieldCheck,
  FileSpreadsheet,
  AlertCircle,
} from 'lucide-react';
import { apiClient } from '@/lib/api-client';
import { formatDateTime } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table';
import type { DatasetSummary, RankingRunSummaryItem } from '@/types';

export const DashboardPage: React.FC = () => {
  // Query lightweight summary list endpoints implemented in Prompt 7.0
  const datasetsQuery = useQuery<DatasetSummary[]>({
    queryKey: ['datasets', 'summaries'],
    queryFn: () => apiClient.get<DatasetSummary[]>('/api/ingestion/datasets', { summary: true, limit: 10 }),
    retry: 1,
  });

  const rankingRunsQuery = useQuery<RankingRunSummaryItem[]>({
    queryKey: ['ranking', 'runs', 'summaries'],
    queryFn: () => apiClient.get<RankingRunSummaryItem[]>('/api/ranking/runs', { summary: true, limit: 10 }),
    retry: 1,
  });

  const datasets = datasetsQuery.data || [];
  const rankingRuns = rankingRunsQuery.data || [];
  const isLoading = datasetsQuery.isLoading || rankingRunsQuery.isLoading;
  const isError = datasetsQuery.isError || rankingRunsQuery.isError;
  const hasHistory = datasets.length > 0 || rankingRuns.length > 0;

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
              <Badge variant="forest" className="font-mono text-[10px]">
                Phase 7 Ready
              </Badge>
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

      {/* Server Connectivity Notice if Backend Offline */}
      {isError && (
        <div className="flex items-start gap-3 rounded-md border border-amber-200 bg-amber-50/70 p-4 text-sm text-amber-900">
          <AlertCircle className="h-5 w-5 shrink-0 text-amber-700 mt-0.5" />
          <div className="space-y-1">
            <p className="font-medium text-amber-950">Backend Connection Diagnostic</p>
            <p className="text-xs text-amber-800 leading-normal">
              Could not reach the FastAPI backend at <code className="font-mono bg-amber-100 px-1 py-0.5 rounded text-amber-950">http://localhost:8000</code>.
              Start the backend with <code className="font-mono bg-amber-100 px-1 py-0.5 rounded text-amber-950">uvicorn app.main:app --reload</code> to view live dataset summaries and evaluation history.
            </p>
          </div>
        </div>
      )}

      {/* Recent Activity / Thoughtful Initial Empty State */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <h3 className="text-base font-semibold text-foreground tracking-tight flex items-center gap-2">
              <Clock className="h-4 w-4 text-muted-foreground" />
              Recent Evaluation Activity
            </h3>
            <p className="text-xs text-muted-foreground">
              Processed candidate datasets and Top-X shortlists stored in backend persistence.
            </p>
          </div>
          {hasHistory && (
            <Badge variant="secondary" className="font-mono text-xs">
              {datasets.length} Datasets · {rankingRuns.length} Runs
            </Badge>
          )}
        </div>

        {/* Empty State Banner (when no datasets exist) */}
        {!hasHistory && !isLoading && (
          <div className="rounded-lg border border-dashed border-border bg-card p-10 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-secondary text-muted-foreground mb-4">
              <Layers className="h-6 w-6 text-muted-foreground" />
            </div>
            <h4 className="text-base font-medium text-foreground mb-1">
              No Evaluation History Recorded Yet
            </h4>
            <p className="text-xs text-muted-foreground max-w-md mx-auto leading-relaxed mb-6">
              Evaluation history, dataset statistics, and ranking runs will appear here once candidate registration data has been uploaded and processed through the evaluation pipeline.
            </p>
            <div className="flex items-center justify-center gap-3">
              <Button asChild variant="default" size="sm" className="gap-2">
                <Link to="/evaluate">
                  <PlayCircle className="h-4 w-4" />
                  Evaluate Sample Dataset
                </Link>
              </Button>
              <Button asChild variant="outline" size="sm" className="gap-2">
                <Link to="/configurations">
                  <SlidersHorizontal className="h-4 w-4" />
                  Inspect Default Presets
                </Link>
              </Button>
            </div>
          </div>
        )}

        {/* Live Datasets Table (when datasets exist) */}
        {datasets.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Uploaded Datasets ({datasets.length})
            </h4>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Dataset ID</TableHead>
                  <TableHead>Filename</TableHead>
                  <TableHead>Format</TableHead>
                  <TableHead>Teams</TableHead>
                  <TableHead>Members</TableHead>
                  <TableHead>Warnings</TableHead>
                  <TableHead>Uploaded At</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {datasets.map((ds) => (
                  <TableRow key={ds.dataset_id}>
                    <TableCell className="font-mono text-xs font-medium text-forest-900">
                      {ds.dataset_id}
                    </TableCell>
                    <TableCell className="font-medium text-xs">{ds.filename}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className="text-[10px] uppercase">
                        {ds.file_type}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs">{ds.teams_count}</TableCell>
                    <TableCell className="text-xs">{ds.members_count}</TableCell>
                    <TableCell>
                      {ds.warnings_count > 0 ? (
                        <Badge variant="warning" className="text-[10px]">
                          {ds.warnings_count} warning{ds.warnings_count !== 1 ? 's' : ''}
                        </Badge>
                      ) : (
                        <Badge variant="success" className="text-[10px]">Clean</Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatDateTime(ds.uploaded_at)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}

        {/* Live Ranking Runs Table (when ranking runs exist) */}
        {rankingRuns.length > 0 && (
          <div className="space-y-2 pt-4">
            <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Top-X Ranking Runs ({rankingRuns.length})
            </h4>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Run ID</TableHead>
                  <TableHead>Dataset Source</TableHead>
                  <TableHead>Rules Preset</TableHead>
                  <TableHead>Scoring Preset</TableHead>
                  <TableHead>Top-X</TableHead>
                  <TableHead>Shortlisted</TableHead>
                  <TableHead>Evaluated At</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rankingRuns.map((r) => (
                  <TableRow key={r.run_id}>
                    <TableCell className="font-mono text-xs font-medium text-forest-900">
                      {r.run_id}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {r.dataset_filename || r.dataset_id || '—'}
                    </TableCell>
                    <TableCell>
                      <Badge variant="forest" className="text-[10px]">
                        {r.eligibility_config_id || 'custom'}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary" className="text-[10px]">
                        {r.scoring_config_id || 'custom'}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs font-mono font-medium">{r.top_x}</TableCell>
                    <TableCell className="text-xs font-semibold text-forest-800">
                      {r.selected_teams_count} teams
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatDateTime(r.evaluated_at)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
    </div>
  );
};
