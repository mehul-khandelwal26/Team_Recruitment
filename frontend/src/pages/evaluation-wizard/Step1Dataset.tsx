import React, { useState, useRef, useMemo } from 'react';
import { useQueryClient } from '@tanstack/react-query';
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
  TableProperties,
  Sparkles,
  X,
  Info,
  Trash2,
} from 'lucide-react';
import { DeleteConfirmModal } from '@/components/common/DeleteConfirmModal';
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
import { useWizardDatasets, useDatasetRecord } from '@/hooks/useEvaluationWizard';
import { apiService } from '@/lib/api-services';
import type {
  DatasetSummary,
  UploadResponse,
  FieldDiscoveryResponse,
  CanonicalFieldInfo,
} from '@/types';
import { cn } from '@/lib/utils';

const DEFAULT_CANONICAL_FIELDS: CanonicalFieldInfo[] = [
  { field_key: 'name', display_name: 'Candidate Name', is_structural_required: true, category: 'Core Identity & Structure', description: 'Participant full name (Required)' },
  { field_key: 'team_name', display_name: 'Team Name', is_structural_required: true, category: 'Core Identity & Structure', description: 'Name of the student team (Required for CSV)' },
  { field_key: 'member_id', display_name: 'Candidate ID', is_structural_required: false, category: 'Core Identity & Structure', description: 'Student roll number or registration ID' },
  { field_key: 'team_id', display_name: 'Team ID', is_structural_required: false, category: 'Core Identity & Structure', description: 'Explicit unique team identifier' },
  { field_key: 'github_url', display_name: 'GitHub Profile URL', is_structural_required: false, category: 'Candidate Signals & Links', description: 'Candidate GitHub profile URL or username' },
  { field_key: 'email', display_name: 'Email Address', is_structural_required: false, category: 'Candidate Signals & Links', description: 'Contact email' },
  { field_key: 'linkedin_url', display_name: 'LinkedIn Profile URL', is_structural_required: false, category: 'Candidate Signals & Links', description: 'Candidate LinkedIn profile link' },
  { field_key: 'portfolio_url', display_name: 'Portfolio / Website URL', is_structural_required: false, category: 'Candidate Signals & Links', description: 'Personal website or portfolio link' },
  { field_key: 'resume_url', display_name: 'Resume / CV URL', is_structural_required: false, category: 'Candidate Signals & Links', description: 'Link to uploaded resume or document' },
  { field_key: 'cgpa', display_name: 'Academic CGPA / Grade', is_structural_required: false, category: 'Academic Performance', description: 'Declared GPA, CPI, or percentage' },
  { field_key: 'academic_year', display_name: 'Academic Year of Study', is_structural_required: false, category: 'Academic Performance', description: 'Current year of study or batch' },
];

const formatCanonicalFieldName = (key: string): string => {
  const match = DEFAULT_CANONICAL_FIELDS.find((f) => f.field_key === key);
  if (match) return match.display_name;
  if (key === 'academic_cgpa') return 'Academic CGPA';
  if (key === 'academic_year') return 'Academic Year';
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
};

interface Step1DatasetProps {
  selectedDataset: DatasetSummary | null;
  onSelectDataset: (dataset: DatasetSummary | null) => void;
  onNext: () => void;
  initialTab?: 'existing' | 'upload';
}

export const Step1Dataset: React.FC<Step1DatasetProps> = ({
  selectedDataset,
  onSelectDataset,
  onNext,
  initialTab,
}) => {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<'existing' | 'upload'>(initialTab || 'existing');

  React.useEffect(() => {
    if (initialTab) {
      setActiveTab(initialTab);
    }
  }, [initialTab]);

  const [searchQuery, setSearchQuery] = useState('');
  const [datasetToDelete, setDatasetToDelete] = useState<DatasetSummary | null>(null);

  // Upload States
  const [fileToUpload, setFileToUpload] = useState<File | null>(null);
  const [resumesZipToUpload, setResumesZipToUpload] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadResult, setUploadResult] = useState<UploadResponse | null>(null);
  const [showAllWarnings, setShowAllWarnings] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const zipInputRef = useRef<HTMLInputElement>(null);

  // Column Mapping & Discovery States
  const [isInspecting, setIsInspecting] = useState(false);
  const [inspectError, setInspectError] = useState<string | null>(null);
  const [discoveryResult, setDiscoveryResult] = useState<FieldDiscoveryResponse | null>(null);
  const [columnMappings, setColumnMappings] = useState<Record<string, string>>({});
  const [canonicalFields, setCanonicalFields] = useState<CanonicalFieldInfo[]>(DEFAULT_CANONICAL_FIELDS);
  const [mappingSearch, setMappingSearch] = useState('');

  // Queries
  const {
    data: datasets,
    isLoading: isLoadingDatasets,
    isError: isDatasetsError,
    error: datasetsError,
    refetch: refetchDatasets,
  } = useWizardDatasets(50);

  const { data: activeDatasetRecord } = useDatasetRecord(selectedDataset?.dataset_id);
  const effectiveActiveMapping: Record<string, string> = useMemo(() => {
    return (
      (selectedDataset?.mapping as Record<string, string>) ||
      (activeDatasetRecord?.mapping as Record<string, string>) ||
      {}
    );
  }, [selectedDataset, activeDatasetRecord]);

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

  const validateAndSetFile = async (file: File) => {
    const ext = file.name.split('.').pop()?.toLowerCase();
    if (ext !== 'csv' && ext !== 'json') {
      setUploadError('Only .csv and .json registration files are supported.');
      setFileToUpload(null);
      setDiscoveryResult(null);
      return;
    }
    setUploadError(null);
    setUploadResult(null);
    setInspectError(null);
    setFileToUpload(file);
    setIsInspecting(true);

    try {
      const [discRes, canonList] = await Promise.all([
        apiService.inspectDataset(file),
        apiService.getCanonicalFields().catch(() => [] as CanonicalFieldInfo[]),
      ]);
      setDiscoveryResult(discRes);
      if (canonList && canonList.length > 0) {
        setCanonicalFields(canonList);
      } else if (discRes.canonical_fields && discRes.canonical_fields.length > 0) {
        setCanonicalFields(discRes.canonical_fields);
      }

      // Initialize mapping dictionary with suggestions
      const initialMap: Record<string, string> = {};
      if (discRes.suggested_mappings) {
        Object.assign(initialMap, discRes.suggested_mappings);
      }
      discRes.discovered_fields?.forEach((df) => {
        const target = df.suggested_mapping || df.recognized_field;
        if (target && !initialMap[df.original_name]) {
          initialMap[df.original_name] = target;
        }
      });
      setColumnMappings(initialMap);
    } catch (err: any) {
      console.warn('Field discovery failed:', err);
      setInspectError(err.message || 'Auto-inspection failed. You can still upload directly.');
    } finally {
      setIsInspecting(false);
    }
  };

  // Check for duplicate target field mappings
  const duplicateTargets = useMemo(() => {
    const counts: Record<string, string[]> = {};
    Object.entries(columnMappings).forEach(([col, target]) => {
      if (target) {
        const norm = target.trim().toLowerCase();
        counts[norm] = counts[norm] || [];
        counts[norm].push(col);
      }
    });
    const duplicates: Record<string, string[]> = {};
    Object.entries(counts).forEach(([target, cols]) => {
      if (cols.length > 1) {
        duplicates[target] = cols;
      }
    });
    return duplicates;
  }, [columnMappings]);

  const hasDuplicateMappings = Object.keys(duplicateTargets).length > 0;

  // Group canonical fields by category for clean dropdown rendering
  const groupedCanonicalFields = useMemo(() => {
    const groups: Record<string, CanonicalFieldInfo[]> = {};
    canonicalFields.forEach((cf) => {
      const cat = cf.category || 'Standard Fields';
      groups[cat] = groups[cat] || [];
      groups[cat].push(cf);
    });
    return groups;
  }, [canonicalFields]);

  // Filter discovered fields by search query
  const filteredDiscoveredFields = useMemo(() => {
    if (!discoveryResult?.discovered_fields) return [];
    if (!mappingSearch.trim()) return discoveryResult.discovered_fields;
    const q = mappingSearch.toLowerCase();
    return discoveryResult.discovered_fields.filter(
      (df) =>
        df.original_name.toLowerCase().includes(q) ||
        (columnMappings[df.original_name] || '').toLowerCase().includes(q) ||
        df.inferred_type.toLowerCase().includes(q)
    );
  }, [discoveryResult, mappingSearch, columnMappings]);

  const mappedCount = Object.values(columnMappings).filter(Boolean).length;
  const totalDiscoveredCount = discoveryResult?.discovered_fields?.length || 0;

  const handleMappingChange = (originalCol: string, targetKey: string) => {
    setColumnMappings((prev) => {
      const next = { ...prev };
      if (!targetKey) {
        delete next[originalCol];
      } else {
        next[originalCol] = targetKey;
      }
      return next;
    });
  };

  const handleResetToAutoSuggestions = () => {
    if (!discoveryResult) return;
    const autoMap: Record<string, string> = {};
    if (discoveryResult.suggested_mappings) {
      Object.assign(autoMap, discoveryResult.suggested_mappings);
    }
    discoveryResult.discovered_fields?.forEach((df) => {
      const tgt = df.suggested_mapping || df.recognized_field;
      if (tgt && !autoMap[df.original_name]) {
        autoMap[df.original_name] = tgt;
      }
    });
    setColumnMappings(autoMap);
  };

  const handleClearAllMappings = () => {
    setColumnMappings({});
  };

  const handleZipChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0];
      if (!file.name.toLowerCase().endsWith('.zip')) {
        setUploadError('Only .zip companion resume archives are supported.');
        setResumesZipToUpload(null);
        return;
      }
      setResumesZipToUpload(file);
      setUploadError(null);
    }
  };

  const handleUploadSubmit = async () => {
    if (!fileToUpload) return;
    if (hasDuplicateMappings) {
      setUploadError(
        `Cannot ingest dataset: duplicate mapping for ${Object.keys(duplicateTargets).join(', ')}. Each target can only be mapped to one column.`
      );
      return;
    }
    setIsUploading(true);
    setUploadError(null);
    setUploadResult(null);

    try {
      const response = await apiService.uploadDataset(
        fileToUpload,
        columnMappings,
        resumesZipToUpload || undefined
      );
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
          mapping: response.mapping || columnMappings,
        };

        // Refresh and invalidate existing dataset lists across wizard and dashboard
        queryClient.invalidateQueries({ queryKey: ['datasets'] });
        queryClient.invalidateQueries({ queryKey: ['wizard', 'datasets'] });
        refetchDatasets();
        onSelectDataset(newDatasetSummary);
      } else if (response.errors && response.errors.length > 0) {
        setUploadError(
          response.errors
            .map((e: any) => {
              const msg = e.message || e.msg || 'Validation error';
              return e.location ? `${e.location}: ${msg}` : msg;
            })
            .join('; ')
        );
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
              {effectiveActiveMapping && Object.keys(effectiveActiveMapping).length > 0 && (
                <div className="flex flex-wrap items-center gap-1.5 mt-2 pt-2 border-t border-forest-200/60">
                  <span className="text-[10px] font-semibold text-forest-900 uppercase tracking-wider">
                    Signal Mappings:
                  </span>
                  {Object.entries(effectiveActiveMapping).map(([orig, tgt]) => (
                    <span
                      key={orig}
                      className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-white/95 border border-forest-300 text-[10px] text-forest-950 shadow-2xs"
                    >
                      <span className="font-mono text-forest-700">{orig}</span>
                      <span className="text-forest-400">→</span>
                      <span className="text-forest-900 font-semibold">{formatCanonicalFieldName(tgt)}</span>
                    </span>
                  ))}
                </div>
              )}
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
                    <TableHead className="w-28 text-right">Actions</TableHead>
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
                          <div className="flex items-center justify-end gap-1.5" onClick={(e) => e.stopPropagation()}>
                            <Button
                              size="sm"
                              variant={isSelected ? 'default' : 'outline'}
                              className="h-7 text-xs px-2.5"
                              onClick={() => onSelectDataset(ds)}
                            >
                              {isSelected ? 'Selected' : 'Select'}
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                              title={`Delete ${ds.filename}`}
                              onClick={() => setDatasetToDelete(ds)}
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
                  accept=".csv,.tsv,.txt,.json"
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
                  Supports CSV, TSV, or JSON registration exports (Max 15MB)
                </p>
              </div>

              {/* Optional Companion Resumes Archive Dropzone */}
              <div className="p-3.5 rounded-lg border border-border bg-card/60 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="h-6 w-6 rounded bg-emerald-100 flex items-center justify-center text-emerald-800">
                      <FileCheck className="h-3.5 w-3.5" />
                    </div>
                    <div>
                      <span className="text-xs font-semibold text-foreground">
                        Attach Resumes Archive (.zip)
                      </span>
                      <Badge variant="outline" className="ml-2 text-[9px] py-0 font-normal">
                        Optional Companion
                      </Badge>
                    </div>
                  </div>
                  {resumesZipToUpload ? (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setResumesZipToUpload(null)}
                      className="text-xs h-6 px-2 text-muted-foreground hover:text-destructive"
                    >
                      <X className="h-3 w-3 mr-1" />
                      Remove ZIP
                    </Button>
                  ) : (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => zipInputRef.current?.click()}
                      className="text-xs h-7 gap-1"
                    >
                      Browse ZIP
                    </Button>
                  )}
                </div>

                <input
                  ref={zipInputRef}
                  type="file"
                  accept=".zip"
                  onChange={handleZipChange}
                  className="hidden"
                />

                {resumesZipToUpload ? (
                  <div className="flex items-center justify-between p-2 rounded bg-forest-50/60 border border-forest-200 text-xs">
                    <span className="font-medium text-forest-900 truncate">
                      {resumesZipToUpload.name} ({formatFileSize(resumesZipToUpload.size)})
                    </span>
                    <Badge variant="forest" className="text-[10px]">
                      Attached
                    </Badge>
                  </div>
                ) : (
                  <p className="text-[11px] text-muted-foreground leading-relaxed">
                    Upload a companion .zip of candidate PDF or DOCX resumes. Candidate names, emails, roll numbers, or CSV resume paths will automatically be matched and extracted without downloading from cloud links.
                  </p>
                )}
              </div>

              {/* Selected File Details & Interactive Column Mapping */}
              {fileToUpload && (
                <div className="space-y-4">
                  {/* File Metadata Bar */}
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
                      variant="ghost"
                      onClick={() => {
                        setFileToUpload(null);
                        setDiscoveryResult(null);
                        setColumnMappings({});
                        setUploadError(null);
                        setUploadResult(null);
                      }}
                      className="text-xs h-7 gap-1 text-muted-foreground hover:text-foreground"
                    >
                      <X className="h-3.5 w-3.5" />
                      Change File
                    </Button>
                  </div>

                  {/* Schema Inspection Loading Skeleton */}
                  {isInspecting && (
                    <div className="p-4 rounded-lg border border-forest-200 bg-forest-50/40 space-y-3 animate-pulse">
                      <div className="flex items-center gap-2 text-xs font-semibold text-forest-900">
                        <RefreshCw className="h-3.5 w-3.5 animate-spin text-forest-700" />
                        Analyzing file schema & detecting candidate signals...
                      </div>
                      <div className="space-y-2">
                        <Skeleton className="h-6 w-3/4" />
                        <Skeleton className="h-10 w-full" />
                        <Skeleton className="h-10 w-full" />
                      </div>
                    </div>
                  )}

                  {/* Schema Inspection Error / Notice */}
                  {inspectError && (
                    <div className="p-3 rounded-lg border border-amber-300 bg-amber-50/60 text-amber-900 text-xs flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0" />
                        <span>{inspectError}</span>
                      </div>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => validateAndSetFile(fileToUpload)}
                        className="h-7 text-xs"
                      >
                        Retry Inspection
                      </Button>
                    </div>
                  )}

                  {/* Column-to-Signal Mapping Table */}
                  {discoveryResult && !isInspecting && (
                    <div className="rounded-lg border border-border bg-card overflow-hidden space-y-3 p-4">
                      {/* Mapping Header & Stats */}
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border pb-3">
                        <div className="space-y-0.5">
                          <div className="flex items-center gap-2">
                            <TableProperties className="h-4 w-4 text-forest-700" />
                            <h4 className="text-sm font-bold text-foreground">
                              Candidate Signal & Column Mapping
                            </h4>
                          </div>
                          <p className="text-[11px] text-muted-foreground">
                            Map custom columns to candidate signals (GitHub URLs, CGPA, Batch) and required team structure. Unmapped columns remain preserved as custom data.
                          </p>
                        </div>

                        {/* Counts Badges */}
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <Badge variant="outline" className="text-[10px] font-mono">
                            {totalDiscoveredCount} Columns Found
                          </Badge>
                          <Badge variant="forest" className="text-[10px] font-mono">
                            {mappedCount} Mapped
                          </Badge>
                          <Badge variant="secondary" className="text-[10px] font-mono">
                            {totalDiscoveredCount - mappedCount} Custom
                          </Badge>
                        </div>
                      </div>

                      {/* Duplicate Target Conflict Alert */}
                      {hasDuplicateMappings && (
                        <div className="p-3 rounded-lg border border-destructive/40 bg-destructive/10 text-destructive text-xs space-y-1">
                          <div className="flex items-center gap-2 font-bold">
                            <AlertCircle className="h-4 w-4" />
                            Duplicate Target Field Conflict:
                          </div>
                          <p className="text-[11px]">
                            The following canonical targets are assigned to multiple columns:{' '}
                            <strong>{Object.keys(duplicateTargets).join(', ')}</strong>. Each canonical target field can only be mapped to one column.
                          </p>
                        </div>
                      )}

                      {/* Missing Structural Fields Warning */}
                      {discoveryResult.missing_structural_fields &&
                        discoveryResult.missing_structural_fields.length > 0 && (
                          <div className="p-3 rounded-lg border border-amber-300 bg-amber-50/60 text-amber-900 text-xs flex items-start gap-2.5">
                            <Info className="h-4 w-4 text-amber-700 shrink-0 mt-0.5" />
                            <div className="space-y-0.5">
                              <span className="font-semibold block">Missing Core Fields Notice:</span>
                              <p className="text-[11px] leading-relaxed">
                                Expected structural fields (<strong>{discoveryResult.missing_structural_fields.join(', ')}</strong>) were not automatically detected. If your file contains candidate name or team columns under different headers, please map them below.
                              </p>
                            </div>
                          </div>
                        )}

                      {/* Search & Actions Toolbar */}
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-1">
                        <div className="relative flex-1 max-w-xs">
                          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
                          <Input
                            placeholder="Filter discovered columns..."
                            value={mappingSearch}
                            onChange={(e) => setMappingSearch(e.target.value)}
                            className="pl-8 text-xs h-8"
                          />
                        </div>
                        <div className="flex items-center gap-2">
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={handleResetToAutoSuggestions}
                            className="text-xs h-8 gap-1.5"
                          >
                            <Sparkles className="h-3.5 w-3.5 text-forest-700" />
                            Reset to Auto-Detected
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="ghost"
                            onClick={handleClearAllMappings}
                            className="text-xs h-8 text-muted-foreground hover:text-foreground"
                          >
                            Clear All
                          </Button>
                        </div>
                      </div>

                      {/* Discovered Columns Table */}
                      <div className="rounded border border-border overflow-hidden">
                        <Table>
                          <TableHeader>
                            <TableRow className="bg-muted/40 text-[11px]">
                              <TableHead className="w-1/3">File Column Name</TableHead>
                              <TableHead className="w-1/4">Sample Values</TableHead>
                              <TableHead className="w-1/3">Mapped Canonical Signal / Field</TableHead>
                              <TableHead className="w-28 text-right">Status</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {filteredDiscoveredFields.map((df) => {
                              const currentTarget = columnMappings[df.original_name] || '';
                              const isDuplicate = currentTarget && (duplicateTargets[currentTarget.toLowerCase()]?.length || 0) > 1;
                              const isDirect = df.is_recognized && currentTarget === df.recognized_field;
                              const isSuggested = Boolean(df.suggested_mapping && currentTarget === df.suggested_mapping);

                              return (
                                <TableRow key={df.original_name} className="text-xs hover:bg-muted/20">
                                  {/* Original Name & Type */}
                                  <TableCell className="align-top py-2.5">
                                    <div className="space-y-1">
                                      <div className="flex items-center gap-1.5">
                                        <span className="font-mono font-semibold text-foreground text-xs">
                                          {df.original_name}
                                        </span>
                                        <Badge variant="outline" className="text-[9px] px-1 py-0 font-mono text-muted-foreground uppercase">
                                          {df.inferred_type}
                                        </Badge>
                                      </div>
                                      <div className="text-[10px] text-muted-foreground">
                                        {df.non_empty_count} / {df.total_count} populated ({df.total_count ? Math.round((df.non_empty_count / df.total_count) * 100) : 0}%)
                                      </div>
                                    </div>
                                  </TableCell>

                                  {/* Sample Preview */}
                                  <TableCell className="align-top py-2.5">
                                    <div className="flex flex-wrap gap-1 max-w-xs">
                                      {df.sample_values && df.sample_values.length > 0 ? (
                                        df.sample_values.slice(0, 2).map((val, idx) => (
                                          <span
                                            key={idx}
                                            className="inline-block px-1.5 py-0.5 rounded bg-muted text-[10px] font-mono text-muted-foreground truncate max-w-[140px]"
                                            title={String(val)}
                                          >
                                            {String(val)}
                                          </span>
                                        ))
                                      ) : (
                                        <span className="text-muted-foreground/60 italic text-[10px]">No sample data</span>
                                      )}
                                    </div>
                                  </TableCell>

                                  {/* Target Select Dropdown */}
                                  <TableCell className="align-top py-2.5">
                                    <div className="space-y-1">
                                      <select
                                        value={currentTarget}
                                        onChange={(e) => handleMappingChange(df.original_name, e.target.value)}
                                        className={cn(
                                          'w-full h-8 px-2.5 text-xs rounded-md border bg-background text-foreground transition-colors focus:outline-none focus:ring-1',
                                          isDuplicate
                                            ? 'border-destructive focus:ring-destructive text-destructive'
                                            : currentTarget?.startsWith('custom:')
                                            ? 'border-purple-600 focus:ring-purple-600 text-purple-900 font-medium'
                                            : currentTarget
                                            ? 'border-forest-600 focus:ring-forest-600'
                                            : 'border-input focus:ring-ring text-muted-foreground'
                                        )}
                                      >
                                        <option value="">-- Do not map (Ignore / Discard) --</option>
                                        <optgroup label="✨ Custom Recruitment Signals">
                                          <option value={`custom:${df.original_name.toLowerCase().replace(/[^a-z0-9_]/g, '_')}`}>
                                            ⭐ Map as Custom Signal
                                          </option>
                                        </optgroup>
                                        {Object.entries(groupedCanonicalFields).map(([cat, fields]) => (
                                          <optgroup key={cat} label={cat}>
                                            {fields.map((f) => (
                                              <option key={f.field_key} value={f.field_key}>
                                                {f.display_name} ({f.field_key}){f.is_structural_required ? ' *' : ''}
                                              </option>
                                            ))}
                                          </optgroup>
                                        ))}
                                      </select>
                                      {df.suggestion_reason && isSuggested && (
                                        <p className="text-[10px] text-muted-foreground italic">
                                          {df.suggestion_reason}
                                        </p>
                                      )}
                                    </div>
                                  </TableCell>

                                  {/* Status Badge */}
                                  <TableCell className="text-right align-top py-2.5">
                                    {isDuplicate ? (
                                      <Badge variant="destructive" className="text-[10px]">
                                        Conflict
                                      </Badge>
                                    ) : currentTarget?.startsWith('custom:') ? (
                                      <Badge variant="forest" className="text-[10px] bg-purple-50 text-purple-900 border-purple-300">
                                        Custom Signal
                                      </Badge>
                                    ) : isDirect ? (
                                      <Badge variant="success" className="text-[10px]">
                                        Direct Match
                                      </Badge>
                                    ) : isSuggested ? (
                                      <Badge variant="forest" className="text-[10px]">
                                        Suggested
                                      </Badge>
                                    ) : currentTarget ? (
                                      <Badge variant="secondary" className="text-[10px]">
                                        User Mapped
                                      </Badge>
                                    ) : (
                                      <Badge variant="outline" className="text-[10px] text-muted-foreground">
                                        Ignored
                                      </Badge>
                                    )}
                                  </TableCell>
                                </TableRow>
                              );
                            })}
                          </TableBody>
                        </Table>
                      </div>

                      {/* Confirm & Ingest Action */}
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-3 border-t border-border">
                        <span className="text-[11px] text-muted-foreground">
                          {mappedCount > 0
                            ? `${mappedCount} column(s) will be translated into standard signals during ingestion.`
                            : 'No column mappings specified. Columns will be stored as raw candidate data.'}
                        </span>
                        <Button
                          size="sm"
                          onClick={handleUploadSubmit}
                          disabled={isUploading || hasDuplicateMappings}
                          className="gap-1.5 shadow-sm"
                        >
                          {isUploading ? (
                            <>
                              <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                              Ingesting with Applied Mappings...
                            </>
                          ) : (
                            <>
                              <UploadCloud className="h-3.5 w-3.5" />
                              Confirm Mapping & Ingest Dataset
                            </>
                          )}
                        </Button>
                      </div>
                    </div>
                  )}

                  {/* Fallback Direct Upload Button if Discovery is not active */}
                  {!discoveryResult && !isInspecting && (
                    <div className="flex justify-end pt-1">
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
                            Upload & Ingest Directly
                          </>
                        )}
                      </Button>
                    </div>
                  )}
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
                      <div className="flex items-center justify-between text-amber-800 font-semibold mb-1">
                        <div className="flex items-center gap-1.5">
                          <AlertTriangle className="h-3.5 w-3.5 text-amber-600" />
                          <span>{uploadResult.warnings.length} Non-fatal Ingestion Warnings:</span>
                        </div>
                        {uploadResult.warnings.length > 5 && (
                          <button
                            type="button"
                            onClick={() => setShowAllWarnings((prev) => !prev)}
                            className="text-xs text-amber-900 underline hover:text-amber-950 font-medium cursor-pointer"
                          >
                            {showAllWarnings ? 'Show less (5)' : `Show all (${uploadResult.warnings.length})`}
                          </button>
                        )}
                      </div>
                      <div
                        className={cn(
                          'overflow-y-auto space-y-1 bg-white/70 p-2 rounded border border-emerald-200/60 font-mono text-[11px]',
                          showAllWarnings ? 'max-h-60' : 'max-h-28'
                        )}
                      >
                        {(showAllWarnings
                          ? uploadResult.warnings
                          : uploadResult.warnings.slice(0, 5)
                        ).map((w, idx) => (
                          <div key={idx} className="text-amber-900">
                            • [{w.team_id || 'Global'}] {w.field}: {w.message}
                          </div>
                        ))}
                        {!showAllWarnings && uploadResult.warnings.length > 5 && (
                          <div className="text-muted-foreground italic">
                            ... and {uploadResult.warnings.length - 5} more warnings (click &apos;Show all&apos; above)
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

      {/* Delete Confirmation Modal */}
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
            queryClient.removeQueries({ queryKey: ['wizard', 'dataset', datasetToDelete.dataset_id] });
            queryClient.invalidateQueries({ queryKey: ['datasets'] });
            queryClient.invalidateQueries({ queryKey: ['wizard', 'datasets'] });
            queryClient.invalidateQueries({ queryKey: ['wizard', 'extractions', datasetToDelete.dataset_id] });
            if (selectedDataset?.dataset_id === datasetToDelete.dataset_id) {
              onSelectDataset(null);
            }
            refetchDatasets();
            setDatasetToDelete(null);
          }}
        />
      )}
    </div>
  );
};
