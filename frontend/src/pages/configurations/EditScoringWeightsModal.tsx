import React, { useState, useEffect } from 'react';
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
  Scale,
  AlertCircle,
  CheckCircle2,
  Loader2,
  Info,
  GitBranch,
} from 'lucide-react';
import type { ScoringConfiguration, EvaluationCriterionInput } from '@/types';
import { useUpdateScoringConfigMutation } from '@/hooks/useConfigurations';

interface EditScoringWeightsModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  config: ScoringConfiguration;
  onSuccess: (newVersion: number) => void;
}

export const EditScoringWeightsModal: React.FC<EditScoringWeightsModalProps> = ({
  open,
  onOpenChange,
  config,
  onSuccess,
}) => {
  const updateMutation = useUpdateScoringConfigMutation();

  const [description, setDescription] = useState(config.description || '');
  const [scaleMax, setScaleMax] = useState<number>(config.scale_max || 100);
  const [criteria, setCriteria] = useState<EvaluationCriterionInput[]>([]);
  const [showConfirm, setShowConfirm] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Initialize or reset form when config or open changes
  useEffect(() => {
    if (open) {
      setDescription(config.description || '');
      setScaleMax(config.scale_max || 100);
      setCriteria(
        (config.criteria || []).map((c) => ({
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
        }))
      );
      setShowConfirm(false);
      setErrorMessage(null);
    }
  }, [open, config]);

  // Handle weight change for a specific criterion
  const handleWeightChange = (index: number, rawVal: string) => {
    const val = parseFloat(rawVal);
    setCriteria((prev) => {
      const copy = [...prev];
      copy[index] = {
        ...copy[index],
        weight: isNaN(val) ? 0 : Math.max(0, val),
      };
      return copy;
    });
  };

  // Toggle criterion enabled
  const handleToggleEnabled = (index: number) => {
    setCriteria((prev) => {
      const copy = [...prev];
      copy[index] = {
        ...copy[index],
        is_enabled: !copy[index].is_enabled,
      };
      return copy;
    });
  };

  // Calculations
  const activeCriteria = criteria.filter((c) => c.is_enabled);
  const totalWeight = activeCriteria.reduce((sum, c) => sum + (c.weight || 0), 0);

  // Validation
  const validateForm = (): string | null => {
    if (scaleMax <= 0) {
      return 'Scale Max must be strictly greater than 0.';
    }
    for (const c of criteria) {
      if (c.weight < 0) {
        return `Criterion "${c.name}" cannot have a negative weight.`;
      }
    }
    if (activeCriteria.length === 0) {
      return 'At least one criterion must be enabled.';
    }
    if (totalWeight <= 0) {
      return 'Total active weight must be greater than 0.';
    }
    return null;
  };

  const handleReviewClick = () => {
    const err = validateForm();
    if (err) {
      setErrorMessage(err);
      return;
    }
    setErrorMessage(null);
    setShowConfirm(true);
  };

  const handleConfirmSave = async () => {
    setErrorMessage(null);
    try {
      const updated = await updateMutation.mutateAsync({
        configId: config.config_id,
        payload: {
          description,
          scale_max: scaleMax,
          criteria,
        },
      });
      onSuccess(updated.version);
      onOpenChange(false);
    } catch (err: any) {
      const msg =
        err?.response?.data?.detail || err?.message || 'Failed to update scoring configuration.';
      setErrorMessage(typeof msg === 'string' ? msg : JSON.stringify(msg));
      setShowConfirm(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent onClose={() => onOpenChange(false)} className="max-w-3xl">
        <DialogHeader>
          <div className="flex items-center gap-2">
            <Badge variant="forest" className="font-mono text-[10px]">
              Scoring Model Editor
            </Badge>
            <span className="text-xs text-muted-foreground flex items-center gap-1">
              <GitBranch className="h-3 w-3" />
              Creates Version {config.version + 1}
            </span>
          </div>
          <DialogTitle className="text-base font-semibold">
            Edit Weights & Criteria: {config.name}
          </DialogTitle>
          <DialogDescription>
            Adjust relative weights and criteria parameters. Saving produces an immutable new version
            leaving previous evaluation results completely reproducible.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-3 overflow-y-auto max-h-[60vh] pr-1">
          {errorMessage && (
            <div className="p-3 rounded-lg border border-red-300 bg-red-50 text-red-800 text-xs flex items-start gap-2">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Model Summary & Scale Max */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-3 bg-muted/40 rounded-lg border border-border/70">
            <div className="sm:col-span-2 space-y-1">
              <label className="text-xs font-semibold text-foreground">Model Description</label>
              <Input
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe scoring rubric rationale..."
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
                  onChange={(e) => setScaleMax(parseFloat(e.target.value) || 0)}
                  className="text-xs h-8 font-mono"
                />
                <span className="text-xs text-muted-foreground font-mono">pts</span>
              </div>
            </div>
          </div>

          {/* Notice about dynamic normalization */}
          <div className="p-2.5 rounded-md bg-forest-50/70 border border-forest-200/80 text-forest-800 text-xs flex items-start gap-2">
            <Info className="h-4 w-4 shrink-0 text-forest-700 mt-0.5" />
            <div className="space-y-0.5 leading-relaxed text-[11px]">
              <span className="font-semibold">Dynamic Relative Normalization:</span> The scoring
              engine does not require weights to sum to 100. Weights define relative importance; if
              optional signals are missing or excluded, remaining weights are automatically
              renormalized by the server.
            </div>
          </div>

          {/* Criteria Table */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs font-semibold text-foreground">
              <span>Configured Evaluation Criteria</span>
              <div className="flex items-center gap-2 font-mono text-[11px] text-muted-foreground">
                <span>Active: {activeCriteria.length}/{criteria.length}</span>
                <span>·</span>
                <span className="text-forest-700 font-semibold">Total Weight: {totalWeight.toFixed(1)}</span>
              </div>
            </div>

            <div className="border border-border rounded-lg overflow-hidden">
              <table className="w-full text-left text-xs">
                <thead className="bg-muted/60 border-b border-border text-[11px] text-muted-foreground">
                  <tr>
                    <th className="py-2 px-3 w-10 text-center">Active</th>
                    <th className="py-2 px-3">Criterion & Signal</th>
                    <th className="py-2 px-3">Type / Aggregation</th>
                    <th className="py-2 px-3 w-28 text-right">Weight</th>
                    <th className="py-2 px-3 w-20 text-right">Share</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {criteria.map((c, idx) => {
                    const share =
                      c.is_enabled && totalWeight > 0
                        ? ((c.weight / totalWeight) * 100).toFixed(1)
                        : '0.0';

                    return (
                      <tr
                        key={c.criterion_id}
                        className={`hover:bg-muted/30 transition-colors ${
                          !c.is_enabled ? 'opacity-50 bg-muted/10' : ''
                        }`}
                      >
                        <td className="py-2.5 px-3 text-center">
                          <input
                            type="checkbox"
                            checked={c.is_enabled}
                            onChange={() => handleToggleEnabled(idx)}
                            className="h-3.5 w-3.5 rounded border-border text-forest-700 focus:ring-forest-600 cursor-pointer"
                          />
                        </td>
                        <td className="py-2.5 px-3">
                          <div className="font-semibold text-foreground">{c.name}</div>
                          <div className="text-[10px] font-mono text-muted-foreground flex items-center gap-1 mt-0.5">
                            <span>signal:</span>
                            <span className="text-forest-700 bg-forest-50 px-1 rounded">
                              {c.target_signal_key}
                            </span>
                          </div>
                        </td>
                        <td className="py-2.5 px-3">
                          <div className="text-[11px] text-foreground font-medium">
                            {c.criterion_type}
                          </div>
                          <div className="text-[10px] text-muted-foreground">
                            agg: <span className="font-mono">{c.aggregation}</span>
                          </div>
                        </td>
                        <td className="py-2.5 px-3 text-right">
                          <Input
                            type="number"
                            min="0"
                            step="0.5"
                            disabled={!c.is_enabled}
                            value={c.weight}
                            onChange={(e) => handleWeightChange(idx, e.target.value)}
                            className="h-7 w-24 text-right font-mono text-xs ml-auto"
                          />
                        </td>
                        <td className="py-2.5 px-3 text-right font-mono text-[11px] text-muted-foreground">
                          {c.is_enabled ? `${share}%` : '—'}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Confirmation Box (when showConfirm is active) */}
          {showConfirm && (
            <div className="p-3.5 rounded-lg border border-amber-300 bg-amber-50/80 text-amber-900 space-y-2 animate-in fade-in">
              <div className="flex items-start gap-2">
                <AlertCircle className="h-4 w-4 shrink-0 text-amber-700 mt-0.5" />
                <div className="space-y-1">
                  <p className="text-xs font-bold text-amber-900">
                    Confirm Version Creation: Version {config.version + 1}
                  </p>
                  <p className="text-[11px] leading-relaxed text-amber-800">
                    This modification will create an incremented, immutable Version {config.version + 1} of{' '}
                    <span className="font-mono font-semibold">{config.config_id}</span>. Existing evaluation runs
                    will continue referencing their respective historical version snapshots.
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>

        <DialogFooter>
          {showConfirm ? (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowConfirm(false)}
                disabled={updateMutation.isPending}
              >
                Back to Edit
              </Button>
              <Button
                variant="default"
                size="sm"
                onClick={handleConfirmSave}
                disabled={updateMutation.isPending}
                className="gap-1.5"
              >
                {updateMutation.isPending ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    Saving Version {config.version + 1}...
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    Confirm & Save Version {config.version + 1}
                  </>
                )}
              </Button>
            </>
          ) : (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={() => onOpenChange(false)}
              >
                Cancel
              </Button>
              <Button
                variant="default"
                size="sm"
                onClick={handleReviewClick}
                className="gap-1.5"
              >
                <Scale className="h-3.5 w-3.5" />
                Review & Save Changes
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
