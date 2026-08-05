###########################    Description    ##################################
# Pandera + Polars schema validation
################################################################################

# Import packages for dataframe validation
import polars as pl
import pandera.polars as pa
import pandera.errors as pe

# Import typing for type hints
from typing import Dict, List, Optional, Any

# Import general python packages
import os
import yaml
import sqlite3

# Define app version
_MIRA_NF_VERSION_URL = "https://raw.githubusercontent.com/CDCgov/Mira-nf/master/DESCRIPTION"
_MIRA_VERSION_URL = "https://raw.githubusercontent.com/CDCgov/MIRA/prod/DESCRIPTION"

# Allow files created by this backend to be group-readable and group-writable.
os.umask(0o002)

# Ensure storage directory exists with correct permissions
def _ensure_storage_directory(path: str) -> None:
    os.makedirs(path, mode=0o2775, exist_ok=True)
    os.chmod(path, 0o2775)

# Read in the config.yml file to get the data storage path
def _read_config_yml() -> Dict[str, Any]:
    config_path = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "config.yml"))
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    return config

# Get deployment type from config.yml or environment variable
def get_deploy_type() -> str:
    config = _read_config_yml()
    deploy_type = config.get("DEPLOY", None)
    if not deploy_type:
        raise ValueError("DEPLOY must be set in config.yml.")
    elif deploy_type not in ["Local", "Docker"]:
        raise ValueError("DEPLOY must be either 'Local' or 'Docker'.")
    return deploy_type

# Get the data storage path from config.yml or environment variable
def get_data_storage_path() -> str:
    config = _read_config_yml()
    data_storage_path = config.get("DATA_ROOT", None)
    if not data_storage_path:
        raise ValueError("DATA_ROOT must be set in config.yml")
    return os.path.realpath(data_storage_path)

# Get the MIRA Nextflow image from config.yml or environment variable
def get_mira_nf_image() -> str:
    config = _read_config_yml()
    mira_nf_image = config.get("MIRA_NF_IMAGE", None)
    if not mira_nf_image:
        raise ValueError("MIRA_NF_IMAGE must be set in config.yml.")
    return mira_nf_image

# Define data storage path for MIRA and SeqSender, allowing override via environment variable
_DEFAULT_DATA_STORAGE_PATH = get_data_storage_path()
_ensure_storage_directory(_DEFAULT_DATA_STORAGE_PATH)

# Define storage path for sqlite database, allowing override via environment variable
_DEFAULT_SQLITE_PATH = os.path.realpath(os.path.join(_DEFAULT_DATA_STORAGE_PATH, "SQlite"))
_ensure_storage_directory(_DEFAULT_SQLITE_PATH)

# Define storage path for MIRA data, allowing override via environment variable
_DEFAULT_MIRA_STORAGE_PATH = os.path.join(_DEFAULT_DATA_STORAGE_PATH, "MIRA")
_ensure_storage_directory(_DEFAULT_MIRA_STORAGE_PATH)

# Define storage path for SeqSender data, allowing override via environment variable
_DEFAULT_SEQSENDER_STORAGE_PATH = os.path.join(_DEFAULT_DATA_STORAGE_PATH, "SeqSender")
_ensure_storage_directory(_DEFAULT_SEQSENDER_STORAGE_PATH)

# Define local host storage path for MIRA to run in Docker
deploy_type = get_deploy_type()
if deploy_type == "Docker":
    _HOST_DATA_STORAGE_PATH = os.getenv("HOST_DATA_STORAGE_PATH", None)
    if not _HOST_DATA_STORAGE_PATH:
        raise ValueError("HOST_DATA_STORAGE_PATH must be set in docker-compose.yml as an environment variable.")
    _HOST_MIRA_STORAGE_PATH = os.path.join(_HOST_DATA_STORAGE_PATH, "MIRA")
elif deploy_type == "Local":
    _HOST_MIRA_STORAGE_PATH = _DEFAULT_DATA_STORAGE_PATH

# DEFINE MIRA-NF DOCKER IMAGE FOR THE APP
_DEFAULT_MIRA_NF_IMAGE = get_mira_nf_image()
if deploy_type == "Docker":
    _HOST_MIRA_NF_IMAGE = os.getenv("HOST_MIRA_NF_IMAGE", None)
    if not _HOST_MIRA_NF_IMAGE:
        raise ValueError("HOST_MIRA_NF_IMAGE must be set in docker-compose.yml as an environment variable.")
elif deploy_type == "Local":
    _HOST_MIRA_NF_IMAGE = _DEFAULT_MIRA_NF_IMAGE

# print(f"Using MIRA-NF Docker Image: {_HOST_MIRA_NF_IMAGE}")
# print(f"Using {deploy_type} Data Storage Path: {_DEFAULT_DATA_STORAGE_PATH}")
# print(f"Using {deploy_type} MIRA Storage Path: {_DEFAULT_MIRA_STORAGE_PATH}")
# print(f"Using Host MIRA Storage Path: {_HOST_MIRA_STORAGE_PATH}")

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
# GLOBAL VARIABLES FOR MIRA
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

# ─── Pipeline stage mapping ─────────────────
_MIRA_STAGE_MAP = [
    "CHECKMIRAVERSION",
    "CONCATFASTQS",
    "NEXTFLOWSAMPLESHEET",
    "SAMPLESHEET_CHECK",
    "FINDCHEMISTRY",
    "TRIMBARCODES",
    "SC2TRIMPRIMERS",
    "IRMA",
    "CONFIRM_IRMA_OUTPUT",
    "CREATE_IRMA_INPUT",
    "CREATE_INPUT",
    "CREATE_IRMA_FOR_QC",
    "CREATE_IRMA_FOR_QC2",
    "PASS_FAILED",
    "CREATE_DAIS_INPUT",
    "DAIS_RIBOSOME",
    "PREPARE_MIRA_REPORTS",
    "GET_NEXTCLADE_DATASET",
    "RUN_NEXTCLADE",
    "UPDATE_MIRA_SUMMARY"
]

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
    name="upload_fastq_files",
)

# ---------------------------------------------------------------------------
# GLOBAL VARIABLES FOR SEQSENDER
# ---------------------------------------------------------------------------
database_targets = ["BioSample", "SRA", "GenBank", "GISAID"]

submission_status = [
    'SUBMITTED', 'CREATED', 'QUEUED', 'PROCESSING',
    'FAILED', 'PROCESSED', 'ERROR', 'WAITING', 
    'DELETED', 'RETIRED', 'VALIDATED', 'EMAILED'
]

pathogen_targets = ["FLU", "COV", "RSV", "POX", "ARBO", "OTHER"]

# ---------------------------------------------------------------------------
# SEQSENDER SUBMISSION TABLE SCHEMA
# ---------------------------------------------------------------------------
submission_tbl_pa_schema = pa.DataFrameSchema(
    columns={
        "submission_name": _required_str(),
        "organism": _required_str(),
        "db": _required_str(),
        "submission_type": _required_str(),
        "submission_status": _required_str(),
        "submission_id": _nullable_str(required=True),
        "submission_id_status": _required_str(),
        "submission_date": _required_str(),
        "upload_date": _required_str(),
    },
    name="submission"
)
# ---------------------------------------------------------------------------
# SEQSENDER METADATA SCHEMA
# ---------------------------------------------------------------------------
metadata_tbl_pa_schema = pa.DataFrameSchema(
    columns={
        "organism": _required_str(),
        "authors": _required_str(),
        "collection_date": _required_str(),
        "bioproject": _required_str(),
        "sequence_name": _required_str(),
        "gb-sample_name": _required_str(),
        "gb-fasta_definition_line_modifiers": _nullable_str(required=False),
        "gb-title": _nullable_str(required=False),
        "gb-comment": _nullable_str(required=False),
        "src-Altitude": _nullable_str(required=False),
        "src-Bio_material": _nullable_str(required=False),
        "src-Breed": _nullable_str(required=False),
        "src-Cell_line": _nullable_str(required=False),
        "src-Cell_type": _nullable_str(required=False),
        "src-Clone": _nullable_str(required=False),
        "src-Collected_by": _nullable_str(required=False),
        "src-geo_loc_name": _required_str(),
        "src-Cultivar": _nullable_str(required=False),
        "src-Culture_collection": _nullable_str(required=False),
        "src-Dev_stage": _nullable_str(required=False),
        "src-Ecotype": _nullable_str(required=False),
        "src-Fwd_primer_name": _nullable_str(required=False),
        "src-Fwd_primer_seq": _nullable_str(required=False),
        "src-Genotype": _nullable_str(required=False),
        "src-Haplogroup": _nullable_str(required=False),
        "src-Haplotype": _nullable_str(required=False),
        "src-Host": _required_str(),
        "src-Isolate": _required_str(),
        "src-Isolation-source": _nullable_str(required=False),
        "src-Lab_host": _nullable_str(required=False),
        "src-Lat_Lon": _nullable_str(required=False),
        "src-Note": _nullable_str(required=False),
        "src-Rev_primer_name": _nullable_str(required=False),
        "src-Rev_primer_seq": _nullable_str(required=False),
        "src-Segment": _nullable_str(required=False),
        "src-Serotype": _nullable_str(required=False),
        "src-Serovar": _nullable_str(required=False),
        "src-Sex": _nullable_str(required=False),
        "src-Specimen_voucher": _nullable_str(required=False),
        "src-Strain": _nullable_str(required=False),
        "src-Sub_species": _nullable_str(required=False),
        "src-Tissue_lib": _nullable_str(required=False),
        "src-Tissue_type": _nullable_str(required=False),
        "src-Variety": _nullable_str(required=False),
        "cmt-StructuredCommentPrefix": _required_str(),
        "cmt-StructuredCommentSuffix": _required_str(),
        "cmt-Assembly Method": _required_str(),
        "gs-sample_name": _required_str(),
        "gs-rsv_subtype": _required_str(),
        "gs-rsv_passage": _required_str(),
        "gs-rsv_location": _required_str(),
        "gs-rsv_add_location": _nullable_str(required=False),
        "gs-rsv_host": _required_str(),
        "gs-rsv_add_host_info": _nullable_str(required=False),
        "gs-rsv_sampling_strategy": _nullable_str(required=False),
        "gs-rsv_sex": _required_str(),
        "gs-rsv_patient_age": _required_str(),
        "gs-rsv_patient_status": _required_str(),
        "gs-rsv_specimen": _nullable_str(required=False),
        "gs-rsv_outbreak": _nullable_str(required=False),
        "gs-rsv_last_vaccinated": _nullable_str(required=False),
        "gs-rsv_treatment": _nullable_str(required=False),
        "gs-rsv_seq_technology": _required_str(),
        "gs-rsv_assembly_method": _nullable_str(required=False),
        "gs-rsv_coverage": _nullable_str(required=False),
        "gs-rsv_orig_lab": _required_str(),
        "gs-rsv_orig_lab_addr": _required_str(),
        "gs-rsv_provider_sample_id": _nullable_str(required=False),
        "gs-rsv_subm_lab": _required_str(),
        "gs-rsv_subm_lab_addr": _required_str(),
        "gs-rsv_subm_sample_id": _nullable_str(required=False),
        "gs-rsv_comment": _required_str(),
        "gs-comment_type": _required_str(),
        "bs-sample_name": _required_str(),
        "bs-sample_title": _required_str(),
        "bs-sample_description": _nullable_str(required=False),
        "bs-strain": _nullable_str(required=False),
        "bs-isolate": _nullable_str(required=False),
        "bs-collected_by": _required_str(),
        "bs-geo_loc_name": _required_str(),
        "bs-host": _required_str(),
        "bs-host_disease": _required_str(),
        "bs-isolation_source": _required_str(),
        "bs-lat_lon": _required_str(),
        "bs-culture_collection": _nullable_str(required=False),
        "bs-genotype": _nullable_str(required=False),
        "bs-host_age": _nullable_str(required=False),
        "bs-host_description": _nullable_str(required=False),
        "bs-host_disease_outcome": _nullable_str(required=False),
        "bs-host_disease_stage": _nullable_str(required=False),
        "bs-host_health_state": _nullable_str(required=False),
        "bs-host_sex": _nullable_str(required=False),
        "bs-host_subject_id": _nullable_str(required=False),
        "bs-host_tissue_sampled": _nullable_str(required=False),
        "bs-passage_history": _nullable_str(required=False),
        "bs-pathotype": _nullable_str(required=False),
        "bs-serotype": _nullable_str(required=False),
        "bs-serovar": _nullable_str(required=False),
        "bs-specimen_voucher": _nullable_str(required=False),
        "bs-subgroup": _nullable_str(required=False),
        "bs-subtype": _nullable_str(required=False),
        "bs-title": _nullable_str(required=False),
        "bs-comment": _nullable_str(required=False),
        "sra-sample_name": _required_str(),
        "sra-file_location": _required_str(),
        "sra-file_1": _required_str(),
        "sra-file_#": _nullable_str(required=False),
        "sra-library_name": _nullable_str(required=False),
        "sra-loader": _nullable_str(required=False),
        "sra-library_strategy": _required_str(),
        "sra-library_source": _required_str(),
        "sra-library_selection": _required_str(),
        "sra-library_layout": _required_str(),
        "sra-platform": _nullable_str(required=False),
        "sra-instrument_model": _required_str(),
        "sra-design_description": _nullable_str(required=False),
        "sra-title": _nullable_str(required=False),
        "sra-comment": _nullable_str(required=False),
    },
    checks=[
        pa.Check(
            lambda data: data.lazyframe.select(
                (pl.col("bs-strain").is_not_null() | pl.col("bs-isolate").is_not_null())
                .alias("bs_strain_or_isolate_present")
            ),
            error="At least one of 'bs-strain' or 'bs-isolate' is required.",
        ),
    ],
    name="metadata",
)


