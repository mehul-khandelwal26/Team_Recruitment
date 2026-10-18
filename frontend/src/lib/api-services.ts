/**
 * API service layer communicating with the FastAPI backend.
 * Uses typed endpoints and models derived from the OpenAPI specification.
 */

import { apiClient } from './api-client';
import type {
  DatasetSummary,
  UploadResponse,
  ExtractionRunSummary,
  ExtractionRunResponse,
  SignalCatalogResponse,
  SignalDefinition,
  RuleConfiguration,
  EligibilityRunResponse,
  ScoringConfiguration,
  ScoringRunResponse,
  RankingRunSummaryItem,
  RankingRunResponse,
  HealthResponse,
} from '@/types';

export const apiService = {
  /**
   * Health status of the backend server.
   */
  getHealth(): Promise<HealthResponse> {
    return apiClient.get<HealthResponse>('/api/health');
  },

  /**
   * Lightweight list of uploaded datasets (newest first).
   */
  getDatasetSummaries(limit = 50): Promise<DatasetSummary[]> {
    return apiClient.get<DatasetSummary[]>('/api/ingestion/datasets', {
      summary: true,
      limit,
    });
  },

  /**
   * Upload a candidate registration file (CSV or JSON).
   */
  uploadDataset(file: File): Promise<UploadResponse> {
    return apiClient.upload<UploadResponse>('/api/ingestion/upload', file);
  },

  /**
   * Retrieve catalog of registered categories, analyzers, and supported signals.
   */
  getSignalCatalog(): Promise<SignalCatalogResponse> {
    return apiClient.get<SignalCatalogResponse>('/api/signals/catalog');
  },

  /**
   * Return all individually selectable evaluation signals supported across analyzers.
   */
  getIndividualSignals(): Promise<SignalDefinition[]> {
    return apiClient.get<SignalDefinition[]>('/api/signals/signals');
  },

  /**
   * Execute signal extraction for teams and their members against a stored dataset.
   */
  extractSignals(datasetId: string, selectedSignals: string[]): Promise<ExtractionRunResponse> {
    return apiClient.post<ExtractionRunResponse>('/api/signals/extract', {
      dataset_id: datasetId,
      selected_signals: selectedSignals,
    });
  },

  /**
   * Lightweight list of signal extraction runs (newest first).
   */
  getExtractionRunSummaries(limit = 50, datasetId?: string): Promise<ExtractionRunSummary[]> {
    return apiClient.get<ExtractionRunSummary[]>('/api/signals/runs', {
      summary: true,
      limit,
      ...(datasetId ? { dataset_id: datasetId } : {}),
    });
  },

  /**
   * List the latest active version of all registered rule configurations.
   */
  getRuleConfigs(): Promise<RuleConfiguration[]> {
    return apiClient.get<RuleConfiguration[]>('/api/rules/configs');
  },

  /**
   * Execute deterministic eligibility evaluation against teams and signals.
   */
  evaluateEligibility(
    datasetId: string,
    extractionRunId: string,
    configId: string,
    configVersion?: number
  ): Promise<EligibilityRunResponse> {
    return apiClient.post<EligibilityRunResponse>('/api/rules/evaluate', {
      dataset_id: datasetId,
      extraction_run_id: extractionRunId,
      config_id: configId,
      ...(configVersion !== undefined ? { config_version: configVersion } : {}),
    });
  },

  /**
   * List latest versions of all stored scoring configurations.
   */
  getScoringConfigs(): Promise<ScoringConfiguration[]> {
    return apiClient.get<ScoringConfiguration[]>('/api/scoring/configs');
  },

  /**
   * Evaluate teams against a scoring configuration.
   */
  evaluateScoring(
    eligibilityRunId: string,
    configId: string,
    configVersion?: number
  ): Promise<ScoringRunResponse> {
    return apiClient.post<ScoringRunResponse>('/api/scoring/evaluate', {
      eligibility_run_id: eligibilityRunId,
      config_id: configId,
      ...(configVersion !== undefined ? { config_version: configVersion } : {}),
    });
  },

  /**
   * Execute deterministic Top-X ranking and selection from scoring results.
   */
  evaluateRanking(
    scoringRunId: string,
    eligibilityRunId: string,
    topX: number,
    includeNeedsReview = false
  ): Promise<RankingRunResponse> {
    return apiClient.post<RankingRunResponse>('/api/ranking/evaluate', {
      scoring_run_id: scoringRunId,
      eligibility_run_id: eligibilityRunId,
      top_x: topX,
      include_needs_review: includeNeedsReview,
    });
  },

  /**
   * Lightweight list of Top-X ranking runs (newest first).
   */
  getRankingRunSummaries(limit = 10): Promise<RankingRunSummaryItem[]> {
    return apiClient.get<RankingRunSummaryItem[]>('/api/ranking/runs', {
      summary: true,
      limit,
    });
  },

  /**
   * Retrieve a recorded ranking run with all shortlisted teams, breakdowns, and exclusions.
   */
  getRankingRun(runId: string): Promise<RankingRunResponse> {
    return apiClient.get<RankingRunResponse>(`/api/ranking/runs/${runId}`);
  },
};

