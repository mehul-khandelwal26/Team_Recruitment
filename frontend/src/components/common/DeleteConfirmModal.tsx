import React, { useState, useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import {
  AlertTriangle,
  Trash2,
  Download,
  RotateCw,
  AlertCircle,
  Layers,
  Cpu,
  Trophy,
  CheckCircle2,
} from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { TruncatedId } from '@/components/common/TruncatedId';
import { apiService } from '@/lib/api-services';
import type { DependencyCounts } from '@/types';

export interface DeleteConfirmModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  itemType: 'dataset' | 'ranking_run' | 'extraction_run';
  itemId: string;
  itemTitle?: string;
  onSuccess?: () => void;
  onDownloadBackup?: () => Promise<void>;
}

export const DeleteConfirmModal: React.FC<DeleteConfirmModalProps> = ({
  open,
  onOpenChange,
  itemType,
  itemId,
  itemTitle,
  onSuccess,
  onDownloadBackup,
}) => {
  const queryClient = useQueryClient();
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  // Cascade toggle state
  const [cascade, setCascade] = useState<boolean>(true);

  // Dependency inspection states
  const [isLoadingDeps, setIsLoadingDeps] = useState(false);
  const [dependencies, setDependencies] = useState<DependencyCounts | null>(null);
  const [isDownloadingBackup, setIsDownloadingBackup] = useState(false);

  // Fetch dependencies when opened for dataset or extraction run
  useEffect(() => {
    if (!open || !itemId) {
      setDependencies(null);
      setDeleteError(null);
      return;
    }

    let isMounted = true;
    if (itemType === 'dataset') {
      setIsLoadingDeps(true);
      apiService
        .getDatasetDependencies(itemId)
        .then((res) => {
          if (isMounted) {
            setDependencies(res.dependencies);
            setCascade(res.has_dependencies);
          }
        })
        .catch(() => {
          if (isMounted) setDependencies(null);
        })
        .finally(() => {
          if (isMounted) setIsLoadingDeps(false);
        });
    } else if (itemType === 'extraction_run') {
      setIsLoadingDeps(true);
      apiService
        .getExtractionRunDependencies(itemId)
        .then((res) => {
          if (isMounted) {
            setDependencies(res.dependencies);
            setCascade(res.has_dependencies);
          }
        })
        .catch(() => {
          if (isMounted) setDependencies(null);
        })
        .finally(() => {
          if (isMounted) setIsLoadingDeps(false);
        });
    } else {
      setDependencies(null);
    }

    return () => {
      isMounted = false;
    };
  }, [open, itemId, itemType]);

  const handleDelete = async () => {
    setIsDeleting(true);
    setDeleteError(null);

    try {
      if (itemType === 'dataset') {
        await apiService.deleteDataset(itemId, cascade);
        // Evict cached dataset details
        queryClient.removeQueries({ queryKey: ['wizard', 'dataset', itemId] });
        // Invalidate dataset lists across Dashboard and Evaluation Wizard
        queryClient.invalidateQueries({ queryKey: ['datasets'] });
        queryClient.invalidateQueries({ queryKey: ['wizard', 'datasets'] });
        queryClient.invalidateQueries({ queryKey: ['wizard', 'extractions', itemId] });
        if (cascade) {
          queryClient.invalidateQueries({ queryKey: ['ranking'] });
          queryClient.invalidateQueries({ queryKey: ['signals'] });
        }
      } else if (itemType === 'ranking_run') {
        await apiService.deleteRankingRun(itemId);
        // Evict specific ranking run cache so subsequent views don't show ghost record
        queryClient.removeQueries({ queryKey: ['ranking', 'run', itemId] });
        // Invalidate ranking lists across Results and Dashboard
        queryClient.invalidateQueries({ queryKey: ['ranking'] });
      } else if (itemType === 'extraction_run') {
        await apiService.deleteExtractionRun(itemId, cascade);
        // Evict specific extraction run cache
        queryClient.removeQueries({ queryKey: ['signals', 'run', itemId] });
        // Invalidate signal extraction lists across Wizard and Dashboard
        queryClient.invalidateQueries({ queryKey: ['signals'] });
        queryClient.invalidateQueries({ queryKey: ['wizard', 'extractions'] });
        if (cascade) {
          queryClient.invalidateQueries({ queryKey: ['ranking'] });
        }
      }

      onOpenChange(false);
      if (onSuccess) {
        onSuccess();
      }
    } catch (err: any) {
      setDeleteError(
        err.message || 'Failed to delete item. Please check backend server status and try again.'
      );
    } finally {
      setIsDeleting(false);
    }
  };

  const handleBackup = async () => {
    if (!onDownloadBackup) return;
    setIsDownloadingBackup(true);
    try {
      await onDownloadBackup();
    } catch (err: any) {
      setDeleteError(err.message || 'Failed to download backup CSV.');
    } finally {
      setIsDownloadingBackup(false);
    }
  };

  const typeLabels = {
    dataset: 'Dataset',
    ranking_run: 'Ranking Run',
    extraction_run: 'Signal Extraction Run',
  };

  const totalDeps = dependencies?.total || 0;
  const hasDeps = totalDeps > 0;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent onClose={() => onOpenChange(false)} className="max-w-lg">
        <DialogHeader>
          <div className="flex items-center gap-2.5">
            <div className="h-9 w-9 rounded-full bg-destructive/10 text-destructive flex items-center justify-center shrink-0">
              <AlertTriangle className="h-5 w-5" />
            </div>
            <div>
              <DialogTitle className="text-destructive font-bold">
                Delete {typeLabels[itemType]}
              </DialogTitle>
              <DialogDescription>
                This action is permanent and cannot be undone.
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div className="space-y-4 py-3 text-xs">
          {/* Target Item Summary */}
          <div className="p-3 rounded-lg border border-border bg-muted/30 space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground font-medium">Selected Item:</span>
              <Badge variant="outline" className="font-mono text-[10px] uppercase">
                {itemType.replace('_', ' ')}
              </Badge>
            </div>
            {itemTitle && (
              <p className="font-semibold text-foreground text-sm truncate" title={itemTitle}>
                {itemTitle}
              </p>
            )}
            <div className="flex items-center gap-1.5 text-muted-foreground font-mono text-[11px]">
              <span>ID:</span>
              <TruncatedId id={itemId} className="font-semibold text-foreground" />
            </div>
          </div>

          {/* Backup prompt for Ranking Runs */}
          {itemType === 'ranking_run' && onDownloadBackup && (
            <div className="p-3 rounded-lg border border-forest-200 bg-forest-50/70 text-forest-950 flex items-center justify-between gap-3">
              <div className="space-y-0.5">
                <span className="font-semibold text-xs block">Need a local copy first?</span>
                <span className="text-[11px] text-muted-foreground">
                  Export this shortlist leaderboard as CSV before deleting.
                </span>
              </div>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={handleBackup}
                disabled={isDownloadingBackup}
                className="h-7 text-xs gap-1 border-forest-300 text-forest-800 hover:bg-forest-100 shrink-0"
              >
                {isDownloadingBackup ? (
                  <RotateCw className="h-3 w-3 animate-spin" />
                ) : (
                  <Download className="h-3 w-3" />
                )}
                Export CSV
              </Button>
            </div>
          )}

          {/* Dependencies Inspection for Datasets & Extractions */}
          {(itemType === 'dataset' || itemType === 'extraction_run') && (
            <div className="space-y-2">
              {isLoadingDeps ? (
                <div className="p-3 rounded-lg border border-border bg-muted/20 flex items-center gap-2 text-muted-foreground">
                  <RotateCw className="h-3.5 w-3.5 animate-spin" />
                  <span>Checking dependent evaluations and shortlists...</span>
                </div>
              ) : hasDeps ? (
                <div className="p-3.5 rounded-lg border border-amber-300 bg-amber-50/80 text-amber-950 space-y-2.5">
                  <div className="flex items-center gap-2 font-semibold text-amber-900">
                    <Layers className="h-4 w-4 text-amber-700 shrink-0" />
                    <span>
                      {totalDeps} Dependent {totalDeps === 1 ? 'Evaluation' : 'Evaluations'} Linked
                    </span>
                  </div>
                  <p className="text-[11px] text-amber-800 leading-relaxed">
                    This {itemType === 'dataset' ? 'dataset' : 'extraction run'} is referenced by historical evaluation runs:
                  </p>
                  <div className="grid grid-cols-2 gap-2 text-[11px]">
                    {dependencies?.ranking_runs ? (
                      <div className="flex items-center gap-1.5 bg-white/80 p-1.5 rounded border border-amber-200">
                        <Trophy className="h-3.5 w-3.5 text-amber-700" />
                        <span>
                          <strong>{dependencies.ranking_runs}</strong> Top-X shortlists
                        </span>
                      </div>
                    ) : null}
                    {dependencies?.scoring_runs ? (
                      <div className="flex items-center gap-1.5 bg-white/80 p-1.5 rounded border border-amber-200">
                        <Layers className="h-3.5 w-3.5 text-amber-700" />
                        <span>
                          <strong>{dependencies.scoring_runs}</strong> scoring runs
                        </span>
                      </div>
                    ) : null}
                    {dependencies?.eligibility_runs ? (
                      <div className="flex items-center gap-1.5 bg-white/80 p-1.5 rounded border border-amber-200">
                        <CheckCircle2 className="h-3.5 w-3.5 text-amber-700" />
                        <span>
                          <strong>{dependencies.eligibility_runs}</strong> eligibility runs
                        </span>
                      </div>
                    ) : null}
                    {dependencies?.extraction_runs ? (
                      <div className="flex items-center gap-1.5 bg-white/80 p-1.5 rounded border border-amber-200">
                        <Cpu className="h-3.5 w-3.5 text-amber-700" />
                        <span>
                          <strong>{dependencies.extraction_runs}</strong> extraction runs
                        </span>
                      </div>
                    ) : null}
                  </div>

                  {/* Cascade Checkbox */}
                  <label className="flex items-start gap-2.5 pt-1 cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={cascade}
                      onChange={(e) => setCascade(e.target.checked)}
                      className="mt-0.5 h-4 w-4 rounded border-amber-400 text-destructive focus:ring-destructive"
                    />
                    <span className="text-[11px] text-amber-950 font-medium">
                      Cascade delete: Permanently remove all {totalDeps} linked evaluation runs and shortlists along with this {itemType === 'dataset' ? 'dataset' : 'extraction run'}.
                    </span>
                  </label>
                  {!cascade && (
                    <p className="text-[10px] text-destructive font-semibold">
                      Note: Unchecking cascade will cause the delete request to be rejected if historical runs still reference this {itemType === 'dataset' ? 'dataset' : 'extraction run'}.
                    </p>
                  )}
                </div>
              ) : (
                <div className="p-2.5 rounded-lg border border-border bg-muted/20 text-muted-foreground flex items-center gap-2 text-[11px]">
                  <CheckCircle2 className="h-3.5 w-3.5 text-forest-700 shrink-0" />
                  <span>No dependent runs or shortlists found. Safe to delete.</span>
                </div>
              )}
            </div>
          )}

          {/* Error Banner */}
          {deleteError && (
            <div className="p-3 rounded-lg border border-destructive/30 bg-destructive/10 text-destructive text-xs flex items-start gap-2">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
              <span>{deleteError}</span>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => onOpenChange(false)}
            disabled={isDeleting}
            className="text-xs"
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant="destructive"
            size="sm"
            onClick={handleDelete}
            disabled={isDeleting || (hasDeps && !cascade)}
            className="text-xs gap-1.5 shadow-sm"
          >
            {isDeleting ? (
              <>
                <RotateCw className="h-3.5 w-3.5 animate-spin" />
                Deleting...
              </>
            ) : (
              <>
                <Trash2 className="h-3.5 w-3.5" />
                Confirm Delete
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
