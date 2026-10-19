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
  ShieldCheck,
  AlertCircle,
  CheckCircle2,
  Loader2,
  GitBranch,
  Layers,
  Plus,
  Trash2,
  Sliders,
  ChevronDown,
  ChevronUp,
  UserCheck,
} from 'lucide-react';
import type { RuleConfiguration, RuleDefinition, RuleTypeCatalogItem, GlobalRuleConfig } from '@/types';
import { useUpdateRuleConfigMutation, useRuleCatalog } from '@/hooks/useConfigurations';

// Sensible default parameters per rule type
const DEFAULT_PARAMETERS_BY_TYPE: Record<string, Record<string, any>> = {
  team_size_min: { min_size: 2 },
  team_size_max: { max_size: 5 },
  required_link: { link_field: 'github_url', member_selection: 'all_members' },
  required_signal_present: { signal_key: 'academic_cgpa', member_selection: 'all_members' },
  signal_threshold: {
    signal_key: 'academic_cgpa',
    operator: '>=',
    threshold: 7.0,
    member_selection: 'all_members',
    aggregation: 'all',
  },
  signal_contains: {
    signal_key: 'skills',
    expected_value: 'Python',
    member_selection: 'any_member',
  },
  allowed_values: {
    field_key: 'track',
    allowed_values: ['AI', 'Web3', 'Open'],
    member_selection: 'all_members',
  },
  track_limit: { field_key: 'track', limit: 10 },
  duplicate_member_email: { email_field: 'email' },
  required_fields_present: { field_keys: ['name', 'email'], member_selection: 'all_members' },
};

interface EditRuleConfigModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  config: RuleConfiguration;
  onSuccess: (newVersion: number) => void;
}

export const EditRuleConfigModal: React.FC<EditRuleConfigModalProps> = ({
  open,
  onOpenChange,
  config,
  onSuccess,
}) => {
  const updateMutation = useUpdateRuleConfigMutation();
  const catalogQuery = useRuleCatalog();

  const [name, setName] = useState(config.name || '');
  const [description, setDescription] = useState(config.description || '');
  const [leadField, setLeadField] = useState(config.global_config?.lead_field || 'role');
  const [leadValues, setLeadValues] = useState(
    (config.global_config?.lead_values || ['lead', 'team lead', 'captain', 'leader', 'team_lead']).join(', ')
  );
  const [defaultAcademicScale, setDefaultAcademicScale] = useState<number>(
    config.global_config?.default_academic_scale ?? 10.0
  );
  const [isGlobalConfigOpen, setIsGlobalConfigOpen] = useState(false);

  const [rules, setRules] = useState<RuleDefinition[]>([]);
  const [expandedRuleIndex, setExpandedRuleIndex] = useState<number | null>(null);
  const [isAddMenuOpen, setIsAddMenuOpen] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setName(config.name || '');
      setDescription(config.description || '');
      setLeadField(config.global_config?.lead_field || 'role');
      setLeadValues(
        (config.global_config?.lead_values || ['lead', 'team lead', 'captain', 'leader', 'team_lead']).join(', ')
      );
      setDefaultAcademicScale(config.global_config?.default_academic_scale ?? 10.0);
      setIsGlobalConfigOpen(false);

      setRules(
        (config.rules || []).map((r) => ({
          ...r,
          parameters: { ...(r.parameters || {}) },
        }))
      );
      setExpandedRuleIndex(null);
      setIsAddMenuOpen(false);
      setShowConfirm(false);
      setErrorMessage(null);
    }
  }, [open, config]);

  const handleToggleEnabled = (index: number) => {
    setRules((prev) => {
      const copy = [...prev];
      copy[index] = { ...copy[index], is_enabled: !copy[index].is_enabled };
      return copy;
    });
  };

  const handleSeverityChange = (index: number, severity: 'hard' | 'soft') => {
    setRules((prev) => {
      const copy = [...prev];
      copy[index] = { ...copy[index], severity };
      return copy;
    });
  };

  const handleOnMissingChange = (
    index: number,
    on_missing: 'manual_review' | 'fail' | 'pass' | 'skip'
  ) => {
    setRules((prev) => {
      const copy = [...prev];
      copy[index] = { ...copy[index], on_missing };
      return copy;
    });
  };

  const handleParameterChange = (index: number, key: string, value: any) => {
    setRules((prev) => {
      const copy = [...prev];
      copy[index] = {
        ...copy[index],
        parameters: {
          ...copy[index].parameters,
          [key]: value,
        },
      };
      return copy;
    });
  };

  const handleRemoveRule = (index: number) => {
    setRules((prev) => prev.filter((_, i) => i !== index));
    if (expandedRuleIndex === index) {
      setExpandedRuleIndex(null);
    }
  };

  const handleAddRuleFromCatalog = (catalogItem: RuleTypeCatalogItem) => {
    const newRuleId = `rule_${catalogItem.rule_type}_${Date.now().toString(36).slice(-4)}`;
    const defaultParams = DEFAULT_PARAMETERS_BY_TYPE[catalogItem.rule_type] || {};

    const newRule: RuleDefinition = {
      rule_id: newRuleId,
      name: catalogItem.name,
      rule_type: catalogItem.rule_type,
      description: catalogItem.description,
      severity: (catalogItem.default_severity as any) || 'hard',
      scope: (catalogItem.scope as any) || 'team',
      order: rules.length,
      on_missing: 'manual_review',
      is_enabled: true,
      parameters: { ...defaultParams },
    };

    setRules((prev) => [...prev, newRule]);
    setIsAddMenuOpen(false);
    setExpandedRuleIndex(rules.length);
  };

  const handleReviewClick = () => {
    if (!name.trim()) {
      setErrorMessage('Configuration Name cannot be left empty.');
      return;
    }

    const activeRules = rules.filter((r) => r.is_enabled);
    if (activeRules.length === 0) {
      setErrorMessage('At least one rule must be enabled in the configuration.');
      return;
    }

    // Validate parameters of each active rule to ensure required fields are not empty
    for (const r of activeRules) {
      const p = r.parameters || {};
      if (r.rule_type === 'required_link') {
        const linkField = typeof p.link_field === 'string' ? p.link_field.trim() : '';
        if (!linkField) {
          setErrorMessage(`Rule "${r.name}" requires a Link Field Name. It cannot be left empty.`);
          return;
        }
      } else if (r.rule_type === 'signal_threshold') {
        const sigKey = typeof p.signal_key === 'string' ? p.signal_key.trim() : '';
        if (!sigKey) {
          setErrorMessage(`Rule "${r.name}" requires a Target Signal Key. It cannot be left empty.`);
          return;
        }
      } else if (r.rule_type === 'signal_contains') {
        const sigKey = typeof p.signal_key === 'string' ? p.signal_key.trim() : '';
        const expVal = typeof p.expected_value === 'string' ? p.expected_value.trim() : '';
        if (!sigKey) {
          setErrorMessage(`Rule "${r.name}" requires a Signal Identifier.`);
          return;
        }
        if (!expVal) {
          setErrorMessage(`Rule "${r.name}" requires an Expected Token / Value.`);
          return;
        }
      } else if (r.rule_type === 'allowed_values') {
        const fKey = typeof p.field_key === 'string' ? p.field_key.trim() : '';
        const sKey = typeof p.signal_key === 'string' ? p.signal_key.trim() : '';
        if (!fKey && !sKey) {
          setErrorMessage(`Rule "${r.name}" requires either a Field Key or a Signal Key.`);
          return;
        }
        if (!Array.isArray(p.allowed_values) || p.allowed_values.length === 0) {
          setErrorMessage(`Rule "${r.name}" requires at least one allowed value.`);
          return;
        }
      } else if (r.rule_type === 'track_limit') {
        const fKey = typeof p.field_key === 'string' ? p.field_key.trim() : '';
        if (!fKey) {
          setErrorMessage(`Rule "${r.name}" requires a Track Field Key.`);
          return;
        }
        if (!p.limit || p.limit < 1) {
          setErrorMessage(`Rule "${r.name}" requires a maximum capacity limit >= 1.`);
          return;
        }
      } else if (r.rule_type === 'duplicate_member_email') {
        const emailField = typeof p.email_field === 'string' ? p.email_field.trim() : '';
        if (!emailField) {
          setErrorMessage(`Rule "${r.name}" requires an Email Field Name.`);
          return;
        }
      } else if (r.rule_type === 'required_signal_present') {
        const sigKey = typeof p.signal_key === 'string' ? p.signal_key.trim() : '';
        if (!sigKey) {
          setErrorMessage(`Rule "${r.name}" requires a Signal Key.`);
          return;
        }
      } else if (r.rule_type === 'required_fields_present') {
        if (!Array.isArray(p.field_keys) || p.field_keys.length === 0) {
          setErrorMessage(`Rule "${r.name}" requires at least one field key.`);
          return;
        }
      }
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

      const globalConfigPayload: GlobalRuleConfig = {
        lead_field: leadField.trim() || 'role',
        lead_values: parsedLeadValues.length > 0 ? parsedLeadValues : ['lead', 'team lead'],
        default_academic_scale: defaultAcademicScale > 0 ? defaultAcademicScale : 10.0,
        extra_mappings: config.global_config?.extra_mappings || {},
      };

      const updated = await updateMutation.mutateAsync({
        configId: config.config_id,
        payload: {
          name: name.trim() || config.name,
          description: description.trim(),
          global_config: globalConfigPayload,
          rules: rules as any,
        },
      });
      onSuccess(updated.version);
      onOpenChange(false);
    } catch (err: any) {
      const msg =
        err?.response?.data?.detail || err?.message || 'Failed to update rule configuration.';
      setErrorMessage(typeof msg === 'string' ? msg : JSON.stringify(msg));
      setShowConfirm(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent onClose={() => onOpenChange(false)} className="max-w-3xl max-h-[92vh] flex flex-col">
        <DialogHeader className="shrink-0">
          <div className="flex items-center gap-2">
            <Badge variant="forest" className="font-mono text-[10px]">
              Eligibility Rule Editor
            </Badge>
            <span className="text-xs text-muted-foreground flex items-center gap-1">
              <GitBranch className="h-3 w-3" />
              Creates Version {config.version + 1}
            </span>
          </div>
          <DialogTitle className="text-base font-semibold">
            Edit Eligibility Configuration: {config.name}
          </DialogTitle>
          <DialogDescription>
            Enable or disable individual evaluator rules, adjust rule severity, and modify missing-data handling. Saving produces an immutable version preserving past runs.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2 overflow-y-auto flex-1 pr-1">
          {errorMessage && (
            <div className="p-3 rounded-lg border border-red-300 bg-red-50 text-red-800 text-xs flex items-start gap-2">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Name & Description */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-3 bg-muted/40 rounded-lg border border-border/70">
            <div className="sm:col-span-1 space-y-1">
              <label className="text-xs font-semibold text-foreground">Configuration Name</label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Hackathon Core Eligibility..."
                className="text-xs h-8 font-medium"
              />
            </div>
            <div className="sm:col-span-2 space-y-1">
              <label className="text-xs font-semibold text-foreground">Description & Scope</label>
              <Input
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe eligibility requirements..."
                className="text-xs h-8"
              />
            </div>
          </div>

          {/* Collapsible Global Configuration & Team Lead Settings */}
          <div className="border border-border/80 rounded-lg overflow-hidden bg-card">
            <button
              type="button"
              onClick={() => setIsGlobalConfigOpen((prev) => !prev)}
              className="w-full flex items-center justify-between p-3 bg-muted/30 hover:bg-muted/50 text-xs font-semibold text-foreground transition-colors cursor-pointer"
            >
              <div className="flex items-center gap-2">
                <Sliders className="h-3.5 w-3.5 text-forest-700" />
                <span>Global Configuration & Team Lead Resolution</span>
                <span className="text-[10px] font-normal text-muted-foreground">
                  (Controls team lead detection and default academic scaling)
                </span>
              </div>
              {isGlobalConfigOpen ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
            </button>

            {isGlobalConfigOpen && (
              <div className="p-3 border-t border-border/70 space-y-3 bg-card text-xs">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
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
                      Registration column identifying member role.
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
                      Values indicating team lead status.
                    </p>
                  </div>

                  <div className="space-y-1">
                    <label className="text-[11px] font-medium text-foreground">
                      Default Academic Scale
                    </label>
                    <Input
                      type="number"
                      step="0.5"
                      min="1"
                      value={defaultAcademicScale}
                      onChange={(e) => setDefaultAcademicScale(parseFloat(e.target.value) || 10.0)}
                      className="h-7 text-xs font-mono"
                    />
                    <p className="text-[10px] text-muted-foreground">
                      Fallback scale (e.g. 10.0, 4.0) if unstated.
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Rules Builder Section */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs font-semibold text-foreground">
              <span className="flex items-center gap-1.5">
                <Layers className="h-3.5 w-3.5 text-forest-700" />
                Rule Evaluators ({rules.filter((r) => r.is_enabled).length}/{rules.length} Active)
              </span>

              <div className="relative">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setIsAddMenuOpen((prev) => !prev)}
                  className="h-7 text-xs gap-1 text-forest-700 border-forest-300 hover:bg-forest-50 font-medium"
                >
                  <Plus className="h-3.5 w-3.5" />
                  Add Rule from Catalog
                  <ChevronDown className="h-3 w-3 ml-0.5" />
                </Button>

                {/* Add Rule Catalog Dropdown */}
                {isAddMenuOpen && (
                  <div className="absolute right-0 top-8 z-50 w-80 max-h-80 overflow-y-auto bg-card border border-border rounded-lg shadow-lg p-1.5 space-y-1 animate-in fade-in zoom-in-95">
                    <div className="px-2 py-1 text-[10px] font-semibold text-muted-foreground uppercase tracking-wider border-b border-border/60">
                      Select Evaluator Type ({catalogQuery.data?.length || 10})
                    </div>
                    {catalogQuery.isLoading ? (
                      <div className="p-3 text-center text-xs text-muted-foreground flex items-center justify-center gap-2">
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        Loading catalog...
                      </div>
                    ) : (
                      (catalogQuery.data || []).map((cat) => (
                        <button
                          key={cat.rule_type}
                          type="button"
                          onClick={() => handleAddRuleFromCatalog(cat)}
                          className="w-full text-left p-2 rounded-md hover:bg-muted/70 transition-colors group flex flex-col cursor-pointer"
                        >
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-semibold text-foreground group-hover:text-forest-700">
                              {cat.name}
                            </span>
                            <Badge variant="outline" className="text-[9px] font-mono py-0 px-1">
                              {cat.scope}
                            </Badge>
                          </div>
                          <span
                            className="text-[10px] text-muted-foreground line-clamp-1 mt-0.5 cursor-help"
                            title={cat.description}
                          >
                            {cat.description}
                          </span>
                        </button>
                      ))
                    )}
                  </div>
                )}
              </div>
            </div>

            {rules.length === 0 ? (
              <div className="p-8 text-center border border-dashed border-border rounded-lg bg-muted/20">
                <ShieldCheck className="h-8 w-8 text-muted-foreground mx-auto mb-2 opacity-50" />
                <p className="text-xs font-semibold text-foreground">No rules configured</p>
                <p className="text-[11px] text-muted-foreground mt-0.5 max-w-sm mx-auto">
                  Add evaluator rules from the catalog to filter teams based on member counts, required signals, or academic thresholds.
                </p>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setIsAddMenuOpen(true)}
                  className="mt-3 text-xs gap-1.5 text-forest-700 border-forest-300 hover:bg-forest-50"
                >
                  <Plus className="h-3.5 w-3.5" />
                  Add First Rule
                </Button>
              </div>
            ) : (
              <div className="border border-border rounded-lg overflow-hidden">
                <table className="w-full text-left text-xs">
                  <thead className="bg-muted/60 border-b border-border text-[11px] text-muted-foreground">
                    <tr>
                      <th className="py-2 px-3 w-10 text-center">Active</th>
                      <th className="py-2 px-3">Rule Definition</th>
                      <th className="py-2 px-3 w-28">Severity</th>
                      <th className="py-2 px-3 w-36">On Missing Data</th>
                      <th className="py-2 px-2 w-10 text-center">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {rules.map((rule, idx) => {
                      const isExpanded = expandedRuleIndex === idx;
                      const params = rule.parameters || {};

                      return (
                        <React.Fragment key={rule.rule_id}>
                          <tr
                            className={`hover:bg-muted/30 transition-colors ${
                              !rule.is_enabled ? 'opacity-50 bg-muted/10' : ''
                            }`}
                          >
                            <td className="py-2.5 px-3 text-center align-top pt-3">
                              <input
                                type="checkbox"
                                checked={rule.is_enabled}
                                onChange={() => handleToggleEnabled(idx)}
                                className="h-3.5 w-3.5 rounded border-border text-forest-700 focus:ring-forest-600 cursor-pointer"
                              />
                            </td>
                            <td className="py-2.5 px-3">
                              <div className="flex items-center gap-2">
                                <span className="font-semibold text-foreground">{rule.name}</span>
                                <Badge variant="forest" className="font-mono text-[9px] py-0 px-1.5">
                                  {rule.rule_type}
                                </Badge>
                              </div>
                              <div className="text-[10px] text-muted-foreground font-mono mt-0.5">
                                id: {rule.rule_id}
                              </div>
                              {rule.description && (
                                <div
                                  className="text-[11px] text-muted-foreground mt-0.5 line-clamp-1 cursor-help hover:text-foreground transition-colors"
                                  title={rule.description}
                                >
                                  {rule.description}
                                </div>
                              )}

                              <div className="mt-1.5">
                                <button
                                  type="button"
                                  onClick={() =>
                                    setExpandedRuleIndex(isExpanded ? null : idx)
                                  }
                                  className="text-[11px] font-medium text-forest-700 hover:text-forest-800 flex items-center gap-1 cursor-pointer"
                                >
                                  <Sliders className="h-3 w-3" />
                                  <span>{isExpanded ? 'Hide Parameters' : 'Edit Parameters'}</span>
                                  {isExpanded ? (
                                    <ChevronUp className="h-3 w-3" />
                                  ) : (
                                    <ChevronDown className="h-3 w-3" />
                                  )}
                                </button>
                              </div>
                            </td>
                            <td className="py-2.5 px-3 align-top pt-2.5">
                              <select
                                disabled={!rule.is_enabled}
                                value={rule.severity}
                                onChange={(e) => handleSeverityChange(idx, e.target.value as any)}
                                className="h-7 text-xs rounded border border-border bg-card px-2 text-foreground focus:outline-none focus:ring-1 focus:ring-forest-600 disabled:opacity-50"
                              >
                                <option value="hard">hard</option>
                                <option value="soft">soft</option>
                              </select>
                            </td>
                            <td className="py-2.5 px-3 align-top pt-2.5">
                              <select
                                disabled={!rule.is_enabled}
                                value={rule.on_missing}
                                onChange={(e) => handleOnMissingChange(idx, e.target.value as any)}
                                className="h-7 text-xs rounded border border-border bg-card px-2 text-foreground focus:outline-none focus:ring-1 focus:ring-forest-600 disabled:opacity-50 font-mono text-[11px]"
                              >
                                <option value="manual_review">manual_review</option>
                                <option value="fail">fail</option>
                                <option value="pass">pass</option>
                                <option value="skip">skip</option>
                              </select>
                            </td>
                            <td className="py-2.5 px-2 text-center align-top pt-2.5">
                              <Button
                                type="button"
                                variant="ghost"
                                size="icon"
                                onClick={() => handleRemoveRule(idx)}
                                className="h-7 w-7 text-muted-foreground hover:text-red-600 hover:bg-red-50"
                                title="Remove rule from configuration"
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </Button>
                            </td>
                          </tr>

                          {/* Expanded Parameter Editor Row */}
                          {isExpanded && (
                            <tr className="bg-muted/40">
                              <td colSpan={5} className="p-3 border-t border-border/70">
                                <div className="space-y-3 bg-card p-3 rounded-md border border-border">
                                  <div className="text-[11px] font-semibold text-foreground flex items-center justify-between">
                                    <span>Configure Parameters: {rule.name}</span>
                                    <span className="font-mono text-[10px] text-muted-foreground">
                                      type: {rule.rule_type}
                                    </span>
                                  </div>

                                  {rule.description && (
                                    <p
                                      className="text-[11px] text-muted-foreground bg-muted/40 p-2.5 rounded-md border border-border/50 leading-relaxed"
                                      title={rule.description}
                                    >
                                      <span className="font-semibold text-foreground">Rule Purpose: </span>
                                      {rule.description}
                                    </p>
                                  )}

                                  {/* Dynamic fields based on rule_type */}
                                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 text-xs">
                                    {rule.rule_type === 'team_size_min' && (
                                      <div className="space-y-1">
                                        <label className="text-[11px] font-medium text-foreground">
                                          Minimum Team Size (min_size)
                                        </label>
                                        <Input
                                          type="number"
                                          min="0"
                                          value={params.min_size ?? 2}
                                          onChange={(e) =>
                                            handleParameterChange(
                                              idx,
                                              'min_size',
                                              parseInt(e.target.value, 10) || 0
                                            )
                                          }
                                          className="h-7 text-xs font-mono"
                                        />
                                      </div>
                                    )}

                                    {rule.rule_type === 'team_size_max' && (
                                      <div className="space-y-1">
                                        <label className="text-[11px] font-medium text-foreground">
                                          Maximum Team Size (max_size)
                                        </label>
                                        <Input
                                          type="number"
                                          min="1"
                                          value={params.max_size ?? 5}
                                          onChange={(e) =>
                                            handleParameterChange(
                                              idx,
                                              'max_size',
                                              parseInt(e.target.value, 10) || 1
                                            )
                                          }
                                          className="h-7 text-xs font-mono"
                                        />
                                      </div>
                                    )}

                                    {rule.rule_type === 'required_link' && (
                                      <>
                                        <div className="space-y-1">
                                          <div className="flex items-center justify-between">
                                            <label className="text-[11px] font-medium text-foreground">
                                              Link Field Name <span className="text-red-500">*</span>
                                            </label>
                                            {params.link_field !== undefined && !params.link_field.trim() && (
                                              <span className="text-[10px] text-red-500 font-medium">Field name required</span>
                                            )}
                                          </div>
                                          <Input
                                            value={params.link_field ?? ''}
                                            onChange={(e) =>
                                              handleParameterChange(idx, 'link_field', e.target.value)
                                            }
                                            placeholder="e.g. github_url, leetcode, portfolio_url..."
                                            className={`h-7 text-xs font-mono ${
                                              params.link_field !== undefined && !params.link_field.trim()
                                                ? 'border-red-400 focus:ring-red-400 bg-red-50/20'
                                                : ''
                                            }`}
                                          />
                                          <div className="flex flex-wrap items-center gap-1 mt-1 pt-0.5">
                                            <span className="text-[10px] text-muted-foreground">Quick pick:</span>
                                            {['github_url', 'leetcode', 'portfolio_url', 'linkedin_url', 'resume_url'].map((k) => (
                                              <button
                                                key={k}
                                                type="button"
                                                onClick={() => handleParameterChange(idx, 'link_field', k)}
                                                className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-muted hover:bg-forest-100 hover:text-forest-800 text-muted-foreground transition-colors cursor-pointer"
                                              >
                                                +{k}
                                              </button>
                                            ))}
                                          </div>
                                        </div>
                                        <div className="space-y-1">
                                          <label className="text-[11px] font-medium text-foreground">
                                            Member Selection
                                          </label>
                                          <select
                                            value={params.member_selection || 'all_members'}
                                            onChange={(e) =>
                                              handleParameterChange(idx, 'member_selection', e.target.value)
                                            }
                                            className="h-7 w-full text-xs rounded border border-border bg-card px-2 text-foreground font-mono text-[11px]"
                                          >
                                            <option value="all_members">all_members</option>
                                            <option value="any_member">any_member</option>
                                            <option value="team_lead">team_lead</option>
                                          </select>
                                        </div>
                                      </>
                                    )}

                                    {rule.rule_type === 'signal_threshold' && (
                                      <>
                                        <div className="space-y-1">
                                          <div className="flex items-center justify-between">
                                            <label className="text-[11px] font-medium text-foreground">
                                              Target Signal Key <span className="text-red-500">*</span>
                                            </label>
                                            {params.signal_key !== undefined && !params.signal_key.trim() && (
                                              <span className="text-[10px] text-red-500 font-medium">Signal key required</span>
                                            )}
                                          </div>
                                          <Input
                                            value={params.signal_key ?? ''}
                                            onChange={(e) =>
                                              handleParameterChange(idx, 'signal_key', e.target.value)
                                            }
                                            placeholder="e.g. academic_cgpa, github_public_repo_count..."
                                            className={`h-7 text-xs font-mono ${
                                              params.signal_key !== undefined && !params.signal_key.trim()
                                                ? 'border-red-400 focus:ring-red-400 bg-red-50/20'
                                                : ''
                                            }`}
                                          />
                                          <div className="flex flex-wrap items-center gap-1 mt-1 pt-0.5">
                                            <span className="text-[10px] text-muted-foreground">Quick pick:</span>
                                            {['academic_cgpa', 'github_public_repo_count', 'resume_experience_years', 'normalized_cgpa_10_scale'].map((k) => (
                                              <button
                                                key={k}
                                                type="button"
                                                onClick={() => handleParameterChange(idx, 'signal_key', k)}
                                                className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-muted hover:bg-forest-100 hover:text-forest-800 text-muted-foreground transition-colors cursor-pointer"
                                              >
                                                +{k}
                                              </button>
                                            ))}
                                          </div>
                                        </div>
                                        <div className="space-y-1">
                                          <label className="text-[11px] font-medium text-foreground">
                                            Comparison Operator
                                          </label>
                                          <select
                                            value={params.operator || '>='}
                                            onChange={(e) =>
                                              handleParameterChange(idx, 'operator', e.target.value)
                                            }
                                            className="h-7 w-full text-xs rounded border border-border bg-card px-2 text-foreground font-mono"
                                          >
                                            <option value=">=">&gt;= (Greater or equal)</option>
                                            <option value=">">&gt; (Strictly greater)</option>
                                            <option value="<=">&lt;= (Less or equal)</option>
                                            <option value="<">&lt; (Strictly less)</option>
                                            <option value="==">== (Exact match)</option>
                                            <option value="!=">!= (Not equal)</option>
                                          </select>
                                        </div>
                                        <div className="space-y-1">
                                          <label className="text-[11px] font-medium text-foreground">
                                            Numeric Threshold
                                          </label>
                                          <Input
                                            type="number"
                                            step="0.1"
                                            value={params.threshold ?? 7.0}
                                            onChange={(e) =>
                                              handleParameterChange(
                                                idx,
                                                'threshold',
                                                parseFloat(e.target.value) || 0
                                              )
                                            }
                                            className="h-7 text-xs font-mono"
                                          />
                                        </div>
                                        <div className="space-y-1">
                                          <label className="text-[11px] font-medium text-foreground">
                                            Member Selection
                                          </label>
                                          <select
                                            value={params.member_selection || 'all_members'}
                                            onChange={(e) =>
                                              handleParameterChange(idx, 'member_selection', e.target.value)
                                            }
                                            className="h-7 w-full text-xs rounded border border-border bg-card px-2 text-foreground font-mono text-[11px]"
                                          >
                                            <option value="all_members">all_members</option>
                                            <option value="any_member">any_member</option>
                                            <option value="team_lead">team_lead</option>
                                          </select>
                                        </div>
                                        <div className="space-y-1">
                                          <label className="text-[11px] font-medium text-foreground">
                                            Aggregation
                                          </label>
                                          <select
                                            value={params.aggregation || 'all'}
                                            onChange={(e) =>
                                              handleParameterChange(idx, 'aggregation', e.target.value)
                                            }
                                            className="h-7 w-full text-xs rounded border border-border bg-card px-2 text-foreground font-mono text-[11px]"
                                          >
                                            <option value="all">all</option>
                                            <option value="any">any</option>
                                            <option value="min">min</option>
                                            <option value="max">max</option>
                                            <option value="mean">mean</option>
                                          </select>
                                        </div>
                                      </>
                                    )}

                                    {rule.rule_type === 'signal_contains' && (
                                      <>
                                        <div className="space-y-1">
                                          <div className="flex items-center justify-between">
                                            <label className="text-[11px] font-medium text-foreground">
                                              Signal Identifier <span className="text-red-500">*</span>
                                            </label>
                                            {params.signal_key !== undefined && !params.signal_key.trim() && (
                                              <span className="text-[10px] text-red-500 font-medium">Identifier required</span>
                                            )}
                                          </div>
                                          <Input
                                            value={params.signal_key ?? ''}
                                            onChange={(e) =>
                                              handleParameterChange(idx, 'signal_key', e.target.value)
                                            }
                                            placeholder="e.g. resume_extracted_skills"
                                            className={`h-7 text-xs font-mono ${
                                              params.signal_key !== undefined && !params.signal_key.trim()
                                                ? 'border-red-400 focus:ring-red-400 bg-red-50/20'
                                                : ''
                                            }`}
                                          />
                                        </div>
                                        <div className="space-y-1">
                                          <div className="flex items-center justify-between">
                                            <label className="text-[11px] font-medium text-foreground">
                                              Expected Token / Value <span className="text-red-500">*</span>
                                            </label>
                                            {params.expected_value !== undefined && !params.expected_value.trim() && (
                                              <span className="text-[10px] text-red-500 font-medium">Token required</span>
                                            )}
                                          </div>
                                          <Input
                                            value={params.expected_value ?? ''}
                                            onChange={(e) =>
                                              handleParameterChange(idx, 'expected_value', e.target.value)
                                            }
                                            placeholder="e.g. Python, React..."
                                            className={`h-7 text-xs font-mono ${
                                              params.expected_value !== undefined && !params.expected_value.trim()
                                                ? 'border-red-400 focus:ring-red-400 bg-red-50/20'
                                                : ''
                                            }`}
                                          />
                                        </div>
                                        <div className="space-y-1">
                                          <label className="text-[11px] font-medium text-foreground">
                                            Member Selection
                                          </label>
                                          <select
                                            value={params.member_selection || 'any_member'}
                                            onChange={(e) =>
                                              handleParameterChange(idx, 'member_selection', e.target.value)
                                            }
                                            className="h-7 w-full text-xs rounded border border-border bg-card px-2 text-foreground font-mono text-[11px]"
                                          >
                                            <option value="any_member">any_member</option>
                                            <option value="all_members">all_members</option>
                                            <option value="team_lead">team_lead</option>
                                          </select>
                                        </div>
                                      </>
                                    )}

                                    {rule.rule_type === 'allowed_values' && (
                                      <>
                                        <div className="space-y-1">
                                          <div className="flex items-center justify-between">
                                            <label className="text-[11px] font-medium text-foreground">
                                              Field Key OR Signal Key <span className="text-red-500">*</span>
                                            </label>
                                            {!params.field_key?.trim() && !params.signal_key?.trim() && (
                                              <span className="text-[10px] text-red-500 font-medium">Key required</span>
                                            )}
                                          </div>
                                          <Input
                                            value={params.field_key || params.signal_key || ''}
                                            onChange={(e) => {
                                              const v = e.target.value;
                                              // If it's a known signal key, store as signal_key, else field_key
                                              if (['academic_year', 'resume_degree_level'].includes(v)) {
                                                handleParameterChange(idx, 'signal_key', v);
                                                handleParameterChange(idx, 'field_key', undefined);
                                              } else {
                                                handleParameterChange(idx, 'field_key', v);
                                                handleParameterChange(idx, 'signal_key', undefined);
                                              }
                                            }}
                                            placeholder="e.g. track, academic_year..."
                                            className="h-7 text-xs font-mono"
                                          />
                                          <div className="flex flex-wrap items-center gap-1 mt-1 pt-0.5">
                                            <span className="text-[10px] text-muted-foreground">Quick pick:</span>
                                            {['track', 'academic_year', 'resume_degree_level'].map((k) => (
                                              <button
                                                key={k}
                                                type="button"
                                                onClick={() => {
                                                  if (['academic_year', 'resume_degree_level'].includes(k)) {
                                                    handleParameterChange(idx, 'signal_key', k);
                                                    handleParameterChange(idx, 'field_key', undefined);
                                                  } else {
                                                    handleParameterChange(idx, 'field_key', k);
                                                    handleParameterChange(idx, 'signal_key', undefined);
                                                  }
                                                }}
                                                className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-muted hover:bg-forest-100 hover:text-forest-800 text-muted-foreground transition-colors cursor-pointer"
                                              >
                                                +{k}
                                              </button>
                                            ))}
                                          </div>
                                        </div>
                                        <div className="space-y-1">
                                          <label className="text-[11px] font-medium text-foreground">
                                            Member Selection
                                          </label>
                                          <select
                                            value={params.member_selection || 'all_members'}
                                            onChange={(e) =>
                                              handleParameterChange(idx, 'member_selection', e.target.value)
                                            }
                                            className="h-7 w-full text-xs rounded border border-border bg-card px-2 text-foreground font-mono text-[11px]"
                                          >
                                            <option value="all_members">all_members</option>
                                            <option value="any_member">any_member</option>
                                            <option value="team_lead">team_lead</option>
                                          </select>
                                        </div>
                                        <div className="space-y-1 sm:col-span-1">
                                          <div className="flex items-center justify-between">
                                            <label className="text-[11px] font-medium text-foreground">
                                              Allowed Values <span className="text-red-500">*</span>
                                            </label>
                                            {Array.isArray(params.allowed_values) && params.allowed_values.length === 0 && (
                                              <span className="text-[10px] text-red-500 font-medium">Value required</span>
                                            )}
                                          </div>
                                          <Input
                                            value={Array.isArray(params.allowed_values) ? params.allowed_values.join(', ') : ''}
                                            onChange={(e) =>
                                              handleParameterChange(
                                                idx,
                                                'allowed_values',
                                                e.target.value
                                                  .split(',')
                                                  .map((s) => s.trim())
                                                  .filter(Boolean)
                                              )
                                            }
                                            placeholder="AI, Web3, Open..."
                                            className="h-7 text-xs font-mono"
                                          />
                                        </div>
                                      </>
                                    )}

                                    {rule.rule_type === 'track_limit' && (
                                      <>
                                        <div className="space-y-1">
                                          <div className="flex items-center justify-between">
                                            <label className="text-[11px] font-medium text-foreground">
                                              Track Field Key <span className="text-red-500">*</span>
                                            </label>
                                            {params.field_key !== undefined && !params.field_key.trim() && (
                                              <span className="text-[10px] text-red-500 font-medium">Field key required</span>
                                            )}
                                          </div>
                                          <Input
                                            value={params.field_key ?? ''}
                                            onChange={(e) =>
                                              handleParameterChange(idx, 'field_key', e.target.value)
                                            }
                                            placeholder="e.g. track"
                                            className={`h-7 text-xs font-mono ${
                                              params.field_key !== undefined && !params.field_key.trim()
                                                ? 'border-red-400 focus:ring-red-400 bg-red-50/20'
                                                : ''
                                            }`}
                                          />
                                        </div>
                                        <div className="space-y-1">
                                          <label className="text-[11px] font-medium text-foreground">
                                            Max Teams Limit per Track
                                          </label>
                                          <Input
                                            type="number"
                                            min="1"
                                            value={params.limit ?? 10}
                                            onChange={(e) =>
                                              handleParameterChange(
                                                idx,
                                                'limit',
                                                parseInt(e.target.value, 10) || 1
                                              )
                                            }
                                            className="h-7 text-xs font-mono"
                                          />
                                        </div>
                                      </>
                                    )}

                                    {rule.rule_type === 'required_fields_present' && (
                                      <div className="space-y-1 sm:col-span-2">
                                        <div className="flex items-center justify-between">
                                          <label className="text-[11px] font-medium text-foreground">
                                            Required Field Keys (comma-separated) <span className="text-red-500">*</span>
                                          </label>
                                          {Array.isArray(params.field_keys) && params.field_keys.length === 0 && (
                                            <span className="text-[10px] text-red-500 font-medium">At least one field key required</span>
                                          )}
                                        </div>
                                        <Input
                                          value={Array.isArray(params.field_keys) ? params.field_keys.join(', ') : ''}
                                          onChange={(e) =>
                                            handleParameterChange(
                                              idx,
                                              'field_keys',
                                              e.target.value
                                                .split(',')
                                                .map((s) => s.trim())
                                                .filter(Boolean)
                                            )
                                          }
                                          placeholder="name, email, github_url..."
                                          className="h-7 text-xs font-mono"
                                        />
                                      </div>
                                    )}

                                    {rule.rule_type === 'duplicate_member_email' && (
                                      <div className="space-y-1">
                                        <div className="flex items-center justify-between">
                                          <label className="text-[11px] font-medium text-foreground">
                                            Email Field Name <span className="text-red-500">*</span>
                                          </label>
                                          {params.email_field !== undefined && !params.email_field.trim() && (
                                            <span className="text-[10px] text-red-500 font-medium">Field name required</span>
                                          )}
                                        </div>
                                        <Input
                                          value={params.email_field ?? ''}
                                          onChange={(e) =>
                                            handleParameterChange(idx, 'email_field', e.target.value)
                                          }
                                          placeholder="e.g. email"
                                          className={`h-7 text-xs font-mono ${
                                            params.email_field !== undefined && !params.email_field.trim()
                                              ? 'border-red-400 focus:ring-red-400 bg-red-50/20'
                                              : ''
                                          }`}
                                        />
                                      </div>
                                    )}

                                    {rule.rule_type === 'required_signal_present' && (
                                      <div className="space-y-1">
                                        <div className="flex items-center justify-between">
                                          <label className="text-[11px] font-medium text-foreground">
                                            Signal Key <span className="text-red-500">*</span>
                                          </label>
                                          {params.signal_key !== undefined && !params.signal_key.trim() && (
                                            <span className="text-[10px] text-red-500 font-medium">Signal key required</span>
                                          )}
                                        </div>
                                        <Input
                                          value={params.signal_key ?? ''}
                                          onChange={(e) =>
                                            handleParameterChange(idx, 'signal_key', e.target.value)
                                          }
                                          placeholder="e.g. academic_cgpa"
                                          className={`h-7 text-xs font-mono ${
                                            params.signal_key !== undefined && !params.signal_key.trim()
                                              ? 'border-red-400 focus:ring-red-400 bg-red-50/20'
                                              : ''
                                          }`}
                                        />
                                        <div className="flex flex-wrap items-center gap-1 mt-1 pt-0.5">
                                          <span className="text-[10px] text-muted-foreground">Quick pick:</span>
                                          {['github_public_repo_count', 'academic_cgpa', 'resume_experience_years', 'github_profile_verified', 'portfolio_site_reachable'].map((k) => (
                                            <button
                                              key={k}
                                              type="button"
                                              onClick={() => handleParameterChange(idx, 'signal_key', k)}
                                              className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-muted hover:bg-forest-100 hover:text-forest-800 text-muted-foreground transition-colors cursor-pointer"
                                            >
                                              +{k}
                                            </button>
                                          ))}
                                        </div>
                                      </div>
                                    )}
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

          {/* Confirmation Alert */}
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
                    <span className="font-mono font-semibold">{config.config_id}</span>. Prior evaluation runs
                    will continue referencing their historical version snapshot.
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
                <ShieldCheck className="h-3.5 w-3.5" />
                Review & Save Changes
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
