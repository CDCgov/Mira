import { useState, useRef, useEffect, useCallback, useMemo, lazy, Suspense, Fragment } from "react";
const Plot = lazy(() => import("react-plotly.js"));
import ShaderAura from "./ShaderAura";
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
  Pencil,
} from "lucide-react";

/* ── utility ─────────────────────────────────────── */
function cn(...classes) {
  return classes.filter(Boolean).join(" ");
}

/* ── recursively read a dropped folder's contents via the FileSystem entry API ── */
function readAllDirectoryEntries(reader) {
  return new Promise((resolve, reject) => {
    const allEntries = [];
    const readBatch = () => {
      // readEntries() only returns a batch at a time — keep calling until it returns empty
      reader.readEntries((entries) => {
        if (!entries.length) { resolve(allEntries); return; }
        allEntries.push(...entries);
        readBatch();
      }, reject);
    };
    readBatch();
  });
}

async function collectFilesFromEntry(entry, out) {
  if (!entry) return;
  if (entry.isFile) {
    const file = await new Promise((resolve, reject) => entry.file(resolve, reject));
    out.push(file);
  } else if (entry.isDirectory) {
    const entries = await readAllDirectoryEntries(entry.createReader());
    for (const child of entries) await collectFilesFromEntry(child, out);
  }
}

// Supports a drop containing a mix of loose files and whole folders in one gesture
async function collectFilesFromDataTransfer(dataTransfer) {
  const items = dataTransfer.items;
  const out = [];
  if (items && items.length && typeof items[0].webkitGetAsEntry === "function") {
    const entries = Array.from(items).map((item) => item.webkitGetAsEntry()).filter(Boolean);
    for (const entry of entries) await collectFilesFromEntry(entry, out);
  } else {
    out.push(...Array.from(dataTransfer.files || []));
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
  retrieveRun:      `${API_BASE}/retrieve/run`,
  createRun:        `${API_BASE}/create/run`,
  deleteSample:     `${API_BASE}/delete/sample`,
  renameRun:        `${API_BASE}/rename/run`,
  deleteRun:        `${API_BASE}/delete/run`,
  copyRun:          `${API_BASE}/copy/run`,
  uploadFastqs:     `${API_BASE}/upload/fastqs`,
  uploadCustomPrimerConfig:     `${API_BASE}/upload/custom_primer_config`,
  uploadCustomIrmaConfig:       `${API_BASE}/upload/custom_irma_config`,
  uploadCustomQcSettings:       `${API_BASE}/upload/custom_qc_settings`,
  downloadCustomIrmaConfig:     `${API_BASE}/download/custom_irma_config`,
  downloadCustomPrimerConfig:   `${API_BASE}/download/custom_primer_config`,
  downloadCustomQcSettings:     `${API_BASE}/download/custom_qc_settings`,
  validateRun:                  `${API_BASE}/validate/run`,
  validateCustomConfigs:        `${API_BASE}/validate/custom_configs`,
  runMIRA:                      `${API_BASE}/run/MIRA`,
  miraDAG:                      `${API_BASE}/MIRA/DAG`,
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
  downloadSeqsenderConfig:           `${API_BASE}/download/seqsender_config_template`,
  downloadSeqsenderMetadataTemplate: `${API_BASE}/download/seqsender_metadata_template`,
};

// Standardized on-disk filenames the backend always saves custom config uploads
// under, regardless of the originally-picked filename (must match schema_validator.py).
const CUSTOM_PRIMER_CONFIG_FILENAME = "custom_primers.fasta";
const CUSTOM_IRMA_CONFIG_FILENAME = "custom_irma_config.sh";
const CUSTOM_QC_SETTINGS_FILENAME = "custom_qc_settings.yaml";

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
  return (
    <div ref={ref} className="relative">
      <div onClick={() => setOpen((v) => !v)}>{trigger}</div>
      {open && (
        <div className={cn("absolute right-0 mt-2 rounded-md border border-border bg-popover shadow-lg z-50 py-1", panelClassName)}>
          {children}
        </div>
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
  { id: "resources",  label: "Resources",  icon: BookOpen },
];

/* ── Home Tab ────────────────────────────────────── */
const STATS = [
  { label: "Sequencing Runs",          value: "1,284",  sub: "successfully completed",  icon: Cpu,        color: "text-primary"     },
  { label: "Sequences to NCBI",        value: "48,312", sub: "GenBank + SRA combined",  icon: Database,   color: "text-sky-600"     },
  { label: "Sequences to GISAID",      value: "31,047", sub: "EpiFlu + EpiCoV",         icon: Database,   color: "text-emerald-600" },
];

const FEATURES = [
  { icon: Cpu,          title: "IRMA Assembly",     desc: "Iterative refinement meta-assembler for influenza, SARS-CoV-2 and RSV consensus genome assembly from FASTQ reads." },
  { icon: ShieldCheck,  title: "QC & Clade Assignment", desc: "Automated quality control metrics per segment and Nextclade-powered clade/lineage assignment for all supported pathogens." },
  { icon: Send,         title: "SeqSender",          desc: "One-click submission pipeline to NCBI BioSample, SRA, GenBank, and GISAID with configurable metadata and validation." },
  { icon: Network,      title: "Nextclade Integration", desc: "Build pre-configured Nextclade Web URLs to visualize clade assignments, mutations, and phylogenetic placement." },
];

// Illustrative placeholder trends for the Home dashboard charts.
// Each run holds one value per sample; charts show every sample as a dot
// with a trend line drawn through the per-run medians.
const SEGMENTS_PER_SAMPLE_TREND = [
  { run: "Jan '25", runId: "R2025-01", samples: [8, 7, 8, 6, 8, 7, 5, 8, 7, 8] },
  { run: "Feb '25", runId: "R2025-02", samples: [8, 8, 7, 8, 6, 8, 8, 7, 8, 8, 7, 8] },
  { run: "Mar '25", runId: "R2025-03", samples: [7, 8, 6, 8, 7, 8, 8, 5, 7, 8] },
  { run: "Apr '25", runId: "R2025-04", samples: [8, 8, 8, 7, 8, 8, 6, 8, 7, 8, 8] },
  { run: "May '25", runId: "R2025-05", samples: [8, 7, 8, 8, 6, 8, 7, 8, 8, 4, 8] },
  { run: "Jun '25", runId: "R2025-06", samples: [8, 8, 8, 8, 7, 8, 8, 6, 8, 8, 7, 8, 8] },
  { run: "Jul '25", runId: "R2025-07", samples: [8, 8, 7, 8, 8, 8, 8, 7, 8, 8] },
  { run: "Aug '25", runId: "R2025-08", samples: [8, 8, 8, 8, 8, 7, 8, 8, 8, 6, 8, 8] },
];

const TURNAROUND_TREND = [
  { run: "Jan '25", runId: "R2025-01", samples: [12, 18, 14, 20, 11, 16, 22, 13, 15] },
  { run: "Feb '25", runId: "R2025-02", samples: [10, 14, 12, 16, 13, 11, 18, 12] },
  { run: "Mar '25", runId: "R2025-03", samples: [13, 15, 14, 17, 12, 16, 11, 19, 14] },
  { run: "Apr '25", runId: "R2025-04", samples: [9, 12, 11, 14, 10, 13, 8, 12, 11] },
  { run: "May '25", runId: "R2025-05", samples: [10, 13, 12, 11, 14, 9, 12, 15, 10] },
  { run: "Jun '25", runId: "R2025-06", samples: [8, 11, 10, 12, 9, 13, 7, 10] },
  { run: "Jul '25", runId: "R2025-07", samples: [7, 9, 10, 8, 11, 6, 9, 8, 10] },
  { run: "Aug '25", runId: "R2025-08", samples: [6, 9, 8, 7, 10, 8, 5, 9, 7, 8] },
];

// Median of a numeric array.
function median(values) {
  if (!values.length) return 0;
  const s = [...values].sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
}

// Dashboard card: a dot per sample plus a trend line through the per-run medians.
function HomeChartCard({ icon: Icon, title, statValue, statLabel, data, color, unit, yTitle }) {
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
        <div className="text-right shrink-0">
          <p className="text-lg font-bold text-primary leading-none">{statValue}</p>
          <p className="text-[10px] text-muted-foreground">{statLabel}</p>
        </div>
      </div>
      <div className="flex-1 min-h-0 p-2">
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
      </div>
    </div>
  );
}

function HomeTab() {
  const [runCount, setRunCount] = useState(null);

  useEffect(() => {
    let cancelled = false;
    fetch(API.listRuns)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (cancelled) return;
        const runs = Array.isArray(data?.run_info) ? data.run_info : [];
        setRunCount(runs.filter((r) => r.assembly_status === "COMPLETED").length);
      })
      .catch(() => { if (!cancelled) setRunCount(0); });
    return () => { cancelled = true; };
  }, []);

  const medSegments = median(SEGMENTS_PER_SAMPLE_TREND.flatMap((d) => d.samples)).toFixed(1);
  const medTurnaround = median(TURNAROUND_TREND.flatMap((d) => d.samples)).toFixed(1);

  return (
    <div className="h-full flex flex-col overflow-hidden">

      

      {/* ── Body grid ────────────────────────────── */}
      <div className="flex-1 overflow-hidden p-4 grid grid-cols-2 grid-rows-[auto_minmax(0,1fr)] gap-4">

        {/* ── Stats row — spans both columns ─────── */}
        <div className="col-span-2 grid grid-cols-3 gap-3">
          {STATS.map(({ label, value, sub, icon: Icon, color }) => {
            const displayValue = label === "Sequencing Runs"
              ? (runCount === null ? "…" : runCount.toLocaleString())
              : value;
            return (
              <div key={label} className="rounded-xl border border-border bg-card px-4 py-3 flex items-center gap-3">
                <Icon size={22} className={`${color} shrink-0`} />
                <div>
                  <p className={`text-xl font-bold leading-none ${color}`}>{displayValue}</p>
                  <p className="text-xs font-semibold text-foreground mt-0.5">{label}</p>
                  <p className="text-xs text-muted-foreground">{sub}</p>
                </div>
              </div>
            );
          })}
        </div>

        {/* ── Segments per sample over time ─── */}
        <HomeChartCard
          icon={BarChart3}
          title="Segments per Sample"
          statValue={medSegments}
          statLabel="median segments / sample"
          data={SEGMENTS_PER_SAMPLE_TREND}
          color="#722161"
          unit="segments"
          yTitle="Segments per sample"
        />

        {/* ── Turnaround time over time ─────── */}
        <HomeChartCard
          icon={Clock}
          title="Turnaround Time"
          statValue={`${medTurnaround}d`}
          statLabel="median days: submission − collection"
          data={TURNAROUND_TREND}
          color="#0081A1"
          unit="days"
          yTitle="Turnaround (days)"
        />

      </div>
    </div>
  );
}

/* ── Assembly Tab ────────────────────────────────── */
const ASSEMBLY_STEPS = [
  { id: "setup",    title: "STEP 1: Mira SETUP",  subtitle: "Define run, configure sample sheet, and set assembly parameters", icon: Upload },
  { id: "progress", title: "STEP 2: PROCESSING",  subtitle: "Monitor assembly progress and stage status",                      icon: RefreshCw },
  { id: "results",  title: "STEP 3: RESULTS",     subtitle: "Assembly statistics, QC decisions, and coverage plots",           icon: BarChart3 },
  { id: "export",   title: "STEP 4: EXPORT",      subtitle: "Download FASTA outputs from the assembly run",                    icon: Download },
];

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
  return <div className="px-4 pb-4 pt-2 space-y-4">{children}</div>;
}

function FieldLabel({ children }) {
  return <p className="text-xs font-semibold text-foreground mb-1">{children}</p>;
}

/* ── Shared Plotly modebar config ───────────────── */
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

/* ── Reusable paginated + sortable result table ──── */
const N_BINS = 8;
const PUBUGN_8 = ['#fff7fb','#ece2f0','#d0d1e6','#a6bddb','#67a9cf','#3690c0','#02818a','#016450'];

function ResultTable({ title, data: rawData, page, setPage, pageSize = 100, colorize = false }) {
  const [sortCol, setSortCol] = useState(null);
  const [sortDir, setSortDir] = useState("asc");
  const [searchQuery, setSearchQuery] = useState("");

  // Normalise: accept a list of row-dicts OR a pandas split-format {columns, data}
  const data = Array.isArray(rawData)
    ? rawData
    : (rawData?.columns && rawData?.data)
      ? rawData.data.map(row => Object.fromEntries(rawData.columns.map((c, i) => [c, row[i]])))
      : [];

  const cols = data.length > 0 && data[0] ? Object.keys(data[0]) : [];

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

  // 1. filter
  const q = searchQuery.trim().toLowerCase();
  const filtered = q
    ? data.filter(row => cols.some(c => (row[c] == null ? "" : String(row[c])).toLowerCase().includes(q)))
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
    <div className="rounded-xl border border-border overflow-hidden">
      {/* header bar */}
      <div className="flex items-center justify-between px-3 py-2 bg-muted/20 border-b border-border">
        <div className="flex items-center gap-2">
          <button onClick={downloadCSV} className="flex items-center gap-1 px-2 py-0.5 rounded text-xs border border-border text-muted-foreground hover:border-primary hover:text-primary transition-colors">
            <Download size={11} /> CSV
          </button>
          <button onClick={downloadExcel} className="flex items-center gap-1 px-2 py-0.5 rounded text-xs border border-border text-muted-foreground hover:border-primary hover:text-primary transition-colors">
            <Download size={11} /> Excel
          </button>
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

      {/* colorize bin legend */}
      {colorize && (
        <div className="flex items-center justify-center gap-2 px-3 py-2 border-b border-border bg-muted/10">
          <span className="text-xs text-muted-foreground shrink-0">Percentile:</span>
          <div className="flex overflow-hidden rounded border border-border shrink-0">
            {PUBUGN_8.map((color, i) => {
              const lo = Math.round((i / N_BINS) * 100);
              const hi = Math.round(((i + 1) / N_BINS) * 100);
              return (
                <div key={i} className="flex flex-col items-center">
                  <span
                    title={`${lo}–${hi} percentile`}
                    className="h-4 w-14 block"
                    style={{ backgroundColor: color }}
                  />
                  <span className="text-[10px] leading-none text-muted-foreground mt-0.5">{lo}–{hi}%</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* table */}
      <div className="overflow-auto max-h-[360px]">
        <table className="w-full text-xs">
          <thead className="bg-muted sticky top-0 z-10">
            <tr>
              {cols.map(c => (
                <th key={c} onClick={() => handleSort(c)} className="px-3 py-2 text-left font-semibold text-muted-foreground font-mono whitespace-nowrap cursor-pointer select-none hover:text-foreground transition-colors">
                  <span className="flex items-center gap-1">
                    {c}
                    {sortCol === c
                      ? sortDir === "asc" ? <ArrowUp size={9} className="text-primary shrink-0" /> : <ArrowDown size={9} className="text-primary shrink-0" />
                      : <ArrowUpDown size={9} className="opacity-30 shrink-0" />}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pageRows.length === 0 ? (
              <tr className="border-t border-border">
                <td colSpan={cols.length} className="px-3 py-4 text-center text-muted-foreground">
                  No rows match your search.
                </td>
              </tr>
            ) : pageRows.map((row, i) => (
              <tr key={pageStart + i} className="border-t border-border hover:bg-muted/10">
                {cols.map(c => {
                  const cellStyle = getCellStyle(c, row[c]);
                  return (
                    <td key={c} className={cn("px-3 py-1.5 font-mono whitespace-nowrap", !cellStyle.backgroundColor && "text-foreground")} style={cellStyle}>
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
    <div className="rounded-xl border border-border overflow-hidden">
      <div className="flex items-center justify-between px-3 py-2 bg-muted/20 border-b border-border">
        <p className="text-xs font-bold text-foreground uppercase tracking-wider">{title}</p>
      </div>
      <div className="px-3 py-6 text-center">
        <p className="text-xs text-muted-foreground">{message}</p>
      </div>
    </div>
  );
}

function AssemblyTab() {
  const [openStep, setOpenStep]                           = useState(() => new Set(ASSEMBLY_STEPS.map((s) => s.id)));
  const [runName, setRunName]                             = useState("");
  const [experimentType, setExperimentType]               = useState("");
  const [primer, setPrimer]                               = useState("");
  const [customPrimers, setCustomPrimers]                 = useState("");   // file path to a custom primer FASTA file
  const [useCustomPrimers, setUseCustomPrimers]           = useState(false); // whether the Custom Primers option is enabled
  const [primerKmerLen, setPrimerKmerLen]                 = useState("");   // required alongside customPrimers
  const [primerRestrictWindow, setPrimerRestrictWindow]   = useState(""); // required alongside customPrimers
  const [subSample, setSubSample]                         = useState("0");
  const [useIrmaModule, setUseIrmaModule]                 = useState(false); // whether the IRMA Module option is enabled (Flu-Illumina only)
  const [irmaModule, setIrmaModule]                       = useState("");   // sensitive | secondary | utr
  const [useCustomIrmaConfig, setUseCustomIrmaConfig]     = useState(false); // whether a custom IRMA config file is used
  const [customIrmaConfig, setCustomIrmaConfig]           = useState("");    // file path to a custom IRMA config file
  const [useCustomQcSettings, setUseCustomQcSettings]     = useState(false); // whether custom QC pass/fail settings are used
  const [customQcSettings, setCustomQcSettings]           = useState("");    // file path to a custom QC settings file
  const [customPrimersFile, setCustomPrimersFile]         = useState(null); // File object selected via Browse, for actual upload
  const [customIrmaConfigFile, setCustomIrmaConfigFile]   = useState(null); // File object selected via Browse, for actual upload
  const [customQcSettingsFile, setCustomQcSettingsFile]   = useState(null); // File object selected via Browse, for actual upload
  const [loadedCustomPrimersName, setLoadedCustomPrimersName] = useState(""); // filename already stored server-side for a loaded run
  const [loadedCustomIrmaConfigName, setLoadedCustomIrmaConfigName] = useState(""); // filename already stored server-side for a loaded run
  const [loadedCustomQcSettingsName, setLoadedCustomQcSettingsName] = useState(""); // filename already stored server-side for a loaded run
  const [customConfigDownloadError, setCustomConfigDownloadError] = useState(null); // { field, message } for a failed custom config download
  const [primersFileError, setPrimersFileError] = useState(null); // validation error when a non-.fasta file is picked for Custom Primers
  const [irmaConfigFileError, setIrmaConfigFileError] = useState(null); // validation error when a non-.sh file is picked for Custom IRMA Config
  const [qcSettingsFileError, setQcSettingsFileError] = useState(null); // validation error when a non-YAML file is picked for Custom QC Settings
  const [createParquet, setCreateParquet]           = useState(false);
  const [nextclade, setNextclade]                   = useState(true);
  const [exportFmt, setExportFmt]                   = useState("fasta");
  const [assembled, setAssembled]                   = useState(false);
  const [rightWidth, setRightWidth]                 = useState(260);
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
  const [runSortDir, setRunSortDir]                 = useState("asc"); // "asc" | "desc" — run_name sort order
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

              // Also fetch linear coverage plot for the first sample
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

            }
          }
        }
      } catch (_) { /* network error — keep polling */ }
    };
    poll(); // immediate first fetch
    const timer = setInterval(poll, 5000);
    return () => { cancelled = true; clearInterval(timer); };
  }, [pipelinePolling, submitProcessId, selectedRun, cancelRun]);

  // ── Cancel the in-flight MIRA run if the tab is closed/refreshed while it's still running ──
  useEffect(() => {
    if (!pipelinePolling || !submitProcessId || cancelRun) return;
    const cancelOnExit = () => {
      const url = `${API.miraCancel}?run_name=${encodeURIComponent(selectedRun?.run_name)}&experiment_type=${encodeURIComponent(selectedRun?.experiment_type)}&pid=${submitProcessId}`;
      // keepalive lets the request survive page unload; response is never read
      fetch(url, { keepalive: true }).catch(() => {});
    };
    window.addEventListener("beforeunload", cancelOnExit);
    window.addEventListener("pagehide", cancelOnExit);
    return () => {
      window.removeEventListener("beforeunload", cancelOnExit);
      window.removeEventListener("pagehide", cancelOnExit);
    };
  }, [pipelinePolling, submitProcessId, selectedRun, cancelRun]);

  // ── Sample sheet state ───────────────────────
  const SAMPLE_TYPES = ["- Control", "+ Control", "Test"];
  const [ontSampleRows, setOntSampleRows]           = useState([]);
  const [illuminaSampleRows, setIlluminaSampleRows] = useState([]);
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
      const res = await fetch(API.deleteSample, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          run_name: runName,
          experiment_type: experimentType,
          sample_id: sample.sample_id,
          fastq: isOnt ? sample.fastq : null,
          fastq_1: isOnt ? null : sample.fastq_1,
          fastq_2: isOnt ? null : sample.fastq_2,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail));
      if (isOnt) setOntSampleRows((prev) => prev.filter((_, i) => i !== idx));
      else setIlluminaSampleRows((prev) => prev.filter((_, i) => i !== idx));
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

  // Export the sample sheet in CSV or Excel format
  const exportSampleSheet = (format) => {
    const isOnt = experimentType.toLowerCase().endsWith("ont");
    const activeRows = isOnt ? ontSampleRows : illuminaSampleRows;
    const headers = isOnt
      ? ["barcode", "sample_id", "sample_type", "single_end", "fastq", "status"]
      : ["sample_id", "sample_type", "single_end", "fastq_1", "fastq_2", "status"];
    const data = activeRows.map(row => isOnt
      ? [row.barcode, row.sample_id, row.sample_type, row.single_end, row.fastq, row.status]
      : [row.sample_id, row.sample_type, row.single_end, row.fastq_1, row.fastq_2, row.status]
    );
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

      // Validate: ONT filenames must contain _barcode##_
      const invalidFiles = sanitized.filter(fname => !/_barcode\d+_/i.test(fname));
      if (invalidFiles.length > 0) {
        setUploadOntError({ items: [`For ONT run, the FASTQ files must contain a barcode pattern (_barcode##_) in their filenames.`], missing: [...invalidFiles] });
        return;
      } else {
        setUploadOntError(null);
      }

      // Store File objects keyed by sanitized filename
      const fileMap = {};
      files.forEach((f, i) => { fileMap[sanitized[i]] = f; });
      setUploadedOntFileObjects(prev => ({ ...prev, ...fileMap }));

      // Group ONT files by barcode extracted from filename
      const grouped = {};
      sanitized.forEach(fname => {
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

      const allPotentialRows = [];
      sortedBarcodes.forEach(barcode => {
        const existingByBarcode = ontSampleRows.find(r => r.barcode === barcode);
        const sample_id = existingByBarcode ? existingByBarcode.sample_id : `sample_${sampleCounter++}`;
        const sample_type = existingByBarcode ? existingByBarcode.sample_type : "Test";
        grouped[barcode].forEach(fname => {
          // Look up status by the specific fastq file first; fall back to barcode-level row
          const existingByFastq = ontSampleRows.find(r => r.fastq === fname);
          const status = existingByFastq ? existingByFastq.status : (existingByBarcode ? existingByBarcode.status : "Keep");
          allPotentialRows.push({
            barcode: barcode,
            sample_id: sample_id,
            sample_type: sample_type,
            single_end: "true",
            fastq: fname,
            status: status
          });
        });
      });

      // Overwrite existing rows with matching fastq and add new ones
      const ontNewRows = allPotentialRows.filter(r => !ontSampleRows.some(e => e.fastq === r.fastq));
      const ontUpdates = allPotentialRows.filter(r => ontSampleRows.some(e => e.fastq === r.fastq));

      setOntSampleRows(prev => {
        const updated = prev.map(r => {
          const u = ontUpdates.find(m => m.fastq === r.fastq);
          return u ? { ...r, ...u } : r;
        });
        return ontNewRows.length > 0 ? [...updated, ...ontNewRows] : updated;
      });

      // Accumulate uploaded ONT fastq filenames
      setUploadOntFastq(prev => [...new Set([...prev, ...sanitized])]);

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
  }, [experimentType, ontSampleRows, illuminaSampleRows]);

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
    const onMove = (e) => {
      if (!dragging.current) return;
      const newW = document.body.clientWidth - e.clientX;
      setRightWidth(Math.max(200, Math.min(420, newW)));
    };
    const onUp = () => { dragging.current = false; window.removeEventListener("mousemove", onMove); window.removeEventListener("mouseup", onUp); };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }, []);

  // 
  const toggle = (id) => setOpenStep((prev) => {
    const next = new Set(prev);
    next.has(id) ? next.delete(id) : next.add(id);
    return next;
  });

  // Fetch the sankey figure for a specific sample (lazy-loads, caches in resultSampleCoverageSankey)
  const fetchSankeyForSample = useCallback(async (sampleId) => {
    setSelectedSampleForCoverage(sampleId);
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

  // Reset all state variables to their initial values, effectively clearing the form and any loaded run data
  const resetRun = useCallback(() => {

    // Cancel any ongoing run if submitProcessId exists
    if (submitProcessId && selectedRun) {
      fetch(`${API.miraCancel}?run_name=${encodeURIComponent(selectedRun.run_name)}&experiment_type=${encodeURIComponent(selectedRun.experiment_type)}&pid=${submitProcessId}`)
        .catch(() => {});
    }

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
    setUseIrmaModule(false);
    setIrmaModule("");
    setUseCustomIrmaConfig(false);
    setCustomIrmaConfig("");
    setIrmaConfigFileError(null);
    setUseCustomQcSettings(false);
    setCustomQcSettings("");
    setQcSettingsFileError(null);
    setCustomPrimersFile(null);
    setCustomIrmaConfigFile(null);
    setCustomQcSettingsFile(null);
    setLoadedCustomPrimersName("");
    setLoadedCustomIrmaConfigName("");
    setLoadedCustomQcSettingsName("");
    setCustomConfigDownloadError(null);
    setCreateParquet(false);
    setNextclade(true);
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
    setRunSortDir("asc");
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
    setOpenStep(new Set(ASSEMBLY_STEPS.map((s) => s.id)));
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
      setUseCustomPrimers(Boolean(info.custom_primers));
      setLoadedCustomPrimersName(info.custom_primers ? CUSTOM_PRIMER_CONFIG_FILENAME : "");
      setPrimerKmerLen(info.primer_kmer_len ? String(info.primer_kmer_len) : "");
      setPrimerRestrictWindow(info.primer_restrict_window ? String(info.primer_restrict_window) : "");
      setSubSample(String(info.subsample_reads ?? 0));
      setIrmaModule(info.irma_module || "");
      setUseIrmaModule(Boolean(info.irma_module));
      setCustomIrmaConfig(info.custom_irma_config ? CUSTOM_IRMA_CONFIG_FILENAME : "");
      setUseCustomIrmaConfig(Boolean(info.custom_irma_config));
      setLoadedCustomIrmaConfigName(info.custom_irma_config ? CUSTOM_IRMA_CONFIG_FILENAME : "");
      setCustomQcSettings(info.custom_qc_settings ? CUSTOM_QC_SETTINGS_FILENAME : "");
      setUseCustomQcSettings(Boolean(info.custom_qc_settings));
      setLoadedCustomQcSettingsName(info.custom_qc_settings ? CUSTOM_QC_SETTINGS_FILENAME : "");
      setCreateParquet(info.parquet_files ?? false);
      setNextclade(info.nextclade ?? true);
      const isOnt = (info.experiment_type ?? "").toLowerCase().endsWith("ont");
      const rows = Array.isArray(data.samplesheet) ? data.samplesheet : [];
      if (isOnt) {
        setOntSampleRows(rows.map(r => ({
          barcode:     r.barcode    ?? "",
          sample_id:   r.sample_id  ?? "",
          sample_type: r.sample_type ?? "Test",
          single_end:  r.single_end ? "true" : "false",
          fastq:       r.fastq      ?? "",
          status:      (r.status ?? "Keep").toLowerCase() === "keep" ? "Keep" : "Exclude",
        })));
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
      setCustomIrmaConfigFile(null);
      setCustomQcSettingsFile(null);
      setCustomConfigDownloadError(null);
      setIrmaConfigFileError(null);
      setQcSettingsFileError(null);
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

      // Close the modal
      setLoadRunModal(false);

    } catch (err) {
      setLoadRunError(err.message);
    } finally {
      setLoadRunLoading(false);
    }
  }, [loadRunSelectedRow]);

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

    // IRMA Module can only be invoked for Flu-Illumina experiments, and requires a module selection
    if (useIrmaModule) {
      if (experimentType !== "Flu-Illumina") {
        setSubmitError({ title: "Assembly Error", items: ["IRMA Module can only be used with the Flu-Illumina experiment type."], missing: null });
        return;
      }
      if (!irmaModule) {
        setSubmitError({ title: "Assembly Error", items: ["Please select an IRMA Module (sensitive, secondary, or utr) or turn off IRMA Module."], missing: null });
        return;
      }
    }

    // Custom IRMA Config requires a file path when enabled
    if (isNewRun === true && assembled === false && useCustomIrmaConfig && !customIrmaConfig) {
      setSubmitError({ title: "Assembly Error", items: ["Please provide a custom IRMA config file or turn off Custom IRMA Config."], missing: null });
      return;
    }
    if (isNewRun === true && assembled === false && useCustomIrmaConfig && customIrmaConfig && !/\.sh$/i.test(customIrmaConfig)) {
      setSubmitError({ title: "Assembly Error", items: ["Custom IRMA Config file must be a shell script (.sh)."], missing: null });
      return;
    }

    // Custom QC Settings requires a file path when enabled, and it must be a YAML file
    if (isNewRun === true && assembled === false && useCustomQcSettings && !customQcSettings) {
      setSubmitError({ title: "Assembly Error", items: ["Please provide a custom QC settings file or turn off Custom QC Settings."], missing: null });
      return;
    }
    if (isNewRun === true && assembled === false && useCustomQcSettings && customQcSettings && !/\.(yaml|yml)$/i.test(customQcSettings)) {
      setSubmitError({ title: "Assembly Error", items: ["Custom QC Settings file must be a YAML file (.yaml or .yml)."], missing: null });
      return;
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
      const badRows = samplesheet.filter(r => !r.fastq || r.single_end !== "true");
      if (badRows.length > 0) {
        const missingFastq = badRows.map(r => `${r.sample_id}: missing fastq`);
        setSubmitError({ title: "Validation Error", items: [`ONT samples require a single-end fastq file.`], missing: { title: "Missing Samples", samples: missingFastq } });
        return;
      }
    }

    // Construct the samplesheet for submission
    const formattedSamplesheet = samplesheet.map(r => isOnt ? {
      barcode:       r.barcode,
      sample_id:     r.sample_id,
      sample_type:   r.sample_type,
      single_end:    r.single_end,
      fastq:         r.fastq,
      status:        r.status,
    } : {
      sample_id:     r.sample_id,
      sample_type:   r.sample_type,
      single_end:    r.single_end,
      fastq_1:       r.fastq_1,
      fastq_2:       r.fastq_2,
      status:        r.status,
    });

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
      irma_module:            useIrmaModule && irmaModule ? irmaModule : "",
      custom_irma_config:     useCustomIrmaConfig,
      custom_qc_settings:     useCustomQcSettings,
      parquet_files:          createParquet,
      nextclade:              nextclade,
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
          const f = r.fastq && uploadedOntFileObjects[r.fastq];
          return f ? [f] : [];
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

      // ── Step 2.2: Upload custom primer, custom IRMA config, and custom QC settings files if a new file was selected ──
      if (useCustomPrimers && customPrimersFile) {
        const primerForm = new FormData();
        primerForm.append("run_name", runName);
        primerForm.append("experiment_type", experimentType);
        primerForm.append("custom_primer_config_file", customPrimersFile);
        const primerRes = await fetch(API.uploadCustomPrimerConfig, { method: "POST", body: primerForm });
        const primerData = await primerRes.json().catch(() => ({}));
        if (!primerRes.ok) throw new Error(primerData.detail || "Failed to upload custom primer config file");
      }
      if (useCustomIrmaConfig && customIrmaConfigFile) {
        const irmaForm = new FormData();
        irmaForm.append("run_name", runName);
        irmaForm.append("experiment_type", experimentType);
        irmaForm.append("custom_irma_config_file", customIrmaConfigFile);
        const irmaRes = await fetch(API.uploadCustomIrmaConfig, { method: "POST", body: irmaForm });
        const irmaData = await irmaRes.json().catch(() => ({}));
        if (!irmaRes.ok) throw new Error(irmaData.detail || "Failed to upload custom IRMA config file");
      }
      if (useCustomQcSettings && customQcSettingsFile) {
        const qcForm = new FormData();
        qcForm.append("run_name", runName);
        qcForm.append("experiment_type", experimentType);
        qcForm.append("custom_qc_settings_file", customQcSettingsFile);
        const qcRes = await fetch(API.uploadCustomQcSettings, { method: "POST", body: qcForm });
        const qcData = await qcRes.json().catch(() => ({}));
        if (!qcRes.ok) throw new Error(qcData.detail || "Failed to upload custom QC settings file");
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

      // ── Step 3.2: Validate custom primers, custom irma config, and custom qc settings files if provided ──
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

      } else {
        // No pid to poll — nothing further will clear the "Processing..." state, so reset it now.
        setSubmitting(false);
      }

    } catch (err) {
      setSubmitError({ title: "Assembly Error", items: [err.message], missing: null });
      setSubmitSuccess(null);
      setSubmitting(false);
    }

  }, [runName, experimentType, ontSampleRows, illuminaSampleRows, subSample, primer, customPrimers, useCustomPrimers, primerKmerLen, primerRestrictWindow, useIrmaModule, irmaModule, useCustomIrmaConfig, customIrmaConfig, useCustomQcSettings, customQcSettings, customPrimersFile, customIrmaConfigFile, customQcSettingsFile, createParquet, nextclade, isNewRun, assembled]);

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
    { id: "result-section-heatmap",  label: "Median Coverage Heatmap",   show: resultCoverageHeatmap !== null },
    { id: "result-section-summary",  label: "Mira Summary",       show: resultMiraSummary !== null },
    { id: "result-section-coverage", label: "Sample Sankey & Coverage Plots",    show: resultSampleCoverageList !== null },
    { id: "result-section-variants", label: "AA Variants",        show: resultVariants !== null },
    { id: "result-section-snvs",     label: "Minor Variants",         show: resultMinorSnvs !== null },
    { id: "result-section-indels",   label: "Minor Indels & Deletions",             show: resultIndels !== null },
  ].filter(({ show }) => show);

  return (
    <div className="flex h-full overflow-hidden">

      {/* ── Left: accordion steps ─────────────────── */}
      <div className="flex-1 overflow-auto p-4 space-y-2">
        {ASSEMBLY_STEPS.map(({ id, title, subtitle, icon }) => (
          <div key={id} id={`step-${id}`} className="rounded-xl border border-border overflow-hidden">
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
                      <div>
                        <FieldLabel>Experiment Type <span className="text-destructive">*</span></FieldLabel>
                        <select
                          value={experimentType}
                          onChange={(e) => {
                            const value = e.target.value;
                            setExperimentType(value);
                            setPrimer(value?.startsWith("SC2") && value?.endsWith("Illumina") ? SC2_PRIMERS[0].value : value?.startsWith("RSV") && value?.endsWith("Illumina") ? RSV_PRIMERS[0].value : "");
                            if (value !== "Flu-Illumina") { setUseIrmaModule(false); setIrmaModule(""); }
                            if (value) {
                              const today = new Date();
                              const yyyymmdd = `${today.getFullYear()}${String(today.getMonth() + 1).padStart(2, "0")}${String(today.getDate()).padStart(2, "0")}`;
                              setRunName(`${yyyymmdd}_${value}`.replace(/\s+/g, "_"));
                            }
                          }}
                          disabled={!isNewRun}
                          className="w-full max-w-xs h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-60 disabled:cursor-not-allowed disabled:bg-muted"
                        >
                          <option value="">— Select experiment type —</option>
                          {EXPERIMENT_TYPES.map((p) => <option key={p}>{p}</option>)}
                        </select>
                      </div>
                      <div>
                        <FieldLabel>Run Name<span className="text-destructive">*</span></FieldLabel>
                        <input
                          value={runName}
                          onChange={(e) => setRunName(e.target.value.replace(/\s+/g, "_"))}
                          placeholder="e.g. Flu_Illumina_2024-01-01"
                          disabled={!isNewRun}
                          className="w-full max-w-xs h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-60 disabled:cursor-not-allowed disabled:bg-muted"
                        />
                      </div>
                    </div>
                    {(experimentType?.startsWith("SC2") || experimentType?.startsWith("RSV")) && experimentType?.endsWith("Illumina") && (
                      <div>
                        <FieldLabel>Primers <span className="text-destructive">*</span></FieldLabel>
                        <p className="mb-2 text-xs text-muted-foreground">Select the appropriate primer for the chosen experiment type.</p>
                        <select
                          value={primer}
                          onChange={(e) => setPrimer(e.target.value)}
                          className="w-full max-w-md h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
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

                    <div className="flex items-center gap-2 pt-1">
                      <span className="text-xs font-bold tracking-wider text-muted-foreground uppercase">Sample Sheet</span>
                      <div className="flex-1 h-px bg-border" />
                    </div>

                    {(!runName || !experimentType) && (
                      <div className="flex items-center gap-2 w-fit max-w-full text-xs text-warning bg-warning/10 rounded-lg px-3 py-2">
                        <AlertCircle size={13} className="shrink-0" /> Please provide a <strong className="mx-0.5">Run Name</strong> and select an <strong className="mx-0.5">Experiment Type</strong> above to continue.
                      </div>
                    )}

                    {runName && experimentType && (<>

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

                    <div>
                      <FieldLabel>Upload FASTQ Files</FieldLabel>
                      <div
                        onClick={() => fastqFileInputRef.current?.click()}
                        onDragOver={(e) => { e.preventDefault(); setFastqDragOver(true); }}
                        onDragLeave={() => setFastqDragOver(false)}
                        onDrop={async (e) => {
                          e.preventDefault();
                          setFastqDragOver(false);
                          const files = await collectFilesFromDataTransfer(e.dataTransfer);
                          handleIncomingFastqFiles(files);
                        }}
                        className={cn(
                          "flex flex-col items-center justify-center gap-2 h-28 rounded-xl border-2 border-dashed bg-muted/10 hover:bg-muted/20 cursor-pointer transition-colors text-muted-foreground text-sm",
                          fastqDragOver ? "border-primary bg-primary/5" : "border-border"
                        )}
                      >
                        <Upload size={22} />
                        <span>
                          Drag &amp; drop files or folders, or <span className="text-primary underline">browse files</span>
                        </span>
                        <span className="text-xs opacity-60">.fastq, .fastq.gz, .fq, .fq.gz accepted — dropped folders are scanned recursively. Sample names must not contain any spaces — spaces will be replaced with underscores.</span>
                        <input
                          ref={fastqFileInputRef}
                          type="file"
                          className="hidden"
                          multiple
                          onChange={(e) => { handleIncomingFastqFiles(Array.from(e.target.files || [])); e.target.value = ""; }}
                        />
                      </div>
                    </div>

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
                      <div className="overflow-y-auto max-h-[300px]">
                      <table className="w-full text-xs">
                        <thead className="bg-muted sticky top-0 z-10">
                          <tr>
                            {(experimentType.toLowerCase().endsWith("ont")
                              ? ["barcode", "sample_id", "sample_type", "single_end", "fastq", "status"]
                              : ["sample_id", "sample_type", "single_end", "fastq_1", "fastq_2", "status"]
                            ).map((h) => (
                              <th
                                key={h}
                                className="px-3 py-2 text-left font-semibold text-muted-foreground font-mono cursor-pointer select-none hover:text-foreground transition-colors"
                                onClick={() => setSortConfig(prev => ({
                                  key: h,
                                  dir: prev.key === h && prev.dir === "asc" ? "desc" : "asc",
                                }))}
                              >
                                <span className="flex items-center gap-1">
                                  {h}
                                  {sortConfig.key === h ? (
                                    sortConfig.dir === "asc"
                                      ? <ArrowUp size={10} className="text-primary shrink-0" />
                                      : <ArrowDown size={10} className="text-primary shrink-0" />
                                  ) : (
                                    <ArrowUpDown size={10} className="opacity-30 shrink-0" />
                                  )}
                                </span>
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
                                    ? [row.barcode, row.sample_id, row.sample_type, row.single_end, row.fastq, row.status]
                                    : [row.sample_id, row.sample_type, row.single_end, row.fastq_1, row.fastq_2, row.status];
                                  return vals.some(v => (v ?? "").toString().toLowerCase().includes(q));
                                })
                              : activeRows;
                            const getVal = (row, k) => {
                              if (isOnt && k === "fastq") return (row.fastq ?? "").toString().toLowerCase();
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
                                <td colSpan={6} className="px-3 py-4 text-center text-muted-foreground">
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
                                          <span className="flex items-center gap-1">
                                            {colVals[ci] && (isOnt ? uploadedOntFileObjects[colVals[ci]] : uploadedIlluminaFileObjects[colVals[ci]]) && (
                                              <Upload size={10} className="text-emerald-500 shrink-0" title="Uploaded this session" />
                                            )}
                                            <span className="block overflow-x-auto whitespace-nowrap max-w-[300px] scrollbar-thin">{colVals[ci]}</span>
                                          </span>
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
                                            ? "bg-emerald-100 text-emerald-700 border-emerald-200 hover:bg-red-50 hover:text-red-600 hover:border-red-200 dark:bg-emerald-900/30 dark:text-emerald-400 dark:border-emerald-800"
                                            : "bg-red-100 text-red-700 border-red-200 hover:bg-emerald-50 hover:text-emerald-600 hover:border-emerald-200 dark:bg-red-900/30 dark:text-red-400 dark:border-red-800"
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
                    </>)}

                    <div className="flex items-center gap-2 pt-1">
                      <span className="text-xs font-bold tracking-wider text-muted-foreground uppercase">Assembly Parameters</span>
                      <div className="flex-1 h-px bg-border" />
                    </div>
                    <div>
                      <FieldLabel>Number of Subsamples <span className="text-destructive">*</span></FieldLabel>
                      <p className="text-xs text-muted-foreground mb-2 leading-relaxed">
                        The number of reads used for subsampling. Set to <code className="font-mono bg-muted px-1 rounded">0</code> to skip subsampling.
                      </p>
                      <input
                        type="number"
                        value={subSample}
                        onChange={(e) => setSubSample(e.target.value)}
                        placeholder="e.g. 100"
                        min={0}
                        className="w-full max-w-md h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                      />
                    </div>

                    <button
                      onClick={() => setUseCustomPrimers((v) => !v)}
                      className="w-fit flex items-center justify-start gap-4 p-3 rounded-lg border border-border bg-muted/10 hover:bg-muted/20 transition-colors text-left"
                    >
                      <div>
                        <p className="text-sm font-medium">Custom Primers</p>
                        <p className="text-xs text-muted-foreground">When set to true, this flag will allow you to provide a custom primer FASTA file and its associated parameters.</p>
                      </div>
                      <span className={cn(
                        "relative w-10 h-5 rounded-full transition-colors shrink-0 pointer-events-none",
                        useCustomPrimers ? "bg-primary" : "bg-muted"
                      )}>
                        <span className={cn("absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform", useCustomPrimers ? "translate-x-5" : "translate-x-0.5")} />
                      </span>
                    </button>

                    {useCustomPrimers && (
                      <>
                        <div>
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
                          <FieldLabel>Custom Primer FASTA File <span className="text-destructive">*</span></FieldLabel>
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

                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <FieldLabel>primer_kmer_len <span className="text-destructive">*</span></FieldLabel>
                            <input
                              type="number"
                              value={primerKmerLen}
                              onChange={(e) => setPrimerKmerLen(e.target.value)}
                              placeholder="e.g. 25"
                              min={0}
                              className="w-full h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                            />
                          </div>
                          <div>
                            <FieldLabel>primer_restrict_window <span className="text-destructive">*</span></FieldLabel>
                            <input
                              type="number"
                              value={primerRestrictWindow}
                              onChange={(e) => setPrimerRestrictWindow(e.target.value)}
                              placeholder="e.g. 30"
                              min={0}
                              className="w-full h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                            />
                          </div>
                        </div>
                      </>
                    )}

                    {experimentType === "Flu-Illumina" && (
                      <>
                        <button
                          onClick={() => setUseIrmaModule((v) => !v)}
                          className="w-fit flex items-center justify-start gap-4 p-3 rounded-lg border border-border bg-muted/10 hover:bg-muted/20 transition-colors text-left"
                        >
                          <div>
                            <p className="text-sm font-medium">IRMA Module</p>
                            <p className="text-xs text-muted-foreground">When set to true, this flag will allow you to call flu-sensitive, flu-secondary or flu-utr IRMA module instead of the built-in flu configs.</p>
                          </div>
                          <span className={cn(
                            "relative w-10 h-5 rounded-full transition-colors shrink-0 pointer-events-none",
                            useIrmaModule ? "bg-primary" : "bg-muted"
                          )}>
                            <span className={cn("absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform", useIrmaModule ? "translate-x-5" : "translate-x-0.5")} />
                          </span>
                        </button>

                        {useIrmaModule && (
                          <div>
                            <select
                              value={irmaModule}
                              onChange={(e) => setIrmaModule(e.target.value)}
                              className="w-full max-w-md h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                            >
                              <option value="">— Select IRMA module —</option>
                              <option value="secondary">secondary</option>
                              <option value="sensitive">sensitive</option>
                              <option value="utr">utr</option>
                            </select>
                          </div>
                        )}
                      </>
                    )}

                    <button
                      onClick={() => setUseCustomIrmaConfig((v) => !v)}
                      className="w-fit flex items-center justify-start gap-4 p-3 rounded-lg border border-border bg-muted/10 hover:bg-muted/20 transition-colors text-left"
                    >
                      <div>
                        <p className="text-sm font-medium">Custom IRMA Config</p>
                        <p className="text-xs text-muted-foreground">When set to true, this flag will allow you to provide a custom IRMA config file to be used with IRMA assembly.</p>
                      </div>
                      <span className={cn(
                        "relative w-10 h-5 rounded-full transition-colors shrink-0 pointer-events-none",
                        useCustomIrmaConfig ? "bg-primary" : "bg-muted"
                      )}>
                        <span className={cn("absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform", useCustomIrmaConfig ? "translate-x-5" : "translate-x-0.5")} />
                      </span>
                    </button>

                    {useCustomIrmaConfig && (
                      <div>
                        {!isNewRun && loadedCustomIrmaConfigName && (
                          <div className="mb-2 text-md text-muted-foreground">
                            <p>
                              Currently stored file:{" "}
                              <button
                                type="button"
                                onClick={() => downloadCustomConfigFile(
                                  `${API.downloadCustomIrmaConfig}?run_name=${encodeURIComponent(selectedRun?.run_name ?? runName)}&experiment_type=${encodeURIComponent(selectedRun?.experiment_type ?? experimentType)}`,
                                  loadedCustomIrmaConfigName,
                                  "irma"
                                )}
                                className="inline-flex items-center gap-1 font-mono text-primary hover:underline"
                              >
                                <Download size={11} className="shrink-0" />
                                {loadedCustomIrmaConfigName}
                              </button>
                            </p>
                            {customConfigDownloadError?.field === "irma" && (
                              <p className="mt-1 flex items-center gap-1 text-xs text-destructive">
                                <AlertCircle size={11} className="shrink-0" /> {customConfigDownloadError.message}
                              </p>
                            )}
                          </div>
                        )}
                        <div className="flex gap-2 max-w-md">
                          <input
                            type="text"
                            value={customIrmaConfig}
                            onChange={(e) => setCustomIrmaConfig(e.target.value)}
                            placeholder="e.g. custom_irma_config.sh"
                            className="flex-1 h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                          />
                          <label className="flex items-center gap-1.5 px-3 h-9 rounded-md border border-border bg-muted/20 hover:bg-muted/40 cursor-pointer text-xs text-muted-foreground transition-colors shrink-0">
                            <FolderOpen size={13} /> Browse
                            <input
                              type="file"
                              className="hidden"
                              accept=".sh"
                              onChange={(e) => {
                                const f = e.target.files?.[0];
                                if (f) {
                                  if (!/\.sh$/i.test(f.name)) {
                                    setIrmaConfigFileError("Custom IRMA Config file must be a shell script (.sh).");
                                  } else {
                                    setIrmaConfigFileError(null);
                                    setCustomIrmaConfig(f.name);
                                    setCustomIrmaConfigFile(f);
                                    setCustomConfigDownloadError(null);
                                  }
                                }
                                e.target.value = "";
                              }}
                            />
                          </label>
                        </div>
                        {irmaConfigFileError && (
                          <p className="mt-1 flex items-center gap-1 text-xs text-destructive">
                            <AlertCircle size={11} className="shrink-0" /> {irmaConfigFileError}
                          </p>
                        )}
                      </div>
                    )}

                    <button
                      onClick={() => setUseCustomQcSettings((v) => !v)}
                      className="w-fit flex items-center justify-start gap-4 p-3 rounded-lg border border-border bg-muted/10 hover:bg-muted/20 transition-colors text-left"
                    >
                      <div>
                        <p className="text-sm font-medium">Custom QC Settings</p>
                        <p className="text-xs text-muted-foreground">When set to true, this flag will allow you to provide a custom QC file with pass/fail settings for constructing the summary files.</p>
                      </div>
                      <span className={cn(
                        "relative w-10 h-5 rounded-full transition-colors shrink-0 pointer-events-none",
                        useCustomQcSettings ? "bg-primary" : "bg-muted"
                      )}>
                        <span className={cn("absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform", useCustomQcSettings ? "translate-x-5" : "translate-x-0.5")} />
                      </span>
                    </button>

                    {useCustomQcSettings && (
                      <div>
                        {!isNewRun && loadedCustomQcSettingsName && (
                          <div className="mb-2 text-md text-muted-foreground">
                            <p>
                              Currently stored file:{" "}
                              <button
                                type="button"
                                onClick={() => downloadCustomConfigFile(
                                  `${API.downloadCustomQcSettings}?run_name=${encodeURIComponent(selectedRun?.run_name ?? runName)}&experiment_type=${encodeURIComponent(selectedRun?.experiment_type ?? experimentType)}`,
                                  loadedCustomQcSettingsName,
                                  "qc"
                                )}
                                className="inline-flex items-center gap-1 font-mono text-primary hover:underline"
                              >
                                <Download size={11} className="shrink-0" />
                                {loadedCustomQcSettingsName}
                              </button>
                            </p>
                            {customConfigDownloadError?.field === "qc" && (
                              <p className="mt-1 flex items-center gap-1 text-xs text-destructive">
                                <AlertCircle size={11} className="shrink-0" /> {customConfigDownloadError.message}
                              </p>
                            )}
                          </div>
                        )}
                        <div className="flex gap-2 max-w-md">
                          <input
                            type="text"
                            value={customQcSettings}
                            onChange={(e) => setCustomQcSettings(e.target.value)}
                            placeholder="e.g. custom_qc_settings.yaml"
                            className="flex-1 h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                          />
                          <label className="flex items-center gap-1.5 px-3 h-9 rounded-md border border-border bg-muted/20 hover:bg-muted/40 cursor-pointer text-xs text-muted-foreground transition-colors shrink-0">
                            <FolderOpen size={13} /> Browse
                            <input
                              type="file"
                              className="hidden"
                              accept=".yaml,.yml"
                              onChange={(e) => {
                                const f = e.target.files?.[0];
                                if (f) {
                                  if (!/\.(yaml|yml)$/i.test(f.name)) {
                                    setQcSettingsFileError("Custom QC Settings file must be a YAML file (.yaml or .yml).");
                                  } else {
                                    setQcSettingsFileError(null);
                                    setCustomQcSettings(f.name);
                                    setCustomQcSettingsFile(f);
                                    setCustomConfigDownloadError(null);
                                  }
                                }
                                e.target.value = "";
                              }}
                            />
                          </label>
                        </div>
                        {qcSettingsFileError && (
                          <p className="mt-1 flex items-center gap-1 text-xs text-destructive">
                            <AlertCircle size={11} className="shrink-0" /> {qcSettingsFileError}
                          </p>
                        )}
                      </div>
                    )}

                    <button
                      onClick={() => setCreateParquet((v) => !v)}
                      className="w-fit flex items-center justify-start gap-4 p-3 rounded-lg border border-border bg-muted/10 hover:bg-muted/20 transition-colors text-left"
                    >
                      <div>
                        <p className="text-sm font-medium">Create Parquet Files</p>
                        <p className="text-xs text-muted-foreground">When set to true, this flag will save the assembly outputs from CSV files to Parquet format for downstream analysis.</p>
                      </div>
                      <span className={cn(
                        "relative w-10 h-5 rounded-full transition-colors shrink-0 pointer-events-none",
                        createParquet ? "bg-primary" : "bg-muted"
                      )}>
                        <span className={cn("absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform", createParquet ? "translate-x-5" : "translate-x-0.5")} />
                      </span>
                    </button>
                    <button
                      onClick={() => setNextclade((v) => !v)}
                      className="w-fit flex items-center justify-start gap-4 p-3 rounded-lg border border-border bg-muted/10 hover:bg-muted/20 transition-colors text-left"
                    >
                      <div>
                        <p className="text-sm font-medium">Run Nextclade</p>
                        <p className="text-xs text-muted-foreground">When set to true, this flag will run Nextclade with your passing samples.</p>
                      </div>
                      <span className={cn(
                        "relative w-10 h-5 rounded-full transition-colors shrink-0 pointer-events-none",
                        nextclade ? "bg-primary" : "bg-muted"
                      )}>
                        <span className={cn("absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform", nextclade ? "translate-x-5" : "translate-x-0.5")} />
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
                            <div className="w-px h-4 bg-border shrink-0" />
                            <div className="flex items-center gap-1.5 shrink-0">
                              <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">PID</span>
                              <span className="text-xs font-mono text-foreground">{submitProcessId || "—"}</span>
                            </div>
                          </div>
                          {pipelineDAG?.workflows?.status && (() => {
                            const s = pipelineDAG?.workflows?.status;
                            const { cls, Icon } = {
                              COMPLETED:  { cls: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400", Icon: Check },
                              FAILED:     { cls: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400", Icon: AlertCircle },
                              PROCESSING: { cls: "bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-400", Icon: RefreshCw },
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

                        {/* pipeline tasks — flat list */}
                        {pipelineDAG?.tasks?.length > 0 && (
                          <div className="rounded-xl border border-border overflow-hidden">
                            <div className="flex items-center justify-between px-3 py-2 bg-muted/20 border-b border-border">
                              <p className="text-xs font-bold text-foreground uppercase tracking-wider">Running Tasks</p>                           
                            </div>
                            <div className="divide-y divide-border/50 max-h-[360px] overflow-y-auto">
                              {pipelineDAG?.tasks?.map(task => {
                                const done   = task.status === "COMPLETED";
                                // PASSFAILED means the sample failed the QC pass/fail check, regardless of the task's own run status
                                const failed = task.status === "FAILED" || task.process_name === "PASSFAILED";
                                return (
                                  <div key={task.task_id} className={cn("flex items-center justify-between gap-3 px-3 py-1.5", failed && "bg-red-50 dark:bg-red-950/20")}>
                                    <div className="flex items-center gap-2 min-w-0">
                                      {done && !failed && <Check size={10} className="text-emerald-500 shrink-0" />}
                                      {failed && <AlertCircle size={10} className="text-destructive shrink-0" />}
                                      {!done && !failed && <AlertCircle size={10} className="text-destructive shrink-0" />}
                                      <span className={cn("text-xs font-mono truncate", failed ? "text-destructive font-semibold" : "text-foreground")}>{task.process_name}</span>
                                      {task.sample && <span className="text-xs text-muted-foreground shrink-0">({task.sample})</span>}
                                    </div>
                                    <span className={cn(
                                      "px-1.5 py-0.5 rounded font-mono text-xs shrink-0",
                                      failed ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
                                      : done ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400"
                                      : "bg-muted text-muted-foreground"
                                    )}>{task.status}</span>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        )}

                        {/* timing footer */}
                        {pipelineDAG?.workflows && (
                          <div className="text-xs text-muted-foreground border-t border-border pt-2 flex items-center justify-between flex-wrap gap-y-1">
                            <div className="flex gap-x-4 flex-wrap gap-y-0.5">
                              <span>Started: <span className="text-foreground">{pipelineDAG?.workflows?.started_at || "—"}</span></span>
                              <span>Completed: <span className="text-foreground">{pipelineDAG?.workflows?.completed_at || "—"}</span></span>
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
                            <div className="flex items-center gap-2 shrink-0">
                              <span className="px-1.5 py-0.5 rounded bg-muted text-muted-foreground font-mono">
                                {pipelineDAG?.workflows?.number_of_samples ?? 0} total samples
                              </span>
                              <span className="px-1.5 py-0.5 rounded bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400 font-mono">
                                {pipelineDAG?.workflows?.number_of_samples_with_failed_tasks ?? 0} samples failed
                              </span>
                              <span className="px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400 font-mono">
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
                          <div id="result-section-barcode">
                            <EmptyResultTable title="Barcode Assignment" />
                          </div>
                        );
                      }
                      return (
                        <div id="result-section-barcode" className="rounded-xl border border-border overflow-hidden">
                          <div className="flex items-center justify-between px-3 py-2 bg-muted/20 border-b border-border">
                            <p className="text-xs font-bold text-foreground uppercase tracking-wider">Barcode Assignment</p>
                          </div>
                          <div className="p-2 overflow-x-auto">
                            <div style={{ minWidth: resultBarcodeAssignments.layout?.width ? `${resultBarcodeAssignments.layout.width}px` : "100%" }}>
                              <Suspense fallback={<div className="flex items-center justify-center h-40 text-xs text-muted-foreground">Loading chart…</div>}>
                                <Plot
                                  data={resultBarcodeAssignments.data ?? []}
                                  layout={{
                                    ...(resultBarcodeAssignments.layout ?? {}),
                                    autosize: true,
                                    margin: { l: 20, r: 20, t: 40, b: 20 },
                                    paper_bgcolor: "transparent",
                                    plot_bgcolor: "transparent",
                                    font: { size: 11 },
                                    showlegend: true,
                                    legend: { orientation: "h", x: 0.5, xanchor: "center", y: -0.1 },
                                  }}
                                  config={PLOT_CONFIG}
                                  style={{ width: "100%", minHeight: 300 }}
                                  useResizeHandler
                                />
                              </Suspense>
                            </div>
                          </div>
                        </div>
                      );
                    })()}

                    {/* ── 2. Automatic QC Decisions heatmap ── */}
                    {assembled && resultQcDecisions !== null && (() => {
                      if ((resultQcDecisions.data ?? []).length === 0) {
                        return (
                          <div id="result-section-qc">
                            <EmptyResultTable title="Automatic Quality Control Decisions" />
                          </div>
                        );
                      }
                      return (
                        <div id="result-section-qc" className="rounded-xl border border-border overflow-hidden">
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
                          <div className="p-2 overflow-x-auto">
                            <div style={{ minWidth: resultQcDecisions.layout?.width ? `${resultQcDecisions.layout.width}px` : "100%" }}>
                              <Suspense fallback={<div className="flex items-center justify-center h-40 text-xs text-muted-foreground">Loading chart…</div>}>
                                <Plot
                                  data={resultQcDecisions.data ?? []}
                                  layout={{
                                    ...(resultQcDecisions.layout ?? {}),
                                    autosize: true,
                                    margin: { l: 60, r: 20, t: 40, b: 20 },
                                    paper_bgcolor: "transparent",
                                    plot_bgcolor: "transparent",
                                    font: { size: 11 },
                                    xaxis: { ...(resultQcDecisions.layout?.xaxis ?? {}), side: "top" },
                                  }}
                                  config={PLOT_CONFIG}
                                  style={{ width: "100%", minHeight: 260 }}
                                  useResizeHandler
                                />
                              </Suspense>
                            </div>
                          </div>
                        </div>
                      );
                    })()}

                    {/* ── 5b. Coverage Heatmap ── */}
                    {assembled && resultCoverageHeatmap !== null && (() => {
                      if ((resultCoverageHeatmap.data ?? []).length === 0) {
                        return (
                          <div id="result-section-heatmap">
                            <EmptyResultTable title="Median Coverage Heatmap" />
                          </div>
                        );
                      }
                      // Ensure every sample label along the x-axis, and every row label along
                      // the y-axis, has enough room to render — size the scrollable container
                      // to the number of columns/rows rather than trusting only the
                      // backend-supplied layout dimensions, and force Plotly to draw every
                      // tick (instead of auto-skipping ones that don't fit).
                      const heatmapXLabels = resultCoverageHeatmap.data?.[0]?.x ?? [];
                      const heatmapYLabels = resultCoverageHeatmap.data?.[0]?.y ?? [];
                      const heatmapMinWidth = Math.max(
                        resultCoverageHeatmap.layout?.width || 0,
                        heatmapXLabels.length * 32 + 120
                      );
                      const heatmapMinHeight = Math.max(
                        260,
                        heatmapYLabels.length * 22 + 120
                      );
                      return (
                        <div id="result-section-heatmap" className="rounded-xl border border-border overflow-hidden">
                          <div className="flex items-center justify-between px-3 py-2 bg-muted/20 border-b border-border">
                            <p className="text-xs font-bold text-foreground uppercase tracking-wider">Median Coverage Heatmap</p>
                          </div>
                          <div className="p-2 overflow-x-auto">
                            <div style={{ minWidth: `${heatmapMinWidth}px` }}>
                              <Suspense fallback={<div className="flex items-center justify-center h-40 text-xs text-muted-foreground">Loading chart…</div>}>
                                <Plot
                                  data={resultCoverageHeatmap.data ?? []}
                                  layout={{
                                    ...(resultCoverageHeatmap.layout ?? {}),
                                    autosize: true,
                                    margin: { l: 100, r: 20, t: 90, b: 20 },
                                    paper_bgcolor: "transparent",
                                    plot_bgcolor: "transparent",
                                    font: { size: 11 },
                                    xaxis: {
                                      ...(resultCoverageHeatmap.layout?.xaxis ?? {}),
                                      side: "top",
                                      tickangle: 360,
                                      automargin: true,
                                      ...(heatmapXLabels.length > 0
                                        ? { tickmode: "array", tickvals: heatmapXLabels, ticktext: heatmapXLabels }
                                        : {}),
                                    },
                                    yaxis: {
                                      ...(resultCoverageHeatmap.layout?.yaxis ?? {}),
                                      automargin: true,
                                      ...(heatmapYLabels.length > 0
                                        ? { tickmode: "array", tickvals: heatmapYLabels, ticktext: heatmapYLabels }
                                        : {}),
                                    },
                                  }}
                                  config={PLOT_CONFIG}
                                  style={{ width: "100%", height: heatmapMinHeight }}
                                  useResizeHandler
                                />
                              </Suspense>
                            </div>
                          </div>
                        </div>
                      );
                    })()}

                    {/* ── 4. MIRA Summary ── */}
                    {assembled && resultMiraSummary !== null && (
                      <div id="result-section-summary">
                        {resultMiraSummary.length === 0 ? (
                          <EmptyResultTable title="Mira Summary Table" />
                        ) : (
                          <ResultTable title="Mira Summary Table" data={resultMiraSummary} page={miraSummaryPage} setPage={setMiraSummaryPage} colorize />
                        )}
                      </div>
                    )}

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
                        <div id="result-section-coverage" className="rounded-xl border border-border overflow-hidden">
                          <div className="flex items-center justify-between px-3 py-2 bg-muted/20 border-b border-border">
                            <p className="text-xs font-bold text-foreground uppercase tracking-wider">Per-Sample Coverage and Sankey Plots</p>
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
                                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider px-1 pb-1">Sankey Plot - {currentSample}</p>
                                <div className="overflow-x-auto">
                                  <div style={{ minWidth: figure.layout?.width ? `${figure.layout.width}px` : "100%" }}>
                                    <Suspense fallback={<div className="flex items-center justify-center h-40 text-xs text-muted-foreground">Loading chart…</div>}>
                                    <Plot
                                      data={figure.data ?? []}
                                      layout={{
                                        ...(figure.layout ?? {}),
                                        autosize: true,
                                        margin: { l: 20, r: 20, t: 30, b: 20 },
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

                          {/* ── Linear Coverage Plot ── */}
                          {(() => {
                            return (
                              <div className="border-t border-border p-2">
                                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider px-1 pb-1">Coverage Plot - {currentSample}</p>
                                {covFigure ? (
                                  <div className="overflow-x-auto">
                                    <div style={{ minWidth: covFigure.layout?.width ? `${covFigure.layout.width}px` : "100%" }}>
                                      <Suspense fallback={<div className="flex items-center justify-center h-40 text-xs text-muted-foreground">Loading chart…</div>}>
                                        <Plot
                                          data={covFigure.data ?? []}
                                          layout={{
                                            ...(covFigure.layout ?? {}),
                                            autosize: true,
                                            margin: { l: 50, r: 20, t: 30, b: 40 },
                                            paper_bgcolor: "transparent",
                                            plot_bgcolor: "transparent",
                                            font: { size: 11 },
                                          }}
                                          config={{ ...(covFigure.config ?? {}), ...PLOT_CONFIG }}
                                          style={{ width: "100%", minHeight: 260 }}
                                          useResizeHandler
                                        />
                                      </Suspense>
                                    </div>
                                  </div>
                                ) : (
                                  <div className="flex items-center gap-2 text-xs text-muted-foreground px-3 py-4">
                                    <Database size={13} className="shrink-0" /> No coverage plot found for this sample.
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
                      <div id="result-section-variants">
                        {resultVariants.length === 0 ? (
                          <EmptyResultTable title="AA Variants Table" />
                        ) : (
                          <ResultTable title="AA Variants Table" data={resultVariants} page={variantsPage} setPage={setVariantsPage} />
                        )}
                      </div>
                    )}

                    {/* ── 7. Minor SNVs ── */}
                    {assembled && resultMinorSnvs !== null && (
                      <div id="result-section-snvs">
                        {resultMinorSnvs.length === 0 ? (
                          <EmptyResultTable title="Minor Variants Table" message="No Minor Variants found for this run." />
                        ) : (
                          <ResultTable title="Minor Variants Table" data={resultMinorSnvs} page={minorSnvsPage} setPage={setMinorSnvsPage} />
                        )}
                      </div>
                    )}

                    {/* ── 8. Reference Indels ── */}
                    {assembled && resultIndels !== null && (
                      <div id="result-section-indels">
                        {resultIndels.length === 0 ? (
                          <EmptyResultTable title="Minor Indels Table" message="No Minor Indels found for this run." />
                        ) : (
                          <ResultTable title="Minor Indels Table" data={resultIndels} page={indelsPage} setPage={setIndelsPage} />
                        )}
                      </div>
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
                        const nextcladeFastaUrl = `${API.downloadNextcladeFasta}?run_name=${encodeURIComponent(selectedRun?.run_name ?? "")}&experiment_type=${encodeURIComponent(selectedRun?.experiment_type ?? "")}&key=${encodeURIComponent(key)}`;
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
                                <ExternalLink size={11} /> View NextClade Assignment
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
      </div>

      {/* ── Resizable divider ────────────────────── */}
      <div
        onMouseDown={onMouseDown}
        className="w-1 shrink-0 cursor-col-resize bg-border hover:bg-primary/40 transition-colors"
      />

      {/* ── Right: run panel ─────────────────────── */}
      <aside
        style={{ width: rightWidth }}
        className="shrink-0 border-l border-border p-4 flex flex-col gap-4 bg-muted/10 overflow-y-auto"
      >
        <div className="pt-3 space-y-1.5">
          <p className="text-xs font-bold tracking-wider text-muted-foreground uppercase mb-2">Quick Actions</p>
          {[
            [PlusCircle, "New Run",  resetRun],
            [FolderOpen, "Load Run", openLoadRunModal],
            [Pencil,     "Edit Run", openEditRunModal],
            [Download,   "Export Run", openExportRunModal],
          ].map(([Icon, label, action]) => (
            <button key={label} onClick={action} className="w-full flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs text-foreground hover:bg-muted/60 transition-colors border border-transparent hover:border-border">
              <Icon size={13} className="text-primary" /> {label}
            </button>
          ))}
        </div>

        {(runName || experimentType) && (
          <div className="border-t border-border pt-3 space-y-1.5">
            <p className="text-xs font-bold tracking-wider text-muted-foreground uppercase mb-2">Run Information</p>
            {runName && (
              <div className="flex items-center gap-1.5 text-xs">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground shrink-0">Name:</span>
                <span className="font-mono font-semibold text-foreground truncate">{runName}</span>
              </div>
            )}
            {experimentType && (
              <div className="flex items-center gap-1.5 text-xs">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground shrink-0">Type:</span>
                <span className="font-mono text-foreground truncate">{experimentType}</span>
              </div>
            )}
            {primer && (
              <div className="flex items-center gap-1.5 text-xs">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground shrink-0">Primer:</span>
                <span className="font-mono text-foreground truncate">
                  {(experimentType?.startsWith("SC2") ? SC2_PRIMERS : experimentType?.startsWith("RSV") ? RSV_PRIMERS : [])
                    .find(p => p.value === primer)?.label || primer}
                </span>
              </div>
            )}
          </div>
        )}

        <div className="border-t border-border pt-3 space-y-1">
          <p className="text-xs font-bold tracking-wider text-muted-foreground uppercase mb-2">Jump To</p>
          {ASSEMBLY_STEPS.map(({ id, title, icon: Icon }) => (
            <Fragment key={id}>
              <button
                onClick={() => {
                  setOpenStep(prev => { const next = new Set(prev); next.add(id); return next; });
                  setTimeout(() => document.getElementById(`step-${id}`)?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
                }}
                className={cn(
                  "w-full flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs transition-colors border text-left",
                  openStep.has(id)
                    ? "text-primary border-primary/20 bg-primary/5"
                    : "text-foreground border-transparent hover:bg-muted/60 hover:border-border"
                )}
              >
                <Icon size={13} className="text-primary shrink-0" />
                <span className="truncate">{title}</span>
              </button>
              {id === "results" && assembled && !hasNoResults && resultSections.length > 0 && (
                <div className="ml-4 pl-2 border-l border-border space-y-0.5">
                  {resultSections.map(({ id: sectionId, label }) => (
                    <button
                      key={sectionId}
                      onClick={() => {
                        setOpenStep(prev => { const next = new Set(prev); next.add("results"); return next; });
                        setTimeout(() => document.getElementById(sectionId)?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
                      }}
                      className="w-full flex items-center px-3 py-1 rounded-md text-xs text-muted-foreground hover:text-primary hover:bg-muted/60 transition-colors text-left"
                    >
                      <span className="truncate">{label}</span>
                    </button>
                  ))}
                </div>
              )}
            </Fragment>
          ))}
        </div>

        <div className="mt-auto border-t border-border pt-3">
          <p className="text-center text-xs text-muted-foreground"><a href="https://cdcgov.github.io/MIRA/" target="_blank" rel="noopener noreferrer" className="font-mono text-primary hover:underline">cdcgov.github.io/MIRA/</a></p>
        </div>
      </aside>

      {/* ── Export Run modal ─────────────────── */}
      {exportRunModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="bg-background border border-border rounded-xl p-6 max-w-2xl w-full mx-4 shadow-xl flex flex-col gap-4">
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
                <p className="text-xs text-muted-foreground text-center py-4">There are no runs with status of "COMPLETED" found in storage.</p>
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
                      <p className="text-xs text-muted-foreground text-center py-3">No runs match your search.</p>
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

      {/* ── Load Run modal ────────────────────── */}
      {loadRunModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="bg-background border border-border rounded-xl p-6 max-w-2xl w-full mx-4 shadow-xl flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-foreground">Load Existing Runs</h3>
              <button onClick={() => setLoadRunModal(false)} className="text-muted-foreground hover:text-foreground transition-colors">
                <X size={14} />
              </button>
            </div>

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
                <p className="text-xs text-muted-foreground text-center py-4">There are no runs found in storage.</p>
              ) : (() => {
                const q = runSearch.trim().toLowerCase();
                const filtered = (q
                  ? availableRuns.filter(r =>
                      [r.run_name, r.experiment_type, r.assembly_status, r.run_date]
                        .some(v => (v ?? "").toLowerCase().includes(q))
                    )
                  : availableRuns
                ).sort((a, b) => runSortDir === "asc"
                  ? (a.run_name ?? "").localeCompare(b.run_name ?? "")
                  : (b.run_name ?? "").localeCompare(a.run_name ?? ""));
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
                      title={`Sort ${runSortDir === "asc" ? "Z→A" : "A→Z"}`}
                      onClick={() => setRunSortDir(d => d === "asc" ? "desc" : "asc")}
                      className="h-8 w-8 shrink-0 flex items-center justify-center rounded-lg border border-border text-muted-foreground hover:text-primary hover:border-primary transition-colors"
                    >
                      {runSortDir === "asc" ? <ArrowUp size={13} /> : <ArrowDown size={13} />}
                    </button>
                    </div>
                    {filtered.length === 0 ? (
                      <p className="text-xs text-muted-foreground text-center py-3">No runs match your search.</p>
                    ) : (
                      <div className={cn("rounded-xl border border-border divide-y divide-border", availableRuns.length > 10 && "max-h-96 overflow-y-auto")}>
                        {filtered.map(run => (
                          <button
                            key={run.assembly_id}
                            onClick={() => setLoadRunSelectedRow(run)}
                            onDoubleClick={() => { setLoadRunSelectedRow(run); handleLoadRun(run); }}
                            className={cn(
                              "w-full text-left px-4 py-3 text-xs transition-colors",
                              loadRunSelectedRow?.assembly_id === run.assembly_id
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
                                {run.run_date && (
                                  <div className="flex items-center gap-1.5 shrink-0">
                                    <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Date:</span>
                                    <span className="font-mono text-foreground">{run.run_date}</span>
                                  </div>
                                )}
                              </div>
                              <span className={cn(
                                "px-2 py-0.5 rounded-full text-xs font-medium shrink-0",
                                run.assembly_status === "SUBMITTED"  ? "bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-400" :
                                run.assembly_status === "PROCESSING" ? "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400" :
                                run.assembly_status === "PROCESSED"  ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400" :
                                "bg-muted text-muted-foreground"
                              )}>{run.assembly_status}</span>
                            </div>
                          </button>
                        ))}
                      </div>
                    )}
                  </>
                );
              })()
            )}

            <div className="flex gap-2 justify-end pt-1">
              <button
                onClick={() => setLoadRunModal(false)}
                className="px-4 py-1.5 rounded-lg border border-border text-xs text-muted-foreground hover:bg-muted/60 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => handleLoadRun()}
                disabled={!loadRunSelectedRow || loadRunLoading}
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-primary text-primary-foreground text-xs font-semibold hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loadRunLoading ? <RefreshCw size={11} className="animate-spin" /> : <FolderOpen size={11} />}
                Load Selected Run
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Edit Run modal ────────────────────── */}
      {editRunModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="bg-background border border-border rounded-xl p-6 max-w-2xl w-full mx-4 shadow-xl flex flex-col gap-4">
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
                <p className="text-xs text-muted-foreground text-center py-4">There are no runs found in storage.</p>
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
                      <p className="text-xs text-muted-foreground text-center py-3">No runs match your search.</p>
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
                      placeholder="e.g. Flu_Illumina_2024-01-01"
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

      {/* ── Confirm Remove Sample modal ────────────── */}
      {confirmRemoveIdx !== null && (() => {
        const isOnt = experimentType.toLowerCase().endsWith("ont");
        const sample = (isOnt ? ontSampleRows : illuminaSampleRows)[confirmRemoveIdx];
        return (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
            <div className="bg-background border border-border rounded-xl p-8 max-w-lg w-full mx-4 shadow-xl flex flex-col gap-5">
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
const SEQSENDER_STEPS = [
  { id: "setup",  title: "STEP 1: SEQSENDER SETUP",    subtitle: "Select database target, organism, input files, and submit",  icon: Database },
  { id: "status", title: "STEP 2: SUBMISSION STATUS",  subtitle: "Track per-database submission progress",                     icon: ClipboardList },
];
const ORGANISMS = ["FLU", "COV", "RSV", "POX", "ARBO", "OTHER"];
const DB_LIST = [
  { key: "biosample", label: "BioSample",  desc: "NCBI BioSample — biological source metadata" },
  { key: "sra",       label: "SRA",        desc: "NCBI Sequence Read Archive — raw read data" },
  { key: "genbank",   label: "GenBank",    desc: "NCBI GenBank — assembled consensus sequences" },
  { key: "gisaid",    label: "GISAID",     desc: "GISAID — submissions of Influenza, SARS-CoV-2, & other pathogens genomic data" },
];

// ── SeqSender Tab Component ────────────────────────
function SeqSenderTab() {
  const [openStep, setOpenStep]           = useState(() => new Set(SEQSENDER_STEPS.map((s) => s.id)));
  const [dbs, setDbs]                     = useState({ biosample: true, sra: true, genbank: true, gisaid: true });
  const [organism, setOrganism]           = useState("");
  const [subName, setSubName]             = useState("");
  const [configFile, setConfigFile]       = useState("");
  const [metaFile, setMetaFile]           = useState("");
  const [fastaFile, setFastaFile]         = useState("");
  const [gisaidCliFile, setGisaidCliFile] = useState("");
  const [gffFile, setGffFile]             = useState("");
  const [table2asn, setTable2asn]         = useState(false);
  const [testMode, setTestMode]           = useState(false);
  const [submitted, setSubmitted]         = useState(false);
  const [rightWidth, setRightWidth]       = useState(260);
  const dragging = useRef(false);

  // Toggle the open/closed state of a step in the accordion
  const toggle = (id) => setOpenStep((prev) => {
    const next = new Set(prev);
    next.has(id) ? next.delete(id) : next.add(id);
    return next;
  });
  const toggleDb = (k) => setDbs((p) => ({ ...p, [k]: !p[k] }));

  // Handle resizing of the right panel
  const onMouseDown = useCallback(() => {
    dragging.current = true;
    const onMove = (e) => {
      if (!dragging.current) return;
      setRightWidth(Math.max(200, Math.min(420, document.body.clientWidth - e.clientX)));
    };
    const onUp = () => { dragging.current = false; window.removeEventListener("mousemove", onMove); window.removeEventListener("mouseup", onUp); };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }, []);

  return (
    <div className="flex h-full overflow-hidden">

      {/* ── Left: accordion steps ─────────────────── */}
      <div className="flex-1 overflow-auto p-4 space-y-2">
        {SEQSENDER_STEPS.map(({ id, title, subtitle, icon }) => (
          <div key={id} className="rounded-xl border border-border overflow-hidden">
            <button onClick={() => toggle(id)} className="w-full px-4 py-3 bg-muted/20 hover:bg-muted/40 transition-colors">
              <StepHeader icon={icon} title={title} subtitle={subtitle} open={openStep.has(id)} />
            </button>

            {openStep.has(id) && (
              <>
                {/* Step 1: Setup */}
                {id === "setup" && (
                  <StepPanel>
                    <div className="flex items-center gap-2 pt-1">
                      <span className="text-xs font-bold tracking-wider text-muted-foreground uppercase">Database Targets</span>
                      <div className="flex-1 h-px bg-border" />
                    </div>
                    <p className="text-xs text-muted-foreground">Select one or more target databases for this submission. <span className="text-destructive font-bold">*</span></p>
                    <div className="grid grid-cols-2 gap-2">
                      {DB_LIST.map(({ key, label, desc }) => (
                        <label key={key} className={cn(
                          "flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-colors",
                          dbs[key] ? "border-primary bg-primary/5" : "border-border hover:bg-muted/20"
                        )}>
                          <input type="checkbox" checked={dbs[key]} onChange={() => toggleDb(key)} className="mt-0.5 accent-primary" />
                          <div>
                            <p className="text-sm font-semibold">{label}</p>
                            <p className="text-xs text-muted-foreground">{desc}</p>
                          </div>
                        </label>
                      ))}
                    </div>

                    <div className="flex items-center gap-2 pt-1">
                      <span className="text-xs font-bold tracking-wider text-muted-foreground uppercase">Pathogen</span>
                      <div className="flex-1 h-px bg-border" />
                    </div>

                    <div>
                      <FieldLabel>Organism <span className="text-destructive">*</span></FieldLabel>
                      <div className="flex flex-wrap gap-2">
                        {ORGANISMS.map((org) => (
                          <button key={org} onClick={() => setOrganism(org)}
                            className={cn(
                              "px-4 py-1.5 rounded-full text-xs font-semibold border transition-colors",
                              organism === org
                                ? "bg-primary text-primary-foreground border-primary"
                                : "border-border text-muted-foreground hover:border-primary hover:text-primary"
                            )}>{org}</button>
                        ))}
                      </div>
                    </div>

                    {Object.values(dbs).some(Boolean) && organism && (
                      <div className="flex flex-wrap gap-2">
                        <a
                          href={`${API.downloadSeqsenderConfig}?organism=${encodeURIComponent(organism)}&${Object.entries(dbs).filter(([, v]) => v).map(([k]) => `${k}=true`).join("&")}`}
                          download
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-border bg-muted/20 hover:bg-muted/40 text-xs font-medium text-foreground transition-colors"
                        >
                          <Download size={13} /> Download Config File
                        </a>
                        <a
                          href={`${API.downloadSeqsenderMetadataTemplate}?organism=${encodeURIComponent(organism)}&${Object.entries(dbs).filter(([, v]) => v).map(([k]) => `${k}=true`).join("&")}`}
                          download
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-border bg-muted/20 hover:bg-muted/40 text-xs font-medium text-foreground transition-colors"
                        >
                          <Download size={13} /> Download Metadata Template
                        </a>
                      </div>
                    )}

                    <div className="flex items-center gap-2 pt-1">
                      <span className="text-xs font-bold tracking-wider text-muted-foreground uppercase">Submission Inputs</span>
                      <div className="flex-1 h-px bg-border" />
                    </div>

                    <div>
                      <FieldLabel>Submission Name <span className="text-destructive">*</span></FieldLabel>
                      <input value={subName} onChange={(e) => setSubName(e.target.value)}
                        placeholder="e.g. FLU_H3N2_2026"
                        className="w-full max-w-md h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
                    </div>

                    {[
                      { label: "Config File",    required: true,  val: configFile,    set: setConfigFile,     accept: ".yaml,.yml,.json",     ph: "config.yaml" },
                      { label: "Metadata File",  required: true,  val: metaFile,      set: setMetaFile,       accept: ".csv,.tsv,.xlsx",      ph: "metadata.csv" },
                      { label: "FASTA Files",    required: true,  val: fastaFile,     set: setFastaFile,      accept: ".fasta,.fa,.fna",      ph: "sequences.fasta" },
                      { label: "GISAID CLI",     required: true,  val: gisaidCliFile, set: setGisaidCliFile,  accept: "binary",               ph: "e.g. fluCLI" },
                      { label: "GFF File",       required: false, val: gffFile,       set: setGffFile,        accept: ".gff,.gff3",           ph: "annotation.gff (optional)" },
                    ].map(({ label, required, val, set, accept, ph }) => (
                      <div key={label}>
                        <FieldLabel>{label} {required && <span className="text-destructive">*</span>}</FieldLabel>
                        <div className="flex gap-2 max-w-md">
                          <input value={val} onChange={(e) => set(e.target.value)} placeholder={ph}
                            className="flex-1 h-9 px-3 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
                          <label className="flex items-center gap-1.5 px-3 h-9 rounded-md border border-border bg-muted/20 hover:bg-muted/40 cursor-pointer text-xs text-muted-foreground transition-colors">
                            <FolderOpen size={13} /> Browse
                            <input type="file" className="hidden" accept={accept}
                              multiple={label === "FASTA Files"}
                              onChange={(e) => e.target.files?.length && set(Array.from(e.target.files).map(file => file.name).join(", "))} />
                          </label>
                        </div>
                      </div>
                    ))}

                    <div className="flex items-center gap-2 pt-1">
                      <span className="text-xs font-bold tracking-wider text-muted-foreground uppercase">Submission Options</span>
                      <div className="flex-1 h-px bg-border" />
                    </div>

                    {[
                      { label: "--table2asn",   desc: "Use table2asn for GenBank submission (required for annotated sequences)", val: table2asn, set: setTable2asn, show: dbs.genbank },
                      { label: "--test",        desc: "Run in test mode — submit to test servers without affecting production",    val: testMode,  set: setTestMode,  show: true },
                    ].filter(({ show }) => show).map(({ label, desc, val, set }) => (
                      <button key={label} onClick={() => set((v) => !v)}
                        className="w-fit flex items-center justify-start gap-4 p-3 rounded-xl border border-border bg-muted/10 hover:bg-muted/20 transition-colors text-left">
                        <div>
                          <p className="text-sm font-mono font-semibold">{label}</p>
                          <p className="text-xs text-muted-foreground mt-0.5">{desc}</p>
                        </div>
                        <span className={cn("relative w-10 h-5 rounded-full transition-colors shrink-0 mt-0.5 pointer-events-none", val ? "bg-primary" : "bg-muted")}>
                          <span className={cn("absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform", val ? "translate-x-5" : "translate-x-0.5")} />
                        </span>
                      </button>
                    ))}

                    <div className="flex items-center gap-2 pt-1">
                      <span className="text-xs font-bold tracking-wider text-muted-foreground uppercase">Review & Submit</span>
                      <div className="flex-1 h-px bg-border" />
                    </div>

                    <button onClick={() => setSubmitted(true)} className="flex items-center gap-2 px-5 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors">
                      <Rocket size={14} /> Submit to {Object.entries(dbs).filter(([,v])=>v).map(([k])=>k).join(", ") || "selected databases"}
                    </button>
                  </StepPanel>
                )}

                {/* Step 2: Status */}
                {id === "status" && (
                  <StepPanel>
                    <div className="flex items-center gap-2 w-fit max-w-full text-xs text-warning bg-warning/10 rounded-lg px-3 py-2">
                      <AlertCircle size={13} /> Submission status and accession numbers will appear here once the submission is submitted and proccessed.
                    </div>

                    {submitted && (
                      <div className="space-y-2">
                        {[
                          { key: "biosample", label: "BioSample", accessionLabel: "BioSample Accession",  placeholder: "e.g. SAMN00000000"    },
                          { key: "sra",       label: "SRA",       accessionLabel: "SRA Accession",        placeholder: "e.g. SRR00000000"    },
                          { key: "genbank",   label: "GenBank",   accessionLabel: "GenBank Accession",    placeholder: "e.g. MN000000"       },
                          { key: "gisaid",    label: "GISAID",    accessionLabel: "EPI ISL Accession",    placeholder: "e.g. EPI_ISL_000000" },
                        ]
                          .filter(({ key }) => dbs[key])
                          .map(({ key, label, accessionLabel, placeholder }) => (
                            <div key={key} className="rounded-xl border border-border bg-muted/10 overflow-hidden">
                              <div className="flex items-center justify-between px-3 py-2 bg-muted/20 border-b border-border">
                                <p className="text-xs font-bold tracking-wide text-foreground">{label}</p>
                                <span className="px-2 py-0.5 rounded-full bg-muted text-muted-foreground text-xs font-medium">Pending</span>
                              </div>
                              <div className="px-3 py-2 space-y-1.5">
                                <div className="flex items-center justify-between text-xs">
                                  <span className="text-muted-foreground">{accessionLabel}</span>
                                  <span className="font-mono text-muted-foreground/60">{placeholder}</span>
                                </div>
                                <div className="flex items-center justify-between text-xs">
                                  <span className="text-muted-foreground">Message</span>
                                  <span className="text-muted-foreground/60">—</span>
                                </div>
                              </div>
                            </div>
                          ))}
                      </div>
                    )}
                    {submitted && (
                      <button className="flex items-center gap-2 px-5 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors">
                        <RefreshCw size={14} /> Refresh Status
                      </button>
                    )}
                  </StepPanel>
                )}

              </>
            )}
          </div>
        ))}
      </div>

      {/* ── Resizable divider ────────────────────── */}
      <div onMouseDown={onMouseDown} className="w-1 shrink-0 cursor-col-resize bg-border hover:bg-primary/40 transition-colors" />

      {/* ── Right: sidebar ───────────────────────── */}
      <aside style={{ width: rightWidth }} className="shrink-0 border-l border-border p-4 flex flex-col gap-4 bg-muted/10 overflow-y-auto">

        <div className="pt-3 space-y-1.5">
          <p className="text-xs font-bold tracking-wider text-muted-foreground uppercase mb-2">Quick Actions</p>
          {[
            [PlusCircle, "New Submission"],
            [FolderOpen, "Load Submission"],
            [Download,   "Download Config"],
          ].map(([Icon, label]) => (
            <button key={label} className="w-full flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs text-foreground hover:bg-muted/60 transition-colors border border-transparent hover:border-border">
              <Icon size={13} className="text-primary" /> {label}
            </button>
          ))}
        </div>

        <div className="mt-auto border-t border-border pt-3">
          <p className="text-center text-xs text-muted-foreground"><a href="https://cdcgov.github.io/seqsender/" target="_blank" rel="noopener noreferrer" className="font-mono text-primary hover:underline">cdcgov.github.io/seqsender/</a></p>
        </div>
      </aside>
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
      <div className="h-full grid grid-cols-2 grid-rows-2 gap-4" style={{ minHeight: "fit-content" }}>

        {/* ── Installation ─────────────────────── */}
        <ResourceCard icon={Package} title="Installation">
          <p className="text-xs text-muted-foreground mb-1">Mira requires Python 3.8+ and conda/mamba. Supports Linux and macOS.</p>
          <ResourceLink href="https://github.com/CDCgov/MIRA" icon={GitFork}>GitHub — CDCgov/MIRA</ResourceLink>
          <ResourceLink href="https://github.com/CDCgov/MIRA/blob/master/MIRA-INSTALL.sh" icon={Download} badge="script">MIRA-INSTALL.sh</ResourceLink>
          <ResourceLink href="https://github.com/CDCgov/MIRA/blob/master/requirements.txt" icon={FileStack}>requirements.txt</ResourceLink>
          <div className="mt-2 rounded-lg bg-muted/30 border border-border px-3 py-2">
            <p className="text-xs font-mono text-foreground">bash MIRA-INSTALL.sh</p>
            <p className="text-xs font-mono text-muted-foreground mt-0.5">conda activate mira &amp;&amp; python app.py</p>
          </div>
          <ResourceLink href="https://github.com/CDCgov/MIRA/blob/master/docker-compose.yml" icon={ExternalLink} badge="docker">Docker Compose</ResourceLink>
        </ResourceCard>

        {/* ── Documentation ────────────────────── */}
        <ResourceCard icon={BookOpen} title="Documentation">
          <ResourceLink href="https://github.com/CDCgov/MIRA/blob/master/README.md">Mira README</ResourceLink>
          <ResourceLink href="https://github.com/CDCgov/MIRA/wiki">Mira Wiki</ResourceLink>
          <div className="mt-1 pt-2 border-t border-border">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">Related Tools</p>
            <ResourceLink href="https://docs.nextstrain.org/projects/nextclade/en/stable/" badge="nextclade">Nextclade Documentation</ResourceLink>
            <ResourceLink href="https://docs.nextstrain.org/projects/nextclade/en/stable/user/nextclade-web/url-parameters.html">Nextclade URL Parameters</ResourceLink>
            <ResourceLink href="https://github.com/CDCgov/seqsender" badge="seqsender">SeqSender Documentation</ResourceLink>
            <ResourceLink href="https://github.com/CDCgov/irma-core">IRMA-core Documentation</ResourceLink>
          </div>
          <div className="mt-1 pt-2 border-t border-border">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">Databases</p>
            <ResourceLink href="https://www.ncbi.nlm.nih.gov/sra">NCBI SRA</ResourceLink>
            <ResourceLink href="https://www.gisaid.org">GISAID</ResourceLink>
            <ResourceLink href="https://clades.nextstrain.org">Nextclade Web</ResourceLink>
          </div>
        </ResourceCard>

        {/* ── GitHub Repositories ──────────────── */}
        <ResourceCard icon={GitFork} title="GitHub Repositories">
          {[
            { repo: "CDCgov/MIRA",          desc: "Main Mira application",              badge: "main" },
            { repo: "CDCgov/seqsender",      desc: "Sequence submission pipeline",       badge: "tool" },
            { repo: "CDCgov/irma-core",      desc: "IRMA assembly core",                badge: "tool" },
            { repo: "nextstrain/nextclade",  desc: "Clade assignment & QC tool",         badge: "ext" },
            { repo: "nextstrain/augur",       desc: "Phylogenetic analysis pipeline",    badge: "ext" },
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
            name="Mira Development Team"
            role="CDC VSDB — Virus Surveillance and Diagnostic Branch"
            email="flu@cdc.gov"
            github="CDCgov"
          />
          <ContactCard
            name="SeqSender Team"
            role="CDC — Sequence submission support"
            github="CDCgov"
          />
          <div className="mt-2 pt-2 border-t border-border space-y-1.5">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Report Issues</p>
            <ResourceLink href="https://github.com/CDCgov/MIRA/issues" icon={MessageSquare} badge="bugs">Mira GitHub Issues</ResourceLink>
            <ResourceLink href="https://github.com/CDCgov/seqsender/issues" icon={MessageSquare} badge="bugs">SeqSender GitHub Issues</ResourceLink>
          </div>
          <div className="mt-2 pt-2 border-t border-border">
            <p className="text-xs text-muted-foreground">For general inquiries about CDC influenza surveillance tools, visit <a href="https://www.cdc.gov/flu" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">cdc.gov/flu</a>.</p>
          </div>
        </ResourceCard>

      </div>
    </div>
  );
}

/* ── Placeholder tab content ─────────────────────── */
function TabContent({ tab }) {
  if (tab.id === "home")       return <HomeTab />;
  if (tab.id === "assembly")   return <AssemblyTab />;
  if (tab.id === "seqsender")  return <SeqSenderTab />;
  if (tab.id === "resources")  return <ResourcesTab />;
  return (
    <div className="p-6">
      <div className="rounded-xl border border-border bg-card p-8 text-center text-muted-foreground">
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
      <header className="h-24 shrink-0 w-full bg-primary border-b border-border flex items-center px-4 gap-3">
        {/* Brand */}
        <button
          onClick={() => navigateTo("home")}
          className="flex items-center gap-3 text-white hover:opacity-90 transition-opacity"
        >
          <div className="relative shrink-0">
            <ShaderAura className="absolute -inset-2 w-[calc(100%+1rem)] h-[calc(100%+1rem)] pointer-events-none" />
            <img
              src="/mira-logo.png"
              alt="MIRA logo"
              className="relative h-20 w-20 object-contain drop-shadow-[0_2px_6px_rgba(0,0,0,0.35)]"
            />
          </div>
          <div className="flex flex-col leading-tight">
            <div className="flex items-baseline gap-2">
              <span className="text-2xl tracking-widest text-white font-bold">Mira</span>
              <span className="text-xs text-white/50 font-mono">{versionInfo?.current_mira_version ?? "v3.0.0"}</span>
            </div>
            <span className="text-xs text-white/80 hidden sm:inline tracking-wider normalcase">
              Influenza, SARS-CoV-2, and RSV Genome Assembly &amp; Curation
            </span>
          </div>
        </button>

        {/* Right controls */}
        <div className="ml-auto flex items-center gap-1">

          {/* Notifications */}
          <Dropdown
            panelClassName="w-80"
            trigger={
              <button onClick={checkBackend} className="relative p-2 rounded-md text-white/80 hover:text-white hover:bg-white/10 transition-colors">
                <Bell size={16} />
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

      {/* ── Main area ────────────────────────────── */}
      <div className="flex-1 flex flex-col overflow-hidden">

        {/* ── Backend API alarm banner ─────────── */}
        {!backendUp && (
          <div className="shrink-0 flex items-center gap-2 px-4 py-2 bg-destructive text-destructive-foreground text-sm font-semibold">
            <AlertCircle size={16} className="shrink-0" />
            BACKEND API IS NOT RUNNING — please make sure the backend service is up and reachable at <span className="font-mono">{API_BASE}</span>
          </div>
        )}

        {/* ── Tab bar ──────────────────────────── */}
        <div className="flex border-b border-border bg-background px-3 pt-2 gap-1 shadow-sm shrink-0">
          {TABS.filter((t) => t.id !== "home").map((tab) => {
            const Icon = tab.icon;
            const active = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => navigateTo(tab.id)}
                className={cn(
                  "flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-t-md border-b-2 transition-colors",
                  active
                    ? "border-primary text-primary"
                    : "border-transparent text-muted-foreground hover:text-foreground hover:bg-muted/40"
                )}
              >
                <Icon size={14} />
                {tab.label}
              </button>
            );
          })}
        </div>
        {/* ── Tab content ──────────────────────── */}
        <main className="flex-1 overflow-hidden">
          {TABS.map((tab) => (
            <div key={tab.id} className={cn("h-full", activeTab !== tab.id && "hidden")}>
              <TabContent tab={tab} />
            </div>
          ))}
        </main>
      </div>
    </div>
  );
}
