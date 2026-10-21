import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiService } from '@/lib/api-services';
import type {
  RuleConfiguration,
  RuleConfigurationUpdate,
  RuleConfigurationCreate,
  RuleTypeCatalogItem,
  ScoringConfiguration,
  ScoringConfigurationUpdate,
  ScoringConfigurationCreate,
  ScoringCatalogResponse,
} from '@/types';

export const CONFIG_QUERY_KEYS = {
  ruleConfigs: () => ['rules', 'configs'] as const,
  ruleConfig: (id: string, version?: number) =>
    ['rules', 'configs', id, version !== undefined ? version : 'latest'] as const,
  ruleConfigVersions: (id: string) => ['rules', 'configs', id, 'versions'] as const,
  ruleCatalog: () => ['rules', 'catalog'] as const,

  scoringConfigs: () => ['scoring', 'configs'] as const,
  scoringConfig: (id: string, version?: number) =>
    ['scoring', 'configs', id, version !== undefined ? version : 'latest'] as const,
  scoringConfigVersions: (id: string) => ['scoring', 'configs', id, 'versions'] as const,
  scoringCatalog: () => ['scoring', 'catalog'] as const,
};

// ---------------------------------------------------------------------------
// Eligibility Rules Hooks
// ---------------------------------------------------------------------------

export function useRuleConfigs() {
  return useQuery<RuleConfiguration[], Error>({
    queryKey: CONFIG_QUERY_KEYS.ruleConfigs(),
    queryFn: () => apiService.getRuleConfigs(),
    staleTime: 1000 * 30,
    refetchOnMount: 'always',
  });
}

export function useRuleConfig(configId: string | null, version?: number) {
  return useQuery<RuleConfiguration, Error>({
    queryKey: configId
      ? CONFIG_QUERY_KEYS.ruleConfig(configId, version)
      : ['rules', 'configs', 'noop'],
    queryFn: () => {
      if (!configId) throw new Error('configId is required');
      return apiService.getRuleConfig(configId, version);
    },
    enabled: Boolean(configId),
    staleTime: 1000 * 30,
  });
}

export function useRuleConfigVersions(configId: string | null) {
  return useQuery<number[], Error>({
    queryKey: configId
      ? CONFIG_QUERY_KEYS.ruleConfigVersions(configId)
      : ['rules', 'configs', 'noop', 'versions'],
    queryFn: () => {
      if (!configId) throw new Error('configId is required');
      return apiService.getRuleConfigVersions(configId);
    },
    enabled: Boolean(configId),
    staleTime: 1000 * 30,
  });
}

export function useRuleCatalog() {
  return useQuery<RuleTypeCatalogItem[], Error>({
    queryKey: CONFIG_QUERY_KEYS.ruleCatalog(),
    queryFn: () => apiService.getRuleCatalog(),
    staleTime: 1000 * 60 * 5,
  });
}

export function useUpdateRuleConfigMutation() {
  const queryClient = useQueryClient();

  return useMutation<
    RuleConfiguration,
    Error,
    { configId: string; payload: RuleConfigurationUpdate }
  >({
    mutationFn: ({ configId, payload }) => apiService.updateRuleConfig(configId, payload),
    onSuccess: (updated) => {
      // Invalidate both local config list and wizard config list
      queryClient.invalidateQueries({ queryKey: CONFIG_QUERY_KEYS.ruleConfigs() });
      queryClient.invalidateQueries({ queryKey: ['wizard', 'rules', 'configs'] });
      queryClient.invalidateQueries({ queryKey: ['rules', 'configs', updated.config_id] });
    },
  });
}

export function useCreateRuleConfigMutation() {
  const queryClient = useQueryClient();

  return useMutation<RuleConfiguration, Error, RuleConfigurationCreate>({
    mutationFn: (payload) => apiService.createRuleConfig(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CONFIG_QUERY_KEYS.ruleConfigs() });
      queryClient.invalidateQueries({ queryKey: ['wizard', 'rules', 'configs'] });
    },
  });
}

export function useDeleteRuleConfigMutation() {
  const queryClient = useQueryClient();

  return useMutation<{ message: string }, Error, string>({
    mutationFn: (configId: string) => apiService.deleteRuleConfig(configId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CONFIG_QUERY_KEYS.ruleConfigs() });
      queryClient.invalidateQueries({ queryKey: ['wizard', 'rules', 'configs'] });
    },
  });
}

// ---------------------------------------------------------------------------
// Scoring Configurations Hooks
// ---------------------------------------------------------------------------

export function useScoringConfigs() {
  return useQuery<ScoringConfiguration[], Error>({
    queryKey: CONFIG_QUERY_KEYS.scoringConfigs(),
    queryFn: () => apiService.getScoringConfigs(),
    staleTime: 1000 * 30,
    refetchOnMount: 'always',
  });
}

export function useScoringConfig(configId: string | null, version?: number) {
  return useQuery<ScoringConfiguration, Error>({
    queryKey: configId
      ? CONFIG_QUERY_KEYS.scoringConfig(configId, version)
      : ['scoring', 'configs', 'noop'],
    queryFn: () => {
      if (!configId) throw new Error('configId is required');
      return apiService.getScoringConfig(configId, version);
    },
    enabled: Boolean(configId),
    staleTime: 1000 * 30,
  });
}

export function useScoringConfigVersions(configId: string | null) {
  return useQuery<number[], Error>({
    queryKey: configId
      ? CONFIG_QUERY_KEYS.scoringConfigVersions(configId)
      : ['scoring', 'configs', 'noop', 'versions'],
    queryFn: () => {
      if (!configId) throw new Error('configId is required');
      return apiService.getScoringConfigVersions(configId);
    },
    enabled: Boolean(configId),
    staleTime: 1000 * 30,
  });
}

export function useScoringCatalog() {
  return useQuery<ScoringCatalogResponse, Error>({
    queryKey: CONFIG_QUERY_KEYS.scoringCatalog(),
    queryFn: () => apiService.getScoringCatalog(),
    staleTime: 1000 * 60 * 5,
  });
}

export function useUpdateScoringConfigMutation() {
  const queryClient = useQueryClient();

  return useMutation<
    ScoringConfiguration,
    Error,
    { configId: string; payload: ScoringConfigurationUpdate }
  >({
    mutationFn: ({ configId, payload }) => apiService.updateScoringConfig(configId, payload),
    onSuccess: (updated) => {
      // Invalidate both local config list and wizard config list
      queryClient.invalidateQueries({ queryKey: CONFIG_QUERY_KEYS.scoringConfigs() });
      queryClient.invalidateQueries({ queryKey: ['wizard', 'scoring', 'configs'] });
      queryClient.invalidateQueries({ queryKey: ['scoring', 'configs', updated.config_id] });
    },
  });
}

export function useCreateScoringConfigMutation() {
  const queryClient = useQueryClient();

  return useMutation<ScoringConfiguration, Error, ScoringConfigurationCreate>({
    mutationFn: (payload) => apiService.createScoringConfig(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CONFIG_QUERY_KEYS.scoringConfigs() });
      queryClient.invalidateQueries({ queryKey: ['wizard', 'scoring', 'configs'] });
    },
  });
}

export function useDeleteScoringConfigMutation() {
  const queryClient = useQueryClient();

  return useMutation<{ message: string }, Error, string>({
    mutationFn: (configId: string) => apiService.deleteScoringConfig(configId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CONFIG_QUERY_KEYS.scoringConfigs() });
      queryClient.invalidateQueries({ queryKey: ['wizard', 'scoring', 'configs'] });
    },
  });
}
