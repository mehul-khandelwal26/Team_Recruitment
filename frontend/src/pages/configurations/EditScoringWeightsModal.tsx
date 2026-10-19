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
  Plus,
  Trash2,
  ChevronDown,
} from 'lucide-react';
import type { ScoringConfiguration, EvaluationCriterionInput } from '@/types';
import { useUpdateScoringConfigMutation } from '@/hooks/useConfigurations';

interface AvailableSignal {
  signal_key: string;
  name: string;
  description: string;
  criterion_type: 'numeric_range' | 'boolean';
  normalization: any;
  aggregation: string;
}

const AVAILABLE_SIGNALS: AvailableSignal[] = [
  {
    signal_key: 'github_public_repo_count',
    name: 'Public GitHub Repositories',
    description: 'Candidate public repositories on GitHub.',
    criterion_type: 'numeric_range',
    normalization: { method: 'linear_range', linear_range: { min_value: 0, max_value: 20 } },
    aggregation: 'mean',
  },
  {
    signal_key: 'academic_cgpa',
    name: 'Academic CGPA',
    description: 'Academic performance score normalized to scale 10.0.',
    criterion_type: 'numeric_range',
    normalization: { method: 'linear_range', linear_range: { min_value: 5.0, max_value: 10.0 } },
    aggregation: 'mean',
  },
  {
    signal_key: 'resume_experience_years',
    name: 'Years of Experience',
    description: 'Total professional or internship experience duration.',
    criterion_type: 'numeric_range',
    normalization: { method: 'linear_range', linear_range: { min_value: 0, max_value: 5.0 } },
    aggregation: 'mean',
  },
  {
    signal_key: 'github_profile_verified',
    name: 'Verified GitHub Profile',
    description: 'Candidate verified identity and authentic GitHub URL.',
    criterion_type: 'boolean',
    normalization: { method: 'boolean_mapping', boolean_mapping: { true_score: 1.0, false_score: 0.0 } },
    aggregation: 'mean',
  },
  {
    signal_key: 'linkedin_profile_present',
    name: 'LinkedIn Profile Present',
    description: 'Checks whether LinkedIn link was provided.',
    criterion_type: 'boolean',
    normalization: { method: 'boolean_mapping', boolean_mapping: { true_score: 1.0, false_score: 0.0 } },
    aggregation: 'mean',
  },
  {
    signal_key: 'portfolio_link_present',
    name: 'Portfolio Link Present',
    description: 'Checks presence of personal portfolio/website URL.',
    criterion_type: 'boolean',
    normalization: { method: 'boolean_mapping', boolean_mapping: { true_score: 1.0, false_score: 0.0 } },
    aggregation: 'mean',
  },
  {
    signal_key: 'ai_ml_skills_present',
    name: 'AI / ML Skills Demonstrated',
    description: 'Experience in machine learning or AI tooling.',
    criterion_type: 'boolean',
    normalization: { method: 'boolean_mapping', boolean_mapping: { true_score: 1.0, false_score: 0.0 } },
    aggregation: 'any',
  },
  {
    signal_key: 'web3_skills_present',
    name: 'Web3 / Smart Contract Skills',
    description: 'Experience in blockchain or smart contracts.',
    criterion_type: 'boolean',
    normalization: { method: 'boolean_mapping', boolean_mapping: { true_score: 1.0, false_score: 0.0 } },
    aggregation: 'any',
  },
  {
    signal_key: 'hackathon_experience',
    name: 'Prior Hackathon Experience',
    description: 'Candidate has previously participated in hackathons.',
    criterion_type: 'boolean',
    normalization: { method: 'boolean_mapping', boolean_mapping: { true_score: 1.0, false_score: 0.0 } },
    aggregation: 'any',
  },
  {
    signal_key: 'leadership_role',
    name: 'Prior Leadership Experience',
    description: 'Has acted as team captain, lead, or organizer.',
    criterion_type: 'boolean',
    normalization: { method: 'boolean_mapping', boolean_mapping: { true_score: 1.0, false_score: 0.0 } },
    aggregation: 'lead_only',
  },
];

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
  const [isAddMenuOpen, setIsAddMenuOpen] = useState(false);
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
      setIsAddMenuOpen(false);
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

  // Change aggregation method
  const handleAggregationChange = (index: number, agg: string) => {
    setCriteria((prev) => {
      const copy = [...prev];
      copy[index] = {
        ...copy[index],
        aggregation: agg as any,
      };
      return copy;
    });
  };

  // Remove a criterion
  const handleRemoveCriterion = (index: number) => {
    setCriteria((prev) => prev.filter((_, i) => i !== index));
  };

  // Add a new criterion from catalog
  const handleAddCriterion = (sig: AvailableSignal) => {
    // Generate clean unique ID
    const newId = `crit_${sig.signal_key.replace(/[^a-z0-9_]/g, '')}_${Date.now().toString(36).slice(-4)}`;
    const newCrit: EvaluationCriterionInput = {
      criterion_id: newId,
      name: sig.name,
      description: sig.description,
      target_signal_key: sig.signal_key,
      criterion_type: sig.criterion_type as any,
      weight: 1.0,
      is_enabled: true,
      normalization: sig.normalization,
      aggregation: sig.aggregation as any,
      missing_data_policy: 'exclude_and_renormalize' as any,
      config: {},
    };
    setCriteria((prev) => [...prev, newCrit]);
    setIsAddMenuOpen(false);
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

          {/* Criteria Builder Section */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs font-semibold text-foreground">
              <span>Configured Evaluation Criteria</span>
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2 font-mono text-[11px] text-muted-foreground">
                  <span>Active: {activeCriteria.length}/{criteria.length}</span>
                  <span>·</span>
                  <span className="text-forest-700 font-semibold">Total Weight: {totalWeight.toFixed(1)}</span>
                </div>

                <div className="relative">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setIsAddMenuOpen((prev) => !prev)}
                    className="h-7 text-xs gap-1 text-forest-700 border-forest-300 hover:bg-forest-50 font-medium"
                  >
                    <Plus className="h-3.5 w-3.5" />
                    Add Criterion
                    <ChevronDown className="h-3 w-3 ml-0.5" />
                  </Button>

                  {/* Add Criterion Catalog Dropdown */}
                  {isAddMenuOpen && (
                    <div className="absolute right-0 top-8 z-50 w-80 max-h-80 overflow-y-auto bg-card border border-border rounded-lg shadow-lg p-1.5 space-y-1 animate-in fade-in zoom-in-95">
                      <div className="px-2 py-1 text-[10px] font-semibold text-muted-foreground uppercase tracking-wider border-b border-border/60">
                        Available Signals to Score ({AVAILABLE_SIGNALS.length})
                      </div>
                      {AVAILABLE_SIGNALS.map((sig) => (
                        <button
                          key={sig.signal_key}
                          type="button"
                          onClick={() => handleAddCriterion(sig)}
                          className="w-full text-left p-2 rounded-md hover:bg-muted/70 transition-colors group flex flex-col cursor-pointer"
                        >
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-semibold text-foreground group-hover:text-forest-700">
                              {sig.name}
                            </span>
                            <Badge variant="outline" className="text-[9px] font-mono py-0 px-1">
                              {sig.criterion_type}
                            </Badge>
                          </div>
                          <span className="text-[10px] text-muted-foreground line-clamp-1 mt-0.5">
                            {sig.description}
                          </span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>

            {criteria.length === 0 ? (
              <div className="p-8 text-center border border-dashed border-border rounded-lg bg-muted/20">
                <Scale className="h-8 w-8 text-muted-foreground mx-auto mb-2 opacity-50" />
                <p className="text-xs font-semibold text-foreground">No criteria configured</p>
                <p className="text-[11px] text-muted-foreground mt-0.5 max-w-sm mx-auto">
                  Add criteria signals to score team member abilities and calculate weighted composite rankings.
                </p>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setIsAddMenuOpen(true)}
                  className="mt-3 text-xs gap-1.5 text-forest-700 border-forest-300 hover:bg-forest-50"
                >
                  <Plus className="h-3.5 w-3.5" />
                  Add First Criterion
                </Button>
              </div>
            ) : (
              <div className="border border-border rounded-lg overflow-hidden">
                <table className="w-full text-left text-xs">
                  <thead className="bg-muted/60 border-b border-border text-[11px] text-muted-foreground">
                    <tr>
                      <th className="py-2 px-3 w-10 text-center">Active</th>
                      <th className="py-2 px-3">Criterion & Signal</th>
                      <th className="py-2 px-3 w-36">Type / Aggregation</th>
                      <th className="py-2 px-3 w-28 text-right">Weight</th>
                      <th className="py-2 px-3 w-20 text-right">Share</th>
                      <th className="py-2 px-2 w-10 text-center">Action</th>
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
                          <td className="py-2.5 px-3 text-center align-top pt-3">
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
                            {c.description && (
                              <div className="text-[10px] text-muted-foreground line-clamp-1 mt-0.5">
                                {c.description}
                              </div>
                            )}
                          </td>
                          <td className="py-2.5 px-3 align-top pt-2">
                            <div className="text-[10px] text-muted-foreground font-mono">
                              {c.criterion_type}
                            </div>
                            <div className="mt-1 flex items-center gap-1">
                              <span className="text-[10px] text-muted-foreground">agg:</span>
                              <select
                                disabled={!c.is_enabled}
                                value={c.aggregation}
                                onChange={(e) => handleAggregationChange(idx, e.target.value)}
                                className="h-6 text-[11px] font-mono rounded border border-border bg-card px-1.5 text-foreground focus:outline-none focus:ring-1 focus:ring-forest-600 disabled:opacity-50"
                              >
                                <option value="mean">mean</option>
                                <option value="max">max</option>
                                <option value="min">min</option>
                                <option value="sum">sum</option>
                                <option value="lead_only">lead_only</option>
                                <option value="top_k">top_k</option>
                              </select>
                            </div>
                          </td>
                          <td className="py-2.5 px-3 text-right align-top pt-2.5">
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
                          <td className="py-2.5 px-3 text-right font-mono text-[11px] text-muted-foreground align-top pt-3">
                            {c.is_enabled ? `${share}%` : '—'}
                          </td>
                          <td className="py-2.5 px-2 text-center align-top pt-2.5">
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon"
                              onClick={() => handleRemoveCriterion(idx)}
                              className="h-7 w-7 text-muted-foreground hover:text-red-600 hover:bg-red-50"
                              title="Remove criterion"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
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
