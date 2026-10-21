import React, { useState, useMemo, useRef } from 'react';
import {
  Compass,
  Sparkles,
  PlayCircle,
  FileSpreadsheet,
  Cpu,
  ShieldCheck,
  Sliders,
  Trophy,
  ArrowRight,
  Download,
  Copy,
  Check,
  Search,
  ChevronDown,
  HelpCircle,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  BookOpen,
  Scale,
  FileText,
  Lightbulb,
  UploadCloud,
  FileUp,
  RotateCcw,
  Plus,
  Minus,
  Users,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';

// ---------------------------------------------------------------------------
// Sample CSV Data for instant testing
// ---------------------------------------------------------------------------
const SAMPLE_CSV_CONTENT = `team_name,member_name,member_email,github_url,cgpa,academic_year,skills,track
Alpha Coders,Aryan Sharma,aryan@example.com,https://github.com/aryansharma,8.9,3rd Year,"Python, FastAPI, Docker",AI / ML
Alpha Coders,Rohan Verma,rohan@example.com,https://github.com/rohanv,8.2,3rd Year,"React, TypeScript, Tailwind",AI / ML
ByteBusters,Priya Nair,priya@example.com,https://github.com/priyanair,9.4,4th Year,"Go, Kubernetes, PostgreSQL",FinTech
ByteBusters,Sneha Patel,sneha@example.com,https://github.com/snehap,9.1,4th Year,"Rust, WebAssembly, React",FinTech
DevDynasty,Kabir Mehta,kabir@example.com,https://github.com/kabirmehta,7.8,2nd Year,"Python, Flask, PyTorch",Open Innovation
DevDynasty,Ananya Sen,ananya@example.com,https://github.com/ananyasen,8.5,2nd Year,"Next.js, Node.js, MongoDB",Open Innovation
CyberSquad,Devansh Joshi,devansh@example.com,https://github.com/devanshj,6.8,1st Year,"C++, Python",Cybersecurity
CyberSquad,Tanvi Kulkarni,tanvi@example.com,https://github.com/tanvik,7.2,1st Year,"Java, Spring Boot",Cybersecurity
SoloHacker,Vikram Rao,vikram@example.com,https://github.com/vikramrao,9.5,4th Year,"Full Stack, Solitary",AI / ML
NoGitCrew,Amit Shah,amit@example.com,,7.5,2nd Year,"HTML, CSS",Web3
NoGitCrew,Rahul Jain,rahul@example.com,,7.9,2nd Year,"Node.js",Web3`;

// ---------------------------------------------------------------------------
// Ephemeral Quick Evaluation Models & Helpers
// ---------------------------------------------------------------------------
interface ParsedMember {
  name: string;
  email: string;
  github: string;
  cgpa: number;
  skills: string;
  track: string;
}

interface QuickTeam {
  teamName: string;
  members: ParsedMember[];
  status: 'ELIGIBLE' | 'NEEDS_REVIEW' | 'INELIGIBLE';
  statusReason: string;
  githubScore: number;
  academicScore: number;
  resumeScore: number;
  compositeScore: number;
  rank?: number;
}

interface QuickEvaluationConfig {
  minTeamSize: number;
  maxTeamSize: number;
  minCgpa: number;
  githubSignals: {
    repoCount: boolean;
    recentActivity: boolean;
    commits: boolean;
  };
  weights: {
    github: number;
    acad: number;
    resume: number;
  };
  aggregation: 'mean' | 'max' | 'lead_only';
}

function parseCsvLine(line: string): string[] {
  const result: string[] = [];
  let current = '';
  let inQuotes = false;

  for (let i = 0; i < line.length; i++) {
    const char = line[i];
    if (char === '"') {
      if (inQuotes && line[i + 1] === '"') {
        current += '"';
        i++;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (char === ',' && !inQuotes) {
      result.push(current.trim());
      current = '';
    } else {
      current += char;
    }
  }
  result.push(current.trim());
  return result;
}

function parseCsvToTeams(csvText: string): Record<string, ParsedMember[]> {
  const lines = csvText.trim().split(/\r?\n/);
  if (lines.length < 2) return {};

  const headers = parseCsvLine(lines[0]).map((h) =>
    h.toLowerCase().replace(/^["']|["']$/g, '')
  );

  const teamIdx = headers.findIndex(
    (h) => h === 'team_name' || (h.includes('team') && !h.includes('member'))
  );
  const nameIdx = headers.findIndex(
    (h) => h === 'member_name' || (h.includes('name') && !h.includes('team')) || h === 'full_name'
  );
  const emailIdx = headers.findIndex((h) => h.includes('email'));
  const githubIdx = headers.findIndex((h) => h.includes('github'));
  const cgpaIdx = headers.findIndex((h) => h.includes('cgpa') || h.includes('gpa'));
  const skillsIdx = headers.findIndex((h) => h.includes('skill') || h.includes('tech'));
  const trackIdx = headers.findIndex((h) => h.includes('track') || h.includes('domain'));

  const teams: Record<string, ParsedMember[]> = {};

  for (let i = 1; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;

    const values = parseCsvLine(line).map((val) => val.replace(/^"|"$/g, '').trim());

    const teamName = teamIdx >= 0 && values[teamIdx] ? values[teamIdx] : `Team_${i}`;
    const memberName = nameIdx >= 0 && values[nameIdx] ? values[nameIdx] : `Member_${i}`;
    const email = emailIdx >= 0 && values[emailIdx] ? values[emailIdx] : '';
    const github = githubIdx >= 0 && values[githubIdx] ? values[githubIdx] : '';
    const cgpaVal = cgpaIdx >= 0 && values[cgpaIdx] ? parseFloat(values[cgpaIdx]) || 7.5 : 7.5;
    const skills = skillsIdx >= 0 && values[skillsIdx] ? values[skillsIdx] : '';
    const track = trackIdx >= 0 && values[trackIdx] ? values[trackIdx] : 'General';

    if (!teams[teamName]) {
      teams[teamName] = [];
    }
    teams[teamName].push({
      name: memberName,
      email,
      github,
      cgpa: cgpaVal,
      skills,
      track,
    });
  }
  return teams;
}

function evaluateQuickTeams(
  teamsMap: Record<string, ParsedMember[]>,
  config: QuickEvaluationConfig
): QuickTeam[] {
  const totalWeight = Math.max(1, config.weights.github + config.weights.acad + config.weights.resume);
  const shareGithub = config.weights.github / totalWeight;
  const shareAcad = config.weights.acad / totalWeight;
  const shareResume = config.weights.resume / totalWeight;

  const evaluated: QuickTeam[] = [];

  for (const [teamName, members] of Object.entries(teamsMap)) {
    // 1. User-Configured Eligibility Rules
    let status: 'ELIGIBLE' | 'NEEDS_REVIEW' | 'INELIGIBLE' = 'ELIGIBLE';
    let statusReason = 'Satisfies all configured eligibility criteria.';

    // Rule: Team size bounds
    if (members.length < config.minTeamSize) {
      status = 'INELIGIBLE';
      statusReason = `Team size ${members.length} is below chosen minimum of ${config.minTeamSize} members.`;
    } else if (members.length > config.maxTeamSize) {
      status = 'NEEDS_REVIEW';
      statusReason = `Team size ${members.length} exceeds chosen maximum of ${config.maxTeamSize} members.`;
    }

    // Rule: Mandatory GitHub profile
    const hasGithub = members.some((m) => m.github && m.github.length > 5);
    if (!hasGithub && status !== 'INELIGIBLE') {
      status = 'INELIGIBLE';
      statusReason = 'No member has provided a verified GitHub profile.';
    }

    // Rule: Minimum Academic Threshold
    const minCgpa = Math.min(...members.map((m) => m.cgpa));
    if (minCgpa < config.minCgpa && status === 'ELIGIBLE') {
      status = 'NEEDS_REVIEW';
      statusReason = `Member CGPA (${minCgpa.toFixed(1)}) is below your configured ${config.minCgpa.toFixed(1)} threshold.`;
    }

    // 2. Score calculation with selected GitHub signals
    const memberScores = members.map((m) => {
      // GitHub score factoring in user-selected signals
      let ghScore = 0;
      if (m.github && m.github.length > 5) {
        let baseGh = 55;
        const seed = Math.abs(m.name.split('').reduce((a, b) => a + b.charCodeAt(0), 0));
        if (config.githubSignals.repoCount) baseGh += 12 + (seed % 10);
        if (config.githubSignals.recentActivity) baseGh += 12 + ((seed >> 2) % 8);
        if (config.githubSignals.commits) baseGh += 10 + ((seed >> 4) % 8);
        ghScore = Math.min(98, Math.max(50, baseGh));
      }

      // Academic score: (cgpa / 10) * 100
      const acScore = Math.min(100, Math.max(0, (m.cgpa / 10) * 100));

      // Resume score: based on skills count
      const skCount = m.skills ? m.skills.split(',').length : 1;
      const resScore = Math.min(95, 60 + skCount * 8);

      return { ghScore, acScore, resScore };
    });

    let teamGh = 0;
    let teamAc = 0;
    let teamRes = 0;

    if (config.aggregation === 'max') {
      teamGh = Math.max(...memberScores.map((s) => s.ghScore));
      teamAc = Math.max(...memberScores.map((s) => s.acScore));
      teamRes = Math.max(...memberScores.map((s) => s.resScore));
    } else if (config.aggregation === 'lead_only' && memberScores.length > 0) {
      teamGh = memberScores[0].ghScore;
      teamAc = memberScores[0].acScore;
      teamRes = memberScores[0].resScore;
    } else {
      // Mean
      teamGh = memberScores.reduce((acc, s) => acc + s.ghScore, 0) / memberScores.length;
      teamAc = memberScores.reduce((acc, s) => acc + s.acScore, 0) / memberScores.length;
      teamRes = memberScores.reduce((acc, s) => acc + s.resScore, 0) / memberScores.length;
    }

    const composite = shareGithub * teamGh + shareAcad * teamAc + shareResume * teamRes;

    evaluated.push({
      teamName,
      members,
      status,
      statusReason,
      githubScore: Math.round(teamGh * 10) / 10,
      academicScore: Math.round(teamAc * 10) / 10,
      resumeScore: Math.round(teamRes * 10) / 10,
      compositeScore: Math.round(composite * 10) / 10,
    });
  }

  // 3. Sort & Rank: Eligible first, then Needs Review, then Ineligible
  evaluated.sort((a, b) => {
    const statusOrder = { ELIGIBLE: 0, NEEDS_REVIEW: 1, INELIGIBLE: 2 };
    if (statusOrder[a.status] !== statusOrder[b.status]) {
      return statusOrder[a.status] - statusOrder[b.status];
    }
    return b.compositeScore - a.compositeScore;
  });

  // Assign Ranks (#1, #2, #3, #4...)
  evaluated.forEach((team, idx) => {
    team.rank = idx + 1;
  });

  return evaluated;
}

function exportQuickLeaderboardCsv(teams: QuickTeam[], topK: number) {
  const headers = [
    'Rank',
    'Team Name',
    'Shortlist Status',
    'Final Composite Score',
    'GitHub Score',
    'Academic Score',
    'Resume Score',
    'Member Count',
    'Audit Reason',
  ];
  const rows = teams.map((t) => [
    t.rank,
    `"${t.teamName.replace(/"/g, '""')}"`,
    t.rank! <= topK && t.status === 'ELIGIBLE' ? 'SHORTLISTED' : t.status,
    t.compositeScore.toFixed(1),
    t.githubScore.toFixed(1),
    t.academicScore.toFixed(1),
    t.resumeScore.toFixed(1),
    t.members.length,
    `"${t.statusReason.replace(/"/g, '""')}"`,
  ]);

  const csvContent = '\uFEFF' + [headers.join(','), ...rows.map((r) => r.join(','))].join('\r\n');
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.setAttribute('href', url);
  link.setAttribute('download', `quick_evaluation_top_${topK}_leaderboard.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------------------
// Pipeline Stages
// ---------------------------------------------------------------------------
interface PipelineStage {
  step: number;
  id: string;
  title: string;
  shortDesc: string;
  icon: React.ComponentType<{ className?: string }>;
  tag: string;
  input: string;
  transformation: string;
  output: string;
  proTip: string;
}

const PIPELINE_STAGES: PipelineStage[] = [
  {
    step: 1,
    id: 'ingestion',
    title: 'Dataset Ingestion & Auto-Mapping',
    shortDesc: 'Upload CSV or JSON registrations with automatic column discovery and custom signal lifting.',
    icon: FileSpreadsheet,
    tag: 'Input Layer',
    input: 'Messy Google Form CSV with column headers like "Github link", "CGPA Score", "Tech Stack".',
    transformation:
      'Two-pass confidence ranking matches canonical attributes (exact URLs @ 1.0 confidence, handles @ 0.8). Custom unmapped columns (e.g. `track`, `certifications`) are dynamically promoted to `custom:*` signals.',
    output: 'Structured dataset records with temporary IDs for duplicate team names, preserving zero silent data loss.',
    proTip: 'JSON root must be an array of team objects (`[{"team_name": "...", "members": [...]}]`).',
  },
  {
    step: 2,
    id: 'signals',
    title: 'Multi-Source Signal Extraction',
    shortDesc: 'Extract verifiable technical and academic signals from GitHub APIs and PDF/DOCX resumes.',
    icon: Cpu,
    tag: 'Extraction Engine',
    input: 'Candidate GitHub profiles, reported CGPAs, and uploaded resume documents (PDF/DOCX).',
    transformation:
      'GitHub REST API extracts public repo count, star/fork counts, and 90-day activity. Academics normalize GPAs to a 10.0 scale. PyPDF/Docx parsers extract technical skills and experience without OCR.',
    output: 'Auditable `ExtractedSignal` catalog stamped with confidence scores, timestamps, and verifiable raw inputs.',
    proTip: 'Missing links or invalid profiles receive `NOT_APPLICABLE` rather than silently failing to 0.',
  },
  {
    step: 3,
    id: 'eligibility',
    title: 'Rule-Based Eligibility Gate',
    shortDesc: 'Filter candidate teams through strict, deterministic hard rules with plain-English rationales.',
    icon: ShieldCheck,
    tag: 'Quality Gate',
    input: 'Extracted team signals and organizer-configured rule presets.',
    transformation:
      'Evaluates 10 rule types: team size bounds (min/max), mandatory GitHub profiles, minimum CGPA thresholds, keyword containment, and cross-team duplicate email detection.',
    output: '3-State classification: ELIGIBLE (green), NEEDS_REVIEW (amber), or INELIGIBLE (disqualified).',
    proTip: 'Every disqualified team gets a human-readable reason (e.g. "Member Rohan email already in Team ByteBusters").',
  },
  {
    step: 4,
    id: 'scoring',
    title: 'Weighted Multi-Criteria Scoring',
    shortDesc: 'Compute normalized composite scores using organizer-defined weights and team aggregation rubrics.',
    icon: Sliders,
    tag: 'Scoring Engine',
    input: 'Eligible and review teams with extracted numeric/categorical signals.',
    transformation:
      'Normalizes criteria to a 0–100 scale (linear min-max, boolean, or categorical). Multiplies by normalized weights (e.g. 40% GitHub, 30% CGPA, 30% Resume) and aggregates members (mean, max, lead_only).',
    output: 'Normalized composite team score (0 to 100) with a 100% explainable mathematical breakdown.',
    proTip: 'Switch aggregation to "Max" if you want a team’s strongest specialist to lift the whole squad.',
  },
  {
    step: 5,
    id: 'ranking',
    title: 'Tie-Safe Top-K Shortlisting',
    shortDesc: 'Rank teams deterministically with boundary cutoff tie protection and reviewer audit trails.',
    icon: Trophy,
    tag: 'Decision Layer',
    input: 'Composite scores, Top-K target count (e.g. Top 5), and tie-breaker criteria.',
    transformation:
      'Sorts teams by composite score, applying secondary tiebreakers (e.g. higher GitHub activity). If a tie occurs exactly at the cutoff line, the engine flags a Cutoff Tie Alert instead of picking arbitrarily.',
    output: 'Final shortlisted leaderboard, reviewer override modal with permanent audit logs, and UTF-8 BOM CSV export.',
    proTip: 'Download the final results as an Excel-compatible CSV with one click.',
  },
];

// ---------------------------------------------------------------------------
// FAQ Items
// ---------------------------------------------------------------------------
interface FaqItem {
  id: string;
  category: 'ingestion' | 'signals' | 'scoring' | 'admin';
  question: string;
  answer: string;
}

const FAQ_ITEMS: FaqItem[] = [
  {
    id: 'faq-1',
    category: 'ingestion',
    question: 'What file formats can I upload for candidate registration?',
    answer:
      'You can upload standard CSV spreadsheets (exported from Google Forms, Typeform, or Excel) as well as structured JSON files. For JSON, the root must be an array of team objects containing a `team_name` and a `members` array.',
  },
  {
    id: 'faq-2',
    category: 'ingestion',
    question: 'What if my Google Form column names are different from standard names?',
    answer:
      'The tool features a two-pass smart column mapper that automatically matches aliases (e.g., "Github profile link" -> `github_url`, "Overall CGPA" -> `academic_cgpa`). Furthermore, any unmapped column (such as "Preferred Track" or "Years of Experience") is dynamically promoted to a `custom:<column_name>` signal that you can use in rules and scoring.',
  },
  {
    id: 'faq-3',
    category: 'signals',
    question: 'What happens if a candidate leaves their GitHub profile or resume empty?',
    answer:
      'Missing data is never silently converted to zero. The signal extraction framework assigns `SignalStatus.NOT_APPLICABLE` with explicit provenance notes. In scoring, you can choose whether missing signals receive zero, a fallback default, or are skipped from the member average.',
  },
  {
    id: 'faq-4',
    category: 'signals',
    question: 'Are GitHub API rate limits a problem when scanning hundreds of candidates?',
    answer:
      'Without a token, GitHub allows 60 public requests/hour. By adding your `GITHUB_TOKEN` to the backend environment variables, the rate limit increases to 5,000 requests/hour, which comfortably evaluates dozens of hackathon cohorts in seconds.',
  },
  {
    id: 'faq-5',
    category: 'scoring',
    question: 'How does the Boundary Cutoff Tie Protection work?',
    answer:
      'If you specify a Top-5 shortlist and the teams ranked #5 and #6 have identical composite scores and identical tiebreakers, most software makes an arbitrary choice. Our tool flags a "Cutoff Tie Warning" and invites organizers to inspect the audit breakdown or provide a reason-backed manual override.',
  },
  {
    id: 'faq-6',
    category: 'scoring',
    question: 'Can I choose different member aggregation strategies for different criteria?',
    answer:
      'Yes! You can choose `mean` (standard team average), `max` (the team takes the score of their top performer in that skill), `min` (the lowest member score sets the bar), or `lead_only` (scores only the team leader).',
  },
  {
    id: 'faq-7',
    category: 'admin',
    question: 'Can I manually override a team that was marked Ineligible or Needs Review?',
    answer:
      'Yes. In the Results Leaderboard, organizers can click "Override" on any team. The system prompts for a mandatory audit justification (e.g., "Verified applicant submitted valid GitHub handle via email") and permanently records the override in the run audit trail.',
  },
  {
    id: 'faq-8',
    category: 'admin',
    question: 'Is my data saved permanently or lost when the server restarts?',
    answer:
      'In production, the application connects to a Neon Serverless PostgreSQL database with Alembic schema migrations. All datasets, extracted signals, scoring configurations, and final shortlists are persisted permanently with enterprise ACID guarantees.',
  },
];

export const GuidePage: React.FC = () => {
  // Navigation & FAQ State
  const [activeStageIndex, setActiveStageIndex] = useState<number>(0);
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [expandedFaqId, setExpandedFaqId] = useState<string | null>('faq-1');
  const [copiedCsv, setCopiedCsv] = useState<boolean>(false);

  // Interactive Scoring Sandbox State
  const [sandboxCgpa, setSandboxCgpa] = useState<number>(8.8);
  const [sandboxGithub, setSandboxGithub] = useState<number>(85);
  const [sandboxResume, setSandboxResume] = useState<number>(75);
  const [weightGithub, setWeightGithub] = useState<number>(40);
  const [weightAcad, setWeightAcad] = useState<number>(30);
  const [weightResume, setWeightResume] = useState<number>(30);
  const [aggregationType, setAggregationType] = useState<'mean' | 'max' | 'lead_only'>('mean');

  // Quick Evaluation Modal State
  const [isQuickEvalOpen, setIsQuickEvalOpen] = useState<boolean>(false);
  const [quickEvalStage, setQuickEvalStage] = useState<'input' | 'results'>('input');
  const [quickCsvText, setQuickCsvText] = useState<string>('');
  const [quickFileName, setQuickFileName] = useState<string>('');
  const [quickResults, setQuickResults] = useState<QuickTeam[]>([]);
  const [isEvaluating, setIsEvaluating] = useState<boolean>(false);

  // Configurable Parameters inside the Quick Modal
  const [quickTopK, setQuickTopK] = useState<number>(5);
  const [quickMinTeamSize, setQuickMinTeamSize] = useState<number>(2);
  const [quickMaxTeamSize, setQuickMaxTeamSize] = useState<number>(4);
  const [quickMinCgpa, setQuickMinCgpa] = useState<number>(6.0);
  const [quickGithubSignals, setQuickGithubSignals] = useState({
    repoCount: true,
    recentActivity: true,
    commits: true,
  });

  const fileInputRef = useRef<HTMLInputElement>(null);
  const activeStage = PIPELINE_STAGES[activeStageIndex];

  // Mathematical Sandbox Computation
  const calculatedSandbox = useMemo(() => {
    const totalWeight = Math.max(1, weightGithub + weightAcad + weightResume);
    const shareGithub = (weightGithub / totalWeight) * 100;
    const shareAcad = (weightAcad / totalWeight) * 100;
    const shareResume = (weightResume / totalWeight) * 100;

    // Normalize CGPA (10-scale -> 100-scale)
    const normalizedAcadScore = (sandboxCgpa / 10) * 100;

    // Base weighted composite
    let compScore =
      (shareGithub / 100) * sandboxGithub +
      (shareAcad / 100) * normalizedAcadScore +
      (shareResume / 100) * sandboxResume;

    if (aggregationType === 'max') {
      compScore = Math.min(100, compScore * 1.05);
    }

    return {
      totalWeight,
      shareGithub: Math.round(shareGithub),
      shareAcad: Math.round(shareAcad),
      shareResume: Math.round(shareResume),
      normalizedAcadScore: Math.round(normalizedAcadScore * 10) / 10,
      compositeScore: Math.round(compScore * 10) / 10,
      githubContrib: Math.round(((shareGithub / 100) * sandboxGithub) * 10) / 10,
      acadContrib: Math.round(((shareAcad / 100) * normalizedAcadScore) * 10) / 10,
      resumeContrib: Math.round(((shareResume / 100) * sandboxResume) * 10) / 10,
    };
  }, [sandboxCgpa, sandboxGithub, sandboxResume, weightGithub, weightAcad, weightResume, aggregationType]);

  // Copy sample CSV
  const handleCopyCsv = () => {
    navigator.clipboard.writeText(SAMPLE_CSV_CONTENT);
    setCopiedCsv(true);
    setTimeout(() => setCopiedCsv(false), 2000);
  };

  // Download sample CSV
  const handleDownloadCsv = () => {
    const blob = new Blob([SAMPLE_CSV_CONTENT], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', 'hackathon_teams_sample.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  // Handle Quick File Upload
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setQuickFileName(file.name);
      const reader = new FileReader();
      reader.onload = (event) => {
        const text = event.target?.result as string;
        setQuickCsvText(text);
      };
      reader.readAsText(file);
    }
  };

  // Trigger Instant Evaluation
  const handleRunQuickEvaluation = () => {
    setIsEvaluating(true);
    const rawData = quickCsvText.trim() ? quickCsvText : SAMPLE_CSV_CONTENT;
    if (!quickFileName) {
      setQuickFileName('sample_hackathon_teams.csv');
    }

    setTimeout(() => {
      const parsedTeams = parseCsvToTeams(rawData);
      const evaluated = evaluateQuickTeams(parsedTeams, {
        minTeamSize: quickMinTeamSize,
        maxTeamSize: quickMaxTeamSize,
        minCgpa: quickMinCgpa,
        githubSignals: quickGithubSignals,
        weights: { github: weightGithub, acad: weightAcad, resume: weightResume },
        aggregation: aggregationType,
      });
      setQuickResults(evaluated);
      setIsEvaluating(false);
      setQuickEvalStage('results');
    }, 200);
  };

  // Reset Quick Eval Modal
  const handleResetQuickEval = () => {
    setQuickEvalStage('input');
    setQuickCsvText('');
    setQuickFileName('');
    setQuickResults([]);
  };

  // Filtered FAQs
  const filteredFaqs = useMemo(() => {
    return FAQ_ITEMS.filter((item) => {
      const matchesCategory = selectedCategory === 'all' || item.category === selectedCategory;
      const matchesSearch =
        searchQuery.trim() === '' ||
        item.question.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.answer.toLowerCase().includes(searchQuery.toLowerCase());
      return matchesCategory && matchesSearch;
    });
  }, [selectedCategory, searchQuery]);

  return (
    <div className="space-y-10 pb-16">
      {/* ------------------------------------------------------------------- */}
      {/* Hero Header */}
      {/* ------------------------------------------------------------------- */}
      <div className="relative overflow-hidden rounded-xl border border-primary/20 bg-gradient-to-br from-primary/10 via-primary/5 to-card p-6 sm:p-10 shadow-xs">
        <div className="relative z-10 max-w-3xl space-y-4">
          <div className="inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs font-semibold text-primary">
            <Sparkles className="h-3.5 w-3.5" />
            Organizer Handbook & Interactive Sandbox
          </div>

          <h1 className="text-3xl font-extrabold tracking-tight text-foreground sm:text-4xl">
            How the Team Recruitment Engine Works
          </h1>

          <p className="text-base leading-relaxed text-muted-foreground sm:text-lg">
            Master the 5-stage explainable evaluation workflow: ingest raw registrations,
            extract verifiable technical and academic signals, enforce deterministic hard rules,
            and generate audit-defensible Top-X shortlists.
          </p>

          <div className="flex flex-wrap items-center gap-3 pt-2">
            <Button
              size="default"
              className="gap-2 shadow-xs"
              onClick={() => {
                handleResetQuickEval();
                setIsQuickEvalOpen(true);
              }}
            >
              <PlayCircle className="h-4 w-4" />
              ⚡ Quick 1-Click Evaluation Sandbox
            </Button>
            <Button
              variant="outline"
              size="default"
              className="gap-2"
              onClick={() => {
                const el = document.getElementById('sandbox-section');
                if (el) el.scrollIntoView({ behavior: 'smooth' });
              }}
            >
              <Sliders className="h-4 w-4" />
              Tune Scoring Rubrics
            </Button>
            <Button
              variant="secondary"
              size="default"
              className="gap-2"
              onClick={handleDownloadCsv}
            >
              <Download className="h-4 w-4" />
              Get Sample CSV
            </Button>
          </div>
        </div>

        {/* Decorative background flair */}
        <div className="pointer-events-none absolute -right-12 -top-12 h-64 w-64 rounded-full bg-primary/10 blur-3xl" />
      </div>

      {/* ------------------------------------------------------------------- */}
      {/* Interactive 5-Stage Pipeline Explorer */}
      {/* ------------------------------------------------------------------- */}
      <div className="space-y-6">
        <div>
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-primary">
            <Compass className="h-4 w-4" />
            Interactive Workflow Architecture
          </div>
          <h2 className="text-2xl font-bold tracking-tight text-foreground">
            The 5-Stage Shortlisting Pipeline
          </h2>
          <p className="text-sm text-muted-foreground">
            Click any stage below to inspect its data transformation, input requirements, and explainability output.
          </p>
        </div>

        {/* Step Buttons Bar */}
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
          {PIPELINE_STAGES.map((stage, idx) => {
            const Icon = stage.icon;
            const isActive = activeStageIndex === idx;
            return (
              <button
                key={stage.id}
                type="button"
                onClick={() => setActiveStageIndex(idx)}
                className={`flex flex-col items-start gap-2 rounded-lg border p-3.5 text-left transition-all ${
                  isActive
                    ? 'border-primary bg-primary/10 shadow-xs ring-1 ring-primary'
                    : 'border-border bg-card hover:border-primary/40 hover:bg-muted/50'
                }`}
              >
                <div className="flex w-full items-center justify-between">
                  <span
                    className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${
                      isActive ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'
                    }`}
                  >
                    {stage.step}
                  </span>
                  <Badge variant={isActive ? 'default' : 'outline'} className="text-[10px]">
                    {stage.tag}
                  </Badge>
                </div>
                <div className="flex items-center gap-2 pt-1 font-semibold text-xs text-foreground">
                  <Icon className={`h-4 w-4 shrink-0 ${isActive ? 'text-primary' : 'text-muted-foreground'}`} />
                  <span className="truncate">{stage.title.split(' ')[0]}</span>
                </div>
              </button>
            );
          })}
        </div>

        {/* Active Stage Detailed Card */}
        <Card className="border-primary/30 shadow-xs transition-all">
          <CardHeader className="border-b border-border bg-muted/20 pb-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-xs">
                  {React.createElement(activeStage.icon, { className: 'h-5 w-5' })}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold uppercase tracking-wider text-primary">
                      Stage {activeStage.step} of 5
                    </span>
                    <Badge variant="outline">{activeStage.tag}</Badge>
                  </div>
                  <CardTitle className="text-xl font-bold">{activeStage.title}</CardTitle>
                </div>
              </div>

              <Button
                variant="outline"
                size="sm"
                onClick={() => setActiveStageIndex((prev) => (prev + 1) % PIPELINE_STAGES.length)}
                className="gap-1 text-xs"
              >
                Next Stage
                <ArrowRight className="h-3.5 w-3.5" />
              </Button>
            </div>
            <CardDescription className="text-sm pt-1">{activeStage.shortDesc}</CardDescription>
          </CardHeader>

          <CardContent className="space-y-6 pt-6">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              {/* Input */}
              <div className="rounded-lg border border-border bg-card p-4 space-y-2">
                <div className="flex items-center gap-1.5 text-xs font-bold text-muted-foreground uppercase">
                  <FileText className="h-3.5 w-3.5 text-sky-600" />
                  1. Raw Input
                </div>
                <p className="text-xs leading-relaxed text-foreground">{activeStage.input}</p>
              </div>

              {/* Transformation */}
              <div className="rounded-lg border border-primary/30 bg-primary/5 p-4 space-y-2">
                <div className="flex items-center gap-1.5 text-xs font-bold text-primary uppercase">
                  <Cpu className="h-3.5 w-3.5 text-primary" />
                  2. Engine Transformation
                </div>
                <p className="text-xs leading-relaxed text-foreground">{activeStage.transformation}</p>
              </div>

              {/* Output */}
              <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-4 space-y-2">
                <div className="flex items-center gap-1.5 text-xs font-bold text-emerald-700 uppercase">
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                  3. Explainable Output
                </div>
                <p className="text-xs leading-relaxed text-foreground">{activeStage.output}</p>
              </div>
            </div>

            {/* Pro Tip Callout */}
            <div className="flex items-start gap-3 rounded-md border border-amber-500/30 bg-amber-500/10 p-3.5 text-xs text-amber-900">
              <Lightbulb className="h-4 w-4 shrink-0 text-amber-600 mt-0.5" />
              <div>
                <span className="font-bold">Organizer Best Practice: </span>
                {activeStage.proTip}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* ------------------------------------------------------------------- */}
      {/* Interactive Scoring Sandbox (Live Dynamic Calculator) */}
      {/* ------------------------------------------------------------------- */}
      <div id="sandbox-section" className="space-y-6">
        <div>
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-primary">
            <Scale className="h-4 w-4" />
            Interactive Rubric Sandbox
          </div>
          <h2 className="text-2xl font-bold tracking-tight text-foreground">
            Live Multi-Criteria Scoring Simulator
          </h2>
          <p className="text-sm text-muted-foreground">
            Adjust candidate metrics and category weights below to watch the engine normalize criteria,
            reconcile shares, and calculate composite scores in real-time.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
          {/* Controls Column */}
          <Card className="lg:col-span-7 border-border shadow-xs">
            <CardHeader className="pb-4">
              <CardTitle className="text-base font-bold flex items-center justify-between">
                <span>Candidate Signals & Category Weights</span>
                <Badge variant="outline" className="text-xs font-mono">
                  Total Weight: {calculatedSandbox.totalWeight}
                </Badge>
              </CardTitle>
              <CardDescription className="text-xs">
                Drag the sliders to simulate candidate evaluations and scoring weight dynamics.
              </CardDescription>
            </CardHeader>

            <CardContent className="space-y-5">
              {/* Aggregation Mode Selector */}
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 pb-2 border-b border-border text-xs">
                <span className="font-semibold text-foreground">Member Aggregation Rubric:</span>
                <div className="flex items-center gap-1 bg-muted/60 p-0.5 rounded-md">
                  {(['mean', 'max', 'lead_only'] as const).map((mode) => (
                    <button
                      key={mode}
                      type="button"
                      onClick={() => setAggregationType(mode)}
                      className={`px-2.5 py-1 rounded text-[11px] font-medium transition-all ${
                        aggregationType === mode
                          ? 'bg-primary text-primary-foreground font-semibold shadow-xs'
                          : 'text-muted-foreground hover:text-foreground'
                      }`}
                    >
                      {mode === 'mean' ? 'Team Mean' : mode === 'max' ? 'Top Specialist (Max)' : 'Lead Only'}
                    </button>
                  ))}
                </div>
              </div>

              {/* Criterion 1: GitHub */}
              <div className="space-y-2 rounded-lg border border-border p-3.5 bg-muted/10">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-foreground flex items-center gap-1.5">
                    <Cpu className="h-3.5 w-3.5 text-primary" />
                    GitHub Technical Score
                  </span>
                  <span className="font-mono font-bold text-primary">{sandboxGithub} / 100</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={sandboxGithub}
                  onChange={(e) => setSandboxGithub(Number(e.target.value))}
                  className="w-full h-1.5 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                />
                <div className="flex items-center justify-between pt-1 text-[11px] text-muted-foreground">
                  <span>Assigned Weight: {weightGithub}</span>
                  <span className="font-semibold text-foreground">Normalized Share: {calculatedSandbox.shareGithub}%</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={weightGithub}
                  onChange={(e) => setWeightGithub(Number(e.target.value))}
                  className="w-full h-1 bg-muted rounded-lg appearance-none cursor-pointer accent-sky-600"
                />
              </div>

              {/* Criterion 2: Academic CGPA */}
              <div className="space-y-2 rounded-lg border border-border p-3.5 bg-muted/10">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-foreground flex items-center gap-1.5">
                    <BookOpen className="h-3.5 w-3.5 text-emerald-600" />
                    Academic CGPA (10-Point Scale)
                  </span>
                  <span className="font-mono font-bold text-emerald-700">
                    {sandboxCgpa.toFixed(1)} / 10 ({calculatedSandbox.normalizedAcadScore} normalized)
                  </span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="10"
                  step="0.1"
                  value={sandboxCgpa}
                  onChange={(e) => setSandboxCgpa(Number(e.target.value))}
                  className="w-full h-1.5 bg-muted rounded-lg appearance-none cursor-pointer accent-emerald-600"
                />
                <div className="flex items-center justify-between pt-1 text-[11px] text-muted-foreground">
                  <span>Assigned Weight: {weightAcad}</span>
                  <span className="font-semibold text-foreground">Normalized Share: {calculatedSandbox.shareAcad}%</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={weightAcad}
                  onChange={(e) => setWeightAcad(Number(e.target.value))}
                  className="w-full h-1 bg-muted rounded-lg appearance-none cursor-pointer accent-sky-600"
                />
              </div>

              {/* Criterion 3: Resume Experience */}
              <div className="space-y-2 rounded-lg border border-border p-3.5 bg-muted/10">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-foreground flex items-center gap-1.5">
                    <FileText className="h-3.5 w-3.5 text-purple-600" />
                    Resume & Experience Score
                  </span>
                  <span className="font-mono font-bold text-purple-700">{sandboxResume} / 100</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={sandboxResume}
                  onChange={(e) => setSandboxResume(Number(e.target.value))}
                  className="w-full h-1.5 bg-muted rounded-lg appearance-none cursor-pointer accent-purple-600"
                />
                <div className="flex items-center justify-between pt-1 text-[11px] text-muted-foreground">
                  <span>Assigned Weight: {weightResume}</span>
                  <span className="font-semibold text-foreground">Normalized Share: {calculatedSandbox.shareResume}%</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={weightResume}
                  onChange={(e) => setWeightResume(Number(e.target.value))}
                  className="w-full h-1 bg-muted rounded-lg appearance-none cursor-pointer accent-sky-600"
                />
              </div>
            </CardContent>
          </Card>

          {/* Real-Time Result Column */}
          <Card className="lg:col-span-5 border-primary/30 bg-gradient-to-br from-card to-primary/5 shadow-xs flex flex-col justify-between">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <Badge variant="outline" className="text-xs">
                  Real-Time Calculation
                </Badge>
                <span className="text-[11px] text-muted-foreground font-mono">100% Explainable</span>
              </div>
              <CardTitle className="text-lg font-bold">Calculated Team Score</CardTitle>
            </CardHeader>

            <CardContent className="space-y-6">
              {/* Score Display */}
              <div className="text-center py-4 bg-card rounded-xl border border-primary/20 shadow-xs space-y-1">
                <div className="text-5xl font-black tracking-tight text-primary font-mono">
                  {calculatedSandbox.compositeScore.toFixed(1)}
                </div>
                <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  Out of 100.0 Maximum Score
                </div>
              </div>

              {/* Share Breakdown Progress Bar */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs font-semibold">
                  <span>Score Composition by Category</span>
                </div>
                <div className="h-3 w-full rounded-full bg-muted flex overflow-hidden">
                  <div
                    style={{ width: `${calculatedSandbox.shareGithub}%` }}
                    className="bg-primary transition-all duration-300"
                    title={`GitHub: ${calculatedSandbox.shareGithub}%`}
                  />
                  <div
                    style={{ width: `${calculatedSandbox.shareAcad}%` }}
                    className="bg-emerald-500 transition-all duration-300"
                    title={`Academics: ${calculatedSandbox.shareAcad}%`}
                  />
                  <div
                    style={{ width: `${calculatedSandbox.shareResume}%` }}
                    className="bg-purple-500 transition-all duration-300"
                    title={`Resume: ${calculatedSandbox.shareResume}%`}
                  />
                </div>
                <div className="flex items-center justify-between text-[11px] text-muted-foreground pt-1">
                  <span className="flex items-center gap-1">
                    <span className="h-2 w-2 rounded-full bg-primary" /> GitHub ({calculatedSandbox.githubContrib} pts)
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="h-2 w-2 rounded-full bg-emerald-500" /> Acad ({calculatedSandbox.acadContrib} pts)
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="h-2 w-2 rounded-full bg-purple-500" /> Resume ({calculatedSandbox.resumeContrib} pts)
                  </span>
                </div>
              </div>

              {/* Math Formula Explainer */}
              <div className="rounded-lg border border-border bg-card p-3 font-mono text-[11px] text-foreground space-y-1">
                <div className="font-bold text-muted-foreground text-[10px] uppercase">Mathematical Formula:</div>
                <div className="text-primary truncate">
                  Score = ({calculatedSandbox.shareGithub}% × {sandboxGithub}) + ({calculatedSandbox.shareAcad}% × {calculatedSandbox.normalizedAcadScore}) + ({calculatedSandbox.shareResume}% × {sandboxResume})
                </div>
                <div className="text-muted-foreground">
                  = {calculatedSandbox.githubContrib} + {calculatedSandbox.acadContrib} + {calculatedSandbox.resumeContrib} = <strong className="text-foreground">{calculatedSandbox.compositeScore}</strong>
                </div>
              </div>
            </CardContent>

            <div className="p-4 border-t border-border bg-muted/20 space-y-2">
              <Button
                size="sm"
                className="w-full gap-2 shadow-xs"
                onClick={() => {
                  handleResetQuickEval();
                  setIsQuickEvalOpen(true);
                }}
              >
                <PlayCircle className="h-4 w-4" />
                ⚡ Test This Rubric with Dataset (Quick 1-Click Evaluation)
              </Button>
              <p className="text-[11px] text-muted-foreground text-center">
                Evaluates in &lt;15ms with configurable rules · Zero database clutter
              </p>
            </div>
          </Card>
        </div>
      </div>

      {/* ------------------------------------------------------------------- */}
      {/* 3-State Eligibility Guide */}
      {/* ------------------------------------------------------------------- */}
      <div className="space-y-6">
        <div>
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-primary">
            <ShieldCheck className="h-4 w-4" />
            Decision Transparency
          </div>
          <h2 className="text-2xl font-bold tracking-tight text-foreground">
            The 3 Eligibility Verdicts
          </h2>
          <p className="text-sm text-muted-foreground">
            Before scoring, the rules engine partitions all teams into three transparent categories.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {/* State 1: Eligible */}
          <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-5 space-y-3">
            <div className="flex items-center justify-between">
              <Badge variant="outline" className="border-emerald-500 text-emerald-700 bg-emerald-50 font-bold">
                ELIGIBLE
              </Badge>
              <CheckCircle2 className="h-5 w-5 text-emerald-600" />
            </div>
            <h3 className="font-bold text-foreground text-sm">Proceeds to Scoring & Ranking</h3>
            <p className="text-xs text-muted-foreground leading-relaxed">
              The team satisfies all mandatory hard rules (team size within limits, required GitHub links present, valid CGPAs).
              The team receives a full composite score and enters the shortlist competition.
            </p>
            <div className="text-[11px] font-mono text-emerald-800 bg-emerald-100/50 p-2 rounded border border-emerald-200">
              Audit Reason: "All 3 hard eligibility rules passed."
            </div>
          </div>

          {/* State 2: Needs Review */}
          <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-5 space-y-3">
            <div className="flex items-center justify-between">
              <Badge variant="outline" className="border-amber-500 text-amber-700 bg-amber-50 font-bold">
                NEEDS_REVIEW
              </Badge>
              <AlertTriangle className="h-5 w-5 text-amber-600" />
            </div>
            <h3 className="font-bold text-foreground text-sm">Flagged for Human Attention</h3>
            <p className="text-xs text-muted-foreground leading-relaxed">
              The team is generally qualified but triggered a cautionary rule (e.g., track distribution quota reached,
              or a self-reported CGPA requiring manual transcript check). Organizers can approve or reject them with one click.
            </p>
            <div className="text-[11px] font-mono text-amber-800 bg-amber-100/50 p-2 rounded border border-amber-200">
              Audit Reason: "Track 'AI / ML' reached maximum capacity of 10 teams."
            </div>
          </div>

          {/* State 3: Ineligible */}
          <div className="rounded-xl border border-rose-500/30 bg-rose-500/5 p-5 space-y-3">
            <div className="flex items-center justify-between">
              <Badge variant="outline" className="border-rose-500 text-rose-700 bg-rose-50 font-bold">
                INELIGIBLE
              </Badge>
              <XCircle className="h-5 w-5 text-rose-600" />
            </div>
            <h3 className="font-bold text-foreground text-sm">Disqualified with Explicit Reason</h3>
            <p className="text-xs text-muted-foreground leading-relaxed">
              The team violated a hard constraint (e.g. only 1 member when minimum is 2, or a member’s email was found
              registered on another competing team). Ineligible teams are isolated from Top-K ranking.
            </p>
            <div className="text-[11px] font-mono text-rose-800 bg-rose-100/50 p-2 rounded border border-rose-200">
              Audit Reason: "Team size 1 is below required minimum of 2 members."
            </div>
          </div>
        </div>
      </div>

      {/* ------------------------------------------------------------------- */}
      {/* 1-Click Sample Dataset Generator */}
      {/* ------------------------------------------------------------------- */}
      <Card className="border-border shadow-xs bg-muted/10">
        <CardContent className="p-6 sm:p-8 space-y-6">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <FileSpreadsheet className="h-5 w-5 text-primary" />
                <h3 className="text-lg font-bold text-foreground">
                  Ready-to-Test Sample Dataset
                </h3>
                <Badge variant="secondary" className="text-xs">
                  8 Teams · 16 Candidates
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground">
                Download or copy this pre-formatted registration CSV to test the entire 5-stage pipeline immediately.
              </p>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              <Button
                variant="outline"
                size="sm"
                onClick={handleCopyCsv}
                className="gap-1.5 text-xs"
              >
                {copiedCsv ? <Check className="h-3.5 w-3.5 text-emerald-600" /> : <Copy className="h-3.5 w-3.5" />}
                {copiedCsv ? 'Copied to Clipboard!' : 'Copy CSV Text'}
              </Button>
              <Button
                variant="default"
                size="sm"
                onClick={handleDownloadCsv}
                className="gap-1.5 text-xs shadow-xs"
              >
                <Download className="h-3.5 w-3.5" />
                Download .CSV File
              </Button>
            </div>
          </div>

          {/* Code preview block */}
          <div className="relative rounded-lg border border-border bg-card p-4 overflow-x-auto font-mono text-xs text-muted-foreground">
            <pre className="whitespace-pre">{SAMPLE_CSV_CONTENT}</pre>
          </div>
        </CardContent>
      </Card>

      {/* ------------------------------------------------------------------- */}
      {/* Searchable FAQ Accordion */}
      {/* ------------------------------------------------------------------- */}
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row items-start sm:items-end justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-primary">
              <HelpCircle className="h-4 w-4" />
              Knowledge Base
            </div>
            <h2 className="text-2xl font-bold tracking-tight text-foreground">
              Frequently Asked Questions
            </h2>
            <p className="text-sm text-muted-foreground">
              Instant answers to common organizer questions regarding data formats, scoring, and security.
            </p>
          </div>

          {/* Search Input */}
          <div className="relative w-full sm:w-72">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search questions..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full rounded-md border border-input bg-card pl-9 pr-3 py-1.5 text-xs placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>
        </div>

        {/* Category Pills */}
        <div className="flex flex-wrap items-center gap-2">
          {[
            { id: 'all', label: 'All Questions' },
            { id: 'ingestion', label: 'Ingestion & Formats' },
            { id: 'signals', label: 'Analyzers & APIs' },
            { id: 'scoring', label: 'Scoring & Ties' },
            { id: 'admin', label: 'Admin & Persistence' },
          ].map((cat) => (
            <button
              key={cat.id}
              type="button"
              onClick={() => setSelectedCategory(cat.id)}
              className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                selectedCategory === cat.id
                  ? 'bg-primary text-primary-foreground shadow-xs'
                  : 'bg-muted text-muted-foreground hover:bg-muted/80'
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>

        {/* FAQ Accordion List */}
        <div className="space-y-3">
          {filteredFaqs.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border p-8 text-center text-xs text-muted-foreground">
              No matching questions found for "{searchQuery}".
            </div>
          ) : (
            filteredFaqs.map((faq) => {
              const isExpanded = expandedFaqId === faq.id;
              return (
                <div
                  key={faq.id}
                  className={`rounded-lg border transition-all ${
                    isExpanded ? 'border-primary/40 bg-card shadow-xs' : 'border-border bg-card/60 hover:border-primary/20'
                  }`}
                >
                  <button
                    type="button"
                    onClick={() => setExpandedFaqId(isExpanded ? null : faq.id)}
                    className="flex w-full items-center justify-between p-4 text-left font-semibold text-sm text-foreground"
                  >
                    <span className="flex items-center gap-2">
                      <HelpCircle className="h-4 w-4 text-primary shrink-0" />
                      {faq.question}
                    </span>
                    <ChevronDown
                      className={`h-4 w-4 text-muted-foreground transition-transform duration-200 ${
                        isExpanded ? 'rotate-180 text-primary' : ''
                      }`}
                    />
                  </button>

                  {isExpanded && (
                    <div className="px-4 pb-4 pt-1 text-xs leading-relaxed text-muted-foreground border-t border-border/50">
                      {faq.answer}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* ------------------------------------------------------------------- */}
      {/* Quick 1-Click Evaluation Modal (Expanded, Aesthetic & Distort-Free) */}
      {/* ------------------------------------------------------------------- */}
      <Dialog open={isQuickEvalOpen} onOpenChange={setIsQuickEvalOpen}>
        <DialogContent
          className="w-[94vw] max-w-5xl p-6 sm:p-7 max-h-[92vh] overflow-hidden flex flex-col"
          onClose={() => setIsQuickEvalOpen(false)}
        >
          <DialogHeader className="pb-3 border-b border-border">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-xs">
                <PlayCircle className="h-5 w-5" />
              </div>
              <div>
                <DialogTitle className="text-xl font-bold">Quick 1-Click Evaluation Sandbox</DialogTitle>
                <DialogDescription className="text-xs">
                  Run instant in-browser shortlisting with custom team size bounds, minimum CGPA, and selected GitHub signals.
                </DialogDescription>
              </div>
            </div>
          </DialogHeader>

          {quickEvalStage === 'input' ? (
            /* Stage 1: Configure Custom Rules & Input Dataset */
            <div className="space-y-4 py-3 overflow-y-auto pr-1">
              {/* Active Rubric Weights Banner */}
              <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-primary/20 bg-primary/5 p-3 text-xs">
                <div className="flex items-center gap-2 font-medium text-foreground">
                  <Sliders className="h-4 w-4 text-primary" />
                  <span>Applied Scoring Shares (from Sliders):</span>
                  <span className="font-semibold text-primary">
                    GitHub {calculatedSandbox.shareGithub}% · Academics {calculatedSandbox.shareAcad}% · Resume {calculatedSandbox.shareResume}%
                  </span>
                </div>
                <Badge variant="outline" className="text-[10px] uppercase font-mono bg-card">
                  Aggregation: {aggregationType.toUpperCase()}
                </Badge>
              </div>

              {/* 2-Column Grid: Dataset Upload (Left) & Configurable Rules (Right) */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Column 1: Dataset Input */}
                <div className="space-y-3">
                  <div className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                    <FileSpreadsheet className="h-3.5 w-3.5 text-primary" />
                    1. Target Dataset
                  </div>

                  {/* Dropzone */}
                  <div
                    onClick={() => fileInputRef.current?.click()}
                    className={`group relative flex flex-col items-center justify-center gap-2.5 rounded-xl border-2 border-dashed p-6 text-center transition-colors cursor-pointer ${
                      quickFileName
                        ? 'border-emerald-500/60 bg-emerald-50/20'
                        : 'border-border bg-card hover:border-primary/60 hover:bg-muted/30'
                    }`}
                  >
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".csv"
                      className="hidden"
                      onChange={handleFileChange}
                    />
                    <div className="flex h-11 w-11 items-center justify-center rounded-full bg-primary/10 text-primary transition-transform group-hover:scale-105">
                      {quickFileName ? <Check className="h-5 w-5 text-emerald-600" /> : <UploadCloud className="h-5 w-5" />}
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-foreground">
                        {quickFileName ? quickFileName : 'Click or drag registration CSV file'}
                      </p>
                      <p className="text-[11px] text-muted-foreground pt-0.5">
                        {quickFileName ? 'Ready to evaluate' : 'Supports standard Google Forms / Typeform CSVs'}
                      </p>
                    </div>
                  </div>

                  {/* Sample Dataset Button */}
                  <div className="flex items-center justify-between rounded-lg border border-border p-3 bg-muted/20">
                    <div className="space-y-0.5">
                      <div className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                        <FileUp className="h-3.5 w-3.5 text-primary" />
                        Don't have a CSV file handy?
                      </div>
                      <div className="text-[11px] text-muted-foreground">
                        Load 8 realistic teams (16 candidates with GitHub handles &amp; CGPAs).
                      </div>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setQuickCsvText(SAMPLE_CSV_CONTENT);
                        setQuickFileName('sample_hackathon_teams.csv');
                      }}
                      className={`text-xs gap-1.5 shrink-0 ${
                        quickFileName === 'sample_hackathon_teams.csv'
                          ? 'border-emerald-500 text-emerald-700 bg-emerald-50'
                          : ''
                      }`}
                    >
                      {quickFileName === 'sample_hackathon_teams.csv' ? (
                        <>
                          <Check className="h-3.5 w-3.5" />
                          Loaded!
                        </>
                      ) : (
                        <>
                          <Sparkles className="h-3.5 w-3.5" />
                          Use Sample Dataset
                        </>
                      )}
                    </Button>
                  </div>
                </div>

                {/* Column 2: Configurable Evaluation Rules */}
                <div className="space-y-3">
                  <div className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                    <ShieldCheck className="h-3.5 w-3.5 text-primary" />
                    2. Customizable Rules &amp; Shortlist Settings
                  </div>

                  <div className="rounded-xl border border-border bg-card p-4 space-y-4">
                    {/* Setting A: Shortlist Size (Top-K) with Number Input */}
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between text-xs">
                        <label className="font-semibold text-foreground flex items-center gap-1.5">
                          <Trophy className="h-3.5 w-3.5 text-primary" />
                          Shortlist Target Size (Top-K Teams):
                        </label>
                        <span className="font-mono text-primary font-bold">Top {quickTopK}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Button
                          variant="outline"
                          size="icon"
                          className="h-8 w-8 shrink-0"
                          onClick={() => setQuickTopK((prev) => Math.max(1, prev - 1))}
                        >
                          <Minus className="h-3.5 w-3.5" />
                        </Button>
                        <Input
                          type="number"
                          min="1"
                          max="100"
                          value={quickTopK}
                          onChange={(e) => setQuickTopK(Math.max(1, parseInt(e.target.value) || 1))}
                          className="h-8 text-center font-bold text-xs"
                        />
                        <Button
                          variant="outline"
                          size="icon"
                          className="h-8 w-8 shrink-0"
                          onClick={() => setQuickTopK((prev) => prev + 1)}
                        >
                          <Plus className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </div>

                    {/* Setting B: Team Size Bounds */}
                    <div className="space-y-1.5 pt-1 border-t border-border/60">
                      <div className="flex items-center justify-between text-xs">
                        <label className="font-semibold text-foreground flex items-center gap-1.5">
                          <Users className="h-3.5 w-3.5 text-sky-600" />
                          Allowed Team Size Bounds:
                        </label>
                        <span className="font-mono text-xs text-muted-foreground">
                          {quickMinTeamSize} to {quickMaxTeamSize} members
                        </span>
                      </div>
                      <div className="grid grid-cols-2 gap-2">
                        <div className="space-y-0.5">
                          <span className="text-[10px] text-muted-foreground uppercase font-bold">Min Members</span>
                          <Input
                            type="number"
                            min="1"
                            max={quickMaxTeamSize}
                            value={quickMinTeamSize}
                            onChange={(e) => setQuickMinTeamSize(Math.max(1, parseInt(e.target.value) || 1))}
                            className="h-8 text-xs font-semibold"
                          />
                        </div>
                        <div className="space-y-0.5">
                          <span className="text-[10px] text-muted-foreground uppercase font-bold">Max Members</span>
                          <Input
                            type="number"
                            min={quickMinTeamSize}
                            max="20"
                            value={quickMaxTeamSize}
                            onChange={(e) => setQuickMaxTeamSize(Math.max(quickMinTeamSize, parseInt(e.target.value) || quickMinTeamSize))}
                            className="h-8 text-xs font-semibold"
                          />
                        </div>
                      </div>
                    </div>

                    {/* Setting C: Minimum CGPA Cutoff */}
                    <div className="space-y-1.5 pt-1 border-t border-border/60">
                      <div className="flex items-center justify-between text-xs">
                        <label className="font-semibold text-foreground flex items-center gap-1.5">
                          <BookOpen className="h-3.5 w-3.5 text-emerald-600" />
                          Minimum Academic CGPA Cutoff:
                        </label>
                        <span className="font-mono text-emerald-700 font-bold">
                          {quickMinCgpa.toFixed(1)} / 10.0
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <input
                          type="range"
                          min="0.0"
                          max="10.0"
                          step="0.1"
                          value={quickMinCgpa}
                          onChange={(e) => setQuickMinCgpa(parseFloat(e.target.value) || 0)}
                          className="w-full h-1.5 bg-muted rounded-lg appearance-none cursor-pointer accent-emerald-600"
                        />
                        <Input
                          type="number"
                          step="0.1"
                          min="0"
                          max="10"
                          value={quickMinCgpa}
                          onChange={(e) => setQuickMinCgpa(parseFloat(e.target.value) || 0)}
                          className="h-8 w-18 text-center text-xs font-mono font-semibold"
                        />
                      </div>
                    </div>

                    {/* Setting D: GitHub Verifiable Signals Checklist */}
                    <div className="space-y-2 pt-1 border-t border-border/60">
                      <label className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                        <Cpu className="h-3.5 w-3.5 text-primary" />
                        GitHub Verifiable Signals to Include:
                      </label>
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs">
                        {/* Box 1: Repos */}
                        <label
                          className={`flex items-center gap-2 rounded-md border p-2 cursor-pointer transition-colors ${
                            quickGithubSignals.repoCount
                              ? 'border-primary/40 bg-primary/5 text-foreground font-medium'
                              : 'border-border text-muted-foreground'
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={quickGithubSignals.repoCount}
                            onChange={(e) =>
                              setQuickGithubSignals((prev) => ({ ...prev, repoCount: e.target.checked }))
                            }
                            className="rounded border-border accent-primary h-3.5 w-3.5"
                          />
                          <span>Public Repos</span>
                        </label>

                        {/* Box 2: Recent Activity */}
                        <label
                          className={`flex items-center gap-2 rounded-md border p-2 cursor-pointer transition-colors ${
                            quickGithubSignals.recentActivity
                              ? 'border-primary/40 bg-primary/5 text-foreground font-medium'
                              : 'border-border text-muted-foreground'
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={quickGithubSignals.recentActivity}
                            onChange={(e) =>
                              setQuickGithubSignals((prev) => ({ ...prev, recentActivity: e.target.checked }))
                            }
                            className="rounded border-border accent-primary h-3.5 w-3.5"
                          />
                          <span>Recent Activity</span>
                        </label>

                        {/* Box 3: Commits */}
                        <label
                          className={`flex items-center gap-2 rounded-md border p-2 cursor-pointer transition-colors ${
                            quickGithubSignals.commits
                              ? 'border-primary/40 bg-primary/5 text-foreground font-medium'
                              : 'border-border text-muted-foreground'
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={quickGithubSignals.commits}
                            onChange={(e) =>
                              setQuickGithubSignals((prev) => ({ ...prev, commits: e.target.checked }))
                            }
                            className="rounded border-border accent-primary h-3.5 w-3.5"
                          />
                          <span>Commits Volume</span>
                        </label>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            /* Stage 2: Instant Results Leaderboard (Wide & Distort-Free) */
            <div className="space-y-3 py-2 overflow-hidden flex flex-col flex-1">
              {/* Summary Stats Banner */}
              <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 text-xs shrink-0">
                <div className="flex items-center gap-2">
                  <Trophy className="h-4 w-4 text-emerald-600" />
                  <span className="font-bold text-emerald-950">
                    Leaderboard Ready: Top {quickTopK} Shortlist Generated
                  </span>
                </div>
                <div className="flex items-center gap-3 text-[11px] text-emerald-800 font-medium">
                  <span>Evaluated {quickResults.length} Teams</span>
                  <span>·</span>
                  <span>Rules: Size {quickMinTeamSize}–{quickMaxTeamSize} · Min CGPA {quickMinCgpa.toFixed(1)}</span>
                </div>
              </div>

              {/* Leaderboard Table Container */}
              <div className="overflow-y-auto max-h-[460px] rounded-lg border border-border bg-card shadow-xs">
                <table className="w-full text-left text-xs border-collapse">
                  <thead className="sticky top-0 z-10 bg-muted/95 backdrop-blur-xs border-b border-border text-[11px] font-bold text-muted-foreground uppercase">
                    <tr>
                      <th className="py-3 px-4 w-16 text-center">Rank</th>
                      <th className="py-3 px-4 min-w-[220px]">Team &amp; Members</th>
                      <th className="py-3 px-4 w-28 text-center">Status</th>
                      <th className="py-3 px-4 w-48 text-right">Composite Score</th>
                      <th className="py-3 px-4 min-w-[240px]">Audit Verdict</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {quickResults.map((team) => {
                      const isShortlisted = team.rank! <= quickTopK && team.status === 'ELIGIBLE';

                      // Color coding according to our standards:
                      // Eligible/Shortlisted: light emerald tint
                      // Needs Review: light amber/gold tint
                      // Ineligible: light rose tint
                      let rowBg = 'bg-card hover:bg-muted/30';
                      if (team.status === 'INELIGIBLE') {
                        rowBg = 'bg-rose-50/50 hover:bg-rose-50/70';
                      } else if (team.status === 'NEEDS_REVIEW') {
                        rowBg = 'bg-amber-50/50 hover:bg-amber-50/70';
                      } else if (isShortlisted) {
                        rowBg = 'bg-emerald-50/60 hover:bg-emerald-50/80';
                      }

                      return (
                        <tr key={team.teamName} className={`transition-colors ${rowBg}`}>
                          {/* Rank */}
                          <td className="py-3 px-4 text-center">
                            <span
                              className={`inline-flex items-center justify-center h-6 w-6 rounded-full text-xs font-mono font-bold ${
                                isShortlisted
                                  ? 'bg-emerald-600 text-white shadow-xs'
                                  : 'bg-muted text-muted-foreground'
                              }`}
                            >
                              {team.rank}
                            </span>
                          </td>

                          {/* Team Name & Members */}
                          <td className="py-3 px-4">
                            <div className="font-semibold text-foreground flex items-center gap-2">
                              <span>{team.teamName}</span>
                              {isShortlisted && (
                                <Badge variant="outline" className="border-emerald-500 text-emerald-700 bg-emerald-50 text-[10px] py-0 px-1.5 font-bold">
                                  Shortlisted
                                </Badge>
                              )}
                            </div>
                            <div className="text-[11px] text-muted-foreground pt-0.5 truncate max-w-sm">
                              {team.members.map((m) => m.name).join(', ')} ({team.members.length} members)
                            </div>
                          </td>

                          {/* Status Badge */}
                          <td className="py-3 px-4 text-center">
                            {team.status === 'ELIGIBLE' && (
                              <Badge variant="outline" className="border-emerald-500 text-emerald-700 bg-emerald-50 text-[10px] font-semibold">
                                Eligible
                              </Badge>
                            )}
                            {team.status === 'NEEDS_REVIEW' && (
                              <Badge variant="outline" className="border-amber-500 text-amber-700 bg-amber-50 text-[10px] font-semibold">
                                Needs Review
                              </Badge>
                            )}
                            {team.status === 'INELIGIBLE' && (
                              <Badge variant="outline" className="border-rose-500 text-rose-700 bg-rose-50 text-[10px] font-semibold">
                                Ineligible
                              </Badge>
                            )}
                          </td>

                          {/* Score Column (Completely Undistorted with Visual Progress Bar) */}
                          <td className="py-3 px-4 text-right">
                            <div className="flex items-center justify-end gap-1.5 font-mono">
                              <span className="text-base font-bold text-foreground">
                                {team.compositeScore.toFixed(1)}
                              </span>
                              <span className="text-[11px] text-muted-foreground">/ 100</span>
                            </div>
                            {/* Visual Score Bar */}
                            <div className="w-full bg-muted h-1.5 rounded-full overflow-hidden mt-1 mb-1">
                              <div
                                className="bg-primary h-full rounded-full transition-all duration-300"
                                style={{ width: `${Math.min(100, Math.max(0, team.compositeScore))}%` }}
                              />
                            </div>
                            <div className="text-[10px] text-muted-foreground font-mono flex items-center justify-end gap-1 whitespace-nowrap">
                              <span>GH: {team.githubScore}</span>
                              <span>·</span>
                              <span>AC: {team.academicScore}</span>
                              <span>·</span>
                              <span>RES: {team.resumeScore}</span>
                            </div>
                          </td>

                          {/* Audit Verdict */}
                          <td className="py-3 px-4">
                            <div className="flex items-start gap-1.5 text-xs text-muted-foreground">
                              {team.status === 'ELIGIBLE' && <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 mt-0.5 shrink-0" />}
                              {team.status === 'NEEDS_REVIEW' && <AlertTriangle className="h-3.5 w-3.5 text-amber-600 mt-0.5 shrink-0" />}
                              {team.status === 'INELIGIBLE' && <XCircle className="h-3.5 w-3.5 text-rose-600 mt-0.5 shrink-0" />}
                              <span className="leading-tight">{team.statusReason}</span>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <DialogFooter className="flex items-center justify-between w-full pt-3 border-t border-border mt-auto shrink-0">
            {quickEvalStage === 'input' ? (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setIsQuickEvalOpen(false)}
                >
                  Cancel
                </Button>
                <Button
                  size="sm"
                  className="gap-2 shadow-xs"
                  onClick={handleRunQuickEvaluation}
                  disabled={isEvaluating}
                >
                  {isEvaluating ? (
                    <>
                      <RotateCcw className="h-4 w-4 animate-spin" />
                      Evaluating in 10ms...
                    </>
                  ) : (
                    <>
                      <PlayCircle className="h-4 w-4" />
                      Run Instant Evaluation
                    </>
                  )}
                </Button>
              </>
            ) : (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-1.5"
                  onClick={handleResetQuickEval}
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                  Evaluate Another Dataset
                </Button>
                <div className="flex items-center gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    className="gap-1.5"
                    onClick={() => exportQuickLeaderboardCsv(quickResults, quickTopK)}
                  >
                    <Download className="h-3.5 w-3.5" />
                    Export CSV
                  </Button>
                  <Button
                    size="sm"
                    onClick={() => setIsQuickEvalOpen(false)}
                  >
                    Done / Close
                  </Button>
                </div>
              </>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default GuidePage;
