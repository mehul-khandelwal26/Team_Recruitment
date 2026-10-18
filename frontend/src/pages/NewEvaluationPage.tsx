import React, { useState, useEffect } from 'react';
import { Badge } from '@/components/ui/badge';
import { WizardStepper } from './evaluation-wizard/WizardStepper';
import { Step1Dataset } from './evaluation-wizard/Step1Dataset';
import { Step2Signals } from './evaluation-wizard/Step2Signals';
import { Step3Eligibility } from './evaluation-wizard/Step3Eligibility';
import { Step4Scoring } from './evaluation-wizard/Step4Scoring';
import { Step5ReviewAndRun } from './evaluation-wizard/Step5ReviewAndRun';
import { useRuleConfigs, useScoringConfigs } from '@/hooks/useEvaluationWizard';
import type {
  DatasetSummary,
  ExtractionRunSummary,
  RuleConfiguration,
  ScoringConfiguration,
} from '@/types';

export const NewEvaluationPage: React.FC = () => {
  // Wizard Navigation
  const [currentStep, setCurrentStep] = useState<number>(1);
  const [completedSteps, setCompletedSteps] = useState<Set<number>>(new Set());

  // Step 1: Dataset
  const [selectedDataset, setSelectedDataset] = useState<DatasetSummary | null>(null);

  // Step 2: Signals
  const [signalMode, setSignalMode] = useState<'configure' | 'reuse'>('configure');
  const [selectedSignals, setSelectedSignals] = useState<string[]>([
    'academic_cgpa',
    'academic_year',
    'normalized_cgpa_10_scale',
  ]);
  const [selectedExtractionRun, setSelectedExtractionRun] = useState<ExtractionRunSummary | null>(
    null
  );

  // Step 3: Eligibility Rules
  const [selectedRuleConfig, setSelectedRuleConfig] = useState<RuleConfiguration | null>(null);
  const { data: ruleConfigs } = useRuleConfigs();

  // Step 4: Scoring Engine
  const [selectedScoringConfig, setSelectedScoringConfig] = useState<ScoringConfiguration | null>(
    null
  );
  const { data: scoringConfigs } = useScoringConfigs();

  // Step 5: Parameters
  const [topX, setTopX] = useState<number>(5);
  const [includeNeedsReview, setIncludeNeedsReview] = useState<boolean>(false);

  // Auto-default configs when loaded
  useEffect(() => {
    if (!selectedRuleConfig && ruleConfigs && ruleConfigs.length > 0) {
      const demoOrBasic =
        ruleConfigs.find((c) => c.config_id === 'demo_mixed_review') ||
        ruleConfigs.find((c) => c.config_id === 'basic') ||
        ruleConfigs[0];
      setSelectedRuleConfig(demoOrBasic);
    }
  }, [ruleConfigs, selectedRuleConfig]);

  useEffect(() => {
    if (!selectedScoringConfig && scoringConfigs && scoringConfigs.length > 0) {
      const balancedOrDefault =
        scoringConfigs.find((c) => c.config_id === 'balanced') ||
        scoringConfigs.find((c) => c.config_id === 'default') ||
        scoringConfigs[0];
      setSelectedScoringConfig(balancedOrDefault);
    }
  }, [scoringConfigs, selectedScoringConfig]);

  // Step completion updates
  const markStepComplete = (stepNumber: number) => {
    setCompletedSteps((prev) => new Set([...prev, stepNumber]));
  };

  const handleSelectDataset = (dataset: DatasetSummary) => {
    setSelectedDataset(dataset);
    markStepComplete(1);
    // If dataset changes, clear previously selected extraction run as it was for another dataset
    setSelectedExtractionRun(null);
  };

  const handleNextFromStep1 = () => {
    if (selectedDataset) {
      markStepComplete(1);
      setCurrentStep(2);
    }
  };

  const handleNextFromStep2 = () => {
    markStepComplete(2);
    setCurrentStep(3);
  };

  const handleNextFromStep3 = () => {
    if (selectedRuleConfig) {
      markStepComplete(3);
      setCurrentStep(4);
    }
  };

  const handleNextFromStep4 = () => {
    if (selectedScoringConfig) {
      markStepComplete(4);
      setCurrentStep(5);
    }
  };

  const handleReset = () => {
    setCurrentStep(1);
    setCompletedSteps(new Set());
    setSelectedDataset(null);
    setSelectedExtractionRun(null);
    setTopX(5);
    setIncludeNeedsReview(false);
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Intro Header */}
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <Badge variant="forest" className="font-mono text-xs">
            Evaluation Wizard
          </Badge>
          <span className="text-xs text-muted-foreground">· End-to-End Pipeline Execution</span>
        </div>
        <h2 className="text-xl font-bold tracking-tight text-foreground">
          New Candidate Evaluation
        </h2>
        <p className="text-xs text-muted-foreground max-w-3xl leading-relaxed">
          Configure and execute the 5-stage automated recruitment workflow. The wizard utilizes the backend&apos;s ID-only evaluation flow to ensure instant execution, full audit trails, and deterministic selection.
        </p>
      </div>

      {/* Stepper Header */}
      <WizardStepper
        currentStep={currentStep}
        completedSteps={completedSteps}
        onStepClick={(step) => setCurrentStep(step)}
      />

      {/* Active Step Container */}
      <div className="pt-2">
        {currentStep === 1 && (
          <Step1Dataset
            selectedDataset={selectedDataset}
            onSelectDataset={handleSelectDataset}
            onNext={handleNextFromStep1}
          />
        )}

        {currentStep === 2 && selectedDataset && (
          <Step2Signals
            selectedDataset={selectedDataset}
            signalMode={signalMode}
            onSignalModeChange={setSignalMode}
            selectedSignals={selectedSignals}
            onSelectedSignalsChange={setSelectedSignals}
            selectedExtractionRun={selectedExtractionRun}
            onSelectExtractionRun={setSelectedExtractionRun}
            onBack={() => setCurrentStep(1)}
            onNext={handleNextFromStep2}
          />
        )}

        {currentStep === 3 && (
          <Step3Eligibility
            selectedRuleConfig={selectedRuleConfig}
            onSelectRuleConfig={setSelectedRuleConfig}
            onBack={() => setCurrentStep(2)}
            onNext={handleNextFromStep3}
          />
        )}

        {currentStep === 4 && (
          <Step4Scoring
            selectedScoringConfig={selectedScoringConfig}
            onSelectScoringConfig={setSelectedScoringConfig}
            onBack={() => setCurrentStep(3)}
            onNext={handleNextFromStep4}
          />
        )}

        {currentStep === 5 && selectedDataset && selectedRuleConfig && selectedScoringConfig && (
          <Step5ReviewAndRun
            selectedDataset={selectedDataset}
            signalMode={signalMode}
            selectedSignals={selectedSignals}
            selectedExtractionRun={selectedExtractionRun}
            selectedRuleConfig={selectedRuleConfig}
            selectedScoringConfig={selectedScoringConfig}
            topX={topX}
            onTopXChange={setTopX}
            includeNeedsReview={includeNeedsReview}
            onIncludeNeedsReviewChange={setIncludeNeedsReview}
            onBack={() => setCurrentStep(4)}
            onReset={handleReset}
          />
        )}
      </div>
    </div>
  );
};
