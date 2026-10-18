import React from 'react';
import { Check, FolderUp, Cpu, ShieldCheck, Calculator, Trophy } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface StepDef {
  number: number;
  id: string;
  title: string;
  shortTitle: string;
  icon: React.ComponentType<{ className?: string }>;
}

export const WIZARD_STEPS: StepDef[] = [
  {
    number: 1,
    id: 'dataset',
    title: 'Dataset Ingestion & Selection',
    shortTitle: 'Dataset',
    icon: FolderUp,
  },
  {
    number: 2,
    id: 'signals',
    title: 'Signal Extraction',
    shortTitle: 'Signals',
    icon: Cpu,
  },
  {
    number: 3,
    id: 'eligibility',
    title: 'Eligibility Verification',
    shortTitle: 'Eligibility',
    icon: ShieldCheck,
  },
  {
    number: 4,
    id: 'scoring',
    title: 'Multi-Criteria Scoring',
    shortTitle: 'Scoring',
    icon: Calculator,
  },
  {
    number: 5,
    id: 'review',
    title: 'Review & Execute Pipeline',
    shortTitle: 'Review & Run',
    icon: Trophy,
  },
];

interface WizardStepperProps {
  currentStep: number;
  completedSteps: Set<number>;
  onStepClick: (step: number) => void;
  isExecuting?: boolean;
}

export const WizardStepper: React.FC<WizardStepperProps> = ({
  currentStep,
  completedSteps,
  onStepClick,
  isExecuting = false,
}) => {
  return (
    <div className="w-full">
      {/* Desktop Stepper */}
      <div className="hidden md:grid md:grid-cols-5 gap-2">
        {WIZARD_STEPS.map((step) => {
          const isCurrent = currentStep === step.number;
          const isCompleted = completedSteps.has(step.number);
          const isClickable = !isExecuting && (isCompleted || step.number < currentStep);
          const Icon = step.icon;

          return (
            <button
              key={step.number}
              type="button"
              disabled={!isClickable && !isCurrent}
              onClick={() => isClickable && onStepClick(step.number)}
              className={cn(
                'group flex items-center gap-3 p-3 rounded-lg border text-left transition-all',
                isCurrent &&
                  'bg-forest-50/70 border-forest-600/70 shadow-sm ring-1 ring-forest-600/20',
                isCompleted && !isCurrent && 'bg-card border-border hover:border-forest-300 hover:bg-muted/40 cursor-pointer',
                !isCurrent && !isCompleted && 'bg-muted/20 border-border/60 opacity-60 cursor-not-allowed'
              )}
            >
              <div
                className={cn(
                  'flex h-7 w-7 shrink-0 items-center justify-center rounded-md font-mono text-xs font-semibold transition-colors',
                  isCurrent && 'bg-forest-800 text-white',
                  isCompleted && !isCurrent && 'bg-emerald-100 text-emerald-800 border border-emerald-300',
                  !isCurrent && !isCompleted && 'bg-muted text-muted-foreground border border-border'
                )}
              >
                {isCompleted && !isCurrent ? (
                  <Check className="h-3.5 w-3.5 stroke-[2.5]" />
                ) : (
                  <span>{step.number}</span>
                )}
              </div>

              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5">
                  <Icon
                    className={cn(
                      'h-3.5 w-3.5 shrink-0',
                      isCurrent
                        ? 'text-forest-800'
                        : isCompleted
                          ? 'text-emerald-700'
                          : 'text-muted-foreground'
                    )}
                  />
                  <span
                    className={cn(
                      'text-xs font-semibold truncate',
                      isCurrent
                        ? 'text-forest-950 font-bold'
                        : isCompleted
                          ? 'text-foreground'
                          : 'text-muted-foreground'
                    )}
                  >
                    {step.shortTitle}
                  </span>
                </div>
                <p className="text-[10px] text-muted-foreground truncate leading-tight mt-0.5">
                  {step.title}
                </p>
              </div>
            </button>
          );
        })}
      </div>

      {/* Mobile Stepper Header */}
      <div className="md:hidden flex items-center justify-between p-3 rounded-lg border border-border bg-card">
        <div className="flex items-center gap-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-forest-800 text-white font-mono text-xs font-bold">
            {currentStep}
          </div>
          <div>
            <span className="text-xs text-muted-foreground block font-medium">
              Step {currentStep} of {WIZARD_STEPS.length}
            </span>
            <span className="text-sm font-bold text-foreground">
              {WIZARD_STEPS[currentStep - 1]?.title}
            </span>
          </div>
        </div>
        <div className="flex gap-1">
          {WIZARD_STEPS.map((s) => (
            <div
              key={s.number}
              className={cn(
                'h-1.5 w-5 rounded-full transition-colors',
                s.number === currentStep
                  ? 'bg-forest-800'
                  : completedSteps.has(s.number)
                    ? 'bg-emerald-500'
                    : 'bg-muted'
              )}
            />
          ))}
        </div>
      </div>
    </div>
  );
};
