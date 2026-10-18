/**
 * API service layer communicating with the FastAPI backend.
 * Uses typed endpoints and models derived from the OpenAPI specification.
 */

import { apiClient } from './api-client';
import type {
  DatasetSummary,
  ExtractionRunSummary,
  RankingRunSummaryItem,
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
  getDatasetSummaries(limit = 10): Promise<DatasetSummary[]> {
    return apiClient.get<DatasetSummary[]>('/api/ingestion/datasets', {
      summary: true,
      limit,
    });
  },

  /**
   * Lightweight list of signal extraction runs (newest first).
   */
  getExtractionRunSummaries(limit = 10, datasetId?: string): Promise<ExtractionRunSummary[]> {
    return apiClient.get<ExtractionRunSummary[]>('/api/signals/runs', {
      summary: true,
      limit,
      ...(datasetId ? { dataset_id: datasetId } : {}),
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
};
