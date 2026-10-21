import React, { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
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
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';

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
CyberSquad,Tanvi Kulkarni,tanvi@example.com,https://github.com/tanvik,7.2,1st Year,"Java, Spring Boot",Cybersecurity`;

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
  // Interactive State
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
            <Button asChild size="default" className="gap-2 shadow-xs">
              <Link to="/evaluate">
                <PlayCircle className="h-4 w-4" />
                Launch Evaluation Wizard
              </Link>
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
              Try Scoring Sandbox
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

            <div className="p-4 border-t border-border bg-muted/20 text-center">
              <Button asChild size="sm" className="w-full gap-2">
                <Link to="/evaluate">
                  Apply This Rubric in Evaluation
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
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
    </div>
  );
};

export default GuidePage;
