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
import type { RuleConfiguration } from '@/types';
import { useCreateRuleConfigMutation } from '@/hooks/useConfigurations';

interface CreateRuleConfigModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  existingConfigs: RuleConfiguration[];
  initialBasePresetId?: string;
  onSuccess: (newConfigId: string) => void;
}

const slugify = (text: string) =>
  text
    .toLowerCase()
    .replace(/[^a-z0-9_-]/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_|_$/g, '');

export const CreateRuleConfigModal: React.FC<CreateRuleConfigModalProps> = ({
  open,
  onOpenChange,
  existingConfigs,
  initialBasePresetId,
  onSuccess,
}) => {
  const createMutation = useCreateRuleConfigMutation();

  const [configId, setConfigId] = useState('');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [isIdManual, setIsIdManual] = useState(false);
  const [basePresetId, setBasePresetId] = useState<string>(
    initialBasePresetId || existingConfigs[0]?.config_id || ''
  );
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  React.useEffect(() => {
    if (open) {
      setConfigId('');
      setName('');
      setDescription('');
      setErrorMessage(null);
      setIsIdManual(false);
      if (initialBasePresetId && existingConfigs.some((c) => c.config_id === initialBasePresetId)) {
        setBasePresetId(initialBasePresetId);
      } else if (existingConfigs[0]?.config_id) {
        setBasePresetId(existingConfigs[0].config_id);
      }
    }
  }, [open, initialBasePresetId, existingConfigs]);

  const handleNameChange = (val: string) => {
    setName(val);
    if (!isIdManual) {
      setConfigId(slugify(val));
    }
  };

  const handleSubmit = async () => {
    const cleanId = configId.trim().toLowerCase().replace(/[^a-z0-9_-]/g, '_');
    if (!cleanId) {
      setErrorMessage('Please enter a valid alphanumeric Configuration ID.');
      return;
    }
    if (!name.trim()) {
      setErrorMessage('Please enter a Configuration Name.');
      return;
    }

    // Check if ID already exists
    if (existingConfigs.some((c) => c.config_id === cleanId)) {
      setErrorMessage(`Configuration ID '${cleanId}' already exists. Please choose a unique ID.`);
      return;
    }

    const isScratch = basePresetId === '__scratch__';
    const template = isScratch ? null : existingConfigs.find((c) => c.config_id === basePresetId);

    const starterRules = [
      {
        rule_id: 'rule_team_min_size',
        name: 'Minimum Team Size',
        rule_type: 'team_size_min',
        description: 'Requires teams to have at least 2 registered members.',
        severity: 'hard' as const,
        scope: 'team' as const,
        order: 0,
        on_missing: 'manual_review' as const,
        is_enabled: true,
        parameters: { min_size: 2 },
      },
    ];

    const rulesToCreate = isScratch
      ? starterRules
      : (template?.rules || []).map((r) => ({ ...r }));

    setErrorMessage(null);
    try {
      const created = await createMutation.mutateAsync({
        config_id: cleanId,
        name: name.trim(),
        description: description.trim(),
        rules: rulesToCreate as any,
        global_config: template?.global_config || {
          lead_field: 'role',
          lead_values: ['lead', 'team lead', 'captain', 'leader'],
          default_academic_scale: 10.0,
          extra_mappings: {},
        },
      });
      onSuccess(created.config_id);
      onOpenChange(false);
    } catch (err: any) {
      const msg =
        err?.response?.data?.detail || err?.message || 'Failed to create rule configuration.';
      setErrorMessage(typeof msg === 'string' ? msg : JSON.stringify(msg));
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent onClose={() => onOpenChange(false)} className="max-w-lg">
        <DialogHeader>
          <div className="flex items-center gap-2">
            <Badge variant="forest" className="font-mono text-[10px]">
              New Configuration
            </Badge>
            <span className="text-xs text-muted-foreground">· Version 1</span>
          </div>
          <DialogTitle className="text-base font-semibold">
            Create Custom Eligibility Configuration
          </DialogTitle>
          <DialogDescription>
            Register a new immutable configuration starting at version 1. You can initialize rules from
            an existing preset.
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
              onChange={(e) => {
                setIsIdManual(true);
                setConfigId(e.target.value);
              }}
              placeholder="e.g. custom_hackathon_rules"
              className="text-xs h-8 font-mono"
            />
            <p className="text-[10px] text-muted-foreground">
              Unique identifier used in API calls and evaluation pipeline.
            </p>
          </div>

          <div className="space-y-1">
            <label className="text-xs font-semibold text-foreground">
              Display Name <span className="text-red-500">*</span>
            </label>
            <Input
              value={name}
              onChange={(e) => handleNameChange(e.target.value)}
              placeholder="e.g. 2026 Winter Hackathon Standard"
              className="text-xs h-8"
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs font-semibold text-foreground">Description</label>
            <Input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g. Requires lead CGPA >= 7.5 and min 2 team members..."
              className="text-xs h-8"
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs font-semibold text-foreground">
              Initial Rules Template
            </label>
            <select
              value={basePresetId}
              onChange={(e) => setBasePresetId(e.target.value)}
              className="w-full h-8 text-xs rounded border border-border bg-card px-2 text-foreground focus:outline-none focus:ring-1 focus:ring-forest-600"
            >
              <option value="__scratch__">✨ Start from Scratch (1 starter rule)</option>
              {existingConfigs.map((cfg) => (
                <option key={cfg.config_id} value={cfg.config_id}>
                  Clone from: {cfg.name} ({cfg.rules?.length || 0} rules)
                </option>
              ))}
            </select>
            <p className="text-[10px] text-muted-foreground">
              Start with an empty rule set to build custom criteria from scratch, or clone an existing preset.
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
                Create Configuration
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
