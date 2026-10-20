import React, { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  AlertCircle,
  Loader2,
  Plus,
} from 'lucide-react';
import type { ScoringConfiguration, EvaluationCriterionInput } from '@/types';
import { useCreateScoringConfigMutation } from '@/hooks/useConfigurations';

interface CreateScoringConfigModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  existingConfigs: ScoringConfiguration[];
  onSuccess: (newConfigId: string) => void;
}

export const CreateScoringConfigModal: React.FC<CreateScoringConfigModalProps> = ({
  open,
  onOpenChange,
  existingConfigs,
  onSuccess,
}) => {
  const createMutation = useCreateScoringConfigMutation();

  const [configId, setConfigId] = useState('');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [scaleMax, setScaleMax] = useState<number | string>(100);
  const [basePresetId, setBasePresetId] = useState<string>(
    existingConfigs[0]?.config_id || ''
  );
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async () => {
    const cleanId = configId.trim().toLowerCase().replace(/[^a-z0-9_-]/g, '_');
    if (!cleanId) {
      setErrorMessage('Please enter a valid alphanumeric Configuration ID.');
      return;
    }
    if (!name.trim()) {
      setErrorMessage('Please enter a Scoring Model Name.');
      return;
    }
    if (Number(scaleMax) <= 0) {
      setErrorMessage('Scale Maximum must be strictly greater than 0.');
      return;
    }

    if (existingConfigs.some((c) => c.config_id === cleanId)) {
      setErrorMessage(`Scoring configuration '${cleanId}' already exists. Please choose a unique ID.`);
      return;
    }

    const isScratch = basePresetId === '__scratch__';
    const template = isScratch ? null : existingConfigs.find((c) => c.config_id === basePresetId);

    const starterCriteria: EvaluationCriterionInput[] = [
      {
        criterion_id: 'crit_repos',
        name: 'Public GitHub Repositories',
        description: 'Measures candidate development activity via public GitHub repositories.',
        target_signal_key: 'github_public_repo_count',
        criterion_type: 'numeric_range' as any,
        weight: 1.0,
        is_enabled: true,
        normalization: {
          linear_range: {
            min_value: 0,
            max_value: 20,
          },
        },
        aggregation: 'mean' as any,
        missing_data_policy: 'exclude_and_renormalize' as any,
        config: {},
      },
    ];

    const templateCriteria: EvaluationCriterionInput[] = isScratch
      ? starterCriteria
      : (template?.criteria || []).map((c) => ({
          criterion_id: c.criterion_id,
          name: c.name,
          description: c.description,
          target_signal_key: c.target_signal_key,
          criterion_type: c.criterion_type as any,
          weight: c.weight,
          is_enabled: c.is_enabled,
          normalization: c.normalization,
          aggregation: c.aggregation as any,
          top_k_value: c.top_k_value,
          missing_data_policy: c.missing_data_policy as any,
          confidence_adjustment: c.confidence_adjustment,
          config: c.config || {},
        }));

    setErrorMessage(null);
    try {
      const created = await createMutation.mutateAsync({
        config_id: cleanId,
        name: name.trim(),
        description: description.trim(),
        scale_max: Number(scaleMax) || 100,
        criteria: templateCriteria,
        lead_field: template?.lead_field || 'role',
        lead_values: template?.lead_values || ['lead', 'team lead', 'captain', 'leader'],
        score_ineligible_teams: template?.score_ineligible_teams ?? true,
      });
      onSuccess(created.config_id);
      onOpenChange(false);
    } catch (err: any) {
      const msg =
        err?.response?.data?.detail || err?.message || 'Failed to create scoring configuration.';
      setErrorMessage(typeof msg === 'string' ? msg : JSON.stringify(msg));
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent onClose={() => onOpenChange(false)} className="max-w-lg">
        <DialogHeader>
          <div className="flex items-center gap-2">
            <Badge variant="forest" className="font-mono text-[10px]">
              New Scoring Model
            </Badge>
            <span className="text-xs text-muted-foreground">· Version 1</span>
          </div>
          <DialogTitle className="text-base font-semibold">
            Create Custom Scoring Model
          </DialogTitle>
          <DialogDescription>
            Register a new immutable scoring model starting at version 1. You can initialize criteria
            from an existing model template.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-3">
          {errorMessage && (
            <div className="p-3 rounded-lg border border-red-300 bg-red-50 text-red-800 text-xs flex items-start gap-2">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
              <span>{errorMessage}</span>
            </div>
          )}

          <div className="space-y-1">
            <label className="text-xs font-semibold text-foreground">
              Configuration ID <span className="text-red-500">*</span>
            </label>
            <Input
              value={configId}
              onChange={(e) => setConfigId(e.target.value)}
              placeholder="e.g. backend_focused_scoring"
              className="text-xs h-8 font-mono"
            />
            <p className="text-[10px] text-muted-foreground">
              Unique identifier used in evaluation pipeline and API requests.
            </p>
          </div>

          <div className="space-y-1">
            <label className="text-xs font-semibold text-foreground">
              Display Name <span className="text-red-500">*</span>
            </label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Backend & Systems Evaluation Rubric"
              className="text-xs h-8"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-semibold text-foreground">Description</label>
              <Input
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Model rubric intent..."
                className="text-xs h-8"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-semibold text-foreground">Scale Maximum</label>
              <div className="flex items-center gap-1.5">
                <Input
                  type="number"
                  min="1"
                  step="1"
                  value={scaleMax}
                  onChange={(e) => {
                    const raw = e.target.value;
                    if (raw === '') {
                      setScaleMax('');
                      return;
                    }
                    const clean = raw.replace(/^0+(?=\d)/, '');
                    setScaleMax(clean);
                  }}
                  onBlur={() => {
                    if (scaleMax === '' || Number(scaleMax) < 1) {
                      setScaleMax(100);
                    } else {
                      setScaleMax(Number(scaleMax));
                    }
                  }}
                  className="text-xs h-8 font-mono"
                />
                <span className="text-xs text-muted-foreground font-mono">pts</span>
              </div>
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-xs font-semibold text-foreground">
              Base Template
            </label>
            <select
              value={basePresetId}
              onChange={(e) => setBasePresetId(e.target.value)}
              className="w-full h-8 text-xs rounded border border-border bg-card px-2 text-foreground focus:outline-none focus:ring-1 focus:ring-forest-600"
            >
              <option value="__scratch__">✨ Start from Scratch (Clean Custom Model)</option>
              {existingConfigs.map((cfg) => (
                <option key={cfg.config_id} value={cfg.config_id}>
                  Clone from: {cfg.name} ({cfg.criteria?.length || 0} criteria)
                </option>
              ))}
            </select>
            <p className="text-[10px] text-muted-foreground">
              Start with a clean single starter criterion to build custom weights, or clone an existing model.
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" size="sm" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            variant="default"
            size="sm"
            onClick={handleSubmit}
            disabled={createMutation.isPending}
            className="gap-1.5"
          >
            {createMutation.isPending ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Creating...
              </>
            ) : (
              <>
                <Plus className="h-3.5 w-3.5" />
                Create Scoring Model
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
