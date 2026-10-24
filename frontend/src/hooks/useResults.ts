import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiService } from '@/lib/api-services';
import type {
  RankingRunResponse,
  RankingRunSummaryItem,
  EligibilityRunResponse,
  ManualOverrideCreate,
  ManualOverride,
} from '@/types';

export const RESULTS_QUERY_KEYS = {
  rankingRun: (runId?: string | null) => ['ranking', 'run', runId] as const,
  eligibilityRun: (runId?: string | null) => ['rules', 'run', runId] as const,
  recentRuns: (limit = 10) => ['ranking', 'runs', 'summary', limit] as const,
};

/**
 * Hook to retrieve a specific Top-X ranking run.
 */
export function useRankingRun(runId?: string | null) {
  return useQuery<RankingRunResponse, Error>({
    queryKey: RESULTS_QUERY_KEYS.rankingRun(runId),
    queryFn: () => {
      if (!runId) throw new Error('No ranking run ID provided');
      return apiService.getRankingRun(runId);
    },
    enabled: Boolean(runId),
    staleTime: 1000 * 60, // 1 min
    refetchOnMount: 'always',
    retry: (failureCount, error: any) => {
      if (error?.status === 404) return false;
      return failureCount < 2;
    },
  });
}

/**
 * Hook to retrieve the upstream eligibility evaluation run for a ranking run.
 * Supplies detailed evaluator rule results and member evaluations.
 */
export function useEligibilityRun(eligibilityRunId?: string | null) {
  return useQuery<EligibilityRunResponse, Error>({
    queryKey: RESULTS_QUERY_KEYS.eligibilityRun(eligibilityRunId),
    queryFn: () => {
      if (!eligibilityRunId) throw new Error('No eligibility run ID provided');
      return apiService.getEligibilityRun(eligibilityRunId);
    },
    enabled: Boolean(eligibilityRunId),
    staleTime: 1000 * 60,
  });
}

/**
 * Hook to retrieve lightweight list of recent ranking runs when no run_id is supplied.
 */
export function useRecentRankingRuns(limit = 10) {
  return useQuery<RankingRunSummaryItem[], Error>({
    queryKey: RESULTS_QUERY_KEYS.recentRuns(limit),
    queryFn: () => apiService.getRankingRunSummaries(limit),
    staleTime: 1000 * 30,
    refetchOnMount: 'always',
  });
}

/**
 * Mutation to apply a manual eligibility override to a team in an eligibility run.
 */
export function useApplyOverrideMutation() {
  const queryClient = useQueryClient();

  return useMutation<
    ManualOverride,
    Error,
    { eligibilityRunId: string; teamId: string; payload: ManualOverrideCreate }
  >({
    mutationFn: ({ eligibilityRunId, teamId, payload }) =>
      apiService.applyTeamEligibilityOverride(eligibilityRunId, teamId, payload),
    onSuccess: (_, variables) => {
      // Invalidate eligibility run query to reflect the override
      queryClient.invalidateQueries({
        queryKey: RESULTS_QUERY_KEYS.eligibilityRun(variables.eligibilityRunId),
      });
    },
  });
}

/**
 * Mutation to re-evaluate ranking after eligibility overrides have been committed.
 */
export function useRerunRankingMutation() {
  const queryClient = useQueryClient();

  return useMutation<
    RankingRunResponse,
    Error,
    {
      scoringRunId: string;
      eligibilityRunId: string;
      topX: number;
      includeNeedsReview?: boolean;
      tiebreakCriterionId?: string | null;
    }
  >({
    mutationFn: ({
      scoringRunId,
      eligibilityRunId,
      topX,
      includeNeedsReview = false,
      tiebreakCriterionId,
    }) =>
      apiService.evaluateRanking(
        scoringRunId,
        eligibilityRunId,
        topX,
        includeNeedsReview,
        tiebreakCriterionId
      ),
    onSuccess: (newRun) => {
      // Seed newly created run into cache and invalidate recent lists
      queryClient.setQueryData(RESULTS_QUERY_KEYS.rankingRun(newRun.run_id), newRun);
      queryClient.invalidateQueries({ queryKey: ['ranking', 'runs'] });
    },
  });
}
