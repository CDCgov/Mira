###########################    Description    ##################################
# Pandera + Polars schema validation
# Each pandera DataFrameSchema mirrors the corresponding *_tbl_schema dict in
# global_var.py and provides richer, human-readable validation error messages.
################################################################################

# Import packages for dataframe validation
import polars as pl
import pandera.polars as pa
import pandera.errors as pe

# Import typing for type hints
from typing import Dict, List, Optional, Any

# Import general python packages
import os
import sqlite3

# Allow files created by this backend to be group-readable and group-writable.
os.umask(0o002)

# Ensure storage directory exists with correct permissions
def _ensure_storage_directory(path: str) -> None:
    os.makedirs(path, mode=0o2775, exist_ok=True)
    os.chmod(path, 0o2775)

# Define storage paths for sqlite database and schema file
_DEFAULT_SCHEMA_FILE = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "sqlite/schema.sql"))

# Define data storage path for MIRA and SeqSender, allowing override via environment variable
_DEFAULT_DATA_STORAGE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "data"))
_ensure_storage_directory(_DEFAULT_DATA_STORAGE_PATH)

# Define storage path for sqlite database, allowing override via environment variable
_DEFAULT_SQLITE_PATH = os.path.realpath(os.path.join(_DEFAULT_DATA_STORAGE_PATH, "sqlite"))
_ensure_storage_directory(_DEFAULT_SQLITE_PATH)

# Create sqlite database if it doesn't exist, using schema.sql
_DEFAULT_SQLITE_FILE = os.path.join(_DEFAULT_SQLITE_PATH, "mira.db")
if not os.path.exists(_DEFAULT_SQLITE_FILE):
    with open(_DEFAULT_SCHEMA_FILE, "r") as f:
        schema_sql = f.read()
    conn = sqlite3.connect(_DEFAULT_SQLITE_FILE)
    conn.executescript(schema_sql)
    conn.commit()
    conn.close()
os.chmod(_DEFAULT_SQLITE_FILE, 0o664)

# Define host storage path for MIRA and SeqSender data, allowing override via environment variable
_DEFAULT_MIRA_STORAGE_PATH = os.path.join(_DEFAULT_DATA_STORAGE_PATH, "MIRA")
_ensure_storage_directory(_DEFAULT_MIRA_STORAGE_PATH)

# HOST-side path to the MIRA storage directory, used ONLY as the bind-mount source
# for sibling "docker run" containers launched via the Docker socket (DooD cleanup /
# pipeline launch in mira_handler.py). The Docker daemon always resolves "-v" sources
# against the HOST filesystem regardless of which container issued the command, so
# this must never be used for direct file I/O inside this process — that's what
# _DEFAULT_MIRA_STORAGE_PATH (above) is for. Set HOST_DATA_STORAGE_PATH in
# docker-compose.yml to the real host path of ./backend/data.
_HOST_DATA_STORAGE_PATH = os.getenv("HOST_DATA_STORAGE_PATH", _DEFAULT_DATA_STORAGE_PATH)
_HOST_MIRA_STORAGE_PATH = os.path.join(_HOST_DATA_STORAGE_PATH, "MIRA")

# DEFINE CURRENT MIRA DOCKER IMAGE FOR THE APP
_MIRA_NF_IMAGE = "cdcgov/mira-nf:v2.1.1"
_DEFAULT_MIRA_NF_IMAGE = os.getenv("HOST_MIRA_NF_IMAGE", _MIRA_NF_IMAGE)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _nullable_str(checks=None, required: bool = True) -> pa.Column:
    """Shorthand: nullable String column."""
    return pa.Column(pl.String, checks=checks, nullable=True, required=required)

def _required_str(checks=None, required: bool = True) -> pa.Column:
    """Shorthand: non-nullable String column."""
    return pa.Column(pl.String, checks=checks, nullable=False, required=required)

def _enum_col(levels: list, nullable: bool = False, required: bool = True) -> pa.Column:
    """String column restricted to *levels* (mirrors pl.Enum)."""
    return pa.Column(pl.String, pa.Check.isin(levels), nullable=nullable, required=required)

def _nullable_enum_col(levels: list, required: bool = True) -> pa.Column:
    """String column allowing NULL, empty string, or a value from *levels*."""
    return pa.Column(pl.String, pa.Check.isin([*levels, ""]), nullable=True, required=required)

def validate_tbl(
    df: pl.DataFrame,
    schema: pa.DataFrameSchema,
    table_name: str = "",
) -> pl.DataFrame:
    """
    Validate *df* against a pandera DataFrameSchema.

    Coercion is applied so that all-null columns (dtype ``Null``) are cast to
    the declared column dtype before validation runs.

    status: Literal[tuple(sample_status)] = Field(..., description="Keep or exclude this sample.")
    Raises ``ValueError`` with a human-readable failure table on schema errors.

    Parameters
    ----------
    df : pl.DataFrame
        The dataframe to validate.
    schema : pa.DataFrameSchema
        The pandera schema to validate against.
    table_name : str, optional
        Display name used in the error header.
    """
    # Cast all-null columns to their declared dtype so pandera dtype check passes
    casts = []
    for col_name, col_schema in schema.columns.items():
        if col_name in df.columns and df[col_name].dtype == pl.Null:
            casts.append(pl.col(col_name).cast(col_schema.dtype.type))
    if casts:
        df = df.with_columns(casts)

    try:
        return schema.validate(df, lazy=True)
    except pe.SchemaErrors as exc:
        label = f"[{table_name}] " if table_name else ""
        raise ValueError(
            f"{label}Schema validation failed:\n{exc.failure_cases}"
        ) from exc
    except pe.SchemaError as exc:
        label = f"[{table_name}] " if table_name else ""
        raise ValueError(f"{label}Schema validation failed: {exc}") from exc


# ---------------------------------------------------------------------------
# GLOBAL VARIABLES
# ---------------------------------------------------------------------------
experiment_types = [
    'Flu-ONT',
    'Flu-Illumina',
    'SC2-Spike-Only-ONT',
    'SC2-Whole-Genome-ONT',
    'SC2-Whole-Genome-Illumina',
    'RSV-Illumina',
    'RSV-ONT'
]
sample_types = ["- Control", "+ Control", "Test"]
sample_status = ["Keep", "Exclude"]
sc2_primers = [
    'articv3',
    'articv4',
    'articv4.1',
    'articv5.3.2',
    'qiagen',
    'swift',
    'swift_211206'
]
rsv_primers = ['RSV_CDC_8amplicon_230901']
irma_modules = ['sensitive', 'secondary', 'utr']
assembly_status = ['SUBMITTED', 'PROCESSING', 'FAILED', 'CANCELED', 'COMPLETED']

# Valid Nextclade Web `dataset-name` shortcuts, keyed by pathogen and segment.
# Source of truth: https://data.clades.nextstrain.org/v3/index.json
# Segments not listed here (e.g. flu h3n2/h1n1pdm pb1/pb2/np/mp/ns) have no
# shortcut and must be referenced by their full dataset `path` instead
# (e.g. "nextstrain/flu/h3n2/pb2").
NEXTCLADE_DATASET_SHORTCUTS = {
    "flu": {
        "h3n2":     {"ha": "flu_h3n2_ha",     "na": "flu_h3n2_na",     "pa": "flu_h3n2_pa"},
        "h1n1pdm":  {"ha": "flu_h1n1pdm_ha",  "na": "flu_h1n1pdm_na",  "pa": "flu_h1n1pdm_pa"},
        "h1n1":     {"ha": "flu_h1n1_ha",     "na": "flu_h1n1_na",     "pa": "flu_h1n1_pa",
                     "pb1": "flu_h1n1_pb1",   "pb2": "flu_h1n1_pb2",   "np": "flu_h1n1_np",
                     "mp": "flu_h1n1_mp",     "ns": "flu_h1n1_ns"},
        "h2n2":     {"ha": "flu_h2n2_ha",     "na": "flu_h2n2_na",     "pa": "flu_h2n2_pa",
                     "pb1": "flu_h2n2_pb1",   "pb2": "flu_h2n2_pb2",   "np": "flu_h2n2_np",
                     "mp": "flu_h2n2_mp",     "ns": "flu_h2n2_ns"},
        "b":        {"ha": "flu_b_ha",        "na": "flu_b_na",        "pa": "flu_b_pa",
                     "pb1": "flu_b_pb1",      "pb2": "flu_b_pb2",      "np": "flu_b_np",
                     "mp": "flu_b_mp",        "ns": "flu_b_ns"},
        "vic":      {"ha": "flu_vic_ha",      "na": "flu_vic_na"},
        "yam":      {"ha": "flu_yam_ha"},
    },
    "rsv": {
        "a": "rsv_a",
        "b": "rsv_b",
    },
    "sars-cov-2": "sars-cov-2",
    "mpox": {
        "all-clades": "MPXV",
        "clade-iib":  "hMPXV",
        "lineage-b.1": "hMPXV_B1",
    },
}

# ---------------------------------------------------------------------------
# ASSEMBLY SCHEMA
# ---------------------------------------------------------------------------
assembly_pa_schema = pa.DataFrameSchema(
    columns={
        "run_name": _required_str(),
        "experiment_type": _required_str(),
        "sc2_primer": _nullable_enum_col(sc2_primers, required=False),
        "rsv_primer": _nullable_enum_col(rsv_primers, required=False),
        "subsample": pa.Column(pl.Int64, nullable=False, required=True),
        "parquet_files": pa.Column(pl.Boolean, nullable=False, required=True),
        "run_nextclade": pa.Column(pl.Boolean, nullable=False, required=True),
        "irma_module": _nullable_enum_col(irma_modules, required=False),
        "custom_irma_config": _nullable_str(required=False),
        "custom_qc_settings": _nullable_str(required=False),
        "assembly_status": _enum_col(assembly_status, nullable=True, required=False),
    },
    name="assembly",
)
# ---------------------------------------------------------------------------
assembly_db_schema = pa.DataFrameSchema(
    columns={
        "assembly_id": pa.Column(pl.Int64, nullable=False, required=False),
        **{col: pa.Column(assembly_pa_schema.columns[col].dtype.type, nullable=assembly_pa_schema.columns[col].nullable, required=assembly_pa_schema.columns[col].required) for col in assembly_pa_schema.columns}
    },
    name="assembly_db",
)

# ---------------------------------------------------------------------------
# ONT SAMPLESHEET SCHEMA
# ---------------------------------------------------------------------------
ont_samplesheet_pa_schema = pa.DataFrameSchema(
    columns={
        "barcode": _required_str(),
        "sample_id": _required_str(),
        "sample_type": _enum_col(sample_types, nullable=False, required=True),
        "single_end": pa.Column(pl.Boolean, nullable=False, required=True),
        "fastq": _required_str(),
        "status": _enum_col(sample_status, nullable=False, required=True),
    },
    name="ont_samplesheet",
)
# ---------------------------------------------------------------------------
ont_samplesheet_db_schema = pa.DataFrameSchema(
    columns={
        "assembly_id": pa.Column(pl.Int64, nullable=False, required=False),
        **{col: pa.Column(ont_samplesheet_pa_schema.columns[col].dtype.type, nullable=ont_samplesheet_pa_schema.columns[col].nullable, required=ont_samplesheet_pa_schema.columns[col].required) for col in ont_samplesheet_pa_schema.columns}
    },
    name="ont_samplesheet_db",
)

# ---------------------------------------------------------------------------
# ILLUMINA SAMPLESHEET SCHEMA
# ---------------------------------------------------------------------------
illumina_samplesheet_pa_schema = pa.DataFrameSchema(
    columns={
        "sample_id": _required_str(),
        "sample_type": _enum_col(sample_types, nullable=False, required=True),
        "single_end": pa.Column(pl.Boolean, nullable=False, required=True),
        "fastq_1": _required_str(),
        "fastq_2": _nullable_str(),
        "status": _enum_col(sample_status, nullable=False, required=True),
    },
    name="illumina_samplesheet",
)
# ---------------------------------------------------------------------------
illumina_samplesheet_db_schema = pa.DataFrameSchema(
    columns={
        "assembly_id": pa.Column(pl.Int64, nullable=False, required=False),
        **{col: pa.Column(illumina_samplesheet_pa_schema.columns[col].dtype.type, nullable=illumina_samplesheet_pa_schema.columns[col].nullable, required=illumina_samplesheet_pa_schema.columns[col].required) for col in illumina_samplesheet_pa_schema.columns}
    },
    name="illumina_samplesheet_db",
)

# ---------------------------------------------------------------------------
# UPLOADED FASTQ FILES SCHEMA
# ---------------------------------------------------------------------------
upload_fastq_files_pa_schema = pa.DataFrameSchema(
    columns={
        "sample_id": _required_str(),
        "fastq_path": pa.Column(pl.String, nullable=False, required=True),
    },
    name="uploaded_fastq_files",
)

# ─── Pipeline stage groupings (process short-name → stage id) ─────────────────
_STAGE_MAP: Dict[str, Dict[str, str]] = {
    "CHECK_MIRA_VERSION":     {"task_id": 1},
    "CONCAT_FASTQS":          {"task_id": 2},
    "NEXTFLOW_SAMPLESHEET":   {"task_id": 3},
    "SAMPLESHEET_CHECK":      {"task_id": 4},
    "FIND_CHEMISTRY":         {"task_id": 5},
    "TRIM_BARCODES":          {"task_id": 6},
    "IRMA":                   {"task_id": 7},
    "CONFIRM_IRMA_OUTPUT":    {"task_id": 8},
    "CREATE_IRMA_INPUT":      {"task_id": 9},
    "CREATE_INPUT":           {"task_id": 10},
    "CREATE_IRMA_FOR_QC":     {"task_id": 11},
    "CREATE_IRMA_FOR_QC2":    {"task_id": 12},
    "PASS_FAILED":            {"task_id": 13},
    "CREATE_DAIS_INPUT":      {"task_id": 14},
    "DAIS_RIBOSOME":          {"task_id": 15},
    "PREPARE_MIRA_REPORTS":   {"task_id": 16},
    "GET_NEXTCLADE_DATASET":  {"task_id": 17},
    "RUN_NEXTCLADE":          {"task_id": 18},
    "UPDATE_MIRA_SUMMARY":    {"task_id": 19},
}
