import React, { useState, useRef } from 'react';
import {
  UploadCloud,
  FileSpreadsheet,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  Search,
  RefreshCw,
  ArrowRight,
  Database,
  FileCheck,
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
import { Skeleton } from '@/components/ui/skeleton';
import { TruncatedId } from '@/components/common/TruncatedId';
import { useWizardDatasets } from '@/hooks/useEvaluationWizard';
import { apiService } from '@/lib/api-services';
import type { DatasetSummary, UploadResponse } from '@/types';
import { cn } from '@/lib/utils';

interface Step1DatasetProps {
  selectedDataset: DatasetSummary | null;
  onSelectDataset: (dataset: DatasetSummary) => void;
  onNext: () => void;
}

export const Step1Dataset: React.FC<Step1DatasetProps> = ({
  selectedDataset,
  onSelectDataset,
  onNext,
}) => {
  const [activeTab, setActiveTab] = useState<'existing' | 'upload'>('existing');
  const [searchQuery, setSearchQuery] = useState('');

  // Upload States
  const [fileToUpload, setFileToUpload] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadResult, setUploadResult] = useState<UploadResponse | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Queries
  const {
    data: datasets,
    isLoading: isLoadingDatasets,
    isError: isDatasetsError,
    error: datasetsError,
    refetch: refetchDatasets,
  } = useWizardDatasets(50);

  // Filter datasets by filename or ID
  const filteredDatasets = (datasets || []).filter((d) => {
    if (!searchQuery.trim()) return true;
    const query = searchQuery.toLowerCase();
    return (
      d.filename.toLowerCase().includes(query) ||
      d.dataset_id.toLowerCase().includes(query) ||
      d.file_type.toLowerCase().includes(query)
    );
  });

  const handleFileDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      validateAndSetFile(file);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0];
      validateAndSetFile(file);
    }
  };

  const validateAndSetFile = (file: File) => {
    const ext = file.name.split('.').pop()?.toLowerCase();
    if (ext !== 'csv' && ext !== 'json') {
      setUploadError('Only .csv and .json registration files are supported.');
      setFileToUpload(null);
      return;
    }
    setUploadError(null);
    setUploadResult(null);
    setFileToUpload(file);
  };

  const handleUploadSubmit = async () => {
    if (!fileToUpload) return;
    setIsUploading(true);
    setUploadError(null);
    setUploadResult(null);

    try {
      const response = await apiService.uploadDataset(fileToUpload);
      setUploadResult(response);

      if (response.success && response.dataset_id) {
        // Build synthetic DatasetSummary from upload response and auto-select
        const newDatasetSummary: DatasetSummary = {
          dataset_id: response.dataset_id,
          filename: fileToUpload.name,
          file_type: fileToUpload.name.endsWith('.json') ? 'json' : 'csv',
          teams_count: response.teams_count,
          members_count: response.members_count,
          uploaded_at: new Date().toISOString(),
          warnings_count: response.warnings?.length || 0,
        };

        // Refresh existing list so it appears there too
        refetchDatasets();
        onSelectDataset(newDatasetSummary);
      } else if (response.errors && response.errors.length > 0) {
        setUploadError(response.errors.map((e) => e.msg).join('; '));
      }
    } catch (err: any) {
      setUploadError(err.message || 'Failed to upload and validate registration file.');
    } finally {
      setIsUploading(false);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  const formatDate = (isoString?: string | null) => {
    if (!isoString) return '—';
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString(undefined, {
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
      {/* Header & Tabs */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-4">
        <div>
          <h3 className="text-lg font-bold text-foreground tracking-tight">
            Step 1: Choose Registration Dataset
          </h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            Select a stored dataset snapshot or upload a new candidate registration file (CSV or JSON).
          </p>
        </div>

        {/* Tab Switcher */}
        <div className="inline-flex rounded-lg border border-border p-1 bg-muted/40">
          <button
            type="button"
            onClick={() => setActiveTab('existing')}
            className={cn(
              'flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded-md transition-all',
              activeTab === 'existing'
                ? 'bg-card text-foreground shadow-sm font-semibold'
                : 'text-muted-foreground hover:text-foreground'
            )}
          >
            <Database className="h-3.5 w-3.5" />
            Existing Datasets
            {datasets && datasets.length > 0 && (
              <Badge variant="secondary" className="text-[10px] h-4 px-1">
                {datasets.length}
              </Badge>
            )}
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('upload')}
            className={cn(
              'flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded-md transition-all',
              activeTab === 'upload'
                ? 'bg-card text-foreground shadow-sm font-semibold'
                : 'text-muted-foreground hover:text-foreground'
            )}
          >
            <UploadCloud className="h-3.5 w-3.5" />
            Upload New File
          </button>
        </div>
      </div>

      {/* Selected Dataset Alert Banner */}
      {selectedDataset && (
        <div className="flex items-center justify-between p-3.5 rounded-lg border border-forest-200 bg-forest-50/60">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-full bg-forest-100 flex items-center justify-center text-forest-800 shrink-0">
              <CheckCircle2 className="h-4 w-4 stroke-[2.5]" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-forest-950">Active Dataset Selected:</span>
                <span className="font-mono text-xs font-semibold text-foreground">
                  {selectedDataset.filename}
                </span>
                <Badge variant="forest" className="text-[10px] uppercase font-mono">
                  {selectedDataset.file_type}
                </Badge>
              </div>
              <div className="flex items-center gap-3 text-[11px] text-muted-foreground mt-0.5">
                <span>
                  ID: <TruncatedId id={selectedDataset.dataset_id} />
                </span>
                <span>·</span>
                <span>
                  <strong className="text-foreground">{selectedDataset.teams_count}</strong> teams
                </span>
                <span>·</span>
                <span>
                  <strong className="text-foreground">{selectedDataset.members_count}</strong> candidates
                </span>
              </div>
            </div>
          </div>
          <Button size="sm" onClick={onNext} className="gap-1.5 shadow-sm">
            Continue to Signals
            <ArrowRight className="h-3.5 w-3.5" />
          </Button>
        </div>
      )}

      {/* Tab Content: Existing Datasets */}
      {activeTab === 'existing' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between gap-3">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
              <Input
                placeholder="Search datasets by name or ID..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-8 text-xs h-8"
              />
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => refetchDatasets()}
              disabled={isLoadingDatasets}
              className="text-xs h-8 gap-1.5"
            >
              <RefreshCw className={cn('h-3.5 w-3.5', isLoadingDatasets && 'animate-spin')} />
              Refresh
            </Button>
          </div>

          {isLoadingDatasets ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
            </div>
          ) : isDatasetsError ? (
            <div className="p-4 rounded-lg border border-destructive/30 bg-destructive/5 text-destructive text-xs space-y-2">
              <div className="flex items-center gap-2 font-semibold">
                <AlertCircle className="h-4 w-4" />
                Failed to load datasets from backend
              </div>
              <p>{datasetsError?.message || 'Server error'}</p>
              <Button size="sm" variant="outline" onClick={() => refetchDatasets()}>
                Retry
              </Button>
            </div>
          ) : filteredDatasets.length === 0 ? (
            <div className="text-center py-10 px-4 rounded-lg border border-dashed border-border bg-card">
              <FileSpreadsheet className="h-9 w-9 text-muted-foreground/60 mx-auto mb-2" />
              <h4 className="text-sm font-semibold text-foreground">No Datasets Found</h4>
              <p className="text-xs text-muted-foreground max-w-md mx-auto mt-1 mb-4">
                {searchQuery
                  ? `No datasets match "${searchQuery}". Clear your search query.`
                  : 'No registration datasets have been uploaded yet. Upload a CSV or JSON file to get started.'}
              </p>
              {searchQuery ? (
                <Button size="sm" variant="outline" onClick={() => setSearchQuery('')}>
                  Clear Search
                </Button>
              ) : (
                <Button size="sm" onClick={() => setActiveTab('upload')} className="gap-1.5">
                  <UploadCloud className="h-4 w-4" />
                  Upload First Dataset
                </Button>
              )}
            </div>
          ) : (
            <div className="rounded-lg border border-border bg-card overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow className="bg-muted/30">
                    <TableHead className="w-12 text-center">Select</TableHead>
                    <TableHead>Filename & ID</TableHead>
                    <TableHead className="w-20">Type</TableHead>
                    <TableHead className="text-right">Teams</TableHead>
                    <TableHead className="text-right">Members</TableHead>
                    <TableHead>Uploaded At</TableHead>
                    <TableHead className="w-24 text-right">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredDatasets.map((ds) => {
                    const isSelected = selectedDataset?.dataset_id === ds.dataset_id;
                    return (
                      <TableRow
                        key={ds.dataset_id}
                        onClick={() => onSelectDataset(ds)}
                        className={cn(
                          'cursor-pointer transition-colors',
                          isSelected
                            ? 'bg-forest-50/70 hover:bg-forest-50'
                            : 'hover:bg-muted/40'
                        )}
                      >
                        <TableCell className="text-center">
                          <input
                            type="radio"
                            name="datasetSelection"
                            checked={isSelected}
                            onChange={() => onSelectDataset(ds)}
                            className="h-4 w-4 text-forest-700 focus:ring-forest-600 border-border"
                          />
                        </TableCell>
                        <TableCell>
                          <div className="space-y-0.5">
                            <span className="font-semibold text-xs text-foreground block">
                              {ds.filename}
                            </span>
                            <div className="text-[11px] text-muted-foreground flex items-center gap-1">
                              <span>ID:</span>
                              <TruncatedId id={ds.dataset_id} />
                            </div>
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline" className="font-mono text-[10px] uppercase">
                            {ds.file_type}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right font-mono text-xs font-medium">
                          {ds.teams_count}
                        </TableCell>
                        <TableCell className="text-right font-mono text-xs font-medium">
                          {ds.members_count}
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {formatDate(ds.uploaded_at)}
                        </TableCell>
                        <TableCell className="text-right">
                          <Button
                            size="sm"
                            variant={isSelected ? 'default' : 'outline'}
                            className="h-7 text-xs px-2.5"
                            onClick={(e) => {
                              e.stopPropagation();
                              onSelectDataset(ds);
                            }}
                          >
                            {isSelected ? 'Selected' : 'Select'}
                          </Button>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </div>
      )}

      {/* Tab Content: Upload New File */}
      {activeTab === 'upload' && (
        <div className="space-y-4">
          <Card className="border-border/80">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold">Upload Candidate Registrations</CardTitle>
              <CardDescription className="text-xs">
                Upload CSV or JSON files. The ingestion engine automatically discovers custom columns, validates team sizing, and detects duplicate candidate names.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Dropzone */}
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setIsDragging(true);
                }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={handleFileDrop}
                onClick={() => fileInputRef.current?.click()}
                className={cn(
                  'border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-all',
                  isDragging
                    ? 'border-forest-600 bg-forest-50/50'
                    : 'border-border hover:border-forest-400 hover:bg-muted/30 bg-card'
                )}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv,.json"
                  onChange={handleFileChange}
                  className="hidden"
                />
                <UploadCloud
                  className={cn(
                    'h-10 w-10 mx-auto mb-2 transition-colors',
                    isDragging ? 'text-forest-700' : 'text-muted-foreground'
                  )}
                />
                <p className="text-sm font-semibold text-foreground">
                  Click to browse or drag and drop registration file here
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  Supports standardized CSV or JSON registration exports (Max 15MB)
                </p>
              </div>

              {/* Selected File Details */}
              {fileToUpload && (
                <div className="flex items-center justify-between p-3 rounded-lg border border-border bg-muted/30">
                  <div className="flex items-center gap-3">
                    <FileCheck className="h-5 w-5 text-forest-700" />
                    <div>
                      <p className="text-xs font-semibold text-foreground">{fileToUpload.name}</p>
                      <p className="text-[11px] text-muted-foreground">
                        {formatFileSize(fileToUpload.size)} · Type:{' '}
                        {fileToUpload.name.endsWith('.json') ? 'JSON' : 'CSV'}
                      </p>
                    </div>
                  </div>
                  <Button
                    size="sm"
                    onClick={handleUploadSubmit}
                    disabled={isUploading}
                    className="gap-1.5"
                  >
                    {isUploading ? (
                      <>
                        <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                        Validating & Ingesting...
                      </>
                    ) : (
                      <>
                        <UploadCloud className="h-3.5 w-3.5" />
                        Upload & Ingest
                      </>
                    )}
                  </Button>
                </div>
              )}

              {/* Error Message */}
              {uploadError && (
                <div className="p-3.5 rounded-lg border border-destructive/30 bg-destructive/10 text-destructive text-xs flex items-start gap-2.5">
                  <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                  <div className="space-y-1">
                    <span className="font-semibold block">Ingestion Failed</span>
                    <p className="leading-relaxed">{uploadError}</p>
                  </div>
                </div>
              )}

              {/* Success Result */}
              {uploadResult && uploadResult.success && (
                <div className="p-4 rounded-lg border border-emerald-300 bg-emerald-50/60 text-emerald-950 text-xs space-y-3">
                  <div className="flex items-center gap-2 font-bold text-sm text-emerald-900">
                    <CheckCircle2 className="h-4 w-4 text-emerald-700" />
                    Dataset Successfully Ingested & Saved!
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 pt-1 border-t border-emerald-200">
                    <div>
                      <span className="text-muted-foreground block text-[10px]">Dataset ID</span>
                      <TruncatedId id={uploadResult.dataset_id} />
                    </div>
                    <div>
                      <span className="text-muted-foreground block text-[10px]">Valid Teams</span>
                      <span className="font-bold font-mono text-emerald-950">
                        {uploadResult.teams_count} teams
                      </span>
                    </div>
                    <div>
                      <span className="text-muted-foreground block text-[10px]">Total Members</span>
                      <span className="font-bold font-mono text-emerald-950">
                        {uploadResult.members_count} candidates
                      </span>
                    </div>
                  </div>

                  {/* Non-fatal Warnings */}
                  {uploadResult.warnings && uploadResult.warnings.length > 0 && (
                    <div className="mt-2 pt-2 border-t border-emerald-200">
                      <div className="flex items-center gap-1.5 text-amber-800 font-semibold mb-1">
                        <AlertTriangle className="h-3.5 w-3.5 text-amber-600" />
                        {uploadResult.warnings.length} Non-fatal Ingestion Warnings:
                      </div>
                      <div className="max-h-28 overflow-y-auto space-y-1 bg-white/70 p-2 rounded border border-emerald-200/60 font-mono text-[11px]">
                        {uploadResult.warnings.slice(0, 5).map((w, idx) => (
                          <div key={idx} className="text-amber-900">
                            • [{w.team_id || 'Global'}] {w.field}: {w.message}
                          </div>
                        ))}
                        {uploadResult.warnings.length > 5 && (
                          <div className="text-muted-foreground italic">
                            ... and {uploadResult.warnings.length - 5} more warnings
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  <div className="pt-1 flex justify-end">
                    <Button size="sm" onClick={onNext} className="gap-1.5">
                      Proceed with this Dataset
                      <ArrowRight className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* Footer Navigation */}
      <div className="flex items-center justify-between border-t border-border pt-4">
        <span className="text-xs text-muted-foreground">
          {selectedDataset
            ? 'Dataset selected. Click Next to configure extraction signals.'
            : 'Please select or upload a dataset to proceed.'}
        </span>
        <Button
          onClick={onNext}
          disabled={!selectedDataset}
          className="gap-2 shadow-sm"
        >
          Next: Signal Extraction
          <ArrowRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
};
