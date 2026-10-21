import React, { useState } from 'react';
import {
  ShieldCheck,
  Plus,
  Layers,
  Edit3,
  AlertCircle,
  Clock,
  UserCheck,
  RefreshCw,
  Trash2,
  Lock,
  Loader2,
  User,
  Users,
  Copy,
} from 'lucide-react';
import { cn } from '@/lib/utils';
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
  useRuleConfigs,
  useRuleConfig,
  useRuleConfigVersions,
  useDeleteRuleConfigMutation,
} from '@/hooks/useConfigurations';
import { EditRuleConfigModal } from './EditRuleConfigModal';
import { CreateRuleConfigModal } from './CreateRuleConfigModal';
import {
  formatRuleType,
  formatMissingPolicy,
  formatScope,
  formatMemberSelection,
  formatRuleParameters,
} from './configFormatters';

const BUILTIN_RULE_PRESETS = ['basic', 'demo_mixed_review', 'open_solo', 'strict'];

interface EligibilityTabProps {
  initialConfigId?: string;
  initialVersion?: number;
}

export const EligibilityTab: React.FC<EligibilityTabProps> = ({
  initialConfigId,
  initialVersion,
}) => {
  const configsQuery = useRuleConfigs();
  const deleteMutation = useDeleteRuleConfigMutation();

  const [selectedConfigId, setSelectedConfigId] = useState<string | null>(
    initialConfigId || null
  );
  const [selectedVersion, setSelectedVersion] = useState<number | undefined>(
    initialVersion
  );

  // Modals state
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  // If no config selected yet, select the first available once loaded
  const configs = configsQuery.data || [];
  const currentConfigId = selectedConfigId || configs[0]?.config_id || null;

  // Versions for the current config
  const versionsQuery = useRuleConfigVersions(currentConfigId);
  const versions = versionsQuery.data || [];
  const latestVersion = versions.length > 0 ? Math.max(...versions) : undefined;

  // Current effective version: if selectedVersion is set use it, else latest
  const effectiveVersion = selectedVersion !== undefined ? selectedVersion : latestVersion;
  const isViewingHistorical =
    latestVersion !== undefined && effectiveVersion !== undefined && effectiveVersion < latestVersion;

  // Single config query (fetches specific version if effectiveVersion is specified)
  const singleConfigQuery = useRuleConfig(currentConfigId, effectiveVersion);
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
      const msg = err?.response?.data?.detail || err?.message || 'Failed to delete configuration.';
      setDeleteError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    }
  };

  // When config selection changes, reset version to latest
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
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
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
            <h4 className="text-sm font-semibold text-red-900">Failed to Load Eligibility Configurations</h4>
            <p className="text-xs text-red-700 mt-1 max-w-md">
              {configsQuery.error?.message || 'An unexpected error occurred while fetching configurations.'}
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

  return (
    <div className="space-y-6">
      {/* Top Bar / Presets Selector Grid */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-foreground tracking-tight flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-forest-700" />
              Eligibility Configurations ({configs.length})
            </h3>
            <p className="text-xs text-muted-foreground">
              Select a rule set to inspect evaluators, parameters, and historical version snapshots.
            </p>
          </div>
          <Button
            variant="default"
            size="sm"
            onClick={() => setIsCreateOpen(true)}
            className="gap-1.5 text-xs"
          >
            <Plus className="h-3.5 w-3.5" />
            New Configuration
          </Button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-3">
          {configs.map((cfg) => {
            const isSelected = cfg.config_id === currentConfigId;
            return (
              <Card
                key={cfg.config_id}
                onClick={() => handleSelectConfig(cfg.config_id)}
                className={cn(
                  'cursor-pointer transition-all border text-left p-3.5 flex flex-col justify-between rounded-xl relative group min-h-[130px]',
                  isSelected
                    ? 'border-forest-700 bg-forest-50/40 ring-1 ring-forest-700/50 shadow-xs'
                    : 'border-border/80 hover:border-forest-600/50 bg-card hover:bg-muted/20 hover:shadow-2xs'
                )}
              >
                <div>
                  <div className="flex items-center justify-between gap-1">
                    <Badge
                      variant={isSelected ? 'forest' : 'outline'}
                      className="font-mono text-[10px]"
                    >
                      v{cfg.version}
                    </Badge>
                    <code className="text-[10px] font-mono text-muted-foreground bg-muted/80 px-1.5 py-0.5 rounded border border-border/70 truncate max-w-[110px]">
                      {cfg.config_id}
                    </code>
                  </div>
                  <div className="mt-2.5">
                    <h4 className="text-xs font-bold text-foreground line-clamp-1" title={cfg.name}>
                      {cfg.name}
                    </h4>
                    <p
                      className={cn(
                        'text-[11px] line-clamp-2 mt-1 leading-snug',
                        cfg.description ? 'text-muted-foreground' : 'text-muted-foreground/60 italic'
                      )}
                      title={cfg.description || 'No description provided.'}
                    >
                      {cfg.description || 'No description provided.'}
                    </p>
                  </div>
                </div>
                <div className="mt-3 pt-2 border-t border-border/60 flex items-center justify-between text-[10px] text-muted-foreground">
                  <span className="flex items-center gap-1 font-mono">
                    <Layers className="h-3 w-3 text-forest-700" />
                    {cfg.rules?.length || 0} Rules
                  </span>
                  <span className={cn('font-mono text-[10px] font-medium', isSelected ? 'text-forest-700 font-semibold' : 'text-muted-foreground group-hover:text-forest-700')}>
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
                    {currentConfig.description || 'No description provided for this configuration.'}
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

                  {BUILTIN_RULE_PRESETS.includes(currentConfig.config_id) || currentConfig.user_id === 'system' ? (
                    <>
                      <Button
                        variant="default"
                        size="sm"
                        onClick={() => setIsCreateOpen(true)}
                        className="gap-1.5 text-xs bg-forest-700 hover:bg-forest-800 text-white"
                        title="System presets are protected. Click to duplicate and customize your own rules."
                      >
                        <Copy className="h-3.5 w-3.5" />
                        Duplicate & Customize
                      </Button>
                      <Badge
                        variant="outline"
                        className="text-[10px] text-muted-foreground border-dashed flex items-center gap-1 py-1"
                        title="Built-in system presets cannot be deleted or modified in-place"
                      >
                        <Lock className="h-3 w-3" />
                        Preset (Protected)
                      </Badge>
                    </>
                  ) : (
                    <>
                      <Button
                        variant="default"
                        size="sm"
                        disabled={isViewingHistorical}
                        onClick={() => setIsEditOpen(true)}
                        className="gap-1.5 text-xs"
                        title={
                          isViewingHistorical
                            ? 'Historical versions are immutable. Switch to latest version to edit.'
                            : 'Edit this configuration'
                        }
                      >
                        <Edit3 className="h-3.5 w-3.5" />
                        Edit Rules
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setIsDeleteOpen(true)}
                        className="gap-1.5 text-xs text-red-600 hover:text-red-700 hover:bg-red-50 border-red-200"
                        title="Deactivate this custom configuration"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                        Delete
                      </Button>
                    </>
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
              {/* Global Config Settings Bar */}
              {currentConfig.global_config && (
                <div className="p-3 bg-muted/30 rounded-xl border border-border/80 flex flex-wrap items-center gap-x-6 gap-y-2.5 text-xs">
                  <div className="flex items-center gap-2">
                    <div className="flex h-6 w-6 items-center justify-center rounded-md bg-forest-50 text-forest-700 border border-forest-200/60">
                      <UserCheck className="h-3.5 w-3.5" />
                    </div>
                    <span className="text-muted-foreground font-medium">Team Lead Field:</span>
                    <span className="font-mono font-semibold text-foreground bg-card px-2 py-0.5 rounded border border-border/80">
                      {currentConfig.global_config.lead_field || 'role'}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground font-medium">Lead Recognition Values:</span>
                    <span className="font-mono text-[11px] text-foreground bg-card px-2 py-0.5 rounded border border-border/80">
                      {(currentConfig.global_config.lead_values || []).join(', ') || 'lead, team lead'}
                    </span>
                  </div>
                  {currentConfig.global_config.default_academic_scale && (
                    <div className="flex items-center gap-2">
                      <span className="text-muted-foreground font-medium">Default Scale:</span>
                      <span className="font-mono font-semibold text-foreground bg-card px-2 py-0.5 rounded border border-border/80">
                        {currentConfig.global_config.default_academic_scale} pts max
                      </span>
                    </div>
                  )}
                </div>
              )}

              {/* Evaluator Rules Table */}
              <div className="space-y-2.5">
                <div className="flex items-center justify-between text-xs font-semibold text-foreground">
                  <span className="flex items-center gap-1.5">
                    <Layers className="h-3.5 w-3.5 text-forest-700" />
                    Evaluator Rules ({currentConfig.rules?.length || 0})
                  </span>
                  <span className="text-[11px] font-mono text-muted-foreground">
                    Sorted by execution order
                  </span>
                </div>

                <div className="border border-border/80 rounded-xl overflow-hidden shadow-2xs">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-muted/50 border-b border-border text-[11px] font-medium text-muted-foreground">
                      <tr>
                        <th className="py-2.5 px-3 w-14 text-center">Order</th>
                        <th className="py-2.5 px-3">Rule Definition</th>
                        <th className="py-2.5 px-3">Scope & Selection</th>
                        <th className="py-2.5 px-3">Severity</th>
                        <th className="py-2.5 px-3">On Missing Data</th>
                        <th className="py-2.5 px-3">Parameters</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/60">
                      {(currentConfig.rules || []).map((rule) => {
                        const isHard = rule.severity === 'hard';
                        const isEnabled = rule.is_enabled;
                        const missingPolicy = formatMissingPolicy(rule.on_missing);
                        const memberSel = formatMemberSelection(rule.member_selection);
                        const paramList = formatRuleParameters(rule.rule_type, rule.parameters);

                        return (
                          <tr
                            key={rule.rule_id}
                            className={`hover:bg-muted/20 transition-colors ${
                              !isEnabled ? 'opacity-40 bg-muted/10' : ''
                            }`}
                          >
                            <td className="py-3 px-3 text-center">
                              <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-muted/80 font-mono text-[11px] font-bold text-muted-foreground">
                                {String(rule.order).padStart(2, '0')}
                              </span>
                            </td>
                            <td className="py-3 px-3">
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="font-semibold text-foreground text-xs">{rule.name}</span>
                                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-forest-50 text-forest-800 border border-forest-200/60">
                                  {formatRuleType(rule.rule_type)}
                                </span>
                                {!isEnabled && (
                                  <Badge variant="outline" className="text-[9px] text-muted-foreground">
                                    Disabled
                                  </Badge>
                                )}
                              </div>
                              <div className="text-[10px] font-mono text-muted-foreground/75 mt-0.5">
                                id: {rule.rule_id}
                              </div>
                              {rule.description && (
                                <p className="text-[11px] text-muted-foreground mt-1 leading-snug max-w-xl">
                                  {rule.description}
                                </p>
                              )}
                            </td>
                            <td className="py-3 px-3">
                              <div className="flex items-center gap-1.5 font-medium text-foreground">
                                {rule.scope === 'member' ? (
                                  <User className="h-3.5 w-3.5 text-forest-700" />
                                ) : (
                                  <Users className="h-3.5 w-3.5 text-forest-700" />
                                )}
                                <span>{formatScope(rule.scope)}</span>
                              </div>
                              {memberSel && (
                                <div className="text-[10px] text-muted-foreground mt-0.5 bg-muted/60 px-1.5 py-0.5 rounded inline-block border border-border/50">
                                  {memberSel}
                                </div>
                              )}
                            </td>
                            <td className="py-3 px-3">
                              <span
                                className={cn(
                                  'inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium border',
                                  isHard
                                    ? 'bg-emerald-50 text-emerald-800 border-emerald-200/80 font-semibold'
                                    : 'bg-secondary text-secondary-foreground border-border'
                                )}
                              >
                                {isHard ? 'Hard Filter' : 'Soft Advisory'}
                              </span>
                            </td>
                            <td className="py-3 px-3">
                              <span
                                className={cn(
                                  'inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium border',
                                  missingPolicy.tone === 'warning'
                                    ? 'bg-amber-50/80 text-amber-800 border-amber-200/60'
                                    : 'bg-muted/70 text-muted-foreground border-border/70'
                                )}
                              >
                                {missingPolicy.label}
                              </span>
                            </td>
                            <td className="py-3 px-3">
                              {paramList.length > 0 ? (
                                <div className="flex flex-wrap gap-1 max-w-xs">
                                  {paramList.map((param, pIdx) => (
                                    <span
                                      key={pIdx}
                                      className="text-[10px] font-mono bg-card px-2 py-0.5 rounded-md border border-border/80 text-foreground flex items-center gap-1 shadow-2xs"
                                    >
                                      <span className="text-muted-foreground font-sans font-medium text-[10px]">{param.label}:</span>
                                      <span className="font-semibold">{param.value}</span>
                                    </span>
                                  ))}
                                </div>
                              ) : (
                                <span className="text-muted-foreground text-[11px]">—</span>
                              )}
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
            No configuration selected. Please select a configuration from the list above.
          </CardContent>
        </Card>
      )}

      {/* Edit Modal */}
      {currentConfig && (
        <EditRuleConfigModal
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
      <CreateRuleConfigModal
        open={isCreateOpen}
        onOpenChange={setIsCreateOpen}
        existingConfigs={configs}
        initialBasePresetId={currentConfig?.config_id}
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
                  Deactivate Configuration
                </Badge>
              </div>
              <DialogTitle className="text-base font-semibold text-red-950">
                Delete Configuration: {currentConfig.name}
              </DialogTitle>
              <DialogDescription className="text-xs text-muted-foreground">
                Are you sure you want to deactivate <span className="font-mono font-semibold text-foreground">{currentConfig.config_id}</span>?
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-3 py-2 text-xs text-muted-foreground leading-relaxed">
              <p>
                This custom configuration will be deactivated and removed from active selection pickers and wizard pipelines.
              </p>
              <p className="text-[11px] bg-muted/60 p-2.5 rounded border border-border">
                <strong>Historical Reproducibility:</strong> Prior evaluations conducted with this configuration will remain fully preserved and unchanged.
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
