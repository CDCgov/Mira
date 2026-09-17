import { useState, useRef, useEffect, useLayoutEffect, useCallback, useMemo, lazy, Suspense, Fragment, forwardRef, useImperativeHandle } from "react";
import { createPortal } from "react-dom";
import Papa from "papaparse";
const Plot = lazy(() => import("react-plotly.js"));
import {
  Dna,
  Home,
  Send,
  BookOpen,
  Bell,
  ChevronDown,
  ChevronRight,
  ChevronLeft,
  Users,
  LogOut,
  User,
  Check,
  Upload,
  Cpu,
  ShieldCheck,
  Tag,
  BarChart3,
  Clock,
  ClipboardList,
  Play,
  RefreshCw,
  Save,
  Download,
  FolderOpen,
  PlusCircle,
  Info,
  Database,
  FlaskConical,
  Rocket,
  Copy,
  Terminal,
  FileStack,
  Globe,
  ExternalLink,
  FileSearch,
  AlertCircle,
  ShieldQuestionMark,
  Network,
  Package,
  GitFork,
  Mail,
  Link,
  ArrowUp,
  ArrowDown,
  ArrowUpDown,
  ArrowRight,
  MessageSquare,
  X,
  Square,
  Trash2,
  Undo2,
  Pencil,
  CloudFog,
  CloudBackup,
  Cloud,
  BadgeQuestionMark,
  Settings2,
  Menu,
  Eye,
  EyeOff,
} from "lucide-react";

/* ── utility ─────────────────────────────────────── */
function cn(...classes) {
  return classes.filter(Boolean).join(" ");
}

/* ── recursively read a dropped folder's contents via the FileSystem entry API ── */
// Only these FASTQ file types are collected from a drop (files and folders alike).
const FASTQ_FILENAME_RE = /\.(fastq|fq)(\.gz)?$/i;

// Fully drain a directory reader: readEntries() only returns a batch (≤100) per
// call, so keep calling until it returns an empty batch to get every child entry.
function readAllDirectoryEntries(reader) {
  return new Promise((resolve, reject) => {
    const allEntries = [];
    const readBatch = () => {
      reader.readEntries((entries) => {
        if (!entries.length) { resolve(allEntries); return; }
        allEntries.push(...entries);
        readBatch();
      }, reject);
    };
    readBatch();
  });
}

// Read a single file entry into a File object.
function fileFromEntry(entry) {
  return new Promise((resolve, reject) => entry.file(resolve, reject));
}

// Walk an arbitrarily deep tree of FileSystem entries (files + directories),
// collecting every file at any depth. Uses an explicit stack so deeply-nested
// folders can't overflow the call stack, and drains each directory completely.
async function collectFilesFromEntry(rootEntry, out) {
  if (!rootEntry) return;
  const stack = [rootEntry];
  while (stack.length) {
    const entry = stack.pop();
    if (!entry) continue;
    if (entry.isFile) {
      // Only collect FASTQ files; ignore everything else in the tree.
      if (FASTQ_FILENAME_RE.test(entry.name)) out.push(await fileFromEntry(entry));
    } else if (entry.isDirectory) {
      const children = await readAllDirectoryEntries(entry.createReader());
      // Push all children (files and subdirectories) so they're visited too.
      for (const child of children) stack.push(child);
    }
  }
}

// Supports a drop containing a mix of loose files and whole folders (at any depth)
// in one gesture. Entries must be captured synchronously from the drop event before
// any await, otherwise the DataTransferItem entries become invalid.
async function collectFilesFromDataTransfer(dataTransfer) {
  const items = dataTransfer.items;
  const out = [];
  if (items && items.length && typeof items[0].webkitGetAsEntry === "function") {
    // Capture every entry synchronously first (before awaiting anything).
    const entries = Array.from(items).map((item) => item.webkitGetAsEntry()).filter(Boolean);
    // Then walk each captured entry tree exhaustively.
    for (const entry of entries) await collectFilesFromEntry(entry, out);
  } else {
    out.push(...Array.from(dataTransfer.files || []).filter((f) => FASTQ_FILENAME_RE.test(f.name)));
  }
  return out;
}

/* ── API BASE URL ───────────────────────────────── */
// Proxy API requests through the frontend dev server (see vite.config.js).
const API_BASE = "/api";

// API endpoints for the MIRA backend
const API = {
  checkVersion:     `${API_BASE}/version`,
  listRuns:         `${API_BASE}/list/runs`,
  listSubmissions:  `${API_BASE}/list/submissions`,
  statsSummary:     `${API_BASE}/stats/summary`,
  retrieveRun:      `${API_BASE}/retrieve/run`,
  createRun:        `${API_BASE}/create/run`,
  deleteSample:     `${API_BASE}/delete/sample`,
  renameRun:        `${API_BASE}/rename/run`,
  deleteRun:        `${API_BASE}/delete/run`,
  copyRun:          `${API_BASE}/copy/run`,
  uploadFastqs:     `${API_BASE}/upload/fastqs`,
  uploadCustomPrimerConfig:     `${API_BASE}/upload/custom_primer_config`,
  downloadCustomPrimerConfig:   `${API_BASE}/download/custom_primer_config`,
  validateRun:                  `${API_BASE}/validate/run`,
  validateCustomConfigs:        `${API_BASE}/validate/custom_configs`,
  runMIRA:                      `${API_BASE}/run/MIRA`,
  miraDAG:                      `${API_BASE}/MIRA/DAG`,
  miraTaskLog:                  `${API_BASE}/MIRA/task_log`,
  miraStatus:                   `${API_BASE}/MIRA/status`,
  miraCancel:                   `${API_BASE}/cancel/MIRA`,
  retrieveBarcodeAssignment:    `${API_BASE}/retrieve/barcode_assignment`,
  retrieveQcStatement:          `${API_BASE}/retrieve/qc_statement`,
  retrieveQcDecisions:          `${API_BASE}/retrieve/quality_control_decisions`,
  retrieveCoverageHeatmap:      `${API_BASE}/retrieve/coverage_heatmap`,  
  retrieveMiraSummary:          `${API_BASE}/retrieve/mira_summary`,
  retrieveSampleCoverageList:   `${API_BASE}/retrieve/sample_coverage_list`,
  retrieveSampleCoverageSankey: `${API_BASE}/retrieve/sample_coverage_sankeyfig`,
  retrieveSampleCoveragePlot:   `${API_BASE}/retrieve/sample_coverage_plot`,
  retrieveSampleCoverageLinear: `${API_BASE}/retrieve/sample_coverage_linearfig`,
  retrieveVariants:             `${API_BASE}/retrieve/variants`,
  retrieveMinorSnvs:            `${API_BASE}/retrieve/minor_snvs`,
  retrieveIndels:               `${API_BASE}/retrieve/indels`,
  retrieveNtPassedFasta:        `${API_BASE}/retrieve/passed_amended_consensus`,
  retrieveNtFailedFasta:        `${API_BASE}/retrieve/failed_amended_consensus`,
  retrieveAaPassedFasta:        `${API_BASE}/retrieve/passed_amino_acid_consensus`,
  retrieveAaFailedFasta:        `${API_BASE}/retrieve/failed_amino_acid_consensus`,
  retrieveNextcladeFasta:       `${API_BASE}/retrieve/nextclade_aligned_fasta`,
  downloadNtPassedFasta:        `${API_BASE}/download/nt_passed_fasta`,
  downloadNtFailedFasta:        `${API_BASE}/download/nt_failed_fasta`,
  downloadAaPassedFasta:        `${API_BASE}/download/aa_passed_fasta`,
  downloadAaFailedFasta:        `${API_BASE}/download/aa_failed_fasta`,
  downloadNextcladeFasta:       `${API_BASE}/download/nextclade_fasta`,
  downloadMiraReports:          `${API_BASE}/download/mira_reports`,
  listSubmitters:                    `${API_BASE}/list/submitters`,
  saveSubmitter:                     `${API_BASE}/save/submitter`,
  deleteSubmitter:                   `${API_BASE}/delete/submitter`,
  downloadSeqsenderConfigTemplate:   `${API_BASE}/download/seqsender/config_template`,
  downloadSeqsenderMetadataTemplate: `${API_BASE}/download/seqsender/metadata_template`,
  downloadSeqsenderMetadata:         `${API_BASE}/download/seqsender/metadata`,
  downloadSeqsenderFasta:            `${API_BASE}/download/seqsender/fasta`,
  downloadSeqsenderGff:              `${API_BASE}/download/seqsender/gff`,
  downloadSeqsenderRawReads:         `${API_BASE}/download/seqsender/raw_reads`,
  validateSeqsenderFiles:            `${API_BASE}/validate/seqsender/files`,
  uploadSeqsenderMetadata:           `${API_BASE}/upload/seqsender/metadata`,
  uploadSeqsenderFasta:              `${API_BASE}/upload/seqsender/fasta`,
  uploadSeqsenderRawReads:           `${API_BASE}/upload/seqsender/raw_reads`,
  uploadSeqsenderGisaidCli:          `${API_BASE}/upload/seqsender/gisaid_cli`,
  uploadSeqsenderGff:                `${API_BASE}/upload/seqsender/gff`,
  createSeqsenderConfig:             `${API_BASE}/create/config`,
  createSeqsenderSubmission:         `${API_BASE}/create/submission`,
  createSeqsenderSubmissionFiles:    `${API_BASE}/create/submission/files`,
  copySeqsenderSubmission:           `${API_BASE}/copy/submission`,
  deleteSeqsenderSubmission:         `${API_BASE}/delete/submission`,
  updateSeqsenderSubmissionComments: `${API_BASE}/update/submission/comments`,
  updateSeqsenderSubmissionStatusReportMessages: `${API_BASE}/update/submission/status_report/messages`,
  submitSeqsenderSubmission:         `${API_BASE}/submit/submission`,
  checkSeqsenderSubmissionProccess:  `${API_BASE}/check/submission/process`,
  checkSeqsenderSubmissionStatus:    `${API_BASE}/check/submission/status`,
  loadSeqsenderSubmissionStatus:     `${API_BASE}/load/submission/status`,
  listSeqSenderSubmissions:          `${API_BASE}/list/submissions`,
  retrieveSeqsenderSubmission:       `${API_BASE}/retrieve/submission`,
  retrieveSeqSenderConfig:           `${API_BASE}/retrieve/config`,
  retrieveSeqSenderMetadata:         `${API_BASE}/retrieve/metadata`,
  retrieveSeqSenderFasta:            `${API_BASE}/retrieve/fasta`,
  retrieveSeqSenderGisaidCli:        `${API_BASE}/retrieve/gisaid_cli`,
  retrieveSeqSenderGff:              `${API_BASE}/retrieve/gff`,
  retrieveSeqSenderTable2asn:        `${API_BASE}/retrieve/table2asn`,
  retrieveSeqSenderSubmissionLog:    `${API_BASE}/retrieve/submission_log`,
  retrieveSeqSenderSubmissionStatus: `${API_BASE}/retrieve/submission_status`,
  retrieveSeqSenderVersion:          `${API_BASE}/seqsender/version`,
};

// Persist the in-flight MIRA run so it keeps processing (and stays cancellable) after the
// user navigates away, closes the browser, and reopens it. The backend process is unaffected
// by the browser; we only need to remember which run/PID to resume polling for.
const ACTIVE_RUN_KEY = "mira.activeRun";
const readActiveRun = () => {
  try { return JSON.parse(localStorage.getItem(ACTIVE_RUN_KEY) || "null"); }
  catch { return null; }
};
const writeActiveRun = (run) => {
  try { localStorage.setItem(ACTIVE_RUN_KEY, JSON.stringify(run)); } catch { /* storage unavailable */ }
};
const clearActiveRun = () => {
  try { localStorage.removeItem(ACTIVE_RUN_KEY); } catch { /* storage unavailable */ }
};

// Standardized on-disk filenames the backend always saves custom config uploads
// under, regardless of the originally-picked filename (must match schema_validator.py).
const CUSTOM_PRIMER_CONFIG_FILENAME = "custom_primers.fasta";

/* ── simple dropdown hook ────────────────────────── */
function useDropdown() {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    function handleClick(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  return { open, setOpen, ref };
}

/* ── Dropdown wrapper ────────────────────────────── */
function Dropdown({ trigger, children, panelClassName = "w-48" }) {
  const { open, setOpen, ref } = useDropdown();
  const [position, setPosition] = useState({ top: 0, right: 8 });

  useLayoutEffect(() => {
    if (!open || !ref.current) return undefined;
    const updatePosition = () => {
      const rect = ref.current?.getBoundingClientRect();
      if (!rect) return;
      setPosition({
        top: rect.bottom + 8,
        right: Math.max(8, window.innerWidth - rect.right),
      });
    };
    updatePosition();
    window.addEventListener("resize", updatePosition);
    return () => window.removeEventListener("resize", updatePosition);
  }, [open, ref]);

  return (
    <div ref={ref} className="relative">
      <div onClick={() => setOpen((v) => !v)}>{trigger}</div>
      {open && createPortal(
        <div
          onMouseDown={(event) => event.stopPropagation()}
          style={{ top: position.top, right: position.right }}
          className={cn("fixed z-[1000] rounded-md border border-border bg-popover shadow-lg py-1", panelClassName)}
        >
          {children}
        </div>,
        document.body
      )}
    </div>
  );
}

// Dropdown item with optional icon
function DropdownItem({ onClick, icon: Icon, children }) {
  return (
    <button
      onClick={onClick}
      className="w-full flex items-center gap-2 px-4 py-2 text-sm text-foreground hover:bg-muted transition-colors"
    >
      {Icon && <Icon size={14} />}
      {children}
    </button>
  );
}

/* ── Tab definitions ─────────────────────────────── */
const TABS = [
  { id: "home",       label: "Home",       icon: Home },
  { id: "assembly",   label: "Mira",   icon: Dna },
  { id: "seqsender",  label: "SeqSender",  icon: Send },
];

/* ── Home Tab ────────────────────────────────────── */
const STATS = [
  { tag: "mira", label: "Sequencing Runs", value: "…",  hover: "Click here to see past runs",  icon: Cpu, color: "text-teal-600" },
  { tag: "seqsender-ncbi", label: "Submissions to NCBI", value: "…", sub: "",  icon: Cloud,   color: "text-purple-500" },
  { tag: "seqsender-gisaid", label: "Submissions to GISAID", value: "…", sub: "", icon: Cloud,   color: "text-purple-500" },
];

const FEATURES = [
  { icon: Cpu,          title: "IRMA Assembly",     desc: "Iterative refinement meta-assembler for influenza, SARS-CoV-2 and RSV consensus genome assembly from FASTQ reads." },
  { icon: ShieldCheck,  title: "QC & Clade Assignment", desc: "Automated quality control metrics per segment and Nextclade-powered clade/lineage assignment for all supported pathogens." },
  { icon: Send,         title: "SeqSender",          desc: "One-click submission pipeline to NCBI BioSample, SRA, GenBank, and GISAID with configurable metadata and validation." },
  { icon: Network,      title: "Nextclade Integration", desc: "Build pre-configured Nextclade Web URLs to visualize clade assignments, mutations, and phylogenetic placement." },
];

// Median of a numeric array.
function median(values) {
  if (!values.length) return 0;
  const s = [...values].sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
}

// Dashboard card: a dot per sample plus a trend line through the per-run medians.
function HomeChartCard({ icon: Icon, title, statValue, statLabel, data, color, unit, yTitle, loading = false, emptyMessage }) {
  const hasData = Array.isArray(data) && data.length > 0;
  const xDots = [];
  const yDots = [];
  const dotMeta = [];
  // Plot samples against a numeric run index with horizontal jitter so
  // overlapping same-value points are all individually visible.
  data.forEach(({ runId, samples }, i) => samples.forEach((v, j) => {
    xDots.push(i + (Math.random() - 0.5) * 0.5);
    yDots.push(v);
    dotMeta.push([`${runId}-S${String(j + 1).padStart(2, "0")}`, runId]);
  }));
  const xMed = data.map((_, i) => i);
  const yMed = data.map((d) => median(d.samples));
  const runLabels = data.map((d) => d.run);

  // Default the downloaded image name to the plot's title.
  const chartConfig = {
    ...PLOT_CONFIG,
    toImageButtonOptions: { ...PLOT_CONFIG.toImageButtonOptions, filename: title.replace(/\s+/g, "_") },
  };

  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden flex flex-col min-h-0">
      <div className="flex items-center justify-between gap-2 px-4 py-3 border-b border-border bg-muted/20 shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <div className="flex items-center justify-center h-7 w-7 rounded-lg bg-primary/10 text-primary shrink-0">
            <Icon size={15} />
          </div>
          <h3 className="text-sm font-bold tracking-wide text-foreground truncate">{title}</h3>
        </div>
        <div className="text-left shrink-0">
          <p className="text-lg font-bold leading-none" style={{ color }}>{statValue}</p>
          <p className="text-[10px] text-muted-foreground">{statLabel}</p>
        </div>
      </div>
      <div className="flex-1 min-h-0 p-2">
        {hasData ? (
        <Suspense fallback={<div className="flex items-center justify-center h-full text-xs text-muted-foreground">Loading chart…</div>}>
          <Plot
            data={[
              {
                x: xDots,
                y: yDots,
                type: "scatter",
                mode: "markers",
                name: "Samples",
                customdata: dotMeta,
                marker: { color, size: 6, opacity: 0.35 },
                hovertemplate: `Sample %{customdata[0]}<br>Run %{customdata[1]}<br>%{y} ${unit}<extra></extra>`,
              },
              {
                x: xMed,
                y: yMed,
                type: "scatter",
                mode: "lines+markers",
                name: "Median",
                text: runLabels,
                line: { color, width: 2, shape: "spline" },
                marker: { color, size: 8, line: { color: "#ffffff", width: 1.5 } },
                hovertemplate: `%{text}<br>median %{y} ${unit}<extra></extra>`,
              },
            ]}
            layout={{
              autosize: true,
              margin: { l: 40, r: 16, t: 10, b: 30 },
              paper_bgcolor: "transparent",
              plot_bgcolor: "transparent",
              font: { size: 11 },
              showlegend: true,
              legend: { orientation: "h", x: 1, xanchor: "right", y: 1.15, font: { size: 10 } },
              hovermode: "closest",
              xaxis: {
                showgrid: false,
                automargin: true,
                tickmode: "array",
                tickvals: xMed,
                ticktext: runLabels,
                range: [-0.5, data.length - 0.5],
              },
              yaxis: { title: { text: yTitle, font: { size: 11 }, standoff: 8 }, showgrid: true, gridcolor: "rgba(0,0,0,0.06)", zeroline: false, automargin: true, rangemode: "tozero" },
            }}
            config={chartConfig}
            style={{ width: "100%", height: "100%", minHeight: 200 }}
            useResizeHandler
          />
        </Suspense>
        ) : (
          <div className="flex h-full items-center justify-center text-left px-6">
            <p className="text-xs text-muted-foreground">
              {loading ? "Loading run data…" : (emptyMessage || "No run data yet.")}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

function HomeTab({ onNewRun, onLoadRun, onOpenSeqSender }) {
  const [runCount, setRunCount] = useState(null);
  const [ncbiCount, setNcbiCount] = useState(null);     // sequences submitted to NCBI (GenBank + SRA)
  const [gisaidCount, setGisaidCount] = useState(null); // sequences submitted to GISAID
  const [segmentsTrend, setSegmentsTrend] = useState(null); // null = loading, [] = no data

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(API.listSubmissions);
        const data = res.ok ? await res.json() : null;
        const rows = Array.isArray(data?.submission_info) ? data.submission_info : [];
        if (!cancelled) {
          // Each row is one (submission, database) pair — count NCBI (GenBank + SRA) and GISAID submissions separately.
          setNcbiCount(rows.filter((r) => ["GENBANK", "SRA", "BIOSAMPLE"].includes((r.database ?? "").toUpperCase())).length);
          setGisaidCount(rows.filter((r) => (r.database ?? "").toUpperCase() === "GISAID").length);
        }
      } catch {
        if (!cancelled) { setNcbiCount(0); setGisaidCount(0); }
      }
    })();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(API.listRuns);
        const data = res.ok ? await res.json() : null;
        const runs = Array.isArray(data?.run_info) ? data.run_info : [];
        const completed = runs.filter((r) => r.assembly_status === "COMPLETED");
        if (!cancelled) setRunCount(completed.length);

        // Oldest→newest by run date; keep the most recent runs for a readable trend.
        const runTime = (r) => {
          const t = Date.parse((r.finished_at || r.created_at || "").replace(" ", "T"));
          return Number.isNaN(t) ? 0 : t;
        };
        // Segment counts are only meaningful for segmented (flu) genomes, so limit the chart to flu runs.
        const fluCompleted = completed.filter((r) => /^flu/i.test(r.experiment_type || ""));
        const recent = [...fluCompleted].sort((a, b) => runTime(a) - runTime(b)).slice(-12);

        // For each run, count assembled segments per sample from its MIRA summary
        // (one summary row per sample-segment), so the trend reflects live run data.
        const trend = await Promise.all(recent.map(async (run) => {
          try {
            const sres = await fetch(`${API.retrieveMiraSummary}?run_name=${encodeURIComponent(run.run_name)}&experiment_type=${encodeURIComponent(run.experiment_type)}`);
            if (!sres.ok) return null;
            const summary = await sres.json();
            const rows = Array.isArray(summary)
              ? summary
              : (summary?.columns && summary?.data)
                ? summary.data.map((r) => Object.fromEntries(summary.columns.map((c, i) => [c, r[i]])))
                : [];
            const perSample = {};
            rows.forEach((row) => {
              const sid = row.sample_id ?? row.Sample ?? row.sample ?? null;
              if (sid == null || sid === "") return;
              perSample[sid] = (perSample[sid] || 0) + 1;
            });
            const samples = Object.values(perSample);
            if (!samples.length) return null;
            const t = runTime(run);
            const label = t ? new Date(t).toLocaleDateString(undefined, { month: "short", day: "numeric" }) : run.run_name;
            return { run: label, runId: run.run_name, samples };
          } catch {
            return null;
          }
        }));

        if (!cancelled) setSegmentsTrend(trend.filter(Boolean));
      } catch {
        if (!cancelled) { setRunCount(0); setSegmentsTrend([]); }
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const segData = segmentsTrend ?? [];
  const medSegments = segData.length ? Math.round(median(segData.flatMap((d) => d.samples))) : "—";

  return (
    <div className="h-full flex flex-col overflow-hidden">

      {/* ── Body grid ────────────────────────────── */}
      <div className="flex-1 overflow-hidden p-8 grid grid-cols-2 grid-rows-[auto_minmax(0,1fr)] gap-4">

        {/* ── Stats row — spans both columns ─────── */}
        <div className="col-span-2 flex flex-nowrap items-stretch justify-between gap-3 overflow-x-auto">
          <div className="flex shrink-0 items-stretch gap-3">
            <button
              onClick={onNewRun}
              className="flex shrink-0 items-center gap-3 rounded-xl border border-emerald-400 bg-emerald-100 px-4 py-3 text-left text-gray-600 transition-colors hover:bg-emerald-300"
            >
              <PlusCircle size={22} className="shrink-0" />
              <p className="whitespace-nowrap text-xl font-bold leading-none">New Run</p>
            </button>
            {STATS.filter(({ tag }) => tag === "mira").map(({ label, icon: Icon, color }) => (
              <button
                key={label}
                onClick={onLoadRun}
                className="flex shrink-0 items-center gap-3 rounded-xl border border-border bg-card px-4 py-3 text-left transition-colors hover:bg-muted/40"
              >
                <Icon size={22} className={`${color} shrink-0`} />
                <div>
                  <p className={`text-xl font-bold leading-none ${color}`}>{runCount === null ? "…" : runCount.toLocaleString()}</p>
                  <p className="mt-0.5 whitespace-nowrap text-xs font-semibold text-foreground">{label}</p>
                </div>
              </button>
            ))}
          </div>

          <div className="ml-auto flex shrink-0 items-stretch gap-3">
            <button
              onClick={onOpenSeqSender}
              className="flex shrink-0 items-center gap-3 rounded-xl border border-sky-400 bg-sky-100 px-4 py-3 text-left text-gray-700 transition-colors hover:bg-sky-200"
            >
              <Send size={22} className="shrink-0 text-sky-700" />
              <p className="whitespace-nowrap text-xl font-bold leading-none">New Submission</p>
            </button>
            {STATS.filter(({ tag }) => tag !== "mira" && tag !== "seqsender-gisaid").map(({ tag, label, sub, icon: Icon, color }) => {
              const displayValue = tag === "seqsender-ncbi"
                ? (ncbiCount === null ? "…" : ncbiCount.toLocaleString())
                : (gisaidCount === null ? "…" : gisaidCount.toLocaleString());
              return (
                <button
                  key={label}
                  onClick={onOpenSeqSender}
                  className="flex shrink-0 items-center gap-3 rounded-xl border border-border bg-card px-4 py-3 text-left transition-colors hover:bg-muted/40"
                >
                  <Icon size={22} className={`${color} shrink-0`} />
                  <div>
                    <p className={`text-xl font-bold leading-none ${color}`}>{displayValue}</p>
                    <p className="mt-0.5 whitespace-nowrap text-xs font-semibold text-foreground">{label}</p>
                    <p className="whitespace-nowrap text-xs text-muted-foreground">{sub}</p>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* ── Segments per sample over time (real run data) ─── */}
        <HomeChartCard
          icon={BarChart3}
          title="Segments per Sample"
          statValue={medSegments}
          statLabel="median segments / sample"
          data={segData}
          loading={segmentsTrend === null}
          emptyMessage="No completed runs yet. Segment counts appear here after your first assembly."
          color="#0081A1"
          unit="segments"
          yTitle="Segment Count"
        />

        {/* ── Turnaround time (pending metadata & SeqSender integration) ─── */}
        <HomeChartCard
          icon={Clock}
          title="Turnaround Time"
          statValue="—"
          statLabel="median days: submission − collection"
          data={[]}
          emptyMessage="Turnaround time will populate once sample metadata and SeqSender submission dates are available."
          color="#722161"
          unit="days"
          yTitle="Days"
        />

      </div>
    </div>
  );
}

/* ── Assembly Tab ────────────────────────────────── */
// Inline width that grows an input/select to fit its text, clamped between a default min and max (in ch).
const fitWidth = (text, min = 20, max = 44) => ({
  width: `${Math.min(max, Math.max(min, String(text ?? "").length + 4))}ch`,
});

const ASSEMBLY_STEPS = [
  { id: "setup",    title: "Step 1: Setup",  subtitle: "Define run, configure sample sheet, and set assembly parameters", icon: Upload },
  { id: "progress", title: "Step 2: Processing",  subtitle: "Monitor assembly progress and stage status",                      icon: RefreshCw },
  { id: "results",  title: "Step 3: Results",     subtitle: "Assembly statistics, QC decisions, and coverage plots",           icon: BarChart3 },
  { id: "export",   title: "Step 4: Export",      subtitle: "Download FASTA outputs from the assembly run",                    icon: Download },
];

const SEQSENDER_ACTION = {
  title: "Step 5: SeqSender",
  subtitle: "Submit assembled sequences to NCBI & GISAID databases",
  icon: Send,
};

function StepHeader({ icon: Icon, title, subtitle, open }) {
  return (
    <div className="flex items-center gap-3 w-full">
      <div className="flex items-center justify-center h-8 w-8 rounded-lg bg-primary/10 text-primary shrink-0">
        <Icon size={16} />
      </div>
      <div className="flex-1 text-left">
        <p className="text-xs font-bold tracking-wider text-primary">{title}</p>
        <p className="text-xs text-muted-foreground">{subtitle}</p>
      </div>
      <ChevronRight size={15} className={cn("text-muted-foreground transition-transform shrink-0", open && "rotate-90")} />
    </div>
  );
}

function StepPanel({ children }) {
  return <div className="flex flex-col items-center px-4 pb-4 pt-2 space-y-4">{children}</div>;
}

function ResultSection({ id, children }) {
  return <div id={id} className="w-full min-w-0 overflow-x-auto overscroll-x-contain">{children}</div>;
}

function FieldLabel({ children }) {
  return <p className="text-xs font-semibold text-foreground mb-1">{children}</p>;
}

// Password input with a toggle to reveal/hide the typed value.
function PasswordInput({ value, onChange, autoComplete = "new-password", className = "", disabled = false }) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <input
        type={visible ? "text" : "password"}
        value={value}
        onChange={onChange}
        autoComplete={autoComplete}
        disabled={disabled}
        className={cn("w-full h-9 px-3 pr-9 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-60 disabled:cursor-not-allowed disabled:bg-muted", className)}
      />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        disabled={disabled}
        title={visible ? "Hide password" : "Show password"}
        className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
      >
        {visible ? <EyeOff size={15} /> : <Eye size={15} />}
      </button>
    </div>
  );
}

// Hover menu that flows a vertical cascade of result-section link pills out of a
// trigger pill (and smoothly back on leave). Rendered in a portal so it is not
// clipped by the Jump-To band's overflow.
function ResultSectionsMenu({ sections, onJump, children }) {
  const [render, setRender] = useState(false);
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState({ top: 0, left: 0 });
  const anchorRef = useRef(null);
  const hideTimer = useRef(null);
  const closeTimer = useRef(null);
  const rafRef = useRef(null);

  const show = () => {
    clearTimeout(hideTimer.current);
    clearTimeout(closeTimer.current);
    const el = anchorRef.current;
    if (el) {
      const r = el.getBoundingClientRect();
      setPos({ top: r.bottom + 6, left: r.left });
    }
    setRender(true);
    cancelAnimationFrame(rafRef.current);
    rafRef.current = requestAnimationFrame(() =>
      requestAnimationFrame(() => setOpen(true))
    );
  };
  const hide = () => {
    clearTimeout(hideTimer.current);
    hideTimer.current = setTimeout(() => {
      setOpen(false);
      closeTimer.current = setTimeout(() => setRender(false), 260);
    }, 120);
  };
  useEffect(() => () => {
    clearTimeout(hideTimer.current);
    clearTimeout(closeTimer.current);
    cancelAnimationFrame(rafRef.current);
  }, []);

  return (
    <div ref={anchorRef} onMouseEnter={show} onMouseLeave={hide} className="shrink-0">
      {children}
      {render && createPortal(
        <div
          onMouseEnter={show}
          onMouseLeave={hide}
          style={{ position: "fixed", top: pos.top, left: pos.left, zIndex: 60, transformOrigin: "top left" }}
          className={cn(
            "flex flex-col gap-1 p-1.5 rounded-xl border border-border bg-popover/95 backdrop-blur shadow-xl transition-all duration-200 ease-out",
            open ? "opacity-100 translate-y-0 scale-100" : "opacity-0 -translate-y-2 scale-95 pointer-events-none"
          )}
        >
          {sections.map(({ id, label }, i) => (
            <button
              key={id}
              onClick={() => onJump(id)}
              style={{ transitionDelay: `${open ? i * 35 : 0}ms` }}
              className={cn(
                "flex items-center px-2.5 py-1 rounded-full text-xs text-muted-foreground hover:text-primary hover:bg-muted/60 border border-dashed border-border whitespace-nowrap text-left transition-all duration-200 ease-out",
                open ? "opacity-100 translate-x-0" : "opacity-0 -translate-x-2"
              )}
            >
              {label}
            </button>
          ))}
        </div>,
        document.body
      )}
    </div>
  );
}

/* ── Shared Plotly modebar config ───────────────── */
// Per-row pixel height shared by the QC Decisions and Median Coverage heatmaps so
// their rows render at the same height.
const HEATMAP_ROW_PX = 14;

const PLOT_CONFIG = {
  responsive: true,
  displayModeBar: 'hover',
  modeBarButtonsToRemove: [
    'select2d', 'lasso2d',
    'hoverClosestCartesian', 'hoverCompareCartesian',
    'toggleSpikelines',
  ],
  toImageButtonOptions: { format: 'svg', scale: 2, filename: 'mira_plot' },
  modeBarButtonsToAdd: [{
    name: 'Download JPEG',
    title: 'Download plot as JPEG',
    icon: {
      width: 500,
      height: 500,
      path: 'M240 60 L340 60 L340 240 L420 240 L250 420 L80 240 L160 240 L160 60 Z M60 440 L440 440 L440 500 L60 500 Z',
    },
    click: (gd) => window.Plotly?.downloadImage(gd, {
      format: 'jpeg',
      scale: 2,
      filename: (typeof gd.layout?.title === 'string' ? gd.layout.title : gd.layout?.title?.text || 'mira_plot').replace(/\s+/g, '_'),
    }),
  }],
};

// Plotly figure pinned to its container's measured width and a viewport-capped
// height, so multi-subplot grids never overflow their box horizontally.
function ResponsivePlot({ data, layout, config, style, minHeight = 320, maxHeight = 640, heightVh = 0.72, ...rest }) {
  const ref = useRef(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    const measure = () => {
      const width = el.clientWidth;
      const height = Math.max(minHeight, Math.min(Math.round(window.innerHeight * heightVh), maxHeight));
      setSize((prev) => (prev.width === width && prev.height === height ? prev : { width, height }));
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    window.addEventListener("resize", measure);
    return () => { ro.disconnect(); window.removeEventListener("resize", measure); };
  }, [minHeight, maxHeight, heightVh]);
  return (
    <div ref={ref} className="w-full">
      {size.width > 0 && (
        <Suspense fallback={<div className="flex items-center justify-center h-40 text-xs text-muted-foreground">Loading chart…</div>}>
          <Plot
            data={data}
            layout={{ ...layout, autosize: false, width: size.width, height: size.height }}
            config={config}
            style={{ ...style, width: `${size.width}px`, height: `${size.height}px` }}
            {...rest}
          />
        </Suspense>
      )}
    </div>
  );
}

/* ── Reusable paginated + sortable result table ──── */
const N_BINS = 8;
const PUBUGN_8 = ['#fff7fb','#ece2f0','#d0d1e6','#a6bddb','#67a9cf','#3690c0','#02818a','#016450'];

// Columns shown by default in the Mira Summary table. Covers every column
// mira-oxide can emit across virus types (flu, sc2-wgs, sc2-spike, rsv),
// including all nextclade call columns. Names absent from a given run's data
// are simply ignored.
const MIRA_SUMMARY_DEFAULT_COLS = [
  "sample_id",
  "total_reads",
  "reads_mapped",
  "reference",
  "percent_reference_coverage",
  "median_coverage",
  "count_minor_snv_at_or_over_5_pct",
  "spike_percent_coverage",
  "spike_median_coverage",
  "di_5prime;di_3prime",
  "pass_fail_reason",
  "subtype",
  // nextclade calls (virus-specific keys; only those present in the data render)
  "clade",
  "clade_who",
  "nextclade_pango",
  "nextclade_alias",
];

function ResultTable({ title, data: rawData, page, setPage, pageSize = 100, colorize = false, compact = false, defaultVisibleCols = null, defaultHiddenCols = null, fitCols = 0, rotateHeaders = false, stickyFirstCol = false }) {
  const [sortCol, setSortCol] = useState(null);
  const [sortDir, setSortDir] = useState("asc");
  const [searchQuery, setSearchQuery] = useState("");
  const [colWidths, setColWidths] = useState({});          // { colName: px } — manually resized columns
  const [hiddenCols, setHiddenCols] = useState(() => {
    // When a default visible-column set is supplied, hide every other (existing) column up front.
    if (defaultVisibleCols) {
      const allCols = Array.isArray(rawData)
        ? (rawData[0] ? Object.keys(rawData[0]) : [])
        : (rawData?.columns ?? []);
      return new Set(allCols.filter(c => !defaultVisibleCols.includes(c)));
    }
    // Otherwise hide only the explicitly listed columns up front.
    if (defaultHiddenCols) return new Set(defaultHiddenCols);
    return new Set();
  });
  const [colFilters, setColFilters] = useState({});        // { colName: filterText } — per-column filters
  const [colMenuOpen, setColMenuOpen] = useState(false);   // column visibility menu
  const [showFilters, setShowFilters] = useState(false);   // per-column filter row visibility

  // Normalise: accept a list of row-dicts OR a pandas split-format {columns, data}
  const data = Array.isArray(rawData)
    ? rawData
    : (rawData?.columns && rawData?.data)
      ? rawData.data.map(row => Object.fromEntries(rawData.columns.map((c, i) => [c, row[i]])))
      : [];

  const cols = data.length > 0 && data[0] ? Object.keys(data[0]) : [];
  const visibleCols = cols.filter(c => !hiddenCols.has(c));

  // Width (in ch) for the first `fitCols` visible columns, sized to their longest header/cell value.
  const fitColWidths = useMemo(() => {
    if (!fitCols) return {};
    const out = {};
    visibleCols.slice(0, fitCols).forEach(c => {
      let maxLen = String(c).length;
      for (const row of data) {
        const v = row[c] == null ? "" : String(row[c]);
        if (v.length > maxLen) maxLen = v.length;
      }
      out[c] = `${Math.min(48, maxLen + 2)}ch`;
    });
    return out;
  }, [fitCols, visibleCols, data]);

  // Precompute numeric column min/max for heatmap coloring (fill_irma_summary_tbl logic)
  const colRanges = useMemo(() => {
    if (!colorize || data.length === 0) return {};
    const ranges = {};
    (data[0] ? Object.keys(data[0]) : []).forEach(c => {
      const nums = [];
      data.forEach(r => {
        const v = r[c];
        if (v !== null && v !== "" && v !== undefined) {
          const n = Number(v);
          if (!isNaN(n)) nums.push(n);
        }
      });
      if (nums.length > 0) ranges[c] = { min: Math.min(...nums), max: Math.max(...nums) };
    });
    return ranges;
  }, [colorize, data]);

  const getCellStyle = (col, val) => {
    if (!colorize || val == null || val === "") return {};
    const range = colRanges[col];
    if (!range) return {};
    const num = Number(val);
    if (isNaN(num)) return {};
    const { min, max } = range;
    const bin = max === min ? 0 : Math.min(Math.floor(((num - min) / (max - min)) * N_BINS), N_BINS - 1);
    return { backgroundColor: PUBUGN_8[bin], color: bin >= N_BINS / 2 ? '#fff' : 'inherit' };
  };

  const handleSort = (col) => {
    if (sortCol === col) {
      setSortDir(d => d === "asc" ? "desc" : "asc");
    } else {
      setSortCol(col);
      setSortDir("asc");
    }
    setPage(0);
  };

  const handleSearch = (q) => {
    setSearchQuery(q);
    setPage(0);
  };

  // Per-column text filter
  const setColFilter = (col, value) => {
    setColFilters(prev => ({ ...prev, [col]: value }));
    setPage(0);
  };

  // Toggle a column's visibility
  const toggleColVisible = (col) => setHiddenCols(prev => {
    const next = new Set(prev);
    next.has(col) ? next.delete(col) : next.add(col);
    return next;
  });

  // Drag-to-resize a column: capture the starting width and follow the pointer.
  const startResize = (col, e) => {
    e.preventDefault();
    e.stopPropagation();
    const th = e.currentTarget.closest("th");
    const startX = e.clientX;
    const startW = colWidths[col] ?? (th ? th.offsetWidth : 120);
    const onMove = (me) => {
      const w = Math.max(50, startW + (me.clientX - startX));
      setColWidths(prev => ({ ...prev, [col]: w }));
    };
    const onUp = () => {
      document.body.style.userSelect = "";
      document.body.style.cursor = "";
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    document.body.style.userSelect = "none";
    document.body.style.cursor = "col-resize";
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  };

  // 1. filter — global search + per-column filters (all AND-combined)
  const q = searchQuery.trim().toLowerCase();
  const activeColFilters = Object.entries(colFilters).filter(([, v]) => (v ?? "").trim() !== "");
  const filtered = (q || activeColFilters.length > 0)
    ? data.filter(row => {
        if (q && !cols.some(c => (row[c] == null ? "" : String(row[c])).toLowerCase().includes(q))) return false;
        for (const [c, fv] of activeColFilters) {
          if (!(row[c] == null ? "" : String(row[c])).toLowerCase().includes(fv.trim().toLowerCase())) return false;
        }
        return true;
      })
    : data;

  // 2. sort
  const sorted = sortCol
    ? [...filtered].sort((a, b) => {
        const va = a[sortCol], vb = b[sortCol];
        const na = Number(va), nb = Number(vb);
        if (va !== null && vb !== null && va !== "" && vb !== "" && !isNaN(na) && !isNaN(nb))
          return sortDir === "asc" ? na - nb : nb - na;
        const sa = String(va ?? "").toLowerCase(), sb = String(vb ?? "").toLowerCase();
        return sortDir === "asc" ? sa.localeCompare(sb) : sb.localeCompare(sa);
      })
    : filtered;

  const totalPages = Math.max(1, Math.ceil(sorted.length / pageSize));
  const pageStart = page * pageSize;
  const pageRows = sorted.slice(pageStart, pageStart + pageSize);
  const fname = title.replace(/\s+/g, "_");

  const downloadCSV = () => {
    const rows = [cols.map(c => `"${c.replace(/"/g, '""')}"`).join(","),
      ...sorted.map(row => cols.map(c => { const v = row[c] == null ? "" : String(row[c]); return `"${v.replace(/"/g, '""')}"`; }).join(","))
    ].join("\n");
    const blob = new Blob([rows], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = `${fname}.csv`; a.click();
    URL.revokeObjectURL(url);
  };

  const downloadExcel = () => {
    const html = `<html><head><meta charset="utf-8"></head><body><table><tr>${cols.map(c => `<th>${c}</th>`).join("")}</tr>${sorted.map(row => `<tr>${cols.map(c => `<td>${row[c] == null ? "" : String(row[c])}</td>`).join("")}</tr>`).join("")}</table></body></html>`;
    const blob = new Blob([html], { type: "application/vnd.ms-excel;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = `${fname}.xls`; a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="w-full min-w-0 rounded-xl border border-border overflow-hidden">
      {/* header bar */}
      <div className="flex items-center justify-between px-3 py-2 bg-muted/20 border-b border-border">
        <div className="flex items-center gap-2">
          <button onClick={downloadCSV} className="flex items-center gap-1 px-2 py-0.5 rounded text-xs border border-border text-muted-foreground hover:border-primary hover:text-primary transition-colors">
            <Download size={11} /> CSV
          </button>
          <button onClick={downloadExcel} className="flex items-center gap-1 px-2 py-0.5 rounded text-xs border border-border text-muted-foreground hover:border-primary hover:text-primary transition-colors">
            <Download size={11} /> Excel
          </button>
          <button
            onClick={() => setShowFilters(v => !v)}
            className={cn(
              "flex items-center gap-1 px-2 py-0.5 rounded text-xs border transition-colors",
              showFilters || activeColFilters.length > 0
                ? "border-primary text-primary bg-primary/5"
                : "border-border text-muted-foreground hover:border-primary hover:text-primary"
            )}
          >
            <FileSearch size={11} /> Filters{activeColFilters.length > 0 ? ` (${activeColFilters.length})` : ""}
          </button>
          <div className="relative">
            <button
              onClick={() => setColMenuOpen(v => !v)}
              className={cn(
                "flex items-center gap-1 px-2 py-0.5 rounded text-xs border transition-colors",
                hiddenCols.size > 0
                  ? "border-primary text-primary bg-primary/5"
                  : "border-border text-muted-foreground hover:border-primary hover:text-primary"
              )}
            >
              <FileStack size={11} /> Columns{hiddenCols.size > 0 ? ` (${cols.length - hiddenCols.size}/${cols.length})` : ""}
            </button>
            {colMenuOpen && (
              <>
                <div className="fixed inset-0 z-40" onClick={() => setColMenuOpen(false)} />
                <div className="absolute left-0 top-full mt-1 z-50 w-52 max-h-72 overflow-y-auto rounded-lg border border-border bg-popover shadow-xl p-1">
                  <div className="flex items-center justify-between px-2 py-1 border-b border-border mb-1">
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Toggle Columns</span>
                    <button onClick={() => setHiddenCols(new Set())} className="text-[10px] text-primary hover:underline">Reset</button>
                  </div>
                  {cols.map(c => (
                    <label key={c} className="flex items-center gap-2 px-2 py-1 rounded text-xs cursor-pointer hover:bg-muted/60 transition-colors">
                      <input type="checkbox" checked={!hiddenCols.has(c)} onChange={() => toggleColVisible(c)} className="accent-primary shrink-0" />
                      <span title={c} className="font-mono truncate">{c}</span>
                    </label>
                  ))}
                </div>
              </>
            )}
          </div>
          <p className="text-xs font-bold text-foreground uppercase tracking-wider">{title}</p>
        </div>
        <span className="text-xs text-muted-foreground">{data.length.toLocaleString()} total rows</span>
      </div>
      {/* search bar */}
      <div className="px-3 py-2 border-b border-border bg-muted/10">
        <div className="relative">
          <FileSearch size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none" />
          <input
            type="text"
            value={searchQuery}
            onChange={e => handleSearch(e.target.value)}
            placeholder={`Search ${title}…`}
            className="w-full h-7 pl-7 pr-7 rounded-md border border-border bg-background text-xs font-mono focus:outline-none focus:ring-1 focus:ring-ring"
          />
          {searchQuery && (
            <button onClick={() => handleSearch("")} className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors">
              <X size={11} />
            </button>
          )}
        </div>
      </div>


      {/* table */}
      <div className="overflow-auto max-h-[360px]">
        <table className={cn("w-full text-xs", (compact || Object.keys(colWidths).length > 0) && "table-fixed")}>
          <colgroup>
            {visibleCols.map(c => (
              <col key={c} style={colWidths[c] ? { width: colWidths[c] } : (fitColWidths[c] ? { width: fitColWidths[c] } : undefined)} />
            ))}
          </colgroup>
          <thead className="bg-muted sticky top-0 z-10">
            <tr>
              {visibleCols.map(c => (
                <th key={c} className={cn("relative px-3 py-2 text-left font-semibold text-muted-foreground font-mono select-none", (compact || colWidths[c]) ? "" : "whitespace-nowrap")}>
                  <span onClick={() => handleSort(c)} className="flex items-center gap-1 cursor-pointer hover:text-foreground transition-colors">
                    <span
                      title={c}
                      className={(compact || colWidths[c]) ? "truncate" : undefined}
                    >
                      {c}
                    </span>
                    {sortCol === c
                      ? sortDir === "asc" ? <ArrowUp size={9} className="text-primary shrink-0" /> : <ArrowDown size={9} className="text-primary shrink-0" />
                      : <ArrowUpDown size={9} className="opacity-30 shrink-0" />}
                  </span>
                  {/* resize grip */}
                  <span
                    onMouseDown={(e) => startResize(c, e)}
                    onClick={(e) => e.stopPropagation()}
                    title="Drag to resize column"
                    className="absolute top-0 right-0 h-full w-1.5 cursor-col-resize hover:bg-primary/40"
                  />
                </th>
              ))}
            </tr>
            {showFilters && (
              <tr className="bg-background">
                {visibleCols.map((c, ci) => (
                  <th key={c} className={cn("px-1.5 py-1 border-t border-border", stickyFirstCol && ci === 0 && "sticky left-0 z-20 bg-background")}>
                    <input
                      value={colFilters[c] ?? ""}
                      onChange={(e) => setColFilter(c, e.target.value)}
                      placeholder="Filter…"
                      className="w-full h-6 px-1.5 rounded border border-border bg-background text-[11px] font-normal font-mono focus:outline-none focus:ring-1 focus:ring-ring"
                    />
                  </th>
                ))}
              </tr>
            )}
          </thead>
          <tbody>
            {pageRows.length === 0 ? (
              <tr className="border-t border-border">
                <td colSpan={visibleCols.length} className="px-3 py-4 text-left text-muted-foreground">
                  No rows match your search.
                </td>
              </tr>
            ) : pageRows.map((row, i) => (
              <tr key={pageStart + i} className="border-t border-border hover:bg-muted/10">
                {visibleCols.map((c, ci) => {
                  const cellStyle = getCellStyle(c, row[c]);
                  return (
                    <td key={c} title={row[c] == null ? undefined : String(row[c])} className={cn("px-3 py-1.5 font-mono", (compact || colWidths[c]) ? "truncate" : "whitespace-nowrap", !cellStyle.backgroundColor && "text-foreground", stickyFirstCol && ci === 0 && "sticky left-0 z-10 bg-background")} style={cellStyle}>
                      {row[c] == null ? <span className="text-muted-foreground/50">—</span> : String(row[c])}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {/* pagination footer */}
      <div className="flex items-center justify-between px-3 py-2 border-t border-border bg-muted/10">
        <span className="text-xs text-muted-foreground">
          {q ? `${sorted.length.toLocaleString()} of ${data.length.toLocaleString()} rows` : `${sorted.length.toLocaleString()} rows`}
          {sorted.length > 0 && <span className="ml-1">· showing {pageStart + 1}–{Math.min(pageStart + pageSize, sorted.length)}</span>}
          {sortCol && <span className="ml-2 opacity-60">(sorted by <span className="font-mono">{sortCol}</span> {sortDir})</span>}
        </span>
        <div className="flex items-center gap-1">
          <button onClick={() => setPage(0)} disabled={page === 0} className="px-2 py-0.5 rounded text-xs border border-border disabled:opacity-40 hover:bg-muted/40 transition-colors">«</button>
          <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0} className="px-2 py-0.5 rounded text-xs border border-border disabled:opacity-40 hover:bg-muted/40 transition-colors">‹</button>
          <span className="px-2 text-xs text-muted-foreground">{page + 1} / {totalPages}</span>
          <button onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))} disabled={page >= totalPages - 1} className="px-2 py-0.5 rounded text-xs border border-border disabled:opacity-40 hover:bg-muted/40 transition-colors">›</button>
          <button onClick={() => setPage(totalPages - 1)} disabled={page >= totalPages - 1} className="px-2 py-0.5 rounded text-xs border border-border disabled:opacity-40 hover:bg-muted/40 transition-colors">»</button>
        </div>
      </div>
    </div>
  );
}

/* ── Empty-state card matching ResultTable's header styling ──── */
function EmptyResultTable({ title, message = "There is no data returned from this run." }) {
  return (
    <div className="w-full min-w-0 rounded-xl border border-border overflow-hidden">
      <div className="flex items-center justify-between px-3 py-2 bg-muted/20 border-b border-border">
        <p className="text-xs font-bold text-foreground uppercase tracking-wider">{title}</p>
      </div>
      <div className="px-3 py-6 text-left">
        <p className="text-xs text-muted-foreground">{message}</p>
      </div>
    </div>
  );
}

// ONT samplesheet fastq cell: shows the sample's fastq list truncated on one line,
// and a styled, scrollable hover card listing every file with a count header.
function OntFastqCell({ fastqList, uploadedMap }) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState({ top: 0, left: 0 });
  const anchorRef = useRef(null);
  const hideTimer = useRef(null);

  const anyUploaded = fastqList.some(fq => uploadedMap[fq]);

  const openCard = () => {
    clearTimeout(hideTimer.current);
    const el = anchorRef.current;
    if (el) {
      const r = el.getBoundingClientRect();
      setPos({ top: r.bottom, left: r.left });
    }
    setOpen(true);
  };
  const scheduleHide = () => {
    clearTimeout(hideTimer.current);
    hideTimer.current = setTimeout(() => setOpen(false), 120);
  };
  useEffect(() => () => clearTimeout(hideTimer.current), []);

  return (
    <span
      ref={anchorRef}
      onMouseEnter={openCard}
      onMouseLeave={scheduleHide}
      className="relative flex items-center gap-1 max-w-[300px] cursor-default"
    >
      {anyUploaded && <Upload size={10} className="text-emerald-500 shrink-0" />}
      <span className="block truncate">{fastqList.join(", ")}</span>
      {open && fastqList.length > 0 && createPortal(
        <div
          onMouseEnter={openCard}
          onMouseLeave={scheduleHide}
          style={{ position: "fixed", top: pos.top, left: pos.left, zIndex: 60 }}
          className="w-[380px] max-w-[80vw] rounded-lg border border-border bg-popover text-popover-foreground shadow-xl overflow-hidden"
        >
          <div className="px-3 py-2 border-b border-border bg-muted/40">
            <span className="text-xs font-semibold text-foreground">
              {fastqList.length} FASTQ file{fastqList.length === 1 ? "" : "s"} to concatenate during processing
            </span>
          </div>
          <div className="max-h-[220px] overflow-y-auto p-1.5 space-y-0.5 scrollbar-thin">
            {fastqList.map((fq, fi) => (
              <div key={fi} className="flex items-center gap-1.5 px-1.5 py-0.5 text-xs font-mono text-foreground">
                {uploadedMap[fq] && <Upload size={9} className="text-emerald-500 shrink-0" title="Uploaded this session" />}
                <span className="break-all">{fq}</span>
              </div>
            ))}
          </div>
        </div>,
        document.body
      )}
    </span>
  );
}

function AssemblyTab({ loadRunSignal, newRunSignal, setHeaderHidden, onOpenSeqSender }) {
  const [openStep, setOpenStep]                           = useState(() => new Set()); // step accordions start collapsed
  const [stepNavCollapsed, setStepNavCollapsed]           = useState(false);
  const stepNavRef                                         = useRef(null);
  const stepNavMeasureRef                                  = useRef(null);
  const { open: stepMenuOpen, setOpen: setStepMenuOpen, ref: stepMenuRef } = useDropdown();
  const [runName, setRunName]                             = useState("");
  const [experimentType, setExperimentType]               = useState("");
  const [primer, setPrimer]                               = useState("");
  const [customPrimers, setCustomPrimers]                 = useState("");   // file path to a custom primer FASTA file
  const [useCustomPrimers, setUseCustomPrimers]           = useState(false); // whether the Custom Primers option is enabled
  const [primerKmerLen, setPrimerKmerLen]                 = useState("");   // required alongside customPrimers
  const [primerRestrictWindow, setPrimerRestrictWindow]   = useState(""); // required alongside customPrimers
  const [subSample, setSubSample]                         = useState("0");
  const [irmaModule, setIrmaModule]                       = useState("");   // "" = FLU (default) | secondary | sensitive | utr
  const [customPrimersFile, setCustomPrimersFile]         = useState(null); // File object selected via Browse, for actual upload
  const [loadedCustomPrimersName, setLoadedCustomPrimersName] = useState(""); // filename already stored server-side for a loaded run
  const [customConfigDownloadError, setCustomConfigDownloadError] = useState(null); // { field, message } for a failed custom config download
  const [primersFileError, setPrimersFileError] = useState(null); // validation error when a non-.fasta file is picked for Custom Primers
  const [createParquet, setCreateParquet]           = useState(false);
  const [nextclade, setNextclade]                   = useState(true);
  const [keepWorkdir, setKeepWorkdir]               = useState(false); // preserve Nextflow work dir after a successful run (for reviewing per-task logs)
  const [exportFmt, setExportFmt]                   = useState("fasta");
  const [assembled, setAssembled]                   = useState(false);
  const [rightWidth, setRightWidth]                 = useState(440);
  const [sampleSearch, setSampleSearch]             = useState("");
  const [sortConfig, setSortConfig]                 = useState({ key: "sample_id", dir: "asc" });
  const [submitting, setSubmitting]                 = useState(false);
  const [submitError, setSubmitError]               = useState(null);
  const [submitSuccess, setSubmitSuccess]           = useState(null);
  const [submitProcessId, setSubmitProcessId]       = useState(null);
  const [loadRunModal, setLoadRunModal]             = useState(false);
  const [loadRunLoading, setLoadRunLoading]         = useState(false);
  const [loadRunError, setLoadRunError]             = useState(null);
  const [availableRuns, setAvailableRuns]           = useState([]);
  const [selectedRun, setSelectedRun]               = useState(null); // the run currently loaded/polled on the page
  const [loadRunSelectedRow, setLoadRunSelectedRow] = useState(null); // row highlighted inside the Load Run modal only
  const [runSearch, setRunSearch]                   = useState("");
  const [runSortDir, setRunSortDir]                 = useState("desc"); // "asc" | "desc" — run date sort order (desc = most recent first)
  const [uploadedOntFileObjects, setUploadedOntFileObjects]           = useState({}); // ONT filename → File object
  const [uploadedIlluminaFileObjects, setUploadedIlluminaFileObjects] = useState({}); // Illumina filename → File object

  // ── Export Run modal state ────────────────
  const [exportRunModal, setExportRunModal]           = useState(false);
  const [exportRunSearch, setExportRunSearch]         = useState("");
  const [exportRunSortDir, setExportRunSortDir]       = useState("asc"); // "asc" | "desc" — run_name sort order
  const [exportSelectedRun, setExportSelectedRun]     = useState(null);
  const [exportRunLoading, setExportRunLoading]       = useState(false);
  const [exportRunError, setExportRunError]           = useState(null);
  const [exportDownloading, setExportDownloading]     = useState(false);
  const [cancelRun, setCancelRun]                     = useState(false);    // whether the run has been cancelled

  // ── Edit Run modal state ───────────────────
  const [editRunModal, setEditRunModal]               = useState(false);
  const [editRunSearch, setEditRunSearch]             = useState("");
  const [editRunSortDir, setEditRunSortDir]           = useState("asc"); // "asc" | "desc" — run_name sort order
  const [editRunLoading, setEditRunLoading]           = useState(false);
  const [editRunError, setEditRunError]               = useState(null);
  const [editSelectedRun, setEditSelectedRun]         = useState(null); // run row chosen from the list
  const [editMode, setEditMode]                       = useState(null); // null | "rename" | "copy" | "delete"
  const [editNewName, setEditNewName]                 = useState("");  // new name input for rename/copy
  const [editActionLoading, setEditActionLoading]     = useState(false);
  const [editActionError, setEditActionError]         = useState(null);

  const [isNewRun, setIsNewRun]                       = useState(true);   // true = new run, false = loaded existing run
  const [confirmRemoveIdx, setConfirmRemoveIdx]       = useState(null); // index of sample row pending removal confirmation
  const [taskLog, setTaskLog]                         = useState(null); // { loading, error, data, process, sample, stream } for the task log popup
  const [taskLogCopied, setTaskLogCopied]             = useState(false); // brief "copied" feedback for the log modal's copy button
  const [taskHover, setTaskHover]                     = useState(null); // { key, process, sample, x, y, loading, error, data } for the streaming stdout hover box
  const [ontConfirmFiles, setOntConfirmFiles]         = useState(null); // [{ file, name }] awaiting confirmation when no flowcell-ID files were found
  const [ontConfirmSelected, setOntConfirmSelected]   = useState(() => new Set()); // sanitized filenames checked in the confirm dialog
  const [uploadOntFastq, setUploadOntFastq]           = useState([]);      // list of sanitized ONT fastq filenames uploaded this session
  const [uploadOntError, setUploadOntError]           = useState(null);   // file-naming validation errors for ONT uploads
  const [uploadIlluminaFastq, setUploadIlluminaFastq] = useState([]); // list of sanitized Illumina fastq filenames uploaded this session
  const [uploadIlluminaError, setUploadIlluminaError] = useState(null); // file-naming validation errors for Illumina uploads
  const [showDAG, setShowDAG]                         = useState(false);  // whether to show the DAG view
  const [pipelineDAG, setPipelineDAG]                 = useState(null);     // pipeline DAG from /pipeline/status
  const [pipelinePolling, setPipelinePolling]         = useState(false);    // whether polling is active

  // ── Result section state ──────────────────────
  const [resultBarcodeAssignments, setResultBarcodeAssignments]       = useState(null);
  const [resultQcStatement, setResultQcStatement]                     = useState(null);
  const [resultQcDecisions, setResultQcDecisions]                     = useState(null);  // Plotly pass/fail heatmap
  const [resultCoverageHeatmap, setResultCoverageHeatmap]             = useState(null);
  const [resultMiraSummary, setResultMiraSummary]                     = useState(null);
  const [resultSampleCoverageList, setResultSampleCoverageList]       = useState(null);
  const [resultSampleCoverageSankey, setResultSampleCoverageSankey]   = useState(null); // {sample_id: plotly_figure}
  const [resultSampleCoveragePlot, setResultSampleCoveragePlot]       = useState(null); // {sample_id: plotly_figure}
  const [resultSampleCoverageLinear, setResultSampleCoverageLinear]   = useState(null); // {sample_id: combined coverage figure}
  const [focusedCovSegment, setFocusedCovSegment]                     = useState(null); // segment name focused in combined view, or null
  const [selectedSampleForCoverage, setSelectedSampleForCoverage]     = useState("");   // selected sample in dropdown
  const [resultVariants, setResultVariants]                           = useState(null);
  const [resultMinorSnvs, setResultMinorSnvs]                         = useState(null);
  const [resultIndels, setResultIndels]                               = useState(null);
  const [resultNtPassedFasta, setResultNtPassedFasta]                 = useState(null);
  const [resultNtFailedFasta, setResultNtFailedFasta]                 = useState(null);
  const [resultAaPassedFasta, setResultAaPassedFasta]                 = useState(null);
  const [resultAaFailedFasta, setResultAaFailedFasta]                 = useState(null);
  const [resultNextcladeFasta, setResultNextcladeFasta]               = useState(null);
  const [indelsPage, setIndelsPage]                                   = useState(0);    // current indels table page (0-indexed)
  const [variantsPage, setVariantsPage]                               = useState(0);    // current variants table page (0-indexed)
  const [minorSnvsPage, setMinorSnvsPage]                             = useState(0);    // current minor SNVs table page (0-indexed)
  const [miraSummaryPage, setMiraSummaryPage]                         = useState(0);    // current MIRA summary table page (0-indexed)

  // ── Poll /pipeline/status every 5 s while run is active ──────
  useEffect(() => {
    if (!pipelinePolling) return;
    let cancelled = false;
    const poll = async () => {
      try {

        // Guard against polling with a stale/missing run identity (e.g. selectedRun
        // was cleared elsewhere) — hammering the API with "undefined" params otherwise
        if (!selectedRun?.run_name || !selectedRun?.experiment_type) {
          if (!cancelled) setPipelinePolling(false);
          return;
        }

        // If the run is still active, poll /pipeline/status for the DAG
        if (submitProcessId && cancelRun === false) {
          const statusRes = await fetch(`${API.miraStatus}?run_name=${encodeURIComponent(selectedRun?.run_name)}&experiment_type=${encodeURIComponent(selectedRun?.experiment_type)}&pid=${submitProcessId}`);
          if (!statusRes.ok) { await statusRes.body?.cancel?.(); }
        }

        // Fetch the DAG from /pipeline/status
        const dagRes = await fetch(`${API.miraDAG}?run_name=${encodeURIComponent(selectedRun?.run_name)}&experiment_type=${encodeURIComponent(selectedRun?.experiment_type)}`);
        
        // If the run was cancelled, don't let a failed/missing DAG response (e.g. the
        // backend already cleared the job) leave polling stuck on forever.
        if (!dagRes.ok) {
          await dagRes.body?.cancel?.();
          if (cancelRun === true && !cancelled) {
            setAssembled(true);
            setSubmitting(false);
            setSubmitSuccess(null);
            setPipelinePolling(false);
            clearActiveRun();
          }
          return;
        }

        // If the DAG response is OK, parse it and update state
        const data = await dagRes.json();

        // If the run was cancelled, don't let a failed/missing DAG response (e.g. the
        // backend already cleared the job) leave polling stuck on forever.
        if (!cancelled) {
          setPipelineDAG(data);
          const done = data?.workflows?.status === "COMPLETED" || data?.workflows?.status === "FAILED" || data?.workflows?.status === "CANCELED" || data?.workflows?.status === "UNKNOWN";
          if (done || cancelRun === true) { 
            try {
              // Fetch all result tables and plots
              const barcodeRes = await fetch(
                `${API.retrieveBarcodeAssignment}?run_name=${encodeURIComponent(selectedRun?.run_name)}&experiment_type=${encodeURIComponent(selectedRun?.experiment_type)}`
              );
              const barcodeData = await barcodeRes.json();
              setResultBarcodeAssignments(barcodeRes.ok && barcodeData && typeof barcodeData === "object" ? barcodeData : null);

              const indelsRes = await fetch(
                `${API.retrieveIndels}?run_name=${encodeURIComponent(selectedRun?.run_name)}&experiment_type=${encodeURIComponent(selectedRun?.experiment_type)}`
              );
              const indelsData = await indelsRes.json();
              if (!indelsRes.ok) throw new Error(indelsData.detail || "Failed to load indels");
              setResultIndels(Array.isArray(indelsData) ? indelsData : null);
              setIndelsPage(0);

              const minorSnvsRes = await fetch(
                `${API.retrieveMinorSnvs}?run_name=${encodeURIComponent(selectedRun?.run_name)}&experiment_type=${encodeURIComponent(selectedRun?.experiment_type)}`
              );
              const minorSnvsData = await minorSnvsRes.json();
              if (!minorSnvsRes.ok) throw new Error(minorSnvsData.detail || "Failed to load minor SNVs");
              setResultMinorSnvs(Array.isArray(minorSnvsData) ? minorSnvsData : null);
              setMinorSnvsPage(0);

              const variantsData = await fetch(
                `${API.retrieveVariants}?run_name=${encodeURIComponent(selectedRun?.run_name)}&experiment_type=${encodeURIComponent(selectedRun?.experiment_type)}`
              );
              const variantsJson = await variantsData.json();
              if (!variantsData.ok) throw new Error(variantsJson.detail || "Failed to load variants");
              setResultVariants(Array.isArray(variantsJson) ? variantsJson : null);
              setVariantsPage(0);

              const heatmapRes = await fetch(
                `${API.retrieveCoverageHeatmap}?run_name=${encodeURIComponent(selectedRun?.run_name)}&experiment_type=${encodeURIComponent(selectedRun?.experiment_type)}`
              );
              const heatmapData = await heatmapRes.json();
              setResultCoverageHeatmap(heatmapRes.ok && heatmapData && typeof heatmapData === "object" ? heatmapData : null);

              const qcDecisionsRes = await fetch(
                `${API.retrieveQcDecisions}?run_name=${encodeURIComponent(selectedRun?.run_name)}&experiment_type=${encodeURIComponent(selectedRun?.experiment_type)}`
              );
              const qcDecisionsData = await qcDecisionsRes.json();
              setResultQcDecisions(qcDecisionsRes.ok && qcDecisionsData && typeof qcDecisionsData === "object" ? qcDecisionsData : null);

              const qcStatementRes = await fetch(
                `${API.retrieveQcStatement}?run_name=${encodeURIComponent(selectedRun?.run_name)}&experiment_type=${encodeURIComponent(selectedRun?.experiment_type)}`
              );
              const qcStatementData = await qcStatementRes.json();
              setResultQcStatement(qcStatementRes.ok && qcStatementData && typeof qcStatementData === "object" ? qcStatementData : null);

              const sampleCoverageListRes = await fetch(
                `${API.retrieveSampleCoverageList}?run_name=${encodeURIComponent(selectedRun?.run_name)}&experiment_type=${encodeURIComponent(selectedRun?.experiment_type)}`
              );
              const sampleCoverageListData = await sampleCoverageListRes.json();
              setResultSampleCoverageList(sampleCoverageListRes.ok ? sampleCoverageListData : null);

              // Fetch sankey for the first available sample
              const _sankeyInitSamples = sampleCoverageListData?.columns && sampleCoverageListData?.data
                ? [...new Set(sampleCoverageListData.data.map(r => r[sampleCoverageListData.columns.indexOf("Sample")]))].sort()
                : [];
              const _sankeyFirst = _sankeyInitSamples[0] ?? null;
              if (_sankeyFirst) {
                const sampleCoverageSankeyRes = await fetch(
                  `${API.retrieveSampleCoverageSankey}?run_name=${encodeURIComponent(selectedRun?.run_name)}&experiment_type=${encodeURIComponent(selectedRun?.experiment_type)}&sample_id=${encodeURIComponent(_sankeyFirst)}`
                );
                const sampleCoverageSankeyData = await sampleCoverageSankeyRes.json();
                if (sampleCoverageSankeyRes.ok && sampleCoverageSankeyData) {
                  setResultSampleCoverageSankey({ [_sankeyFirst]: sampleCoverageSankeyData });
                  setSelectedSampleForCoverage(_sankeyFirst);
                }
              }

              // Also fetch segment coverage plot for the first sample
              if (_sankeyFirst) {
                const coveragePlotRes = await fetch(
                  `${API.retrieveSampleCoveragePlot}?run_name=${encodeURIComponent(selectedRun?.run_name)}&experiment_type=${encodeURIComponent(selectedRun?.experiment_type)}&sample_id=${encodeURIComponent(_sankeyFirst)}`
                );
                const coveragePlotData = await coveragePlotRes.json();
                if (coveragePlotRes.ok && coveragePlotData) {
                  setResultSampleCoveragePlot({ [_sankeyFirst]: coveragePlotData });
                }
              }

              const miraSummaryRes = await fetch(
                `${API.retrieveMiraSummary}?run_name=${encodeURIComponent(selectedRun?.run_name)}&experiment_type=${encodeURIComponent(selectedRun?.experiment_type)}`
              );
              const miraSummaryData = await miraSummaryRes.json();
              if (!miraSummaryRes.ok) throw new Error(miraSummaryData.detail || "Failed to load MIRA summary");
              setResultMiraSummary(miraSummaryData ?? null);

              // Populate downloadable fasta files (if they exist)
              const ntPassedRes = await fetch(
                `${API.retrieveNtPassedFasta}?run_name=${encodeURIComponent(selectedRun?.run_name)}&experiment_type=${encodeURIComponent(selectedRun?.experiment_type)}`
              );
              const ntPassedData = await ntPassedRes.json();
              if (!ntPassedRes.ok) throw new Error(ntPassedData.detail || "Failed to load NT passed fasta");
              setResultNtPassedFasta(ntPassedData?.location ?? null);

              const ntFailedRes = await fetch(
                `${API.retrieveNtFailedFasta}?run_name=${encodeURIComponent(selectedRun?.run_name)}&experiment_type=${encodeURIComponent(selectedRun?.experiment_type)}`
              );
              const ntFailedData = await ntFailedRes.json();
              if (!ntFailedRes.ok) throw new Error(ntFailedData.detail || "Failed to load NT failed fasta");
              setResultNtFailedFasta(ntFailedData?.location ?? null);

              const aaPassedRes = await fetch(
                `${API.retrieveAaPassedFasta}?run_name=${encodeURIComponent(selectedRun?.run_name)}&experiment_type=${encodeURIComponent(selectedRun?.experiment_type)}`
              );
              const aaPassedData = await aaPassedRes.json();
              if (!aaPassedRes.ok) throw new Error(aaPassedData.detail || "Failed to load AA passed fasta");
              setResultAaPassedFasta(aaPassedData?.location ?? null);

              const aaFailedRes = await fetch(
                `${API.retrieveAaFailedFasta}?run_name=${encodeURIComponent(selectedRun?.run_name)}&experiment_type=${encodeURIComponent(selectedRun?.experiment_type)}`
              );
              const aaFailedData = await aaFailedRes.json();
              if (!aaFailedRes.ok) throw new Error(aaFailedData.detail || "Failed to load AA failed fasta");
              setResultAaFailedFasta(aaFailedData?.location ?? null);

              const nextcladeRes = await fetch(
                `${API.retrieveNextcladeFasta}?run_name=${encodeURIComponent(selectedRun?.run_name)}&experiment_type=${encodeURIComponent(selectedRun?.experiment_type)}`
              );
              const nextcladeData = await nextcladeRes.json();
              if (!nextcladeRes.ok) throw new Error(nextcladeData.detail || "Failed to load Nextclade fasta");
              setResultNextcladeFasta(nextcladeData?.location ?? null);

            } catch (resultErr) {

              // A single missing/failed result endpoint shouldn't keep the run stuck
              // in "Processing..." forever — log it and still mark the run as done.
              console.error("Failed to load one or more result sets:", resultErr);

            } finally {

              // If the run is done, stop polling regardless of individual result-fetch outcomes
              setAssembled(true);
              setIsNewRun(false);
              setSubmitting(false);
              setSubmitSuccess(null);
              setPipelinePolling(false);
              clearActiveRun();

            }
          }
        }
      } catch (_) { /* network error — keep polling */ }
    };
    poll(); // immediate first fetch
    const timer = setInterval(poll, 5000);
    return () => { cancelled = true; clearInterval(timer); };
  }, [pipelinePolling, submitProcessId, selectedRun, cancelRun]);

  // ── Sample sheet state ───────────────────────
  const SAMPLE_TYPES = ["- Control", "+ Control", "Test"];
  const [ontSampleRows, setOntSampleRows]           = useState([]);
  const [illuminaSampleRows, setIlluminaSampleRows] = useState([]);
  const [sampleColWidths, setSampleColWidths]       = useState({}); // { colName: px } — manually resized sample-sheet columns

  // Drag-to-resize a sample-sheet column: capture the starting width and follow the pointer.
  const startSampleColResize = (col, e) => {
    e.preventDefault();
    e.stopPropagation();
    const th = e.currentTarget.closest("th");
    const startX = e.clientX;
    const startW = sampleColWidths[col] ?? (th ? th.offsetWidth : 120);
    const onMove = (me) => {
      const w = Math.max(50, startW + (me.clientX - startX));
      setSampleColWidths(prev => ({ ...prev, [col]: w }));
    };
    const onUp = () => {
      document.body.style.userSelect = "";
      document.body.style.cursor = "";
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    document.body.style.userSelect = "none";
    document.body.style.cursor = "col-resize";
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  };
  const toggleSampleStatus = (idx) => {
    if (experimentType.toLowerCase().endsWith("ont")) {
      setOntSampleRows((prev) => prev.map((r, i) => i === idx ? { ...r, status: r.status === "Keep" ? "Exclude" : "Keep" } : r));
    } else {
      setIlluminaSampleRows((prev) => prev.map((r, i) => i === idx ? { ...r, status: r.status === "Keep" ? "Exclude" : "Keep" } : r));
    }
  };

  // Perform the actual removal: client-side only for new runs, deletes from the
  // database first for already-loaded runs.
  const performRemoveSample = async (idx) => {
    const isOnt = experimentType.toLowerCase().endsWith("ont");
    const rows = isOnt ? ontSampleRows : illuminaSampleRows;
    const sample = rows[idx];
    if (!sample) return;

    // New run: samplesheet only exists in local state, simply remove it
    if (isNewRun) {
      if (isOnt) setOntSampleRows((prev) => prev.filter((_, i) => i !== idx));
      else setIlluminaSampleRows((prev) => prev.filter((_, i) => i !== idx));
      return;
    }

    // Loaded run: sample is already persisted, delete it from the database first
    try {
      if (isOnt) {
        // ONT rows are one-per-sample with a list of fastqs; delete each fastq row from the DB
        for (const fq of (Array.isArray(sample.fastq) ? sample.fastq : [])) {
          const res = await fetch(API.deleteSample, {
            method: "DELETE",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              run_name: runName,
              experiment_type: experimentType,
              sample_id: sample.sample_id,
              fastq: fq,
              fastq_1: null,
              fastq_2: null,
            }),
          });
          const data = await res.json();
          if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail));
        }
        setOntSampleRows((prev) => prev.filter((_, i) => i !== idx));
      } else {
        const res = await fetch(API.deleteSample, {
          method: "DELETE",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            run_name: runName,
            experiment_type: experimentType,
            sample_id: sample.sample_id,
            fastq: null,
            fastq_1: sample.fastq_1,
            fastq_2: sample.fastq_2,
          }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail));
        setIlluminaSampleRows((prev) => prev.filter((_, i) => i !== idx));
      }
    } catch (err) {
      setSubmitError({ title: "Remove Sample Error", items: [err.message || "Failed to remove sample from the database."], missing: null });
    }
  };

  // Ask for confirmation before removing a sample row
  const removeSample = (idx) => setConfirmRemoveIdx(idx);

  // User confirmed removal — run the actual removal and close the modal
  const confirmRemoveSample = () => {
    if (confirmRemoveIdx !== null) performRemoveSample(confirmRemoveIdx);
    setConfirmRemoveIdx(null);
  };

  // Fetch and show the log for a task-sample in a modal. When `stream` is "stdout" the
  // process output (.command.out/.command.log) is shown; otherwise the error log.
  const openTaskLog = async (task, process, sample, stream) => {
    closeTaskHover(); // stop the live hover box while the modal is open
    if (!task?.hash || !selectedRun?.run_name || !selectedRun?.experiment_type) {
      setTaskLog({ loading: false, error: "No log is available for this task (its work directory may have been cleaned up).", data: null, process, sample, stream, hash: task?.hash ?? null });
      return;
    }
    setTaskLog({ loading: true, error: null, data: null, process, sample, stream, hash: task.hash });
    try {
      const streamParam = stream ? `&stream=${encodeURIComponent(stream)}` : "";
      const res = await fetch(`${API.miraTaskLog}?run_name=${encodeURIComponent(selectedRun.run_name)}&experiment_type=${encodeURIComponent(selectedRun.experiment_type)}&hash=${encodeURIComponent(task.hash)}${streamParam}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to load task log");
      setTaskLog(prev => (prev && prev.hash === task.hash && prev.stream === stream) ? { loading: false, error: null, data, process, sample, stream, hash: task.hash } : prev);
    } catch (err) {
      setTaskLog(prev => (prev && prev.hash === task.hash && prev.stream === stream) ? { loading: false, error: err.message, data: null, process, sample, stream, hash: task.hash } : prev);
    }
  };

  // Copy the entire log file's contents to the clipboard (not just the displayed
  // tail), with brief feedback.
  const copyTaskLog = async () => {
    if (!taskLog?.hash || !selectedRun?.run_name || !selectedRun?.experiment_type) return;
    try {
      const streamParam = taskLog.stream ? `&stream=${encodeURIComponent(taskLog.stream)}` : "";
      const res = await fetch(`${API.miraTaskLog}?run_name=${encodeURIComponent(selectedRun.run_name)}&experiment_type=${encodeURIComponent(selectedRun.experiment_type)}&hash=${encodeURIComponent(taskLog.hash)}${streamParam}&full=1`);
      const data = await res.json();
      const text = res.ok
        ? (data.full_text ?? (data.lines ?? []).map(ln => ln.text).join("\n"))
        : (taskLog.data?.lines ?? []).map(ln => ln.text).join("\n");
      if (!text) return;
      await navigator.clipboard.writeText(text);
      setTaskLogCopied(true);
      setTimeout(() => setTaskLogCopied(false), 1500);
    } catch {
      /* clipboard unavailable — ignore */
    }
  };

  // ── Task log modal: live feed ──
  // While the modal is open on a task that hasn't exited yet, keep re-fetching its
  // log so the feed stays current. Depends only on primitives so data updates don't
  // reset the polling interval.
  const taskLogRunning = taskLog?.data != null && taskLog.data.exit_code == null;
  useEffect(() => {
    if (!taskLog?.hash || taskLog.loading || taskLog.error) return;
    if (!taskLogRunning) return;
    if (!selectedRun?.run_name || !selectedRun?.experiment_type) return;
    const { hash, stream, process, sample } = taskLog;
    const streamParam = stream ? `&stream=${encodeURIComponent(stream)}` : "";
    const id = setInterval(async () => {
      try {
        const res = await fetch(`${API.miraTaskLog}?run_name=${encodeURIComponent(selectedRun.run_name)}&experiment_type=${encodeURIComponent(selectedRun.experiment_type)}&hash=${encodeURIComponent(hash)}${streamParam}`);
        const data = await res.json();
        if (!res.ok) return;
        setTaskLog(prev => (prev && prev.hash === hash && prev.stream === stream)
          ? { ...prev, loading: false, error: null, data, process, sample }
          : prev);
      } catch {
        /* transient fetch error — keep the last good feed */
      }
    }, 2000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [taskLog?.hash, taskLog?.stream, taskLog?.loading, taskLog?.error, taskLogRunning, selectedRun]);

  // Auto-scroll the log body to the bottom as new lines stream in, unless the user
  // has scrolled up to read earlier output.
  const taskLogBodyRef  = useRef(null);
  const taskLogStickRef = useRef(true);
  const onTaskLogScroll = (e) => {
    const el = e.currentTarget;
    taskLogStickRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
  };
  useEffect(() => {
    const el = taskLogBodyRef.current;
    if (el && taskLogStickRef.current) el.scrollTop = el.scrollHeight;
  }, [taskLog?.data?.lines?.length]);

  // ── Task Progress hover box: stream a task's stdout while the cursor is over its cell ──
  const taskHoverPollRef = useRef(null); // setInterval id for the streaming refresh
  const taskHoverKeyRef  = useRef(null); // key of the cell currently hovered (guards stale responses)

  // Fetch the stdout for a single task and apply it only if its cell is still hovered.
  const fetchTaskStdout = useCallback(async (task, process, sample, key) => {
    try {
      const res = await fetch(`${API.miraTaskLog}?run_name=${encodeURIComponent(selectedRun.run_name)}&experiment_type=${encodeURIComponent(selectedRun.experiment_type)}&hash=${encodeURIComponent(task.hash)}&stream=stdout`);
      const data = await res.json();
      if (taskHoverKeyRef.current !== key) return; // moved to another cell — ignore
      if (!res.ok) throw new Error(data.detail || "Failed to load task output");
      setTaskHover(prev => (prev && prev.key === key) ? { ...prev, loading: false, error: null, data } : prev);
    } catch (err) {
      if (taskHoverKeyRef.current !== key) return;
      setTaskHover(prev => (prev && prev.key === key) ? { ...prev, loading: false, error: err.message, data: null } : prev);
    }
  }, [selectedRun]);

  // Begin streaming stdout for the hovered task cell.
  const openTaskHover = (e, task, process, sample) => {
    if (!task?.hash || !selectedRun?.run_name || !selectedRun?.experiment_type) return;
    const key = `${process}||${sample ?? ""}`;
    const rect = e.currentTarget.getBoundingClientRect();
    taskHoverKeyRef.current = key;
    setTaskHover({ key, process, sample, x: rect.right, y: rect.top, loading: true, error: null, data: null });
    fetchTaskStdout(task, process, sample, key);
    if (taskHoverPollRef.current) clearInterval(taskHoverPollRef.current);
    taskHoverPollRef.current = setInterval(() => fetchTaskStdout(task, process, sample, key), 2000);
  };

  // Stop streaming and hide the hover box.
  const closeTaskHover = () => {
    taskHoverKeyRef.current = null;
    if (taskHoverPollRef.current) { clearInterval(taskHoverPollRef.current); taskHoverPollRef.current = null; }
    setTaskHover(null);
  };

  // Clear the streaming interval if the component unmounts mid-hover.
  useEffect(() => () => { if (taskHoverPollRef.current) clearInterval(taskHoverPollRef.current); }, []);


  // Export the sample sheet in CSV or Excel format
  const exportSampleSheet = (format) => {
    const isOnt = experimentType.toLowerCase().endsWith("ont");
    const activeRows = isOnt ? ontSampleRows : illuminaSampleRows;
    const headers = isOnt
      ? ["barcode", "sample_id", "sample_type", "single_end", "fastq", "status"]
      : ["sample_id", "sample_type", "single_end", "fastq_1", "fastq_2", "status"];
    const data = isOnt
      ? activeRows.flatMap(row => (Array.isArray(row.fastq) ? row.fastq : [row.fastq]).map(fq =>
          [row.barcode, row.sample_id, row.sample_type, row.single_end, fq, row.status]
        ))
      : activeRows.map(row => [row.sample_id, row.sample_type, row.single_end, row.fastq_1, row.fastq_2, row.status]);
    const fname = selectedRun?.run_name || "samplesheet";
    if (format === "csv") {
      const csv = [headers, ...data]
        .map(r => r.map(v => `"${(v ?? "").toString().replace(/"/g, '""')}"`).join(","))
        .join("\n");
      const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `${fname}.csv`; a.click();
      URL.revokeObjectURL(url);
    } else {
      const html = `<html><head><meta charset="utf-8"></head><body><table>${
        [headers, ...data].map(r => `<tr>${r.map(v => `<td>${(v ?? "").toString()}</td>`).join("")}</tr>`).join("")
      }</table></body></html>`;
      const blob = new Blob([html], { type: "application/vnd.ms-excel;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `${fname}.xls`; a.click();
      URL.revokeObjectURL(url);
    }
  };

  // Ref to track whether the user is currently dragging the right panel for resizing
  const dragging = useRef(false);

  // ── FASTQ upload dropzone: supports browsing files, and dragging-and-dropping
  // a mix of loose files and folders in one gesture ──
  const fastqFileInputRef = useRef(null);
  const [fastqDragOver, setFastqDragOver] = useState(false);

  // Populate the ONT sample sheet from parallel arrays of File objects and their
  // sanitized filenames. Shared by the normal (flowcell-ID prefixed) path and the
  // user-confirmed path for files that lack a flowcell ID.
  const processOntFiles = useCallback((ontFiles, ontSanitized) => {
    // Validate: ONT filenames must contain barcode##
    const invalidFiles = ontSanitized.filter(fname => !/barcode\d+/i.test(fname));
    if (invalidFiles.length > 0) {
      setUploadOntError({ items: [`For ONT run, the FASTQ files must contain a barcode pattern (barcode##) in their filenames.`], missing: [...invalidFiles] });
      return;
    } else {
      setUploadOntError(null);
    }

    // Store File objects keyed by sanitized filename
    const fileMap = {};
    ontFiles.forEach((f, i) => { fileMap[ontSanitized[i]] = f; });
    setUploadedOntFileObjects(prev => ({ ...prev, ...fileMap }));

    // Group ONT files by barcode extracted from filename
    const grouped = {};
    ontSanitized.forEach(fname => {
      const match = fname.match(/_barcode(\d+)_/i);
      const barcode = match
        ? `barcode${String(parseInt(match[1])).padStart(2, "0")}`
        : fname.replace(/\.(fastq|fq)(\.gz)?$/i, "");
      if (!grouped[barcode]) grouped[barcode] = [];
      grouped[barcode].push(fname);
    });

    // Sort barcodes ascending (barcode01, barcode02, ...)
    const sortedBarcodes = Object.keys(grouped).sort((a, b) => {
      const na = parseInt(a.match(/\d+/)?.[0] ?? "0");
      const nb = parseInt(b.match(/\d+/)?.[0] ?? "0");
      return na - nb;
    });

    // Continue sample numbering after existing rows
    const existingNums = ontSampleRows
      .map(r => parseInt(r.sample_id.replace(/\D+/g, "") || "0"))
      .filter(Boolean);
    let sampleCounter = existingNums.length > 0 ? Math.max(...existingNums) + 1 : 1;

    // Build one row per sample (barcode); each row's fastq is a list of filenames.
    const allPotentialRows = sortedBarcodes.map(barcode => {
      const existingByBarcode = ontSampleRows.find(r => r.barcode === barcode);
      const sample_id = existingByBarcode ? existingByBarcode.sample_id : `sample_${sampleCounter++}`;
      const sample_type = existingByBarcode ? existingByBarcode.sample_type : "Test";
      const status = existingByBarcode ? existingByBarcode.status : "Keep";
      // Merge any already-present fastqs for this sample with the newly uploaded ones
      const existingFastqs = existingByBarcode && Array.isArray(existingByBarcode.fastq) ? existingByBarcode.fastq : [];
      const fastq = [...new Set([...existingFastqs, ...grouped[barcode]])].sort((a, b) => a.localeCompare(b));
      return {
        barcode: barcode,
        sample_id: sample_id,
        sample_type: sample_type,
        single_end: "true",
        fastq: fastq,
        status: status
      };
    });

    // Update existing sample rows in place (matched by barcode) and append new ones
    setOntSampleRows(prev => {
      const byBarcode = new Map(allPotentialRows.map(r => [r.barcode, r]));
      const updated = prev.map(r => byBarcode.has(r.barcode) ? { ...r, ...byBarcode.get(r.barcode) } : r);
      const ontNewRows = allPotentialRows.filter(r => !prev.some(e => e.barcode === r.barcode));
      return ontNewRows.length > 0 ? [...updated, ...ontNewRows] : updated;
    });

    // Accumulate uploaded ONT fastq filenames
    setUploadOntFastq(prev => [...new Set([...prev, ...ontSanitized])]);
  }, [ontSampleRows]);

  // Confirm using the FASTQ files that were found when none carried a flowcell ID —
  // processes only the files the user checked in the dialog, then closes it.
  const confirmOntFilesWithoutFlowcell = useCallback(() => {
    setOntConfirmFiles(prev => {
      const chosen = (prev ?? []).filter(({ name }) => ontConfirmSelected.has(name));
      if (chosen.length > 0) processOntFiles(chosen.map(c => c.file), chosen.map(c => c.name));
      return null;
    });
  }, [ontConfirmSelected, processOntFiles]);

  const handleIncomingFastqFiles = useCallback((files) => {
    if (!files.length) return;

    // Determine if the experiment type is ONT or Illumina
    const isOnt = experimentType.toLowerCase().endsWith("ont");

    // Sanitize: replace spaces with underscores
    const sanitized = files.map(f => f.name.replace(/\s+/g, "_"));

    // Validate: only .fastq, .fastq.gz, .fq, .fq.gz files are accepted (case-insensitive)
    const nonFastqFiles = sanitized.filter(fname => !/\.(fastq|fq)(\.gz)?$/i.test(fname));
    if (nonFastqFiles.length > 0) {
      const err = { items: [`Only FASTQ files (.fastq, .fastq.gz, .fq, .fq.gz) are accepted.`], missing: [...nonFastqFiles] };
      isOnt ? setUploadOntError(err) : setUploadIlluminaError(err);
      return;
    }

    // Validate filenames based on experiment type
    if (isOnt) {

      // Ignore any files that don't start with an apparent ONT flowcell ID.
      // MinKNOW names its outputs "<FLOWCELL>_..." (e.g. FAP12345_..., PAM11162_...).
      const ONT_FLOWCELL_RE = /^[A-Za-z]{3}\d{3,}/;
      const ontKeep = sanitized
        .map((name, i) => (ONT_FLOWCELL_RE.test(name) ? i : -1))
        .filter(i => i >= 0);
      const ontFiles = ontKeep.map(i => files[i]);
      const ontSanitized = ontKeep.map(i => sanitized[i]);

      // No flowcell-ID-prefixed files were found — rather than rejecting outright,
      // surface every FASTQ that WAS found and let the user opt in to using them.
      if (ontSanitized.length === 0) {
        setUploadOntError(null);
        setOntConfirmFiles(files.map((f, i) => ({ file: f, name: sanitized[i] })));
        setOntConfirmSelected(new Set(sanitized));
        return;
      }

      processOntFiles(ontFiles, ontSanitized);

    } else {

      // Validate: Illumina filenames must contain _R1 or _R2
      const invalidFiles = sanitized.filter(fname => {
        const base = fname.replace(/\.(fastq|fq)(\.gz)?$/i, "");
        return !/_R1(?:_|$)/i.test(base) && !/_R2(?:_|$)/i.test(base);
      });
      if (invalidFiles.length > 0) {
        setUploadIlluminaError({ items: [`For Illumina run, the FASTQ files must contain "_R1" or "_R2" in their filenames.`], missing: [...invalidFiles] });
        return;
      } else {
        setUploadIlluminaError(null);
      }

      // Store File objects keyed by sanitized filename
      const fileMap = {};
      files.forEach((f, i) => { fileMap[sanitized[i]] = f; });
      setUploadedIlluminaFileObjects(prev => ({ ...prev, ...fileMap }));

      // Pair R1 / R2 files by sample_id prefix
      // Matches _R1_ (mid-filename) or _R1 at end, e.g. SAMPLE_R1_001 or SAMPLE_R1
      const grouped = {};
      sanitized.forEach(fname => {
        const base = fname.replace(/\.(fastq|fq)(\.gz)?$/i, "");
        const r1 = base.match(/^(.+?)_R1(?:_|$)/i);
        const r2 = base.match(/^(.+?)_R2(?:_|$)/i);
        let sampleId, read;
        if (r1) { sampleId = r1[1]; read = "R1"; }
        else if (r2) { sampleId = r2[1]; read = "R2"; }
        else { sampleId = base; read = "R1"; }
        if (!grouped[sampleId]) grouped[sampleId] = {};
        grouped[sampleId][read] = fname;
      });
      const allPotentialRows = Object.entries(grouped).map(([sampleId, reads]) => ({
        sample_id: sampleId,
        sample_type: "Test",
        single_end: reads.R1 && reads.R2 ? "false" : "true",
        fastq_1: reads.R1 || "",
        fastq_2: reads.R2 || "",
        status: "Keep",
      }));

      // Classify each new row: new sample or overwrite existing
      const newRows = [];
      const mergeUpdates = [];

      for (const newRow of allPotentialRows) {
        const existingRow = illuminaSampleRows.find(e => e.sample_id === newRow.sample_id);
        if (!existingRow) {
          newRows.push(newRow);
        } else {
          const sample_id = existingRow.sample_id;
          const sample_type = existingRow.sample_type;
          const fastq_1 = existingRow.fastq_1 ? existingRow.fastq_1 : newRow.fastq_1;
          const fastq_2 = existingRow.fastq_2 ? existingRow.fastq_2 : newRow.fastq_2;
          const single_end = fastq_1 && fastq_2 ? "false" : "true";
          const status = existingRow.status;
          mergeUpdates.push({
            sample_id:  sample_id,
            sample_type: sample_type,
            fastq_1:    fastq_1,
            fastq_2:    fastq_2,
            single_end: single_end,
            status: status,
          });
        }
      }

      // Apply updates + additions atomically
      setIlluminaSampleRows(prev => {
        const updated = prev.map(r => {
          const u = mergeUpdates.find(m => m.sample_id === r.sample_id);
          return u ? { ...r, ...u } : r;
        });
        return newRows.length > 0 ? [...updated, ...newRows] : updated;
      });

      // Accumulate uploaded Illumina fastq filenames
      setUploadIlluminaFastq(prev => [...new Set([...prev, ...sanitized])]);

    }
  }, [experimentType, ontSampleRows, illuminaSampleRows, processOntFiles]);

  // Ref-based (synchronous) guard against double-submission — React state updates
  // (e.g. `submitting`) are batched, so a fast double-click can invoke submitAssembly
  // twice before the button's `disabled` prop takes effect, launching two MIRA-NF
  // pipelines for the same run.
  const submitLockRef = useRef(false);

  // Define experiment types options for the dropdowns
  const EXPERIMENT_TYPES = [
    'Flu-Illumina',
    'Flu-ONT',
    'RSV-Illumina',
    'RSV-ONT',
    'SC2-Spike-Only-ONT',
    'SC2-Whole-Genome-Illumina',
    'SC2-Whole-Genome-ONT',
  ];

  // Define SC2 primers options for the dropdowns
  const SC2_PRIMERS = [
    { value: "articv3",     label: "Artic V3" },
    { value: "articv4",     label: "Artic V4" },
    { value: "articv4.1",   label: "Artic V4.1" },
    { value: "articv5.3.2", label: "Artic V5.3.2" },
    { value: "qiagen",      label: "Qiagen QIAseq" },
    { value: "swift",       label: "xGen\u2122 SARS-CoV-2 Amplicon Panel" },
    { value: "swift_211206",label: "xGen\u2122 SARS-CoV-2 Amplicon Panel (CDC customized)" },
  ];

  // Define RSV primers options for the dropdowns
  const RSV_PRIMERS = [
    { value: "RSV_CDC_8amplicon_230901", label: "RSV CDC 8 amplicon 230901" },
  ];

  // Handle mouse down event for resizing the right panel
  const onMouseDown = useCallback(() => {
    dragging.current = true;
    document.body.style.userSelect = "none";
    document.body.style.cursor = "col-resize";
    const onMove = (e) => {
      if (!dragging.current) return;
      const newW = document.body.clientWidth - e.clientX;
      setRightWidth(Math.max(280, Math.min(window.innerWidth * 0.75, newW)));
    };
    const onUp = () => {
      dragging.current = false;
      document.body.style.userSelect = "";
      document.body.style.cursor = "";
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }, []);

  // Hide the app header when the accordion is scrolled down, reveal it when scrolling back up.
  // The header collapses via a height transition, which grows this scroll container and makes
  // the browser clamp scrollTop back down mid-animation. On pages too short to sustain the
  // scroll, that clamp reads as "scrolling up" and re-reveals the header, causing a jitter loop.
  // A brief lock after each toggle absorbs those reflow-driven scroll events.
  const lastScrollTopRef = useRef(0);
  const headerToggleLockRef = useRef(0);
  const handleContentScroll = useCallback((e) => {
    const st = e.currentTarget.scrollTop;
    const delta = st - lastScrollTopRef.current;
    lastScrollTopRef.current = st;
    if (performance.now() < headerToggleLockRef.current) return;
    if (delta > 0 && st > 60) {
      setHeaderHidden?.(true);
      headerToggleLockRef.current = performance.now() + 350;
    } else if (delta < 0) {
      setHeaderHidden?.(false);
      headerToggleLockRef.current = performance.now() + 350;
    }
  }, [setHeaderHidden]);

  // Always restore the header when this tab unmounts.
  useEffect(() => () => setHeaderHidden?.(false), [setHeaderHidden]);

  // Auto-expand a step the moment its content first appears (steps start collapsed).
  useEffect(() => { if (showDAG) setOpenStep(prev => new Set(prev).add("progress")); }, [showDAG]);
  useEffect(() => { if (assembled) setOpenStep(prev => new Set(prev).add("results")); }, [assembled]);

  // 
  const toggle = (id) => setOpenStep((prev) => {
    const next = new Set(prev);
    next.has(id) ? next.delete(id) : next.add(id);
    return next;
  });

  // Fetch the sankey figure for a specific sample (lazy-loads, caches in resultSampleCoverageSankey)
  const fetchSankeyForSample = useCallback(async (sampleId) => {
    setSelectedSampleForCoverage(sampleId);
    setFocusedCovSegment(null); // switching samples returns to the separate-plots (grid) view
    if (!selectedRun || !sampleId) return;
    const fetchPromises = [];
    if (!resultSampleCoverageSankey?.[sampleId]) {
      fetchPromises.push(
        fetch(`${API.retrieveSampleCoverageSankey}?run_name=${encodeURIComponent(selectedRun.run_name)}&experiment_type=${encodeURIComponent(selectedRun.experiment_type)}&sample_id=${encodeURIComponent(sampleId)}`)
          .then(r => r.ok ? r.json() : null)
          .then(d => { if (d) setResultSampleCoverageSankey(prev => ({ ...(prev ?? {}), [sampleId]: d })); })
          .catch(() => {})
      );
    }
    if (!resultSampleCoveragePlot?.[sampleId]) {
      fetchPromises.push(
        fetch(`${API.retrieveSampleCoveragePlot}?run_name=${encodeURIComponent(selectedRun.run_name)}&experiment_type=${encodeURIComponent(selectedRun.experiment_type)}&sample_id=${encodeURIComponent(sampleId)}`)
          .then(r => r.ok ? r.json() : null)
          .then(d => { if (d) setResultSampleCoveragePlot(prev => ({ ...(prev ?? {}), [sampleId]: d })); })
          .catch(() => {})
      );
    }
    await Promise.all(fetchPromises);
  }, [selectedRun, resultSampleCoverageSankey, resultSampleCoveragePlot]);

  // Lazy-load the combined (all-segment) coverage figure for a sample, caching it.
  const fetchLinearForSample = useCallback((sampleId) => {
    if (!selectedRun || !sampleId || resultSampleCoverageLinear?.[sampleId]) return;
    fetch(`${API.retrieveSampleCoverageLinear}?run_name=${encodeURIComponent(selectedRun.run_name)}&experiment_type=${encodeURIComponent(selectedRun.experiment_type)}&sample_id=${encodeURIComponent(sampleId)}`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setResultSampleCoverageLinear(prev => ({ ...(prev ?? {}), [sampleId]: d })); })
      .catch(() => {});
  }, [selectedRun, resultSampleCoverageLinear]);

  // Reset all state variables to their initial values, effectively clearing the form and any loaded run data
  const resetRun = useCallback(() => {

    // Cancel any ongoing run if submitProcessId exists
    if (submitProcessId && selectedRun) {
      fetch(`${API.miraCancel}?run_name=${encodeURIComponent(selectedRun.run_name)}&experiment_type=${encodeURIComponent(selectedRun.experiment_type)}&pid=${submitProcessId}`)
        .catch(() => {});
    }
    clearActiveRun();

    // Reset all state variables to their initial values
    setRunName("");
    setExperimentType("");
    setPrimer("");
    setCustomPrimers("");
    setUseCustomPrimers(false);
    setPrimersFileError(null);
    setPrimerKmerLen("");
    setPrimerRestrictWindow("");
    setSubSample("0");
    setIrmaModule("");
    setCustomPrimersFile(null);
    setLoadedCustomPrimersName("");
    setCustomConfigDownloadError(null);
    setCreateParquet(false);
    setNextclade(true);
    setKeepWorkdir(false);
    setExportFmt("fasta");
    setAssembled(false);
    setSortConfig({ key: "sample_id", dir: "asc" });
    setSampleSearch("");
    setUploadedOntFileObjects({});
    setUploadedIlluminaFileObjects({});
    setSubmitting(false);
    setSubmitError(null);
    setSubmitSuccess(null);
    setSubmitProcessId(null);
    setIsNewRun(true);
    setLoadRunModal(false);
    setAvailableRuns([]);
    setLoadRunLoading(false);
    setLoadRunError(null);
    setSelectedRun(null);
    setLoadRunSelectedRow(null);
    setRunSearch("");
    setRunSortDir("desc");
    setExportRunModal(false);
    setExportRunSearch("");
    setExportRunSortDir("asc");
    setExportSelectedRun(null);
    setExportRunLoading(false);
    setExportRunError(null);
    setExportDownloading(false);
    setEditRunModal(false);
    setEditRunSearch("");
    setEditRunSortDir("asc");
    setEditRunLoading(false);
    setEditRunError(null);
    setEditSelectedRun(null);
    setEditMode(null);
    setEditNewName("");
    setEditActionLoading(false);
    setEditActionError(null);
    setConfirmRemoveIdx(null);
    setOntConfirmFiles(null);
    setOntConfirmSelected(new Set());
    setTaskLog(null);
    setShowDAG(false);
    setFastqDragOver(false);
    setUploadOntError(null);
    setUploadIlluminaError(null);
    setUploadOntFastq([]);
    setUploadIlluminaFastq([]);
    setPipelineDAG(null);
    setPipelinePolling(false);
    setCancelRun(false);
    setOntSampleRows([]);
    setIlluminaSampleRows([]);
    setResultBarcodeAssignments(null);
    setResultQcStatement(null);
    setResultQcDecisions(null);
    setResultVariants(null);
    setResultMinorSnvs(null);
    setResultIndels(null);
    setResultSampleCoverageList(null);
    setResultSampleCoverageSankey(null);
    setResultSampleCoveragePlot(null);
    setResultSampleCoverageLinear(null);
    setFocusedCovSegment(null);
    setSelectedSampleForCoverage("");
    setResultCoverageHeatmap(null);
    setResultNtPassedFasta(null);
    setResultNtFailedFasta(null);
    setResultAaPassedFasta(null);
    setResultAaFailedFasta(null);
    setResultNextcladeFasta(null);
    setIndelsPage(0);
    setVariantsPage(0);
    setMinorSnvsPage(0);
    setResultMiraSummary(null);
    setMiraSummaryPage(0);
    setOpenStep(new Set());
  }, []);

  // ── Load run modal: fetches available runs from the backend and displays them in a table ──
  const openLoadRunModal = useCallback(async () => {
    setLoadRunModal(true);
    setLoadRunLoading(true);
    setLoadRunError(null);
    setLoadRunSelectedRow(null);
    setRunSearch("");
    try {
      const res = await fetch(`${API.listRuns}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to fetch runs");
      setAvailableRuns(data.run_info ?? []);
    } catch (err) {
      if (err.name !== "AbortError") setLoadRunError(err.message);
    } finally {
      setLoadRunLoading(false);
    }
  }, []);

  // Open the Load Run modal when signaled from outside (e.g. the Home "Sequencing Runs" card).
  useEffect(() => {
    if (loadRunSignal) openLoadRunModal();
  }, [loadRunSignal, openLoadRunModal]);

  // Reset every assembly-page input to a clean "new run" state.
  const resetInputs = useCallback(() => {
    // Step 1 — run configuration
    setRunName("");
    setExperimentType("");
    setPrimer("");
    setSubSample("0");
    setIrmaModule("");
    setUseCustomPrimers(false);
    setCustomPrimers("");
    setPrimerKmerLen("");
    setPrimerRestrictWindow("");
    setCustomPrimersFile(null);
    setLoadedCustomPrimersName("");
    setCustomConfigDownloadError(null);
    setPrimersFileError(null);
    setCreateParquet(false);
    setNextclade(true);
    setKeepWorkdir(false);
    // Sample sheet + uploads
    setOntSampleRows([]);
    setIlluminaSampleRows([]);
    setUploadedOntFileObjects({});
    setUploadedIlluminaFileObjects({});
    setUploadOntFastq([]);
    setUploadIlluminaFastq([]);
    setUploadOntError(null);
    setUploadIlluminaError(null);
    setSampleSearch("");
    setSortConfig({ key: "sample_id", dir: "asc" });
    setConfirmRemoveIdx(null);
    setOntConfirmFiles(null);
    setOntConfirmSelected(new Set());
    // Run / processing / results context — start fresh
    setIsNewRun(true);
    setSelectedRun(null);
    setSubmitError(null);
    setSubmitSuccess(null);
    setSubmitProcessId(null);
    setSubmitting(false);
    setAssembled(false);
    setCancelRun(false);
    setShowDAG(false);
    setPipelineDAG(null);
    setPipelinePolling(false);
    clearActiveRun();
  }, []);

  // Refresh the inputs when signaled from outside (e.g. the Home "New Run" card).
  useEffect(() => {
    if (newRunSignal) resetInputs();
  }, [newRunSignal, resetInputs]);

  const openExportRunModal = useCallback(async () => {
    setExportRunModal(true);
    setExportRunLoading(true);
    setExportRunError(null);
    setExportSelectedRun(null);
    setExportRunSearch("");
    try {      
      const res = await fetch(`${API.listRuns}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to fetch runs");
      // Only completed runs have reports available to export
      setAvailableRuns((data.run_info ?? []).filter((r) => r.assembly_status === "COMPLETED"));
    } catch (err) {
      if (err.name !== "AbortError") setExportRunError(err.message);
    } finally {
      setExportRunLoading(false);
    }
  }, []);

  const handleExportDownload = useCallback(() => {
    if (!exportSelectedRun) return;
    setExportDownloading(true);
    const a = document.createElement("a");
    a.href = `${API.downloadMiraReports}?run_name=${encodeURIComponent(exportSelectedRun.run_name)}&experiment_type=${encodeURIComponent(exportSelectedRun.experiment_type)}`;
    a.download = `${exportSelectedRun.run_name}_mira_reports.zip`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => setExportDownloading(false), 2000);
  }, [exportSelectedRun]);

  // Fetch a custom config file and either surface the API error inline or trigger the browser download —
  // avoids navigating the page (or opening a blank tab) to a raw 404 response.
  const downloadCustomConfigFile = useCallback(async (url, filename, field) => {
    setCustomConfigDownloadError(null);
    try {
      const res = await fetch(url);
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setCustomConfigDownloadError({ field, message: data.detail || `Failed to download file (HTTP ${res.status})` });
        return;
      }
      const blob = await res.blob();
      const blobUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = blobUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(blobUrl);
    } catch (err) {
      setCustomConfigDownloadError({ field, message: err.message || "Failed to download file." });
    }
  }, []);

  const openEditRunModal = useCallback(async () => {
    setEditRunModal(true);
    setEditRunLoading(true);
    setEditRunError(null);
    setEditSelectedRun(null);
    setEditRunSearch("");
    setEditMode(null);
    setEditNewName("");
    setEditActionError(null);
    try {
      const res = await fetch(`${API.listRuns}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to fetch runs");
      setAvailableRuns(data.run_info ?? []);
    } catch (err) {
      if (err.name !== "AbortError") setEditRunError(err.message);
    } finally {
      setEditRunLoading(false);
    }
  }, []);

  const closeEditRunModal = useCallback(() => {
    setEditRunModal(false);
    setEditSelectedRun(null);
    setEditMode(null);
    setEditNewName("");
    setEditActionError(null);
  }, []);

  // selects a run and its action in one click, so the rename/copy/delete form shows immediately
  const selectRunForEdit = useCallback((run, mode) => {
    setEditSelectedRun(run);
    setEditMode(mode);
    setEditNewName(mode === "copy" ? `${run.run_name}_copy` : run.run_name);
    setEditActionError(null);
  }, []);

  const handleRenameRun = useCallback(async () => {
    if (!editSelectedRun) return;
    const trimmed = editNewName.trim().replace(/\s+/g, "_");
    if (!trimmed) { setEditActionError("Please enter a new run name."); return; }
    setEditActionLoading(true);
    setEditActionError(null);
    try {
      const res = await fetch(API.renameRun, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          run_name: editSelectedRun.run_name,
          experiment_type: editSelectedRun.experiment_type,
          new_run_name: trimmed,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to rename run");
      // Keep the currently loaded run's session state in sync if it's the one being renamed
      if (selectedRun?.assembly_id === editSelectedRun.assembly_id) {
        setRunName(trimmed);
        setSelectedRun((prev) => prev && ({ ...prev, run_name: trimmed }));
      }
      setAvailableRuns((prev) => prev.map((r) => r.assembly_id === editSelectedRun.assembly_id ? { ...r, run_name: trimmed } : r));
      setEditSelectedRun(null);
      setEditMode(null);
      setEditNewName("");
    } catch (err) {
      setEditActionError(err.message);
    } finally {
      setEditActionLoading(false);
    }
  }, [editSelectedRun, editNewName, selectedRun]);

  const handleCopyRun = useCallback(async () => {
    if (!editSelectedRun) return;
    const trimmed = editNewName.trim().replace(/\s+/g, "_");
    if (!trimmed) { setEditActionError("Please enter a name for the copy."); return; }
    setEditActionLoading(true);
    setEditActionError(null);
    try {
      const res = await fetch(API.copyRun, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          run_name: editSelectedRun.run_name,
          experiment_type: editSelectedRun.experiment_type,
          new_run_name: trimmed,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to copy run");

      // Refresh the run list so the new copy shows up
      const listRes = await fetch(`${API.listRuns}`);
      const listData = await listRes.json();
      if (listRes.ok) setAvailableRuns(listData.run_info ?? []);

      setEditMode(null);
      setEditNewName("");
      setEditSelectedRun(null);
    } catch (err) {
      setEditActionError(err.message);
    } finally {
      setEditActionLoading(false);
    }
  }, [editSelectedRun, editNewName]);

  const handleDeleteRun = useCallback(async () => {
    if (!editSelectedRun) return;
    setEditActionLoading(true);
    setEditActionError(null);
    try {
      const res = await fetch(API.deleteRun, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          run_name: editSelectedRun.run_name,
          experiment_type: editSelectedRun.experiment_type,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to delete run");

      // If the currently loaded run was deleted, reset the active session
      if (selectedRun?.assembly_id === editSelectedRun.assembly_id) {
        resetRun();
      }
      setAvailableRuns((prev) => prev.filter((r) => r.assembly_id !== editSelectedRun.assembly_id));
      setEditMode(null);
      setEditSelectedRun(null);
    } catch (err) {
      setEditActionError(err.message);
    } finally {
      setEditActionLoading(false);
    }
  }, [editSelectedRun, selectedRun, resetRun]);

  // Load a selected run from the backend API and populate the form with its data
  const handleLoadRun = useCallback(async (runOverride) => {
    const run = runOverride ?? loadRunSelectedRow;
    if (!run) return;
    setLoadRunLoading(true);
    setLoadRunError(null);
    try {

      // Cancel any ongoing run if submitProcessId exists
      if (submitProcessId && selectedRun) {
        fetch(`${API.miraCancel}?run_name=${encodeURIComponent(selectedRun.run_name)}&experiment_type=${encodeURIComponent(selectedRun.experiment_type)}&pid=${submitProcessId}`)
          .catch(() => {});
      }

      // Fetch run info and samplesheet from backend API
      const res = await fetch(
        `${API.retrieveRun}?run_name=${encodeURIComponent(run.run_name)}&experiment_type=${encodeURIComponent(run.experiment_type)}`
      );
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to load run");

      // run_info comes back as a list; take the first row
      const info = Array.isArray(data.run_info) ? data.run_info[0] : data.run_info;
      if (!info) throw new Error("Run data not found.");
      setRunName(info.run_name ?? "");
      setExperimentType(info.experiment_type ?? "");
      setPrimer(info.sc2_primer || info.rsv_primer || "");
      setCustomPrimers(info.custom_primers ? CUSTOM_PRIMER_CONFIG_FILENAME : "");
      setUseCustomPrimers(false);
      setLoadedCustomPrimersName(info.custom_primers ? CUSTOM_PRIMER_CONFIG_FILENAME : "");
      setPrimerKmerLen(info.primer_kmer_len ? String(info.primer_kmer_len) : "");
      setPrimerRestrictWindow(info.primer_restrict_window ? String(info.primer_restrict_window) : "");
      setSubSample(String(info.subsample_reads ?? 0));
      setIrmaModule(info.irma_module || "");
      setCreateParquet(info.parquet_files ?? false);
      setNextclade(info.nextclade ?? true);
      setKeepWorkdir(info.keep_workdir ?? false);
      const isOnt = (info.experiment_type ?? "").toLowerCase().endsWith("ont");
      const rows = Array.isArray(data.samplesheet) ? data.samplesheet : [];
      if (isOnt) {
        // DB stores one row per fastq; collapse to one row per sample with a fastq list
        const groups = new Map();
        rows.forEach(r => {
          const key = `${r.barcode ?? ""}||${r.sample_id ?? ""}`;
          if (!groups.has(key)) {
            groups.set(key, {
              barcode:     r.barcode    ?? "",
              sample_id:   r.sample_id  ?? "",
              sample_type: r.sample_type ?? "Test",
              single_end:  r.single_end ? "true" : "false",
              fastq:       [],
              status:      (r.status ?? "Keep").toLowerCase() === "keep" ? "Keep" : "Exclude",
            });
          }
          if (r.fastq) groups.get(key).fastq.push(r.fastq);
        });
        setOntSampleRows([...groups.values()].map(g => ({ ...g, fastq: [...g.fastq].sort((a, b) => a.localeCompare(b)) })));
        setIlluminaSampleRows([]);
      } else {
        setIlluminaSampleRows(rows.map(r => ({
          sample_id:   r.sample_id  ?? "",
          sample_type: r.sample_type ?? "Test",
          single_end:  r.fastq_1 && r.fastq_2 ? "false" : "true",
          fastq_1:     r.fastq_1    ?? "",
          fastq_2:     r.fastq_2    ?? "",
          status:      (r.status ?? "Keep").toLowerCase() === "keep" ? "Keep" : "Exclude",
        })));
        setOntSampleRows([]);
      }

      // Reset the uploaded/selected file objects, since we are loading an existing run and
      // don't have the actual File objects for its already-stored custom config files —
      // stale File objects left over from a prior "New Run" session must not leak into a
      // "Re-run" submission and silently overwrite this run's stored files.
      setUploadedOntFileObjects({});
      setUploadedIlluminaFileObjects({});
      setCustomPrimersFile(null);
      setCustomConfigDownloadError(null);
      setPrimersFileError(null);

      // This run is now the page's actively loaded/polled run — set it here rather than
      // relying on the modal's row-selection state, which resets whenever the modal reopens
      setSelectedRun(run);

      // Clear any results/DAG left over from a previously loaded or submitted run so stale
      // data doesn't flash before this run's own data is fetched
      setPipelineDAG(null);
      setResultBarcodeAssignments(null);
      setResultQcStatement(null);
      setResultQcDecisions(null);
      setResultCoverageHeatmap(null);
      setResultMiraSummary(null);
      setMiraSummaryPage(0);
      setResultSampleCoverageList(null);
      setSelectedSampleForCoverage("");
      setResultSampleCoverageSankey(null);
      setResultSampleCoveragePlot(null);
      setResultSampleCoverageLinear(null);
      setFocusedCovSegment(null);
      setResultVariants(null);
      setVariantsPage(0);
      setResultMinorSnvs(null);
      setMinorSnvsPage(0);
      setResultIndels(null);
      setIndelsPage(0);
      setResultNtPassedFasta(null);
      setResultNtFailedFasta(null);
      setResultAaPassedFasta(null);
      setResultAaFailedFasta(null);
      setResultNextcladeFasta(null);

      // Update state to reflect loaded run
      setSubmitSuccess(null);
      setSubmitError(null);
      setIsNewRun(false);
      setSubmitProcessId(null);

      // A run still actively PROCESSING has no results yet and must keep polling live;
      // any other status (COMPLETED/FAILED/CANCELED/SUBMITTED) is treated as done so its
      // existing results are fetched in a single pass instead of polling indefinitely.
      const isActive = (info.assembly_status ?? run.assembly_status) === "PROCESSING";
      setAssembled(!isActive);
      setCancelRun(!isActive);

      // Start polling the pipeline status and show the DAG view
      setPipelinePolling(true);
      setShowDAG(true);

      // Keep the Past Runs panel open — it only closes via the pill toggle or its X.

    } catch (err) {
      setLoadRunError(err.message);
    } finally {
      setLoadRunLoading(false);
    }
  }, [loadRunSelectedRow]);

  // ── Resume an in-flight run after a browser reload/reopen ──
  // The backend process keeps running independently of the browser, so if a run was still
  // processing when the app was last closed, reload its context and resume live polling.
  useEffect(() => {
    const active = readActiveRun();
    if (!active?.run_name || !active?.experiment_type) return;
    (async () => {
      try {
        const statusRes = await fetch(`${API.miraStatus}?run_name=${encodeURIComponent(active.run_name)}&experiment_type=${encodeURIComponent(active.experiment_type)}&pid=${active.pid ?? -1}`);
        const statusData = await statusRes.json().catch(() => ({}));
        if (statusRes.ok && statusData?.status === "PROCESSING") {
          // Repopulate the form/DAG for this run, then restore the PID so the Cancel Run
          // button reappears and status polling can reach the still-running process.
          await handleLoadRun({ run_name: active.run_name, experiment_type: active.experiment_type, assembly_status: "PROCESSING" });
          setSubmitProcessId(active.pid);
          setSubmitting(true);
        } else {
          // Run already finished while the browser was closed — nothing to resume.
          clearActiveRun();
        }
      } catch { /* backend unreachable — leave the marker so a later reload can retry */ }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Submit assembly to backend API ─────────────
  const submitAssembly = useCallback(async () => {

    // Clear any prior submission errors
    setCustomConfigDownloadError(null);

    // Trim leading/trailing whitespace from run nam
    if (!runName) {
      setSubmitError({ title: "Assembly Error", items: ["Run Name is required."], missing: null });
      return;
    }

    // Validate experiment type
    if (!experimentType) {
      setSubmitError({ title: "Assembly Error", items: ["Experiment Type is required."], missing: null });
      return;
    }

    // Validate primer selection for SC2 experiments
    if (experimentType.includes("SC2") && experimentType.includes("Illumina") && !primer) {
      setSubmitError({ title: "Assembly Error", items: ["SC2 experiments require a primer selection."], missing: null });
      return;
    }

    // Validate primer selection for RSV experiments
    if (experimentType.includes("RSV") && experimentType.includes("Illumina") && !primer) {
      setSubmitError({ title: "Assembly Error", items: ["RSV experiments require a primer selection."], missing: null });
      return;
    }

    // Validate subsample value
    if (!subSample || isNaN(parseInt(subSample)) || parseInt(subSample) < 0) {
      setSubmitError({ title: "Assembly Error", items: ["Subsample must be a non-negative integer."], missing: null });
      return;
    }

    // Custom Primers requires a file path, primer_kmer_len, and primer_restrict_window to also be set
    if (useCustomPrimers) {
      if (isNewRun === true && assembled === false && !customPrimers) {
        setSubmitError({ title: "Assembly Error", items: ["Please provide your custom primer FASTA file or turn off Custom Primers."], missing: null });
        return;
      }
      if (isNewRun === true && assembled === false && !/\.fasta$/i.test(customPrimers)) {
        setSubmitError({ title: "Assembly Error", items: ["Custom Primers file must be a FASTA file (.fasta)."], missing: null });
        return;
      }
      if (!primerKmerLen || isNaN(parseInt(primerKmerLen)) || parseInt(primerKmerLen) < 0) {
        setSubmitError({ title: "Assembly Error", items: ["primer_kmer_len is required and must be a non-negative integer when Custom Primers is used."], missing: null });
        return;
      }
      if (!primerRestrictWindow || isNaN(parseInt(primerRestrictWindow)) || parseInt(primerRestrictWindow) < 0) {
        setSubmitError({ title: "Assembly Error", items: ["primer_restrict_window is required and must be a non-negative integer when Custom Primers is used."], missing: null });
        return;
      }
    }

    // Make sure at least one sample exists and with "Keep" status in the samplesheet
    const isOnt = experimentType.toLowerCase().endsWith("ont");
    const samplesheet = (isOnt ? ontSampleRows : illuminaSampleRows)
    
    // Filter out samples with empty sample_id or fastq fields
    if (samplesheet.length == 0) {
      setSubmitError({ title: "Assembly Error", items: ["Sample sheet cannot be empty — please upload a list of FASTQ files to auto-populate the samplesheet"], missing: null });
      return;
    } else if (samplesheet.filter(r => r.status === "Keep").length === 0) {
      setSubmitError({ title: "Assembly Error", items: ["Please mark at least one sample as 'Keep' in the sample sheet to start the assembly."], missing: null });
      return;
    }

    // Validate Illumina samples: must have both fastq_1 and fastq_2 and single_end must be "false"
    if (!isOnt) {
      const badRows = samplesheet.filter(r => !r.fastq_1 || !r.fastq_2 || r.single_end !== "false");
      if (badRows.length > 0) {
        const ids = badRows.map(r => r.sample_id).join(", ");
        const missingR1 = badRows.filter(r => !r.fastq_1).map(r => `${r.sample_id}: missing fastq_1`);
        const missingR2 = badRows.filter(r => !r.fastq_2).map(r => `${r.sample_id}: missing fastq_2`);
        setSubmitError({ title: "Validation Error", items: [`Illumina samples require both fastq_1 and fastq_2 (paired-end).`, "Please upload the missing FASTQ files."], missing: { title: "Missing Samples", samples: [...missingR1, ...missingR2] } });
        return;
      }
    }else{
      const badRows = samplesheet.filter(r => !r.fastq || r.fastq.length === 0 || r.single_end !== "true");
      if (badRows.length > 0) {
        const missingFastq = badRows.map(r => `${r.sample_id}: missing fastq`);
        setSubmitError({ title: "Validation Error", items: [`ONT samples require a single-end fastq file.`], missing: { title: "Missing Samples", samples: missingFastq } });
        return;
      }
    }

    // Construct the samplesheet for submission. ONT rows are one-per-sample with a
    // fastq list in the UI; expand them back to the backend's one-row-per-fastq format.
    const formattedSamplesheet = isOnt
      ? samplesheet.flatMap(r => (Array.isArray(r.fastq) ? r.fastq : [r.fastq]).map(fq => ({
          barcode:       r.barcode,
          sample_id:     r.sample_id,
          sample_type:   r.sample_type,
          single_end:    r.single_end,
          fastq:         fq,
          status:        r.status,
        })))
      : samplesheet.map(r => ({
          sample_id:     r.sample_id,
          sample_type:   r.sample_type,
          single_end:    r.single_end,
          fastq_1:       r.fastq_1,
          fastq_2:       r.fastq_2,
          status:        r.status,
        }));

    // Construct the request body for the API
    const body = {
      run_name:               runName,
      experiment_type:        experimentType,
      sc2_primer:             experimentType.includes("SC2") ? (primer || "") : "",
      rsv_primer:             experimentType.includes("RSV") ? (primer || "") : "",
      subsample_reads:        parseInt(subSample) || 0,
      custom_primers:         useCustomPrimers,
      primer_kmer_len:        useCustomPrimers && primerKmerLen ? (parseInt(primerKmerLen) || 0) : 0,
      primer_restrict_window: useCustomPrimers && primerRestrictWindow ? (parseInt(primerRestrictWindow) || 0) : 0,
      irma_module:            experimentType === "Flu-Illumina" ? irmaModule : "",
      parquet_files:          createParquet,
      nextclade:              nextclade,
      keep_workdir:           keepWorkdir,
      samplesheet:            formattedSamplesheet,
      assembly_status:        "SUBMITTED",
    };

    // Run the submission in a try/catch block to handle errors
    try {

      // Reflect the in-flight submission in the UI immediately, rather than waiting
      // for all the sequential API calls below to finish.
      setSubmitting(true);

      // Check if the run name already exists in the database (for new runs only)
      if (isNewRun === true && assembled === false) {
        const checkRes = await fetch(`${API.retrieveRun}?run_name=${encodeURIComponent(runName)}&experiment_type=${encodeURIComponent(experimentType)}`);
        const checkData = await checkRes.json();
        if (!checkRes.ok) throw new Error(checkData.detail || "Failed to check run name");
        const duplicate = Array.isArray(checkData.run_info) && checkData.run_info.find(r => r.run_name === runName);
        if (duplicate) {
          setSubmitError({ title: "Assembly Error", items: [`Run name "${runName}" already exists. Please enter a different name or use "Load Run" on the right menu to reload it.`], missing: null });
          setSubmitting(false);
          return;
        }
      }

      // ── Step 1: register the run in the database ──
      const res = await fetch(API.createRun, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail));
      
      // Set the run as not new, since we are submitting it now
      setIsNewRun(false);

      // ── Step 2.1: upload FASTQ files the user provided via the file picker ──
      const filesToUpload = samplesheet.flatMap(r => {
        if (isOnt) {
          return (Array.isArray(r.fastq) ? r.fastq : [r.fastq])
            .map(fq => fq && uploadedOntFileObjects[fq])
            .filter(Boolean);
        } else {
          return [
            r.fastq_1 && uploadedIlluminaFileObjects[r.fastq_1],
            r.fastq_2 && uploadedIlluminaFileObjects[r.fastq_2],
          ].filter(Boolean);
        }
      });
      if (filesToUpload.length > 0) {
        const form = new FormData();
        form.append("run_name", runName);
        form.append("experiment_type", experimentType);
        filesToUpload.forEach(f => form.append("fastq_files", f));
        const upRes = await fetch(API.uploadFastqs, { method: "POST", body: form });
        if (!upRes.ok) {
          const upErr = await upRes.json().catch(() => ({}));
          throw new Error(upErr.detail || `File upload failed (HTTP ${upRes.status})`);
        }
      }

      // ── Step 2.2: Upload the custom primer file if a new file was selected ──
      if (useCustomPrimers && customPrimersFile) {
        const primerForm = new FormData();
        primerForm.append("run_name", runName);
        primerForm.append("experiment_type", experimentType);
        primerForm.append("custom_primer_config_file", customPrimersFile);
        const primerRes = await fetch(API.uploadCustomPrimerConfig, { method: "POST", body: primerForm });
        const primerData = await primerRes.json().catch(() => ({}));
        if (!primerRes.ok) throw new Error(primerData.detail || "Failed to upload custom primer config file");
      }

      // ── Step 3.1: Validate samplesheet and fastq files exist for each sample ──
      const valRes = await fetch(`${API.validateRun}?run_name=${encodeURIComponent(runName)}&experiment_type=${encodeURIComponent(experimentType)}`);
      const valData = await valRes.json();
      if (!valRes.ok) throw new Error(valData.detail || "Validation failed");
      if (valData.validation_status !== "passed") {
        const valItems = Array.isArray(valData.message) ? valData.message : [valData.message || valData.validation_status];
        setSubmitError({ title: "Validation Error", items: valItems, missing: valData.missing_fastq_files?.length ? { title: "Missing Samples", samples: valData.missing_fastq_files } : null });
        setSubmitting(false);
        return;
      }

      // ── Step 3.2: Validate custom primers file if provided ──
      const customValRes = await fetch(`${API.validateCustomConfigs}?run_name=${encodeURIComponent(runName)}&experiment_type=${encodeURIComponent(experimentType)}`);
      const customValData = await customValRes.json();
      if (!customValRes.ok) throw new Error(customValData.detail || "Custom configuration validation failed");
      if (customValData.validation_status !== "passed") {
        const customValItems = Array.isArray(customValData.message) ? customValData.message : [customValData.message || customValData.validation_status];
        setSubmitError({ title: "Custom Configuration Validation Error", items: customValItems, missing: customValData.missing_config_files?.length ? { title: "Missing Config Files", files: customValData.missing_config_files } : null });
        setSubmitting(false);
        return;
      }

      // ── Step 4: Run MIRA assembly ──
      const miraRes = await fetch(`${API.runMIRA}?run_name=${encodeURIComponent(runName)}&experiment_type=${encodeURIComponent(experimentType)}`);
      const miraData = await miraRes.json();
      if (!miraRes.ok) throw new Error(miraData.detail || "run Mira assembly failed");

      // Step 5: Start polling for pipeline status
      // Check if pid returned from the response is still running, if so, start polling for status
      if (miraData.pid) {

        // Update the selected run for the UI state
        setSelectedRun({
          run_name:         runName,
          experiment_type:  experimentType,
        });

        // Stage the submission status, error, and success messages
        setSubmitSuccess("Mira assembly launched successfully! You can monitor its progress in the 'Processing' step.");
        setSubmitError(null);

        // Clear previous results now that a new run has started
        setResultBarcodeAssignments(null);
        setResultQcStatement(null);
        setResultQcDecisions(null);
        setResultCoverageHeatmap(null);
        setResultMiraSummary(null);
        setMiraSummaryPage(0);
        setResultSampleCoverageList(null);
        setSelectedSampleForCoverage("");      
        setResultSampleCoverageSankey(null);
        setResultSampleCoveragePlot(null);
        setResultSampleCoverageLinear(null);
        setFocusedCovSegment(null);
        setResultVariants(null);      
        setVariantsPage(0);
        setResultMinorSnvs(null);
        setMinorSnvsPage(0);
        setResultIndels(null);
        setIndelsPage(0);
        setResultAaFailedFasta(null);
        setResultAaPassedFasta(null);
        setResultNtFailedFasta(null);
        setResultNtPassedFasta(null);      
        setResultNextcladeFasta(null);

        // Update the selected run for the UI state
        setSubmitProcessId(miraData.pid);
        setAssembled(false);
        setCancelRun(false);
        setShowDAG(true);
        setPipelinePolling(true);

        // Remember this run so it keeps processing (and stays cancellable) across browser reloads
        writeActiveRun({ pid: miraData.pid, run_name: runName, experiment_type: experimentType });

      } else {
        // No pid to poll — nothing further will clear the "Processing..." state, so reset it now.
        setSubmitting(false);
      }

    } catch (err) {
      setSubmitError({ title: "Assembly Error", items: [err.message], missing: null });
      setSubmitSuccess(null);
      setSubmitting(false);
    }

  }, [runName, experimentType, ontSampleRows, illuminaSampleRows, subSample, primer, customPrimers, useCustomPrimers, primerKmerLen, primerRestrictWindow, irmaModule, customPrimersFile, createParquet, nextclade, keepWorkdir, isNewRun, assembled]);

  // True once assembly finishes but every result field is still empty (nothing to display).
  const hasNoResults = [
    resultBarcodeAssignments,
    resultQcStatement,
    resultQcDecisions,
    resultCoverageHeatmap,
    resultMiraSummary,
    resultSampleCoverageList,
    resultVariants,
    resultIndels,
    resultMinorSnvs,
  ].every((result) => result === null);

  // Result sub-sections available for jump-to navigation under Step 3: Results (only shown once populated).
  const resultSections = [
    { id: "result-section-barcode",  label: "Barcode Assignment", show: resultBarcodeAssignments !== null },
    { id: "result-section-qc",       label: "QC Decisions",       show: resultQcDecisions !== null },
    { id: "result-section-summary",  label: "Mira Summary",       show: resultMiraSummary !== null },
    { id: "result-section-heatmap",  label: "Median Coverage Heatmap",   show: resultCoverageHeatmap !== null },
    { id: "result-section-coverage", label: "Sample Sankey & Coverage Plots",    show: resultSampleCoverageList !== null },
    { id: "result-section-variants", label: "AA Variants",        show: resultVariants !== null },
    { id: "result-section-snvs",     label: "Minor Variants",         show: resultMinorSnvs !== null },
    { id: "result-section-indels",   label: "Minor Indels & Deletions",             show: resultIndels !== null },
  ].filter(({ show }) => show);

  useLayoutEffect(() => {
    const navigation = stepNavRef.current;
    const naturalNavigation = stepNavMeasureRef.current;
    if (!navigation || !naturalNavigation) return undefined;

    const updateNavigationMode = () => {
      setStepNavCollapsed(naturalNavigation.offsetWidth > navigation.clientWidth);
    };
    updateNavigationMode();

    const observer = new ResizeObserver(updateNavigationMode);
    observer.observe(navigation);
    observer.observe(naturalNavigation);
    return () => observer.disconnect();
  }, []);

  const jumpToAssemblyStep = (id) => {
    setOpenStep(prev => { const next = new Set(prev); next.add(id); return next; });
    setStepMenuOpen(false);
    setTimeout(() => document.getElementById(`step-${id}`)?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
  };

  return (
    <div className="flex flex-col h-full overflow-hidden">

      {/* ── Jump To navigation band ───────────────── */}
      <div ref={stepNavRef} className="relative z-30 shrink-0 flex items-center gap-2 px-4 py-2 border-b border-border bg-muted/10">
        <button
          onClick={resetInputs}
          className="shrink-0 mr-auto flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold transition-colors border border-primary/30 text-primary bg-primary/5 hover:bg-primary/10"
        >
          <PlusCircle size={13} className="shrink-0" />
          <span className="whitespace-nowrap">New Run</span>
        </button>
        {stepNavCollapsed ? (
          <div ref={stepMenuRef} className="relative shrink-0">
            <button
              type="button"
              aria-haspopup="menu"
              aria-expanded={stepMenuOpen}
              onClick={() => setStepMenuOpen(open => !open)}
              className="flex items-center gap-1.5 px-3 py-1 rounded-full border border-border bg-background text-xs font-semibold text-foreground hover:border-primary/30 hover:text-primary transition-colors"
            >
              <span className="whitespace-nowrap">Assembly Steps</span>
              <ChevronDown size={13} className={cn("shrink-0 transition-transform", stepMenuOpen && "rotate-180")} />
            </button>
            {stepMenuOpen && (
              <div role="menu" className="absolute left-1/2 top-full z-50 mt-2 w-64 -translate-x-1/2 rounded-lg border border-border bg-popover p-1 shadow-xl">
                {ASSEMBLY_STEPS.map(({ id, title, icon: Icon }) => (
                  <button
                    key={id}
                    type="button"
                    role="menuitem"
                    onClick={() => jumpToAssemblyStep(id)}
                    className={cn(
                      "flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-xs transition-colors",
                      openStep.has(id)
                        ? "bg-primary/10 text-primary"
                        : "text-foreground hover:bg-muted"
                    )}
                  >
                    <Icon size={14} className="shrink-0 text-primary" />
                    <span>{title}</span>
                  </button>
                ))}
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => { setStepMenuOpen(false); onOpenSeqSender(); }}
                  className="flex w-full items-center gap-2 rounded-lg bg-primary px-3 py-2 text-left text-xs font-medium text-primary-foreground transition-colors hover:bg-primary/90"
                >
                  <Send size={14} className="shrink-0" />
                  <span>{SEQSENDER_ACTION.title}</span>
                </button>
              </div>
            )}
          </div>
        ) : ASSEMBLY_STEPS.map(({ id, title, icon: Icon }) => {
          const stepButton = (
            <button
              onClick={() => jumpToAssemblyStep(id)}
              className={cn(
                "shrink-0 flex items-center gap-1.5 px-3 py-1 rounded-full text-xs transition-colors border",
                openStep.has(id)
                  ? "text-primary border-primary/20 bg-primary/5"
                  : "text-foreground border-transparent hover:bg-muted/60 hover:border-border"
              )}
            >
              <Icon size={13} className="text-primary shrink-0" />
              <span className="whitespace-nowrap">{title}</span>
            </button>
          );

          if (id === "results" && assembled && !hasNoResults && resultSections.length > 0) {
            return (
              <ResultSectionsMenu
                key={id}
                sections={resultSections}
                onJump={(sectionId) => {
                  setOpenStep(prev => { const next = new Set(prev); next.add("results"); return next; });
                  setTimeout(() => document.getElementById(sectionId)?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
                }}
              >
                {stepButton}
              </ResultSectionsMenu>
            );
          }

          return <Fragment key={id}>{stepButton}</Fragment>;
        })}
        {!stepNavCollapsed && (
          <button
            type="button"
            onClick={onOpenSeqSender}
            className="shrink-0 flex items-center gap-1.5 px-3 py-1 rounded-full text-xs transition-colors border border-transparent text-foreground hover:bg-muted/60 hover:border-border"
          >
            <Send size={13} className="text-primary shrink-0" />
            <span className="whitespace-nowrap">{SEQSENDER_ACTION.title}</span>
          </button>
        )}
        <button
          onClick={() => loadRunModal ? setLoadRunModal(false) : openLoadRunModal()}
          className={cn(
            "shrink-0 ml-auto flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold transition-colors border",
            loadRunModal
              ? "border-primary/30 text-primary bg-primary/5 hover:bg-primary/10"
              : "border-border text-foreground hover:bg-muted/60 hover:border-primary/30 hover:text-primary"
          )}
        >
          <FolderOpen size={13} className="shrink-0" />
          <span className="whitespace-nowrap">Past Runs</span>
        </button>
      </div>

      <div
        ref={stepNavMeasureRef}
        aria-hidden="true"
        className="fixed -left-[10000px] top-0 invisible flex w-max items-center gap-2 px-4 py-2 pointer-events-none"
      >
        <span className="flex items-center gap-1.5 px-3 py-1 text-xs font-semibold"><PlusCircle size={13} />New Run</span>
        {ASSEMBLY_STEPS.map(({ id, title, icon: Icon }) => (
          <span key={id} className="flex items-center gap-1.5 px-3 py-1 text-xs"><Icon size={13} />{title}</span>
        ))}
        <span className="flex items-center gap-1.5 px-3 py-1 text-xs"><Send size={13} />{SEQSENDER_ACTION.title}</span>
        <span className="flex items-center gap-1.5 px-3 py-1 text-xs font-semibold"><FolderOpen size={13} />Past Runs</span>
      </div>

      {/* ── Main row: accordion + run panel ─────────── */}
      <div className="flex flex-1 overflow-hidden">

      {/* ── Left: accordion steps ─────────────────── */}
      <div className="relative min-w-0 flex-1 overflow-auto p-4" onScroll={handleContentScroll}>
        <div className="mx-auto flex w-full min-w-[min(500px,100%)] flex-col items-center gap-2">
          {ASSEMBLY_STEPS.map(({ id, title, subtitle, icon }) => (
            <div
              key={id}
              id={`step-${id}`}
              className={cn(
                "min-w-[500px] max-w-full rounded-xl border border-border overflow-hidden transition-all duration-300",
                openStep.has(id)
                  ? id === "results" ? "w-full" : "w-fit"
                  : "w-[min(500px,100%)]"
              )}
            >
              {/* ── Step Header ────────────────────────── */}
              <button
                onClick={() => toggle(id)}
                className="w-full px-4 py-3 bg-muted/20 hover:bg-muted/40 transition-colors"
              >
                <StepHeader
                  icon={id === "progress" && isNewRun === true && pipelinePolling === true && assembled === false && cancelRun === false
                    ? ({ size }) => <RefreshCw size={size} className="animate-spin" />
                    : icon
                  }
                  title={title}
                  subtitle={subtitle}
                  open={openStep.has(id)}
                />
              </button>
              {/* ── Step Panel Content ──────────────────── */}
              {openStep.has(id) && (
                <>
                  {/* ── Step 1: Setup ──────────────────── */}
                  {id === "setup" && (
                    <StepPanel>
                      <div className="flex items-center gap-2 pt-1">
                        <span className="text-xs font-bold tracking-wider text-muted-foreground uppercase">Run Information</span>
                        <div className="flex-1 h-px bg-border" />
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="w-[min(300px,100%)]">
                          <FieldLabel>Experiment Type <span className="text-destructive"></span></FieldLabel>
                          <select
                            value={experimentType}
                            onChange={(e) => {
                              const value = e.target.value;
                              setExperimentType(value);
                              setPrimer(value?.startsWith("SC2") && value?.endsWith("Illumina") ? SC2_PRIMERS[0].value : value?.startsWith("RSV") && value?.endsWith("Illumina") ? RSV_PRIMERS[0].value : "");
                              if (value !== "Flu-Illumina") { setIrmaModule(""); }
                              if (value) {
                                const today = new Date();
                                const yyyymmdd = `${today.getFullYear()}${String(today.getMonth() + 1).padStart(2, "0")}${String(today.getDate()).padStart(2, "0")}`;
                                setRunName(`${yyyymmdd}_${value}`.replace(/\s+/g, "_"));
                              }
                            }}
                            disabled={!isNewRun}
                            className="w-full h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-60 disabled:cursor-not-allowed disabled:bg-muted"
                          >
                            <option value="">— Select experiment type —</option>
                            {EXPERIMENT_TYPES.map((p) => <option key={p}>{p}</option>)}
                          </select>
                        </div>
                        <div className="w-[min(300px,100%)]">
                          <FieldLabel>Run Name<span className="text-destructive"></span></FieldLabel>
                          <input
                            value={runName}
                            onChange={(e) => setRunName(e.target.value.replace(/\s+/g, "_"))}
                            placeholder="e.g. YYYYMMDD_experiment-type"
                            disabled={!isNewRun}
                            className="w-full h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-60 disabled:cursor-not-allowed disabled:bg-muted"
                          />
                        </div>
                      </div>
                      {(experimentType?.startsWith("SC2") || experimentType?.startsWith("RSV")) && experimentType?.endsWith("Illumina") && (
                        <div className="w-[min(350px,100%)]">
                          <FieldLabel>Primers <span className="text-destructive">*</span></FieldLabel>
                          <p className="mb-2 text-xs text-muted-foreground">Select the appropriate primer for the chosen experiment type.</p>
                          <select
                            value={primer}
                            onChange={(e) => setPrimer(e.target.value)}
                            className="w-full h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                          >
                            {experimentType?.startsWith("SC2") && experimentType?.endsWith("Illumina") && SC2_PRIMERS.map(({ value, label }) => (
                              <option key={value} value={value}>{label}</option>
                            ))}
                            {experimentType?.startsWith("RSV") && experimentType?.endsWith("Illumina") && RSV_PRIMERS.map(({ value, label }) => (
                              <option key={value} value={value}>{label}</option>
                            ))}
                          </select>
                        </div>
                      )}

                      {/* ── Step 1.5: Upload FASTQ files ─────────────── */}
                      {runName && experimentType && (
                        <div>
                          <FieldLabel>Upload FASTQ Files</FieldLabel>
                          <div
                            onDragOver={(e) => { e.preventDefault(); setFastqDragOver(true); }}
                            onDragLeave={() => setFastqDragOver(false)}
                            onDrop={async (e) => {
                              e.preventDefault();
                              setFastqDragOver(false);
                              const files = await collectFilesFromDataTransfer(e.dataTransfer);
                              handleIncomingFastqFiles(files);
                            }}
                            className={cn(
                              "flex flex-col items-center justify-center px-2 gap-2 h-28 rounded-xl border-2 border-dashed bg-muted/10 transition-colors text-muted-foreground text-sm",
                              fastqDragOver ? "border-primary bg-primary/5" : "border-border"
                            )}
                          >
                            <Upload size={22} />
                            <span>Drag &amp; drop folder containing fastq files here</span>
                            <span className="text-xs opacity-60">*.fastq, *.fastq.gz, *.fq, &amp; *.fq.gz accepted — dropped folders are scanned recursively.</span>
                          </div>
                        </div>
                      )}

                      <div className="flex items-center gap-2 pt-1">
                        <span className="text-xs font-bold tracking-wider text-muted-foreground uppercase">Sample Sheet</span>
                        <div className="flex-1 h-px bg-border" />
                      </div>

                      {(!runName || !experimentType) && (
                        <div className="flex items-center gap-2 w-fit max-w-full text-xs text-warning bg-warning/10 rounded-lg px-3 py-2">
                          <AlertCircle size={13} className="shrink-0" /><span>Please provide a <strong className="mx-0.5">Run Name</strong> and select an <strong className="mx-0.5">Experiment Type</strong> above to continue.</span> 
                        </div>
                      )}

                      {runName && experimentType && (
                        <>
                          {(experimentType.toLowerCase().endsWith("ont") ? ontSampleRows : illuminaSampleRows).length === 0 && (
                          <div className="flex items-center gap-2 w-fit max-w-full text-xs text-warning bg-warning/10 rounded-lg px-3 py-2">
                            <AlertCircle size={13} /> Upload FASTQ files to auto-populate the sample sheet.
                          </div>
                          )}

                          {(experimentType.toLowerCase().endsWith("ont") ? uploadOntError : uploadIlluminaError) && (
                            <div className="rounded-lg border bg-red-50 border-red-200 dark:bg-red-950/20 dark:border-red-800 px-3 py-2 space-y-1 text-xs mb-2 max-h-[150px] overflow-y-auto">
                              <p className="font-semibold text-destructive mb-1">Upload Error:</p>
                              {(experimentType.toLowerCase().endsWith("ont") ? uploadOntError.items : uploadIlluminaError.items).map((msg, i) => (
                                <div key={i} className="flex items-start gap-2">
                                  <AlertCircle size={12} className="shrink-0 mt-0.5 text-destructive" />
                                  <span className="text-destructive font-mono">{msg}</span>
                                </div>
                              ))}
                              <p className="font-semibold text-destructive mb-1">Invalid Files:</p>
                              {(experimentType.toLowerCase().endsWith("ont") ? uploadOntError.missing : uploadIlluminaError.missing).map((msg, i) => (
                                <div key={i}>
                                  <div className="flex items-start gap-2">
                                    <AlertCircle size={12} className="shrink-0 mt-0.5 text-destructive" />
                                    <span className="text-destructive font-mono">{msg}</span>
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}

                          {(experimentType.toLowerCase().endsWith("ont") ? ontSampleRows : illuminaSampleRows).length > 0 && (
                            <div className="flex items-center gap-2">
                              <div className="flex gap-1.5 shrink-0">
                                <button
                                  onClick={() => exportSampleSheet("csv")}
                                  className="flex items-center gap-1 px-3 py-1 rounded-md border border-border text-xs text-muted-foreground hover:border-primary hover:text-primary transition-colors"
                                >
                                  <Download size={11} /> CSV
                                </button>
                                <button
                                  onClick={() => exportSampleSheet("excel")}
                                  className="flex items-center gap-1 px-3 py-1 rounded-md border border-border text-xs text-muted-foreground hover:border-primary hover:text-primary transition-colors"
                                >
                                  <Download size={11} /> Excel
                                </button>
                              </div>
                              <input
                                type="text"
                                value={sampleSearch}
                                onChange={(e) => setSampleSearch(e.target.value)}
                                placeholder="Search samples…"
                                className="flex-1 h-7 px-2 rounded-md border border-border bg-background text-xs font-mono focus:outline-none focus:ring-1 focus:ring-ring"
                              />
                            </div>
                          )}

                          <div className="rounded-xl border border-border overflow-hidden">
                            <div className="overflow-auto max-h-[300px]">
                            <table className={cn("w-full text-xs", Object.keys(sampleColWidths).length > 0 && "table-fixed")}>
                              <colgroup>
                                {(experimentType.toLowerCase().endsWith("ont")
                                  ? ["barcode", "sample_id", "sample_type", "single_end", "fastq", "status"]
                                  : ["sample_id", "sample_type", "single_end", "fastq_1", "fastq_2", "status"]
                                ).map((h) => (
                                  <col key={h} style={sampleColWidths[h] ? { width: sampleColWidths[h] } : undefined} />
                                ))}
                              </colgroup>
                              <thead className="bg-muted sticky top-0 z-10">
                                <tr>
                                  {(experimentType.toLowerCase().endsWith("ont")
                                    ? ["barcode", "sample_id", "sample_type", "single_end", "fastq", "status"]
                                    : ["sample_id", "sample_type", "single_end", "fastq_1", "fastq_2", "status"]
                                  ).map((h) => (
                                    <th
                                      key={h}
                                      className="relative px-3 py-2 text-left font-semibold text-muted-foreground font-mono select-none"
                                    >
                                      <span
                                        onClick={() => setSortConfig(prev => ({
                                          key: h,
                                          dir: prev.key === h && prev.dir === "asc" ? "desc" : "asc",
                                        }))}
                                        className="flex items-center gap-1 cursor-pointer hover:text-foreground transition-colors"
                                      >
                                        <span title={h} className={sampleColWidths[h] ? "truncate" : undefined}>{h}</span>
                                        {sortConfig.key === h ? (
                                          sortConfig.dir === "asc"
                                            ? <ArrowUp size={10} className="text-primary shrink-0" />
                                            : <ArrowDown size={10} className="text-primary shrink-0" />
                                        ) : (
                                          <ArrowUpDown size={10} className="opacity-30 shrink-0" />
                                        )}
                                      </span>
                                      {/* resize grip */}
                                      <span
                                        onMouseDown={(e) => startSampleColResize(h, e)}
                                        onClick={(e) => e.stopPropagation()}
                                        title="Drag to resize column"
                                        className="absolute top-0 right-0 h-full w-1.5 cursor-col-resize hover:bg-primary/40"
                                      />
                                    </th>
                                  ))}
                                </tr>
                              </thead>
                              <tbody>
                                {(() => {
                                  const isOnt = experimentType.toLowerCase().endsWith("ont");
                                  const activeRows = isOnt ? ontSampleRows : illuminaSampleRows;
                                  const q = sampleSearch.trim().toLowerCase();
                                  const filteredRows = q
                                    ? activeRows.filter(row => {
                                        const vals = isOnt
                                          ? [row.barcode, row.sample_id, row.sample_type, row.single_end, (Array.isArray(row.fastq) ? row.fastq.join(" ") : row.fastq), row.status]
                                          : [row.sample_id, row.sample_type, row.single_end, row.fastq_1, row.fastq_2, row.status];
                                        return vals.some(v => (v ?? "").toString().toLowerCase().includes(q));
                                      })
                                    : activeRows;
                                  const getVal = (row, k) => {
                                    if (isOnt && k === "fastq") return (Array.isArray(row.fastq) ? row.fastq.join(" ") : (row.fastq ?? "")).toLowerCase();
                                    return (row[k] ?? "").toString().toLowerCase();
                                  };
                                  const sortedRows = sortConfig.key
                                    ? [...filteredRows].sort((a, b) => {
                                        const va = getVal(a, sortConfig.key);
                                        const vb = getVal(b, sortConfig.key);
                                        if (va < vb) return sortConfig.dir === "asc" ? -1 : 1;
                                        if (va > vb) return sortConfig.dir === "asc" ? 1 : -1;
                                        return 0;
                                      })
                                    : filteredRows;
                                  if (sortedRows.length === 0) return (
                                    <tr className="border-t border-border">
                                      <td colSpan={6} className="px-3 py-4 text-left text-muted-foreground">
                                        {q ? "No samples match your search." : "No samples loaded — upload FASTQ files to populate."}
                                      </td>
                                    </tr>
                                  );
                                  return sortedRows.map((row) => {
                                    const idx = activeRows.indexOf(row);
                                    const colKeys = isOnt
                                      ? ["barcode", "sample_id", "sample_type", "single_end", "fastq"]
                                      : ["sample_id", "sample_type", "single_end", "fastq_1", "fastq_2"];
                                    const colVals = isOnt
                                      ? [row.barcode, row.sample_id, row.sample_type, row.single_end, row.fastq]
                                      : [row.sample_id, row.sample_type, row.single_end, row.fastq_1, row.fastq_2];
                                    return (
                                      <tr key={idx} className={cn("border-t border-border transition-colors", row.status === "Exclude" && "opacity-50 bg-muted/20")}>
                                        {colKeys.map((key, ci) => (
                                          <td key={ci} className="px-3 py-2 font-mono text-foreground">
                                            {key === "sample_type" ? (
                                              <select
                                                value={row.sample_type}
                                                onChange={(e) => {
                                                  const newType = e.target.value;
                                                  // ONT: a barcode can span multiple fastq rows — keep them all in sync
                                                  if (isOnt) {
                                                    setOntSampleRows((prev) => prev.map((r) => r.barcode === row.barcode ? { ...r, sample_type: newType } : r));
                                                  } else {
                                                    setIlluminaSampleRows((prev) => prev.map((r, i) => i === idx ? { ...r, sample_type: newType } : r));
                                                  }
                                                }}
                                                className="h-7 px-2 rounded border border-border bg-background text-xs font-mono focus:outline-none focus:ring-1 focus:ring-ring"
                                              >
                                                {SAMPLE_TYPES.map((opt) => <option key={opt}>{opt}</option>)}
                                              </select>
                                            ) : (
                                              key.startsWith("fastq") ? (
                                                isOnt ? (() => {
                                                  const fastqList = Array.isArray(colVals[ci]) ? colVals[ci] : (colVals[ci] ? [colVals[ci]] : []);
                                                  return <OntFastqCell fastqList={fastqList} uploadedMap={uploadedOntFileObjects} />;
                                                })() : (
                                                  <span className="flex items-center gap-1">
                                                    {colVals[ci] && uploadedIlluminaFileObjects[colVals[ci]] && (
                                                      <Upload size={10} className="text-emerald-500 shrink-0" title="Uploaded this session" />
                                                    )}
                                                    <span className="block overflow-x-auto whitespace-nowrap max-w-[300px] scrollbar-thin">{colVals[ci]}</span>
                                                  </span>
                                                )
                                              ) : (
                                                <span className="block overflow-x-auto whitespace-nowrap max-w-[300px] scrollbar-thin">{colVals[ci]}</span>
                                              )
                                            )}
                                          </td>
                                        ))}
                                        <td className="px-3 py-2">
                                          <div className="flex items-center gap-1.5">
                                            <button
                                              onClick={() => toggleSampleStatus(idx)}
                                              className={cn(
                                                "px-2 py-0.5 rounded-full text-xs font-semibold border transition-colors",
                                                row.status === "Keep"
                                                  ? "bg-emerald-100 text-emerald-700 border-emerald-200 hover:bg-red-50 hover:text-red-600 hover:border-red-200 dark:bg-emerald-900/10 dark:text-emerald-400 dark:border-emerald-800"
                                                  : "bg-red-100 text-red-700 border-red-200 hover:bg-emerald-50 hover:text-emerald-600 hover:border-emerald-200 dark:bg-red-900/10 dark:text-red-400 dark:border-red-800"
                                              )}
                                            >
                                              {row.status === "Keep" ? "Keep" : "Exclude"}
                                            </button>
                                            <button
                                              onClick={() => removeSample(idx)}
                                              title="Remove sample"
                                              className="p-1 rounded-md text-muted-foreground hover:text-destructive hover:bg-red-50 dark:hover:bg-red-950/20 transition-colors"
                                            >
                                              <Trash2 size={12} />
                                            </button>
                                          </div>
                                        </td>
                                      </tr>
                                    );
                                  });
                                })()}
                              </tbody>
                            </table>
                            </div>
                          </div>
                        </>
                      )}

                      <div className="flex items-center gap-2 pt-1">
                        <span className="text-xs font-bold tracking-wider text-muted-foreground uppercase">Assembly Parameters</span>
                        <div className="flex-1 h-px bg-border" />
                      </div>
                      
                      {/* Subsample Reads */}
                      <div className="w-[min(300px,100%)]">
                        <FieldLabel>
                          <span className="relative inline-flex items-center group">
                            <span className="cursor-help decoration-muted-foreground/50">Subsample Reads</span>
                            <BadgeQuestionMark size={13} className="text-muted-foreground cursor-help" />
                            <span
                              role="tooltip"
                              className="pointer-events-none absolute bottom-full left-0 z-50 mb-1.5 w-max max-w-xs rounded-md border border-border bg-popover px-2.5 py-1.5 text-xs font-normal text-popover-foreground shadow-lg opacity-0 translate-y-1 transition-all duration-150 group-hover:opacity-100 group-hover:translate-y-0"
                            >
                              The number of reads to randomly subsample to.<br /><code className="font-mono bg-muted px-1 rounded">0</code> <em>skips</em> subsampling.
                            </span>
                          </span>
                          {" "}
                          <span className="text-destructive"></span>
                        </FieldLabel>
                        <p className="text-xs text-muted-foreground mb-2 leading-relaxed">
                        </p>
                        <input
                          type="number"
                          value={subSample}
                          onChange={(e) => setSubSample(e.target.value)}
                          placeholder="e.g. 100"
                          min={0}
                          className="w-full h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                        />
                      </div>

                      {/* Run Nextclade toggle */}
                      <button
                        onClick={() => setNextclade((v) => !v)}
                        className="w-[min(300px,100%)] flex items-center justify-between gap-4 p-3 rounded-lg border border-border bg-muted/10 hover:bg-muted/20 transition-colors text-left"
                      >
                        <div className="flex items-center gap-1.5">
                          <p className="text-sm font-medium">Run Nextclade</p>
                          <span
                            role="link"
                            tabIndex={0}
                            title="Learn more about Nextclade"
                            onClick={(e) => { e.stopPropagation(); window.open("https://github.com/nextstrain/nextclade", "_blank", "noopener,noreferrer"); }}
                            className="text-muted-foreground hover:text-primary transition-colors cursor-pointer"
                          >
                            <ExternalLink size={13} />
                          </span>
                        </div>
                        <span className={cn(
                          "relative w-10 h-5 rounded-full transition-colors shrink-0 pointer-events-none",
                          nextclade ? "bg-primary" : "bg-muted"
                        )}>
                          <span className={cn("absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform", nextclade ? "translate-x-5" : "translate-x-0.5")} />
                        </span>
                      </button>
                      <button
                        onClick={() => setUseCustomPrimers((v) => !v)}
                        className="w-[min(300px,100%)] flex items-center justify-between gap-4 p-3 rounded-lg border border-border bg-muted/10 hover:bg-muted/20 transition-colors text-left"
                      >
                        <div>
                          <p className="text-sm font-medium">Custom Primers</p>
                        </div>
                        <span className={cn(
                          "relative w-10 h-5 rounded-full transition-colors shrink-0 pointer-events-none",
                          useCustomPrimers ? "bg-primary" : "bg-muted"
                        )}>
                          <span className={cn("absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform", useCustomPrimers ? "translate-x-5" : "translate-x-0.5")} />
                        </span>
                      </button>

                      {/* Custom Primers */}
                      {useCustomPrimers && (
                        <>
                          <div className="w-[min(300px,100%)]">
                            {!isNewRun && loadedCustomPrimersName && (
                              <div className="mb-2 text-md text-muted-foreground">
                                <p>
                                  Currently stored file:{" "}
                                  <button
                                    type="button"
                                    onClick={() => downloadCustomConfigFile(
                                      `${API.downloadCustomPrimerConfig}?run_name=${encodeURIComponent(selectedRun?.run_name ?? runName)}&experiment_type=${encodeURIComponent(selectedRun?.experiment_type ?? experimentType)}`,
                                      loadedCustomPrimersName,
                                      "primer"
                                    )}
                                    className="inline-flex items-center gap-1 font-mono text-primary hover:underline"
                                  >
                                    <Download size={11} className="shrink-0" />
                                    {loadedCustomPrimersName}
                                  </button>
                                </p>
                                {customConfigDownloadError?.field === "primer" && (
                                  <p className="mt-1 flex items-center gap-1 text-xs text-destructive">
                                    <AlertCircle size={11} className="shrink-0" /> {customConfigDownloadError.message}
                                  </p>
                                )}
                              </div>
                            )}                          
                            <FieldLabel>Custom Primer FASTA File <span className="text-destructive"></span></FieldLabel>
                            <div className="flex gap-2 max-w-md">
                              <input
                                type="text"
                                value={customPrimers}
                                onChange={(e) => setCustomPrimers(e.target.value)}
                                placeholder="e.g. custom_primers.fasta"
                                className="flex-1 h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                              />
                              <label className="flex items-center gap-1.5 px-3 h-9 rounded-md border border-border bg-muted/20 hover:bg-muted/40 cursor-pointer text-xs text-muted-foreground transition-colors shrink-0">
                                <FolderOpen size={13} /> Browse
                                <input
                                  type="file"
                                  className="hidden"
                                  accept=".fasta"
                                  onChange={(e) => {
                                    const f = e.target.files?.[0];
                                    if (f) {
                                      if (!/\.fasta$/i.test(f.name)) {
                                        setPrimersFileError("Custom Primers file must be a FASTA file (.fasta).");
                                      } else {
                                        setPrimersFileError(null);
                                        setCustomPrimers(f.name);
                                        setCustomPrimersFile(f);
                                        setCustomConfigDownloadError(null);
                                      }
                                    }
                                    e.target.value = "";
                                  }}
                                />
                              </label>
                            </div>
                            {primersFileError && (
                              <p className="mt-1 flex items-center gap-1 text-xs text-destructive">
                                <AlertCircle size={11} className="shrink-0" /> {primersFileError}
                              </p>
                            )}
                          </div>
                          
                          {/* K-mer length and Restrict Window */}
                          <div className="w-[min(300px,100%)] grid grid-cols-2 gap-3">
                            <div>
                              <FieldLabel>
                                <span className="inline-flex items-center gap-1.5">
                                  K-mer length to decompose primers into:
                                  <a
                                    href="https://github.com/CDCgov/MIRA-NF#:~:text=with%20this%20flag-,primer_kmer_len,-When%20primer_kmer_len%20is"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    title="Learn more about primer_kmer_len"
                                    className="text-muted-foreground hover:text-primary transition-colors"
                                  >
                                    <ExternalLink size={13} />
                                  </a>
                                </span>
                                <span className="text-destructive"></span>
                              </FieldLabel>
                              <input
                                type="number"
                                value={primerKmerLen}
                                onChange={(e) => setPrimerKmerLen(e.target.value)}
                                placeholder="∀ p ∈ primer.fasta : |p|"
                                min={0}
                                className="w-[min(200px,100%)] h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                              />
                            </div>
                            <div>
                              <FieldLabel>
                                <span className="inline-flex items-center gap-1.5">
                                  Number of bases from read end to search for primer k-mers
                                  <a
                                    href="https://github.com/CDCgov/MIRA-NF#:~:text=reads)%20is%20performed.-,primer_restrict_window,-The%20N%20number"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    title="Learn more about primer_restrict_window"
                                    className="text-muted-foreground hover:text-primary transition-colors"
                                  >
                                    <ExternalLink size={13} />
                                  </a>
                                </span>
                                <span className="text-destructive"></span>
                              </FieldLabel>
                              <input
                                type="number"
                                value={primerRestrictWindow}
                                onChange={(e) => setPrimerRestrictWindow(e.target.value)}
                                placeholder="∀ p ∈ primer.fasta : |p|"
                                min={0}
                                className="w-[min(200px,100%)] h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                              />
                            </div>
                          </div>
                        </>
                      )}

                      {/* IRMA module selection for Flu-Illumina experiments */}
                      {experimentType === "Flu-Illumina" && (
                        <div className="w-[min(300px,100%)]">
                          <FieldLabel>
                            <span className="inline-flex items-center gap-1.5">
                              IRMA module
                              <a
                                href="https://wonder.cdc.gov/amd/flu/irma/modules.html"
                                target="_blank"
                                rel="noopener noreferrer"
                                title="Learn more about IRMA modules"
                                className="text-muted-foreground hover:text-primary transition-colors"
                              >
                                <ExternalLink size={13} />
                              </a>
                            </span>
                          </FieldLabel>
                          <select
                            value={irmaModule}
                            onChange={(e) => setIrmaModule(e.target.value)}
                            className="w-full h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                          >
                            <option value="">FLU (default)</option>
                            <option value="secondary">secondary</option>
                            <option value="sensitive">sensitive</option>
                            <option value="utr">utr</option>
                          </select>
                        </div>
                      )}

                      {/* Output Parquet toggle */}
                      <button
                        onClick={() => setCreateParquet((v) => !v)}
                        className="w-[min(300px,100%)] flex items-center justify-between gap-4 p-3 rounded-lg border border-border bg-muted/10 hover:bg-muted/20 transition-colors text-left"
                      >
                        <div className="flex items-center gap-1.5">
                          <p className="text-sm font-medium">Output Parquet</p>
                          <span className="relative inline-flex items-center group">
                              <BadgeQuestionMark size={13} className="text-muted-foreground cursor-help" />
                              <span
                                role="tooltip"
                                className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 z-50 mb-1.5 w-max max-w-xs rounded-md border border-border bg-popover px-2.5 py-1.5 text-xs font-normal text-popover-foreground shadow-lg opacity-0 translate-y-1 transition-all duration-150 group-hover:opacity-100 group-hover:translate-y-0"
                              >
                                Parquet is a columnar storage file format that is optimized for use with large datasets.<br></br><br></br>
                                It is read by database engines like Apache Hive and Apache Impala.<br></br><br></br>
                                It is not commonly used by laboratories.
                              </span>
                            </span>
                          <span
                            role="link"
                            tabIndex={0}
                            title="Learn more about Apache Parquet"
                            onClick={(e) => { e.stopPropagation(); window.open("https://parquet.apache.org/", "_blank", "noopener,noreferrer"); }}
                            className="text-muted-foreground hover:text-primary transition-colors cursor-pointer"
                          >
                            <ExternalLink size={13} />
                          </span>
                        </div>
                        <span className={cn(
                          "relative w-10 h-5 rounded-full transition-colors shrink-0 pointer-events-none",
                          createParquet ? "bg-primary" : "bg-muted"
                        )}>
                          <span className={cn("absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform", createParquet ? "translate-x-5" : "translate-x-0.5")} />
                        </span>
                      </button>
                      
                      {/* Preserve Work Directory toggle */}
                      <button
                        onClick={() => setKeepWorkdir((v) => !v)}
                        className="w-[min(300px,100%)] flex items-center justify-between gap-4 p-3 rounded-lg border border-border bg-muted/10 hover:bg-muted/20 transition-colors text-left"
                      >
                        <div>
                          <div className="flex items-center gap-1.5">
                            <p className="text-sm font-medium">Preserve Work Directory</p>
                            <span className="relative inline-flex items-center group">
                              <BadgeQuestionMark size={13} className="text-muted-foreground cursor-help" />
                              <span
                                role="tooltip"
                                className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 z-50 mb-1.5 w-max max-w-xs rounded-md border border-border bg-popover px-2.5 py-1.5 text-xs font-normal text-popover-foreground shadow-lg opacity-0 translate-y-1 transition-all duration-150 group-hover:opacity-100 group-hover:translate-y-0"
                              >
                                This will greatly increase disc space used and is not recommended for routine use.
                              </span>
                            </span>
                          </div>
                          <p className="text-xs text-muted-foreground mt-0.5">Keep all intermediate processing data</p>
                        </div>
                        <span className={cn(
                          "relative w-10 h-5 rounded-full transition-colors shrink-0 pointer-events-none",
                          keepWorkdir ? "bg-primary" : "bg-muted"
                        )}>
                          <span className={cn("absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform", keepWorkdir ? "translate-x-5" : "translate-x-0.5")} />
                        </span>
                      </button>

                      {submitSuccess && submitError === null && (
                        <div className="flex items-start gap-2 text-xs text-emerald-700 bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-800 rounded-lg px-3 py-2">
                          <Check size={13} className="shrink-0 mt-0.5" /> {submitSuccess}
                        </div>
                      )}

                      {submitError && (
                        <div className="rounded-lg border bg-red-50 border-red-200 dark:bg-red-950/20 dark:border-red-800 px-3 py-2 space-y-1.5 text-xs">
                          {submitError.title && submitError.title.length > 0 && (
                            <p className="font-semibold text-destructive mb-1">{submitError.title}</p>
                          )}
                          {Array.isArray(submitError.items) && submitError.items.map((msg, i) => (
                            <div key={i} className="flex items-start gap-2">
                              <AlertCircle size={12} className="shrink-0 mt-0.5 text-destructive" />
                              <span className="text-destructive">{msg}</span>
                            </div>
                          ))}
                          {Array.isArray(submitError.missing?.samples) && submitError.missing.samples.length > 0 && (
                            <div className="mt-2 pt-2 border-t border-red-200 dark:border-red-800 space-y-1">
                              <p className="font-semibold text-destructive">{submitError.missing.title}</p>
                              {submitError.missing.samples.map((msg, i) => (
                                <div key={i} className="flex items-start gap-2">
                                  <AlertCircle size={11} className="shrink-0 mt-0.5 text-destructive" />
                                  <span className="text-destructive">
                                    <span className="font-mono font-semibold">{msg}</span>
                                  </span>
                                </div>
                              ))}
                            </div>
                          )}
                          {Array.isArray(submitError.missing?.files) && submitError.missing.files.length > 0 && (
                            <div className="mt-2 pt-2 border-t border-red-200 dark:border-red-800 space-y-1">
                              <p className="font-semibold text-destructive">{submitError.missing.title}</p>
                              {submitError.missing.files.map((entry, i) => (
                                <div key={i} className="flex items-start gap-2">
                                  <AlertCircle size={11} className="shrink-0 mt-0.5 text-destructive" />
                                  <span className="text-destructive">
                                    <span className="font-mono font-semibold">{Object.values(entry)[0]}</span>
                                  </span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                      
                      <div className="flex items-center gap-2">
                        <button
                          disabled={submitting}
                          onClick={async () => {
                            if (submitLockRef.current) return;
                            submitLockRef.current = true;
                            try {
                              await submitAssembly();
                            } finally {
                              submitLockRef.current = false;
                            }
                          }}
                          className="flex items-center gap-2 px-5 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          {submitting ? <RefreshCw size={14} className="animate-spin" /> : <Play size={14} />}
                          {submitting ? "Processing..." : isNewRun ? "Run Genome Assembly" : "Re-run Genome Assembly"}
                        </button>
                        {submitProcessId && pipelinePolling && (
                          <button
                            onClick={async () => {
                              try {
                                const statusRes = await fetch(`${API.miraCancel}?run_name=${encodeURIComponent(selectedRun.run_name)}&experiment_type=${encodeURIComponent(selectedRun.experiment_type)}&pid=${submitProcessId}`);
                                const data = await statusRes.json();
                                if (!statusRes.ok) throw new Error(data.detail || "Failed to cancel Mira run");
                                setCancelRun(true);
                                setSubmitting(false);
                                clearActiveRun();
                                setSubmitError({
                                  title: "Canceled Status",
                                  items: Array.isArray(data.message) ? data.message : [data.message || "Mira run was canceled or interrupted."],
                                  missing: null,
                                });
                              } catch (err) {
                                setSubmitError({ title: "Cancellation Error", items: [err.message], missing: null });
                              }
                            }}
                            className="flex items-center gap-2 px-5 py-2 rounded-lg bg-destructive text-destructive-foreground text-sm font-medium hover:bg-destructive/90 transition-colors"
                          >
                            <Square size={14} /> Cancel Run
                          </button>
                        )}
                      </div>
                    </StepPanel>
                  )}

                  {/* ── Step 2: Processing ─────────── */}
                  {id === "progress" && (
                    <StepPanel>
                      {/* ── no run loaded yet ── */}
                      {showDAG == false && (
                        <div className="flex items-center gap-2 w-fit max-w-full text-xs text-warning bg-warning/10 rounded-lg px-3 py-2">
                          <AlertCircle size={13} /> Run Mira assembly in Step 1 to watch its live progress here.
                        </div>
                      )}

                      {/* ── run loaded / submitted ── */}
                      {showDAG == true && (
                        <>
                          {/* header row */}
                          <div className="flex items-center justify-between gap-3 flex-wrap">
                            <div className="flex items-center gap-3 min-w-0 bg-muted/60 border border-border px-3 py-1.5 rounded-lg">
                              <div className="flex items-center gap-1.5 min-w-0">
                                <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground shrink-0">Run</span>
                                <span className="text-xs font-mono font-semibold text-foreground truncate max-w-[220px]">{selectedRun?.run_name || "—"}</span>
                              </div>
                              <div className="w-px h-4 bg-border shrink-0" />
                              <div className="flex items-center gap-1.5 shrink-0">
                                <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Type</span>
                                <span className="text-xs font-mono text-foreground">{selectedRun?.experiment_type || "—"}</span>
                              </div>
                            </div>
                            {pipelineDAG?.workflows?.status && (() => {
                              const s = pipelineDAG?.workflows?.status;
                              const { cls, Icon } = {
                                COMPLETED:  { cls: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/10 dark:text-emerald-400", Icon: Check },
                                FAILED:     { cls: "bg-red-100 text-red-700 dark:bg-red-900/10 dark:text-red-400", Icon: AlertCircle },
                                PROCESSING: { cls: "bg-sky-100 text-sky-700 dark:bg-sky-900/10 dark:text-sky-400", Icon: RefreshCw },
                              }[s] ?? { cls: "bg-muted text-muted-foreground", Icon: AlertCircle };
                              return (
                                <span className={cn("flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold shrink-0", cls)}>
                                  <Icon size={12} className={submitting === true ? "animate-spin" : ""} />
                                  {s}
                                </span>
                              );
                            })()}
                          </div>

                          {/* CANCELED status message */}
                          {pipelineDAG?.workflows?.status && (
                            Array.isArray(pipelineDAG?.message) && pipelineDAG.message.length > 0
                              ? pipelineDAG.message.map((msg, i) => (
                                  <div key={i} className="flex items-start gap-2 text-xs text-warning bg-warning/10 border border-warning/30 rounded-lg px-3 py-2">
                                    <AlertCircle size={13} className="shrink-0 mt-0.5" />
                                    <span>{msg}</span>
                                  </div>
                                ))
                              : pipelineDAG?.workflows?.status === "CANCELED" && (
                                  <div className="flex items-start gap-2 text-xs text-warning bg-warning/10 border border-warning/30 rounded-lg px-3 py-2">
                                    <AlertCircle size={13} className="shrink-0 mt-0.5" />
                                    <span>Mira run was canceled or interrupted.</span>
                                  </div>
                                )
                          )}

                          {/* pipeline tasks — grid: distinct tasks (rows) x samples (columns) */}
                          {(pipelineDAG?.tasks?.length > 0 || pipelineDAG?.process_names?.length > 0) && (() => {
                            const tasks = pipelineDAG.tasks ?? [];
                            // Seed rows with every potential task parsed from the .nextflow.log
                            // ("Starting process > ...") so all rows appear up front.
                            const taskNames = Array.isArray(pipelineDAG.process_names) ? [...pipelineDAG.process_names] : [];
                            tasks.forEach(t => {
                              const p = t.process_name || "unknown";
                              if (!taskNames.includes(p)) taskNames.push(p);
                            });

                            // Columns = real samples from the samplesheet. Fall back to task-derived
                            // samples only when the backend didn't provide sample_ids.
                            const knownSamples = Array.isArray(pipelineDAG.sample_ids) ? pipelineDAG.sample_ids : [];
                            const samples = [...knownSamples];
                            if (knownSamples.length === 0) {
                              tasks.forEach(t => { if (t.sample && !samples.includes(t.sample)) samples.push(t.sample); });
                            }
                            samples.sort((a, b) => a.localeCompare(b));
                            const knownSet = new Set(samples);

                            // Rotated -80deg labels: vertical extent ≈ (char width) × length × sin(80°).
                            // At text-xs mono that's ~7px/char; add padding so the longest name fits comfortably.
                            const maxSampleLen = samples.reduce((m, s) => Math.max(m, String(s).length), 0);
                            const headerHeightPx = Math.max(56, Math.round(maxSampleLen * 7) + 40);

                            const rank = { failed: 3, running: 2, success: 1 };
                            // A task-sample is FAILED only when it has a non-zero exit code; a "0"
                            // exit (or COMPLETED status) is success; anything still in-flight is running.
                            const exitOf = (t) => (t.exit_code ?? "").toString().trim();
                            const isFailedExit = (t) => {
                              const e = exitOf(t);
                              return e !== "" && e !== "-" && !isNaN(Number(e)) && Number(e) !== 0;
                            };
                            // PASSFAILED's non-zero exit encodes a sample's QC verdict, not a task failure —
                            // it succeeds as long as the process ran to completion.
                            const isVerdictProcess = (t) => /passfailed/i.test(t.process_name || "");
                            const bucketOf = (t) => {
                              if (isVerdictProcess(t)) {
                                return (t.status === "COMPLETED" || exitOf(t) !== "") ? "success" : "running";
                              }
                              return isFailedExit(t)
                                ? "failed"
                                : (t.status === "COMPLETED" || exitOf(t) === "0") ? "success" : "running";
                            };
                            const bump = (map, key, bucket) => {
                              const prev = map.get(key);
                              if (!prev || rank[bucket] > rank[prev]) map.set(key, bucket);
                            };
                            // Per-sample cells keyed by "process||sample"; run-level tasks (not tied to a
                            // real sample, e.g. NEXTFLOWSAMPLESHEET (1)) get one status applied to every column.
                            const cellMap = new Map();
                            const rowLevelMap = new Map();
                            const failedTaskMap = new Map(); // key -> the failed task (for its log/hash on click)
                            const cellTaskMap = new Map(); // key -> { task, bucket } representative task (for the hover stdout box)
                            tasks.forEach(t => {
                              const p = t.process_name || "unknown";
                              const bucket = bucketOf(t);
                              const perSample = t.sample && knownSet.has(t.sample);
                              const key = perSample ? `${p}||${t.sample}` : `__row__${p}`;
                              if (perSample) bump(cellMap, `${p}||${t.sample}`, bucket);
                              else bump(rowLevelMap, p, bucket);
                              if (bucket === "failed") failedTaskMap.set(key, t);
                              // Track the highest-ranked (and, at equal rank, most recent) task per cell
                              // so hovering can stream that task's stdout.
                              const prevT = cellTaskMap.get(key);
                              if (t.hash && (!prevT || rank[bucket] >= rank[prevT.bucket])) cellTaskMap.set(key, { task: t, bucket });
                            });
                            return (
                              <div className="rounded-xl border border-border overflow-hidden">
                                <div className="flex items-center justify-between px-3 py-2 bg-muted/20 border-b border-border">
                                  <p className="text-xs font-bold text-foreground uppercase tracking-wider">Task Progress</p>
                                </div>
                                <div className="overflow-x-auto">
                                  <table className="text-xs border-collapse">
                                    <thead>
                                      <tr>
                                        <th className="sticky left-0 top-0 z-20 bg-muted px-3 py-2 text-left align-bottom font-semibold text-muted-foreground border-b border-r border-border whitespace-nowrap">Task \ Sample</th>
                                        {samples.map(s => (
                                          <th key={s} style={{ height: `${headerHeightPx}px` }} className="sticky top-0 z-10 bg-muted border-b border-border p-0 align-bottom">
                                            <div className="flex h-full items-end justify-center px-1 pb-8">
                                              <span className="origin-bottom rotate-[-80deg] whitespace-nowrap font-mono font-semibold text-foreground leading-none">{s}</span>
                                            </div>
                                          </th>
                                        ))}
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {taskNames.map(p => (
                                        <tr key={p} className="border-b border-border/50">
                                          <td className="sticky left-0 z-10 bg-background px-3 py-1.5 font-mono text-foreground border-r border-border whitespace-nowrap">{p}</td>
                                          {samples.map(s => {
                                            const bucket = cellMap.get(`${p}||${s}`) ?? rowLevelMap.get(p);
                                            const failedTask = bucket === "failed"
                                              ? (failedTaskMap.get(`${p}||${s}`) ?? failedTaskMap.get(`__row__${p}`))
                                              : null;
                                            const hoverTask = (cellTaskMap.get(`${p}||${s}`) ?? cellTaskMap.get(`__row__${p}`))?.task;
                                            const canHover = !!hoverTask?.hash;
                                            return (
                                              <td
                                                key={s}
                                                className={cn("px-3 py-1.5 text-left align-middle", canHover && "cursor-pointer")}
                                                onMouseEnter={canHover ? (e) => openTaskHover(e, hoverTask, p, s) : undefined}
                                                onMouseLeave={canHover ? closeTaskHover : undefined}
                                                onClick={canHover && bucket !== "failed" ? () => openTaskLog(hoverTask, p, s, "stdout") : undefined}
                                                title={canHover && bucket !== "failed" ? "Click to open log" : undefined}
                                              >
                                                {bucket === "success" && <Check size={13} className="inline text-emerald-500" />}
                                                {bucket === "failed" && (
                                                  <button
                                                    onClick={(e) => { e.stopPropagation(); openTaskLog(failedTask, p, s); }}
                                                    title="View error log"
                                                    className="inline-flex items-center justify-center text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950/30 rounded transition-colors"
                                                  >
                                                    <X size={13} />
                                                  </button>
                                                )}
                                                {bucket === "running" && <RefreshCw size={13} className="inline text-sky-500 animate-spin" />}
                                              </td>
                                            );
                                          })}
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                </div>
                              </div>
                            );
                          })()}

                          {/* timing footer */}
                          {pipelineDAG?.workflows && (
                            <div className="text-xs text-muted-foreground border-t border-border pt-2 grid grid-cols-2 gap-x-4">
                              <div className="flex flex-col gap-y-1">
                                <span>Began: <span className="text-foreground">{pipelineDAG?.workflows?.started_at || "—"}</span></span>
                                <span>Ended: <span className="text-foreground">{pipelineDAG?.workflows?.completed_at || "—"}</span></span>
                                {pipelineDAG?.workflows?.runtime && (
                                  <span>Runtime: <span className="text-foreground font-mono">{pipelineDAG.workflows.runtime}</span></span>
                                )}
                                {(() => {
                                  const startedAt = pipelineDAG?.workflows?.started_at;
                                  const completedAt = pipelineDAG?.workflows?.completed_at;
                                  if (!startedAt || !completedAt) return null;
                                  const startMs = new Date(startedAt).getTime();
                                  const endMs = new Date(completedAt).getTime();
                                  if (isNaN(startMs) || isNaN(endMs) || endMs < startMs) return null;
                                  const totalSeconds = Math.floor((endMs - startMs) / 1000);
                                  const h = Math.floor(totalSeconds / 3600);
                                  const m = Math.floor((totalSeconds % 3600) / 60);
                                  const s = totalSeconds % 60;
                                  const parts = [];
                                  if (h > 0) parts.push(`${h}h`);
                                  if (h > 0 || m > 0) parts.push(`${m}m`);
                                  parts.push(`${s}s`);
                                  return <span>Duration: <span className="text-foreground font-mono">{parts.join(" ")}</span></span>;
                                })()}
                              </div>
                              <div className="flex flex-col items-start gap-y-1">
                                <span className="w-fit px-1.5 py-0.5 rounded bg-muted text-muted-foreground font-mono">
                                  {pipelineDAG?.workflows?.number_of_samples ?? 0} total samples
                                </span>
                                <span className="w-fit px-1.5 py-0.5 rounded bg-red-100 text-red-700 dark:bg-red-900/10 dark:text-red-400 font-mono">
                                  {pipelineDAG?.workflows?.number_of_samples_with_failed_tasks ?? 0} samples failed
                                </span>
                                <span className="w-fit px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700 dark:bg-emerald-900/05 dark:text-emerald-400 font-mono">
                                  {pipelineDAG?.workflows?.number_of_samples_with_successful_tasks ?? 0} samples passed
                                </span>
                              </div>
                            </div>
                          )}
                        </>
                      )}
                    </StepPanel>
                  )}

                  {/* ── Step 3: Results ─────────────── */}
                  {id === "results" && (
                    <StepPanel>
                      {!assembled && (
                        <div className="flex items-center gap-2 w-fit max-w-full text-xs text-warning bg-warning/10 rounded-lg px-3 py-2">
                          <AlertCircle size={13} /> Results will appear here after assembly is completed.
                        </div>
                      )}
                      {assembled && cancelRun && hasNoResults && (
                        <div className="flex items-center gap-2 w-fit max-w-full text-xs text-warning bg-warning/10 rounded-lg px-3 py-2">
                          <AlertCircle size={13} /> Run was canceled. There are no results generated for this run.
                        </div>
                      )}
                      {assembled && !cancelRun && hasNoResults && (
                        <div className="flex items-center gap-2 w-fit max-w-full text-xs text-warning bg-warning/10 rounded-lg px-3 py-2">
                          <AlertCircle size={13} /> The assembly completed, but there are no results generated for this run.
                        </div>
                      )}

                      {/* ── 1. Barcode Assignment ── */}
                      {assembled && resultBarcodeAssignments !== null && (() => {
                        if ((resultBarcodeAssignments.data ?? []).length === 0) {
                          return (
                            <ResultSection id="result-section-barcode">
                              <EmptyResultTable title="Barcode Assignment" />
                            </ResultSection>
                          );
                        }
                        return (
                          <ResultSection id="result-section-barcode">
                          <div className="w-full min-w-0 rounded-xl border border-border overflow-hidden">
                            <div className="flex items-center justify-between px-3 py-2 bg-muted/20 border-b border-border">
                              <p className="text-xs font-bold text-foreground uppercase tracking-wider">Barcode Assignment</p>
                            </div>
                            <div className="p-2 overflow-x-auto">
                              <div style={{ minWidth: resultBarcodeAssignments.layout?.width ? `${resultBarcodeAssignments.layout.width}px` : "100%" }}>
                                <Suspense fallback={<div className="flex items-center justify-center h-40 text-xs text-muted-foreground">Loading chart…</div>}>
                                  <Plot
                                    data={resultBarcodeAssignments.data ?? []}
                                    layout={{
                                      autosize: true,
                                      paper_bgcolor: "transparent",
                                      plot_bgcolor: "transparent",
                                      font: { size: 11 },
                                      // Respect the layout mira-oxide emits (margin, annotations, height,
                                      // axes, legend) so the stacked-bar plot renders as designed.
                                      ...(resultBarcodeAssignments.layout ?? {}),
                                    }}
                                    config={PLOT_CONFIG}
                                    style={{ width: "100%", minHeight: 300 }}
                                    useResizeHandler
                                  />
                                </Suspense>
                              </div>
                            </div>
                          </div>
                          </ResultSection>
                        );
                      })()}

                      {/* ── 2. Automatic QC Decisions heatmap ── */}
                      {assembled && resultQcDecisions !== null && (() => {
                        if ((resultQcDecisions.data ?? []).length === 0) {
                          return (
                            <ResultSection id="result-section-qc">
                              <EmptyResultTable title="Automatic Quality Control Decisions" />
                            </ResultSection>
                          );
                        }
                        // The heatmap trace stores x/y as parallel per-cell arrays, so size by the
                        // number of UNIQUE rows/columns rather than the raw array length.
                        const qcRawX = resultQcDecisions.data?.[0]?.x ?? [];
                        const qcRawY = resultQcDecisions.data?.[0]?.y ?? [];
                        const qcCols = [...new Set(qcRawX)];
                        const qcRows = [...new Set(qcRawY)];
                        const qcManyCols = qcCols.length > 12;
                        const qcHeight = Math.max(120, qcRows.length * HEATMAP_ROW_PX + 120);
                        return (
                          <ResultSection id="result-section-qc">
                          <div className="w-full min-w-0 rounded-xl border border-border overflow-hidden">
                            <div className="flex items-center justify-between px-3 py-2 bg-muted/20 border-b border-border">
                              <p className="text-xs font-bold text-foreground uppercase tracking-wider">Automatic Quality Control Decisions</p>
                            </div>
                            {/* ── QC Statement ── */}
                            {resultQcStatement && (() => {
                              const fails = Object.entries(resultQcStatement["FAILS QC"] ?? {});
                              const passes = Object.entries(resultQcStatement["passes QC"] ?? {});
                              if (fails.length === 0 && passes.length === 0) return null;
                              return (
                                <div className="px-3 py-2 border-b border-border space-y-1 bg-muted/5">
                                  {fails.map(([sample, pct]) => (
                                    <div key={`fail-${sample}`} className="flex items-start gap-1.5 text-xs text-red-600 dark:text-red-400">
                                      <AlertCircle size={11} className="shrink-0 mt-0.5" />
                                      <span>Your negative sample <strong>&ldquo;{sample}&rdquo; FAILS QC</strong> with {pct}% reads mapping to reference.</span>
                                    </div>
                                  ))}
                                  {passes.map(([sample, pct]) => (
                                    <div key={`pass-${sample}`} className="flex items-start gap-1.5 text-xs text-foreground">
                                      <Check size={11} className="shrink-0 mt-0.5 text-emerald-500" />
                                      <span>Your negative sample &ldquo;{sample}&rdquo; passes QC with {pct}% reads mapping to reference.</span>
                                    </div>
                                  ))}
                                </div>
                              );
                            })()}
                            <div className="p-2">
                              <div style={{ width: "100%" }}>
                                <Suspense fallback={<div className="flex items-center justify-center h-40 text-xs text-muted-foreground">Loading chart…</div>}>
                                  <Plot
                                    data={resultQcDecisions.data ?? []}
                                    layout={{
                                      ...(resultQcDecisions.layout ?? {}),
                                      autosize: true,
                                      width: undefined,
                                      height: undefined,
                                      margin: { l: 60, r: 20, t: 40, b: 20 },
                                      paper_bgcolor: "transparent",
                                      plot_bgcolor: "transparent",
                                      font: { size: 11 },
                                      xaxis: {
                                        ...(resultQcDecisions.layout?.xaxis ?? {}),
                                        type: "category",
                                        side: "top",
                                        automargin: true,
                                        tickmode: "linear",
                                        dtick: 1,
                                        tickangle: qcManyCols ? -60 : 0,
                                        tickfont: { size: qcManyCols ? 8 : 10 },
                                      },
                                      yaxis: {
                                        ...(resultQcDecisions.layout?.yaxis ?? {}),
                                        type: "category",
                                        automargin: true,
                                        tickmode: "linear",
                                        dtick: 1,
                                        tickfont: { size: qcManyCols ? 10 : 10 },
                                      },
                                    }}
                                    config={PLOT_CONFIG}
                                    style={{ width: "100%", height: qcHeight }}
                                    useResizeHandler
                                  />
                                </Suspense>
                              </div>
                            </div>
                          </div>
                          </ResultSection>
                        );
                      })()}

                      {/* ── 4. MIRA Summary ── */}
                      {assembled && resultMiraSummary !== null && (
                        <ResultSection id="result-section-summary">
                          {resultMiraSummary.length === 0 ? (
                            <EmptyResultTable title="Mira Summary Table" />
                          ) : (
                            <ResultTable title="Mira Summary Table" data={resultMiraSummary} page={miraSummaryPage} setPage={setMiraSummaryPage} colorize compact defaultVisibleCols={MIRA_SUMMARY_DEFAULT_COLS} />
                          )}
                        </ResultSection>
                      )}

                      {/* ── 5b. Coverage Heatmap (after Mira Summary) ── */}
                      {assembled && resultCoverageHeatmap !== null && (() => {
                        if ((resultCoverageHeatmap.data ?? []).length === 0) {
                          return (
                            <ResultSection id="result-section-heatmap">
                              <EmptyResultTable title="Median Coverage Heatmap" />
                            </ResultSection>
                          );
                        }
                        // The heatmap trace stores x/y as parallel per-cell arrays (one entry per
                        // cell), so size by the number of UNIQUE rows/columns — not the array length.
                        const rawHeatmapX = resultCoverageHeatmap.data?.[0]?.x ?? [];
                        const rawHeatmapY = resultCoverageHeatmap.data?.[0]?.y ?? [];
                        const heatmapCols = [...new Set(rawHeatmapX)];
                        const heatmapRows = [...new Set(rawHeatmapY)];
                        // The trace ships x/y/z as parallel per-cell 1D arrays; Plotly needs z as a
                        // 2D [row][col] matrix for a proper grid and reliable click points.
                        const rawHeatmapZ = resultCoverageHeatmap.data?.[0]?.z ?? [];
                        const zByCell = new Map();
                        for (let i = 0; i < rawHeatmapX.length; i++) {
                          zByCell.set(`${rawHeatmapY[i]}\u0000${rawHeatmapX[i]}`, rawHeatmapZ[i]);
                        }
                        const heatmapZ = heatmapRows.map((r) =>
                          heatmapCols.map((c) => {
                            const v = zByCell.get(`${r}\u0000${c}`);
                            return v === undefined ? null : v;
                          })
                        );
                        const heatmapTrace = {
                          ...(resultCoverageHeatmap.data?.[0] ?? {}),
                          x: heatmapCols,
                          y: heatmapRows,
                          z: heatmapZ,
                        };
                        const heatmapManyCols = heatmapCols.length > 12;
                        const heatmapMinHeight = Math.max(
                          120,
                          heatmapRows.length * HEATMAP_ROW_PX + 120
                        );
                        return (
                          <ResultSection id="result-section-heatmap">
                          <div className="w-full min-w-0 rounded-xl border border-border overflow-hidden">
                            <div className="flex items-center justify-between px-3 py-2 bg-muted/20 border-b border-border">
                              <p className="text-xs font-bold text-foreground uppercase tracking-wider">Median Coverage Heatmap</p>
                            </div>
                            <div className="p-2">
                              <div style={{ width: "100%" }}>
                                <Suspense fallback={<div className="flex items-center justify-center h-40 text-xs text-muted-foreground">Loading chart…</div>}>
                                  <Plot
                                    data={[heatmapTrace]}
                                    layout={{
                                      ...(resultCoverageHeatmap.layout ?? {}),
                                      autosize: true,
                                      width: undefined,
                                      height: undefined,
                                      margin: { l: 100, r: 20, t: 90, b: 20 },
                                      paper_bgcolor: "transparent",
                                      plot_bgcolor: "transparent",
                                      font: { size: 11 },
                                      xaxis: {
                                        ...(resultCoverageHeatmap.layout?.xaxis ?? {}),
                                        type: "category",
                                        side: "top",
                                        automargin: true,
                                        tickmode: "linear",
                                        dtick: 1,
                                        tickangle: heatmapManyCols ? -60 : 0,
                                        tickfont: { size: heatmapManyCols ? 8 : 10 },
                                      },
                                      yaxis: {
                                        ...(resultCoverageHeatmap.layout?.yaxis ?? {}),
                                        type: "category",
                                        automargin: true,
                                        tickmode: "linear",
                                        dtick: 1,
                                        tickfont: { size: heatmapManyCols ? 10 : 10 },
                                      },
                                    }}
                                    config={PLOT_CONFIG}
                                    style={{ width: "100%", height: heatmapMinHeight, cursor: "pointer" }}
                                    useResizeHandler
                                    onClick={(e) => {
                                      // A cell's x category is the sample; select it in the
                                      // Per-Sample Coverage and Sankey Plots section below.
                                      const pt = e?.points?.[0];
                                      if (!pt) return;
                                      let sample = pt.x;
                                      if (sample == null && Array.isArray(pt.data?.x) && typeof pt.pointNumber?.[1] === "number") {
                                        sample = pt.data.x[pt.pointNumber[1]];
                                      }
                                      if (sample == null) return;
                                      fetchSankeyForSample(String(sample));
                                      setTimeout(() => document.getElementById("result-section-coverage")?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
                                    }}
                                  />
                                </Suspense>
                              </div>
                            </div>
                          </div>
                          </ResultSection>
                        );
                      })()}

                      {/* ── 5c. Sample Coverage Plot ── */}
                      {assembled && resultSampleCoverageList !== null && (() => {
                        // Derive sorted sample list from the sample coverage list (pandas split-format).
                        const sampleOptions = resultSampleCoverageList.columns && resultSampleCoverageList.data
                          ? [...new Set(resultSampleCoverageList.data.map(row => row[resultSampleCoverageList.columns.indexOf("Sample")]))].sort()
                          : Object.keys(resultSampleCoverageSankey ?? {}).sort();
                        const currentSample = selectedSampleForCoverage || sampleOptions[0] || "";
                        const figure = resultSampleCoverageSankey?.[currentSample] ?? null;
                        const covFigure = resultSampleCoveragePlot?.[currentSample] ?? null;
                        return (
                          <div id="result-section-coverage" className="w-full min-w-0 rounded-xl border border-border overflow-hidden">
                            <div className="flex items-center justify-between px-3 py-2 bg-muted/20 border-b border-border">
                              <p className="text-xs font-bold text-foreground uppercase tracking-wider">Read Assignment and Coverage Plots</p>
                              <select
                                value={currentSample}
                                onChange={e => fetchSankeyForSample(e.target.value)}
                                className="h-7 px-2 rounded-md border border-border bg-background text-xs font-mono focus:outline-none focus:ring-1 focus:ring-ring"
                              >
                                {sampleOptions.map(s => <option key={s} value={s}>{s}</option>)}
                              </select>
                            </div>
                            <div className="p-2">
                              {figure ? (
                                <>
                                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider px-1 pb-1">Read Assignment - {currentSample}</p>
                                  <div className="overflow-x-auto">
                                    <div style={{ width: "75%", margin: "0 auto", minWidth: figure.layout?.width ? `${figure.layout.width}px` : undefined }}>
                                      <Suspense fallback={<div className="flex items-center justify-center h-40 text-xs text-muted-foreground">Loading chart…</div>}>
                                      <Plot
                                        data={figure.data ?? []}
                                        layout={{
                                          ...(figure.layout ?? {}),
                                          title: undefined,
                                          autosize: true,
                                          margin: { l: 20, r: 20, t: 10, b: 20 },
                                          paper_bgcolor: "transparent",
                                          plot_bgcolor: "transparent",
                                          font: { size: 11 },
                                        }}
                                        config={PLOT_CONFIG}
                                        style={{ width: "100%", minHeight: 280 }}
                                        useResizeHandler
                                      />
                                      </Suspense>
                                    </div>
                                  </div>
                                </>
                              ) : (
                                <div className="flex items-center gap-2 text-xs text-muted-foreground px-3 py-4">
                                  <Database size={13} className="shrink-0" /> No sankey plot found for this sample.
                                </div>
                              )}
                            </div>

                            {/* ── Segment Coverage Plot ── */}
                            {(() => {
                              const linearFig = resultSampleCoverageLinear?.[currentSample] ?? null;
                              // All traces of a segment share a legendgroup (the segment name);
                              // fall back to the trace name to identify the clicked segment.
                              const onSegmentClick = (e) => {
                                const pt = e?.points?.[0];
                                if (!pt) return;
                                const seg = pt.data?.legendgroup || pt.data?.name;
                                if (!seg) return;
                                fetchLinearForSample(currentSample);
                                setFocusedCovSegment(seg);
                              };
                              return (
                                <div className="border-t border-border p-2">
                                  <div className="flex items-center justify-between px-1 pb-1">
                                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                                      {focusedCovSegment ? `Coverage - ${currentSample} · ${focusedCovSegment}` : `Segment Coverage - ${currentSample}`}
                                    </p>
                                    {focusedCovSegment && (
                                      <button
                                        onClick={() => setFocusedCovSegment(null)}
                                        className="flex items-center gap-1 h-7 px-2 rounded-md border border-border bg-background text-xs font-medium text-foreground hover:border-primary hover:text-primary transition-colors"
                                      >
                                        <ChevronLeft size={13} className="shrink-0" /> Back to separate plots
                                      </button>
                                    )}
                                  </div>
                                  {focusedCovSegment ? (
                                    linearFig ? (
                                      <ResponsivePlot
                                        data={(linearFig.data ?? []).map((tr) => {
                                          // Isolate the clicked segment, like a legend double-click.
                                          const match = (tr.legendgroup ?? tr.name) === focusedCovSegment;
                                          return { ...tr, visible: match ? true : "legendonly" };
                                        })}
                                        layout={{
                                          ...(linearFig.layout ?? {}),
                                          title: undefined,
                                          margin: { l: 55, r: 15, t: 10, b: 40 },
                                          paper_bgcolor: "transparent",
                                          plot_bgcolor: "transparent",
                                          font: { size: 11 },
                                          // Autoscale axes to the isolated segment.
                                          xaxis: { ...(linearFig.layout?.xaxis ?? {}), autorange: true, range: undefined },
                                          yaxis: { ...(linearFig.layout?.yaxis ?? {}), autorange: true, range: undefined },
                                        }}
                                        config={{ ...(linearFig.config ?? {}), ...PLOT_CONFIG }}
                                        maxHeight={520}
                                        useResizeHandler
                                      />
                                    ) : (
                                      <div className="flex items-center gap-2 text-xs text-muted-foreground px-3 py-4">
                                        <Database size={13} className="shrink-0" /> Loading combined coverage…
                                      </div>
                                    )
                                  ) : covFigure ? (
                                    <ResponsivePlot
                                      data={covFigure.data ?? []}
                                      layout={{
                                        ...(covFigure.layout ?? {}),
                                        title: undefined,
                                        margin: { l: 45, r: 15, t: 20, b: 30 },
                                        paper_bgcolor: "transparent",
                                        plot_bgcolor: "transparent",
                                        font: { size: 10 },
                                      }}
                                      config={{ ...(covFigure.config ?? {}), ...PLOT_CONFIG }}
                                      onClick={onSegmentClick}
                                      useResizeHandler
                                    />
                                  ) : (
                                    <div className="flex items-center gap-2 text-xs text-muted-foreground px-3 py-4">
                                      <Database size={13} className="shrink-0" /> No segment coverage plot found for this sample.
                                    </div>
                                  )}
                                </div>
                              );
                            })()}

                          </div>
                        );
                      })()}

                      {/* ── 6. Reference Variants ── */}
                      {assembled && resultVariants !== null && (
                        <ResultSection id="result-section-variants">
                          {resultVariants.length === 0 ? (
                            <EmptyResultTable title="AA Variants Table" />
                          ) : (
                            <ResultTable title="AA Variants Table" data={resultVariants} page={variantsPage} setPage={setVariantsPage} compact fitCols={5} defaultHiddenCols={["positional_reference_id"]} />
                          )}
                        </ResultSection>
                      )}

                      {/* ── 7. Minor SNVs ── */}
                      {assembled && resultMinorSnvs !== null && (
                        <ResultSection id="result-section-snvs">
                          {resultMinorSnvs.length === 0 ? (
                            <EmptyResultTable title="Minor Variants Table" message="No Minor Variants found for this run." />
                          ) : (
                            <ResultTable title="Minor Variants Table" data={resultMinorSnvs} page={minorSnvsPage} setPage={setMinorSnvsPage} compact fitCols={5} defaultHiddenCols={["dais_reference"]} stickyFirstCol />
                          )}
                        </ResultSection>
                      )}

                      {/* ── 8. Reference Indels ── */}
                      {assembled && resultIndels !== null && (
                        <ResultSection id="result-section-indels">
                          {resultIndels.length === 0 ? (
                            <EmptyResultTable title="Minor Indels Table" message="No Minor Indels found for this run." />
                          ) : (
                            <ResultTable title="Minor Indels Table" data={resultIndels} page={indelsPage} setPage={setIndelsPage} />
                          )}
                        </ResultSection>
                      )}
                    </StepPanel>
                  )}

                  {/* ── Step 4: Export ──────────────── */}
                  {id === "export" && (
                    <StepPanel>
                      {!assembled && (
                        <div className="flex items-center gap-2 w-fit max-w-full text-xs text-warning bg-warning/10 rounded-lg px-3 py-2">
                          <AlertCircle size={13} /> Export files will be available after assembly is completed.
                        </div>
                      )}
                      {assembled && cancelRun && !resultNtPassedFasta && !resultAaFailedFasta && !resultNtFailedFasta && !resultAaPassedFasta && !resultNextcladeFasta && (
                        <div className="flex items-center gap-2 w-fit max-w-full text-xs text-warning bg-warning/10 rounded-lg px-3 py-2">
                          <AlertCircle size={13} /> Run was canceled. There are no FASTA files generated from this run.
                        </div>
                      )}
                      {assembled && !cancelRun && !resultNtPassedFasta && !resultAaFailedFasta && !resultNtFailedFasta && !resultAaPassedFasta && !resultNextcladeFasta && (
                        <div className="flex items-center gap-2 w-fit max-w-full text-xs text-warning bg-warning/10 rounded-lg px-3 py-2">
                          <AlertCircle size={13} /> The assembly completed, but there are no FASTA files generated from this run.
                        </div>
                      )}
                      <div className="space-y-2">
                        {[
                          { label: "NT Passed FASTA",  desc: "Nucleotide consensus sequences that passed QC thresholds",  location: resultNtPassedFasta,  dlUrl: API.downloadNtPassedFasta },
                          { label: "NT Failed FASTA",  desc: "Nucleotide consensus sequences that failed QC thresholds",  location: resultNtFailedFasta,  dlUrl: API.downloadNtFailedFasta },
                          { label: "AA Passed FASTA",  desc: "Amino acid translated sequences that passed QC thresholds",  location: resultAaPassedFasta,  dlUrl: API.downloadAaPassedFasta },
                          { label: "AA Failed FASTA",  desc: "Amino acid translated sequences that failed QC thresholds",  location: resultAaFailedFasta,  dlUrl: API.downloadAaFailedFasta },
                        ].filter(({ location }) => location).map(({ label, desc, location, dlUrl }) => (
                          <div key={label} className="flex items-start justify-between gap-3 p-3 rounded-xl border border-border bg-muted/10">
                            <div>
                              <p className="text-sm font-semibold text-foreground">{label}</p>
                              <p className="text-xs text-muted-foreground mt-0.5">{desc}</p>
                            </div>
                            <a
                              href={`${dlUrl}?run_name=${encodeURIComponent(selectedRun?.run_name ?? "")}&experiment_type=${encodeURIComponent(selectedRun?.experiment_type ?? "")}`}
                              download
                              className="shrink-0 flex items-center gap-1.5 px-3 py-1 rounded-full border border-primary bg-primary text-primary-foreground text-xs font-medium hover:bg-primary/90 transition-colors"
                            >
                              <Download size={11} /> Download
                            </a>
                          </div>
                        ))}

                        {/* Nextclade FASTA files (one per subtype/segment) */}
                        {resultNextcladeFasta && typeof resultNextcladeFasta === "object" && Object.keys(resultNextcladeFasta).map(key => {
                          // Relative URL resolves against clades.nextstrain.org, not this app — use an absolute URL so the external viewer can fetch it.
                          const nextcladeFastaUrl = `${window.location.origin}${API.downloadNextcladeFasta}?run_name=${encodeURIComponent(selectedRun?.run_name ?? "")}&experiment_type=${encodeURIComponent(selectedRun?.experiment_type ?? "")}&key=${encodeURIComponent(key)}`;
                          const nextcladeViewUrl = `${NEXTCLADE_BASE}?dataset-name=${encodeURIComponent(key)}&input-fasta=${encodeURIComponent(nextcladeFastaUrl)}`;
                          return (
                            <div key={key} className="flex items-start justify-between gap-3 p-3 rounded-xl border border-border bg-muted/10">
                              <div>
                                <p className="text-sm font-semibold text-foreground">Nextclade FASTA — {key}</p>
                                <p className="text-xs text-muted-foreground mt-0.5">Nextclade-aligned sequences for {key}</p>
                              </div>
                              <div className="shrink-0 flex items-center gap-2">
                                <a
                                  href={nextcladeViewUrl}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="flex items-center gap-1.5 px-3 py-1 rounded-full border border-primary text-primary text-xs font-medium hover:bg-primary/10 transition-colors"
                                >
                                  <ExternalLink size={11} /> View on NextClade
                                </a>
                                <a
                                  href={nextcladeFastaUrl}
                                  download
                                  className="flex items-center gap-1.5 px-3 py-1 rounded-full border border-primary bg-primary text-primary-foreground text-xs font-medium hover:bg-primary/90 transition-colors"
                                >
                                  <Download size={11} /> Download
                                </a>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </StepPanel>
                  )}
                </>
              )}
            </div>
          ))}
          <button
            type="button"
            onClick={onOpenSeqSender}
            className="mx-auto flex w-fit min-w-[min(500px,100%)] max-w-full items-center gap-3 rounded-xl bg-primary px-4 py-3 text-left transition-colors hover:bg-primary/90"
          >
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-primary-foreground">
              <Send size={16} />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-xs font-bold tracking-wider text-primary-foreground">{SEQSENDER_ACTION.title}</span>
              <span className="block text-xs text-primary-foreground/80">{SEQSENDER_ACTION.subtitle}</span>
            </span>
          </button>
        </div>
      </div>

      {/* ── Past Runs slide-in panel (splits the main content, width-adjustable) ── */}
      {loadRunModal && (
        <>
          {/* draggable divider */}
          <div
            onMouseDown={onMouseDown}
            title="Drag to resize"
            className="w-1.5 shrink-0 cursor-col-resize bg-border hover:bg-primary/50 transition-colors"
          />
          <aside style={{ width: rightWidth, maxWidth: "75%" }} className="relative z-10 shrink-0 flex flex-col overflow-hidden border-l border-border bg-background">
            {/* header */}
            <div className="shrink-0 flex items-center justify-between px-4 py-3 border-b border-border bg-muted/20">
              <div className="flex items-center gap-2">
                <FolderOpen size={15} className="text-primary" />
                <h3 className="text-sm font-bold text-foreground">Load Existing Run</h3>
              </div>
              <button onClick={() => setLoadRunModal(false)} className="text-muted-foreground hover:text-foreground transition-colors">
                <X size={15} />
              </button>
            </div>

            {/* body */}
            <div className="flex-1 overflow-auto p-4 flex flex-col gap-3">
              {loadRunLoading && (
                <div className="flex items-center gap-2 text-xs text-muted-foreground py-4 justify-center">
                  <RefreshCw size={13} className="animate-spin" /> Loading runs…
                </div>
              )}

              {loadRunError && (
                <div className="rounded-lg border bg-red-50 border-red-200 dark:bg-red-950/20 dark:border-red-800 px-3 py-2 space-y-1 text-xs">
                  <p className="font-semibold text-destructive mb-1">Load Error:</p>
                  <div className="flex items-start gap-2">
                    <AlertCircle size={12} className="shrink-0 mt-0.5 text-destructive" />
                    <span className="text-destructive">{loadRunError}</span>
                  </div>
                </div>
              )}

              {!loadRunLoading && !loadRunError && (
                availableRuns.length === 0 ? (
                  <p className="text-xs text-muted-foreground text-left py-4">There are no runs found in storage.</p>
                ) : (() => {
                  const q = runSearch.trim().toLowerCase();
                  // Sort by run date (finished, else created); undated runs sink to the bottom.
                  const runTime = (r) => {
                    const t = Date.parse((r.finished_at || r.created_at || "").replace(" ", "T"));
                    return Number.isNaN(t) ? null : t;
                  };
                  const filtered = (q
                    ? availableRuns.filter(r =>
                        [r.run_name, r.experiment_type, r.assembly_status, r.finished_at, r.created_at]
                          .some(v => (v ?? "").toLowerCase().includes(q))
                      )
                    : availableRuns
                  ).slice().sort((a, b) => {
                    const ta = runTime(a), tb = runTime(b);
                    const direction = runSortDir === "asc" ? 1 : -1;
                    const nameComparison = (a.run_name ?? "").localeCompare(b.run_name ?? "");
                    if (ta === null && tb === null) return direction * nameComparison;
                    if (ta === null) return 1;
                    if (tb === null) return -1;
                    const timeComparison = ta - tb;
                    return direction * (timeComparison || nameComparison);
                  });
                  return (
                    <>
                      <div className="flex items-center gap-2">
                        <div className="relative flex-1">
                          <FileSearch size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none" />
                          <input
                            value={runSearch}
                            onChange={(e) => { setRunSearch(e.target.value); setLoadRunSelectedRow(null); }}
                            placeholder="Search runs…"
                            className="w-full h-8 pl-8 pr-3 rounded-lg border border-border bg-background text-xs font-mono focus:outline-none focus:ring-1 focus:ring-ring"
                          />
                        </div>
                        <button
                          type="button"
                          title={`Sort ${runSortDir === "asc" ? "newest first" : "oldest first"}`}
                          onClick={() => setRunSortDir(d => d === "asc" ? "desc" : "asc")}
                          className="h-8 w-8 shrink-0 flex items-center justify-center rounded-lg border border-border text-muted-foreground hover:text-primary hover:border-primary transition-colors"
                        >
                          {runSortDir === "asc" ? <ArrowUp size={13} /> : <ArrowDown size={13} />}
                        </button>
                      </div>
                      {filtered.length === 0 ? (
                        <p className="text-xs text-muted-foreground text-left py-3">No runs match your search.</p>
                      ) : (
                        <div className="rounded-xl border border-border overflow-hidden">
                          <table className="w-full text-xs">
                            <thead className="bg-muted sticky top-0 z-10">
                              <tr>
                                <th className="px-4 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Name</th>
                                <th className="px-4 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Type</th>
                                <th className="px-4 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Ended time</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-border">
                              {filtered.map(run => (
                                <tr
                                  key={run.assembly_id}
                                  onClick={() => { setLoadRunSelectedRow(run); handleLoadRun(run); }}
                                  className={cn(
                                    "cursor-pointer transition-colors",
                                    loadRunSelectedRow?.assembly_id === run.assembly_id
                                      ? "bg-primary/10"
                                      : "hover:bg-muted/40"
                                  )}
                                >
                                  <td className="px-4 py-2 font-mono font-semibold text-foreground truncate max-w-[240px]">{run.run_name}</td>
                                  <td className="px-4 py-2 font-mono text-foreground whitespace-nowrap">{run.experiment_type}</td>
                                  <td className="px-4 py-2 font-mono text-muted-foreground whitespace-nowrap">{(() => {
                                    // Nextflow's reported finish time; trim seconds to minute precision
                                    const ts = run.finished_at;
                                    return ts ? ts.replace(/(\d{1,2}:\d{2}):\d{2}/, "$1") : "—";
                                  })()}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </>
                  );
                })()
              )}
            </div>
          </aside>
        </>
      )}

      </div>

      {/* ── Export Run modal ─────────────────── */}
      {exportRunModal && (
        <div onClick={() => setExportRunModal(false)} className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div onClick={(e) => e.stopPropagation()} className="bg-background border border-border rounded-xl p-6 max-w-2xl w-full mx-4 shadow-xl flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-foreground">Export Mira Reports</h3>
              <button onClick={() => setExportRunModal(false)} className="text-muted-foreground hover:text-foreground transition-colors">
                <X size={14} />
              </button>
            </div>

            {exportRunLoading && (
              <div className="flex items-center gap-2 text-xs text-muted-foreground py-4 justify-center">
                <RefreshCw size={13} className="animate-spin" /> Loading runs…
              </div>
            )}

            {exportRunError && (
              <div className="rounded-lg border bg-red-50 border-red-200 dark:bg-red-950/20 dark:border-red-800 px-3 py-2 space-y-1 text-xs">
                <p className="font-semibold text-destructive mb-1">Load Error:</p>
                <div className="flex items-start gap-2">
                  <AlertCircle size={12} className="shrink-0 mt-0.5 text-destructive" />
                  <span className="text-destructive">{exportRunError}</span>
                </div>
              </div>
            )}

            {!exportRunLoading && !exportRunError && (
              availableRuns.length === 0 ? (
                <p className="text-xs text-muted-foreground text-left py-4">There are no runs with status of "COMPLETED" found in storage.</p>
              ) : (() => {
                const q = exportRunSearch.trim().toLowerCase();
                const filtered = (q
                  ? availableRuns.filter(r =>
                      [r.run_name, r.experiment_type, r.assembly_status, r.run_date]
                        .some(v => (v ?? "").toLowerCase().includes(q))
                    )
                  : availableRuns
                ).sort((a, b) => exportRunSortDir === "asc"
                  ? (a.run_name ?? "").localeCompare(b.run_name ?? "")
                  : (b.run_name ?? "").localeCompare(a.run_name ?? ""));
                return (
                  <>
                    <p className="text-xs text-muted-foreground">
                      Select a run to download its Mira results as a <span className="font-mono">zip</span> archive.
                    </p>                  
                    <div className="flex items-center gap-2">
                    <div className="relative flex-1">
                      <FileSearch size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none" />
                      <input
                        value={exportRunSearch}
                        onChange={(e) => { setExportRunSearch(e.target.value); setExportSelectedRun(null); }}
                        placeholder="Search runs…"
                        className="w-full h-8 pl-8 pr-3 rounded-lg border border-border bg-background text-xs font-mono focus:outline-none focus:ring-1 focus:ring-ring"
                      />
                    </div>
                    <button
                      type="button"
                      title={`Sort ${exportRunSortDir === "asc" ? "Z→A" : "A→Z"}`}
                      onClick={() => setExportRunSortDir(d => d === "asc" ? "desc" : "asc")}
                      className="h-8 w-8 shrink-0 flex items-center justify-center rounded-lg border border-border text-muted-foreground hover:text-primary hover:border-primary transition-colors"
                    >
                      {exportRunSortDir === "asc" ? <ArrowUp size={13} /> : <ArrowDown size={13} />}
                    </button>
                    </div>
                    {filtered.length === 0 ? (
                      <p className="text-xs text-muted-foreground text-left py-3">No runs match your search.</p>
                    ) : (
                      <div className={cn("rounded-xl border border-border divide-y divide-border", availableRuns.length > 10 && "max-h-96 overflow-y-auto")}>
                        {filtered.map(run => (
                          <button
                            key={run.assembly_id}
                            onClick={() => setExportSelectedRun(run)}
                            className={cn(
                              "w-full text-left px-4 py-3 text-xs transition-colors",
                              exportSelectedRun?.assembly_id === run.assembly_id
                                ? "bg-primary/10 border-l-2 border-primary"
                                : "hover:bg-muted/40"
                            )}
                          >
                            <div className="flex items-center justify-between gap-3">
                              <div className="flex items-center gap-3 min-w-0">
                                <div className="flex items-center gap-1.5 min-w-0">
                                  <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground shrink-0">Name:</span>
                                  <span className="font-semibold text-foreground font-mono truncate">{run.run_name}</span>
                                </div>
                                <div className="flex items-center gap-1.5 shrink-0">
                                  <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Type:</span>
                                  <span className="font-mono text-foreground">{run.experiment_type}</span>
                                </div>
                              </div>
                              <span className={cn(
                                  "px-2 py-0.5 rounded-full text-xs font-medium shrink-0",
                                  run.assembly_status === "SUBMITTED"  ? "bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-400" :
                                  run.assembly_status === "PROCESSING" ? "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400" :
                                  run.assembly_status === "PROCESSED"  ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400" :
                                  "bg-muted text-muted-foreground"
                                )}>{run.assembly_status}
                              </span>
                            </div>
                          </button>
                        ))}
                      </div>
                    )}
                  </>
                );
              })()
            )}

            {exportSelectedRun && (
              <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-muted/20 border border-border text-xs">
                <Download size={11} className="text-primary shrink-0" />
                <span className="text-muted-foreground">Will download as:</span>
                <span className="font-mono font-semibold text-foreground">{exportSelectedRun.run_name}_mira_reports.zip</span>
              </div>
            )}

            <div className="flex gap-2 justify-end pt-1">
              <button
                onClick={() => setExportRunModal(false)}
                className="px-4 py-1.5 rounded-lg border border-border text-xs text-muted-foreground hover:bg-muted/60 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleExportDownload}
                disabled={!exportSelectedRun || exportDownloading || exportRunLoading}
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-primary text-primary-foreground text-xs font-semibold hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {exportDownloading ? <RefreshCw size={11} className="animate-spin" /> : <Download size={11} />}
                {exportDownloading ? "Downloading…" : "Download Reports"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Load Run panel is rendered inline in the main row above (slide-in, resizable) ── */}

      {/* ── Edit Run modal ────────────────────── */}
      {editRunModal && (
        <div onClick={closeEditRunModal} className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div onClick={(e) => e.stopPropagation()} className="bg-background border border-border rounded-xl p-6 max-w-2xl w-full mx-4 shadow-xl flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-foreground">{editSelectedRun ? "Edit Run" : "Select a Run to Edit"}</h3>
              <button onClick={closeEditRunModal} className="text-muted-foreground hover:text-foreground transition-colors">
                <X size={14} />
              </button>
            </div>

            {editRunLoading && (
              <div className="flex items-center gap-2 text-xs text-muted-foreground py-4 justify-center">
                <RefreshCw size={13} className="animate-spin" /> Loading runs…
              </div>
            )}

            {editRunError && (
              <div className="rounded-lg border bg-red-50 border-red-200 dark:bg-red-950/20 dark:border-red-800 px-3 py-2 space-y-1 text-xs">
                <p className="font-semibold text-destructive mb-1">Load Error:</p>
                <div className="flex items-start gap-2">
                  <AlertCircle size={12} className="shrink-0 mt-0.5 text-destructive" />
                  <span className="text-destructive">{editRunError}</span>
                </div>
              </div>
            )}

            {!editRunLoading && !editRunError && !editSelectedRun && (
              availableRuns.length === 0 ? (
                <p className="text-xs text-muted-foreground text-left py-4">There are no runs found in storage.</p>
              ) : (() => {
                const q = editRunSearch.trim().toLowerCase();
                const filtered = (q
                  ? availableRuns.filter(r =>
                      [r.run_name, r.experiment_type, r.assembly_status, r.run_date]
                        .some(v => (v ?? "").toLowerCase().includes(q))
                    )
                  : availableRuns
                ).sort((a, b) => editRunSortDir === "asc"
                  ? (a.run_name ?? "").localeCompare(b.run_name ?? "")
                  : (b.run_name ?? "").localeCompare(a.run_name ?? ""));
                return (
                  <>
                    <div className="flex items-center gap-2">
                    <div className="relative flex-1">
                      <FileSearch size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none" />
                      <input
                        value={editRunSearch}
                        onChange={(e) => setEditRunSearch(e.target.value)}
                        placeholder="Search runs…"
                        className="w-full h-8 pl-8 pr-3 rounded-lg border border-border bg-background text-xs font-mono focus:outline-none focus:ring-1 focus:ring-ring"
                      />
                    </div>
                    <button
                      type="button"
                      title={`Sort ${editRunSortDir === "asc" ? "Z→A" : "A→Z"}`}
                      onClick={() => setEditRunSortDir(d => d === "asc" ? "desc" : "asc")}
                      className="h-8 w-8 shrink-0 flex items-center justify-center rounded-lg border border-border text-muted-foreground hover:text-primary hover:border-primary transition-colors"
                    >
                      {editRunSortDir === "asc" ? <ArrowUp size={13} /> : <ArrowDown size={13} />}
                    </button>
                    </div>
                    {filtered.length === 0 ? (
                      <p className="text-xs text-muted-foreground text-left py-3">No runs match your search.</p>
                    ) : (
                      <div className={cn("rounded-xl border border-border divide-y divide-border", availableRuns.length > 10 && "max-h-96 overflow-y-auto")}>
                        {filtered.map(run => {
                          const locked = run.assembly_status === "PROCESSING";
                          return (
                            <div key={run.assembly_id} className="flex items-center justify-between gap-3 px-4 py-3 text-xs hover:bg-muted/40 transition-colors">
                              <div className="flex items-center gap-3 min-w-0">
                                <div className="flex items-center gap-1.5 min-w-0">
                                  <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground shrink-0">Name:</span>
                                  <span className="font-semibold text-foreground font-mono truncate">{run.run_name}</span>
                                </div>
                                <div className="flex items-center gap-1.5 shrink-0">
                                  <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Type:</span>
                                  <span className="font-mono text-foreground">{run.experiment_type}</span>
                                </div>
                              </div>
                              <div className="flex items-center gap-1.5 shrink-0">
                                <span className={cn(
                                  "px-2 py-0.5 rounded-full text-xs font-medium",
                                  run.assembly_status === "SUBMITTED"  ? "bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-400" :
                                  run.assembly_status === "PROCESSING" ? "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400" :
                                  run.assembly_status === "COMPLETED"  ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400" :
                                  "bg-muted text-muted-foreground"
                                )}>{run.assembly_status}</span>
                                <button
                                  title="Rename"
                                  onClick={() => selectRunForEdit(run, "rename")}
                                  disabled={locked}
                                  className="p-1.5 rounded-md text-muted-foreground hover:text-primary hover:bg-primary/10 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                                >
                                  <Pencil size={13} />
                                </button>
                                <button
                                  title="Duplicate"
                                  onClick={() => selectRunForEdit(run, "copy")}
                                  disabled={locked}
                                  className="p-1.5 rounded-md text-muted-foreground hover:text-primary hover:bg-primary/10 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                                >
                                  <Copy size={13} />
                                </button>
                                <button
                                  title="Delete"
                                  onClick={() => selectRunForEdit(run, "delete")}
                                  disabled={locked}
                                  className="p-1.5 rounded-md text-muted-foreground hover:text-destructive hover:bg-red-50 dark:hover:bg-red-950/20 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                                >
                                  <Trash2 size={13} />
                                </button>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </>
                );
              })()
            )}

            {editSelectedRun && (
              <div className="flex flex-col gap-3">
                <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-muted/20 border border-border text-xs flex-wrap">
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground shrink-0">Name:</span>
                  <span className="font-mono font-semibold text-foreground truncate">{editSelectedRun.run_name}</span>
                  <span className="w-px h-4 bg-border shrink-0 mx-1" />
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground shrink-0">Type:</span>
                  <span className="font-mono text-foreground">{editSelectedRun.experiment_type}</span>
                </div>

                {editSelectedRun.assembly_status === "PROCESSING" && (
                  <div className="flex items-center gap-2 text-xs text-red-600 bg-red-50 dark:bg-red-950/30 rounded-lg px-3 py-2">
                    <AlertCircle size={13} /> This run has a pipeline in progress. Cancel or wait for it to finish before editing.
                  </div>
                )}

                {editActionError && (
                  <div className="rounded-lg border bg-red-50 border-red-200 dark:bg-red-950/20 dark:border-red-800 px-3 py-2 space-y-1 text-xs">
                    <div className="flex items-start gap-2">
                      <AlertCircle size={12} className="shrink-0 mt-0.5 text-destructive" />
                      <span className="text-destructive">{editActionError}</span>
                    </div>
                  </div>
                )}

                {(editMode === "rename" || editMode === "copy") && (
                  <div className="flex flex-col gap-2">
                    <FieldLabel>{editMode === "rename" ? "New Run Name" : "Name for the Copy"}</FieldLabel>
                    <input
                      value={editNewName}
                      onChange={(e) => setEditNewName(e.target.value.replace(/\s+/g, "_"))}
                      placeholder="e.g. YYYYMMDD_experiment-type"
                      className="w-full max-w-md h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                    />
                    <div className="flex gap-2 justify-end pt-1">
                      <button
                        onClick={() => { setEditSelectedRun(null); setEditMode(null); setEditActionError(null); }}
                        className="px-4 py-1.5 rounded-lg border border-border text-xs text-muted-foreground hover:bg-muted/60 transition-colors"
                      >
                        Back
                      </button>
                      <button
                        onClick={editMode === "rename" ? handleRenameRun : handleCopyRun}
                        disabled={editActionLoading}
                        className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-primary text-primary-foreground text-xs font-semibold hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {editActionLoading ? <RefreshCw size={11} className="animate-spin" /> : (editMode === "rename" ? <Pencil size={11} /> : <Copy size={11} />)}
                        {editMode === "rename" ? "Rename" : "Duplicate"}
                      </button>
                    </div>
                  </div>
                )}

                {editMode === "delete" && (
                  <div className="flex flex-col gap-3">
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      Are you sure you want to delete <span className="font-mono font-semibold text-foreground">{editSelectedRun.run_name}</span> from the data storage?
                    </p>
                    <div className="flex gap-2 justify-end pt-1">
                      <button
                        onClick={() => { setEditSelectedRun(null); setEditMode(null); setEditActionError(null); }}
                        className="px-4 py-1.5 rounded-lg border border-border text-xs text-muted-foreground hover:bg-muted/60 transition-colors"
                      >
                        Back
                      </button>
                      <button
                        onClick={handleDeleteRun}
                        disabled={editActionLoading}
                        className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-destructive text-destructive-foreground text-xs font-semibold hover:bg-destructive/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {editActionLoading ? <RefreshCw size={11} className="animate-spin" /> : <Trash2 size={11} />}
                        Delete
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── ONT files without flowcell ID confirmation modal ────────────── */}
      {ontConfirmFiles !== null && (() => {
        const allSelected = ontConfirmFiles.length > 0 && ontConfirmFiles.every(({ name }) => ontConfirmSelected.has(name));
        const toggleName = (name) => setOntConfirmSelected(prev => {
          const next = new Set(prev);
          next.has(name) ? next.delete(name) : next.add(name);
          return next;
        });
        const toggleAll = () => setOntConfirmSelected(allSelected ? new Set() : new Set(ontConfirmFiles.map(f => f.name)));
        return (
          <div onClick={() => setOntConfirmFiles(null)} className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
            <div onClick={(e) => e.stopPropagation()} className="bg-background border border-border rounded-xl p-6 max-w-lg w-full mx-4 shadow-xl flex flex-col gap-4">
              <div className="flex items-center justify-between">
                <h3 className="text-base font-bold text-foreground">No Flowcell ID Detected</h3>
                <button onClick={() => setOntConfirmFiles(null)} className="text-muted-foreground hover:text-foreground transition-colors">
                  <X size={16} />
                </button>
              </div>
              <p className="text-sm text-muted-foreground leading-relaxed">
                None of the uploaded FASTQ files start with a flowcell ID (e.g. <span className="font-mono">FAP12345_…</span>).
                Select the files you want to use anyway — they must still contain a barcode pattern
                (<span className="font-mono">_barcode##_</span>) to populate the sample sheet.
              </p>
              <div className="flex items-center justify-between">
                <label className="flex items-center gap-2 text-sm font-medium text-foreground cursor-pointer">
                  <input type="checkbox" checked={allSelected} onChange={toggleAll} className="accent-primary" />
                  Select all
                </label>
                <span className="text-xs text-muted-foreground">{ontConfirmSelected.size} of {ontConfirmFiles.length} selected</span>
              </div>
              <div className="rounded-lg border border-border divide-y divide-border max-h-64 overflow-y-auto">
                {ontConfirmFiles.map(({ name }) => (
                  <label key={name} className="flex items-center gap-2 px-3 py-2 text-xs font-mono cursor-pointer hover:bg-muted/40 transition-colors">
                    <input type="checkbox" checked={ontConfirmSelected.has(name)} onChange={() => toggleName(name)} className="accent-primary shrink-0" />
                    <span className="break-all">{name}</span>
                  </label>
                ))}
              </div>
              <div className="flex gap-3 justify-end pt-1">
                <button
                  onClick={() => setOntConfirmFiles(null)}
                  className="px-5 py-2 rounded-lg border border-border text-sm text-muted-foreground hover:bg-muted/60 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={confirmOntFilesWithoutFlowcell}
                  disabled={ontConfirmSelected.size === 0}
                  className="flex items-center gap-1.5 px-5 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Check size={13} /> Use Selected
                </button>
              </div>
            </div>
          </div>
        );
      })()}

      {/* ── Task Progress stdout hover box (streams a task's stdout while hovered) ── */}
      {taskHover !== null && (() => {
        const boxW = 440;
        const boxH = 300;
        const left = Math.min(Math.max(8, taskHover.x + 12), window.innerWidth - boxW - 8);
        const top = Math.min(Math.max(8, taskHover.y), window.innerHeight - boxH - 8);
        const lines = taskHover.data?.lines ?? [];
        return (
          <div
            style={{ left, top, width: boxW, maxHeight: boxH }}
            className="fixed z-[60] pointer-events-none flex flex-col rounded-xl border border-border bg-background shadow-2xl overflow-hidden"
          >
            <div className="flex items-center gap-2 px-3 py-2 border-b border-border bg-muted/30 shrink-0">
              <Terminal size={13} className="text-sky-500 shrink-0" />
              <span className="text-xs font-bold font-mono text-foreground truncate">{taskHover.process}</span>
              {taskHover.sample && <span className="text-xs font-mono text-muted-foreground truncate">({taskHover.sample})</span>}
              {taskHover.loading
                ? <RefreshCw size={11} className="ml-auto shrink-0 text-muted-foreground animate-spin" />
                : <span className="ml-auto shrink-0 flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider text-sky-500"><span className="w-1.5 h-1.5 rounded-full bg-sky-500 animate-pulse" />live</span>}
            </div>
            <div
              ref={el => { if (el) el.scrollTop = el.scrollHeight; }}
              className="flex-1 overflow-auto bg-muted/10 px-3 py-2 font-mono text-[11px] leading-relaxed text-foreground whitespace-pre-wrap break-all"
            >
              {taskHover.error && <span className="text-destructive">{taskHover.error}</span>}
              {!taskHover.error && lines.length === 0 && (
                <span className="text-muted-foreground">{taskHover.loading ? "Loading stdout…" : "No stdout output yet."}</span>
              )}
              {!taskHover.error && lines.map((ln, i) => (
                <div key={i}>{ln.text || "\u00A0"}</div>
              ))}
            </div>
            <div className="px-3 py-1 border-t border-border bg-muted/20 shrink-0 text-[10px] font-mono text-muted-foreground truncate flex items-center gap-2">
              {taskHover.data?.log_file && <span className="truncate">{taskHover.data.log_file}</span>}
              <span className="ml-auto shrink-0 not-italic text-muted-foreground/70">click to open &amp; copy</span>
            </div>
          </div>
        );
      })()}

      {/* ── Task log modal (stdout / error) ────────────── */}
      {taskLog !== null && (
        <div onClick={() => setTaskLog(null)} className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div onClick={(e) => e.stopPropagation()} className="bg-background border border-border rounded-xl p-0 max-w-3xl w-full mx-4 shadow-xl flex flex-col gap-0 max-h-[85vh]">
            <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-muted/20 shrink-0">
              <div className="flex items-center gap-2 min-w-0">
                {taskLog.stream === "stdout"
                  ? <Terminal size={15} className="text-sky-500 shrink-0" />
                  : <AlertCircle size={15} className="text-destructive shrink-0" />}
                <h3 className="text-sm font-bold text-foreground truncate">
                  {taskLog.stream === "stdout" ? "Task Log" : "Task Error"} — <span className="font-mono">{taskLog.process}</span>
                  {taskLog.sample ? <span className="font-mono text-muted-foreground"> ({taskLog.sample})</span> : null}
                </h3>
                {taskLog.data && taskLog.data.exit_code == null && (
                  <span className="flex items-center gap-1 shrink-0 text-[10px] font-semibold uppercase tracking-wider text-sky-500">
                    <span className="h-1.5 w-1.5 rounded-full bg-sky-500 animate-pulse" /> Live
                  </span>
                )}
              </div>
              <button onClick={() => setTaskLog(null)} className="text-muted-foreground hover:text-foreground transition-colors shrink-0">
                <X size={15} />
              </button>
            </div>

            <div className="flex-1 overflow-auto p-4 flex flex-col gap-3">
              {taskLog.loading && (
                <div className="flex items-center gap-2 text-xs text-muted-foreground py-4 justify-center">
                  <RefreshCw size={13} className="animate-spin" /> Loading log…
                </div>
              )}

              {taskLog.error && (
                <div className="rounded-lg border bg-red-50 border-red-200 dark:bg-red-950/20 dark:border-red-800 px-3 py-2 flex items-start gap-2 text-xs">
                  <AlertCircle size={12} className="shrink-0 mt-0.5 text-destructive" />
                  <span className="text-destructive">{taskLog.error}</span>
                </div>
              )}

              {taskLog.data && (
                <>
                  {/* file metadata */}
                  <div className="rounded-lg border border-border bg-muted/10 px-3 py-2 space-y-1 text-xs">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground shrink-0">File</span>
                      <span className="font-mono font-semibold text-foreground">{taskLog.data.log_file}</span>
                      {taskLog.data.exit_code != null && (
                        <span className="ml-auto px-1.5 py-0.5 rounded bg-red-100 text-red-700 dark:bg-red-900/20 dark:text-red-400 font-mono shrink-0">exit {taskLog.data.exit_code}</span>
                      )}
                    </div>
                    <div className="flex items-start gap-2">
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground shrink-0 mt-0.5">Path</span>
                      <span className="font-mono text-muted-foreground break-all">{taskLog.data.log_path}</span>
                    </div>
                  </div>

                  {/* related error lines */}
                  {taskLog.data.error_lines?.length > 0 && (
                    <div>
                      <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1">Related Errors</p>
                      <div className="rounded-lg border border-red-200 dark:border-red-800 overflow-hidden">
                        <table className="w-full text-xs font-mono">
                          <tbody>
                            {taskLog.data.error_lines.map((ln, i) => (
                              <tr key={i} className="border-b border-red-100 dark:border-red-900/40 last:border-b-0 bg-red-50/50 dark:bg-red-950/10">
                                <td className="px-2 py-1 text-left text-red-400 select-none align-top w-12 shrink-0">{ln.line_number}</td>
                                <td className="px-2 py-1 text-red-700 dark:text-red-300 whitespace-pre-wrap break-all">{ln.text}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {/* full log */}
                  {taskLog.data.lines?.length > 0 && (
                    <div>
                      <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1">Log ({taskLog.data.log_file})</p>
                      <div ref={taskLogBodyRef} onScroll={onTaskLogScroll} className="rounded-lg border border-border overflow-auto max-h-96 bg-muted/10">
                        <table className="w-full text-xs font-mono">
                          <tbody>
                            {taskLog.data.lines.map((ln, i) => (
                              <tr key={i} className="hover:bg-muted/30">
                                <td className="px-2 py-0.5 text-left text-muted-foreground/60 select-none align-top w-12 shrink-0">{ln.line_number}</td>
                                <td className="px-2 py-0.5 text-foreground whitespace-pre-wrap break-all">{ln.text}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {(!taskLog.data.lines?.length && !taskLog.data.error_lines?.length) && (
                    <p className="text-xs text-muted-foreground text-left py-3">The log file is empty or could not be read.</p>
                  )}
                </>
              )}
            </div>

            <div className="flex justify-end gap-2 px-4 py-3 border-t border-border bg-muted/10 shrink-0">
              <button
                onClick={copyTaskLog}
                disabled={!taskLog.data?.lines?.length}
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg border border-border text-xs text-muted-foreground hover:bg-muted/60 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {taskLogCopied ? <><Check size={13} className="text-emerald-500" /> Copied</> : <><Copy size={13} /> Copy log</>}
              </button>
              <button
                onClick={() => setTaskLog(null)}
                className="px-4 py-1.5 rounded-lg border border-border text-xs text-muted-foreground hover:bg-muted/60 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Confirm Remove Sample modal ────────────── */}
      {confirmRemoveIdx !== null && (() => {
        const isOnt = experimentType.toLowerCase().endsWith("ont");
        const sample = (isOnt ? ontSampleRows : illuminaSampleRows)[confirmRemoveIdx];
        return (
          <div onClick={() => setConfirmRemoveIdx(null)} className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
            <div onClick={(e) => e.stopPropagation()} className="bg-background border border-border rounded-xl p-8 max-w-lg w-full mx-4 shadow-xl flex flex-col gap-5">
              <div className="flex items-center justify-between">
                <h3 className="text-base font-bold text-foreground">Remove Sample</h3>
                <button onClick={() => setConfirmRemoveIdx(null)} className="text-muted-foreground hover:text-foreground transition-colors">
                  <X size={16} />
                </button>
              </div>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Are you sure you want to remove{" "}
                <span className="font-mono font-semibold text-foreground">{sample?.sample_id ?? "this sample"}</span>{" "}
                from the sample sheet?
                {!isNewRun && (
                  <>
                    {" This will permanently remove the sample from the database storage. To deselect a sample, just toggle the "}
                    <span className="font-mono font-semibold text-foreground">'Keep'</span> status to switch its status to <span className="font-mono font-semibold text-foreground">'exclude'</span>.
                  </>
                )}
              </p>
              <div className="flex gap-3 justify-end pt-2">
                <button
                  onClick={() => setConfirmRemoveIdx(null)}
                  className="px-5 py-2 rounded-lg border border-border text-sm text-muted-foreground hover:bg-muted/60 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={confirmRemoveSample}
                  className="flex items-center gap-1.5 px-5 py-2 rounded-lg bg-destructive text-destructive-foreground text-sm font-semibold hover:bg-destructive/90 transition-colors"
                >
                  <Trash2 size={13} /> Remove
                </button>
              </div>
            </div>
          </div>
        );
      })()}
    </div>
  );
}

/* ── SeqSender Tab ──────────────────────────────── */
const ORGANISMS = [
  { value: "FLU", label: "INFLUENZA" },
  { value: "COV", label: "SARS-COV-2" },
  { value: "RSV", label: "RSV" },
];

// Database targets for SeqSender submission, with links to their respective websites
const DB_LIST = [
  { key: "biosample", value: "BIOSAMPLE", label: "BioSample", url: "https://www.ncbi.nlm.nih.gov/biosample/"},
  { key: "sra", value: "SRA", label: "SRA", url: "https://www.ncbi.nlm.nih.gov/sra/ "},
  { key: "genbank", value: "GENBANK", label: "GenBank", url: "https://www.ncbi.nlm.nih.gov/genbank/"},
  //{ key: "gisaid", value: "GISAID", label: "GISAID", url: "https://www.gisaid.org/"},
];

// Collapsible section header — click to toggle the section's content below it.
function SectionHeader({ title, icon: Icon, open, onToggle, widthClass = "w-full", id }) {
  return (
    <button
      type="button"
      id={id}
      onClick={onToggle}
      className={cn(widthClass, "flex items-center gap-2 pt-1 text-left bg-transparent")}
    >
      {Icon && <Icon size={13} className="shrink-0 text-muted-foreground" />}
      <span className="text-xs font-bold tracking-wider text-muted-foreground uppercase">{title}</span>
      <div className="flex-1 h-px bg-border" />
      <ChevronDown size={13} className={cn("shrink-0 text-muted-foreground transition-transform", !open && "-rotate-90")} />
    </button>
  );
}

// Pick an existing submitter (by portal), used by the NCBI/GISAID credential
// blocks' "Existing User" mode.
function ExistingSubmitterPicker({ submitters, loading, error, selectedId, onSelect, placeholder, disabled = false }) {
  return (
    <div>
      <select
        value={selectedId}
        onChange={(e) => {
          const selected = submitters.find((submitter) => String(submitter.submitter_id) === e.target.value);
          if (selected) onSelect(selected);
        }}
        disabled={disabled || loading || !!error || submitters.length === 0}
        className="w-full h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-60 disabled:cursor-not-allowed disabled:bg-muted"
      >
        <option value="">{loading ? "Loading submitters…" : placeholder}</option>
        {submitters.map((submitter) => (
          <option key={submitter.submitter_id} value={String(submitter.submitter_id)}>
            {submitter.submitter_name}
          </option>
        ))}
      </select>
      {error && <p className="mt-1 text-xs text-destructive">{error}</p>}
      {!loading && !error && submitters.length === 0 && (
        <p className="mt-1 text-xs text-muted-foreground">No existing submitters found.</p>
      )}
    </div>
  );
}

// Badge color classes for a submission/database status value, shared by the Submission Status cards.
const SUBMISSION_STATUS_BADGE_STYLES = {
  PENDING:    "bg-muted text-muted-foreground",
  CREATED:    "bg-muted text-muted-foreground",
  PROCESSING: "bg-sky-100 text-sky-700 dark:bg-sky-900/20 dark:text-sky-400",
  SUBMITTED:  "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/20 dark:text-emerald-400",
  COMPLETED:  "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/20 dark:text-emerald-400",
  FAILED:     "bg-red-100 text-red-700 dark:bg-red-900/20 dark:text-red-400",
  CANCELED:   "bg-muted text-muted-foreground",
};

const SEQSENDER_METADATA_TABLES = [
  { key: "biosample", title: "BioSample Metadata", prefixes: ["bs-"], sampleNameColumn: "bs-sample_name" },
  { key: "sra", title: "SRA Metadata", prefixes: ["sra-"], sampleNameColumn: "sra-sample_name" },
  { key: "genbank", title: "GenBank Metadata", prefixes: ["gb-", "src-", "cmt-"], sampleNameColumn: "gb-sample_name" },
  { key: "gisaid", title: "GISAID Metadata", prefixes: ["gs-"], sampleNameColumn: "gs-sample_name" },
];

const SEQSENDER_DATABASE_PREFIXES = SEQSENDER_METADATA_TABLES.flatMap(({ prefixes }) => prefixes);

function SeqSenderMetadataTable({ title, columns, rows, onRemoveRows, onUndoRows, canUndo = false, editable = true, sampleNameColumn }) {
  const pageSize = 10;
  const [page, setPage] = useState(0);
  const [searchQuery, setSearchQuery] = useState("");
  const [sortColumn, setSortColumn] = useState(null);
  const [sortDirection, setSortDirection] = useState("asc");
  const [selectedRows, setSelectedRows] = useState(() => new Set());

  const filteredRows = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) return rows;
    return rows.filter((row) => columns.some((column) =>
      String(row[column] ?? "").toLowerCase().includes(query)
    ));
  }, [columns, rows, searchQuery]);

  const sortedRows = useMemo(() => {
    if (!sortColumn) return filteredRows;
    return [...filteredRows].sort((firstRow, secondRow) => {
      const firstValue = firstRow[sortColumn] ?? "";
      const secondValue = secondRow[sortColumn] ?? "";
      const firstNumber = Number(firstValue);
      const secondNumber = Number(secondValue);
      const bothNumeric = firstValue !== "" && secondValue !== "" && Number.isFinite(firstNumber) && Number.isFinite(secondNumber);
      const comparison = bothNumeric
        ? firstNumber - secondNumber
        : String(firstValue).localeCompare(String(secondValue), undefined, { numeric: true, sensitivity: "base" });
      return sortDirection === "asc" ? comparison : -comparison;
    });
  }, [filteredRows, sortColumn, sortDirection]);

  const totalPages = Math.max(1, Math.ceil(sortedRows.length / pageSize));
  const pageRows = sortedRows.slice(page * pageSize, (page + 1) * pageSize);
  const allPageRowsSelected = pageRows.length > 0 && pageRows.every((row) => selectedRows.has(row));
  const somePageRowsSelected = pageRows.some((row) => selectedRows.has(row)) && !allPageRowsSelected;

  const handleSort = (column) => {
    if (sortColumn === column) {
      if (sortDirection === "asc") {
        setSortDirection("desc");
      } else {
        setSortColumn(null);
        setSortDirection("asc");
      }
    } else {
      setSortColumn(column);
      setSortDirection("asc");
    }
    setPage(0);
  };

  const toggleRow = (row) => {
    setSelectedRows((current) => {
      const next = new Set(current);
      if (next.has(row)) next.delete(row);
      else next.add(row);
      return next;
    });
  };

  const togglePageRows = () => {
    setSelectedRows((current) => {
      const next = new Set(current);
      if (allPageRowsSelected) pageRows.forEach((row) => next.delete(row));
      else pageRows.forEach((row) => next.add(row));
      return next;
    });
  };

  const removeSelectedRows = () => {
    if (!selectedRows.size) return;
    onRemoveRows?.([...selectedRows], sampleNameColumn);
    setSelectedRows(new Set());
  };

  useEffect(() => {
    setPage(0);
    setSelectedRows(new Set());
  }, [editable, rows]);

  return (
    <div className="w-full overflow-hidden rounded-lg border border-border">
      <div className="flex items-center justify-between gap-3 border-b border-border bg-muted/20 px-3 py-2">
        <div className="flex min-w-0 items-center gap-2">
          <Database size={13} className="shrink-0 text-primary" />
          <p className="truncate text-xs font-bold text-foreground">{title}</p>
        </div>
        <span className="shrink-0 text-[10px] text-muted-foreground">
          {searchQuery ? `${filteredRows.length.toLocaleString()} of ` : ""}{rows.length.toLocaleString()} rows · {columns.length.toLocaleString()} columns
        </span>
      </div>
      <div className="border-b border-border bg-muted/10 px-3 py-2">
        <div className="relative">
          <FileSearch size={12} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            type="search"
            value={searchQuery}
            onChange={(event) => {
              setSearchQuery(event.target.value);
              setPage(0);
            }}
            placeholder={`Search ${title}…`}
            aria-label={`Search ${title}`}
            className="h-7 w-full rounded-md border border-border bg-background pl-7 pr-7 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-ring"
          />
          {searchQuery && (
            <button
              type="button"
              title="Clear search"
              aria-label={`Clear ${title} search`}
              onClick={() => {
                setSearchQuery("");
                setPage(0);
              }}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground transition-colors hover:text-foreground"
            >
              <X size={11} />
            </button>
          )}
        </div>
      </div>
      <div className="max-h-72 overflow-auto">
        <table className="min-w-max border-collapse text-xs">
          <thead className="sticky top-0 z-10 bg-muted">
            <tr>
              {editable && (
                <th className="w-9 border-b border-r border-border px-3 py-2">
                  <input
                    ref={(input) => {
                      if (input) input.indeterminate = somePageRowsSelected;
                    }}
                    type="checkbox"
                    checked={allPageRowsSelected}
                    disabled={pageRows.length === 0}
                    onChange={togglePageRows}
                    aria-label={`Select all ${title} rows on this page`}
                    className="block accent-primary disabled:cursor-not-allowed"
                  />
                </th>
              )}
              {columns.map((column) => (
                <th key={column} className="max-w-52 whitespace-nowrap border-b border-r border-border p-0 text-left font-mono text-[10px] font-semibold text-muted-foreground last:border-r-0">
                  <button
                    type="button"
                    title={`Sort by ${column}`}
                    aria-label={`Sort ${title} by ${column}${sortColumn === column ? `, currently ${sortDirection}ending` : ""}`}
                    onClick={() => handleSort(column)}
                    className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left transition-colors hover:bg-muted/70 hover:text-foreground"
                  >
                    <span className="truncate">{column}</span>
                    {sortColumn === column
                      ? sortDirection === "asc"
                        ? <ArrowUp size={10} className="shrink-0 text-primary" />
                        : <ArrowDown size={10} className="shrink-0 text-primary" />
                      : <ArrowUpDown size={10} className="shrink-0 opacity-35" />}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {pageRows.map((row, rowIndex) => (
              <tr
                key={rows.indexOf(row)}
                aria-selected={editable ? selectedRows.has(row) : undefined}
                onClick={editable ? () => toggleRow(row) : undefined}
                className={cn(
                  editable && "cursor-pointer transition-colors hover:bg-muted/20",
                  editable && selectedRows.has(row) && "bg-primary/10 hover:bg-primary/15"
                )}
              >
                {editable && (
                  <td className="w-9 border-r border-border px-3 py-2">
                    <input
                      type="checkbox"
                      checked={selectedRows.has(row)}
                      onChange={() => toggleRow(row)}
                      onClick={(event) => event.stopPropagation()}
                      aria-label={`Select ${title} row ${page * pageSize + rowIndex + 1}`}
                      className="block accent-primary"
                    />
                  </td>
                )}
                {columns.map((column) => (
                  <td key={column} title={String(row[column] ?? "")} className="max-w-52 truncate whitespace-nowrap border-r border-border px-3 py-2 font-mono text-[11px] text-foreground last:border-r-0">
                    {row[column] || <span className="text-muted-foreground/50">—</span>}
                  </td>
                ))}
              </tr>
            ))}
            {pageRows.length === 0 && (
              <tr>
                <td colSpan={Math.max(1, columns.length + (editable ? 1 : 0))} className="px-3 py-8 text-center text-xs text-muted-foreground">
                  {searchQuery ? `No metadata rows match “${searchQuery}”.` : "No metadata rows remain."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <div className={cn("flex items-center gap-3 border-t border-border bg-muted/10 px-3 py-1.5", editable ? "justify-between" : "justify-end")}>
        {editable && (
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              disabled={selectedRows.size === 0}
              onClick={removeSelectedRows}
              className="flex h-6 items-center gap-1 rounded border border-red-200 px-2 text-[10px] font-medium text-destructive transition-colors hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-40 dark:border-red-800 dark:hover:bg-red-950/20"
            >
              <Trash2 size={11} />
              Remove{selectedRows.size > 0 ? ` (${selectedRows.size})` : ""}
            </button>
            <button
              type="button"
              disabled={!canUndo}
              onClick={onUndoRows}
              title="Restore the original metadata worksheet"
              className="flex h-6 items-center gap-1 rounded border border-border px-2 text-[10px] font-medium text-muted-foreground transition-colors hover:border-primary hover:text-primary disabled:cursor-not-allowed disabled:opacity-40"
            >
              <Undo2 size={11} />
              Undo
            </button>
          </div>
        )}
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-muted-foreground">Page {page + 1} of {totalPages}</span>
          <button type="button" title="Previous page" disabled={page === 0} onClick={() => setPage((value) => value - 1)} className="flex h-6 w-6 items-center justify-center rounded border border-border text-muted-foreground hover:text-primary disabled:cursor-not-allowed disabled:opacity-40">
            <ChevronLeft size={12} />
          </button>
          <button type="button" title="Next page" disabled={page >= totalPages - 1} onClick={() => setPage((value) => value + 1)} className="flex h-6 w-6 items-center justify-center rounded border border-border text-muted-foreground hover:text-primary disabled:cursor-not-allowed disabled:opacity-40">
            <ChevronRight size={12} />
          </button>
        </div>
      </div>
    </div>
  );
}

// Roll up a submission's per-database rows into a single overall status/message,
// used to seed and refresh the Submission Status banner for a selected past submission.
function deriveOverallSubmissionStatus(rows) {
  if (!rows || rows.length === 0) return null;
  const statuses = rows.map((row) => row.submission_status);
  const status = statuses.includes("FAILED")
    ? "FAILED"
    : statuses.includes("PROCESSING")
      ? "PROCESSING"
      : statuses.every((s) => s === "SUBMITTED" || s === "COMPLETED")
        ? "SUBMITTED"
        : statuses[0] ?? "CREATED";
  return { status, pid: null, return_code: null};
}

// Section keys/labels/icons for the SeqSender "Jump To" step links, shared by SeqSenderTab and SeqSenderPanel.
const SEQSENDER_SECTIONS = [
  { key: "database",    label: "Database Targets",       icon: Database },
  { key: "pathogen",    label: "Pathogen",               icon: FlaskConical },
  { key: "credentials", label: "Submission Credentials", icon: ShieldCheck },
  { key: "inputs",      label: "Submission Inputs",      icon: Upload },
  { key: "options",     label: "Submission Options",     icon: Settings2 },
  { key: "submit",      label: "Review & Submit",        icon: Rocket },
  { key: "status",      label: "Submission Status",      icon: ClipboardList },
];

// Normalize a collection_date value into ISO 8601 (YYYY-MM-DD) so SeqSender's metadata
// validator accepts it regardless of the format it was entered/uploaded in (e.g. MM/DD/YYYY).
// Values already in ISO form (YYYY-MM-DD, YYYY-MM, or YYYY) and unrecognized formats are left
// untouched so SeqSender can surface a clear validation error for anything we can't confidently convert.
const normalizeCollectionDate = (value) => {
  const raw = String(value ?? "").trim();
  if (!raw || /^\d{4}(-\d{2}(-\d{2})?)?$/.test(raw)) return raw;
  // MM/DD/YYYY or M/D/YYYY (also accepts "-" or "." as the separator).
  let match = raw.match(/^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})$/);
  if (match) {
    const [, month, day, year] = match;
    return `${year}-${month.padStart(2, "0")}-${day.padStart(2, "0")}`;
  }
  // YYYY/MM/DD or YYYY.MM.DD (year-first, but not already dash-separated ISO).
  match = raw.match(/^(\d{4})[/.](\d{1,2})[/.](\d{1,2})$/);
  if (match) {
    const [, year, month, day] = match;
    return `${year}-${month.padStart(2, "0")}-${day.padStart(2, "0")}`;
  }
  return raw;
};

// Per-database submission status report (Sample/Status/Accession/Message) — sortable by any
// column, with an editable Message column (local edits only; reset whenever a fresh status
// check replaces the underlying rows).
const STATUS_REPORT_COLUMNS = [
  { key: "sample_name", label: "Sample" },
  { key: "status", label: "Status" },
  { key: "accession", label: "Accession" },
  { key: "message", label: "Message" },
];

function StatusReportTable({ rows, onMessageChange }) {
  const [sortColumn, setSortColumn] = useState(null);
  const [sortDir, setSortDir] = useState("asc");
  const [editedMessages, setEditedMessages] = useState({}); // row index (within `rows`) -> edited message text

  // A fresh status check replaced the underlying rows — drop any local message edits.
  useEffect(() => { setEditedMessages({}); }, [rows]);

  const handleSort = (key) => {
    if (sortColumn === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortColumn(key);
      setSortDir("asc");
    }
  };

  // Sort a copy that still carries each row's original index, so edits stay tied to the right row after sorting.
  const sortedRows = rows
    .map((row, index) => ({ row, index }))
    .sort((a, b) => {
      if (!sortColumn) return 0;
      const av = String(a.row[sortColumn] ?? "").toLowerCase();
      const bv = String(b.row[sortColumn] ?? "").toLowerCase();
      const comparison = av.localeCompare(bv, undefined, { numeric: true, sensitivity: "base" });
      return sortDir === "asc" ? comparison : -comparison;
    });

  // The Message column reflects any local edits, so exports match what's currently shown.
  const messageFor = (row, index) => editedMessages[index] ?? row.message ?? "";

  const downloadCSV = () => {
    const csv = [
      STATUS_REPORT_COLUMNS.map(({ label }) => `"${label}"`).join(","),
      ...sortedRows.map(({ row, index }) => STATUS_REPORT_COLUMNS.map(({ key }) => {
        const v = key === "message" ? messageFor(row, index) : (row[key] ?? "");
        return `"${String(v).replace(/"/g, '""')}"`;
      }).join(",")),
    ].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = "status_report.csv"; a.click();
    URL.revokeObjectURL(url);
  };

  const downloadExcel = () => {
    const html = `<html><head><meta charset="utf-8"></head><body><table><tr>${
      STATUS_REPORT_COLUMNS.map(({ label }) => `<th>${label}</th>`).join("")
    }</tr>${
      sortedRows.map(({ row, index }) => `<tr>${
        STATUS_REPORT_COLUMNS.map(({ key }) => `<td>${key === "message" ? messageFor(row, index) : (row[key] ?? "")}</td>`).join("")
      }</tr>`).join("")
    }</table></body></html>`;
    const blob = new Blob([html], { type: "application/vnd.ms-excel;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = "status_report.xls"; a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="rounded-lg border border-border overflow-hidden">
      <div className="flex items-center gap-1.5 px-2 py-1 border-b border-border bg-muted/20">
        <button
          type="button"
          onClick={downloadCSV}
          className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] border border-border text-muted-foreground hover:border-primary hover:text-primary transition-colors"
        >
          <Download size={10} /> CSV
        </button>
        <button
          type="button"
          onClick={downloadExcel}
          className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] border border-border text-muted-foreground hover:border-primary hover:text-primary transition-colors"
        >
          <Download size={10} /> Excel
        </button>
      </div>
      <div className="overflow-auto max-h-48">
        <table className="w-full text-[11px]">
          <thead className="sticky top-0 bg-muted text-foreground">
            <tr>
              {STATUS_REPORT_COLUMNS.map(({ key, label }) => (
                <th key={key} className="px-2 py-1 text-left font-semibold">
                  <button
                    type="button"
                    onClick={() => handleSort(key)}
                    className="flex items-center gap-1 hover:text-primary transition-colors"
                  >
                    {label}
                    {sortColumn === key
                      ? sortDir === "asc" ? <ArrowUp size={9} className="text-primary shrink-0" /> : <ArrowDown size={9} className="text-primary shrink-0" />
                      : <ArrowUpDown size={9} className="opacity-30 shrink-0" />}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {sortedRows.map(({ row, index }) => (
              <tr key={index}>
                <td className="px-2 py-1 font-mono text-foreground whitespace-nowrap align-top">{row.sample_name || "—"}</td>
                <td className="px-2 py-1 font-mono text-foreground whitespace-nowrap align-top">{row.status || "—"}</td>
                <td className="px-2 py-1 font-mono text-foreground whitespace-nowrap align-top">{row.accession || "—"}</td>
                <td className="px-2 py-1 text-muted-foreground align-top">
                  <textarea
                    value={editedMessages[index] ?? row.message ?? ""}
                    onChange={(e) => {
                      const message = e.target.value;
                      setEditedMessages((prev) => ({ ...prev, [index]: message }));
                      if (row.sample_name) onMessageChange?.(row.sample_name, message);
                    }}
                    placeholder="—"
                    rows={1}
                    className="w-full min-w-[140px] resize-y rounded border border-border bg-transparent px-1 py-0.5 text-[11px] leading-snug text-muted-foreground whitespace-pre-wrap break-words focus:border-primary focus:bg-background focus:outline-none focus:ring-1 focus:ring-ring"
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── SeqSender form — opened from the Step 5 action button ──
const SeqSenderPanel = forwardRef(function SeqSenderPanel(props, ref) {
  const initialSubmission = props.initialSubmission ?? null;
  const initialRows = initialSubmission?.rows ?? [];
  const initialDatabases = new Set(initialRows.map((row) => row.database));
  const initialNcbiRow = initialRows.find((row) => row.submission_portal === "NCBI") ?? null;
  const initialGisaidRow = initialRows.find((row) => row.submission_portal === "GISAID") ?? null;
  const storedSubmissionQuery = (() => {
    if (!initialSubmission) return "";
    const params = new URLSearchParams();
    params.set("submission_name", initialSubmission.submission_name);
    params.set("organism", initialSubmission.organism);
    [...new Set(initialRows.map((row) => row.database).filter(Boolean))]
      .forEach((database) => params.append("database", database));
    params.set("submission_type", initialSubmission.submission_type);
    return params.toString();
  })();
  const storedDownloadUrl = (endpoint, extraParams = {}) => {
    if (!storedSubmissionQuery) return "";
    const params = new URLSearchParams(storedSubmissionQuery);
    Object.entries(extraParams).forEach(([key, value]) => params.set(key, value));
    return `${endpoint}?${params.toString()}`;
  };
  const [storedDownloadError, setStoredDownloadError] = useState(null); // { field, message } for a failed stored-file download
  const [storedDownloading, setStoredDownloading] = useState(null); // field currently downloading
  const [existingRows, setExistingRows] = useState(initialRows); // per-database status rows for a selected past submission, refetchable
  const [existingStatusRefreshing, setExistingStatusRefreshing] = useState(false);
  const [existingStatusError, setExistingStatusError] = useState(null);
  const [metadataPreview, setMetadataPreview] = useState({ columns: [], rows: [], loading: false, error: null });

  // Ask SeqSender to check the remote submission portals and return the latest status.
  const refreshSubmissionStatus = async () => {
    const params = submissionJob
      ? (() => {
          const query = new URLSearchParams();
          query.set("submission_name", submissionJob.submission_name);
          query.set("organism", submissionJob.organism);
          submissionJob.database.forEach((database) => query.append("database", database));
          query.set("submission_type", submissionJob.submission_type);
          return query;
        })()
      : new URLSearchParams(storedSubmissionQuery);
    if (!params.get("submission_name")) return;
    setExistingStatusRefreshing(true);
    setExistingStatusError(null);
    try {
      const res = await fetch(`${API.checkSeqsenderSubmissionStatus}?${params.toString()}`);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || data.message || "Failed to refresh submission status.");
      setRefreshedSubmissionStatus(data);
      setSubmissionStatusError(null);
      if (data.database_statuses && typeof data.database_statuses === "object") {
        setExistingRows((rows) => rows.map((row) => {
          const entry = data.database_statuses[row.database];
          return {
            ...row,
            submission_status: entry?.status ?? row.submission_status,
            ncbi_submission_id: entry?.accession || row.ncbi_submission_id,
          };
        }));
      }
      // The status report table was just re-pulled from SeqSender — drop any unsaved local
      // message edits for those databases so stale edits aren't later saved over fresh rows.
      if (data.submission_status_report && typeof data.submission_status_report === "object") {
        setStatusReportMessageEdits((prev) => {
          const next = { ...prev };
          Object.keys(data.submission_status_report).forEach((database) => { next[database] = {}; });
          return next;
        });
      }
      props.onSubmitted?.();
    } catch (err) {
      setExistingStatusError(err.message || "Failed to refresh submission status.");
    } finally {
      setExistingStatusRefreshing(false);
    }
  };

  // Load whatever submission/status info is already stored locally for a selected past
  // submission — no external SeqSender CLI call, so this is fast and safe to run on open.
  const loadSubmissionStatus = async () => {
    if (!storedSubmissionQuery) return;
    setExistingStatusRefreshing(true);
    setExistingStatusError(null);
    try {
      const [submissionRes, statusRes] = await Promise.all([
        fetch(`${API.retrieveSeqsenderSubmission}?${storedSubmissionQuery}`),
        fetch(`${API.loadSeqsenderSubmissionStatus}?${storedSubmissionQuery}`),
      ]);
      const submissionData = await submissionRes.json().catch(() => ({}));
      if (submissionRes.ok && Array.isArray(submissionData?.submission_info) && submissionData.submission_info.length) {
        setExistingRows(submissionData.submission_info);
        // Populate each database's Comments box from the freshly loaded submission record.
        setComments((prev) => {
          const next = { ...prev };
          submissionData.submission_info.forEach((row) => { if (row.database) next[row.database] = row.comments ?? ""; });
          return next;
        });
      }
      const data = await statusRes.json().catch(() => ({}));
      if (!statusRes.ok) throw new Error(data.detail || data.message || "Failed to load submission status.");
      // This is a silent background load (not a user-initiated "Refresh Status" click), so
      // suppress the status message banner on success — only surface it via refreshSubmissionStatus.
      setRefreshedSubmissionStatus({ ...data, message: null });
      setSubmissionStatusError(null);
      if (data.database_statuses && typeof data.database_statuses === "object") {
        setExistingRows((rows) => rows.map((row) => {
          const entry = data.database_statuses[row.database];
          return {
            ...row,
            submission_status: entry?.status ?? row.submission_status,
            ncbi_submission_id: entry?.accession || row.ncbi_submission_id,
          };
        }));
      }
    } catch (err) {
      setExistingStatusError(err.message || "Failed to load submission status.");
    } finally {
      setExistingStatusRefreshing(false);
    }
  };

  // Fetch a stored submission file and either trigger its download or surface the API's error message —
  // a plain <a download> can't show why a download failed (e.g. the file was moved/deleted).
  const downloadStoredFile = async (url, field, fallbackName) => {
    if (!url) return;
    setStoredDownloadError(null);
    setStoredDownloading(field);
    try {
      const res = await fetch(url);
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setStoredDownloadError({ field, message: data.detail || `Failed to download file (HTTP ${res.status})` });
        return;
      }
      const blob = await res.blob();
      const disposition = res.headers.get("Content-Disposition") || "";
      const match = disposition.match(/filename\*?="?([^";]+)"?/i);
      const filename = match ? match[1] : fallbackName;
      const blobUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = blobUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(blobUrl);
    } catch (err) {
      setStoredDownloadError({ field, message: err.message || "Failed to download file." });
    } finally {
      setStoredDownloading(null);
    }
  };
  const [dbs, setDbs] = useState(() => initialSubmission ? {
    biosample: initialDatabases.has("BIOSAMPLE"),
    sra: initialDatabases.has("SRA"),
    genbank: initialDatabases.has("GENBANK"),
    gisaid: initialDatabases.has("GISAID"),
  } : { biosample: true, sra: true, genbank: true, gisaid: false });
  const [organism, setOrganism]             = useState(initialSubmission?.organism ?? "FLU"); // default to Influenza
  const [subName, setSubName]               = useState(initialSubmission?.submission_name ?? "");
  const [metaFile, setMetaFile]             = useState(initialSubmission ? "metadata.csv (stored)" : "");
  const [metaFileObject, setMetaFileObject] = useState(null); // File object for the selected Metadata File, for actual upload
  const [fastaFile, setFastaFile]           = useState(initialSubmission ? "sequence.fasta (stored)" : "");
  const [fastaFileObject, setFastaFileObject] = useState(null); // File object for the selected FASTA File, for actual upload
  const [rawReadsFiles, setRawReadsFiles]     = useState(initialDatabases.has("SRA") ? "FASTQ files (stored)" : ""); // multiple raw FASTQ read files for SRA submission
  const [rawReadsFileObjects, setRawReadsFileObjects] = useState([]); // File objects for the selected Raw Reads files, for actual upload
  const [gisaidCliFile, setGisaidCliFile]             = useState("");
  const [gisaidCliFileObject, setGisaidCliFileObject] = useState(null); // File object for the selected GISAID CLI file, for actual upload
  const [gisaidCliMode, setGisaidCliMode]   = useState(initialDatabases.has("GISAID") ? "existing" : "new"); // "new" | "existing" — reuse the CLI already stored for this organism
  const [gffFile, setGffFile]               = useState(initialRows.some((row) => row.gff_file) ? "annotation.gff (stored)" : "");
  const [gffFileObject, setGffFileObject]   = useState(null);
  const [table2asn, setTable2asn]           = useState(initialRows.some((row) => row.table2asn));
  const [testMode, setTestMode]             = useState(initialSubmission ? initialSubmission.submission_type === "TEST" : true);
  const [submitted, setSubmitted]           = useState(false);
  const [submissionJob, setSubmissionJob]   = useState(null);

  // Whether the loaded past submission's rows (or, for this session's own submission,
  // its confirmed "SUBMITTED" status) still allow editing the metadata table.
  const canEditSubmission = (!initialSubmission || (
    existingRows.length > 0
    && existingRows.every((row) => ["FAILED", "CREATED"].includes(row.submission_status))
  )) && !submitted;

  // Stricter than canEditSubmission: Create Files / Submit are only offered for a brand-new
  // submission, or a past submission that's still entirely CREATED (never actually submitted).
  // Once this session's own submission is confirmed SUBMITTED, lock the whole form.
  const canCreateOrSubmit = (!initialSubmission || (
    existingRows.length > 0
    && existingRows.every((row) => row.submission_status === "CREATED")
  )) && !submitted;

  // Seed from the selected past submission's stored per-database rows so the status banner/cards
  // reflect it immediately, without waiting for a fresh submit or a manual "Refresh Status" click.
  const [submissionProcessStatus, setSubmissionProcessStatus] = useState(() => deriveOverallSubmissionStatus(initialRows));
  // Result of an explicit "Refresh Status" check, kept separate so it doesn't clobber
  // submissionProcessStatus (also written by the live-submission process poller).
  const [refreshedSubmissionStatus, setRefreshedSubmissionStatus] = useState(null);
  const [submissionPolling, setSubmissionPolling] = useState(false);
  const [submissionStatusError, setSubmissionStatusError] = useState(null);
  const [submitError, setSubmitError]       = useState(null); // missing required field messages, shown before final submit
  const [uploadingFiles, setUploadingFiles] = useState(false); // uploading submission files to the backend
  const [uploadError, setUploadError]       = useState(null);
  // "Create submission files" — preps SeqSender's per-database submission files without actually submitting.
  const [creatingFiles, setCreatingFiles]   = useState(false);
  const [createFilesResult, setCreateFilesResult] = useState(null); // { status, message, databases }
  const [createFilesError, setCreateFilesError]   = useState(null);

  // Free-text comments attached to a submission, editable per-database below each status card.
  const [comments, setComments] = useState(() => {
    const map = {};
    initialRows.forEach((row) => { if (row.database) map[row.database] = row.comments ?? ""; });
    return map;
  });
  const [commentsSaveStatus, setCommentsSaveStatus] = useState({}); // database -> "idle" | "saving" | "saved" | "error"
  const [commentsSaveError, setCommentsSaveError] = useState({}); // database -> error message
  const [statusReportMessageEdits, setStatusReportMessageEdits] = useState({}); // database -> sample_name -> edited message

  // Persist the Message edits typed into a database's StatusReportTable, keyed by sample_name,
  // into the on-disk submission_status_report.csv (separate from the submission's own comments).
  const saveStatusReportMessages = async (database, messagesBySample) => {
    const submissionNameForReport = submissionJob?.submission_name ?? initialSubmission?.submission_name ?? subName;
    const organismForReport = submissionJob?.organism ?? initialSubmission?.organism ?? organism;
    const submissionTypeForReport = submissionJob?.submission_type ?? initialSubmission?.submission_type ?? (testMode ? "TEST" : "PRODUCTION");
    if (!submissionNameForReport || Object.keys(messagesBySample).length === 0) return;
    const res = await fetch(API.updateSeqsenderSubmissionStatusReportMessages, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        submission_name: submissionNameForReport,
        organism: organismForReport,
        database,
        submission_type: submissionTypeForReport,
        messages: messagesBySample,
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || data.message || "Failed to save status report messages.");
  };

  const saveSubmissionComments = async (database) => {
    const submissionNameForComments = submissionJob?.submission_name ?? initialSubmission?.submission_name ?? subName;
    const organismForComments = submissionJob?.organism ?? initialSubmission?.organism ?? organism;
    const submissionTypeForComments = submissionJob?.submission_type ?? initialSubmission?.submission_type ?? (testMode ? "TEST" : "PRODUCTION");
    if (!submissionNameForComments) return;
    setCommentsSaveStatus((prev) => ({ ...prev, [database]: "saving" }));
    setCommentsSaveError((prev) => ({ ...prev, [database]: null }));
    try {
      const res = await fetch(API.updateSeqsenderSubmissionComments, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          submission_name: submissionNameForComments,
          organism: organismForComments,
          database,
          submission_type: submissionTypeForComments,
          comments: comments[database] ?? "",
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || data.message || "Failed to save comments.");
      await saveStatusReportMessages(database, statusReportMessageEdits[database] ?? {});
      setCommentsSaveStatus((prev) => ({ ...prev, [database]: "saved" }));
      setExistingRows((rows) => rows.map((row) => (row.database === database ? { ...row, comments: comments[database] ?? "" } : row)));
      setStatusReportMessageEdits((prev) => ({ ...prev, [database]: {} }));
      // Refresh the Past Submissions list so its cached rows (used to seed this panel on reopen) aren't stale.
      props.onSubmitted?.();
    } catch (err) {
      setCommentsSaveStatus((prev) => ({ ...prev, [database]: "error" }));
      setCommentsSaveError((prev) => ({ ...prev, [database]: err.message || "Failed to save comments." }));
    }
  };

  useEffect(() => {
    let cancelled = false;

    const parseMetadata = (file) => {
      Papa.parse(file, {
        header: true,
        skipEmptyLines: "greedy",
        transformHeader: (header) => header.replace(/^\uFEFF/, "").trim(),
        complete: ({ data, meta, errors }) => {
          if (cancelled) return;
          const columns = (meta.fields ?? []).filter(Boolean);
          const rows = data
            .filter((row) => columns.some((column) => String(row[column] ?? "").trim()))
            .map((row) => ("collection_date" in row ? { ...row, collection_date: normalizeCollectionDate(row.collection_date) } : row));
          const fatalError = errors.find(({ code }) => code === "UndetectableDelimiter" || code === "MissingQuotes");
          setMetadataPreview({
            columns,
            rows,
            loading: false,
            error: fatalError?.message ?? (!columns.length ? "The metadata file does not contain a header row." : null),
          });
        },
        error: (error) => {
          if (!cancelled) setMetadataPreview({ columns: [], rows: [], loading: false, error: error.message || "Failed to read metadata." });
        },
      });
    };

    const loadMetadata = async () => {
      if (metaFileObject) {
        if (/\.xlsx?$/i.test(metaFileObject.name)) {
          setMetadataPreview({ columns: [], rows: [], loading: false, error: "Metadata table preview supports CSV and TSV files." });
          return;
        }
        setMetadataPreview((current) => ({ ...current, loading: true, error: null }));
        parseMetadata(metaFileObject);
        return;
      }
      if (!storedSubmissionQuery) {
        setMetadataPreview({ columns: [], rows: [], loading: false, error: null });
        return;
      }
      setMetadataPreview((current) => ({ ...current, loading: true, error: null }));
      try {
        // no-store: the stored metadata can change between opens of the same submission (e.g.
        // rows removed), but the request URL never changes, so the browser cache must be bypassed.
        const response = await fetch(`${API.downloadSeqsenderMetadata}?${storedSubmissionQuery}`, { cache: "no-store" });
        if (!response.ok) throw new Error("Stored metadata could not be loaded for preview.");
        parseMetadata(await response.blob());
      } catch (error) {
        if (!cancelled) setMetadataPreview({ columns: [], rows: [], loading: false, error: error.message || "Failed to load stored metadata." });
      }
    };

    loadMetadata();
    return () => { cancelled = true; };
  }, [metaFileObject, storedSubmissionQuery]);

  // Memoized so unrelated re-renders (typing in another field, status polling, etc.) don't hand
  // SeqSenderMetadataTable a brand-new `rows` array reference each time — that would trip its
  // "rows changed" effect and silently clear the user's row selection before Remove is clicked.
  const selectedMetadataTables = useMemo(() => SEQSENDER_METADATA_TABLES
    .filter(({ key }) => dbs[key])
    .map((table) => {
      const columns = metadataPreview.columns.filter((column) => {
        // "sequence_name" just repeats the FASTA link across every table — never database-specific.
        if (column.toLowerCase() === "sequence_name") return false;
        const normalizedColumn = column.toLowerCase();
        const isShared = !SEQSENDER_DATABASE_PREFIXES.some((prefix) => normalizedColumn.startsWith(prefix));
        return isShared || table.prefixes.some((prefix) => normalizedColumn.startsWith(prefix));
      });
      // Collapse duplicate rows for the same sample (this database's own sample_name column)
      // down to one row per sample, keeping the most recently seen values.
      const rows = Array.from(
        metadataPreview.rows.reduce((map, row) => map.set(row[table.sampleNameColumn], row), new Map()).values()
      );
      return {
        ...table,
        columns,
        rows,
      };
    }), [metadataPreview.columns, metadataPreview.rows, dbs]);

  // Snapshot of the metadata worksheet as it stood just before the first row removal, so
  // "Undo" can restore it. Cleared once restored, or when a genuinely new file is browsed.
  const [metadataUndoSnapshot, setMetadataUndoSnapshot] = useState(null);

  const removeMetadataRows = (rowsToRemove, sampleNameColumn) => {
    // Filter the master metadata by this database's own sample_name value (not object identity)
    // so the removal reliably matches rows even if they were re-parsed into new row objects.
    const removedSampleNames = new Set(
      rowsToRemove
        .map((row) => row[sampleNameColumn])
        .filter((value) => value !== undefined && value !== null && String(value).trim() !== "")
    );
    const removalSet = new Set(rowsToRemove);
    const remainingRows = (sampleNameColumn && removedSampleNames.size > 0)
      ? metadataPreview.rows.filter((row) => !removedSampleNames.has(row[sampleNameColumn]))
      : metadataPreview.rows.filter((row) => !removalSet.has(row));
    const isTsv = /\.tsv$/i.test(metaFileObject?.name ?? "");
    const fileName = metaFileObject?.name ?? (isTsv ? "metadata.tsv" : "metadata.csv");
    const serializedMetadata = Papa.unparse({
      fields: metadataPreview.columns,
      data: remainingRows.map((row) => metadataPreview.columns.map((column) => row[column] ?? "")),
    }, { delimiter: isTsv ? "\t" : "," });

    // Only capture the pre-removal state once, so undo always restores the very first version.
    setMetadataUndoSnapshot((current) => current ?? {
      rows: metadataPreview.rows,
      fileObject: metaFileObject,
      fileName: metaFile,
    });
    setMetadataPreview((current) => ({ ...current, rows: remainingRows }));
    setMetaFileObject(new File(
      [serializedMetadata],
      fileName,
      { type: isTsv ? "text/tab-separated-values" : "text/csv" }
    ));
    setMetaFile(fileName);
    setSubmitError(null);
  };

  // Restore the metadata worksheet to how it stood before any rows were removed this session.
  const undoMetadataRemoval = () => {
    if (!metadataUndoSnapshot) return;
    setMetadataPreview((current) => ({ ...current, rows: metadataUndoSnapshot.rows }));
    setMetaFileObject(metadataUndoSnapshot.fileObject);
    setMetaFile(metadataUndoSnapshot.fileName);
    setMetadataUndoSnapshot(null);
    setSubmitError(null);
  };

  // Serialize the currently displayed/edited metadata preview into a metadata.csv file,
  // so what gets uploaded always matches exactly what's shown in the table (incl. row removals).
  // collection_date is re-normalized here too, defensively, in case metadataPreview was ever
  // populated without going through parseMetadata's normalization.
  const buildMetadataCsvFile = () => {
    const normalizedRows = metadataPreview.rows.map((row) =>
      "collection_date" in row ? { ...row, collection_date: normalizeCollectionDate(row.collection_date) } : row
    );
    const serializedMetadata = Papa.unparse({
      fields: metadataPreview.columns,
      data: normalizedRows.map((row) => metadataPreview.columns.map((column) => row[column] ?? "")),
    });
    return { file: new File([serializedMetadata], "metadata.csv", { type: "text/csv" }), rows: normalizedRows };
  };

  // ── Submission credentials (Submission.NCBI / Submission.GISAID in config.yaml) ──
  const [ncbiUsername, setNcbiUsername]             = useState("");
  const [ncbiPassword, setNcbiPassword]             = useState("");
  const [ncbiSpuidNamespace, setNcbiSpuidNamespace] = useState("");
  // NCBI Description.Organization
  const [ncbiOrgRole, setNcbiOrgRole]               = useState("owner");
  const [ncbiOrgType, setNcbiOrgType]               = useState("center");
  const [ncbiOrgTypeOther, setNcbiOrgTypeOther]     = useState(""); // custom value when Type is "other"
  const [ncbiOrgName, setNcbiOrgName]               = useState("");
  // NCBI Description.Organization.Address
  const [ncbiAddrAffil, setNcbiAddrAffil]           = useState("");
  const [ncbiAddrDiv, setNcbiAddrDiv]               = useState("");
  const [ncbiAddrStreet, setNcbiAddrStreet]         = useState("");
  const [ncbiAddrCity, setNcbiAddrCity]             = useState("");
  const [ncbiAddrSub, setNcbiAddrSub]               = useState("");
  const [ncbiAddrPostalCode, setNcbiAddrPostalCode] = useState("");
  const [ncbiAddrCountry, setNcbiAddrCountry]       = useState("");
  const [ncbiAddrEmail, setNcbiAddrEmail]           = useState("");
  const [ncbiAddrPhone, setNcbiAddrPhone]           = useState("");
  // NCBI Description.Organization.Address.Submitter
  const [ncbiSubmitterEmail, setNcbiSubmitterEmail]         = useState("");
  const [ncbiSubmitterAltEmail, setNcbiSubmitterAltEmail]   = useState("");
  const [ncbiSubmitterFirst, setNcbiSubmitterFirst]         = useState("");
  const [ncbiSubmitterLast, setNcbiSubmitterLast]           = useState("");
  // NCBI Publication fields
  const [ncbiPubTitle, setNcbiPubTitle]                     = useState(initialNcbiRow?.ncbi_publication_title ?? "");
  const [ncbiPubStatus, setNcbiPubStatus]                   = useState(initialNcbiRow?.ncbi_publication_status ?? "Unpublished");
  const [ncbiPubReleaseDate, setNcbiPubReleaseDate]         = useState(initialNcbiRow?.ncbi_release_date ?? "");
  const [gisaidClientId, setGisaidClientId]         = useState("");
  const [gisaidUsername, setGisaidUsername]         = useState("");
  const [gisaidPassword, setGisaidPassword]         = useState("");

  // ── New vs Existing submitter picker (per portal) ──
  const [ncbiUserMode, setNcbiUserMode]             = useState("new"); // "new" | "existing"
  const [ncbiSubmitters, setNcbiSubmitters]         = useState([]);
  const [ncbiSubmittersLoading, setNcbiSubmittersLoading] = useState(false);
  const [ncbiSubmittersError, setNcbiSubmittersError]     = useState(null);
  const [ncbiSelectedSubmitterId, setNcbiSelectedSubmitterId] = useState("");
  const [gisaidUserMode, setGisaidUserMode]         = useState("new"); // "new" | "existing"
  const [gisaidSubmitters, setGisaidSubmitters]     = useState([]);
  const [gisaidSubmittersLoading, setGisaidSubmittersLoading] = useState(false);
  const [gisaidSubmittersError, setGisaidSubmittersError]     = useState(null);
  const [gisaidSelectedSubmitterId, setGisaidSelectedSubmitterId] = useState("");

  // ── Standalone "Save credentials" state (per portal) ──
  const [ncbiSaveStatus, setNcbiSaveStatus]         = useState("idle"); // "idle" | "saving" | "saved" | "error"
  const [ncbiSaveError, setNcbiSaveError]           = useState(null);
  const [gisaidSaveStatus, setGisaidSaveStatus]     = useState("idle"); // "idle" | "saving" | "saved" | "error"
  const [gisaidSaveError, setGisaidSaveError]       = useState(null);

  // ── Standalone "Delete submitter" state (per portal) ──
  const [ncbiDeleteStatus, setNcbiDeleteStatus]     = useState("idle"); // "idle" | "deleting" | "error"
  const [ncbiDeleteError, setNcbiDeleteError]       = useState(null);
  const [gisaidDeleteStatus, setGisaidDeleteStatus] = useState("idle"); // "idle" | "deleting" | "error"
  const [gisaidDeleteError, setGisaidDeleteError]   = useState(null);
  const [deleteSubmitterModal, setDeleteSubmitterModal] = useState(null); // "NCBI" | "GISAID" | null — which portal's confirmation modal is open


  // Fetch the saved submitters for a portal (lazily, the first time "Existing User" is picked).
  const loadSubmitters = useCallback(async (portal) => {
    const isNcbi = portal === "NCBI";
    (isNcbi ? setNcbiSubmittersLoading : setGisaidSubmittersLoading)(true);
    (isNcbi ? setNcbiSubmittersError : setGisaidSubmittersError)(null);
    try {
      const res = await fetch(`${API.listSubmitters}?submission_portal=${encodeURIComponent(portal)}`);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "Failed to load submitters.");
      (isNcbi ? setNcbiSubmitters : setGisaidSubmitters)(Array.isArray(data.SubmitterInfo) ? data.SubmitterInfo : []);
    } catch (err) {
      (isNcbi ? setNcbiSubmittersError : setGisaidSubmittersError)(err.message || "Failed to load submitters.");
    } finally {
      (isNcbi ? setNcbiSubmittersLoading : setGisaidSubmittersLoading)(false);
    }
  }, []);

  // Fetch both portals' saved submitters up front — whether the New/Existing toggle is
  // shown at all depends on whether any submitters exist, so this can't be lazy.
  useEffect(() => {
    loadSubmitters("NCBI");
    loadSubmitters("GISAID");
  }, [loadSubmitters]);
  // For a brand-new submission (no initialSubmission to hydrate from), default straight to
  // "Existing User" the first time each portal's submitter list loads with entries, so
  // previously stored usernames are immediately available for selection instead of requiring
  // an extra click. Guarded by a ref (not state) so a later reload of the list — e.g. after a
  // successful submit — doesn't clobber a user who deliberately switched back to "New User".
  const ncbiAutoModeSetRef = useRef(false);
  useEffect(() => {
    if (!initialSubmission && !ncbiAutoModeSetRef.current && ncbiSubmitters.length > 0) {
      ncbiAutoModeSetRef.current = true;
      setNcbiUserMode("existing");
    }
  }, [initialSubmission, ncbiSubmitters]);
  const gisaidAutoModeSetRef = useRef(false);
  useEffect(() => {
    if (!initialSubmission && !gisaidAutoModeSetRef.current && gisaidSubmitters.length > 0) {
      gisaidAutoModeSetRef.current = true;
      setGisaidUserMode("existing");
    }
  }, [initialSubmission, gisaidSubmitters]);

  // Poll the SeqSender submission process status at regular intervals.
  useEffect(() => {
    if (!submissionPolling || !submissionJob) return;
    let cancelled = false;

    const poll = async () => {
      try {
        const params = new URLSearchParams();
        params.set("submission_name", submissionJob.submission_name);
        params.set("organism", submissionJob.organism);
        submissionJob.database.forEach((database) => params.append("database", database));
        params.set("submission_type", submissionJob.submission_type);
        params.set("pid", String(submissionJob.pid));

        const response = await fetch(`${API.checkSeqsenderSubmissionProccess}?${params.toString()}`);
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || "Failed to check SeqSender submission status.");
        if (cancelled) return;

        setSubmissionProcessStatus(data);
        setSubmissionStatusError(null);
        // Confirmed SUBMITTED (not just launched) — lock the form and stop polling.
        if (data.status === "SUBMITTED") {
          setSubmitted(true);
        }
        if (data.status === "SUBMITTED" || data.status === "FAILED") {
          // Let the parent tab know a submission was just created/updated so the Past Submissions
          // panel refreshes even if it was already open (its own mount-time fetch won't rerun otherwise).
          props.onSubmitted?.();
          setSubmissionPolling(false);
        }
      } catch (err) {
        if (!cancelled) {
          setSubmissionStatusError(err.message || "Failed to check SeqSender submission status.");
          setSubmissionPolling(false);
        }
      }
    };

    poll();
    const timer = setInterval(poll, 5000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [submissionPolling, submissionJob]);

  // Opening a past/initial submission shows its locally-stored status immediately, but also
  // reload the stored submission rows and status report from the backend (no external SeqSender
  // CLI call) so the banner/cards reflect whatever was last recorded without an expensive check.
  // Skip entirely for a submission still stuck at CREATED — it was never actually submitted, so
  // there's no SeqSender status/report to load yet.
  useEffect(() => {
    if (initialSubmission && !initialRows.every((row) => row.submission_status === "CREATED")) {
      loadSubmissionStatus();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialSubmission]);

  // Fill every NCBI field from a previously saved submitter.
  const selectNcbiSubmitter = (s) => {
    setNcbiSaveStatus("idle");
    setNcbiSaveError(null);
    setNcbiDeleteStatus("idle");
    setNcbiDeleteError(null);
    setNcbiSelectedSubmitterId(String(s.submitter_id));
    setNcbiUsername(s.submitter_name ?? "");
    setNcbiPassword(s.submitter_password ?? "");
    setNcbiSpuidNamespace(s.ncbi_spuid_namespace ?? "");
    setNcbiOrgRole(s.ncbi_org_role ?? "owner");
    const knownOrgTypes = ["center", "institute", "lab", "program", "unit"];
    if (s.ncbi_org_type && knownOrgTypes.includes(s.ncbi_org_type)) {
      setNcbiOrgType(s.ncbi_org_type);
      setNcbiOrgTypeOther("");
    } else {
      setNcbiOrgType("other");
      setNcbiOrgTypeOther(s.ncbi_org_type ?? "");
    }
    setNcbiOrgName(s.ncbi_org_name ?? "");
    setNcbiAddrAffil(s.ncbi_org_affiliation ?? "");
    setNcbiAddrDiv(s.ncbi_org_division ?? "");
    setNcbiAddrStreet(s.ncbi_addr_street ?? "");
    setNcbiAddrCity(s.ncbi_addr_city ?? "");
    setNcbiAddrSub(s.ncbi_addr_state ?? "");
    setNcbiAddrPostalCode(s.ncbi_addr_postal_code ?? "");
    setNcbiAddrCountry(s.ncbi_addr_country ?? "");
    setNcbiAddrEmail(s.ncbi_addr_email ?? "");
    setNcbiAddrPhone(s.ncbi_addr_phone ?? "");
    setNcbiSubmitterEmail(s.ncbi_submitter_email ?? "");
    setNcbiSubmitterAltEmail(s.ncbi_submitter_alt_email ?? "");
    setNcbiSubmitterFirst(s.ncbi_submitter_first_name ?? "");
    setNcbiSubmitterLast(s.ncbi_submitter_last_name ?? "");
    setNcbiPubTitle(s.ncbi_publication_title ?? "");
    setNcbiPubStatus(s.ncbi_publication_status ?? "Unpublished");
    setNcbiPubReleaseDate(s.ncbi_release_date ?? "");
  };

  // Fill GISAID fields from a previously saved submitter.
  const selectGisaidSubmitter = (s) => {
    setGisaidSaveStatus("idle");
    setGisaidSaveError(null);
    setGisaidDeleteStatus("idle");
    setGisaidDeleteError(null);
    setGisaidSelectedSubmitterId(String(s.submitter_id));
    setGisaidUsername(s.submitter_name ?? "");
    setGisaidPassword(s.submitter_password ?? "");
    setGisaidClientId(s.gisaid_client_id ?? "");
  };

  // Clear every NCBI credential/organization field back to a blank "New User" form.
  const clearNcbiFields = () => {
    setNcbiUsername("");
    setNcbiPassword("");
    setNcbiSpuidNamespace("");
    setNcbiOrgRole("owner");
    setNcbiOrgType("center");
    setNcbiOrgTypeOther("");
    setNcbiOrgName("");
    setNcbiAddrAffil("");
    setNcbiAddrDiv("");
    setNcbiAddrStreet("");
    setNcbiAddrCity("");
    setNcbiAddrSub("");
    setNcbiAddrPostalCode("");
    setNcbiAddrCountry("");
    setNcbiAddrEmail("");
    setNcbiAddrPhone("");
    setNcbiSubmitterEmail("");
    setNcbiSubmitterAltEmail("");
    setNcbiSubmitterFirst("");
    setNcbiSubmitterLast("");
  };

  // Clear every GISAID credential field back to a blank "New User" form.
  const clearGisaidFields = () => {
    setGisaidUsername("");
    setGisaidPassword("");
    setGisaidClientId("");
  };

  // Permanently remove the selected NCBI submitter's saved credentials.
  const handleDeleteNcbiSubmitter = async () => {
    const submitter = ncbiSubmitters.find((s) => String(s.submitter_id) === ncbiSelectedSubmitterId);
    if (!submitter) return;
    setNcbiDeleteStatus("deleting");
    setNcbiDeleteError(null);
    try {
      const res = await fetch(API.deleteSubmitter, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ submitter_name: submitter.submitter_name, submission_portal: "NCBI" }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "Failed to delete NCBI submitter.");
      setNcbiSelectedSubmitterId("");
      clearNcbiFields();
      setNcbiDeleteStatus("idle");
      setDeleteSubmitterModal(null);
      await loadSubmitters("NCBI");
    } catch (err) {
      setNcbiDeleteStatus("error");
      setNcbiDeleteError(err.message || "Failed to delete NCBI submitter.");
    }
  };

  // Permanently remove the selected GISAID submitter's saved credentials.
  const handleDeleteGisaidSubmitter = async () => {
    const submitter = gisaidSubmitters.find((s) => String(s.submitter_id) === gisaidSelectedSubmitterId);
    if (!submitter) return;
    setGisaidDeleteStatus("deleting");
    setGisaidDeleteError(null);
    try {
      const res = await fetch(API.deleteSubmitter, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ submitter_name: submitter.submitter_name, submission_portal: "GISAID" }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "Failed to delete GISAID submitter.");
      setGisaidSelectedSubmitterId("");
      clearGisaidFields();
      setGisaidDeleteStatus("idle");
      setDeleteSubmitterModal(null);
      await loadSubmitters("GISAID");
    } catch (err) {
      setGisaidDeleteStatus("error");
      setGisaidDeleteError(err.message || "Failed to delete GISAID submitter.");
    }
  };

  // Hydrate credentials from the saved submitter rows associated with a selected past submission.
  useEffect(() => {
    if (!initialSubmission) return;
    if (initialNcbiRow) {
      setNcbiUserMode("existing");
      const submitter = ncbiSubmitters.find((item) => item.submitter_name === initialNcbiRow.submitter_name);
      if (submitter) selectNcbiSubmitter(submitter);
      setNcbiPubTitle(initialNcbiRow.ncbi_publication_title ?? "");
      setNcbiPubStatus(initialNcbiRow.ncbi_publication_status ?? "Unpublished");
      setNcbiPubReleaseDate(initialNcbiRow.ncbi_release_date ?? "");
    }
    if (initialGisaidRow) {
      setGisaidUserMode("existing");
      const submitter = gisaidSubmitters.find((item) => item.submitter_name === initialGisaidRow.submitter_name);
      if (submitter) selectGisaidSubmitter(submitter);
    }
  }, [initialSubmission, ncbiSubmitters, gisaidSubmitters]);

  const isValidEmailAddr = (value) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());

  // Save just the NCBI credentials/organization block to the database, independent of any submission.
  const handleSaveNcbiSubmitter = async () => {
    const missing = [];
    if (!ncbiUsername) missing.push("NCBI Credentials: Username");
    if (!ncbiPassword) missing.push("NCBI Credentials: Password");
    if (!ncbiSpuidNamespace) missing.push("NCBI Credentials: Spuid Namespace");
    if (!ncbiOrgName) missing.push("NCBI Organization: Name");
    if (!ncbiAddrAffil.trim()) missing.push("NCBI Organization: Affiliation");
    if (!ncbiAddrDiv.trim()) missing.push("NCBI Organization: Division");
    if (ncbiOrgType === "other" && !ncbiOrgTypeOther) missing.push("NCBI Organization: Type (please specify)");
    if (!ncbiAddrStreet) missing.push("NCBI Address: Street");
    if (!ncbiAddrCity) missing.push("NCBI Address: City");
    if (!ncbiAddrSub) missing.push("NCBI Address: State");
    if (!ncbiAddrPostalCode) missing.push("NCBI Address: Postal Code");
    else if (!/^\d+$/.test(ncbiAddrPostalCode.trim())) missing.push("NCBI Address: Postal Code must contain only digits");
    if (!ncbiAddrCountry) missing.push("NCBI Address: Country");
    if (!ncbiAddrEmail.trim()) missing.push("NCBI Address: Email");
    else if (!isValidEmailAddr(ncbiAddrEmail)) missing.push("NCBI Address: Email must be a valid email address");
    if (!ncbiSubmitterEmail.trim()) missing.push("NCBI Submitter: Email");
    else if (!isValidEmailAddr(ncbiSubmitterEmail)) missing.push("NCBI Submitter: Email must be a valid email address");
    if (ncbiSubmitterAltEmail.trim() && !isValidEmailAddr(ncbiSubmitterAltEmail)) {
      missing.push("NCBI Submitter: Alt Email must be a valid email address");
    }
    if (!ncbiSubmitterFirst) missing.push("NCBI Submitter: First Name");
    if (!ncbiSubmitterLast) missing.push("NCBI Submitter: Last Name");

    if (missing.length > 0) {
      setNcbiSaveStatus("error");
      setNcbiSaveError(missing);
      return;
    }

    setNcbiSaveStatus("saving");
    setNcbiSaveError(null);
    try {
      const res = await fetch(API.saveSubmitter, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          submitter_name: ncbiUsername,
          submitter_password: ncbiPassword,
          submission_portal: "NCBI",
          ncbi_spuid_namespace: ncbiSpuidNamespace,
          ncbi_org_role: ncbiOrgRole,
          ncbi_org_type: ncbiOrgType === "other" ? ncbiOrgTypeOther : ncbiOrgType,
          ncbi_org_name: ncbiOrgName,
          ncbi_org_affiliation: ncbiAddrAffil,
          ncbi_org_division: ncbiAddrDiv,
          ncbi_addr_street: ncbiAddrStreet,
          ncbi_addr_city: ncbiAddrCity,
          ncbi_addr_state: ncbiAddrSub,
          ncbi_addr_postal_code: ncbiAddrPostalCode,
          ncbi_addr_country: ncbiAddrCountry,
          ncbi_addr_email: ncbiAddrEmail,
          ncbi_addr_phone: ncbiAddrPhone,
          ncbi_submitter_email: ncbiSubmitterEmail,
          ncbi_submitter_alt_email: ncbiSubmitterAltEmail,
          ncbi_submitter_first_name: ncbiSubmitterFirst,
          ncbi_submitter_last_name: ncbiSubmitterLast,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "Failed to save NCBI credentials.");
      setNcbiSaveStatus("saved");
      await loadSubmitters("NCBI");
    } catch (err) {
      setNcbiSaveStatus("error");
      setNcbiSaveError([err.message || "Failed to save NCBI credentials."]);
    }
  };

  // Save just the GISAID credentials block to the database, independent of any submission.
  const handleSaveGisaidSubmitter = async () => {
    const missing = [];
    if (!gisaidUsername) missing.push("GISAID Credentials: Username");
    if (!gisaidPassword) missing.push("GISAID Credentials: Password");
    if (!gisaidClientId) missing.push("GISAID Credentials: Client-Id");

    if (missing.length > 0) {
      setGisaidSaveStatus("error");
      setGisaidSaveError(missing);
      return;
    }

    setGisaidSaveStatus("saving");
    setGisaidSaveError(null);
    try {
      const res = await fetch(API.saveSubmitter, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          submitter_name: gisaidUsername,
          submitter_password: gisaidPassword,
          submission_portal: "GISAID",
          gisaid_client_id: gisaidClientId,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "Failed to save GISAID credentials.");
      setGisaidSaveStatus("saved");
      await loadSubmitters("GISAID");
    } catch (err) {
      setGisaidSaveStatus("error");
      setGisaidSaveError([err.message || "Failed to save GISAID credentials."]);
    }
  };

  // ── Collapsible section state ──
  // A new submission, or a past submission still entirely CREATED (never submitted), opens every
  // section; any other past submission collapses every section except Status.
  const initialSectionsExpanded = !initialSubmission
    || (initialRows.length > 0 && initialRows.every((row) => row.submission_status === "CREATED"));
  const [openSections, setOpenSections] = useState({
    database: initialSectionsExpanded,
    pathogen: initialSectionsExpanded,
    credentials: initialSectionsExpanded,
    inputs: initialSectionsExpanded,
    options: initialSectionsExpanded,
    submit: initialSectionsExpanded,
    status: true,
  });
  const toggleSection = (key) => setOpenSections((prev) => ({ ...prev, [key]: !prev[key] }));

  // Let the parent (SeqSenderTab) open a given section and scroll it into view from the step-link row.
  useImperativeHandle(ref, () => ({
    jumpToSection: (key) => {
      setOpenSections((prev) => ({ ...prev, [key]: true }));
      setTimeout(() => document.getElementById(`seqsender-section-${key}`)?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
    },
  }));

  const toggleDb = (k) => setDbs((p) => ({ ...p, [k]: !p[k] }));

  // Validate every required field (scoped to the selected databases) before allowing final submission.
  const handleSubmit = async (mode = "submit") => {

    // Determine if the submission is a preparation-only submission.
    const isPrep = mode === "prep";

    // Helper function to validate email addresses.
    const isValidEmail = (value) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());
    
    // Initialize an array to keep track of missing required fields.
    const missing = [];
    if (!Object.values(dbs).some(Boolean)) missing.push("Database Targets: select at least one database");
    if (!organism) missing.push("Pathogen: Organism");
    if (!subName) missing.push("Submission Inputs: Submission Name");

    // table2asn's GFF file is only surfaced in the UI for FLU/COV, so only require it there.
    const gffRequired = table2asn && (organism === "FLU" || organism === "COV");
    if (gffRequired && !gffFile) missing.push("Submission Options: GFF File is required when --table2asn is enabled.");

    // FASTA is only required for GenBank/GISAID submissions — BioSample and SRA don't need sequences.
    const fastaRequired = dbs.genbank || dbs.gisaid;

    if (!initialSubmission) {
      if (!metaFile) missing.push("Submission Inputs: Metadata File");
      else if (!metaFileObject) missing.push("Submission Inputs: Metadata File (please browse and upload a file, not just type its name)");
      if (fastaRequired) {
        if (!fastaFile) missing.push("Submission Inputs: FASTA File");
        else if (!fastaFileObject) missing.push("Submission Inputs: FASTA File (please browse and upload a file, not just type its name)");
      }
      if (dbs.sra && !rawReadsFiles) missing.push("Submission Inputs: Raw Reads (FASTQs)");
      else if (dbs.sra && rawReadsFiles && !rawReadsFileObjects.length) missing.push("Submission Inputs: Raw Reads (FASTQs) (please browse and upload files, not just type their names)");
      if (gffFile && !gffFileObject) missing.push("Submission Options: GFF File (please browse and upload a file, not just type its name)");
    }

    // Existing CLI mode reuses whatever file is already stored for this organism — no upload required.
    if (dbs.gisaid && gisaidCliMode === "new") {
      if (!gisaidCliFile) missing.push("Submission Inputs: GISAID CLI");
      else if (!gisaidCliFileObject) missing.push("Submission Inputs: GISAID CLI (please browse and upload a file, not just type its name)");
    }

    // NCBI Credentials and Organization Information Validation
    if (dbs.biosample || dbs.sra || dbs.genbank) {
      if (!ncbiUsername) missing.push("NCBI Credentials: Username");
      if (!ncbiPassword) missing.push("NCBI Credentials: Password");
      if (!ncbiSpuidNamespace) missing.push("NCBI Credentials: Spuid Namespace");
      if (!ncbiOrgName) missing.push("NCBI Organization: Name");
      if (!ncbiAddrAffil.trim()) missing.push("NCBI Organization: Affiliation");
      if (!ncbiAddrDiv.trim()) missing.push("NCBI Organization: Division");
      if (ncbiOrgType === "other" && !ncbiOrgTypeOther) missing.push("NCBI Organization: Type (please specify)");
      if (!ncbiAddrStreet) missing.push("NCBI Address: Street");
      if (!ncbiAddrCity) missing.push("NCBI Address: City");
      if (!ncbiAddrSub) missing.push("NCBI Address: State");
      if (!ncbiAddrPostalCode) missing.push("NCBI Address: Postal Code");
      else if (!/^\d+$/.test(ncbiAddrPostalCode.trim())) missing.push("NCBI Address: Postal Code must contain only digits");
      if (!ncbiAddrCountry) missing.push("NCBI Address: Country");
      if (!ncbiAddrEmail.trim()) missing.push("NCBI Address: Email");
      else if (!isValidEmail(ncbiAddrEmail)) missing.push("NCBI Address: Email must be a valid email address");
      if (!ncbiSubmitterEmail.trim()) missing.push("NCBI Submitter: Email");
      else if (!isValidEmail(ncbiSubmitterEmail)) missing.push("NCBI Submitter: Email must be a valid email address");
      if (ncbiSubmitterAltEmail.trim() && !isValidEmail(ncbiSubmitterAltEmail)) {
        missing.push("NCBI Submitter: Alt Email must be a valid email address");
      }
      if (!ncbiSubmitterFirst) missing.push("NCBI Submitter: First Name");
      if (!ncbiSubmitterLast) missing.push("NCBI Submitter: Last Name");
    }

    // GISAID Credentials Validation
    if (dbs.gisaid) {
      if (!gisaidUsername) missing.push("GISAID Credentials: Username");
      if (!gisaidPassword) missing.push("GISAID Credentials: Password");
      if (!gisaidClientId) missing.push("GISAID Credentials: Client-Id");
    }

    // Check if any required fields are missing for NCBI and GISAID
    if (missing.length > 0) {
      setSubmitError(missing);
      // Expand every section so the user can see and fill in what's missing.
      setOpenSections((prev) => ({ ...prev, database: true, pathogen: true, credentials: true, inputs: true, submit: true }));
      setTimeout(() => document.getElementById("seqsender-section-submit")?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
      return;
    }

    if (metadataPreview.rows.length === 0) {
      setSubmitError(["Metadata must contain at least one sample."]);
      setOpenSections((prev) => ({ ...prev, inputs: true, submit: true }));
      setTimeout(() => document.getElementById("seqsender-section-submit")?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
      return;
    }

    // Check if the metadata exceeds the maximum allowed number of samples (3,000)
    if (metadataPreview.rows.length > 3000) {
      setSubmitError(["Metadata cannot contain more than 3,000 samples."]);
      setOpenSections((prev) => ({ ...prev, database: true, pathogen: true, credentials: true, inputs: true, submit: true }));
      setTimeout(() => document.getElementById("seqsender-section-submit")?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
      return;
    }
    
    // Upload the submission files to the SeqSender submission folder in the backend
    setSubmitError(null);
    if (isPrep) {
      setCreateFilesError(null);
      setCreateFilesResult(null);
      setCreatingFiles(true);
    } else {
      setUploadError(null);
      setUploadingFiles(true);
    }

    // Attempt to upload the submission data and files to the backend
    try {

      // Build the NCBI submitter information block
      const ncbiActive = dbs.biosample || dbs.sra || dbs.genbank;
      const ncbiSubmitterInfo = ncbiActive ? {
        submitter_name: ncbiUsername,
        submitter_password: ncbiPassword,
        submission_portal: "NCBI",
        ncbi_spuid_namespace: ncbiSpuidNamespace,
        ncbi_org_role: ncbiOrgRole,
        ncbi_org_type: ncbiOrgType === "other" ? ncbiOrgTypeOther : ncbiOrgType,
        ncbi_org_name: ncbiOrgName,
        ncbi_org_affiliation: ncbiAddrAffil,
        ncbi_org_division: ncbiAddrDiv,
        ncbi_addr_street: ncbiAddrStreet,
        ncbi_addr_city: ncbiAddrCity,
        ncbi_addr_state: ncbiAddrSub,
        ncbi_addr_postal_code: ncbiAddrPostalCode,
        ncbi_addr_country: ncbiAddrCountry,
        ncbi_addr_email: ncbiAddrEmail,
        ncbi_addr_phone: ncbiAddrPhone,
        ncbi_submitter_email: ncbiSubmitterEmail,
        ncbi_submitter_alt_email: ncbiSubmitterAltEmail,
        ncbi_submitter_first_name: ncbiSubmitterFirst,
        ncbi_submitter_last_name: ncbiSubmitterLast,
      } : null;

      // Build the GISAID submitter information block
      const gisaidSubmitterInfo = dbs.gisaid ? {
        submitter_name: gisaidUsername,
        submitter_password: gisaidPassword,
        submission_portal: "GISAID",
        gisaid_client_id: gisaidClientId,
      } : null;

      // Create a submission record 
      const submissionData = {
        submission_name: subName,
        organism: organism.toUpperCase(),
        database: Object.entries(dbs).filter(([, v]) => v).map(([k]) => k.toUpperCase()),
        submission_type: testMode ? "TEST" : "PRODUCTION",
        ncbi_submitter_info: ncbiSubmitterInfo,
        gisaid_submitter_info: gisaidSubmitterInfo,
        gff_file: !!gffFile,
        table2asn: table2asn,
        ncbi_publication_title: ncbiPubTitle,
        ncbi_publication_status: ncbiPubStatus,
        ncbi_release_date: ncbiPubReleaseDate,
      };

      // Build the shared URL parameters before either validation request uses them.
      const checkParams = new URLSearchParams();
      checkParams.set("submission_name", submissionData.submission_name);
      checkParams.set("organism", submissionData.organism);
      submissionData.database.forEach((db) => checkParams.append("database", db));
      checkParams.set("submission_type", submissionData.submission_type);

      // Helper function to upload a single file (or multiple files) to the backend API endpoint for a
      // given file type. organism/database/submission_type must match the just-created submission record exactly.
      const uploadFile = async (url, fieldName, file) => {
        const form = new FormData();
        form.append("submission_name", submissionData.submission_name);
        form.append("organism", submissionData.organism);
        if (Array.isArray(file)) file.forEach((f) => form.append(fieldName, f));
        else if (file) form.append(fieldName, file);
        const uploadRes = await fetch(url, { method: "POST", body: form });
        const uploadData = await uploadRes.json().catch(() => ({}));
        if (!uploadRes.ok) throw new Error(uploadData.detail || `Failed to upload ${fieldName}`);
      };
      const uploadGisaidCli = async (url, fieldName, file) => {
        const form = new FormData();
        form.append("organism", submissionData.organism);
        if (Array.isArray(file)) file.forEach((f) => form.append(fieldName, f));
        else if (file) form.append(fieldName, file);
        const uploadRes = await fetch(url, { method: "POST", body: form });
        const uploadData = await uploadRes.json().catch(() => ({}));
        if (!uploadRes.ok) throw new Error(uploadData.detail || `Failed to upload ${fieldName}`);
      };
      // Upload the selected files to the backend API endpoints for each file type.
      // Metadata is always re-serialized from metadataPreview (not gated on metaFileObject) so a
      // past submission's stored metadata.csv also picks up normalization (e.g. collection_date)
      // even when the user didn't browse a new file this session.
      if (metadataPreview.columns.length > 0) {
        const { file: metadataCsvFile, rows: normalizedMetadataRows } = buildMetadataCsvFile();
        await uploadFile(API.uploadSeqsenderMetadata, "metadata_file", metadataCsvFile);
        // Reflect the exact (normalized) data that was just uploaded back into the preview table.
        setMetadataPreview((current) => ({ ...current, rows: normalizedMetadataRows }));
      }
      if (fastaFileObject) {
        await uploadFile(API.uploadSeqsenderFasta, "fasta_file", fastaFileObject);
      }
      if (dbs.sra && rawReadsFileObjects.length) {
        await uploadFile(API.uploadSeqsenderRawReads, "raw_read_files", rawReadsFileObjects);
      }
      if (gffFileObject) {
        await uploadFile(API.uploadSeqsenderGff, "gff_file", gffFileObject);
      }
      // "Existing CLI" mode reuses whatever GISAID CLI file is already stored for this organism — skip upload.
      if (dbs.gisaid && gisaidCliMode === "new" && gisaidCliFileObject) {
        await uploadGisaidCli(API.uploadSeqsenderGisaidCli, "gisaid_cli_file", gisaidCliFileObject);
      }

      // If new submission, check for existing submission with the same identity.
      if(!initialSubmission) {
        const checkRes = await fetch(`${API.retrieveSeqsenderSubmission}?${checkParams.toString()}`);
        const checkData = await checkRes.json().catch(() => ({}));
        if (!checkRes.ok) throw new Error(checkData.detail || "Failed to check for an existing submission.");
        if (Array.isArray(checkData?.submission_info) && checkData.submission_info.length > 0) {
          setUploadError(`Submission "${submissionData.submission_name}" already exists for organism ${submissionData.organism} with database(s): ${checkData.submission_info.map((row) => row.database).join(", ")}. Please choose a different name or select "Past Submissions" to reload it.`);
          if (isPrep) setCreatingFiles(false); else setUploadingFiles(false);
          return;
        }
      }

      // Send the submission data to the backend API endpoint to create a new submission record.
      // This must happen before file uploads, since the upload endpoints look up this record.
      const res = await fetch(API.createSeqsenderSubmission, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(submissionData),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "Failed to create submission record.");

      // Validate stored submission files -- required gff file parameter in the check.
      checkParams.set("gff_file", String(submissionData.gff_file));
      const fileCheckRes = await fetch(`${API.validateSeqsenderFiles}?${checkParams.toString()}`);
      const fileCheckData = await fileCheckRes.json().catch(() => ({}));
      if (!fileCheckRes.ok) throw new Error(fileCheckData.detail || "Failed to check stored submission files.");

      // Determine which required submission files are missing from the storage location.
      const replacements = {
        metadata: metadataPreview.columns.length > 0,
        fasta: !!fastaFileObject,
        raw_reads: rawReadsFileObjects.length > 0,
        gisaid_cli: gisaidCliMode === "new" && !!gisaidCliFileObject,
        gff: !!gffFileObject,
      };

      // Filter out the files that are already present in the storage location based on the replacements object.  
      const missingStoredFiles = (fileCheckData.missing_files ?? [])
        .filter(({ key }) => !replacements[key]);
      if (missingStoredFiles.length > 0) {
        setSubmitError(missingStoredFiles.map(({ label }) =>
          `Submission Inputs: ${label} not found in the storage location. File(s) may have been moved or deleted; Browse and upload the file(s) again.`
        ));
        setOpenSections((prev) => ({ ...prev, inputs: true, options: true, submit: true }));
        if (isPrep) setCreatingFiles(false); else setUploadingFiles(false);
        return;
      }

      if (isPrep) {

        // Only generate the per-database submission files — no actual portal submission is launched.
        const prepRes = await fetch(API.createSeqsenderSubmissionFiles, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            submission_name:  submissionData.submission_name,
            organism:         submissionData.organism,
            database:         submissionData.database,
            submission_type:  submissionData.submission_type,
          }),
        });
        const prepData = await prepRes.json().catch(() => ({}));
        if (!prepRes.ok) throw new Error(prepData.detail || "Failed to create submission files.");
        setCreateFilesResult(prepData);

        if (ncbiActive) loadSubmitters("NCBI");
        if (dbs.gisaid) loadSubmitters("GISAID");
        props.onSubmitted?.();

      } else {

        // Launch the SeqSender submission pipeline for the newly created submission record.
        const submitRes = await fetch(API.submitSeqsenderSubmission, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            submission_name:  submissionData.submission_name,
            organism:         submissionData.organism,
            database:         submissionData.database,
            submission_type:  submissionData.submission_type,
          }),
        });
        const submitData = await submitRes.json().catch(() => ({}));
        if (!submitRes.ok) throw new Error(submitData.detail || "Failed to launch SeqSender submission.");
        if (submitData.status !== "success" || !Number.isInteger(submitData.pid)) {
          throw new Error("SeqSender did not return a valid process ID.");
        }

        // Update the local state to reflect the newly launched submission job.
        setSubmissionJob({
          submission_name: submissionData.submission_name,
          organism: submissionData.organism,
          database: submissionData.database,
          submission_type: submissionData.submission_type,
          pid: submitData.pid,
        });

        // Update the submission process status to indicate that SeqSender has been launched successfully.
        setSubmissionProcessStatus({
          status: "PROCESSING",
          pid: submitData.pid,
          return_code: null,
          message: "SeqSender was launched successfully and is being processed.",
        });

        setSubmissionPolling(true);
        setSubmissionStatusError(null);

        // The backend upserts the submitter row (new OR existing) as part of /create/submission,
        // so re-fetch from the backend rather than patching local state — a local patch only ever
        // carried submitter_name/ncbi_spuid_namespace, dropping every other field (org, address,
        // publication, etc.), so re-selecting that "just created" entry later showed blank fields.
        if (ncbiActive) loadSubmitters("NCBI");
        if (dbs.gisaid) loadSubmitters("GISAID");

        // Let the parent tab know a submission was just created/updated so the Past Submissions
        // panel refreshes even if it was already open (its own mount-time fetch won't rerun otherwise).
        props.onSubmitted?.();

      }

    } catch (err) {
      if (isPrep) setCreateFilesError(err.message || "Failed to create submission files.");
      else setUploadError(err.message || "Failed to upload submission files.");
    } finally {
      if (isPrep) setCreatingFiles(false); else setUploadingFiles(false);
    }

  };

  return (
    <>
      {/* ── Database selection ────────────── */}
      <SectionHeader id="seqsender-section-database" title="Database Targets" icon={Database} open={openSections.database} onToggle={() => toggleSection("database")} />
      {openSections.database && (
        <>
          <div className="grid w-full grid-cols-3 gap-2">
            {DB_LIST.map(({ key, label, desc, url }) => (
              <label key={key} className={cn(
                "flex items-start gap-3 p-3 rounded-xl border transition-colors",
                !canCreateOrSubmit ? "cursor-not-allowed opacity-60" : "cursor-pointer",
                dbs[key] ? "border-primary bg-primary/5" : "border-border hover:bg-muted/20"
              )}>
                <input type="checkbox" checked={dbs[key]} onChange={() => toggleDb(key)} disabled={!canCreateOrSubmit} className="mt-0.5 accent-primary disabled:cursor-not-allowed" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold">{label}</p>
                  <p className="text-xs text-muted-foreground">{desc}</p>
                </div>
                {url && (
                  <a
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={(e) => e.stopPropagation()}
                    title={`Learn more about ${label}`}
                    className="shrink-0 text-muted-foreground hover:text-primary transition-colors"
                  >
                    <ExternalLink size={13} />
                  </a>
                )}
              </label>
            ))}
          </div>

          {/* ── Download metadata template — generated by SeqSender for the selected organism + databases ────────────── */}
          <div className="flex flex-col gap-1.5">
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => downloadStoredFile(
                  (() => {
                    const selectedDatabases = Object.entries(dbs).filter(([, v]) => v).map(([k]) => k.toUpperCase());
                    if (!organism || selectedDatabases.length === 0) return "";
                    const params = new URLSearchParams();
                    params.set("organism", organism);
                    selectedDatabases.forEach((db) => params.append("database", db));
                    return `${API.downloadSeqsenderMetadataTemplate}?${params.toString()}`;
                  })(),
                  "metadataTemplate",
                  `${organism.toLowerCase()}_metadata_template.csv`
                )}
                disabled={!organism || !Object.values(dbs).some(Boolean) || storedDownloading === "metadataTemplate"}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-primary bg-primary hover:bg-primary/90 text-xs font-medium text-primary-foreground transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {storedDownloading === "metadataTemplate" ? <RefreshCw size={13} className="animate-spin" /> : <Download size={13} />}
                Download Metadata Template
              </button>
            </div>
            {storedDownloadError?.field === "metadataTemplate" && (
              <p className="flex items-center gap-1 text-xs text-destructive">
                <AlertCircle size={11} className="shrink-0" /> {storedDownloadError.message}
              </p>
            )}
          </div>
        </>
      )}

      {/* ── Organism selection ────────────── */}
      <SectionHeader id="seqsender-section-pathogen" title="Pathogen" icon={FlaskConical} open={openSections.pathogen} onToggle={() => toggleSection("pathogen")} />
      {openSections.pathogen && (
        <div>
          <FieldLabel>Organism <span className="text-destructive">*</span></FieldLabel>
          <div className="flex flex-wrap gap-2">
            {ORGANISMS.map(({ value, label }) => (
              <button key={value} disabled={!canCreateOrSubmit} onClick={() => setOrganism(value)}
                className={cn(
                  "px-4 py-1.5 rounded-full text-xs font-semibold border transition-colors",
                  !canCreateOrSubmit && "cursor-not-allowed opacity-60",
                  organism === value
                    ? "bg-primary text-primary-foreground border-primary"
                    : "border-border text-muted-foreground hover:border-primary hover:text-primary"
                )}>{label}</button>
            ))}
          </div>
        </div>
      )}

      {/* ── Credentials inputs ────────────── */}
      <SectionHeader id="seqsender-section-credentials" title="Submission Credentials" icon={ShieldCheck} open={openSections.credentials} onToggle={() => toggleSection("credentials")} />
      {openSections.credentials && (
        <>
          {(dbs.biosample || dbs.sra || dbs.genbank) && (
            <div className="w-full rounded-xl border border-border bg-muted/10 p-3 space-y-3">
              <p className="text-xs font-bold text-foreground uppercase tracking-wider">NCBI</p>
              <div>
                <FieldLabel>Username <span className="text-destructive">*</span></FieldLabel>
                {ncbiSubmitters.length > 0 && (
                  <div className="flex gap-2 mb-2">
                    <button type="button" disabled={!canCreateOrSubmit} onClick={() => { setNcbiUserMode("new"); setNcbiSelectedSubmitterId(""); setNcbiSaveStatus("idle"); setNcbiSaveError(null); setNcbiDeleteStatus("idle"); setNcbiDeleteError(null); clearNcbiFields(); }}
                      className={cn("px-3 py-1 rounded-full text-xs font-semibold border transition-colors disabled:opacity-60 disabled:cursor-not-allowed",
                        ncbiUserMode === "new" ? "bg-primary text-primary-foreground border-primary" : "border-border text-muted-foreground hover:border-primary hover:text-primary")}>
                      New User
                    </button>
                    <button type="button" disabled={!canCreateOrSubmit} onClick={() => { setNcbiUserMode("existing"); setNcbiSaveStatus("idle"); setNcbiSaveError(null); setNcbiDeleteStatus("idle"); setNcbiDeleteError(null); }}
                      className={cn("px-3 py-1 rounded-full text-xs font-semibold border transition-colors disabled:opacity-60 disabled:cursor-not-allowed",
                        ncbiUserMode === "existing" ? "bg-primary text-primary-foreground border-primary" : "border-border text-muted-foreground hover:border-primary hover:text-primary")}>
                      Existing User
                    </button>
                  </div>
                )}
                {ncbiUserMode === "existing" && ncbiSubmitters.length > 0 ? (
                  <ExistingSubmitterPicker
                    submitters={ncbiSubmitters}
                    loading={ncbiSubmittersLoading}
                    error={ncbiSubmittersError}
                    selectedId={ncbiSelectedSubmitterId}
                    onSelect={selectNcbiSubmitter}
                    placeholder="Select an NCBI submitter…"
                    disabled={!canCreateOrSubmit}
                  />
                ) : (
                  <input
                    value={ncbiUsername}
                    onChange={(e) => setNcbiUsername(e.target.value)}
                    placeholder="e.g. your NCBI username"
                    autoComplete="off"
                    disabled={!canCreateOrSubmit}
                    className="w-full h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-60 disabled:cursor-not-allowed disabled:bg-muted"
                  />
                )}
              </div>
              <div>
                <FieldLabel>Password <span className="text-destructive">*</span></FieldLabel>
                <PasswordInput value={ncbiPassword} onChange={(e) => setNcbiPassword(e.target.value)} disabled={!canCreateOrSubmit} />
              </div>
              <div>
                <FieldLabel>Spuid Namespace <span className="text-destructive">*</span></FieldLabel>
                <input
                  value={ncbiSpuidNamespace}
                  onChange={(e) => setNcbiSpuidNamespace(e.target.value)}
                  placeholder="e.g. your organization's NCBI namespace"
                  autoComplete="off"
                  disabled={!canCreateOrSubmit}
                  className="w-full h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-60 disabled:cursor-not-allowed disabled:bg-muted"
                />
              </div>

              {/* ── Description.Organization ────────────── */}
              <div className="pt-1">
                <p className="text-xs font-bold text-foreground uppercase tracking-wider mt-2 mb-2">Organization</p>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <FieldLabel>Role <span className="text-destructive">*</span></FieldLabel>
                    <select value={ncbiOrgRole} onChange={(e) => setNcbiOrgRole(e.target.value)} disabled={!canCreateOrSubmit}
                      className="w-full h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-60 disabled:cursor-not-allowed disabled:bg-muted">
                      <option value="owner">Owner</option>
                    </select>
                  </div>
                  <div>
                    <FieldLabel>Type <span className="text-destructive">*</span></FieldLabel>
                    <select value={ncbiOrgType} onChange={(e) => setNcbiOrgType(e.target.value)} disabled={!canCreateOrSubmit}
                      className="w-full h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-60 disabled:cursor-not-allowed disabled:bg-muted">
                      <option value="center">Center</option>
                      <option value="institute">Institute</option>
                      <option value="lab">Lab</option>
                      <option value="program">Program</option>
                      <option value="unit">Unit</option>
                      <option value="other">Other</option>
                    </select>
                    {ncbiOrgType === "other" && (
                      <input value={ncbiOrgTypeOther} onChange={(e) => setNcbiOrgTypeOther(e.target.value)}
                        placeholder="e.g. bureau" disabled={!canCreateOrSubmit}
                        className="w-full h-9 px-3 mt-2 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-60 disabled:cursor-not-allowed disabled:bg-muted" />
                    )}
                  </div>
                </div>
                <div className="mt-3">
                  <FieldLabel>Name <span className="text-destructive">*</span></FieldLabel>
                  <input value={ncbiOrgName} onChange={(e) => setNcbiOrgName(e.target.value)} disabled={!canCreateOrSubmit}
                    className="w-full h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-60 disabled:cursor-not-allowed disabled:bg-muted" />
                </div>            
                <div className="grid grid-cols-2 mt-3 gap-3">
                  <div>
                    <FieldLabel>Affiliation <span className="text-destructive">*</span></FieldLabel>
                    <input required value={ncbiAddrAffil} onChange={(e) => setNcbiAddrAffil(e.target.value)} disabled={!canCreateOrSubmit}
                      className="w-full h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-60 disabled:cursor-not-allowed disabled:bg-muted" />
                  </div>
                  <div>
                    <FieldLabel>Division <span className="text-destructive">*</span></FieldLabel>
                    <input required value={ncbiAddrDiv} onChange={(e) => setNcbiAddrDiv(e.target.value)} disabled={!canCreateOrSubmit}
                      className="w-full h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-60 disabled:cursor-not-allowed disabled:bg-muted" />
                  </div>
                </div>
              </div>

              {/* ── Description.Organization.Address ────────────── */}
              <div className="pt-1">
                <p className="text-xs font-bold text-foreground uppercase tracking-wider mt-2 mb-2">Address</p>
                <div className="mt-3">
                  <FieldLabel>Street <span className="text-destructive">*</span></FieldLabel>
                  <input value={ncbiAddrStreet} onChange={(e) => setNcbiAddrStreet(e.target.value)} disabled={!canCreateOrSubmit}
                    className="w-full h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-60 disabled:cursor-not-allowed disabled:bg-muted" />
                </div>
                <div className="grid grid-cols-2 gap-3 mt-3">
                  <div>
                    <FieldLabel>City <span className="text-destructive">*</span></FieldLabel>
                    <input value={ncbiAddrCity} onChange={(e) => setNcbiAddrCity(e.target.value)} disabled={!canCreateOrSubmit}
                      className="w-full h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-60 disabled:cursor-not-allowed disabled:bg-muted" />
                  </div>
                  <div>
                    <FieldLabel>State <span className="text-destructive">*</span></FieldLabel>
                    <input value={ncbiAddrSub} onChange={(e) => setNcbiAddrSub(e.target.value)} disabled={!canCreateOrSubmit}
                      className="w-full h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-60 disabled:cursor-not-allowed disabled:bg-muted" />
                  </div>
                  <div>
                    <FieldLabel>Postal Code <span className="text-destructive">*</span></FieldLabel>
                    <input inputMode="numeric" pattern="[0-9]*" value={ncbiAddrPostalCode} onChange={(e) => setNcbiAddrPostalCode(e.target.value)} disabled={!canCreateOrSubmit}
                      className="w-full h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-60 disabled:cursor-not-allowed disabled:bg-muted" />
                  </div>
                  <div>
                    <FieldLabel>Country <span className="text-destructive">*</span></FieldLabel>
                    <input value={ncbiAddrCountry} onChange={(e) => setNcbiAddrCountry(e.target.value)} disabled={!canCreateOrSubmit}
                      className="w-full h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-60 disabled:cursor-not-allowed disabled:bg-muted" />
                  </div>
                  <div>
                    <FieldLabel>Email <span className="text-destructive">*</span></FieldLabel>
                    <input type="email" required value={ncbiAddrEmail} onChange={(e) => setNcbiAddrEmail(e.target.value)} disabled={!canCreateOrSubmit}
                      className="w-full h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-60 disabled:cursor-not-allowed disabled:bg-muted" />
                  </div>
                  <div>
                    <FieldLabel>Phone</FieldLabel>
                    <input value={ncbiAddrPhone} onChange={(e) => setNcbiAddrPhone(e.target.value)} disabled={!canCreateOrSubmit}
                      className="w-full h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-60 disabled:cursor-not-allowed disabled:bg-muted" />
                  </div>
                </div>
              </div>

              {/* ── Description.Organization.Address.Submitter ────────────── */}
              <div className="pt-1">
                <p className="text-xs font-bold text-foreground uppercase tracking-wider mt-2 mb-2">Submitter</p>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <FieldLabel>Email <span className="text-destructive">*</span></FieldLabel>
                    <input type="email" value={ncbiSubmitterEmail} onChange={(e) => setNcbiSubmitterEmail(e.target.value)} disabled={!canCreateOrSubmit}
                      className="w-full h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-60 disabled:cursor-not-allowed disabled:bg-muted" />
                  </div>
                  <div>
                    <FieldLabel>Alt Email</FieldLabel>
                    <input type="email" value={ncbiSubmitterAltEmail} onChange={(e) => setNcbiSubmitterAltEmail(e.target.value)} disabled={!canCreateOrSubmit}
                      className="w-full h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-60 disabled:cursor-not-allowed disabled:bg-muted" />
                  </div>
                  <div>
                    <FieldLabel>First Name <span className="text-destructive">*</span></FieldLabel>
                    <input value={ncbiSubmitterFirst} onChange={(e) => setNcbiSubmitterFirst(e.target.value)} disabled={!canCreateOrSubmit}
                      className="w-full h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-60 disabled:cursor-not-allowed disabled:bg-muted" />
                  </div>
                  <div>
                    <FieldLabel>Last Name <span className="text-destructive">*</span></FieldLabel>
                    <input value={ncbiSubmitterLast} onChange={(e) => setNcbiSubmitterLast(e.target.value)} disabled={!canCreateOrSubmit}
                      className="w-full h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-60 disabled:cursor-not-allowed disabled:bg-muted" />
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-3 pt-1 flex-wrap">
                <button
                  type="button"
                  onClick={handleSaveNcbiSubmitter}
                  disabled={ncbiSaveStatus === "saving" || !canCreateOrSubmit}
                  className="inline-flex items-center gap-1.5 h-8 px-3 rounded-md bg-primary text-xs font-semibold text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {ncbiSaveStatus === "saving" ? <RefreshCw size={13} className="animate-spin" /> : <Save size={13} />}
                  Save NCBI Credentials
                </button>
                {ncbiSelectedSubmitterId && (
                  <button
                    type="button"
                    onClick={() => { setNcbiDeleteStatus("idle"); setNcbiDeleteError(null); setDeleteSubmitterModal("NCBI"); }}
                    disabled={!canCreateOrSubmit}
                    className="inline-flex items-center gap-1.5 h-8 px-3 rounded-md border border-border text-xs font-semibold text-destructive hover:bg-red-50 dark:hover:bg-red-950/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <Trash2 size={13} /> Delete Submitter
                  </button>
                )}
                {ncbiSaveStatus === "saved" && (
                  <span className="inline-flex items-center gap-1 text-xs font-medium text-green-600 dark:text-green-400">
                    <Check size={13} /> Saved for future use
                  </span>
                )}
              </div>
              {ncbiSaveStatus === "error" && ncbiSaveError && (
                <ul className="space-y-0.5">
                  {ncbiSaveError.map((msg, i) => (
                    <li key={i} className="flex items-start gap-1.5 text-xs text-destructive">
                      <AlertCircle size={12} className="shrink-0 mt-0.5" />
                      <span>{msg}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {dbs.gisaid && (
            <div className="w-full rounded-xl border border-border bg-muted/10 p-3 space-y-3">
              <p className="text-xs font-bold text-foreground uppercase tracking-wider">GISAID</p>
              <div>
                <FieldLabel>Username <span className="text-destructive">*</span></FieldLabel>
                {gisaidSubmitters.length > 0 && (
                  <div className="flex gap-2 mb-2">
                    <button type="button" disabled={!canCreateOrSubmit} onClick={() => { setGisaidUserMode("new"); setGisaidSelectedSubmitterId(""); setGisaidSaveStatus("idle"); setGisaidSaveError(null); setGisaidDeleteStatus("idle"); setGisaidDeleteError(null); clearGisaidFields(); }}
                      className={cn("px-3 py-1 rounded-full text-xs font-semibold border transition-colors disabled:opacity-60 disabled:cursor-not-allowed",
                        gisaidUserMode === "new" ? "bg-primary text-primary-foreground border-primary" : "border-border text-muted-foreground hover:border-primary hover:text-primary")}>
                      New User
                    </button>
                    <button type="button" disabled={!canCreateOrSubmit} onClick={() => { setGisaidUserMode("existing"); setGisaidSaveStatus("idle"); setGisaidSaveError(null); setGisaidDeleteStatus("idle"); setGisaidDeleteError(null); }}
                      className={cn("px-3 py-1 rounded-full text-xs font-semibold border transition-colors disabled:opacity-60 disabled:cursor-not-allowed",
                        gisaidUserMode === "existing" ? "bg-primary text-primary-foreground border-primary" : "border-border text-muted-foreground hover:border-primary hover:text-primary")}>
                      Existing User
                    </button>
                  </div>
                )}
                {gisaidUserMode === "existing" && gisaidSubmitters.length > 0 ? (
                  <ExistingSubmitterPicker
                    submitters={gisaidSubmitters}
                    loading={gisaidSubmittersLoading}
                    error={gisaidSubmittersError}
                    selectedId={gisaidSelectedSubmitterId}
                    onSelect={selectGisaidSubmitter}
                    placeholder="Select a GISAID submitter…"
                    disabled={!canCreateOrSubmit}
                  />
                ) : (
                  <input
                    value={gisaidUsername}
                    onChange={(e) => setGisaidUsername(e.target.value)}
                    placeholder="e.g. your GISAID username"
                    autoComplete="off"
                    disabled={!canCreateOrSubmit}
                    className="w-full h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-60 disabled:cursor-not-allowed disabled:bg-muted"
                  />
                )}
              </div>
              <div>
                <FieldLabel>Password <span className="text-destructive">*</span></FieldLabel>
                <PasswordInput value={gisaidPassword} onChange={(e) => setGisaidPassword(e.target.value)} disabled={!canCreateOrSubmit} />
              </div>
              <div>
                <FieldLabel>Client-Id <span className="text-destructive">*</span></FieldLabel>
                <input
                  value={gisaidClientId}
                  onChange={(e) => setGisaidClientId(e.target.value)}
                  autoComplete="off"
                  disabled={!canCreateOrSubmit}
                  className="w-full h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-60 disabled:cursor-not-allowed disabled:bg-muted"
                />        
              </div>
              <div className="flex items-center gap-3 pt-1 flex-wrap">
                <button
                  type="button"
                  onClick={handleSaveGisaidSubmitter}
                  disabled={gisaidSaveStatus === "saving" || !canCreateOrSubmit}
                  className="inline-flex items-center gap-1.5 h-8 px-3 rounded-md bg-primary text-xs font-semibold text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {gisaidSaveStatus === "saving" ? <RefreshCw size={13} className="animate-spin" /> : <Save size={13} />}
                  Save GISAID Credentials
                </button>
                {gisaidSelectedSubmitterId && (
                  <button
                    type="button"
                    onClick={() => { setGisaidDeleteStatus("idle"); setGisaidDeleteError(null); setDeleteSubmitterModal("GISAID"); }}
                    disabled={!canCreateOrSubmit}
                    className="inline-flex items-center gap-1.5 h-8 px-3 rounded-md border border-border text-xs font-semibold text-destructive hover:bg-red-50 dark:hover:bg-red-950/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <Trash2 size={13} /> Delete Submitter
                  </button>
                )}
                {gisaidSaveStatus === "saved" && (
                  <span className="inline-flex items-center gap-1 text-xs font-medium text-green-600 dark:text-green-400">
                    <Check size={13} /> Saved for future use
                  </span>
                )}
              </div>
              {gisaidSaveStatus === "error" && gisaidSaveError && (
                <ul className="space-y-0.5">
                  {gisaidSaveError.map((msg, i) => (
                    <li key={i} className="flex items-start gap-1.5 text-xs text-destructive">
                      <AlertCircle size={12} className="shrink-0 mt-0.5" />
                      <span>{msg}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </>
      )}

      {/* ── Submission inputs ────────────── */}
      <SectionHeader id="seqsender-section-inputs" title="Submission Inputs" icon={Upload} open={openSections.inputs} onToggle={() => toggleSection("inputs")} />
      {openSections.inputs && (
        <>
          {/* ── Submission name ────────────── */}
          <div className="w-full">
            <FieldLabel>Submission Name <span className="text-destructive">*</span></FieldLabel>
            <input value={subName} onChange={(e) => setSubName(e.target.value.replace(/\s+/g, "_"))}
              placeholder="e.g. FLU_H3N2_2026"
              disabled={!!initialSubmission || submitted}
              className="w-full h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:bg-muted disabled:opacity-60" />
          </div>

          {(dbs.biosample || dbs.sra || dbs.genbank) && (
            <>
              {/* ── Publication ────────────── */}
              <div className="w-full">
                <div className="grid grid-cols-1 gap-3">
                  <div>
                    <FieldLabel>Publication Title</FieldLabel>
                    <input value={ncbiPubTitle} onChange={(e) => setNcbiPubTitle(e.target.value)}
                      disabled={!canCreateOrSubmit}
                      className="w-full h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:bg-muted disabled:opacity-60" />
                  </div>
                  <div>
                    <FieldLabel>Publication Status</FieldLabel>
                    <select value={ncbiPubStatus} onChange={(e) => setNcbiPubStatus(e.target.value)}
                      disabled={!canCreateOrSubmit}
                      className="w-full h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:bg-muted disabled:opacity-60">
                      <option value="Unpublished">Unpublished</option>
                      <option value="In-press">In Press</option>
                      <option value="Published">Published</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* ── Release ────────────── */}
              <div className="w-full">
                <FieldLabel>Specified Release Date</FieldLabel>
                <input type="date" value={ncbiPubReleaseDate} onChange={(e) => setNcbiPubReleaseDate(e.target.value)}
                  disabled={!canCreateOrSubmit}
                  className="w-full h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:bg-muted disabled:opacity-60" />
              </div>
            </>
          )}

          {/* ── File inputs ────────────── */}
          {[
            { label: "Metadata File",  required: true,  val: metaFile,      set: setMetaFile,       accept: ".csv,.tsv,.xlsx",      ph: "metadata.csv",            show: true, downloadUrl: API.downloadSeqsenderMetadata, onFile: (files) => { setMetaFileObject(files[0] ?? null); setMetadataUndoSnapshot(null); } },
            { label: "FASTA File",  required: dbs.genbank || dbs.gisaid,  val: fastaFile,     set: setFastaFile,      accept: ".fasta,.fa,.fna",      ph: "sequences.fasta",         show: true, downloadUrl: API.downloadSeqsenderFasta, onFile: (files) => setFastaFileObject(files[0] ?? null) },
            { label: "Raw Reads (FASTQs)", required: true, val: rawReadsFiles, set: setRawReadsFiles, accept: ".fastq,.fq,.fastq.gz,.fq.gz", ph: "e.g. sample_R1.fastq.gz, sample_R2.fastq.gz", show: dbs.sra, multiple: true, downloadUrl: API.downloadSeqsenderRawReads, downloadLabel: "Download stored raw reads (.zip)", onFile: (files) => setRawReadsFileObjects(files) },
          ].filter(({ show }) => show).map(({ label, required, val, set, accept, ph, desc, multiple, downloadUrl, downloadLabel, onFile }) => (
            <div key={label} className="w-full">
              <FieldLabel>{label} {required && <span className="text-destructive">*</span>}</FieldLabel>
              {desc && <p className="text-xs text-muted-foreground mb-2">{desc}</p>}
              <div className="flex w-full gap-2">
                <input value={val} onChange={(e) => set(e.target.value)} placeholder={ph}
                  disabled={!canCreateOrSubmit}
                  className="flex-1 h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:bg-muted disabled:opacity-60" />
                <label className={cn(
                  "flex items-center gap-1.5 px-3 h-9 rounded-md border border-border bg-muted/20 text-xs text-muted-foreground transition-colors",
                  !canCreateOrSubmit ? "cursor-not-allowed opacity-60" : "hover:bg-muted/40 cursor-pointer"
                )}>
                  <FolderOpen size={13} /> Browse
                  <input type="file" className="hidden" accept={accept}
                    multiple={!!multiple}
                    disabled={!canCreateOrSubmit}
                    onChange={(e) => {
                      const files = Array.from(e.target.files ?? []);
                      if (files.length) {
                        set(files.map(file => file.name).join(", "));
                        onFile?.(files);
                      }
                    }} />
                </label>
              </div>
              {initialSubmission && downloadUrl && (
                <button
                  type="button"
                  onClick={() => downloadStoredFile(storedDownloadUrl(downloadUrl), label, downloadLabel ?? "stored_file")}
                  disabled={storedDownloading === label}
                  className="mt-1.5 inline-flex items-center gap-1 text-xs font-mono text-primary hover:underline disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {storedDownloading === label ? <RefreshCw size={11} className="shrink-0 animate-spin" /> : <Download size={11} className="shrink-0" />} {downloadLabel ?? "Download stored file"}
                </button>
              )}
              {storedDownloadError?.field === label && (
                <p className="mt-1 flex items-center gap-1 text-xs text-destructive">
                  <AlertCircle size={11} className="shrink-0" /> {storedDownloadError.message}
                </p>
              )}
            </div>
          ))}

          {/* ── GISAID CLI: New upload vs reuse the existing file already stored for this organism ────────────── */}
          {dbs.gisaid && (
            <div className="w-full">
              <FieldLabel>GISAID CLI <span className="text-destructive">*</span></FieldLabel>
              <div className="flex gap-2 mb-2">
                <button type="button" disabled={!canCreateOrSubmit}
                  onClick={() => { setGisaidCliMode("new"); setGisaidCliFile(""); setGisaidCliFileObject(null); }}
                  className={cn("px-3 py-1 rounded-full text-xs font-semibold border transition-colors disabled:cursor-not-allowed disabled:opacity-60",
                    gisaidCliMode === "new" ? "bg-primary text-primary-foreground border-primary" : "border-border text-muted-foreground hover:border-primary hover:text-primary")}>
                  New CLI
                </button>
                <button type="button" disabled={!canCreateOrSubmit}
                  onClick={() => { setGisaidCliMode("existing"); setGisaidCliFile(""); setGisaidCliFileObject(null); }}
                  className={cn("px-3 py-1 rounded-full text-xs font-semibold border transition-colors disabled:cursor-not-allowed disabled:opacity-60",
                    gisaidCliMode === "existing" ? "bg-primary text-primary-foreground border-primary" : "border-border text-muted-foreground hover:border-primary hover:text-primary")}>
                  Existing CLI
                </button>
              </div>
              {gisaidCliMode === "new" ? (
                <div className="flex w-full gap-2">
                  <input value={gisaidCliFile} onChange={(e) => setGisaidCliFile(e.target.value)} placeholder="e.g. fluCLI"
                    disabled={!canCreateOrSubmit}
                    className="flex-1 h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:bg-muted disabled:opacity-60" />
                  <label className={cn(
                    "flex items-center gap-1.5 px-3 h-9 rounded-md border border-border bg-muted/20 text-xs text-muted-foreground transition-colors",
                    !canCreateOrSubmit ? "cursor-not-allowed opacity-60" : "hover:bg-muted/40 cursor-pointer"
                  )}>
                    <FolderOpen size={13} /> Browse
                    <input type="file" className="hidden" accept="binary"
                      disabled={!canCreateOrSubmit}
                      onChange={(e) => {
                        const f = e.target.files?.[0];
                        if (f) { setGisaidCliFile(f.name); setGisaidCliFileObject(f); }
                        e.target.value = "";
                      }} />
                  </label>
                </div>
              ) : (
                <p className="flex items-center gap-1.5 text-xs text-muted-foreground rounded-md border border-border bg-muted/20 px-3 h-9">
                  <FolderOpen size={13} className="shrink-0" /> Will reuse the CLI file already stored in this organism's submission folder.
                </p>
              )}
            </div>
          )}
        </>
      )}

      {/* ── Submission options ────────────── */}
      <SectionHeader id="seqsender-section-options" title="Submission Options" icon={Settings2} open={openSections.options} onToggle={() => toggleSection("options")} />
      {openSections.options && (
        <>
          {/* ── Submission options toggles ────────────── */}
          {[
            { label: "--table2asn",   desc: "Use table2asn for GenBank submission (required for annotated sequences)", val: table2asn, set: setTable2asn, show: dbs.genbank },
            { label: "--test",        desc: "Run in test mode — submit to test servers without affecting production (applicable to NCBI databases only)",  val: testMode,  set: setTestMode,  show: true },
          ].filter(({ show }) => show).map(({ label, desc, val, set }) => (
            <Fragment key={label}>
              <button onClick={() => set((v) => !v)} disabled={!canCreateOrSubmit}
                className="flex w-full items-center justify-between gap-4 p-3 rounded-xl border border-border bg-muted/10 hover:bg-muted/20 transition-colors text-left disabled:cursor-not-allowed disabled:opacity-60">
                <div>
                  <p className="text-sm font-mono font-semibold">{label}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">{desc}</p>
                </div>
                <span className={cn("relative w-10 h-5 rounded-full transition-colors shrink-0 mt-0.5 pointer-events-none", val ? "bg-primary" : "bg-muted")}>
                  <span className={cn("absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform", val ? "translate-x-5" : "translate-x-0.5")} />
                </span>
              </button>

              {label === "--table2asn" && val && (organism === "FLU" || organism === "COV") && (
                <div className="w-full rounded-xl border border-border bg-muted/10 p-3">
                  <p className="text-sm font-mono font-semibold">--gff_file <span className="text-destructive">*</span></p>
                  <p className="text-xs text-muted-foreground mb-2 mt-0.5">Provide an annotation file for table2asn submission.</p>
                  <div className="flex w-full gap-2">
                    <input value={gffFile} onChange={(e) => setGffFile(e.target.value)} placeholder="annotation.gff"
                      disabled={!canCreateOrSubmit}
                      className="flex-1 h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:bg-muted disabled:opacity-60" />
                    <label className={cn(
                      "flex items-center gap-1.5 px-3 h-9 rounded-md border border-border bg-muted/20 text-xs text-muted-foreground transition-colors",
                      !canCreateOrSubmit ? "cursor-not-allowed opacity-60" : "hover:bg-muted/40 cursor-pointer"
                    )}>
                      <FolderOpen size={13} /> Browse
                      <input type="file" className="hidden" accept=".gff,.gff3"
                        disabled={!canCreateOrSubmit}
                        onChange={(e) => {
                          const f = e.target.files?.[0];
                          if (f) {
                            setGffFile(f.name);
                            setGffFileObject(f);
                          }
                          e.target.value = "";
                        }} />
                    </label>
                  </div>
                  {initialSubmission && gffFile && (
                    <button
                      type="button"
                      onClick={() => downloadStoredFile(storedDownloadUrl(API.downloadSeqsenderGff), "gff", "annotation.gff")}
                      disabled={storedDownloading === "gff"}
                      className="mt-1.5 inline-flex items-center gap-1 text-xs font-mono text-primary hover:underline disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {storedDownloading === "gff" ? <RefreshCw size={11} className="shrink-0 animate-spin" /> : <Download size={11} className="shrink-0" />} Download stored file
                    </button>
                  )}
                  {storedDownloadError?.field === "gff" && (
                    <p className="mt-1 flex items-center gap-1 text-xs text-destructive">
                      <AlertCircle size={11} className="shrink-0" /> {storedDownloadError.message}
                    </p>
                  )}
                </div>
              )}
            </Fragment>
          ))}
        </>
      )}

      {/* ── Submit button ────────────── */}
      <SectionHeader id="seqsender-section-submit" title="Review & Submit" icon={Rocket} open={openSections.submit} onToggle={() => toggleSection("submit")} />      
      {openSections.submit && (
        <>
          {metadataPreview.loading && (
            <div className="flex w-full items-center gap-2 rounded-lg border border-border bg-muted/10 px-3 py-2 text-xs text-muted-foreground">
              <RefreshCw size={13} className="shrink-0 animate-spin" /> Loading metadata tables…
            </div>
          )}
          {!metadataPreview.loading && metadataPreview.error && (
            <div className="flex w-full items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-destructive dark:border-red-800 dark:bg-red-950/20">
              <AlertCircle size={13} className="mt-0.5 shrink-0" /> {metadataPreview.error}
            </div>
          )}
          {!metadataPreview.loading && !metadataPreview.error && metadataPreview.columns.length > 0 && (
            <div className="w-full space-y-3">
              {selectedMetadataTables.map(({ key, title, columns, rows, sampleNameColumn }) => (
                <SeqSenderMetadataTable
                  key={key}
                  title={title}
                  columns={columns}
                  rows={rows}
                  onRemoveRows={removeMetadataRows}
                  onUndoRows={undoMetadataRemoval}
                  canUndo={!!metadataUndoSnapshot}
                  editable={canEditSubmission}
                  sampleNameColumn={sampleNameColumn}
                />
              ))}
            </div>
          )}

          {submitError && submitError.length > 0 && (
            <div className="w-full rounded-lg border bg-red-50 border-red-200 dark:bg-red-950/20 dark:border-red-800 px-3 py-2 space-y-1 text-left text-xs">
              <p className="font-semibold text-destructive mb-1">Please provide the following required fields before submitting:</p>
              {submitError.map((msg, i) => (
                <div key={i} className="flex items-start gap-2">
                  <AlertCircle size={12} className="shrink-0 mt-0.5 text-destructive" />
                  <span className="text-destructive">{msg}</span>
                </div>
              ))}
            </div>
          )}

          {uploadError && (
            <div className="flex w-full items-start gap-2 rounded-lg border bg-red-50 border-red-200 px-3 py-2 text-xs dark:border-red-800 dark:bg-red-950/20">
              <AlertCircle size={12} className="shrink-0 mt-0.5 text-destructive" />
              <span className="text-destructive">{uploadError}</span>
            </div>
          )}

          {createFilesError && (
            <div className="flex w-full items-start gap-2 rounded-lg border bg-red-50 border-red-200 px-3 py-2 text-xs dark:border-red-800 dark:bg-red-950/20">
              <AlertCircle size={12} className="shrink-0 mt-0.5 text-destructive" />
              <span className="text-destructive">{createFilesError}</span>
            </div>
          )}

          {createFilesResult && (
            <div className="flex w-full items-start gap-2 rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-xs dark:border-green-800 dark:bg-green-950/20">
              <Check size={12} className="shrink-0 mt-0.5 text-green-700 dark:text-green-300" />
              <span className="text-green-700 dark:text-green-300">{createFilesResult.message || "Submission files were created successfully."}</span>
            </div>
          )}

          {/* ── Create submission files / Submit — disabled (not hidden) unless this is a new submission or a past submission still entirely CREATED ────────────── */}
          <button onClick={() => handleSubmit("prep")} disabled={!canCreateOrSubmit || creatingFiles || uploadingFiles || submissionPolling}
            className="flex w-full items-center gap-2 rounded-lg bg-primary px-5 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50">
            {creatingFiles ? <RefreshCw size={14} className="animate-spin" /> : <Package size={14} />}
            {creatingFiles ? "Creating files…" : `Create submission files for ${Object.entries(dbs).filter(([,v])=>v).map(([k])=>k).join(", ") || "selected databases"}`}
          </button>

          <button onClick={() => handleSubmit("submit")} disabled={!canCreateOrSubmit || uploadingFiles || submissionPolling}
            className="flex w-full items-center gap-2 rounded-lg bg-primary px-5 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50">
            {uploadingFiles || submissionPolling ? <RefreshCw size={14} className="animate-spin" /> : <Rocket size={14} />}
            {uploadingFiles ? "Uploading…" : submissionPolling ? "SeqSender running…" : `Submit to ${Object.entries(dbs).filter(([,v])=>v).map(([k])=>k).join(", ") || "selected databases"}`}
          </button>
        </>
      )}

      {/* ── Submission status — header always shows; body depends on new/submitted/past-selected state ────────────── */}
      <SectionHeader id="seqsender-section-status" title="Submission Status" icon={ClipboardList} open={openSections.status} onToggle={() => toggleSection("status")} />
      {openSections.status && (
        <>
          {/* ── New submission: nothing submitted yet and no past submission selected ────────────── */}
          {!submitted && !initialSubmission && !submissionJob && (
            <div className="flex w-full items-start gap-2 rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-xs text-warning">
              <AlertCircle size={13} className="mt-0.5 shrink-0" />
              <span>Submission status will appear here once the submission is submitted and proccessed.</span>
            </div>
          )}

          {/* ── Latest submission status message — prefers a manual Refresh Status check over the process poller ────────────── */}
          {(() => {
            const displayedStatus = refreshedSubmissionStatus ?? submissionProcessStatus;
            return (submitted || initialSubmission || submissionJob) && displayedStatus?.message && (
            <div className={cn(
              "flex w-full items-start gap-2 rounded-lg border px-3 py-2 text-xs",
              displayedStatus?.status === "FAILED"
                ? "border-red-200 bg-red-50 text-destructive dark:border-red-800 dark:bg-red-950/20"
                : ["SUBMITTED", "COMPLETED"].includes(displayedStatus?.status)
                  ? "border-green-200 bg-green-50 text-green-700 dark:border-green-800 dark:bg-green-950/20 dark:text-green-300"
                  : "border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-800 dark:bg-blue-950/20 dark:text-blue-300"
            )}>
              {(submissionPolling || existingStatusRefreshing)
                ? <RefreshCw size={13} className="mt-0.5 shrink-0 animate-spin" />
                : ["SUBMITTED", "COMPLETED"].includes(displayedStatus?.status)
                  ? <Check size={13} className="mt-0.5 shrink-0" />
                  : <AlertCircle size={13} className="mt-0.5 shrink-0" />}
              <div className="min-w-0">
                <p className="mt-0.5 break-words opacity-80">
                  {displayedStatus?.message}
                  {submissionJob?.pid ? ` (PID ${submissionJob.pid})` : ""}
                </p>
              </div>
            </div>
            );
          })()}

          {/* ── Submission error message — only relevant after this session's Submit was clicked ────────────── */}
          {(submissionStatusError || existingStatusError) && (
            <div className="flex w-full items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs dark:border-red-800 dark:bg-red-950/20">
              <AlertCircle size={13} className="mt-0.5 shrink-0 text-destructive" />
              <div className="min-w-0">
                <p className="font-semibold text-destructive">Unable to check SeqSender status</p>
                <p className="mt-0.5 break-words text-destructive opacity-80">{submissionStatusError || existingStatusError}</p>
              </div>
            </div>
          )}

          {/* ── Submission status cards — shown for a submitted session or a selected past submission ────────────── */}
          {(submitted || initialSubmission || submissionJob) && (
            <div className="w-full space-y-2">
              {[
                { key: "biosample", label: "BioSample", accessionLabel: "Submission ID",  placeholder: "e.g. SAMN00000000"    },
                { key: "sra",       label: "SRA",       accessionLabel: "Submission ID",  placeholder: "e.g. SRR00000000"    },
                { key: "genbank",   label: "GenBank",   accessionLabel: "Submission ID",  placeholder: "e.g. MN000000"       },
                { key: "gisaid",    label: "GISAID",    accessionLabel: "EPI ISL Accession",    placeholder: "e.g. EPI_ISL_000000" },
              ]
                .filter(({ key }) => dbs[key])
                .map(({ key, label, accessionLabel, placeholder }) => {
                  // Prefer a manual Refresh Status check (real SeqSender portal status), then this
                  // session's just-launched process status, then the selected past submission's stored row.
                  const refreshedEntry = refreshedSubmissionStatus?.database_statuses?.[key.toUpperCase()];
                  const storedRow = (existingRows.length ? existingRows : initialRows).find((row) => row.database === key.toUpperCase());
                  const dbStatus = refreshedEntry?.status
                    ?? submissionProcessStatus?.database_statuses?.[key.toUpperCase()]?.status
                    ?? (submissionJob && submissionProcessStatus?.status
                      ? submissionProcessStatus.status
                      : storedRow?.submission_status ?? "PENDING");
                  const dbAccession = refreshedEntry?.accession || storedRow?.ncbi_submission_id || "";
                  const rawStatusReportRows = refreshedSubmissionStatus?.submission_status_report?.[key.toUpperCase()] ?? [];
                  // Collapse duplicate rows for the same sample (e.g. re-checks appending to the
                  // report) down to one row per sample_name, keeping the most recently seen values.
                  const statusReportRows = Array.from(
                    rawStatusReportRows.reduce((map, row) => map.set(row.sample_name, row), new Map()).values()
                  );
                  return (
                  <div key={key} className="rounded-xl border border-border bg-muted/10 overflow-hidden">
                    <div className="flex items-center justify-between gap-2 px-3 py-2 bg-muted/20 border-b border-border">
                      <p className="text-xs font-bold tracking-wide text-foreground">{label}</p>
                      <span className="font-mono px-2 py-0.5 rounded-full bg-primary/10 text-xs">Submission ID: {dbAccession || "—"}</span>
                      <span className={cn("px-2 py-0.5 rounded-full text-xs font-medium", SUBMISSION_STATUS_BADGE_STYLES[dbStatus] ?? "bg-muted text-muted-foreground")}>{dbStatus}</span>
                    </div>
                    <div className="px-3 py-2 space-y-1.5">
                      <div className="flex items-center justify-between text-xs">
                        <span>
                          {storedRow?.date_submitted && (
                            <span className="font-mono px-2 py-0.5 rounded-full bg-primary/10 text-primary">Submitted {storedRow.date_submitted}</span>
                          )}
                        </span>
                        <span>
                          {storedRow?.date_updated && (
                            <span className="font-mono px-2 py-0.5 rounded-full bg-primary/10 text-primary">Updated {storedRow.date_updated}</span>
                          )}
                        </span>
                      </div>
                      {statusReportRows.length > 0 && (
                        <StatusReportTable
                          rows={statusReportRows}
                          onMessageChange={(sampleName, message) => {
                            const database = key.toUpperCase();
                            setStatusReportMessageEdits((prev) => ({
                              ...prev,
                              [database]: { ...prev[database], [sampleName]: message },
                            }));
                            setCommentsSaveStatus((prev) => ({ ...prev, [database]: "idle" }));
                            setCommentsSaveError((prev) => ({ ...prev, [database]: null }));
                          }}
                        />
                      )}
                      {/* ── Comments — free-text notes attached to this database's submission row ────────────── */}
                      <div className="space-y-1.5 pt-1">
                        <label htmlFor={`seqsender-comments-${key}`} className="text-xs font-semibold text-foreground">Comments</label>
                        <textarea
                          id={`seqsender-comments-${key}`}
                          rows={2}
                          value={comments[key.toUpperCase()] ?? ""}
                          onChange={(e) => {
                            const db = key.toUpperCase();
                            const value = e.target.value;
                            setComments((prev) => ({ ...prev, [db]: value }));
                            setCommentsSaveStatus((prev) => ({ ...prev, [db]: "idle" }));
                            setCommentsSaveError((prev) => ({ ...prev, [db]: null }));
                          }}
                          placeholder={`Add any notes about the ${label} submission here...`}
                          className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
                        />
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => saveSubmissionComments(key.toUpperCase())}
                            disabled={commentsSaveStatus[key.toUpperCase()] === "saving"}
                            className="flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1 text-[11px] font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            {commentsSaveStatus[key.toUpperCase()] === "saving" ? "Saving…" : "Save Comments"}
                          </button>
                          {commentsSaveStatus[key.toUpperCase()] === "saved" && (
                            <span className="text-[11px] font-medium text-emerald-600 dark:text-emerald-400">Saved</span>
                          )}
                          {commentsSaveStatus[key.toUpperCase()] === "error" && (
                            <span className="text-[11px] font-medium text-destructive">{commentsSaveError[key.toUpperCase()] || "Failed to save comments."}</span>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                  );
                })}
            </div>
          )}

          {/* ── Refresh status button — hidden for a past submission stuck at CREATED, since it was never actually submitted ────────────── */}
          {(submitted || initialSubmission || submissionJob) && !(initialSubmission && !submitted && existingRows.length > 0 && existingRows.every((row) => row.submission_status === "CREATED")) && (
            <button
              onClick={refreshSubmissionStatus}
              disabled={submissionPolling || existingStatusRefreshing}
              className="flex w-full items-center gap-2 rounded-lg bg-primary px-5 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <RefreshCw size={14} className={(submissionPolling || existingStatusRefreshing) ? "animate-spin" : ""} />
              {(submissionPolling || existingStatusRefreshing) ? "Checking Status…" : "Refresh Status"}
            </button>
          )}
        </>
      )}

      {/* ── Delete Submitter confirmation modal (shared by NCBI/GISAID) ────────────── */}
      {deleteSubmitterModal && (() => {
        const isNcbi = deleteSubmitterModal === "NCBI";
        const submitters = isNcbi ? ncbiSubmitters : gisaidSubmitters;
        const selectedId = isNcbi ? ncbiSelectedSubmitterId : gisaidSelectedSubmitterId;
        const submitter = submitters.find((s) => String(s.submitter_id) === selectedId);
        const deleteStatus = isNcbi ? ncbiDeleteStatus : gisaidDeleteStatus;
        const deleteError = isNcbi ? ncbiDeleteError : gisaidDeleteError;
        const handleDelete = isNcbi ? handleDeleteNcbiSubmitter : handleDeleteGisaidSubmitter;
        const closeModal = () => {
          if (deleteStatus === "deleting") return;
          setDeleteSubmitterModal(null);
        };
        return (
          <div onClick={closeModal} className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
            <div onClick={(e) => e.stopPropagation()} className="bg-background border border-border rounded-xl p-6 max-w-md w-full mx-4 shadow-xl flex flex-col gap-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-foreground">Delete {deleteSubmitterModal} Submitter</h3>
                <button onClick={closeModal} className="text-muted-foreground hover:text-foreground transition-colors">
                  <X size={14} />
                </button>
              </div>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Are you sure you want to permanently delete the {deleteSubmitterModal} submitter{" "}
                <span className="font-mono font-semibold text-foreground">{submitter?.submitter_name ?? "this submitter"}</span>? This cannot be undone.
              </p>
              {deleteStatus === "error" && deleteError && (
                <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs dark:border-red-800 dark:bg-red-950/20">
                  <AlertCircle size={12} className="shrink-0 mt-0.5 text-destructive" />
                  <span className="text-destructive">{deleteError}</span>
                </div>
              )}
              <div className="flex gap-2 justify-end pt-1">
                <button
                  onClick={closeModal}
                  disabled={deleteStatus === "deleting"}
                  className="px-4 py-1.5 rounded-lg border border-border text-xs text-muted-foreground hover:bg-muted/60 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Cancel
                </button>
                <button
                  onClick={handleDelete}
                  disabled={deleteStatus === "deleting"}
                  className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-destructive text-destructive-foreground text-xs font-semibold hover:bg-destructive/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {deleteStatus === "deleting" ? <RefreshCw size={11} className="animate-spin" /> : <Trash2 size={11} />}
                  {deleteStatus === "deleting" ? "Deleting…" : "Delete"}
                </button>
              </div>
            </div>
          </div>
        );
      })()}
    </>
  );
});

// Sortable columns for the Past Submissions table, keyed by the value each column sorts on.
const PAST_SUBMISSIONS_COLUMNS = [
  { key: "submission_name", label: "Submission Name" },
  { key: "organism", label: "Organism" },  
  { key: "number_of_samples", label: "Databases" },
  { key: "submission_type", label: "Type" },
  { key: "submission_status", label: "Status" },
  { key: "accessions", label: "Submission IDs" },
  { key: "date_submitted", label: "Submitted" },
  { key: "date_updated", label: "Updated" },
];

// Table body rows beyond this count get a scrollable, sticky-header container instead of growing forever.
const PAST_SUBMISSIONS_MAX_VISIBLE_ROWS = 20;

function PastSubmissionsPanel({ onSelectSubmission }) {
  const [submissions, setSubmissions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [sortColumn, setSortColumn] = useState("date_submitted"); // which column header is currently sorted
  const [sortDir, setSortDir] = useState("desc"); // "asc" | "desc"
  const [selectedRow, setSelectedRow] = useState(null); // row highlighted by a single click (Copy/Delete/Update Status act on this)
  const [actionMode, setActionMode] = useState(null); // null | "copy" | "delete" — which confirmation modal is open
  const [copyName, setCopyName] = useState("");
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState(null);
  const [statusMessage, setStatusMessage] = useState(null); // { type: "warning"|"error"|"success", text } feedback banner for the Update Status action

  const loadSubmissions = useCallback(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetch(API.listSubmissions)
      .then(async (response) => {
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Failed to load submissions.");
        if (!cancelled) setSubmissions(Array.isArray(data.submission_info) ? data.submission_info : []);
      })
      .catch((fetchError) => {
        if (!cancelled) setError(fetchError.message || "Failed to load submissions.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => loadSubmissions(), [loadSubmissions]);

  // The backend returns one flat row per (submission_name, database) pair — group them back
  // into a single entry per submission, the way each MIRA run is a single entry in Past Runs.
  const groupedSubmissions = useMemo(() => {
    const bySubmission = new Map();
    for (const row of submissions) {
      const key = `${row.submission_name}::${row.organism}::${row.submission_type}`;
      if (!bySubmission.has(key)) {
        bySubmission.set(key, {
          submission_id: row.submission_id,
          submission_name: row.submission_name,
          organism: row.organism,
          submission_type: row.submission_type,
          submitter_name: row.submitter_name,
          date_submitted: row.date_submitted,
          date_updated: row.date_updated,
          number_of_samples: row.number_of_samples,
          submission_status: row.submission_status,
          databases: [],
          rows: [],
        });
      }
      bySubmission.get(key).databases.push({
        database: row.database,
        status: row.submission_status,
        accession: row.ncbi_submission_id,
        ncbiStatus: row.ncbi_submission_status,
        samples: row.number_of_samples,
      });
      bySubmission.get(key).rows.push(row);
    }
    return Array.from(bySubmission.values());
  }, [submissions]);

  // Duplicate the selected submission's database rows and stored files under a new name.
  const handleCopySubmission = async () => {
    if (!selectedRow) return;
    const trimmed = copyName.trim().replace(/\s+/g, "_");
    if (!trimmed) { setActionError("Please enter a new submission name."); return; }
    setActionLoading(true);
    setActionError(null);
    try {
      const res = await fetch(API.copySeqsenderSubmission, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          submission_name: selectedRow.submission_name,
          organism: selectedRow.organism,
          new_submission_name: trimmed,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "Failed to copy submission.");
      setActionMode(null);
      setCopyName("");
      setSelectedRow(null);
      loadSubmissions();
    } catch (err) {
      setActionError(err.message || "Failed to copy submission.");
    } finally {
      setActionLoading(false);
    }
  };

  // Permanently remove the selected submission's database rows and stored files.
  const handleDeleteSubmission = async () => {
    if (!selectedRow) return;
    setActionLoading(true);
    setActionError(null);
    try {
      const res = await fetch(API.deleteSeqsenderSubmission, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          submission_name: selectedRow.submission_name,
          organism: selectedRow.organism,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "Failed to delete submission.");
      setActionMode(null);
      setSelectedRow(null);
      loadSubmissions();
    } catch (err) {
      setActionError(err.message || "Failed to delete submission.");
    } finally {
      setActionLoading(false);
    }
  };

  // Ask SeqSender to check the real submission portals for the selected submission, then reload
  // the list so the updated status/accession show up in the table.
  const handleUpdateStatus = async () => {   
    if (!selectedRow) return;
    setStatusMessage(null);
    // A submission still stuck at CREATED was never actually submitted — there's no portal
    // status to check yet, so warn the user instead of calling the backend.
    if (selectedRow.submission_status === "CREATED") {
      setStatusMessage({ type: "warning", text: "This submission has not been submitted yet. Please open it, submit it, and then check its status again." });
      return;
    }
    setActionLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("submission_name", selectedRow.submission_name);
      params.set("organism", selectedRow.organism);
      selectedRow.databases.forEach(({ database }) => params.append("database", database));
      params.set("submission_type", selectedRow.submission_type);
      const res = await fetch(`${API.checkSeqsenderSubmissionStatus}?${params.toString()}`);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || data.message || "Failed to check submission status.");
      setStatusMessage({ type: "success", text: data.message || "Submission status updated." });
      loadSubmissions();
    } catch (err) {
      setStatusMessage({ type: "error", text: err.message || "Failed to update submission status." });
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 py-10 text-xs text-muted-foreground">
        <RefreshCw size={13} className="animate-spin" /> Loading submissions…
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-destructive dark:border-red-800 dark:bg-red-950/20">
        <AlertCircle size={13} className="mt-0.5 shrink-0" /> {error}
      </div>
    );
  }

  if (groupedSubmissions.length === 0) {
    return <p className="py-10 text-left text-xs text-muted-foreground">There are no past submissions.</p>;
  }

  // Toggle sort direction when clicking the already-active column header, otherwise switch to the
  // clicked column ascending.
  const handleSort = (column) => {
    if (sortColumn === column) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortColumn(column);
      setSortDir("asc");
    }
  };

  // Extract the value a given row sorts on for the currently selected column.
  const getSortValue = (row, column) => {
    switch (column) {
      case "organism": return row.organism ?? "";
      case "databases": return row.databases.map((d) => d.database).sort().join(", ");
      case "submission_type": return row.submission_type ?? "";
      case "number_of_samples": {
        const sampleCounts = row.databases.map((d) => d.samples).filter((n) => typeof n === "number");
        return sampleCounts.length ? sampleCounts.reduce((sum, n) => sum + n, 0) : null;
      }
      case "submission_status": return row.submission_status ?? "";
      case "accessions": return row.databases.map((d) => d.accession).filter(Boolean).sort().join(", ");
      case "date_updated": return row.date_updated ?? "";
      case "date_submitted": return row.date_submitted ?? "";
      default: return row.submission_name ?? "";
    }
  };

  const q = search.trim().toLowerCase();
  const filtered = (q
    ? groupedSubmissions.filter((s) =>
        [s.submission_name, s.organism, s.submission_type, s.submitter_name, ...s.databases.map((d) => d.database)]
          .some((v) => (v ?? "").toLowerCase().includes(q))
      )
    : groupedSubmissions
  ).slice().sort((a, b) => {
    const direction = sortDir === "asc" ? 1 : -1;
    const nameComparison = (a.submission_name ?? "").localeCompare(b.submission_name ?? "");
    const av = getSortValue(a, sortColumn);
    const bv = getSortValue(b, sortColumn);
    if (typeof av === "number" || typeof bv === "number" || av === null || bv === null) {
      if (av === null && bv === null) return direction * nameComparison;
      if (av === null) return 1;
      if (bv === null) return -1;
      return direction * (av - bv) || nameComparison;
    }
    const as = String(av).trim();
    const bs = String(bv).trim();
    if (!as && !bs) return direction * nameComparison;
    if (!as) return 1;
    if (!bs) return -1;
    return direction * as.localeCompare(bs, undefined, { numeric: true, sensitivity: "base" }) || nameComparison;
  });

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <FileSearch size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search submissions…"
            className="w-full h-8 pl-8 pr-3 rounded-lg border border-border bg-background text-xs font-mono focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
        <button
          type="button"
          title="Refresh"
          onClick={loadSubmissions}
          className="h-8 w-8 shrink-0 flex items-center justify-center rounded-lg border border-border text-muted-foreground hover:text-primary hover:border-primary transition-colors"
        >
          <RefreshCw size={13} />
        </button>
      </div>

      <div className="flex items-center gap-2">
        <button
          type="button"
          disabled={!selectedRow}
          onClick={() => { setStatusMessage(null); onSelectSubmission(selectedRow); }}
          className="flex items-center gap-1.5 px-3 py-1 rounded-md border border-primary bg-primary text-primary-foreground text-xs font-semibold hover:bg-primary/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed disabled:bg-primary/50"
        >
          <ExternalLink size={12} /> Open
        </button>
        <button
          type="button"
          disabled={!selectedRow}
          onClick={() => { setStatusMessage(null); setActionMode("copy"); setCopyName(`${selectedRow.submission_name}_copy`); setActionError(null); }}
          className="flex items-center gap-1.5 px-3 py-1 rounded-md border border-border text-xs font-semibold text-foreground hover:border-primary hover:text-primary transition-colors disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:border-border disabled:hover:text-foreground"
        >
          <Copy size={12} /> Copy
        </button>
        <button
          type="button"
          disabled={!selectedRow}
          onClick={() => { setStatusMessage(null); setActionMode("delete"); setActionError(null); }}
          className="flex items-center gap-1.5 px-3 py-1 rounded-md border border-border text-xs font-semibold text-destructive hover:bg-red-50 dark:hover:bg-red-950/20 transition-colors disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-transparent"
        >
          <Trash2 size={12} /> Delete
        </button>
        <button
          type="button"
          disabled={!selectedRow || actionLoading}
          onClick={handleUpdateStatus}
          className="flex items-center gap-1.5 px-3 py-1 rounded-md border border-border text-xs font-semibold text-foreground hover:border-primary hover:text-primary transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <RefreshCw size={12} className={actionLoading ? "animate-spin" : undefined} /> {actionLoading ? "Updating…" : "Update Status"}
        </button>
      </div>

      {statusMessage && (() => {
        const isWarning = statusMessage.type === "warning";
        const isError = statusMessage.type === "error";
        const Icon = isError ? AlertCircle : isWarning ? AlertCircle : Check;
        return (
          <div className={cn(
            "flex items-start gap-2 rounded-lg border px-3 py-2.5 text-xs font-medium shadow-sm",
            isError
              ? "border-red-300 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-950/30 dark:text-red-300"
              : isWarning
                ? "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-300"
                : "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-300"
          )}>
            <Icon size={14} className="mt-0.5 shrink-0" />
            <span>{statusMessage.text}</span>
          </div>
        );
      })()}

      {filtered.length === 0 ? (
        <p className="py-6 text-left text-xs text-muted-foreground">No submissions match your search.</p>
      ) : (
        <div className="overflow-hidden rounded-xl border border-border">
          <div className={cn("overflow-auto", filtered.length > PAST_SUBMISSIONS_MAX_VISIBLE_ROWS && "max-h-[720px]")}>
            <table className="w-full text-xs">
              <thead className="bg-muted sticky top-0 z-10">
                <tr>
                  {PAST_SUBMISSIONS_COLUMNS.map(({ key, label }) => (
                    <th key={key} className="whitespace-nowrap px-3 py-2 text-left text-[12px] font-semibold uppercase tracking-wider text-muted-foreground">
                      <button
                        type="button"
                        onClick={() => handleSort(key)}
                        className="flex items-center gap-1 hover:text-foreground transition-colors"
                      >
                        {label}
                        {sortColumn === key
                          ? sortDir === "asc" ? <ArrowUp size={10} className="text-primary shrink-0" /> : <ArrowDown size={10} className="text-primary shrink-0" />
                          : <ArrowUpDown size={10} className="opacity-30 shrink-0" />}
                      </button>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filtered.map((submission, index) => (
                  <tr
                    key={submission.submission_id ?? `${submission.submission_name}-${index}`}
                    role="button"
                    tabIndex={0}
                    title={`Click to select · double-click or "Open" to view ${submission.submission_name}`}
                    onClick={() => { setStatusMessage(null); setSelectedRow(submission); }}
                    onDoubleClick={() => { setStatusMessage(null); onSelectSubmission(submission); }}
                    className={cn(
                      "cursor-pointer transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary",
                      selectedRow?.submission_id === submission.submission_id ? "bg-primary/10" : "hover:bg-muted/40"
                    )}
                  >
                    <td className="whitespace-nowrap px-3 py-2 font-mono font-semibold text-foreground">{submission.submission_name}</td>
                    <td className="whitespace-nowrap px-3 py-2 font-mono text-foreground">{submission.organism}</td>
                    <td className="px-3 py-2">
                      <div className="flex flex-wrap gap-1">
                        {submission.databases.map(({ database, samples }) => (
                          <span
                            key={database}
                            title={`${database}: ${samples ?? "—"} samples`}
                            className="whitespace-nowrap rounded-full bg-muted px-2 py-0.5 font-mono text-[10px] font-medium text-foreground"
                          >
                            {database}: {samples ?? "—"}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="whitespace-nowrap px-3 py-2 font-mono text-foreground">{submission.submission_type}</td>
                    <td className="whitespace-nowrap px-3 py-2">
                      <span className={cn("px-2 py-0.5 rounded-full text-[10px] font-medium", SUBMISSION_STATUS_BADGE_STYLES[submission.submission_status] ?? "bg-muted text-muted-foreground")}>
                        {submission.submission_status || "—"}
                      </span>
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex flex-wrap gap-1">
                        {submission.databases.filter(({ accession }) => accession).map(({ database, accession, ncbiStatus }) => (
                          <span
                            key={database}
                            title={`${database}: ${accession}${ncbiStatus ? ` (${ncbiStatus})` : ""}`}
                            className="whitespace-nowrap rounded-full bg-muted px-2 py-0.5 font-mono text-[10px] font-medium text-foreground"
                          >
                            {database}: {accession}
                            {ncbiStatus ? <span className="text-muted-foreground"> · {ncbiStatus}</span> : null}
                          </span>
                        ))}
                        {submission.databases.every(({ accession }) => !accession) && (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </div>
                    </td>
                    <td className="whitespace-nowrap px-3 py-2 font-mono text-muted-foreground">{submission.date_submitted || "—"}</td>
                    <td className="whitespace-nowrap px-3 py-2 font-mono text-muted-foreground">{submission.date_updated || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Copy Submission modal ── */}
      {actionMode === "copy" && selectedRow && (
        <div onClick={() => setActionMode(null)} className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div onClick={(e) => e.stopPropagation()} className="bg-background border border-border rounded-xl p-6 max-w-md w-full mx-4 shadow-xl flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-foreground">Copy Submission</h3>
              <button onClick={() => setActionMode(null)} className="text-muted-foreground hover:text-foreground transition-colors"><X size={14} /></button>
            </div>
            <p className="text-xs text-muted-foreground">
              Duplicate <span className="font-mono font-semibold text-foreground">{selectedRow.submission_name}</span> (and its stored files) under a new name.
            </p>
            <div>
              <FieldLabel>New Submission Name</FieldLabel>
              <input
                value={copyName}
                onChange={(e) => setCopyName(e.target.value.replace(/\s+/g, "_"))}
                className="w-full h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            {actionError && (
              <div className="flex items-start gap-2 text-xs text-destructive">
                <AlertCircle size={12} className="shrink-0 mt-0.5" /> {actionError}
              </div>
            )}
            <div className="flex gap-2 justify-end pt-1">
              <button onClick={() => setActionMode(null)} className="px-4 py-1.5 rounded-lg border border-border text-xs text-muted-foreground hover:bg-muted/60 transition-colors">Cancel</button>
              <button
                onClick={handleCopySubmission}
                disabled={actionLoading}
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-primary text-primary-foreground text-xs font-semibold hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {actionLoading ? <RefreshCw size={11} className="animate-spin" /> : <Copy size={11} />}
                Copy
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Delete Submission modal ── */}
      {actionMode === "delete" && selectedRow && (
        <div onClick={() => setActionMode(null)} className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div onClick={(e) => e.stopPropagation()} className="bg-background border border-border rounded-xl p-6 max-w-md w-full mx-4 shadow-xl flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-foreground">Delete Submission</h3>
              <button onClick={() => setActionMode(null)} className="text-muted-foreground hover:text-foreground transition-colors"><X size={14} /></button>
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Are you sure you want to delete <span className="font-mono font-semibold text-foreground">{selectedRow.submission_name}</span>? This permanently removes its database rows and stored files.
            </p>
            {actionError && (
              <div className="flex items-start gap-2 text-xs text-destructive">
                <AlertCircle size={12} className="shrink-0 mt-0.5" /> {actionError}
              </div>
            )}
            <div className="flex gap-2 justify-end pt-1">
              <button onClick={() => setActionMode(null)} className="px-4 py-1.5 rounded-lg border border-border text-xs text-muted-foreground hover:bg-muted/60 transition-colors">Cancel</button>
              <button
                onClick={handleDeleteSubmission}
                disabled={actionLoading}
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-destructive text-destructive-foreground text-xs font-semibold hover:bg-destructive/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {actionLoading ? <RefreshCw size={11} className="animate-spin" /> : <Trash2 size={11} />}
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Prefix a raw version string with "v" unless it's already prefixed (case-insensitive).
const formatVersionLabel = (version) => {
  if (!version) return null;
  return /^v/i.test(version) ? version : `v${version}`;
};

function SeqSenderTab({ onBack, showBackToMira, newSubmissionSignal }) {
  const [panelSession, setPanelSession] = useState({ key: 0, submission: null });
  const panelRef = useRef(null);
  const [seqsenderVersion, setSeqsenderVersion] = useState(null); // fetched from /seqsender/version on load
  const [submissionsRefreshKey, setSubmissionsRefreshKey] = useState(0); // bumped to force Past Submissions to refetch
  const [sectionNavCollapsed, setSectionNavCollapsed] = useState(false);
  const sectionNavRef = useRef(null);
  const sectionNavMeasureRef = useRef(null);
  const { open: sectionMenuOpen, setOpen: setSectionMenuOpen, ref: sectionMenuRef } = useDropdown();
  const [headerCollapsed, setHeaderCollapsed] = useState(false);
  const headerRowRef = useRef(null);
  const headerMeasureRef = useRef(null);
  const { open: headerMenuOpen, setOpen: setHeaderMenuOpen, ref: headerMenuRef } = useDropdown();

  // ── Past Submissions slide-in panel (mirrors AssemblyTab's Past Runs panel) ──
  const [pastSubmissionsOpen, setPastSubmissionsOpen] = useState(false);
  const [rightWidth, setRightWidth] = useState(440);
  const dragging = useRef(false);
  const onMouseDown = useCallback(() => {
    dragging.current = true;
    document.body.style.userSelect = "none";
    document.body.style.cursor = "col-resize";
    const onMove = (e) => {
      if (!dragging.current) return;
      const newW = document.body.clientWidth - e.clientX;
      setRightWidth(Math.max(280, Math.min(window.innerWidth * 0.75, newW)));
    };
    const onUp = () => {
      dragging.current = false;
      document.body.style.userSelect = "";
      document.body.style.cursor = "";
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }, []);

  // Open a new submission panel
  const openNewSubmission = () => {
    setPanelSession(({ key }) => ({ key: key + 1, submission: null }));
  };
  
  // Open a past submission panel
  const openPastSubmission = (submission) => {
    setPanelSession(({ key }) => ({ key: key + 1, submission }));
  };

  // Also start a fresh submission (remounting SeqSenderPanel, which re-fetches submitters) when
  // the tab is entered via the Home/Assembly "New Submission" entry points, not just this tab's own pill.
  useEffect(() => {
    if (newSubmissionSignal) openNewSubmission();
  }, [newSubmissionSignal]);

  // Fetch the SeqSender CLI version once on load to display next to the tab title.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(API.retrieveSeqSenderVersion);
        const data = await res.json().catch(() => ({}));
        if (!cancelled && res.ok) setSeqsenderVersion(data.version ?? null);
      } catch {
        /* leave version unset on failure */
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // Collapse the step-link row into a "Submission Steps" dropdown once the pills no longer fit.
  useLayoutEffect(() => {
    const navigation = sectionNavRef.current;
    const naturalNavigation = sectionNavMeasureRef.current;
    if (!navigation || !naturalNavigation) return undefined;
    const updateNavigationMode = () => {
      setSectionNavCollapsed(naturalNavigation.offsetWidth > navigation.clientWidth);
    };
    updateNavigationMode();
    const observer = new ResizeObserver(updateNavigationMode);
    observer.observe(navigation);
    observer.observe(naturalNavigation);
    return () => observer.disconnect();
  }, []);

  // Collapse the whole header (back button, steps, New/Past Submission buttons) into a single
  // "Menu" dropdown once even their minimal (collapsed-pill) footprint no longer fits the bar.
  useLayoutEffect(() => {
    const header = headerRowRef.current;
    const naturalHeader = headerMeasureRef.current;
    if (!header || !naturalHeader) return undefined;
    const updateHeaderMode = () => {
      setHeaderCollapsed(naturalHeader.offsetWidth > header.clientWidth);
    };
    updateHeaderMode();
    const observer = new ResizeObserver(updateHeaderMode);
    observer.observe(header);
    observer.observe(naturalHeader);
    return () => observer.disconnect();
  }, [showBackToMira]);

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div ref={headerRowRef} className="flex shrink-0 items-center gap-3 border-b border-border bg-muted/10 px-4 py-2">
        {headerCollapsed ? (
          <>
            <div className="flex min-w-0 items-baseline gap-2">
              <Send size={15} className="shrink-0 self-center text-primary" />
              <h2 className="truncate text-sm font-bold text-foreground">SeqSender</h2>
              <span className="shrink-0 text-xs font-mono text-muted-foreground">{formatVersionLabel(seqsenderVersion) ?? "…"}</span>
            </div>
            <div ref={headerMenuRef} className="relative ml-auto shrink-0">
              <button
                type="button"
                aria-haspopup="menu"
                aria-expanded={headerMenuOpen}
                onClick={() => setHeaderMenuOpen((open) => !open)}
                className="flex items-center gap-1.5 px-3 py-1 rounded-full border border-border bg-background text-xs font-semibold text-foreground hover:border-primary/30 hover:text-primary transition-colors"
              >
                <Menu size={13} className="shrink-0" />
                <span className="whitespace-nowrap">Menu</span>
              </button>
              {headerMenuOpen && (
                <div role="menu" className="absolute right-0 top-full z-50 mt-2 w-64 rounded-lg border border-border bg-popover p-1 shadow-xl">
                  {showBackToMira && (
                    <button
                      type="button"
                      role="menuitem"
                      onClick={() => { setHeaderMenuOpen(false); onBack(); }}
                      className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-xs text-foreground hover:bg-muted transition-colors"
                    >
                      <ChevronLeft size={14} className="shrink-0 text-primary" />
                      <span>Back to Mira</span>
                    </button>
                  )}
                  <div className="my-1 border-t border-border" />
                  <p className="px-3 pb-1 pt-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Jump to Section</p>
                  {SEQSENDER_SECTIONS.map(({ key, label, icon: Icon }) => (
                    <button
                      key={key}
                      type="button"
                      role="menuitem"
                      onClick={() => { setHeaderMenuOpen(false); panelRef.current?.jumpToSection(key); }}
                      className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-xs text-foreground hover:bg-muted transition-colors"
                    >
                      {Icon && <Icon size={14} className="shrink-0 text-primary" />}
                      <span>{label}</span>
                    </button>
                  ))}
                  <div className="my-1 border-t border-border" />
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => { setHeaderMenuOpen(false); openNewSubmission(); }}
                    className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-xs text-foreground hover:bg-muted transition-colors"
                  >
                    <PlusCircle size={14} className="shrink-0 text-primary" />
                    <span>New Submission</span>
                  </button>
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => { setHeaderMenuOpen(false); setPastSubmissionsOpen((open) => !open); }}
                    className={cn(
                      "flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-xs transition-colors",
                      pastSubmissionsOpen ? "bg-primary/10 text-primary" : "text-foreground hover:bg-muted"
                    )}
                  >
                    <ClipboardList size={14} className="shrink-0 text-primary" />
                    <span>Past Submissions</span>
                  </button>
                </div>
              )}
            </div>
          </>
        ) : (
          <>
            {showBackToMira ? (
              <>
                <button
                  type="button"
                  onClick={onBack}
                  className="flex items-center gap-1.5 rounded-full bg-primary border border-primary px-3 py-1 text-xs font-semibold text-primary-foreground transition-colors hover:bg-primary/90"
                >
                  <ChevronLeft size={13} className="shrink-0" />
                  <span>Back to Mira</span>
                </button>
                <div className="flex min-w-0 items-baseline gap-2">
                  <Send size={15} className="shrink-0 self-center text-primary" />
                  <h2 className="truncate text-sm font-bold text-foreground">SeqSender</h2>
                  <span className="shrink-0 text-xs font-mono text-muted-foreground">{formatVersionLabel(seqsenderVersion) ?? "…"}</span>
                </div>
              </>
            ) : (
              <div className="flex min-w-0 items-baseline gap-2">
                <Send size={15} className="shrink-0 self-center text-primary" />
                <h2 className="truncate text-sm font-bold text-foreground">SeqSender</h2>
                <span className="shrink-0 text-xs font-mono text-muted-foreground">{formatVersionLabel(seqsenderVersion) ?? "…"}</span>
              </div>
            )}

            {/* Navigation Tabs */}
            <div ref={sectionNavRef} className={cn("flex flex-1 min-w-0 items-center justify-center gap-1.5", !sectionNavCollapsed && "overflow-x-auto")}>
              {sectionNavCollapsed ? (
                <div ref={sectionMenuRef} className="relative shrink-0">
                  <button
                    type="button"
                    aria-haspopup="menu"
                    aria-expanded={sectionMenuOpen}
                    onClick={() => setSectionMenuOpen((open) => !open)}
                    className="flex items-center gap-1.5 px-3 py-1 rounded-full border border-border bg-background text-xs font-semibold text-foreground hover:border-primary/30 hover:text-primary transition-colors"
                  >
                    <span className="whitespace-nowrap">Submission Steps</span>
                    <ChevronDown size={13} className={cn("shrink-0 transition-transform", sectionMenuOpen && "rotate-180")} />
                  </button>
                  {sectionMenuOpen && (
                    <div role="menu" className="absolute left-1/2 top-full z-50 mt-2 w-64 -translate-x-1/2 rounded-lg border border-border bg-popover p-1 shadow-xl">
                      {SEQSENDER_SECTIONS.map(({ key, label, icon: Icon }) => (
                        <button
                          key={key}
                          type="button"
                          role="menuitem"
                          onClick={() => { setSectionMenuOpen(false); panelRef.current?.jumpToSection(key); }}
                          className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-xs text-foreground hover:bg-muted transition-colors"
                        >
                          {Icon && <Icon size={14} className="shrink-0 text-primary" />}
                          <span>{label}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              ) : SEQSENDER_SECTIONS.map(({ key, label, icon: Icon }) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => panelRef.current?.jumpToSection(key)}
                  className="shrink-0 flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold border border-transparent text-foreground hover:bg-muted/60 hover:border-border transition-colors whitespace-nowrap"
                >
                  {Icon && <Icon size={13} className="shrink-0 text-primary" />}
                  {label}
                </button>
              ))}
            </div>

            <div className="ml-auto flex shrink-0 items-center gap-2">
              <button
                type="button"
                onClick={openNewSubmission}
                className="flex items-center gap-1.5 rounded-full border border-primary bg-primary/5 px-3 py-1 text-xs font-semibold text-primary transition-colors hover:bg-primary/10"
              >
                <PlusCircle size={13} className="shrink-0" />
                <span>New Submission</span>
              </button>
              <button
                type="button"
                onClick={() => setPastSubmissionsOpen((open) => !open)}
                className={cn(
                  "flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold transition-colors",
                  pastSubmissionsOpen
                    ? "border-primary bg-primary/5 text-primary"
                    : "border-border text-foreground hover:border-primary/30 hover:bg-muted/60 hover:text-primary"
                )}
              >
                <ClipboardList size={13} className="shrink-0" />
                <span>Past Submissions</span>
              </button>
            </div>
          </>
        )}
      </div>

      {/* Hidden, off-screen copy of the step pills used only to measure their natural (unwrapped) width. */}
      <div
        ref={sectionNavMeasureRef}
        aria-hidden="true"
        className="fixed -left-[10000px] top-0 invisible flex w-max items-center gap-1.5 pointer-events-none"
      >
        {SEQSENDER_SECTIONS.map(({ key, label, icon: Icon }) => (
          <span key={key} className="flex items-center gap-1.5 px-3 py-1 text-xs font-semibold">
            {Icon && <Icon size={13} />}
            {label}
          </span>
        ))}
      </div>

      {/* Hidden, off-screen copy of the full header controls (in their most-collapsed form) used
          only to measure whether the header bar can fit them all without wrapping. */}
      <div
        ref={headerMeasureRef}
        aria-hidden="true"
        className="fixed -left-[10000px] top-0 invisible flex w-max items-center gap-3 pointer-events-none"
      >
        {showBackToMira && (
          <span className="flex items-center gap-1.5 px-3 py-1 text-xs font-semibold"><ChevronLeft size={13} />Back to Mira</span>
        )}
        <span className="flex items-baseline gap-2 text-sm font-bold"><Send size={15} />SeqSender<span className="text-xs font-mono">{formatVersionLabel(seqsenderVersion) ?? "…"}</span></span>
        <span className="flex items-center gap-1.5 px-3 py-1 text-xs font-semibold">Submission Steps<ChevronDown size={13} /></span>
        <span className="flex items-center gap-1.5 px-3 py-1 text-xs font-semibold"><PlusCircle size={13} />New Submission</span>
        <span className="flex items-center gap-1.5 px-3 py-1 text-xs font-semibold"><ClipboardList size={13} />Past Submissions</span>
      </div>

      <div className="flex flex-1 overflow-hidden">
        <div className="flex-1 overflow-y-auto p-6">
          <div className="mx-auto flex w-[min(550px,100%)] flex-col items-start gap-4">
            <SeqSenderPanel key={panelSession.key} ref={panelRef} initialSubmission={panelSession.submission} onSubmitted={() => setSubmissionsRefreshKey((k) => k + 1)} />
          </div>
        </div>

        {/* ── Past Submissions slide-in panel (mirrors AssemblyTab's Past Runs panel) ── */}
        {pastSubmissionsOpen && (
          <>
            <div
              onMouseDown={onMouseDown}
              title="Drag to resize"
              className="w-1.5 shrink-0 cursor-col-resize bg-border hover:bg-primary/50 transition-colors"
            />
            <aside style={{ width: rightWidth }} className="shrink-0 flex flex-col overflow-hidden border-l border-border bg-background">
              <div className="shrink-0 flex items-center justify-between px-4 py-3 border-b border-border bg-muted/20">
                <div className="flex items-center gap-2">
                  <ClipboardList size={15} className="text-primary" />
                  <h3 className="text-sm font-bold text-foreground">Past Submissions</h3>
                </div>
                <button onClick={() => setPastSubmissionsOpen(false)} className="text-muted-foreground hover:text-foreground transition-colors">
                  <X size={15} />
                </button>
              </div>
              <div className="flex-1 overflow-auto p-4">
                <PastSubmissionsPanel key={submissionsRefreshKey} onSelectSubmission={openPastSubmission} />
              </div>
            </aside>
          </>
        )}
      </div>
    </div>
  );
}

const NEXTCLADE_BASE = "https://clades.nextstrain.org";

/* ── Resources Tab ──────────────────────────────── */
function ResourceCard({ icon: Icon, title, children }) {
  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden flex flex-col">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-border bg-muted/20 shrink-0">
        <div className="flex items-center justify-center h-7 w-7 rounded-lg bg-primary/10 text-primary">
          <Icon size={15} />
        </div>
        <h3 className="text-sm font-bold tracking-wide text-foreground">{title}</h3>
      </div>
      <div className="p-4 space-y-2 overflow-y-auto flex-1">{children}</div>
    </div>
  );
}

function ResourceLink({ href, icon: Icon = ExternalLink, children, badge }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer"
      className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-foreground hover:bg-muted/60 hover:text-primary transition-colors group">
      <Icon size={13} className="text-muted-foreground group-hover:text-primary shrink-0" />
      <span className="flex-1">{children}</span>
      {badge && <span className="text-xs px-1.5 py-0.5 rounded-full bg-primary/10 text-primary font-medium">{badge}</span>}
    </a>
  );
}

function ContactCard({ name, role, email, github }) {
  return (
    <div className="flex items-start gap-3 p-3 rounded-lg border border-border bg-muted/10">
      <div className="flex items-center justify-center h-8 w-8 rounded-full bg-primary/10 text-primary text-xs font-bold shrink-0">
        {name.split(" ").map(n => n[0]).join("").slice(0, 2).toUpperCase()}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-foreground">{name}</p>
        <p className="text-xs text-muted-foreground">{role}</p>
        <div className="flex flex-wrap gap-2 mt-1.5">
          {email && (
            <a href={`mailto:${email}`} className="flex items-center gap-1 text-xs text-primary hover:underline">
              <Mail size={10} /> {email}
            </a>
          )}
          {github && (
            <a href={`https://github.com/${github}`} target="_blank" rel="noopener noreferrer"
              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-primary hover:underline">
              <GitFork size={10} /> @{github}
            </a>
          )}
        </div>
      </div>
    </div>
  );
}

function ResourcesTab() {
  return (
    <div className="h-full overflow-auto p-4">
      <div className="h-full grid grid-cols-2 grid-rows-1 gap-4" style={{ minHeight: "fit-content" }}>
        {/* ── Installation (disabled) ─────────────────────── */}
        {false && (
        <ResourceCard icon={Package} title="Installation">
          <p className="text-xs text-muted-foreground mb-1">Mira requires Python 3.8+ and conda/mamba. Supports Linux and macOS.</p>
          <ResourceLink href="https://github.com/CDCgov/MIRA" icon={GitFork}>GitHub — CDCgov/MIRA</ResourceLink>
          <ResourceLink href="https://github.com/CDCgov/MIRA/blob/master/MIRA-INSTALL.sh" icon={Download} >MIRA-INSTALL.sh</ResourceLink>
          <ResourceLink href="https://github.com/CDCgov/MIRA/blob/master/requirements.txt" icon={FileStack}>requirements.txt</ResourceLink>
          <div className="mt-2 rounded-lg bg-muted/30 border border-border px-3 py-2">
            <p className="text-xs font-mono text-foreground">bash MIRA-INSTALL.sh</p>
            <p className="text-xs font-mono text-muted-foreground mt-0.5">conda activate mira &amp;&amp; python app.py</p>
          </div>
          <ResourceLink href="https://github.com/CDCgov/MIRA/blob/master/docker-compose.yml" icon={ExternalLink} >Docker Compose</ResourceLink>
        </ResourceCard>
        )}
        {/* ── Documentation (disabled) ────────────────────── */}
        {false && (
        <ResourceCard icon={BookOpen} title="Documentation">
          <ResourceLink href="https://github.com/CDCgov/MIRA/blob/master/README.md">Mira README</ResourceLink>
          <ResourceLink href="https://github.com/CDCgov/MIRA/wiki">Mira Wiki</ResourceLink>
          <div className="mt-1 pt-2 border-t border-border">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">Related Tools</p>
            <ResourceLink href="https://docs.nextstrain.org/projects/nextclade/en/stable/" >Nextclade Documentation</ResourceLink>
            <ResourceLink href="https://docs.nextstrain.org/projects/nextclade/en/stable/user/nextclade-web/url-parameters.html">Nextclade URL Parameters</ResourceLink>
            <ResourceLink href="https://github.com/CDCgov/seqsender" >SeqSender Documentation</ResourceLink>
            <ResourceLink href="https://github.com/CDCgov/irma-core">IRMA-core Documentation</ResourceLink>
          </div>
          <div className="mt-1 pt-2 border-t border-border">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">Databases</p>
            <ResourceLink href="https://www.ncbi.nlm.nih.gov/sra">NCBI SRA</ResourceLink>
            <ResourceLink href="https://www.gisaid.org">GISAID</ResourceLink>
            <ResourceLink href="https://clades.nextstrain.org">Nextclade Web</ResourceLink>
          </div>
        </ResourceCard>
        )}

        {/* ── GitHub Repositories ──────────────── */}
        <ResourceCard icon={GitFork} title="GitHub Repositories">
          {[
            { repo: "CDCgov/MIRA",          desc: "Mira + Graphical User Interface (GUI)"             },
            { repo: "CDCgov/Mira-nf",          desc: "Mira nextflow pipeline used by GUI or CLI "             },
            { repo: "CDCgov/mira-oxide",          desc: "Rust tools used by Mira"             },
            { repo: "CDCgov/IRMA",          desc: "The Assembler used by Mira"             },
            { repo: "CDCgov/irma-core",      desc: "Rust tools used by IRMA"               },
            { repo: "CDCgov/dais-ribosome",      desc: "ORF annotator used by Mira"               },
            { repo: "CDCgov/seqsender",      desc: "Sequence submission tool used by Mira"      },
            { repo: "nextstrain/nextclade",  desc: "Clade assignment tool used by Mira"       },
          ].map(({ repo, desc, badge }) => (
            <a key={repo} href={`https://github.com/${repo}`} target="_blank" rel="noopener noreferrer"
              className="flex items-start gap-2.5 px-3 py-2 rounded-lg hover:bg-muted/60 transition-colors group">
              <GitFork size={14} className="text-muted-foreground group-hover:text-primary mt-0.5 shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-mono text-foreground group-hover:text-primary">{repo}</span>
                  <span className={cn(
                    "text-xs px-1.5 py-0.5 rounded-full font-medium",
                    badge === "main" ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"
                  )}>{badge}</span>
                </div>
                <p className="text-xs text-muted-foreground">{desc}</p>
              </div>
            </a>
          ))}
        </ResourceCard>

        {/* ── Contact ──────────────────────────── */}
        <ResourceCard icon={Mail} title="Who to Contact">
          <ContactCard
            name="Mira And Laboratory Support"
            role="CDC VSDB — Virus Surveillance and Diagnostic Branch"
            email="idseqsupport@cdc.gov"
          />
          <ContactCard
            name="Ben Rambo-Martin"
            role="Mira project lead"
            email="brambomartin@cdc.gov"
          />
          <div className="mt-2 pt-2 border-t border-border space-y-1.5">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Report Issues</p>
            <ResourceLink href="https://github.com/CDCgov/MIRA/issues" icon={MessageSquare} >Mira GitHub Issues</ResourceLink>
          </div>
        </ResourceCard>

      </div>
    </div>
  );
}

/* ── Placeholder tab content ─────────────────────── */
function TabContent({ tab, navigateTo, loadRunSignal, newRunSignal, onLoadRun, onNewRun, onOpenSeqSender, seqSenderOrigin, newSubmissionSignal, setHeaderHidden }) {
  if (tab.id === "home")       return <HomeTab onNewRun={onNewRun} onLoadRun={onLoadRun} onOpenSeqSender={() => onOpenSeqSender("home")} />;
  if (tab.id === "assembly")   return <AssemblyTab loadRunSignal={loadRunSignal} newRunSignal={newRunSignal} setHeaderHidden={setHeaderHidden} onOpenSeqSender={() => onOpenSeqSender("assembly")} />;
  if (tab.id === "seqsender")  return <SeqSenderTab onBack={() => navigateTo("assembly")} showBackToMira={seqSenderOrigin === "assembly"} newSubmissionSignal={newSubmissionSignal} />;
  return (
    <div className="p-6">
      <div className="rounded-xl border border-border bg-card p-8 text-left text-muted-foreground">
        <p className="text-lg font-medium">{tab.label}</p>
        <p className="text-sm mt-1">Content for the {tab.label} tab goes here.</p>
      </div>
    </div>
  );
}

/* ── Main App ────────────────────────────────────── */
export default function App() {

  // Determine the initial tab based on the URL hash
  const getInitialTab = () => {
    const hash = window.location.hash.slice(1);
    return TABS.find((t) => t.id === hash) ? hash : "home";
  };

  // State for the active tab and version info
  const [activeTab, setActiveTab] = useState(getInitialTab);
  const [versionInfo, setVersionInfo] = useState(null);
  const [backendUp, setBackendUp] = useState(true); // assume healthy until the first check completes
  const [resourcesOpen, setResourcesOpen] = useState(false); // Resources overlay visibility
  const [loadRunSignal, setLoadRunSignal] = useState(0); // bumped to signal AssemblyTab to open its Load Run modal
  const [newRunSignal, setNewRunSignal] = useState(0);   // bumped to signal AssemblyTab to reset its inputs for a new run
  const [headerHidden, setHeaderHidden] = useState(false); // whether the top header is collapsed (auto-hide on scroll)
  const [seqSenderOrigin, setSeqSenderOrigin] = useState(null); // show Back to Mira only when SeqSender was launched from Assembly
  const [newSubmissionSignal, setNewSubmissionSignal] = useState(0); // bumped to signal SeqSenderTab to start a fresh submission (and re-fetch submitters)

  // Check MIRA-NF version on app startup so we can alert users if it's out-of-date,
  // and detect whether the backend API is reachable at all. Re-checked on demand
  // (e.g. when the notifications button is clicked) rather than on a timer.
  const checkBackend = useCallback(() => {
    fetch(API.checkVersion)
      .then((res) => {
        setBackendUp(res.ok);
        if (res.ok) res.json().then((data) => setVersionInfo(data)).catch(() => {});
      })
      .catch(() => setBackendUp(false));
  }, []);

  useEffect(() => {
    checkBackend();
  }, [checkBackend]);

  // Update the URL hash when the active tab changes
  const updateUrl = (tabId) => {
    window.history.pushState({ tab: tabId }, "", tabId === "home" ? location.pathname : `#${tabId}`);
  };

  const navigateTo = (tabId) => {
    if (tabId === activeTab) return;
    setActiveTab(tabId);
    updateUrl(tabId);
    setHeaderHidden(false);
  };

  // Navigate to the Mira tab and open its Load Run modal (triggered from the Home dashboard).
  const openLoadRunFromHome = () => {
    navigateTo("assembly");
    setLoadRunSignal((n) => n + 1);
  };

  const openNewRunFromHome = () => {
    navigateTo("assembly");
    setNewRunSignal((n) => n + 1);
  };

  const openSeqSender = (origin) => {
    setSeqSenderOrigin(origin);
    navigateTo("seqsender");
    setNewSubmissionSignal((n) => n + 1);
  };

  // Sync active tab when browser back/forward is used
  useEffect(() => {
    const onPopState = () => {
      const hash = window.location.hash.slice(1);
      setActiveTab(TABS.find((t) => t.id === hash) ? hash : "home");
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const currentTab = TABS.find((t) => t.id === activeTab);

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-background text-foreground">

      {/* ── Header ───────────────────────────────── */}
      <header className={cn("shrink-0 w-full bg-primary border-b border-border flex items-center px-4 gap-3 overflow-hidden transition-[height] duration-300", headerHidden ? "h-0 border-b-0" : "h-24")}>
        {/* Brand */}
        <button
          onClick={() => navigateTo("home")}
          className="flex items-center gap-3 text-white hover:opacity-90 transition-opacity"
        >
          <div className="relative shrink-0">
            <img
              src="/mira-logo.png"
              alt="MIRA logo"
              className="relative h-24 w-24 object-contain drop-shadow-[0_2px_6px_rgba(0,0,0,0.35)]"
            />
          </div>
          <div className="flex flex-col leading-tight">
            <div className="flex items-baseline gap-2">
              <span className="text-3xl tracking-widest text-white font-bold">Mira</span>
              <span className="text-xs text-white/50 font-mono">{versionInfo?.current_mira_version ?? "v3.0.0"}</span>
            </div>

          </div>
        </button>

        {/* Right controls */}
        <div className="ml-auto flex items-center gap-1">

          {/* Home */}
          <button
            onClick={() => navigateTo("home")}
            title="Home"
            className="p-2 rounded-md text-white/80 hover:text-white hover:bg-white/10 transition-colors"
          >
            <Home size={22} />
          </button>

          {/* Resources */}
          <button
            onClick={() => setResourcesOpen(true)}
            title="Resources"
            className="p-2 rounded-md text-white/80 hover:text-white hover:bg-white/10 transition-colors"
          >
            <BookOpen size={22} />
          </button>



          {/* Notifications */}
          <Dropdown
            panelClassName="w-80"
            trigger={
              <button onClick={checkBackend} className="relative p-2 rounded-md text-white/80 hover:text-white hover:bg-white/10 transition-colors">
                <Bell size={22} />
                {versionInfo?.status === "out-of-date" && (
                  <span className="absolute top-1 right-1 h-2 w-2 rounded-full bg-red-500" />
                )}
              </button>
            }
          >
            <div className="px-4 py-2 text-xs text-muted-foreground font-medium border-b border-border">
              Notifications
            </div>
            {versionInfo?.status === "out-of-date" ? (
              <div className="divide-y divide-border">
                {versionInfo?.mira_status === "out-of-date" && (
                  <div className="px-4 py-3 text-sm text-foreground">
                    <p className="mb-1 flex items-center gap-1.5">
                      <AlertCircle size={13} className="text-warning shrink-0" />
                      A new version of Mira is available
                    </p>
                    <div className="flex items-center gap-1.5 mb-1.5 text-xs">
                      <span className="text-muted-foreground">Current:</span>
                      <span className="font-mono font-semibold text-foreground">{versionInfo.current_mira_version}</span>
                      <ArrowRight size={11} className="text-muted-foreground shrink-0" />
                      <span className="text-muted-foreground">Available:</span>
                      <span className="font-mono font-semibold text-primary">{versionInfo.available_mira_version}</span>
                    </div>
                    <a
                      href="https://github.com/CDCgov/MIRA/releases"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary hover:underline"
                    >
                      Click here to see how to upgrade Mira to the latest version
                    </a>
                  </div>
                )}
                {versionInfo?.mira_nf_status === "out-of-date" && (
                  <div className="px-4 py-3 text-sm text-foreground">
                    <p className="mb-1 flex items-center gap-1.5">
                      <AlertCircle size={13} className="text-warning shrink-0" />
                      A new version of MIRA-NF is available
                    </p>
                    <div className="flex items-center gap-1.5 mb-1.5 text-xs">
                      <span className="text-muted-foreground">Current:</span>
                      <span className="font-mono font-semibold text-foreground">{versionInfo.current_mira_nf_version}</span>
                      <ArrowRight size={11} className="text-muted-foreground shrink-0" />
                      <span className="text-muted-foreground">Available:</span>
                      <span className="font-mono font-semibold text-primary">{versionInfo.available_mira_nf_version}</span>
                    </div>
                    <a
                      href="https://cdcgov.github.io/MIRA/articles/upgrading-mira.html"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary hover:underline"
                    >
                      Click here to see how to upgrade MIRA-NF to the latest version
                    </a>
                  </div>
                )}
              </div>
            ) : (
              <DropdownItem>There are no new notifications</DropdownItem>
            )}
          </Dropdown>
        </div>
      </header>

      {/* ── Resources modal ──────────────────────── */}
      {resourcesOpen && (
        <div onClick={() => setResourcesOpen(false)} className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          <div onClick={(e) => e.stopPropagation()} className="bg-background border border-border rounded-xl shadow-xl w-full max-w-6xl h-[85vh] flex flex-col overflow-hidden">
            <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
              <div className="flex items-center gap-2">
                <BookOpen size={16} className="text-primary" />
                <h3 className="text-sm font-bold text-foreground">Resources</h3>
              </div>
              <button onClick={() => setResourcesOpen(false)} className="text-muted-foreground hover:text-foreground transition-colors">
                <X size={16} />
              </button>
            </div>
            <div className="flex-1 overflow-hidden">
              <ResourcesTab />
            </div>
          </div>
        </div>
      )}

      {/* ── Main area ────────────────────────────── */}
      <div className="flex-1 flex flex-col overflow-hidden">

        {/* ── Backend API alarm banner ─────────── */}
        {!backendUp && (
          <div className="shrink-0 flex items-center gap-2 px-4 py-2 bg-destructive text-destructive-foreground text-sm font-semibold">
            <AlertCircle size={16} className="shrink-0" />
            BACKEND API IS NOT RUNNING — please make sure the backend service is up and reachable at <span className="font-mono">{API_BASE}</span>
          </div>
        )}

        {/* ── Tab content ──────────────────────── */}
        <main className="flex-1 overflow-hidden px-6">
          {TABS.map((tab) => (
            <div key={tab.id} className={cn("h-full", activeTab !== tab.id && "hidden")}>
              <TabContent tab={tab} navigateTo={navigateTo} loadRunSignal={loadRunSignal} newRunSignal={newRunSignal} onLoadRun={openLoadRunFromHome} onNewRun={openNewRunFromHome} onOpenSeqSender={openSeqSender} seqSenderOrigin={seqSenderOrigin} newSubmissionSignal={newSubmissionSignal} setHeaderHidden={setHeaderHidden} />
            </div>
          ))}
        </main>
      </div>
    </div>
  );
}
