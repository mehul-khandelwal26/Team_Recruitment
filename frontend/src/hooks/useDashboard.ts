import { useQuery } from '@tanstack/react-query';
import { apiService } from '@/lib/api-services';
import type {
  DatasetSummary,
  ExtractionRunSummary,
  RankingRunSummaryItem,
  HealthResponse,
} from '@/types';

export const DASHBOARD_QUERY_KEYS = {
  datasets: (limit = 10) => ['datasets', 'summary', limit] as const,
  extractions: (limit = 10) => ['signals', 'runs', 'summary', limit] as const,
  rankings: (limit = 10) => ['ranking', 'runs', 'summary', limit] as const,
  health: () => ['backend', 'health'] as const,
};

/**
 * Hook to retrieve the latest uploaded dataset summaries.
 */
export function useDatasetSummaries(limit = 10) {
  return useQuery<DatasetSummary[], Error>({
    queryKey: DASHBOARD_QUERY_KEYS.datasets(limit),
    queryFn: () => apiService.getDatasetSummaries(limit),
    staleTime: 1000 * 30, // 30s
    refetchOnMount: 'always',
  });
}

/**
 * Hook to retrieve the latest signal extraction run summaries.
 */
export function useExtractionRunSummaries(limit = 10) {
  return useQuery<ExtractionRunSummary[], Error>({
    queryKey: DASHBOARD_QUERY_KEYS.extractions(limit),
    queryFn: () => apiService.getExtractionRunSummaries(limit),
    staleTime: 1000 * 30,
    refetchOnMount: 'always',
  });
}

/**
 * Hook to retrieve the latest Top-X ranking run summaries.
 */
export function useRankingRunSummaries(limit = 10) {
  return useQuery<RankingRunSummaryItem[], Error>({
    queryKey: DASHBOARD_QUERY_KEYS.rankings(limit),
    queryFn: () => apiService.getRankingRunSummaries(limit),
    staleTime: 1000 * 30,
    refetchOnMount: 'always',
  });
}

/**
 * Hook to monitor backend health and storage backend status.
 */
export function useBackendHealth() {
  return useQuery<HealthResponse, Error>({
    queryKey: DASHBOARD_QUERY_KEYS.health(),
    queryFn: () => apiService.getHealth(),
    refetchInterval: 1000 * 15, // poll every 15s to keep status accurate
    retry: 1,
  });
}
