/**
 * Convenience re-exports and domain type aliases derived from generated OpenAPI schema.
 */

import type { components, paths } from './api';

export type Schema<T extends keyof components['schemas']> = components['schemas'][T];

// Ingestion & Dataset models
export type DatasetRecord = Schema<'DatasetRecord'>;
export type DatasetSummary = Schema<'DatasetSummary'>;
export type UploadResponse = Schema<'UploadResponse'>;
export type ValidationWarning = Schema<'ValidationWarning'>;
export type ValidationError = Schema<'ValidationError'>;

// Signals & Extraction models
export type ExtractionRunResponse = Schema<'ExtractionRunResponse-Output'>;
export type ExtractionRunSummary = Schema<'ExtractionRunSummary'>;
export type SignalDefinition = Schema<'SignalDefinition'>;
export type SignalCatalogResponse = Schema<'SignalCatalogResponse'>;

// Rules & Eligibility models
export type RuleConfiguration = Schema<'RuleConfiguration'>;
export type RuleConfigurationUpdate = Schema<'RuleConfigurationUpdate'>;
export type RuleConfigurationCreate = Schema<'RuleConfigurationCreate'>;
export type RuleDefinition = Schema<'RuleDefinition'>;
export type RuleTypeCatalogItem = Schema<'RuleTypeCatalogItem'>;
export type EligibilityRunResponse = Schema<'EligibilityRunResponse'>;
export type TeamEligibilityResult = Schema<'TeamEligibilityResult'>;
export type ManualOverride = Schema<'ManualOverride'>;
export type ManualOverrideCreate = Schema<'ManualOverrideCreate'>;
export type RuleResult = Schema<'RuleResult'>;

// Scoring models
export type ScoringConfiguration = Schema<'ScoringConfiguration-Output'>;
export type ScoringConfigurationUpdate = Schema<'ScoringConfigurationUpdate'>;
export type ScoringConfigurationCreate = Schema<'ScoringConfigurationCreate'>;
export type EvaluationCriterionInput = Schema<'EvaluationCriterion-Input'>;
export type EvaluationCriterionOutput = Schema<'EvaluationCriterion-Output'>;
export type ScoringCatalogResponse = Schema<'ScoringCatalogResponse'>;
export type ScoringRunResponse = Schema<'ScoringRunResponse'>;
export type TeamScoringResult = Schema<'TeamScoringResult'>;
export type CriterionScoreBreakdown = Schema<'CriterionScoreBreakdown'>;

// Ranking models
export type RankingRunResponse = Schema<'RankingRunResponse'>;
export type RankingRunSummary = Schema<'RankingRunSummary'>;
export type RankingRunSummaryItem = Schema<'RankingRunSummaryItem'>;
export type RankedTeamResult = Schema<'RankedTeamResult'>;
export type ExcludedTeamResult = Schema<'ExcludedTeamResult'>;

export type HealthResponse = {
  status: string;
  environment: string;
  version: string;
  storage_backend: string;
};

// Navigation types
export type NavItem = {
  title: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  description?: string;
  badge?: string;
};

// Re-export paths and components
export type { paths, components };
