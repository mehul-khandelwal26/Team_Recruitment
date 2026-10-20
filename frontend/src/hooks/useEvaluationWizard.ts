import { useQuery } from '@tanstack/react-query';
import { apiService } from '@/lib/api-services';
import type {
  DatasetSummary,
  ExtractionRunSummary,
  RuleConfiguration,
  ScoringConfiguration,
  SignalDefinition,
} from '@/types';

export const WIZARD_QUERY_KEYS = {
  datasets: (limit = 50) => ['wizard', 'datasets', limit] as const,
  datasetRecord: (datasetId?: string) => ['wizard', 'dataset', datasetId] as const,
  extractionsForDataset: (datasetId?: string) => ['wizard', 'extractions', datasetId] as const,
  ruleConfigs: () => ['wizard', 'rules', 'configs'] as const,
  scoringConfigs: () => ['wizard', 'scoring', 'configs'] as const,
  signals: () => ['wizard', 'signals'] as const,
};

/**
 * Hook to retrieve available datasets for evaluation selection.
 */
export function useWizardDatasets(limit = 50) {
  return useQuery<DatasetSummary[], Error>({
    queryKey: WIZARD_QUERY_KEYS.datasets(limit),
    queryFn: () => apiService.getDatasetSummaries(limit),
    staleTime: 1000 * 30,
    refetchOnMount: 'always',
  });
}

/**
 * Hook to retrieve a specific dataset record with full schema and applied field mappings.
 */
export function useDatasetRecord(datasetId?: string) {
  return useQuery({
    queryKey: WIZARD_QUERY_KEYS.datasetRecord(datasetId),
    queryFn: () => (datasetId ? apiService.getDataset(datasetId) : null),
    enabled: Boolean(datasetId),
    staleTime: 1000 * 60,
  });
}

/**
 * Hook to retrieve existing extraction runs for a selected dataset.
 */
export function useWizardExtractions(datasetId?: string) {
  return useQuery<ExtractionRunSummary[], Error>({
    queryKey: WIZARD_QUERY_KEYS.extractionsForDataset(datasetId),
    queryFn: () => apiService.getExtractionRunSummaries(50, datasetId),
    enabled: Boolean(datasetId),
    staleTime: 1000 * 30,
    refetchOnMount: 'always',
  });
}

/**
 * Hook to retrieve available rule configurations.
 */
export function useRuleConfigs() {
  return useQuery<RuleConfiguration[], Error>({
    queryKey: WIZARD_QUERY_KEYS.ruleConfigs(),
    queryFn: () => apiService.getRuleConfigs(),
    staleTime: 1000 * 60,
  });
}

/**
 * Hook to retrieve available scoring configurations.
 */
export function useScoringConfigs() {
  return useQuery<ScoringConfiguration[], Error>({
    queryKey: WIZARD_QUERY_KEYS.scoringConfigs(),
    queryFn: () => apiService.getScoringConfigs(),
    staleTime: 1000 * 60,
  });
}

/**
 * Hook to retrieve the list of individually selectable signals.
 */
export function useAvailableSignals() {
  return useQuery<SignalDefinition[], Error>({
    queryKey: WIZARD_QUERY_KEYS.signals(),
    queryFn: () => apiService.getIndividualSignals(),
    staleTime: 1000 * 120,
    retry: 1,
  });
}
