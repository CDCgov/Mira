###########################    Description    ##################################
# Global variables + Pandera + Polars schema validation
################################################################################

# Import packages for dataframe validation
import polars as pl
import pandera.polars as pa
import pandera.errors as pe

# Import typing for type hints
from typing import Dict, List, Optional, Any

# Import general python packages
import re
import os
import yaml

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

# Get REACT base URL from config.yml or environment variable
def get_react_port() -> str:
    config = _read_config_yml()
    react_port = config.get("REACT_PORT", None)
    if not react_port:
        raise ValueError("REACT_PORT must be set in config.yml.")
    return react_port

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

# Get deployment type from config.yml
_DEPLOY_TYPE = get_deploy_type()

# DEFINE MIRA-NF DOCKER IMAGE FOR THE APP
_MIRA_NF_IMAGE = get_mira_nf_image()

# Define React base URL for the app
_REACT_PORT = get_react_port()

# print(f"Deploy Type: {_DEPLOY_TYPE}")
# print(f"MIRA-NF Image: {_MIRA_NF_IMAGE}")
# print(f"Data Storage Path: {_DEFAULT_DATA_STORAGE_PATH}")
# print(f"MIRA Storage Path: {_DEFAULT_MIRA_STORAGE_PATH}")
# print(f"React Port: {_REACT_PORT}")

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _nullable_str(checks=None, required: bool = True, description: str = None) -> pa.Column:
    """Shorthand: nullable String column."""
    return pa.Column(pl.String, checks=checks, nullable=True, required=required, description=description)

def _required_str(checks=None, required: bool = True, description: str = None) -> pa.Column:
    """Shorthand: non-nullable String column."""
    return pa.Column(pl.String, checks=checks, nullable=False, required=required, description=description)

def _required_enum_col(levels: list, nullable: bool = False, required: bool = True, checks=None, description: str = None) -> pa.Column:
    """String column restricted to *levels* (mirrors pl.Enum)."""
    all_checks = [pa.Check.isin(levels), *([checks] if checks is not None else [])]
    return pa.Column(pl.String, all_checks, nullable=nullable, required=required, description=description)

def _nullable_enum_col(levels: list, required: bool = True, checks=None, description: str = None) -> pa.Column:
    """String column allowing NULL, empty string, or a value from *levels*."""
    all_checks = [pa.Check.isin([*levels, ""]), *([checks] if checks is not None else [])]
    return pa.Column(pl.String, all_checks, nullable=True, required=required, description=description)

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
# GLOBAL VARIABLES FOR SEQSENDER
# --------------------------------------------------------------------------- 
organisms = ["FLU", "COV", "RSV"]
biosample_packages = {
    "FLU": "Pathogen.cl.1.0",
    "COV": "Pathogen.cl.1.0",
    "RSV": "Pathogen.cl.1.0"
}
database_targets = [
    "BIOSAMPLE",
    "SRA",
    "GENBANK",
    "GISAID"
]
database_prefixes = {
    "BIOSAMPLE": "bs",
    "SRA": "sra",
    "GENBANK": "gb",
    "GISAID": "gs"
}
database_statuses = ["ACTIVE", "INACTIVE"]
submission_types = ["TEST", "PRODUCTION"]
submission_portals = ["NCBI", "GISAID"]
submission_statuses = [
    'CREATED', 'RUNNING', 'SUBMITTED', 'PROCESSING', 
    'CANCELED','FAILED', 'COMPLETED'
]
ncbi_publication_statuses = ['Unpublished', 'In Press', 'Published']
ncbi_submission_statuses = [
    'SUBMITTED', 'CREATED', 'QUEUED', 'PROCESSING', 
    'FAILED', 'PROCESSED', 'ERROR', 'WAITING',
    'DELETED', 'RETRIED', 'VALIDATED', 'EMAILED'
]
gisaid_cli_file = {
    "FLU": "fluCLI",
    "COV": "covCLI",
    "RSV": "rsvCLI"
}
# Aliases for SeqSender databases and mapping of SeqSender statuses to internal statuses.
SEQSENDER_DATABASE_ALIASES = {
    "GENBANK-FTP": "GENBANK",
    "GENBANK-TABLE2ASN": "GENBANK",
}
# Mapping of SeqSender statuses to internal statuses.
SEQSENDER_STATUS_MAP = {
    "CREATED": "CREATED",
    "SUBMITTED": "SUBMITTED",
    "VALIDATED": "SUBMITTED",
    "QUEUED": "PROCESSING",
    "PROCESSING": "PROCESSING",
    "WAITING": "PROCESSING",
    "RETRIED": "PROCESSING",
    "FAILED": "FAILED",
    "ERROR": "FAILED",
    "DELETED": "FAILED",
    "PROCESSED": "COMPLETED",
    "EMAILED": "COMPLETED",
}
# ---------------------------------------------------------------------------
# STANDARDIZED FILENAMES FOR SEQSENDER FILES
# ---------------------------------------------------------------------------
SEQSENDER_IMAGE = "ghcr.io/cdcgov/seqsender:v1.5.1"
CONFIG_FILENAME = "config.yaml"
METADATA_FILENAME = "metadata.csv"
FASTA_FILENAME = "sequence.fasta"
GFF_FILENAME = "annotation.gff"
TABLE2ASN_FILENAME = "table2asn"
SUBMISSION_LOG_FILENAME = "submission_log.csv"
SUBMISSION_STATUS_REPORT_FILENAME = "submission_status_report.csv"
CONFIG_TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "..", "seqsender", "config_template.yaml")
METADATA_TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "..", "seqsender", "metadata_template.csv")

# ---------------------------------------------------------------------------
# SUBMITTER SCHEMA
# ---------------------------------------------------------------------------
submitter_pa_schema = pa.DataFrameSchema(
    columns={
        "submitter_name": _required_str(description="Name of the submitter."),
        "submitter_password": _required_str(description="Password for the submitter."),
        "submission_portal":  _required_enum_col(submission_portals, description="Type of submission portal used by the submitter."),
        "ncbi_spuid_namespace":  _nullable_str(description="Organization SPUID namespace for NCBI submission."),
        "gisaid_client_id":      _nullable_str(description="Client ID for GISAID submission."),
        "ncbi_org_role":         _nullable_str(description="Organization role for NCBI submission."),
        "ncbi_org_type":         _nullable_str(description="Organization type for NCBI submission."),
        "ncbi_org_name":         _nullable_str(description="Organization name for NCBI submission."),
        "ncbi_org_affiliation":  _nullable_str(description="Organization affiliation for NCBI submission."),
        "ncbi_org_division":     _nullable_str(description="Organization division for NCBI submission."),
        "ncbi_addr_street":      _nullable_str(description="Organization street address for NCBI submission."),
        "ncbi_addr_city":        _nullable_str(description="Organization city for NCBI submission."),
        "ncbi_addr_state":       _nullable_str(description="Organization state for NCBI submission."),
        "ncbi_addr_postal_code": _nullable_str(description="Organization postal code for NCBI submission."),
        "ncbi_addr_country":     _nullable_str(description="Organization country for NCBI submission."),
        "ncbi_addr_email":       _nullable_str(description="Organization email for NCBI submission."),
        "ncbi_addr_phone":       _nullable_str(description="Organization phone for NCBI submission."),
        "ncbi_submitter_email":      _nullable_str(description="Submitter email for NCBI submission."),
        "ncbi_submitter_alt_email":  _nullable_str(description="Submitter alternate email for NCBI submission."),
        "ncbi_submitter_first_name": _nullable_str(description="Submitter first name for NCBI submission."),
        "ncbi_submitter_last_name":  _nullable_str(description="Submitter last name for NCBI submission."),
    },
    name="submitter",
)
# ---------------------------------------------------------------------------
submitter_db_schema = pa.DataFrameSchema(
    columns={
        "submitter_id": pa.Column(pl.Int64, nullable=False, required=False, description="Primary key for the submitter table in database."),
        **{col: pa.Column(submitter_pa_schema.columns[col].dtype.type, nullable=submitter_pa_schema.columns[col].nullable, required=submitter_pa_schema.columns[col].required) for col in submitter_pa_schema.columns}
    },
    name="submitter",
)

# ---------------------------------------------------------------------------
# SUBMISSION SCHEMA
# ---------------------------------------------------------------------------
submission_pa_schema = pa.DataFrameSchema(
    columns={
        "submission_name": _required_str(
            description="Name of the submission."
        ),
        "organism": _required_enum_col(
            organisms, description="Type of organism."
        ),
        "submission_portal": _required_enum_col(
            submission_portals, 
            description="Submission portal used by the submitter."
        ),
        "database": _required_enum_col(
            database_targets, 
            description="Target database."
        ),
        "database_status": _required_enum_col(
            database_statuses,
            description="Status of the target database."
        ),
        "submission_type": _required_enum_col(
            submission_types, 
            description="Type of submission: Test or Production."
        ),
        "gff_file": pa.Column(
            pl.Boolean, nullable=False, required=True,
            description="Whether to include GFF file in the submission."
        ),
        "table2asn": pa.Column(
            pl.Boolean, nullable=False, required=True,
            description="Whether to run table2asn."
        ),
        "submitter_name": _required_str(
            description="Name of the submitter."
        ),
        "ncbi_publication_title": _nullable_str(
            description="Publication title for NCBI submission."
        ),
        "ncbi_publication_status": _nullable_enum_col(
            ncbi_publication_statuses, 
            description="Publication status for NCBI submission."
        ),
        "ncbi_release_date": _nullable_str(
            description="Release date for NCBI submission."
        ),
        "number_of_samples": pa.Column(
            pl.Int64, nullable=False, required=False,
            description="Number of samples in the submission's metadata/FASTA."
        ),
        "ncbi_submission_id": _nullable_str(
            required=False,
            description="Accession/ID returned by the submission portal."
        ),
        "ncbi_submission_status": _nullable_enum_col(
            ncbi_submission_statuses,
            required=False,
            description="Raw status reported by the submission portal."
        ),
        "submission_status": _nullable_enum_col(
            submission_statuses,
            description="Status of the submission."
        ),
        "comments": _nullable_str(
            required=False,
            description="Additional comments for the submission."
        ),
        "date_submitted": _nullable_str(
            required=False,
            description="Date the submission was created."
        ),
        "date_updated": _nullable_str(
            required=False,
            description="Date the submission was last updated."
        ),
    },
    name="submission",
)
# ---------------------------------------------------------------------------
submission_db_schema = pa.DataFrameSchema(
    columns={
        "submission_id": pa.Column(pl.Int64, nullable=False, required=False, description="Primary key for the submission table in database."),
        **{col: pa.Column(submission_pa_schema.columns[col].dtype.type, nullable=submission_pa_schema.columns[col].nullable, required=submission_pa_schema.columns[col].required) for col in submission_pa_schema.columns}
    },
    name="submission",
)

# ---------------------------------------------------------------------------
# SEQSENDER SUBMISSION LOG SCHEMA
# ---------------------------------------------------------------------------
submission_log_pa_schema = pa.DataFrameSchema(
    columns={
        "Submission_Name": _required_str(
            description="Name of the SeqSender submission."
        ),
        "Organism": _required_enum_col(
            organisms,
            description="Organism associated with the submission."
        ),
        "Database": _required_enum_col(
            ["BIOSAMPLE", "SRA", "GENBANK-FTP", "GENBANK-TABLE2ASN", "GISAID"],
            description="SeqSender database target and submission method."
        ),
        "Submission_Type": _required_enum_col(
            submission_types,
            description="Submission environment used by SeqSender."
        ),
        "Submission_Date": _required_str(
            description="Date the submission was created."
        ),
        "Submission_ID": _required_str(
            description="Identifier assigned to the submission."
        ),
        "Submission_Status": _required_enum_col(
            ncbi_submission_statuses,
            description="Raw status reported by SeqSender."
        ),
        "Submission_Directory": _required_str(
            description="Directory containing the generated submission files."
        ),
        "Config_File": _required_str(
            description="Configuration file used for the submission."
        ),
        "Update_Date": _required_str(
            description="Date the submission log row was last updated."
        ),
    },
    name="submission_log",
)

# ---------------------------------------------------------------------------
# SEQSENDER SUBMISSION STATUS REPORT SCHEMA FOR BIOSAMPLE
# ---------------------------------------------------------------------------
submission_status_report_pa_schema = pa.DataFrameSchema(
    columns={
        "bs-sample_name": _nullable_str(
            description="BioSample sample name from the submitted metadata.",
            required=False,
        ),
        "biosample_status": _nullable_str(
            description="Status reported by BioSample for the sample.",
            required=False,
        ),
        "biosample_accession": _nullable_str(
            description="BioSample accession assigned to the sample.",
            required=False,
        ),
        "biosample_message": _nullable_str(
            description="Message returned by BioSample for the sample.",
            required=False,
        ),
        "sra-sample_name": _nullable_str(
            description="SRA sample name from the submitted metadata.",
            required=False,
        ),
        "sra_status": _nullable_str(
            description="Status reported by SRA for the sample.",
            required=False,
        ),
        "sra_accession": _nullable_str(
            description="SRA accession assigned to the sample.",
            required=False,
        ),
        "sra_message": _nullable_str(
            description="Message returned by SRA for the sample.",
            required=False,
        ),
        "gb-sample_name": _nullable_str(
            description="GenBank sample name from the submitted metadata.",
            required=False,
        ),
        "genbank_status": _nullable_str(
            description="Status reported by GenBank for the sample.",
            required=False,
        ),
        "genbank_accession": _nullable_str(
            description="GenBank accession assigned to the sample.",
            required=False,
        ),
        "genbank_message": _nullable_str(
            description="Message returned by GenBank for the sample.",
            required=False,
        ),
    },
    name="submission_status_report",
)

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

# Standardized on-disk filenames for the custom config uploads (custom_primers/
# custom_irma_config/custom_qc_settings are now plain booleans in the DB -- the
# actual file, when present, always lives under the run directory with these names.
CUSTOM_PRIMER_CONFIG_FILENAME = "custom_primers.fasta"
CUSTOM_IRMA_CONFIG_FILENAME = "custom_irma_config.sh"
CUSTOM_QC_SETTINGS_FILENAME = "custom_qc_settings.yaml"

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
# VARIANTS OF INTEREST
# ---------------------------------------------------------------------------

variants_of_interest = pa.DataFrameSchema(
    columns={
        "subtype": _required_str(),
        "protein": _required_str(),
        "position": pa.Column(pl.Int64, nullable=False, required=True),
        "mutation_of_interest": _required_str(),
        "phenotypic_consensus": _required_str(),
    },
    name="variants_of_interest"
)

# ---------------------------------------------------------------------------
# ASSEMBLY SCHEMA
# ---------------------------------------------------------------------------
assembly_pa_schema = pa.DataFrameSchema(
    columns={
        "run_name": _required_str(description="Name of the sequencing run."),
        "experiment_type": _required_str(description=f"Type of the experiment. Options: {experiment_types}"),
        "sc2_primer": _nullable_enum_col(
            sc2_primers, required=False,
            checks=pa.Check(
                lambda data: data.lazyframe.select(
                    (~(pl.col("experiment_type").str.contains("SC2") & pl.col("experiment_type").str.contains("Illumina")) | pl.col("sc2_primer").is_not_null())
                    .alias("sc2_primer_required_for_sc2_illumina")
                ),
                error="sc2_primer is required when experiment_type contains 'SC2' and 'Illumina'.",
            ),
            description=f"Provide a SC2 primer if experiment type is SC2-Illumina. Options: {sc2_primers}"
        ),
        "rsv_primer": _nullable_enum_col(
            rsv_primers, required=False,
            checks=pa.Check(
                lambda data: data.lazyframe.select(
                    (~(pl.col("experiment_type").str.contains("RSV") & pl.col("experiment_type").str.contains("Illumina")) | pl.col("rsv_primer").is_not_null())
                    .alias("rsv_primer_required_for_rsv_illumina")
                ),
                error="rsv_primer is required when experiment_type contains 'RSV' and 'Illumina'.",
            ),
            description=f"Provide a RSV primer if experiment type is RSV-Illumina. Options: {rsv_primers}"
        ),
        "subsample_reads": pa.Column(
            pl.Int64, nullable=False, required=True,
            checks=pa.Check.ge(0),
            description="Number of reads to subsample for MIRA assembly."
        ),
        "custom_primers": pa.Column(
            pl.Boolean, nullable=False, required=True,
            description="Whether to use a custom primer file for assembly. If true, primer_kmer_len and primer_restrict_window must also be specified."
        ),
        "primer_kmer_len": pa.Column(
            pl.Int64, nullable=True, required=False, 
            checks=[
                pa.Check.ge(0),
                pa.Check(
                    lambda data: data.lazyframe.select(
                        (pl.col("primer_kmer_len").is_null() | (pl.col("primer_kmer_len") == 0) | pl.col("custom_primers"))
                        .alias("primer_kmer_len_requires_custom_primers")
                    ),
                    error="custom_primers must be true when primer_kmer_len is specified.",
                ),
            ],
            description="K-mer length for primer trimming. custom_primers must be true if primer_kmer_len is specified."
        ),
        "primer_restrict_window": pa.Column(
            pl.Int64, nullable=True, required=False, 
            checks=[
                pa.Check.ge(0),
                pa.Check(
                    lambda data: data.lazyframe.select(
                        (pl.col("primer_restrict_window").is_null() | (pl.col("primer_restrict_window") == 0) | pl.col("custom_primers"))
                        .alias("primer_restrict_window_requires_custom_primers")
                    ),
                    error="custom_primers must be true when primer_restrict_window is specified.",
                ),
            ],
            description="Window size for primer trimming. custom_primers must be true if primer_restrict_window is specified."
        ),
        "irma_module": _nullable_enum_col(
            irma_modules, required=False,
            checks=pa.Check(
                lambda data: data.lazyframe.select(
                    (pl.col("irma_module").is_null() | (pl.col("irma_module") == "") | pl.col("experiment_type").str.contains("Illumina"))
                    .alias("irma_module_only_for_illumina")
                ),
                error="irma_module can only be set when experiment_type contains 'Illumina'.",
            ),
            description=f"Specify the IRMA module to use for assembly (Illumina experiment types only). Options: {irma_modules}"
        ),
        "custom_irma_config": pa.Column(
            pl.Boolean, nullable=False, required=True,
            description="Whether to use a custom IRMA configuration file for assembly."
        ),
        "custom_qc_settings": pa.Column(
            pl.Boolean, nullable=False, required=True,
            description="Whether to use custom QC settings for assembly."
        ),
        "parquet_files": pa.Column(
            pl.Boolean, nullable=False, required=True,
            description="Whether to generate parquet files."
        ),
        "nextclade": pa.Column(
            pl.Boolean, nullable=False, required=True,
            description="Whether to run Nextclade analysis."
        ),
        "keep_workdir": pa.Column(
            pl.Boolean, nullable=False, required=False,
            description="Whether to preserve the Nextflow work directory after a successful run."
        ),
        "assembly_status": _required_enum_col(
            assembly_status, nullable=False, required=False,
            description=f"Status of the assembly. Options: {assembly_status}"
        ),
    },
    name="assembly",
)
# ---------------------------------------------------------------------------
assembly_db_schema = pa.DataFrameSchema(
    columns={
        "assembly_id": pa.Column(pl.Int64, nullable=False, required=False, description="Foreign key linking to the assembly table in database."),
        **{col: pa.Column(assembly_pa_schema.columns[col].dtype.type, nullable=assembly_pa_schema.columns[col].nullable, required=assembly_pa_schema.columns[col].required) for col in assembly_pa_schema.columns}
    },
    name="assembly",
)

# ---------------------------------------------------------------------------
# ONT SAMPLESHEET SCHEMA
# ---------------------------------------------------------------------------
ont_samplesheet_pa_schema = pa.DataFrameSchema(
    columns={
        "barcode": _required_str(description="ONT barcode identifier (e.g. barcode01)."),
        "sample_id": _required_str(description="Sample identifier."),
        "sample_type": _required_enum_col(
            sample_types, nullable=False, required=True,
            description=f"Type of the sample. Options: {sample_types}"
        ),
        "single_end": pa.Column(
            pl.Boolean, nullable=False, required=True, 
            description="Whether the sequencing is single-end. Default is True for ONT samples."
        ),
        "fastq": _required_str(description="Path to the FASTQ file for the sample."),
        "status": _required_enum_col(
            sample_status, nullable=False, required=True,
            description=f"Status of the sample. Options: {sample_status}"
        ),
    },
    name="ont_samplesheet",
)
# ---------------------------------------------------------------------------
ont_samplesheet_db_schema = pa.DataFrameSchema(
    columns={
        "assembly_id": pa.Column(pl.Int64, nullable=False, required=False, description="Foreign key linking to the assembly table in database."),
        **{col: pa.Column(ont_samplesheet_pa_schema.columns[col].dtype.type, nullable=ont_samplesheet_pa_schema.columns[col].nullable, required=ont_samplesheet_pa_schema.columns[col].required) for col in ont_samplesheet_pa_schema.columns}
    },
    name="ont_samplesheet",
)

# ---------------------------------------------------------------------------
# ILLUMINA SAMPLESHEET SCHEMA
# ---------------------------------------------------------------------------
illumina_samplesheet_pa_schema = pa.DataFrameSchema(
    columns={
        "sample_id": _required_str(description="Sample identifier."),
        "sample_type": _required_enum_col(
            sample_types, nullable=False, required=True,
            description=f"Type of the sample. Options: {sample_types}"
        ),
        "single_end": pa.Column(
            pl.Boolean, nullable=False, required=True,
            description="Whether the sequencing is single-end. Default is False for Illumina samples."
        ),
        "fastq_1": _required_str(description="Path to the first FASTQ file for the sample."),
        "fastq_2": _nullable_str(description="Path to the second FASTQ file for the sample (if paired-end)."),
        "status": _required_enum_col(
            sample_status, nullable=False, required=True,
            description=f"Status of the sample. Options: {sample_status}"
        ),
    },
    name="illumina_samplesheet",
)
# ---------------------------------------------------------------------------
illumina_samplesheet_db_schema = pa.DataFrameSchema(
    columns={
        "assembly_id": pa.Column(pl.Int64, nullable=False, required=False, description="Foreign key linking to the assembly table in database."),
        **{col: pa.Column(illumina_samplesheet_pa_schema.columns[col].dtype.type, nullable=illumina_samplesheet_pa_schema.columns[col].nullable, required=illumina_samplesheet_pa_schema.columns[col].required) for col in illumina_samplesheet_pa_schema.columns}
    },
    name="illumina_samplesheet",
)
