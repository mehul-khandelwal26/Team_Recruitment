/**
 * Configuration Formatting Utilities
 * Presentation-layer mappers for converting raw backend database enums,
 * rule evaluator keys, and algorithm identifiers into professional, human-readable labels.
 */

export function formatRuleType(ruleType: string): string {
  const map: Record<string, string> = {
    team_size_range: 'Team Size Range',
    team_size_min: 'Minimum Team Size',
    team_size_max: 'Maximum Team Size',
    required_link: 'Required Profile Link',
    signal_threshold: 'Signal Threshold',
    custom_signal_threshold: 'Custom Signal Threshold',
    academic_year_range: 'Academic Year Range',
    cgpa_minimum: 'Minimum CGPA / CPI',
    normalized_cgpa_minimum: 'Normalized Minimum CGPA',
    github_repos_minimum: 'Minimum GitHub Repositories',
    required_signal_present: 'Required Signal Present',
    signal_contains: 'Signal Value Contains',
    allowed_values: 'Allowed Categorical Values',
    track_limit: 'Track Capacity Limit',
    duplicate_member_email: 'Duplicate Member Check',
    required_fields_present: 'Required Registration Fields',
    // Preserved aliases & legacy display identifiers
    track_whitelist: 'Allowed Track Whitelist',
    academic_year_filter: 'Academic Year Filter',
    disallowed_email_domain: 'Disallowed Email Domain',
    custom_composite: 'Custom Composite',
  };
  if (map[ruleType]) return map[ruleType];
  return ruleType
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

export function formatMissingPolicy(policy: string): { label: string; tone: 'neutral' | 'warning' | 'info' } {
  switch (policy) {
    case 'manual_review':
      return { label: 'Manual Review', tone: 'warning' };
    case 'pass':
      return { label: 'Pass (Permissive)', tone: 'neutral' };
    case 'fail':
      return { label: 'Disqualify (Strict)', tone: 'warning' };
    case 'skip':
      return { label: 'Skip Evaluation', tone: 'neutral' };
    case 'exclude_and_renormalize':
      return { label: 'Renormalize Weights', tone: 'info' };
    case 'zero_score':
    case 'zero_fill':
      return { label: 'Zero Score (0.0 pts)', tone: 'neutral' };
    case 'default_score':
      return { label: 'Default Score', tone: 'neutral' };
    default:
      return {
        label: policy.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
        tone: 'neutral',
      };
  }
}

export function formatScope(scope: string): string {
  switch (scope?.toLowerCase()) {
    case 'team':
      return 'Team-Wide';
    case 'member':
      return 'Member-Level';
    case 'cross_team':
      return 'Cross-Team';
    default:
      return scope || 'Team-Wide';
  }
}

export function formatMemberSelection(selection?: string | null): string | null {
  if (!selection) return null;
  switch (selection.toLowerCase()) {
    case 'any_member':
      return 'Any Member (≥1)';
    case 'all_members':
      return 'All Members';
    case 'team_lead':
    case 'lead_only':
      return 'Team Lead Only';
    default:
      return selection.replace(/_/g, ' ');
  }
}

export function formatCriterionType(type: string): string {
  switch (type?.toLowerCase()) {
    case 'numeric_range':
      return 'Numeric Range';
    case 'categorical':
      return 'Categorical Scale';
    case 'boolean':
      return 'Binary Flag';
    case 'custom':
      return 'Custom Rubric';
    default:
      return type ? type.replace(/_/g, ' ') : 'Standard';
  }
}

export function formatAggregation(agg?: string): string {
  switch (agg?.toLowerCase()) {
    case 'mean':
      return 'Mean Average';
    case 'lead':
    case 'lead_only':
      return 'Team Lead Value';
    case 'top_k':
      return 'Top-K Average';
    case 'all':
      return 'All Members Match';
    case 'any':
      return 'Any Member Matches';
    case 'max':
      return 'Maximum Value';
    case 'min':
      return 'Minimum Value';
    case 'sum':
      return 'Sum Total';
    default:
      return agg ? agg.replace(/_/g, ' ') : 'Mean';
  }
}

export interface FormattedParameter {
  label: string;
  value: string;
}

export function formatRuleParameters(
  _ruleType: string,
  params?: Record<string, any>
): FormattedParameter[] {
  if (!params || Object.keys(params).length === 0) return [];

  const result: FormattedParameter[] = [];

  // Always show Signal or Field first if explicitly specified
  if (params.signal_key) {
    result.push({ label: 'Signal', value: String(params.signal_key) });
  }
  if (params.field_key) {
    result.push({ label: 'Field', value: String(params.field_key) });
  }
  if (params.link_field) {
    result.push({ label: 'Field', value: String(params.link_field) });
  }

  // Min/Max team size or generic min/max values
  if (params.min_size !== undefined) {
    result.push({ label: 'Min', value: `${params.min_size} members` });
  } else if (params.min_value !== undefined) {
    result.push({ label: 'Min', value: String(params.min_value) });
  }

  if (params.max_size !== undefined) {
    result.push({ label: 'Max', value: `${params.max_size} members` });
  } else if (params.max_value !== undefined) {
    result.push({ label: 'Max', value: String(params.max_value) });
  }

  // Threshold rule: combine operator + threshold
  if (params.threshold !== undefined) {
    const op = params.operator || '>=';
    result.push({ label: 'Cutoff', value: `${op} ${params.threshold}` });
  }

  // Allowed tracks / categories / values
  if (Array.isArray(params.allowed_tracks)) {
    result.push({ label: 'Tracks', value: params.allowed_tracks.join(', ') });
  }
  if (Array.isArray(params.allowed_values)) {
    result.push({ label: 'Values', value: params.allowed_values.join(', ') });
  }
  if (Array.isArray(params.blocked_domains)) {
    result.push({ label: 'Blocked', value: params.blocked_domains.join(', ') });
  }

  // Keywords (signal_contains)
  if (params.keywords !== undefined) {
    result.push({
      label: 'Keywords',
      value: Array.isArray(params.keywords) ? params.keywords.join(', ') : String(params.keywords),
    });
  }

  // Required registration fields (required_fields_present)
  if (Array.isArray(params.required_fields)) {
    result.push({ label: 'Required', value: params.required_fields.join(', ') });
  }

  // Track capacity limit
  if (params.max_teams_per_track !== undefined) {
    result.push({ label: 'Max / Track', value: `${params.max_teams_per_track} teams` });
  }

  // Expected value
  if (params.expected_value !== undefined) {
    result.push({ label: 'Expected', value: String(params.expected_value) });
  }

  // If no recognized parameter was extracted, fall back to formatting all remaining keys (excluding duplicates)
  if (result.length === 0) {
    for (const [key, val] of Object.entries(params)) {
      if (['aggregation', 'member_selection'].includes(key)) continue;
      const label = key.replace(/_/g, ' ');
      const formattedVal = Array.isArray(val)
        ? val.join(', ')
        : typeof val === 'object' && val !== null
        ? JSON.stringify(val)
        : String(val);
      result.push({ label, value: formattedVal });
    }
  }

  return result;
}
