/**
 * API service layer communicating with the FastAPI backend.
 * Uses typed endpoints and models derived from the OpenAPI specification.
 */

import { apiClient } from './api-client';
import type {
  DatasetRecord,
  DatasetSummary,
  UploadResponse,
  ExtractionRunSummary,
  ExtractionRunResponse,
  SignalCatalogResponse,
  SignalDefinition,
  RuleConfiguration,
  RuleConfigurationUpdate,
  RuleConfigurationCreate,
  RuleTypeCatalogItem,
  EligibilityRunResponse,
  ManualOverride,
  ManualOverrideCreate,
  ScoringConfiguration,
  ScoringConfigurationUpdate,
  ScoringConfigurationCreate,
  ScoringCatalogResponse,
  ScoringRunResponse,
  RankingRunSummaryItem,
  RankingRunResponse,
  HealthResponse,
  FieldDiscoveryResponse,
  CanonicalFieldInfo,
  DatasetDependenciesResponse,
  ExtractionRunDependenciesResponse,
  DeleteResponse,
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
   * Retrieve full dataset record by ID, including applied field mapping and details.
   */
  getDataset(datasetId: string): Promise<DatasetRecord> {
    return apiClient.get<DatasetRecord>(`/api/ingestion/datasets/${datasetId}`);
  },

  /**
   * Inspect a candidate registration file without committing to storage.
   * Discovers columns, computes fill stats, and suggests canonical field mappings.
   */
  inspectDataset(file: File): Promise<FieldDiscoveryResponse> {
    return apiClient.upload<FieldDiscoveryResponse>('/api/ingestion/inspect', file);
  },

  /**
   * Retrieve catalog of recognized canonical target fields and descriptions.
   */
  getCanonicalFields(): Promise<CanonicalFieldInfo[]> {
    return apiClient.get<CanonicalFieldInfo[]>('/api/ingestion/canonical-fields');
  },

  /**
   * Upload a candidate registration file (CSV or JSON) with optional column mapping and optional companion resumes ZIP archive.
   */
  uploadDataset(
    file: File,
    mapping?: Record<string, string>,
    resumesArchive?: File
  ): Promise<UploadResponse> {
    const extraFields =
      mapping && Object.keys(mapping).length > 0
        ? { mapping: JSON.stringify(mapping) }
        : undefined;
    const extraFiles = resumesArchive ? { resumes_archive: resumesArchive } : undefined;
    return apiClient.upload<UploadResponse>('/api/ingestion/upload', file, extraFields, extraFiles);
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
   * Return catalog of available eligibility rule types, supported scopes, and parameters.
   */
  getRuleCatalog(): Promise<RuleTypeCatalogItem[]> {
    return apiClient.get<RuleTypeCatalogItem[]>('/api/rules/catalog');
  },

  /**
   * List the latest active version of all registered rule configurations.
   */
  getRuleConfigs(): Promise<RuleConfiguration[]> {
    return apiClient.get<RuleConfiguration[]>('/api/rules/configs');
  },

  /**
   * Retrieve a rule configuration by ID (latest version if omitted, or specific version).
   */
  getRuleConfig(configId: string, version?: number): Promise<RuleConfiguration> {
    return apiClient.get<RuleConfiguration>(`/api/rules/configs/${configId}`, {
      ...(version !== undefined ? { version } : {}),
    });
  },

  /**
   * List all available version numbers for a given rule configuration.
   */
  getRuleConfigVersions(configId: string): Promise<number[]> {
    return apiClient.get<number[]>(`/api/rules/configs/${configId}/versions`);
  },

  /**
   * Update a rule configuration by creating a new immutable version.
   */
  updateRuleConfig(
    configId: string,
    payload: RuleConfigurationUpdate
  ): Promise<RuleConfiguration> {
    return apiClient.put<RuleConfiguration>(`/api/rules/configs/${configId}`, payload);
  },

  /**
   * Create a new custom eligibility rule configuration (version 1).
   */
  createRuleConfig(payload: RuleConfigurationCreate): Promise<RuleConfiguration> {
    return apiClient.post<RuleConfiguration>('/api/rules/configs', payload);
  },

  /**
   * Soft-delete a rule configuration by marking it inactive.
   */
  deleteRuleConfig(configId: string): Promise<{ message: string }> {
    return apiClient.delete<{ message: string }>(`/api/rules/configs/${configId}`);
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
   * Return metadata catalog of criterion types, normalization methods, and aggregation strategies.
   */
  getScoringCatalog(): Promise<ScoringCatalogResponse> {
    return apiClient.get<ScoringCatalogResponse>('/api/scoring/catalog');
  },

  /**
   * List latest versions of all stored scoring configurations.
   */
  getScoringConfigs(): Promise<ScoringConfiguration[]> {
    return apiClient.get<ScoringConfiguration[]>('/api/scoring/configs');
  },

  /**
   * Retrieve a scoring configuration by ID (latest version if omitted, or specific version).
   */
  getScoringConfig(configId: string, version?: number): Promise<ScoringConfiguration> {
    return apiClient.get<ScoringConfiguration>(`/api/scoring/configs/${configId}`, {
      ...(version !== undefined ? { version } : {}),
    });
  },

  /**
   * List all available version numbers for a scoring configuration.
   */
  getScoringConfigVersions(configId: string): Promise<number[]> {
    return apiClient.get<number[]>(`/api/scoring/configs/${configId}/versions`);
  },

  /**
   * Update a scoring configuration by creating a new immutable version.
   */
  updateScoringConfig(
    configId: string,
    payload: ScoringConfigurationUpdate
  ): Promise<ScoringConfiguration> {
    return apiClient.put<ScoringConfiguration>(`/api/scoring/configs/${configId}`, payload);
  },

  /**
   * Create a new validated scoring configuration (starts at version 1).
   */
  createScoringConfig(payload: ScoringConfigurationCreate): Promise<ScoringConfiguration> {
    return apiClient.post<ScoringConfiguration>('/api/scoring/configs', payload);
  },

  /**
   * Soft-delete a scoring configuration by marking it inactive.
   */
  deleteScoringConfig(configId: string): Promise<{ message: string }> {
    return apiClient.delete<{ message: string }>(`/api/scoring/configs/${configId}`);
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

  /**
   * Retrieve an eligibility evaluation run's results (with any manual overrides merged).
   */
  getEligibilityRun(runId: string): Promise<EligibilityRunResponse> {
    return apiClient.get<EligibilityRunResponse>(`/api/rules/runs/${runId}`);
  },

  /**
   * Apply an organizer's manual eligibility override to a team in an evaluation run.
   */
  applyTeamEligibilityOverride(
    eligibilityRunId: string,
    teamId: string,
    payload: ManualOverrideCreate
  ): Promise<ManualOverride> {
    return apiClient.post<ManualOverride>(
      `/api/rules/runs/${eligibilityRunId}/teams/${teamId}/override`,
      payload
    );
  },

  /**
   * Export a recorded ranking run as a CSV file.
   */
  exportRankingRunCsv(runId: string): Promise<{ blob: Blob; filename?: string }> {
    return apiClient.downloadBlob(`/api/ranking/runs/${runId}/export`);
  },

  /**
   * Check dependent run counts for a dataset before deletion.
   */
  getDatasetDependencies(datasetId: string): Promise<DatasetDependenciesResponse> {
    return apiClient.get<DatasetDependenciesResponse>(`/api/ingestion/datasets/${datasetId}/dependencies`);
  },

  /**
   * Permanently delete a dataset from backend storage.
   */
  deleteDataset(datasetId: string, cascade = false): Promise<DeleteResponse> {
    return apiClient.delete<DeleteResponse>(`/api/ingestion/datasets/${datasetId}`, {
      params: { cascade },
    });
  },

  /**
   * Permanently delete a recorded ranking run from backend storage.
   */
  deleteRankingRun(runId: string): Promise<DeleteResponse> {
    return apiClient.delete<DeleteResponse>(`/api/ranking/runs/${runId}`);
  },

  /**
   * Check dependent run counts for a signal extraction run before deletion.
   */
  getExtractionRunDependencies(runId: string): Promise<ExtractionRunDependenciesResponse> {
    return apiClient.get<ExtractionRunDependenciesResponse>(`/api/signals/runs/${runId}/dependencies`);
  },

  /**
   * Permanently delete an extraction run from backend storage.
   */
  deleteExtractionRun(runId: string, cascade = false): Promise<DeleteResponse> {
    return apiClient.delete<DeleteResponse>(`/api/signals/runs/${runId}`, {
      params: { cascade },
    });
  },
};


