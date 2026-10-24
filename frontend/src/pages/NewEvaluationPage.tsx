import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Info, X, RotateCcw } from 'lucide-react';
import { WizardStepper } from './evaluation-wizard/WizardStepper';
import { Step1Dataset } from './evaluation-wizard/Step1Dataset';
import { Step2Signals } from './evaluation-wizard/Step2Signals';
import { Step3Eligibility } from './evaluation-wizard/Step3Eligibility';
import { Step4Scoring } from './evaluation-wizard/Step4Scoring';
import { Step5ReviewAndRun } from './evaluation-wizard/Step5ReviewAndRun';
import {
  useRuleConfigs,
  useScoringConfigs,
  useWizardDatasets,
  useWizardExtractions,
  useWizardParameters,
} from '@/hooks/useEvaluationWizard';
import type {
  DatasetSummary,
  ExtractionRunSummary,
  RuleConfiguration,
  ScoringConfiguration,
} from '@/types';

const STEP_STAGE_INFO: Record<number, { title: string; desc: string }> = {
  1: {
    title: 'Dataset Ingestion & Selection',
    desc: 'Select an existing registered candidate cohort or upload a new CSV / JSON dataset.',
  },
  2: {
    title: 'Signal Extraction & Calibration',
    desc: 'Extract and calibrate academic performance, parsed resume credentials, and GitHub metrics.',
  },
  3: {
    title: 'Eligibility Verification Rules',
    desc: 'Select or adjust automated gatekeeping rules to screen candidate qualifications.',
  },
  4: {
    title: 'Multi-Criteria Scoring Weights',
    desc: 'Apply normalized weighted scoring models across academic, technical skill, and portfolio dimensions.',
  },
  5: {
    title: 'Pipeline Review & Shortlist Execution',
    desc: 'Inspect the pre-flight configuration, specify Top-X team cutoff targets, and generate rankings.',
  },
};

export const NewEvaluationPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const urlDatasetId = searchParams.get('dataset_id');
  const urlExtractionRunId = searchParams.get('extraction_run_id');
  const urlTab = searchParams.get('tab') as 'existing' | 'upload' | null;

  // Wizard Navigation
  const [currentStep, setCurrentStep] = useState<number>(1);
  const [completedSteps, setCompletedSteps] = useState<Set<number>>(new Set());

  // Step 1: Dataset
  const [selectedDataset, setSelectedDataset] = useState<DatasetSummary | null>(null);

  // Queries for auto-selection
  const { data: datasets } = useWizardDatasets(50);
  const { data: extractions } = useWizardExtractions(
    selectedDataset?.dataset_id || urlDatasetId || undefined
  );

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
  const {
    allowScaleConversion,
    setAllowScaleConversion,
    tiebreakCriterionId,
    setTiebreakCriterionId,
    resetWizard: resetWizardParams,
  } = useWizardParameters();

  // Auto-select dataset if specified in URL query params
  useEffect(() => {
    if (urlDatasetId && datasets && !selectedDataset) {
      const match = datasets.find((d) => d.dataset_id === urlDatasetId);
      if (match) {
        setSelectedDataset(match);
        setCompletedSteps((prev) => new Set([...prev, 1]));
      }
    }
  }, [urlDatasetId, datasets, selectedDataset]);

  // Auto-select extraction run if specified in URL query params
  useEffect(() => {
    if (urlExtractionRunId && extractions && !selectedExtractionRun) {
      const match = extractions.find((e) => e.run_id === urlExtractionRunId);
      if (match) {
        setSignalMode('reuse');
        setSelectedExtractionRun(match);
        setCompletedSteps((prev) => new Set([...prev, 1, 2]));
        if (selectedDataset || urlDatasetId) {
          setCurrentStep(3);
        }
      }
    }
  }, [urlExtractionRunId, extractions, selectedExtractionRun, selectedDataset, urlDatasetId]);

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

  const handleSelectDataset = (dataset: DatasetSummary | null) => {
    setSelectedDataset(dataset);
    if (dataset) {
      markStepComplete(1);
    } else {
      setCompletedSteps((prev) => {
        const next = new Set(prev);
        next.delete(1);
        return next;
      });
    }
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
    resetWizardParams();
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Context Stage Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-1 border-b border-border/60">
        <div className="space-y-0.5">
          <div className="flex items-center gap-2">
            <Badge variant="forest" className="font-mono text-[10px] tracking-wider uppercase px-2 py-0.5 font-semibold">
              Stage {currentStep} of 5
            </Badge>
            <span className="text-xs font-semibold text-foreground">
              {STEP_STAGE_INFO[currentStep]?.title || 'Evaluation Pipeline'}
            </span>
          </div>
          <p className="text-xs text-muted-foreground leading-relaxed">
            {STEP_STAGE_INFO[currentStep]?.desc}
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0 self-start sm:self-auto">
          {selectedDataset && (
            <Badge variant="outline" className="text-xs bg-muted/40 gap-1.5 py-1 px-2.5 font-normal">
              <span className="w-1.5 h-1.5 rounded-full bg-forest-600 animate-pulse" />
              <span className="text-muted-foreground">Active Cohort:</span>
              <strong className="font-semibold text-foreground truncate max-w-[180px]">
                {selectedDataset.filename}
              </strong>
            </Badge>
          )}

          {(currentStep > 1 || completedSteps.size > 0 || selectedDataset !== null) && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleReset}
              className="h-7 px-2.5 text-xs text-muted-foreground hover:text-foreground gap-1.5"
              title="Reset evaluation wizard to initial state"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              Reset Wizard
            </Button>
          )}
        </div>
      </div>

      {/* Deep-link Notice Banner if initialized from dashboard */}
      {(urlDatasetId || urlExtractionRunId) && (
        <div className="flex items-center justify-between p-3 px-4 rounded-lg border border-forest-200 bg-forest-50/70 text-xs text-forest-900 shadow-xs">
          <div className="flex items-center gap-2">
            <Info className="h-4 w-4 text-forest-700 shrink-0" />
            <span>
              Pipeline pre-loaded from Dashboard:
              {selectedDataset && (
                <span className="font-semibold ml-1">
                  Dataset &ldquo;{selectedDataset.filename}&rdquo;
                </span>
              )}
              {selectedExtractionRun && (
                <span className="ml-1">
                  with Extraction Run <code className="font-mono">{selectedExtractionRun.run_id.slice(0, 8)}...</code>
                </span>
              )}
            </span>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setSearchParams({});
              handleReset();
            }}
            className="h-6 px-2 text-[11px] text-forest-800 hover:text-forest-950 hover:bg-forest-100/60 gap-1"
          >
            <X className="h-3 w-3" />
            Clear
          </Button>
        </div>
      )}

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
            initialTab={urlTab === 'upload' ? 'upload' : 'existing'}
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
            allowScaleConversion={allowScaleConversion}
            onAllowScaleConversionChange={setAllowScaleConversion}
            activeMapping={selectedDataset.mapping as Record<string, string> || undefined}
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
            allowScaleConversion={allowScaleConversion}
            tiebreakCriterionId={tiebreakCriterionId}
            onTiebreakCriterionIdChange={setTiebreakCriterionId}
            onBack={() => setCurrentStep(4)}
            onReset={handleReset}
          />
        )}
      </div>
    </div>
  );
};
