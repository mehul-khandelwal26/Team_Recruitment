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
  ChevronUp,
  Sliders,
  UserCheck,
} from 'lucide-react';
import type { ScoringConfiguration, EvaluationCriterionInput } from '@/types';
import { useUpdateScoringConfigMutation } from '@/hooks/useConfigurations';

interface AvailableSignal {
  signal_key: string;
  name: string;
  description: string;
  criterion_type: 'numeric_range' | 'boolean' | 'categorical';
  normalization: any;
  aggregation: 'mean' | 'max' | 'min' | 'sum' | 'lead_only' | 'top_k';
  top_k_value?: number;
}

// Aligned 100% with backend default_signal_registry
const AVAILABLE_SIGNALS: AvailableSignal[] = [
  {
    signal_key: 'github_public_repo_count',
    name: 'Public GitHub Repositories',
    description: 'Total count of public repositories on candidate profile.',
    criterion_type: 'numeric_range',
    normalization: { linear_range: { min_value: 0, max_value: 20 } },
    aggregation: 'mean',
  },
  {
    signal_key: 'academic_cgpa',
    name: 'Academic Score (CGPA / CPI)',
    description: 'Validated academic score normalized to 10-point scale.',
    criterion_type: 'numeric_range',
    normalization: { linear_range: { min_value: 6.0, max_value: 10.0 } },
    aggregation: 'mean',
  },
  {
    signal_key: 'normalized_cgpa_10_scale',
    name: 'Normalized CGPA (10-Point)',
    description: 'Scale-checked normalized CGPA across diverse grading scales.',
    criterion_type: 'numeric_range',
    normalization: { linear_range: { min_value: 6.0, max_value: 10.0 } },
    aggregation: 'mean',
  },
  {
    signal_key: 'resume_experience_years',
    name: 'Years of Experience',
    description: 'Duration of professional and internship experience from resume.',
    criterion_type: 'numeric_range',
    normalization: { linear_range: { min_value: 0.0, max_value: 5.0 } },
    aggregation: 'mean',
  },
  {
    signal_key: 'github_profile_verified',
    name: 'Verified GitHub Profile',
    description: 'Verifies candidate GitHub profile exists and is reachable.',
    criterion_type: 'boolean',
    normalization: { boolean_mapping: { true_score: 1.0, false_score: 0.0 } },
    aggregation: 'max',
  },
  {
    signal_key: 'portfolio_site_reachable',
    name: 'Portfolio Site Reachable',
    description: 'Verifies candidate personal portfolio website is online.',
    criterion_type: 'boolean',
    normalization: { boolean_mapping: { true_score: 1.0, false_score: 0.0 } },
    aggregation: 'max',
  },
  {
    signal_key: 'portfolio_has_live_projects',
    name: 'Live Demonstrable Projects',
    description: 'Identifies demonstrable live projects on candidate portfolio.',
    criterion_type: 'boolean',
    normalization: { boolean_mapping: { true_score: 1.0, false_score: 0.0 } },
    aggregation: 'max',
  },
  {
    signal_key: 'academic_year',
    name: 'Academic Seniority / Year',
    description: 'Academic standing progression (1st Year to 4th Year/Postgraduate).',
    criterion_type: 'categorical',
    normalization: {
      categorical_mapping: {
        category_scores: {
          '1st Year': 0.25,
          '2nd Year': 0.5,
          '3rd Year': 0.75,
          '4th Year': 1.0,
          'Postgraduate': 1.0,
        },
        default_score: 0.5,
        case_sensitive: false,
      },
    },
    aggregation: 'mean',
  },
  {
    signal_key: 'resume_degree_level',
    name: 'Highest Degree Level',
    description: 'Highest academic degree level identified from resume text.',
    criterion_type: 'categorical',
    normalization: {
      categorical_mapping: {
        category_scores: {
          BCA: 0.7,
          'B.Tech': 0.85,
          'M.Tech': 0.95,
          'Ph.D.': 1.0,
        },
        default_score: 0.75,
        case_sensitive: false,
      },
    },
    aggregation: 'max',
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

  const [name, setName] = useState(config.name || '');
  const [description, setDescription] = useState(config.description || '');
  const [scaleMax, setScaleMax] = useState<number>(config.scale_max || 100);
  const [scoreIneligibleTeams, setScoreIneligibleTeams] = useState<boolean>(
    config.score_ineligible_teams ?? true
  );
  const [leadField, setLeadField] = useState(config.lead_field || 'role');
  const [leadValues, setLeadValues] = useState(
    (config.lead_values || ['lead', 'team lead', 'captain', 'leader']).join(', ')
  );
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  const [criteria, setCriteria] = useState<EvaluationCriterionInput[]>([]);
  const [expandedCritIndex, setExpandedCritIndex] = useState<number | null>(null);
  const [newCatName, setNewCatName] = useState<Record<number, string>>({});
  const [newCatScore, setNewCatScore] = useState<Record<number, string>>({});
  const [isAddMenuOpen, setIsAddMenuOpen] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Initialize or reset form when config or open changes
  useEffect(() => {
    if (open) {
      setName(config.name || '');
      setDescription(config.description || '');
      setScaleMax(config.scale_max || 100);
      setScoreIneligibleTeams(config.score_ineligible_teams ?? true);
      setLeadField(config.lead_field || 'role');
      setLeadValues((config.lead_values || ['lead', 'team lead', 'captain', 'leader']).join(', '));
      setIsSettingsOpen(false);

      setCriteria(
        (config.criteria || []).map((c) => {
          let norm = c.normalization ? JSON.parse(JSON.stringify(c.normalization)) : {};
          if (c.criterion_type === 'categorical') {
            if (
              !norm.categorical_mapping ||
              !norm.categorical_mapping.category_scores ||
              Object.keys(norm.categorical_mapping.category_scores).length === 0
            ) {
              const foundSig = AVAILABLE_SIGNALS.find((s) => s.signal_key === c.target_signal_key);
              norm = {
                ...norm,
                categorical_mapping: foundSig?.normalization?.categorical_mapping
                  ? JSON.parse(JSON.stringify(foundSig.normalization.categorical_mapping))
                  : {
                      category_scores: { 'Option A': 0.5, 'Option B': 1.0 },
                      default_score: 0.5,
                      case_sensitive: false,
                    },
              };
            }
          }
          return {
            criterion_id: c.criterion_id,
            name: c.name,
            description: c.description,
            target_signal_key: c.target_signal_key,
            criterion_type: c.criterion_type as any,
            weight: c.weight,
            is_enabled: c.is_enabled,
            normalization: norm,
            aggregation: c.aggregation as any,
            top_k_value: c.top_k_value,
            missing_data_policy: (c.missing_data_policy as any) || 'exclude_and_renormalize',
            confidence_adjustment: c.confidence_adjustment,
            config: c.config || {},
          };
        })
      );
      setExpandedCritIndex(null);
      setNewCatName({});
      setNewCatScore({});
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
      const prevCrit = copy[index];
      copy[index] = {
        ...prevCrit,
        aggregation: agg as any,
        top_k_value: agg === 'top_k' ? prevCrit.top_k_value || 2 : prevCrit.top_k_value,
      };
      return copy;
    });
  };

  // Change top_k_value
  const handleTopKChange = (index: number, kVal: number) => {
    setCriteria((prev) => {
      const copy = [...prev];
      copy[index] = {
        ...copy[index],
        top_k_value: Math.max(1, kVal),
      };
      return copy;
    });
  };

  // Change missing data policy
  const handleMissingDataPolicyChange = (index: number, policy: string) => {
    setCriteria((prev) => {
      const copy = [...prev];
      copy[index] = {
        ...copy[index],
        missing_data_policy: policy as any,
      };
      return copy;
    });
  };

  // Change linear range bounds
  const handleLinearRangeChange = (index: number, bound: 'min' | 'max', val: number) => {
    setCriteria((prev) => {
      const copy = [...prev];
      const crit = copy[index];
      const norm = crit.normalization || {};
      const lr = norm.linear_range || { min_value: 0, max_value: 10 };
      copy[index] = {
        ...crit,
        normalization: {
          ...norm,
          linear_range: {
            ...lr,
            [bound === 'min' ? 'min_value' : 'max_value']: val,
          },
        },
      };
      return copy;
    });
  };

  // Categorical mapping: change single category score
  const handleCategoryScoreChange = (index: number, catKey: string, rawVal: string) => {
    const val = parseFloat(rawVal);
    const score = isNaN(val) ? 0 : Math.min(1.0, Math.max(0.0, val));
    setCriteria((prev) => {
      const copy = [...prev];
      const crit = copy[index];
      const norm = crit.normalization || {};
      const catMap = norm.categorical_mapping || {
        category_scores: {} as Record<string, number>,
        default_score: 0.5,
        case_sensitive: false,
      };
      copy[index] = {
        ...crit,
        normalization: {
          ...norm,
          categorical_mapping: {
            ...catMap,
            case_sensitive: catMap.case_sensitive ?? false,
            category_scores: {
              ...(catMap.category_scores || {}),
              [catKey]: score,
            },
          },
        },
      };
      return copy;
    });
  };

  // Categorical mapping: add category
  const handleAddCategory = (index: number, catKey: string, rawScore: string) => {
    const cleanKey = catKey.trim();
    if (!cleanKey) return;
    const val = parseFloat(rawScore);
    const score = isNaN(val) ? 0.5 : Math.min(1.0, Math.max(0.0, val));
    setCriteria((prev) => {
      const copy = [...prev];
      const crit = copy[index];
      const norm = crit.normalization || {};
      const catMap = norm.categorical_mapping || {
        category_scores: {} as Record<string, number>,
        default_score: 0.5,
        case_sensitive: false,
      };
      copy[index] = {
        ...crit,
        normalization: {
          ...norm,
          categorical_mapping: {
            ...catMap,
            case_sensitive: catMap.case_sensitive ?? false,
            category_scores: {
              ...(catMap.category_scores || {}),
              [cleanKey]: score,
            },
          },
        },
      };
      return copy;
    });
  };

  // Categorical mapping: remove category
  const handleRemoveCategory = (index: number, catKey: string) => {
    setCriteria((prev) => {
      const copy = [...prev];
      const crit = copy[index];
      const norm = crit.normalization || {};
      const catMap = norm.categorical_mapping || {
        category_scores: {} as Record<string, number>,
        default_score: 0.5,
        case_sensitive: false,
      };
      const currentScores: Record<string, number> = { ...(catMap.category_scores || {}) };
      delete currentScores[catKey];
      copy[index] = {
        ...crit,
        normalization: {
          ...norm,
          categorical_mapping: {
            ...catMap,
            case_sensitive: catMap.case_sensitive ?? false,
            category_scores: currentScores,
          },
        },
      };
      return copy;
    });
  };

  // Categorical mapping: change default fallback score
  const handleCategoryDefaultScoreChange = (index: number, rawVal: string) => {
    const val = parseFloat(rawVal);
    const defScore = isNaN(val) ? 0.5 : Math.min(1.0, Math.max(0.0, val));
    setCriteria((prev) => {
      const copy = [...prev];
      const crit = copy[index];
      const norm = crit.normalization || {};
      const catMap = norm.categorical_mapping || {
        category_scores: {} as Record<string, number>,
        default_score: 0.5,
        case_sensitive: false,
      };
      copy[index] = {
        ...crit,
        normalization: {
          ...norm,
          categorical_mapping: {
            ...catMap,
            case_sensitive: catMap.case_sensitive ?? false,
            default_score: defScore,
          },
        },
      };
      return copy;
    });
  };

  // Remove a criterion
  const handleRemoveCriterion = (index: number) => {
    setCriteria((prev) => prev.filter((_, i) => i !== index));
    if (expandedCritIndex === index) setExpandedCritIndex(null);
  };

  // Add a new criterion from catalog
  const handleAddCriterion = (sig: AvailableSignal) => {
    const newId = `crit_${sig.signal_key.replace(/[^a-z0-9_]/g, '')}_${Date.now().toString(36).slice(-4)}`;
    const newCrit: EvaluationCriterionInput = {
      criterion_id: newId,
      name: sig.name,
      description: sig.description,
      target_signal_key: sig.signal_key,
      criterion_type: sig.criterion_type as any,
      weight: 1.0,
      is_enabled: true,
      normalization: JSON.parse(JSON.stringify(sig.normalization)),
      aggregation: sig.aggregation as any,
      top_k_value: sig.aggregation === 'top_k' ? 2 : undefined,
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
    if (!name.trim()) {
      return 'Model Name cannot be left empty.';
    }
    if (scaleMax <= 0) {
      return 'Scale Max must be strictly greater than 0.';
    }
    if (activeCriteria.length === 0) {
      return 'At least one criterion must be enabled in the scoring model.';
    }
    if (totalWeight <= 0) {
      return 'Total active weight must be greater than 0.';
    }

    for (const c of activeCriteria) {
      if (c.weight < 0) {
        return `Criterion "${c.name}" cannot have a negative weight.`;
      }
      if (c.aggregation === 'top_k') {
        if (!c.top_k_value || c.top_k_value < 1) {
          return `Criterion "${c.name}" uses top_k aggregation and requires top_k_value >= 1.`;
        }
      }
      if (c.criterion_type === 'numeric_range' && c.normalization?.linear_range) {
        const { min_value, max_value } = c.normalization.linear_range;
        if (typeof min_value === 'number' && typeof max_value === 'number') {
          if (max_value <= min_value) {
            return `Criterion "${c.name}": max_value (${max_value}) must be strictly greater than min_value (${min_value}).`;
          }
        }
      }
      if (c.criterion_type === 'categorical') {
        const catMap = c.normalization?.categorical_mapping;
        const catScores = catMap?.category_scores || {};
        if (Object.keys(catScores).length === 0) {
          return `Criterion "${c.name}": categorical mapping must have at least one category score defined.`;
        }
        for (const [catName, score] of Object.entries(catScores)) {
          if (typeof score !== 'number' || score < 0.0 || score > 1.0) {
            return `Criterion "${c.name}": score for category "${catName}" must be between 0.0 and 1.0.`;
          }
        }
      }
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
      const parsedLeadValues = leadValues
        .split(',')
        .map((s) => s.trim().toLowerCase())
        .filter(Boolean);

      const cleanedCriteria = criteria.map((c) => ({
        ...c,
        top_k_value: c.aggregation === 'top_k' ? c.top_k_value || 2 : undefined,
      }));

      const updated = await updateMutation.mutateAsync({
        configId: config.config_id,
        payload: {
          name: name.trim() || config.name,
          description: description.trim(),
          scale_max: scaleMax,
          score_ineligible_teams: scoreIneligibleTeams,
          lead_field: leadField.trim() || 'role',
          lead_values: parsedLeadValues.length > 0 ? parsedLeadValues : ['lead', 'team lead'],
          criteria: cleanedCriteria,
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
      <DialogContent onClose={() => onOpenChange(false)} className="max-w-4xl max-h-[92vh] flex flex-col">
        <DialogHeader className="shrink-0">
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
            Edit Weights & Rubric: {config.name}
          </DialogTitle>
          <DialogDescription>
            Adjust relative weights, normalization bounds, and member aggregations. Saving creates an immutable new version preserving historical auditability.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2 overflow-y-auto flex-1 pr-1">
          {errorMessage && (
            <div className="p-3 rounded-lg border border-red-300 bg-red-50 text-red-800 text-xs flex items-start gap-2">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Model Identification & Scale */}
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 p-3 bg-muted/40 rounded-lg border border-border/70">
            <div className="sm:col-span-2 space-y-1">
              <label className="text-xs font-semibold text-foreground">Scoring Model Name</label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Balanced Technical Evaluation..."
                className="text-xs h-8 font-medium"
              />
            </div>
            <div className="sm:col-span-2 space-y-1">
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
                <span className="text-xs text-muted-foreground font-mono">points</span>
              </div>
            </div>
            <div className="sm:col-span-4 space-y-1">
              <label className="text-xs font-semibold text-foreground">Model Description & Rubric Rationale</label>
              <Input
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe scoring rubric rationale..."
                className="text-xs h-8"
              />
            </div>
          </div>

          {/* Collapsible Model & Team Lead Resolution Settings */}
          <div className="border border-border/80 rounded-lg overflow-hidden bg-card">
            <button
              type="button"
              onClick={() => setIsSettingsOpen((prev) => !prev)}
              className="w-full flex items-center justify-between p-3 bg-muted/30 hover:bg-muted/50 text-xs font-semibold text-foreground transition-colors cursor-pointer"
            >
              <div className="flex items-center gap-2">
                <Sliders className="h-3.5 w-3.5 text-forest-700" />
                <span>Eligibility Policy & Team Lead Settings</span>
                <span className="text-[10px] font-normal text-muted-foreground">
                  (Ineligible team scoring, lead resolution)
                </span>
              </div>
              {isSettingsOpen ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
            </button>

            {isSettingsOpen && (
              <div className="p-3 border-t border-border/70 space-y-3 bg-card text-xs">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="text-[11px] font-medium text-foreground flex items-center gap-1">
                      <UserCheck className="h-3.5 w-3.5 text-forest-700" />
                      Team Lead Field Key
                    </label>
                    <Input
                      value={leadField}
                      onChange={(e) => setLeadField(e.target.value)}
                      placeholder="e.g. role, captain, designation"
                      className="h-7 text-xs font-mono"
                    />
                    <p className="text-[10px] text-muted-foreground">
                      Registration attribute identifying member role for lead_only criteria.
                    </p>
                  </div>

                  <div className="space-y-1">
                    <label className="text-[11px] font-medium text-foreground">
                      Lead Identifier Values (comma-separated)
                    </label>
                    <Input
                      value={leadValues}
                      onChange={(e) => setLeadValues(e.target.value)}
                      placeholder="lead, team lead, captain, leader"
                      className="h-7 text-xs font-mono"
                    />
                    <p className="text-[10px] text-muted-foreground">
                      Case-insensitive values designating the team lead.
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2 pt-1 border-t border-border/40">
                  <input
                    type="checkbox"
                    id="score-ineligible"
                    checked={scoreIneligibleTeams}
                    onChange={(e) => setScoreIneligibleTeams(e.target.checked)}
                    className="h-3.5 w-3.5 rounded border-border text-forest-700 focus:ring-forest-600 cursor-pointer"
                  />
                  <label htmlFor="score-ineligible" className="text-xs text-foreground cursor-pointer select-none">
                    <span className="font-medium">Score Ineligible Teams: </span>
                    <span className="text-muted-foreground">
                      Calculate informational scores for ineligible teams (if unchecked, ineligible teams receive 0.0 / DISQUALIFIED).
                    </span>
                  </label>
                </div>
              </div>
            )}
          </div>

          {/* Dynamic Normalization Notice */}
          <div className="p-2.5 rounded-md bg-forest-50/70 border border-forest-200/80 text-forest-800 text-xs flex items-start gap-2">
            <Info className="h-4 w-4 shrink-0 text-forest-700 mt-0.5" />
            <div className="space-y-0.5 leading-relaxed text-[11px]">
              <span className="font-semibold">Dynamic Relative Normalization:</span> Criteria weights define relative importance (e.g. 35 vs 20) and are automatically renormalized to {scaleMax} points. If a member lacks optional signals, remaining weights rebalance transparently.
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
                  <span className="text-forest-700 font-semibold">Total Relative Weight: {totalWeight.toFixed(1)}</span>
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
                    <div className="absolute right-0 top-8 z-50 w-84 max-h-80 overflow-y-auto bg-card border border-border rounded-lg shadow-lg p-1.5 space-y-1 animate-in fade-in zoom-in-95">
                      <div className="px-2 py-1 text-[10px] font-semibold text-muted-foreground uppercase tracking-wider border-b border-border/60">
                        Registered Signals ({AVAILABLE_SIGNALS.length})
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
                          <span
                            className="text-[10px] text-muted-foreground line-clamp-1 mt-0.5 cursor-help"
                            title={sig.description}
                          >
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
                      <th className="py-2 px-3 w-40">Aggregation</th>
                      <th className="py-2 px-3 w-36">Missing Policy</th>
                      <th className="py-2 px-3 w-28 text-right">Weight</th>
                      <th className="py-2 px-3 w-16 text-right">Share</th>
                      <th className="py-2 px-2 w-10 text-center">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {criteria.map((c, idx) => {
                      const share =
                        c.is_enabled && totalWeight > 0
                          ? ((c.weight / totalWeight) * 100).toFixed(1)
                          : '0.0';
                      const isExpanded = expandedCritIndex === idx;
                      const hasLinearRange = c.criterion_type === 'numeric_range' && c.normalization?.linear_range;

                      return (
                        <React.Fragment key={c.criterion_id}>
                          <tr
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
                              <div className="flex items-center gap-1.5">
                                <span className="font-semibold text-foreground">{c.name}</span>
                                <Badge variant="forest" className="font-mono text-[9px] py-0 px-1">
                                  {c.criterion_type}
                                </Badge>
                              </div>
                              <div className="text-[10px] font-mono text-muted-foreground flex items-center gap-1 mt-0.5">
                                <span>signal:</span>
                                <span className="text-forest-700 bg-forest-50 px-1 rounded">
                                  {c.target_signal_key}
                                </span>
                              </div>
                              {c.description && (
                                <div
                                  className="text-[10px] text-muted-foreground line-clamp-1 mt-0.5 cursor-help hover:text-foreground transition-colors"
                                  title={c.description}
                                >
                                  {c.description}
                                </div>
                              )}

                              {hasLinearRange && (
                                <button
                                  type="button"
                                  onClick={() => setExpandedCritIndex(isExpanded ? null : idx)}
                                  className="text-[10px] text-forest-700 hover:text-forest-800 font-medium flex items-center gap-0.5 mt-1 cursor-pointer"
                                >
                                  <Sliders className="h-2.5 w-2.5" />
                                  <span>
                                    {isExpanded ? 'Hide Range Bounds' : `Range: [${c.normalization?.linear_range?.min_value ?? 0} → ${c.normalization?.linear_range?.max_value ?? 10}]`}
                                  </span>
                                </button>
                              )}

                              {c.criterion_type === 'categorical' && (
                                <button
                                  type="button"
                                  onClick={() => setExpandedCritIndex(isExpanded ? null : idx)}
                                  className="text-[10px] text-forest-700 hover:text-forest-800 font-medium flex items-center gap-0.5 mt-1 cursor-pointer"
                                >
                                  <Sliders className="h-2.5 w-2.5" />
                                  <span>
                                    {isExpanded
                                      ? 'Hide Category Rubric'
                                      : `Category Rubric: [${Object.keys(c.normalization?.categorical_mapping?.category_scores || {}).length} categories]`}
                                  </span>
                                </button>
                              )}
                            </td>
                            <td className="py-2.5 px-3 align-top pt-2">
                              <select
                                disabled={!c.is_enabled}
                                value={c.aggregation}
                                onChange={(e) => handleAggregationChange(idx, e.target.value)}
                                className="h-6 w-full text-[11px] font-mono rounded border border-border bg-card px-1.5 text-foreground focus:outline-none focus:ring-1 focus:ring-forest-600 disabled:opacity-50"
                              >
                                <option value="mean">mean</option>
                                <option value="max">max</option>
                                <option value="min">min</option>
                                <option value="sum">sum</option>
                                <option value="lead_only">lead_only</option>
                                <option value="top_k">top_k</option>
                              </select>

                              {c.aggregation === 'top_k' && (
                                <div className="flex items-center gap-1 mt-1 bg-amber-50/70 p-1 rounded border border-amber-200">
                                  <span className="text-[10px] font-semibold text-amber-900 font-mono">k =</span>
                                  <Input
                                    type="number"
                                    min="1"
                                    disabled={!c.is_enabled}
                                    value={c.top_k_value ?? 2}
                                    onChange={(e) => handleTopKChange(idx, parseInt(e.target.value, 10) || 1)}
                                    className="h-5 w-14 text-[10px] font-mono px-1 py-0 bg-white"
                                    title="Top K highest members"
                                  />
                                </div>
                              )}
                            </td>
                            <td className="py-2.5 px-3 align-top pt-2">
                              <select
                                disabled={!c.is_enabled}
                                value={c.missing_data_policy || 'exclude_and_renormalize'}
                                onChange={(e) => handleMissingDataPolicyChange(idx, e.target.value)}
                                className="h-6 w-full text-[10px] font-mono rounded border border-border bg-card px-1 text-foreground focus:outline-none focus:ring-1 focus:ring-forest-600 disabled:opacity-50"
                                title="Missing Data Policy"
                              >
                                <option value="exclude_and_renormalize">exclude & renormalize</option>
                                <option value="zero_score">zero score (0.0)</option>
                              </select>
                            </td>
                            <td className="py-2.5 px-3 text-right align-top pt-2">
                              <Input
                                type="number"
                                min="0"
                                step="0.5"
                                disabled={!c.is_enabled}
                                value={c.weight}
                                onChange={(e) => handleWeightChange(idx, e.target.value)}
                                className="h-6 w-20 text-right font-mono text-xs ml-auto"
                              />
                            </td>
                            <td className="py-2.5 px-3 text-right font-mono text-[11px] text-muted-foreground align-top pt-2.5">
                              {c.is_enabled ? `${share}%` : '—'}
                            </td>
                            <td className="py-2.5 px-2 text-center align-top pt-2">
                              <Button
                                type="button"
                                variant="ghost"
                                size="icon"
                                onClick={() => handleRemoveCriterion(idx)}
                                className="h-6 w-6 text-muted-foreground hover:text-red-600 hover:bg-red-50"
                                title="Remove criterion"
                              >
                                <Trash2 className="h-3 w-3" />
                              </Button>
                            </td>
                          </tr>

                          {/* Expanded Normalization Bounds Editor Row */}
                          {isExpanded && hasLinearRange && (
                            <tr className="bg-muted/30">
                              <td colSpan={7} className="p-2.5 border-t border-border/60">
                                <div className="flex items-center gap-4 text-xs bg-card p-2 rounded border border-border max-w-md">
                                  <span className="font-semibold text-foreground text-[11px]">
                                    Linear Range Mapping:
                                  </span>
                                  <div className="flex items-center gap-1.5">
                                    <span className="text-[10px] text-muted-foreground font-medium">Min (0.0):</span>
                                    <Input
                                      type="number"
                                      step="0.5"
                                      value={c.normalization?.linear_range?.min_value ?? 0}
                                      onChange={(e) =>
                                        handleLinearRangeChange(idx, 'min', parseFloat(e.target.value) || 0)
                                      }
                                      className="h-7 w-20 text-xs font-mono text-center px-1.5 focus:ring-forest-600"
                                    />
                                  </div>
                                  <div className="flex items-center gap-1.5">
                                    <span className="text-[10px] text-muted-foreground font-medium">Max (1.0):</span>
                                    <Input
                                      type="number"
                                      step="0.5"
                                      value={c.normalization?.linear_range?.max_value ?? 10}
                                      onChange={(e) =>
                                        handleLinearRangeChange(idx, 'max', parseFloat(e.target.value) || 1)
                                      }
                                      className="h-7 w-20 text-xs font-mono text-center px-1.5 focus:ring-forest-600"
                                    />
                                  </div>
                                </div>
                              </td>
                            </tr>
                          )}

                          {/* Expanded Categorical Rubric Editor Row */}
                          {isExpanded && c.criterion_type === 'categorical' && (
                            <tr className="bg-muted/30">
                              <td colSpan={7} className="p-3 border-t border-border/60">
                                <div className="bg-card p-3 rounded-lg border border-border space-y-3">
                                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border/60 pb-2">
                                    <div className="flex items-center gap-2">
                                      <Badge variant="forest" className="font-mono text-[9px]">
                                        Categorical Scoring Rubric
                                      </Badge>
                                      <span className="text-[11px] font-semibold text-foreground">
                                        Map discrete values to normalized scores [0.0 to 1.0]
                                      </span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                      <span className="text-[10px] text-muted-foreground font-medium">Default Fallback Score:</span>
                                      <Input
                                        type="number"
                                        step="0.05"
                                        min="0"
                                        max="1"
                                        value={c.normalization?.categorical_mapping?.default_score ?? 0.5}
                                        onChange={(e) => handleCategoryDefaultScoreChange(idx, e.target.value)}
                                        className="h-7 w-20 text-xs font-mono text-center px-1.5 focus:ring-forest-600"
                                        title="Fallback score for unlisted categories (0.0 to 1.0)"
                                      />
                                    </div>
                                  </div>

                                  {/* Existing Category Scores Grid */}
                                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5">
                                    {Object.entries(c.normalization?.categorical_mapping?.category_scores || {}).map(
                                      ([catKey, catScore]) => {
                                        const catCount = Object.keys(c.normalization?.categorical_mapping?.category_scores || {}).length;
                                        return (
                                          <div
                                            key={catKey}
                                            className="flex items-center justify-between gap-2 p-2 rounded-md border border-border bg-muted/20 text-xs"
                                          >
                                            <span className="font-semibold text-foreground truncate min-w-[60px]" title={catKey}>
                                              {catKey}
                                            </span>
                                            <div className="flex items-center gap-1.5 shrink-0">
                                              <Input
                                                type="number"
                                                step="0.05"
                                                min="0"
                                                max="1"
                                                value={catScore as number}
                                                onChange={(e) => handleCategoryScoreChange(idx, catKey, e.target.value)}
                                                className="h-7 w-20 text-xs font-mono text-center px-1.5 focus:ring-forest-600"
                                                title={`Score for ${catKey} (0.0 to 1.0)`}
                                              />
                                              <Button
                                                type="button"
                                                variant="ghost"
                                                size="icon"
                                                disabled={catCount <= 1}
                                                onClick={() => handleRemoveCategory(idx, catKey)}
                                                className="h-6 w-6 text-muted-foreground hover:text-red-600 disabled:opacity-30"
                                                title={`Delete category ${catKey}`}
                                              >
                                                <Trash2 className="h-3.5 w-3.5" />
                                              </Button>
                                            </div>
                                          </div>
                                        );
                                      }
                                    )}
                                  </div>

                                  {/* Add Category Form */}
                                  <div className="flex items-center gap-2 pt-2 border-t border-border/50">
                                    <Input
                                      placeholder="New category name (e.g. Master's, 5th Year)..."
                                      value={newCatName[idx] || ''}
                                      onChange={(e) => setNewCatName((prev) => ({ ...prev, [idx]: e.target.value }))}
                                      className="h-7 text-xs flex-1"
                                    />
                                    <Input
                                      type="number"
                                      step="0.05"
                                      min="0"
                                      max="1"
                                      placeholder="Score (0.0 - 1.0)"
                                      value={newCatScore[idx] ?? '1.0'}
                                      onChange={(e) => setNewCatScore((prev) => ({ ...prev, [idx]: e.target.value }))}
                                      className="h-7 w-28 text-xs font-mono text-center px-1.5 focus:ring-forest-600"
                                    />
                                    <Button
                                      type="button"
                                      size="sm"
                                      variant="outline"
                                      onClick={() => {
                                        const name = newCatName[idx];
                                        const score = newCatScore[idx] ?? '1.0';
                                        if (name && name.trim()) {
                                          handleAddCategory(idx, name.trim(), score);
                                          setNewCatName((prev) => ({ ...prev, [idx]: '' }));
                                          setNewCatScore((prev) => ({ ...prev, [idx]: '1.0' }));
                                        }
                                      }}
                                      className="h-7 px-3 text-xs gap-1 text-forest-700 border-forest-300 hover:bg-forest-50"
                                    >
                                      <Plus className="h-3.5 w-3.5" />
                                      Add Category
                                    </Button>
                                  </div>
                                </div>
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
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

        <DialogFooter className="shrink-0 pt-2 border-t border-border">
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
