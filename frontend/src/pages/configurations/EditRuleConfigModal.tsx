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
} from 'lucide-react';
import type { RuleConfiguration, RuleDefinition } from '@/types';
import { useUpdateRuleConfigMutation } from '@/hooks/useConfigurations';

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

  const [description, setDescription] = useState(config.description || '');
  const [rules, setRules] = useState<RuleDefinition[]>([]);
  const [showConfirm, setShowConfirm] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setDescription(config.description || '');
      setRules(
        (config.rules || []).map((r) => ({
          ...r,
        }))
      );
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

  const handleReviewClick = () => {
    const activeRules = rules.filter((r) => r.is_enabled);
    if (activeRules.length === 0) {
      setErrorMessage('At least one rule must be enabled in the configuration.');
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
          rules,
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
      <DialogContent onClose={() => onOpenChange(false)} className="max-w-3xl">
        <DialogHeader>
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
            Enable or disable individual evaluator rules, adjust rule severity, and modify missing-data
            handling. Saving produces an immutable version preserving past runs.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-3 overflow-y-auto max-h-[60vh] pr-1">
          {errorMessage && (
            <div className="p-3 rounded-lg border border-red-300 bg-red-50 text-red-800 text-xs flex items-start gap-2">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Description */}
          <div className="space-y-1 p-3 bg-muted/40 rounded-lg border border-border/70">
            <label className="text-xs font-semibold text-foreground">Configuration Description</label>
            <Input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe eligibility requirements..."
              className="text-xs h-8"
            />
          </div>

          {/* Rules Table */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs font-semibold text-foreground">
              <span className="flex items-center gap-1.5">
                <Layers className="h-3.5 w-3.5 text-forest-700" />
                Rule Evaluators ({rules.filter((r) => r.is_enabled).length}/{rules.length} Active)
              </span>
            </div>

            <div className="border border-border rounded-lg overflow-hidden">
              <table className="w-full text-left text-xs">
                <thead className="bg-muted/60 border-b border-border text-[11px] text-muted-foreground">
                  <tr>
                    <th className="py-2 px-3 w-10 text-center">Active</th>
                    <th className="py-2 px-3">Rule Definition</th>
                    <th className="py-2 px-3 w-32">Severity</th>
                    <th className="py-2 px-3 w-36">On Missing</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {rules.map((rule, idx) => (
                    <tr
                      key={rule.rule_id}
                      className={`hover:bg-muted/30 transition-colors ${
                        !rule.is_enabled ? 'opacity-50 bg-muted/10' : ''
                      }`}
                    >
                      <td className="py-2.5 px-3 text-center">
                        <input
                          type="checkbox"
                          checked={rule.is_enabled}
                          onChange={() => handleToggleEnabled(idx)}
                          className="h-3.5 w-3.5 rounded border-border text-forest-700 focus:ring-forest-600 cursor-pointer"
                        />
                      </td>
                      <td className="py-2.5 px-3">
                        <div className="font-semibold text-foreground">{rule.name}</div>
                        <div className="text-[10px] text-muted-foreground font-mono mt-0.5">
                          {rule.rule_id} · type: <span className="text-forest-700">{rule.rule_type}</span>
                        </div>
                        {rule.description && (
                          <div className="text-[11px] text-muted-foreground mt-0.5 line-clamp-1">
                            {rule.description}
                          </div>
                        )}
                      </td>
                      <td className="py-2.5 px-3">
                        <select
                          disabled={!rule.is_enabled}
                          value={rule.severity}
                          onChange={(e) => handleSeverityChange(idx, e.target.value as any)}
                          className="h-7 text-xs rounded border border-border bg-card px-2 text-foreground focus:outline-none focus:ring-1 focus:ring-forest-600 disabled:opacity-50"
                        >
                          <option value="hard">hard (disqualifies)</option>
                          <option value="soft">soft (advisory)</option>
                        </select>
                      </td>
                      <td className="py-2.5 px-3">
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
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
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
