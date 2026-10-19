import React, { useState } from 'react';
import {
  Scale,
  Plus,
  Edit3,
  AlertCircle,
  Clock,
  Layers,
  UserCheck,
  RefreshCw,
  Trash2,
  Lock,
  Loader2,
} from 'lucide-react';
import { Card, CardHeader, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import {
  useScoringConfigs,
  useScoringConfig,
  useScoringConfigVersions,
  useDeleteScoringConfigMutation,
} from '@/hooks/useConfigurations';
import { EditScoringWeightsModal } from './EditScoringWeightsModal';
import { CreateScoringConfigModal } from './CreateScoringConfigModal';

const BUILTIN_SCORING_PRESETS = [
  'balanced',
  'technical_heavy',
  'academic_heavy',
  'technical_focus',
  'academic_focus',
  'hackathon_demo',
];

interface ScoringTabProps {
  initialConfigId?: string;
  initialVersion?: number;
}

export const ScoringTab: React.FC<ScoringTabProps> = ({
  initialConfigId,
  initialVersion,
}) => {
  const configsQuery = useScoringConfigs();
  const deleteMutation = useDeleteScoringConfigMutation();

  const [selectedConfigId, setSelectedConfigId] = useState<string | null>(
    initialConfigId || null
  );
  const [selectedVersion, setSelectedVersion] = useState<number | undefined>(
    initialVersion
  );

  const [isEditOpen, setIsEditOpen] = useState(false);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const configs = configsQuery.data || [];
  const currentConfigId = selectedConfigId || configs[0]?.config_id || null;

  const versionsQuery = useScoringConfigVersions(currentConfigId);
  const versions = versionsQuery.data || [];
  const latestVersion = versions.length > 0 ? Math.max(...versions) : undefined;

  const effectiveVersion = selectedVersion !== undefined ? selectedVersion : latestVersion;
  const isViewingHistorical =
    latestVersion !== undefined && effectiveVersion !== undefined && effectiveVersion < latestVersion;

  const singleConfigQuery = useScoringConfig(currentConfigId, effectiveVersion);
  const currentConfig = singleConfigQuery.data || configs.find((c) => c.config_id === currentConfigId);

  const handleConfirmDelete = async () => {
    if (!currentConfig) return;
    setDeleteError(null);
    try {
      await deleteMutation.mutateAsync(currentConfig.config_id);
      setIsDeleteOpen(false);
      const remaining = configs.filter((c) => c.config_id !== currentConfig.config_id);
      setSelectedConfigId(remaining[0]?.config_id || null);
      setSelectedVersion(undefined);
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to delete scoring model.';
      setDeleteError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    }
  };

  const handleSelectConfig = (configId: string) => {
    setSelectedConfigId(configId);
    setSelectedVersion(undefined);
  };

  const handleVersionChange = (vStr: string) => {
    if (vStr === 'latest') {
      setSelectedVersion(undefined);
    } else {
      setSelectedVersion(parseInt(vStr, 10));
    }
  };

  if (configsQuery.isLoading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-28 rounded-lg" />
          ))}
        </div>
        <Skeleton className="h-96 rounded-lg" />
      </div>
    );
  }

  if (configsQuery.isError) {
    return (
      <Card className="border-red-200 bg-red-50/50">
        <CardContent className="p-6 flex flex-col items-center justify-center text-center space-y-3">
          <AlertCircle className="h-8 w-8 text-red-600" />
          <div>
            <h4 className="text-sm font-semibold text-red-900">Failed to Load Scoring Configurations</h4>
            <p className="text-xs text-red-700 mt-1 max-w-md">
              {configsQuery.error?.message || 'An unexpected error occurred while fetching scoring models.'}
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => configsQuery.refetch()}
            className="gap-1.5 text-xs"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Retry
          </Button>
        </CardContent>
      </Card>
    );
  }

  // Calculate total weights for active criteria
  const activeCriteria = (currentConfig?.criteria || []).filter((c) => c.is_enabled);
  const totalWeight = activeCriteria.reduce((sum, c) => sum + (c.weight || 0), 0);

  return (
    <div className="space-y-6">
      {/* Top Bar / Presets Selector Grid */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-foreground tracking-tight flex items-center gap-2">
              <Scale className="h-4 w-4 text-forest-700" />
              Scoring Configurations & Models ({configs.length})
            </h3>
            <p className="text-xs text-muted-foreground">
              Pre-configured multi-criteria relative weighting, aggregation models, and scoring rubrics.
            </p>
          </div>
          <Button
            variant="default"
            size="sm"
            onClick={() => setIsCreateOpen(true)}
            className="gap-1.5 text-xs"
          >
            <Plus className="h-3.5 w-3.5" />
            New Scoring Model
          </Button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {configs.map((cfg) => {
            const isSelected = cfg.config_id === currentConfigId;
            return (
              <Card
                key={cfg.config_id}
                onClick={() => handleSelectConfig(cfg.config_id)}
                className={`cursor-pointer transition-all border text-left p-3.5 ${
                  isSelected
                    ? 'border-forest-700 bg-forest-50/40 ring-1 ring-forest-700/50 shadow-sm'
                    : 'border-border/80 hover:border-forest-600/50 bg-card hover:bg-muted/20'
                }`}
              >
                <div className="flex items-center justify-between gap-1">
                  <Badge
                    variant={isSelected ? 'forest' : 'outline'}
                    className="font-mono text-[10px]"
                  >
                    v{cfg.version}
                  </Badge>
                  <code className="text-[10px] font-mono text-muted-foreground bg-muted px-1.5 py-0.5 rounded border border-border truncate max-w-[120px]">
                    {cfg.config_id}
                  </code>
                </div>
                <div className="mt-2">
                  <h4 className="text-xs font-bold text-foreground truncate">{cfg.name}</h4>
                  <p className="text-[11px] text-muted-foreground line-clamp-2 mt-1 leading-snug">
                    {cfg.description || 'No description provided.'}
                  </p>
                </div>
                <div className="mt-3 pt-2 border-t border-border/60 flex items-center justify-between text-[10px] text-muted-foreground">
                  <span className="flex items-center gap-1 font-mono">
                    <Scale className="h-3 w-3 text-forest-700" />
                    Scale: {cfg.scale_max || 100} pts
                  </span>
                  <span className="font-mono text-[10px] text-forest-700 font-medium">
                    {isSelected ? '● Selected' : 'Select →'}
                  </span>
                </div>
              </Card>
            );
          })}
        </div>
      </div>

      {/* Selected Configuration Detail View */}
      {currentConfig ? (
        <div className="space-y-4">
          {/* Detail Header Card */}
          <Card className="border-border">
            <CardHeader className="pb-4">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="text-base font-bold text-foreground tracking-tight">
                      {currentConfig.name}
                    </h3>
                    <code className="text-xs font-mono text-muted-foreground bg-muted px-2 py-0.5 rounded border border-border">
                      {currentConfig.config_id}
                    </code>
                    <Badge variant={currentConfig.is_active ? 'forest' : 'secondary'} className="text-[10px]">
                      {currentConfig.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground max-w-3xl leading-relaxed">
                    {currentConfig.description || 'No description provided for this scoring model.'}
                  </p>
                </div>

                {/* Actions & Version Switcher */}
                <div className="flex items-center gap-2.5 shrink-0">
                  {/* Version Selector */}
                  <div className="flex items-center gap-1.5 bg-muted/60 p-1 rounded-md border border-border">
                    <Clock className="h-3.5 w-3.5 text-muted-foreground ml-1.5" />
                    <span className="text-[11px] font-semibold text-muted-foreground">Version:</span>
                    <select
                      value={effectiveVersion !== undefined ? String(effectiveVersion) : 'latest'}
                      onChange={(e) => handleVersionChange(e.target.value)}
                      className="h-6 text-xs font-mono font-medium rounded border-0 bg-card px-2 text-foreground focus:ring-1 focus:ring-forest-600 cursor-pointer shadow-xs"
                    >
                      {versions.length > 0 ? (
                        versions
                          .slice()
                          .sort((a, b) => b - a)
                          .map((v) => (
                            <option key={v} value={String(v)}>
                              v{v} {v === latestVersion ? '(Latest)' : '(Historical)'}
                            </option>
                          ))
                      ) : (
                        <option value="1">v1 (Latest)</option>
                      )}
                    </select>
                  </div>

                  <Button
                    variant="default"
                    size="sm"
                    disabled={isViewingHistorical}
                    onClick={() => setIsEditOpen(true)}
                    className="gap-1.5 text-xs"
                    title={
                      isViewingHistorical
                        ? 'Historical versions are immutable. Switch to latest version to edit.'
                        : 'Edit weights and criteria'
                    }
                  >
                    <Edit3 className="h-3.5 w-3.5" />
                    Edit Weights
                  </Button>

                  {/* Builtin protection / Delete button */}
                  {BUILTIN_SCORING_PRESETS.includes(currentConfig.config_id) ? (
                    <Badge
                      variant="outline"
                      className="text-[10px] text-muted-foreground border-dashed flex items-center gap-1 py-1"
                      title="Built-in system presets cannot be deleted"
                    >
                      <Lock className="h-3 w-3" />
                      Preset (Protected)
                    </Badge>
                  ) : (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setIsDeleteOpen(true)}
                      className="gap-1.5 text-xs text-red-600 hover:text-red-700 hover:bg-red-50 border-red-200"
                      title="Deactivate this custom scoring model"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                      Delete
                    </Button>
                  )}
                </div>
              </div>

              {/* Historical Warning Banner if viewing an older snapshot */}
              {isViewingHistorical && (
                <div className="mt-3 p-3 rounded-md bg-amber-50 border border-amber-200 text-amber-900 text-xs flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Clock className="h-4 w-4 text-amber-700 shrink-0" />
                    <span>
                      Viewing <strong>Historical Snapshot v{effectiveVersion}</strong> (Immutable).
                      Evaluation runs conducted with this version remain 100% reproducible.
                    </span>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setSelectedVersion(undefined)}
                    className="text-xs bg-white text-amber-900 border-amber-300 hover:bg-amber-100"
                  >
                    Switch to Latest (v{latestVersion})
                  </Button>
                </div>
              )}
            </CardHeader>

            <CardContent className="space-y-5 pt-0">
              {/* Model Parameters Bar */}
              <div className="p-3 bg-muted/40 rounded-lg border border-border/70 flex flex-wrap items-center gap-x-6 gap-y-2 text-xs">
                <div className="flex items-center gap-1.5">
                  <span className="text-muted-foreground">Scale Maximum:</span>
                  <span className="font-mono font-bold text-forest-700 bg-forest-50 px-1.5 py-0.5 rounded border border-forest-200/60">
                    {currentConfig.scale_max || 100.0} pts
                  </span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="text-muted-foreground">Score Ineligible Teams:</span>
                  <span className="font-mono text-foreground font-semibold">
                    {currentConfig.score_ineligible_teams ? 'Enabled (Calculates Informational Score)' : 'Disabled (0.0 Disqualified)'}
                  </span>
                </div>
                {currentConfig.lead_field && (
                  <div className="flex items-center gap-1.5">
                    <UserCheck className="h-3.5 w-3.5 text-forest-700" />
                    <span className="text-muted-foreground">Lead Field:</span>
                    <span className="font-mono font-semibold text-foreground">
                      {currentConfig.lead_field}
                    </span>
                  </div>
                )}
              </div>

              {/* Criteria Table */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs font-semibold text-foreground">
                  <span className="flex items-center gap-1.5">
                    <Layers className="h-3.5 w-3.5 text-forest-700" />
                    Evaluation Criteria ({currentConfig.criteria?.length || 0})
                  </span>
                  <div className="flex items-center gap-2 font-mono text-[11px] text-muted-foreground">
                    <span>Active: {activeCriteria.length}</span>
                    <span>·</span>
                    <span className="text-forest-700 font-semibold">
                      Total Relative Weight: {totalWeight.toFixed(1)}
                    </span>
                  </div>
                </div>

                <div className="border border-border rounded-lg overflow-hidden">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-muted/60 border-b border-border text-[11px] text-muted-foreground">
                      <tr>
                        <th className="py-2.5 px-3">Criterion & Signal Key</th>
                        <th className="py-2.5 px-3">Type</th>
                        <th className="py-2.5 px-3">Normalization / Aggregation</th>
                        <th className="py-2.5 px-3">Missing Policy</th>
                        <th className="py-2.5 px-3 w-32 text-right">Relative Weight</th>
                        <th className="py-2.5 px-3 w-28 text-right">Weight Share</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {(currentConfig.criteria || []).map((crit) => {
                        const isEnabled = crit.is_enabled;
                        const share =
                          isEnabled && totalWeight > 0
                            ? ((crit.weight / totalWeight) * 100).toFixed(1)
                            : '0.0';

                        return (
                          <tr
                            key={crit.criterion_id}
                            className={`hover:bg-muted/20 transition-colors ${
                              !isEnabled ? 'opacity-40 bg-muted/10' : ''
                            }`}
                          >
                            <td className="py-3 px-3">
                              <div className="flex items-center gap-1.5">
                                <span className="font-semibold text-foreground">{crit.name}</span>
                                {!isEnabled && (
                                  <Badge variant="outline" className="text-[9px] text-muted-foreground">
                                    Disabled
                                  </Badge>
                                )}
                              </div>
                              <div className="text-[10px] font-mono text-muted-foreground mt-0.5">
                                id: <span className="text-foreground">{crit.criterion_id}</span>
                              </div>
                              <div className="text-[10px] font-mono text-forest-700 bg-forest-50 inline-block px-1 rounded mt-0.5 border border-forest-100">
                                {crit.target_signal_key}
                              </div>
                              {crit.description && (
                                <p className="text-[11px] text-muted-foreground mt-1 leading-snug">
                                  {crit.description}
                                </p>
                              )}
                            </td>
                            <td className="py-3 px-3">
                              <Badge variant="outline" className="font-mono text-[10px]">
                                {crit.criterion_type}
                              </Badge>
                            </td>
                            <td className="py-3 px-3">
                              <div className="text-foreground font-medium text-[11px]">
                                Agg: <span className="font-mono text-forest-700">{crit.aggregation}</span>
                              </div>
                              {crit.normalization?.linear_range && (
                                <div className="text-[10px] font-mono text-muted-foreground mt-0.5">
                                  min: {crit.normalization.linear_range.min_value}, max:{' '}
                                  {crit.normalization.linear_range.max_value}
                                </div>
                              )}
                              {crit.normalization?.boolean_mapping && (
                                <div className="text-[10px] font-mono text-muted-foreground mt-0.5">
                                  T: {crit.normalization.boolean_mapping.true_score}, F:{' '}
                                  {crit.normalization.boolean_mapping.false_score}
                                </div>
                              )}
                            </td>
                            <td className="py-3 px-3">
                              <span className="font-mono text-[10px] bg-muted/80 px-1.5 py-0.5 rounded border border-border">
                                {crit.missing_data_policy}
                              </span>
                            </td>
                            <td className="py-3 px-3 text-right">
                              <span className="font-mono font-bold text-sm text-foreground bg-muted/50 px-2 py-0.5 rounded border border-border">
                                {crit.weight.toFixed(1)}
                              </span>
                            </td>
                            <td className="py-3 px-3 text-right">
                              <div className="flex flex-col items-end">
                                <span className="font-mono text-xs font-semibold text-forest-700">
                                  {isEnabled ? `${share}%` : '—'}
                                </span>
                                {isEnabled && (
                                  <div className="w-16 h-1.5 bg-muted rounded-full overflow-hidden mt-1">
                                    <div
                                      className="h-full bg-forest-600 rounded-full"
                                      style={{ width: `${Math.min(100, parseFloat(share))}%` }}
                                    />
                                  </div>
                                )}
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      ) : (
        <Card className="border-border">
          <CardContent className="p-8 text-center text-xs text-muted-foreground">
            No scoring configuration selected. Please select a model from the list above.
          </CardContent>
        </Card>
      )}

      {/* Edit Modal */}
      {currentConfig && (
        <EditScoringWeightsModal
          open={isEditOpen}
          onOpenChange={setIsEditOpen}
          config={currentConfig}
          onSuccess={(newVersion) => {
            setSelectedVersion(newVersion);
            singleConfigQuery.refetch();
            configsQuery.refetch();
          }}
        />
      )}

      {/* Create Modal */}
      <CreateScoringConfigModal
        open={isCreateOpen}
        onOpenChange={setIsCreateOpen}
        existingConfigs={configs}
        onSuccess={(newId) => {
          setSelectedConfigId(newId);
          setSelectedVersion(undefined);
          configsQuery.refetch();
        }}
      />

      {/* Delete Confirmation Dialog */}
      {currentConfig && (
        <Dialog open={isDeleteOpen} onOpenChange={setIsDeleteOpen}>
          <DialogContent onClose={() => setIsDeleteOpen(false)} className="max-w-md">
            <DialogHeader>
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="border-red-300 text-red-700 bg-red-50 text-[10px]">
                  Deactivate Model
                </Badge>
              </div>
              <DialogTitle className="text-base font-semibold text-red-950">
                Delete Scoring Model: {currentConfig.name}
              </DialogTitle>
              <DialogDescription className="text-xs text-muted-foreground">
                Are you sure you want to deactivate <span className="font-mono font-semibold text-foreground">{currentConfig.config_id}</span>?
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-3 py-2 text-xs text-muted-foreground leading-relaxed">
              <p>
                This custom scoring model will be deactivated and removed from active selection pickers and wizard pipelines.
              </p>
              <p className="text-[11px] bg-muted/60 p-2.5 rounded border border-border">
                <strong>Historical Reproducibility:</strong> Prior evaluations conducted with this scoring model will remain fully preserved and intact.
              </p>
              {deleteError && (
                <div className="p-2.5 rounded border border-red-300 bg-red-50 text-red-800 text-xs flex items-start gap-1.5">
                  <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                  <span>{deleteError}</span>
                </div>
              )}
            </div>

            <DialogFooter>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsDeleteOpen(false)}
                disabled={deleteMutation.isPending}
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={handleConfirmDelete}
                disabled={deleteMutation.isPending}
                className="gap-1.5"
              >
                {deleteMutation.isPending ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
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
      )}
    </div>
  );
};
