# Import future annotations for Pydantic models
from typing import List, Optional, Literal, Dict, Any

# Import context manager for managing application lifespan
from contextlib import asynccontextmanager

# Import FastAPI and related packages
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse

# Import general python packages
import os
import io
import re
import json
import shutil
import tempfile
import zipfile
import requests
from datetime import datetime

# Import background task handling from Starlette
from starlette.background import BackgroundTask

# Import asyncio for running blocking operations in a thread
import asyncio

# Import polars for dataframe operations
import polars as pl

# Import schema
from .schema import (
    RunRequest,
    ListRunResponse,
    RunStatusRequest,
    TaskLogRequest,
    AssemblyRequest,
    DownloadFastaRequest,
    DeleteSampleRequest,
    RenameRunRequest,
    CopyRunRequest,
    SubmissionRequest,
    DeleteSubmissionRequest,
    CopySubmissionRequest,
    CreateSubmissionRequest,
    UpdateSubmissionCommentsRequest,
    UpdateSubmissionStatusReportMessagesRequest,
    StatusUpdateCronRequest,
    ListSubmissionResponse,
    ListSubmitterResponse,
    SubmitterInfo,
    DeleteSubmitterRequest,
)

# Import schema validation
from .schema_validator import (
    _DEFAULT_SEQSENDER_STORAGE_PATH,
    _DEFAULT_MIRA_STORAGE_PATH,
    _MIRA_NF_VERSION_URL,
    _MIRA_VERSION_URL,
    _MIRA_NF_IMAGE,
    _REACT_PORT,
    validate_tbl,
    organisms,
    submission_portals,
    database_targets,
    submission_types,
    experiment_types,
    assembly_pa_schema,
    ont_samplesheet_pa_schema,
    illumina_samplesheet_pa_schema, 
    CONFIG_TEMPLATE_PATH,
    CONFIG_FILENAME,
    METADATA_FILENAME,
    FASTA_FILENAME,
    GFF_FILENAME,
    TABLE2ASN_FILENAME,
    CUSTOM_PRIMER_CONFIG_FILENAME,
    CUSTOM_IRMA_CONFIG_FILENAME,
    CUSTOM_QC_SETTINGS_FILENAME,
)

# Import MIRA handler 
from .mira_handler import (
    create_mira_run,
    retrieve_run,
    delete_sample_from_run,
    rename_mira_run,
    delete_mira_run,
    copy_mira_run,
    run_mira_docker,
    create_mira_dag,
    retrieve_task_log,
    check_mira_status,
    cancel_mira_run,
    retrieve_barcode_assignment,
    retrieve_qc_statement,
    retrieve_quality_control_decisions,
    retrieve_mira_summary,
    retrieve_coverage_table,
    retrieve_coverage_heatmap,
    retrieve_sample_coverage_list,
    retrieve_sample_coverage_sankeyfig,
    retrieve_sample_coverage_plot,
    retrieve_sample_coverage_linearfig,
    retrieve_variants,
    retrieve_minor_snvs,
    retrieve_indels,
    retrieve_failed_amino_acid_consensus,
    retrieve_passed_amino_acid_consensus,
    retrieve_failed_amended_consensus,
    retrieve_passed_amended_consensus,
    retrieve_nextclade_aligned_fasta,
    validate_samplesheet_and_fastqs_in_storage,
    validate_custom_configs_in_storage,
)

# Import SeqSender handler
from .seqsender_handler import (
    _get_seqsender_version,
    retrieve_submission,
    create_seqsender_submission,
    delete_seqsender_submission,
    copy_seqsender_submission,
    update_seqsender_submission_comments,
    update_seqsender_submission_status_report_messages,
    save_submitter,
    delete_submitter,
    submit_ncbi_submission,
    prep_seqsender_submission,
    check_seqsender_submission,
    load_submission_status,
    retrieve_seqsender_config,
    retrieve_seqsender_metadata,
    retrieve_seqsender_metadata_template,
    retrieve_seqsender_fasta,
    retrieve_seqsender_raw_reads,
    validate_seqsender_uploaded_files,
    retrieve_seqsender_gff,
    retrieve_seqsender_table2asn,
    retrieve_seqsender_gisaid_cli,
    retrieve_seqsender_submission_log,
    retrieve_seqsender_status_report,
    retrieve_seqsender_process_status,
)

# Import sqlite handler for database operations
from .sqlite_handler import (
    lookup_tbl_in_database,
)

# Import shared logger (INFO/DEBUG -> stdout, WARNING/ERROR/CRITICAL -> stderr)
from .logging_config import logger

from .status_scheduler import (
    delete_status_update_schedule,
    get_status_update_schedule,
    save_status_update_schedule,
    start_status_update_scheduler,
    stop_status_update_scheduler,
    wake_status_update_scheduler,
)

# Define the lifespan context manager for the FastAPI app, 
# which starts and stops the status update scheduler.
@asynccontextmanager
async def lifespan(_: FastAPI):
    start_status_update_scheduler()
    try:
        yield
    finally:
        await stop_status_update_scheduler()


# FastAPI application instance
app = FastAPI(title = "MIRA Backend", lifespan=lifespan)

# Compress responses >= 1 KB with gzip (reduces large JSON payloads 5-10x)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Define React base URL and internal base URL for the app
_REACT_BASE_URL = f"http://localhost:{_REACT_PORT}"
_REACT_INTERNAL_BASE_URL = f"http://127.0.0.1:{_REACT_PORT}"

# CORS for your Vite dev server + Nextclade Web (fetches input-fasta directly from the browser)
# Also accept the 127.0.0.1 form of the same host:port, since some dev setups (e.g. remote
# port-forwarding) rewrite "localhost" to "127.0.0.1" in the browser's Origin header.
app.add_middleware(
    CORSMiddleware,
    allow_origins = [
        _REACT_BASE_URL,
        _REACT_INTERNAL_BASE_URL,
        "https://clades.nextstrain.org",
        "https://nextclade.org",
    ],
    allow_credentials = True,
    allow_methods = ["*"],
    allow_headers = ["*"],
)

# ---------------------------------------------------------------------------
# Global exception logging
# ---------------------------------------------------------------------------
# Every route below catches its own exceptions and re-raises as HTTPException(detail=str(err)),
# which discards the traceback on the wire. Python's implicit exception chaining still attaches
# the original exception (with its traceback) to `__context__`, so recover and log it here —
# this makes 500s fully diagnosable from the stderr stream without touching every route.
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code >= 500:
        original = exc.__context__ or exc
        logger.error(
            "%s %s -> %s %s", request.method, request.url.path, exc.status_code, exc.detail,
            exc_info=(type(original), original, original.__traceback__),
        )
    elif exc.status_code >= 400:
        logger.warning("%s %s -> %s %s", request.method, request.url.path, exc.status_code, exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

# Catch anything that escapes a route's own try/except (e.g. middleware/dependency bugs)
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("%s %s -> unhandled exception", request.method, request.url.path, exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})

##############################################
# 
# HELPERS FUNCTIONS
# 
##############################################

# ---------- Helper: parse uploaded JSON/CSV/EXCEL files → Polars DataFrame ----------
async def _parse_upload_to_df(file: UploadFile) -> pl.DataFrame:
    """Parse a JSON / CSV / Excel upload into a Polars DataFrame."""
    content = await file.read()
    name = (file.filename or "").lower()
    if name.endswith(".json"):
        return pl.DataFrame(json.loads(content))
    elif name.endswith(".csv"):
        return pl.read_csv(io.BytesIO(content))
    elif name.endswith((".xlsx", ".xls")):
        return pl.read_excel(io.BytesIO(content))
    else:
        raise ValueError(f"Unsupported file type '{file.filename}'. Accepted: .json, .csv, .xlsx, .xls")
    
# ---------- Helper: upload fastq files to MIRA storage location ----------
def upload_fastq_files_to_storage(
    run_name: str,  
    experiment_type: str,
    fastq_files: List[UploadFile],
) -> Dict[str, Any]:

    # Retrieve assembly table from database
    db_assembly_tbl = lookup_tbl_in_database(
        db_tbl_name = ["assembly"],
        return_var = ["*"],
        filter_coln_var = ["run_name", "experiment_type"],
        filter_coln_val = {"run_name": [run_name], "experiment_type": [experiment_type]},
        filter_var_by = ["AND"]
    )

    # Make sure db_assembly_tbl is not empty
    if db_assembly_tbl.shape[0] == 0:
        raise ValueError(f"No assembly found for run_name '{run_name}' and experiment_type '{experiment_type}'.")

    # Extract assembly information from assembly_tbl
    assembly_id = db_assembly_tbl.select("assembly_id").to_series()[0]    

    # Extract pathogen and instrument type from experiment_type
    pathogen =experiment_type.split("-")[0]
    instrument =experiment_type.split("-")[-1]

    # Get samplesheet table from database based on assembly_id and experiment_type
    if "ONT" in experiment_type.upper():
        db_samplesheet_tbl = lookup_tbl_in_database(
            db_tbl_name = ["ont_samplesheet"],
            return_var = ["*"],
            filter_coln_var = ["assembly_id"],
            filter_coln_val = {"assembly_id": [assembly_id]},
            filter_var_by = ["AND"]
        )
    elif "ILLUMINA" in experiment_type.upper():
        db_samplesheet_tbl = lookup_tbl_in_database(
            db_tbl_name = ["illumina_samplesheet"],
            return_var = ["*"],
            filter_coln_var = ["assembly_id"],
            filter_coln_val = {"assembly_id": [assembly_id]},
            filter_var_by = ["AND"]
        )

    # Filter fastq_files to only include files that exist and have the correct extension
    fastq_files = [f for f in fastq_files if re.search(r"\.(fastq|fq)(\.gz)?$", (f.filename or "").lower())]

    # Create a placeholder list to store the paths of successfully saved files
    saved: List[str] = []

    # Extract sample_ids from db_samplesheet_tbl
    for i in range(db_samplesheet_tbl.shape[0]):
        row = db_samplesheet_tbl.row(i, named=True)
        if "ONT" in instrument.upper():
            sample_id = row["barcode"]
            sample_fastq_files = [row["fastq"]]
            storage_dir = os.path.realpath(os.path.join(_DEFAULT_MIRA_STORAGE_PATH, pathogen, instrument, run_name, "fastq_pass", sample_id))
        elif "ILLUMINA" in instrument.upper():
            sample_id = row["sample_id"]
            sample_fastq_files = [row["fastq_1"], row["fastq_2"]]
            storage_dir = os.path.realpath(os.path.join(_DEFAULT_MIRA_STORAGE_PATH, pathogen, instrument, run_name, "fastqs"))
        # Create the storage directory if it doesn't exist
        os.makedirs(storage_dir, exist_ok=True)        
        # Find UploadFile objects whose filename matches the expected sample fastq files
        matching_uploads = [f for f in fastq_files if (f.filename or "").lower().replace(" ", "_") in [sf.lower().replace(" ", "_") for sf in sample_fastq_files]]
        # Write each matching UploadFile stream directly to the storage location
        for upload_file in matching_uploads:
            dest_file_path = os.path.join(storage_dir, upload_file.filename)
            upload_file.file.seek(0)
            with open(dest_file_path, "wb") as buf:
                shutil.copyfileobj(upload_file.file, buf)
            saved.append(upload_file.filename)
            
    # Return the list of successfully saved files and their count
    return {
        "message": "fastq files have been uploaded successfully.", 
        "saved": saved, 
        "count": len(saved)
    }

# ---------- Helper: parse a dotted version string into a comparable tuple of ints ----------
def _version_tuple(version: str) -> tuple:
    return tuple(int(part) for part in re.findall(r"\d+", version))


##############################################
# 
# MIRA HEALTH SECTION
# 
##############################################


# ---------- Health Check ----------
@app.get("/health", tags=["Health"], summary="Health check", response_model=Dict[str, Any])
def health():
    try:
        resp = requests.get(_REACT_BASE_URL, timeout=2)
        react_reachable = resp.status_code < 500
        if not react_reachable:
            logger.error("Health check: REACT_BASE_URL '%s' returned status %s.", _REACT_BASE_URL, resp.status_code)
    except requests.RequestException as err:
        react_reachable = False
        logger.error("Health check: REACT_BASE_URL '%s' is unreachable: %s", _REACT_BASE_URL, err)
    return {"ok": True, "react_base_url": _REACT_BASE_URL, "react_reachable": react_reachable}


##############################################
# 
# MIRA UTILS SECTION
# 
##############################################


# --------- Get MIRA version ----------
@app.get("/version", response_model=Dict[str, str], summary="Get MIRA version", tags=["MIRA Utils"])
async def check_mira_version():
    # Get current version from Docker image tag without the v
    current_mira_nf_version = re.findall(r"[^:]+$", _MIRA_NF_IMAGE)[0].lstrip("v")
    # Get available version on Github — network errors (e.g. GitHub unreachable) shouldn't crash this endpoint
    try:
        github_mira_nf_version = requests.get(_MIRA_NF_VERSION_URL, timeout=5)
    except requests.RequestException as err:
        logger.error("Failed to check MIRA-NF version from GitHub: %s", err)
        github_mira_nf_version = None
    if github_mira_nf_version is not None and github_mira_nf_version.status_code == 200:
        version_match = re.search(r"Version:\s*(\S+)", github_mira_nf_version.text)
        available_mira_nf_version = version_match.group(1) if version_match else "0.0.0"
        # Check if current version is lesser than available version online
        if _version_tuple(current_mira_nf_version) < _version_tuple(available_mira_nf_version):
            mira_nf_status = "out-of-date"
        else:
            mira_nf_status = "up-to-date"
    else:
        available_mira_nf_version = "unknown"
        mira_nf_status = "unknown"

    # Read in the DESCRIPTION file from the MIRA repo to get the current version of MIRA
    # (kept inside backend/ so it is included in the Docker build context / dev bind mount)
    current_mira_version_file = os.path.realpath(f"{os.path.dirname(os.path.realpath(__file__))}/../../DESCRIPTION")
    current_mira_version = "unknown"
    with open(current_mira_version_file, "r") as f:
        current_mira_version = re.search(r"Version:\s*(\S+)", f.read()).group(1)
    # Get available version on Github — network errors (e.g. GitHub unreachable) shouldn't crash this endpoint
    try:
        github_mira_version = requests.get(_MIRA_VERSION_URL, timeout=5)
    except requests.RequestException as err:
        logger.error("Failed to check MIRA version from GitHub: %s", err)
        github_mira_version = None
    if github_mira_version is not None and github_mira_version.status_code == 200:
        version_match = re.search(r"Version:\s*(\S+)", github_mira_version.text)
        available_mira_version = version_match.group(1) if version_match else "0.0.0"
        # Check if current version is lesser than available version online
        if current_mira_version != "unknown" and _version_tuple(current_mira_version) < _version_tuple(available_mira_version):
            mira_status = "out-of-date"
        else:
            mira_status = "up-to-date"
    else:
        available_mira_version = "unknown"
        mira_status = "unknown"

    # Overall status is out-of-date if either MIRA or MIRA-NF is out-of-date
    status = "out-of-date" if "out-of-date" in (mira_status, mira_nf_status) else (
        "unknown" if "unknown" in (mira_status, mira_nf_status) else "up-to-date"
    )

    # Return the current version, available version, and status for MIRA and MIRA-NF
    check_result = {
        "current_mira_nf_version": f"v{current_mira_nf_version}",
        "available_mira_nf_version": f"v{available_mira_nf_version}",
        "mira_nf_status": mira_nf_status,
        "current_mira_version": f"v{current_mira_version}",
        "available_mira_version": f"v{available_mira_version}",
        "mira_status": mira_status,
        "status": status
    }
    return check_result


# ---------- List all runs ----------
@app.get("/list/runs", response_model=ListRunResponse, summary="List all assembly runs", tags=["MIRA Utils"])
async def get_runs():
    """
    Return a list of assembly runs in database.
    """
    # Query for all assembly runs
    try:
        db_assembly_tbl = lookup_tbl_in_database(
            db_tbl_name = ["assembly"],
            return_var  = ["*"]
        )
        # If no runs found, return an empty list
        if db_assembly_tbl.shape[0] == 0:
            return {"run_info": []}
        else:
            return {"run_info": db_assembly_tbl.to_dicts()}
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
    

# ---------- Dashboard Summary Counts ----------
@app.get("/stats/summary", response_model=Dict[str, int], summary="Dashboard summary counts (submitted sequences)", tags=["MIRA Utils"])
async def get_stats_summary():
    """
    Return real counts for the home dashboard: sequences submitted to NCBI
    (GenBank + SRA) and to GISAID, derived from assigned accessions in the
    submission-status tables.
    """
    def _count_assigned(table: str, accession_col: str) -> int:
        # Count distinct rows that have a non-null accession assigned; treat a
        # missing/empty table as zero so the dashboard still renders.
        try:
            df = lookup_tbl_in_database(db_tbl_name=[table], return_var=[accession_col])
        except Exception:
            return 0
        if df.is_empty():
            return 0
        return df.filter(pl.col(accession_col).is_not_null()).height

    try:
        genbank = await asyncio.to_thread(_count_assigned, "gb_submission_status", "genbank_accession")
        sra = await asyncio.to_thread(_count_assigned, "sra_submission_status", "sra_accession")
        gisaid = await asyncio.to_thread(_count_assigned, "gs_submission_status", "gisaid_accession_epi_isl_id")
        return {
            "ncbi_sequences": genbank + sra,
            "gisaid_sequences": gisaid,
        }
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
    

# ---------- Retrieve Specific Run Information ----------
@app.get("/retrieve/run", response_model=Optional[Dict[str, Any]], summary="Retrieve a run information", tags=["MIRA Utils"])
async def get_run_info(req: RunRequest = Depends()):
    """
    Retrieve assembly information, samplesheet, QC decisions, coverage, variants, etc., for a given sequencing run.
    """
    try:
        result = await asyncio.to_thread(
            retrieve_run, 
            run_name = req.run_name, 
            experiment_type = req.experiment_type
        )
        return result
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
    

##############################################
# 
# MIRA WORKFLOWS SECTION
# 
##############################################    


# ---------- Create a MIRA run (with file uploads) ----------
@app.post(
    "/create/run/upload",
    response_model=Dict[str, Any],
    summary="Create a MIRA run (with File Uploads, Accepted Formats: JSON/CSV/Excel for samplesheet; .fastq/.fastq.gz/.fq/.fq.gz for raw reads)",
    tags=["MIRA Workflows"],
    openapi_extra={
        "requestBody": {
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["run_name", "experiment_type", "assembly_file", "samplesheet_file"],
                        "properties": {
                            "run_name":         {"type": "string", "default": "ont_test_run", "description": "Name of the sequencing run"},
                            "experiment_type":  {"type": "string", "enum": experiment_types, "default": "Flu-ONT", "description": "Type of sequencing experiments"},
                            "assembly_file":    {"type": "string", "format": "binary", "description": "Assembly file as JSON file"},
                            "samplesheet_file": {"type": "string", "format": "binary", "description": "Samplesheet file as Excel or CSV file"},
                            "fastq_files": {
                                "type": "array",
                                "items": {"type": "string", "format": "binary", "title": "another file"},
                                "description": "One or more .fastq/.fastq.gz/.fq/.fq.gz files — Select `Add string item` to add another import field for additional files.",
                            },
                        },
                    }
                }
            }
        }
    },
)
async def create_run_upload(
    run_name: str = Form("ont_test_run", description="Name of the sequencing run."),
    experiment_type: str = Form("Flu-ONT", description="Type of sequencing experiments."),
    assembly_file: UploadFile = File(..., description="Assembly file (JSON)."),
    samplesheet_file: UploadFile = File(..., description="Samplesheet file (Excel or CSV)."),
    fastq_files: List[UploadFile] = File(default=[], description="One or more .fastq/.fastq.gz/.fq/.fq.gz files to upload.")
):
    """
    Submit a MIRA assembly run via **file uploads**.
    Accepted formats: JSON / CSV / Excel for assembly and samplesheet; .fastq/.fastq.gz/.fq/.fq.gz for reads.
    """
    try:
        # ── Assembly ───────────────────────────────────────────────
        assembly_tbl = await _parse_upload_to_df(assembly_file)
        assembly_tbl = assembly_tbl.unique()
        assembly_tbl = validate_tbl(assembly_tbl, assembly_pa_schema, "assembly")
        # ── Samplesheet ───────────────────────────────────────────────
        samplesheet_tbl = await _parse_upload_to_df(samplesheet_file)
        samplesheet_tbl = samplesheet_tbl.unique()
        if "ONT" in experiment_type.upper():
            samplesheet_tbl = validate_tbl(samplesheet_tbl, ont_samplesheet_pa_schema, "ont_samplesheet")
        elif "ILLUMINA" in experiment_type.upper():
            samplesheet_tbl = validate_tbl(samplesheet_tbl, illumina_samplesheet_pa_schema, "illumina_samplesheet")
        # ── Store assembly and samplesheet to database ──────────────────────────────────────────────
        assembly_info = await asyncio.to_thread(
            create_mira_run,
            run_name = run_name,
            experiment_type = experiment_type,
            assembly_tbl = assembly_tbl,
            samplesheet_tbl = samplesheet_tbl,
        )
        # ── Upload Fastq files to storage location ───────────────────────────────────────────────
        fastq_info = await asyncio.to_thread(
            upload_fastq_files_to_storage,
            run_name = run_name,
            experiment_type = experiment_type,
            fastq_files = fastq_files
        )
        return {
            "status": "success",
            "message": "MIRA run has been created successfully.",
            "assembly_info": assembly_info,
            "fastq_info": fastq_info
        }
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
    

# ---------- Create a MIRA assembly run ----------
@app.post("/create/run", response_model=Dict[str, Any], summary="Create a MIRA run with appropriate samplesheet", tags=["MIRA Workflows"])
async def create_run(req: AssemblyRequest):
    """
    Create a MIRA run via a **JSON request body**.
    Use this option when all inputs are available as structured data.
    This endpoint works together with the `/upload/fastqs` endpoint to create a complete MIRA run."""
    try:
        # Create assembly table from request data and validate it
        assembly_tbl    = pl.DataFrame({
            "run_name":                 [req.run_name],
            "experiment_type":          [req.experiment_type],
            "subsample_reads":          [req.subsample_reads],
            "sc2_primer":               [req.sc2_primer],
            "rsv_primer":               [req.rsv_primer],
            "custom_primers":           [req.custom_primers],
            "primer_kmer_len":          [req.primer_kmer_len if req.custom_primers and req.primer_kmer_len > 0 else None],
            "primer_restrict_window":   [req.primer_restrict_window if req.custom_primers and req.primer_restrict_window > 0 else None],
            "irma_module":              [req.irma_module],
            "custom_irma_config":       [req.custom_irma_config],
            "custom_qc_settings":       [req.custom_qc_settings],
            "parquet_files":            [req.parquet_files],
            "nextclade":                [req.nextclade],
            "keep_workdir":             [req.keep_workdir],
            "assembly_status":          [req.assembly_status],
            "created_at":               [datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
        })
        # Log the request parameters for debugging and auditing purposes
        logger.info(
            "Create MIRA run:\n" +
            f"run_name='{req.run_name}'\n"
            f"experiment_type='{req.experiment_type}'\n"
            f"subsample_reads='{req.subsample_reads}'\n"
            f"sc2_primer='{req.sc2_primer}'\n"
            f"rsv_primer='{req.rsv_primer}'\n"
            f"custom_primers='{req.custom_primers}'\n"
            f"primer_kmer_len='{req.primer_kmer_len if req.custom_primers and req.primer_kmer_len > 0 else ''}'\n"
            f"primer_restrict_window='{req.primer_restrict_window if req.custom_primers and req.primer_restrict_window > 0 else ''}'\n"
            f"irma_module='{req.irma_module}'\n"
            f"custom_irma_config='{req.custom_irma_config}'\n"
            f"custom_qc_settings='{req.custom_qc_settings}'\n"
            f"parquet_files='{req.parquet_files}'\n"
            f"nextclade='{req.nextclade}'\n"
            f"keep_workdir='{req.keep_workdir}'\n"
            f"assembly_status='{req.assembly_status}'\n",
        )
        # Validate assembly table based on assembly schema
        assembly_tbl = validate_tbl(assembly_tbl, assembly_pa_schema, "assembly")
        # Validate samplesheet table based on experiment type
        if "ONT" in req.experiment_type.upper():
            samplesheet_tbl = pl.DataFrame([row.model_dump() for row in req.samplesheet]).unique()
            samplesheet_tbl = validate_tbl(samplesheet_tbl, ont_samplesheet_pa_schema, "ont_samplesheet")
        elif "ILLUMINA" in req.experiment_type.upper():
            samplesheet_tbl = pl.DataFrame([row.model_dump() for row in req.samplesheet]).unique()
            samplesheet_tbl = validate_tbl(samplesheet_tbl, illumina_samplesheet_pa_schema, "illumina_samplesheet")
        # Store assembly and samplesheet to database
        await asyncio.to_thread(
            create_mira_run,
            run_name = req.run_name,
            experiment_type = req.experiment_type,
            assembly_tbl = assembly_tbl,
            samplesheet_tbl = samplesheet_tbl
        )
        # Return results
        return{
            "status": "success",
            "message": "MIRA run has been created successfully."
        }
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))  
          

# ---------- Upload FASTQ files to storage ----------
@app.post(
    "/upload/fastqs", 
    response_model=Dict[str, Any], 
    summary="Upload FASTQ files to a specific MIRA run", 
    tags=["MIRA Workflows"],
    openapi_extra={
        "requestBody": {
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["run_name", "experiment_type", "fastq_files"],
                        "properties": {
                            "run_name":         {"type": "string", "default": "ont_test_run", "description": "Name of the sequencing run"},
                            "experiment_type":  {"type": "string", "enum": experiment_types, "default": "Flu-ONT", "description": "Type of sequencing experiments"},
                            "fastq_files": {
                                "type": "array",
                                "items": {"type": "string", "format": "binary", "title": "another file"},
                                "description": "One or more .fastq/.fastq.gz/.fq/.fq.gz files — Select `Add string item` to add another import field for additional files.",
                            },
                        },
                    }
                }
            }
        }
    },
)
async def upload_fastqs(
    run_name:        str                    = Form(..., description="Name of the sequencing run."),
    experiment_type: str                    = Form(..., description="Type of sequencing experiments."),
    fastq_files:     List[UploadFile]       = File(default=[], description="One or more .fastq/.fastq.gz/.fq/.fq.gz files to upload."),
):
    """
    Upload FASTQ files to a specific sequencing run.
    This endpoint is intended to be used after creating a MIRA run via the `/create/run` endpoint.
    """
    try:
        upload_result = await asyncio.to_thread(
            upload_fastq_files_to_storage,
            run_name = run_name,
            experiment_type = experiment_type,
            fastq_files = fastq_files
        )
        return upload_result
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))   
     

# Upload custom primger config file to storage location
@app.post("/upload/custom_primer_config", response_model=Dict[str, Any], summary="Upload a custom primer config file to storage location", tags=["MIRA Workflows"])
async def upload_custom_primer_config(
    run_name: str = Form("", description="Name of the sequencing run."),
    experiment_type: Literal[tuple(experiment_types)] = Form(..., description="Type of sequencing experiments."),
    custom_primer_config_file: UploadFile = File(..., description="Custom primers file to upload.")
):
    """
    Upload a custom primer config file to the storage location for a given sequencing run.
    """
    try:
        # Retrieve assembly table from database
        db_assembly_tbl = lookup_tbl_in_database(
            db_tbl_name = ["assembly"],
            return_var = ["*"],
            filter_coln_var = ["run_name", "experiment_type"],
            filter_coln_val = {"run_name": [run_name], "experiment_type": [experiment_type]},
            filter_var_by = ["AND"]
        )
        # Make sure db_assembly_tbl is not empty
        if db_assembly_tbl.shape[0] == 0:
            raise ValueError(f"No assembly found for run_name '{run_name}' and experiment_type '{experiment_type}'.")   
        # Make sure the uploaded file has a valid extension .fasta
        if not custom_primer_config_file.filename.lower().endswith((".fasta", ".fa")):
            raise ValueError(f"Custom primer config file '{custom_primer_config_file.filename}' must be a .fasta or .fa file.")     
        # Get pathogen and instrument type from experiment_type
        pathogen = experiment_type.split("-")[0]
        instrument = experiment_type.split("-")[-1]
        # Define the storage directory based on run name and experiment type
        storage_dir = os.path.realpath(os.path.join(_DEFAULT_MIRA_STORAGE_PATH, pathogen, instrument, run_name))
        os.makedirs(storage_dir, exist_ok=True)
        # Standardize the filename for custom primer config
        filename = CUSTOM_PRIMER_CONFIG_FILENAME
        dest_file_path = os.path.join(storage_dir, filename)
        # Copy custom primer config file to the destination file path
        custom_primer_config_file.file.seek(0)
        with open(dest_file_path, "wb") as buf:
            shutil.copyfileobj(custom_primer_config_file.file, buf)
        # Return success message with file path and name
        return {
            "status": "success",
            "message": f"Custom primer config file '{custom_primer_config_file.filename}' has been uploaded successfully.",
            "file_path": dest_file_path,
            "file_name": filename
        }
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))    
    

# Upload custom IRMA config file to storage location
@app.post("/upload/custom_irma_config", response_model=Dict[str, Any], summary="Upload a custom IRMA config file to storage location", tags=["MIRA Workflows"])
async def upload_custom_irma_config(
    run_name: str = Form("", description="Name of the sequencing run."),
    experiment_type: Literal[tuple(experiment_types)] = Form(..., description="Type of sequencing experiments."),
    custom_irma_config_file: UploadFile = File(..., description="Custom IRMA config file to upload.")
):
    """
    Upload a custom IRMA config file to the storage location for a given sequencing run.
    """
    try:
        # Retrieve assembly table from database
        db_assembly_tbl = lookup_tbl_in_database(
            db_tbl_name = ["assembly"],
            return_var = ["*"],
            filter_coln_var = ["run_name", "experiment_type"],
            filter_coln_val = {"run_name": [run_name], "experiment_type": [experiment_type]},
            filter_var_by = ["AND"]
        )
        # Make sure db_assembly_tbl is not empty
        if db_assembly_tbl.shape[0] == 0:
            raise ValueError(f"No assembly found for run_name '{run_name}' and experiment_type '{experiment_type}'.")
        # Make sure upload file is a yaml file
        if not custom_irma_config_file.filename.lower().endswith((".sh")):
            raise ValueError(f"Custom IRMA config file '{custom_irma_config_file.filename}' must be a .sh file.")
        # Get pathogen and instrument type from experiment_type
        pathogen = experiment_type.split("-")[0]
        instrument = experiment_type.split("-")[-1]
        # Define the storage directory based on run name and experiment type
        storage_dir = os.path.realpath(os.path.join(_DEFAULT_MIRA_STORAGE_PATH, pathogen, instrument, run_name))
        os.makedirs(storage_dir, exist_ok=True)
        # Standardize the filename for custom IRMA config
        filename = CUSTOM_IRMA_CONFIG_FILENAME
        dest_file_path = os.path.join(storage_dir, filename)
        # Copy custom IRMA config file to the destination file path
        custom_irma_config_file.file.seek(0)
        with open(dest_file_path, "wb") as buf:
            shutil.copyfileobj(custom_irma_config_file.file, buf)
        # Return success message with file path and name
        return {
            "status": "success",
            "message": f"Custom IRMA config file '{custom_irma_config_file.filename}' has been uploaded successfully.",
            "file_path": dest_file_path,
            "file_name": filename
        }
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
    

# Upload custom QC settings file to storage location
@app.post("/upload/custom_qc_settings", response_model=Dict[str, Any], summary="Upload a custom QC settings file to storage location", tags=["MIRA Workflows"])
async def upload_custom_qc_settings(
    run_name: str = Form("", description="Name of the sequencing run."),
    experiment_type: Literal[tuple(experiment_types)] = Form(..., description="Type of sequencing experiments."),
    custom_qc_settings_file: UploadFile = File(..., description="Custom QC settings file to upload.")
):
    """
    Upload a custom QC settings file to the storage location for a given sequencing run.
    """
    try:
        # Retrieve assembly table from database
        db_assembly_tbl = lookup_tbl_in_database(
            db_tbl_name = ["assembly"],
            return_var = ["*"],
            filter_coln_var = ["run_name", "experiment_type"],
            filter_coln_val = {"run_name": [run_name], "experiment_type": [experiment_type]},
            filter_var_by = ["AND"]
        )
        # Make sure db_assembly_tbl is not empty
        if db_assembly_tbl.shape[0] == 0:
            raise ValueError(f"No assembly found for run_name '{run_name}' and experiment_type '{experiment_type}'.") 
        # Make sure upload file is a yaml file
        if not custom_qc_settings_file.filename.lower().endswith((".yaml", ".yml")):
            raise ValueError(f"Custom QC settings file '{custom_qc_settings_file.filename}' must be a .yaml or .yml file.")       
        # Get pathogen and instrument type from experiment_type
        pathogen = experiment_type.split("-")[0]
        instrument = experiment_type.split("-")[-1]
        # Define the storage directory based on run name and experiment type
        storage_dir = os.path.realpath(os.path.join(_DEFAULT_MIRA_STORAGE_PATH, pathogen, instrument, run_name))
        os.makedirs(storage_dir, exist_ok=True)
        # Standardize the filename for custom QC settings
        filename = CUSTOM_QC_SETTINGS_FILENAME
        dest_file_path = os.path.join(storage_dir, filename)
        # Copy custom QC settings file to the destination location
        custom_qc_settings_file.file.seek(0)
        with open(dest_file_path, "wb") as buf:
            shutil.copyfileobj(custom_qc_settings_file.file, buf)
        # Return success message with file path and name
        return {
            "status": "success",
            "message": f"Custom QC settings file '{custom_qc_settings_file.filename}' has been uploaded successfully.",
            "file_path": dest_file_path,
            "file_name": filename
        }
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))    
    

# ---------- Validate samplesheet and all FASTQ files exist for a given sequencing run. ----------
@app.get("/validate/run", response_model=Dict[str, Any], summary="Validate samplesheet and FASTQ files exist for a given run", tags=["MIRA Workflows"])
async def validate_run(req: RunRequest = Depends()):
    """
    Validate samplesheet and all FASTQ files exist for a given sequencing run.
    """
    try:
        validation_result = await asyncio.to_thread(
            validate_samplesheet_and_fastqs_in_storage,
            run_name = req.run_name,
            experiment_type = req.experiment_type,
        )
        return validation_result
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
    
    
@app.get("/validate/custom_configs", response_model=Dict[str, Any], summary="Validate custom primers, custom IRMA config, and custom QC settings exist for a given run if provided", tags=["MIRA Workflows"])
async def validate_custom_configs(req: RunRequest = Depends()):
    """
    Validate that any provided custom primer, custom IRMA config, and custom QC settings files exist in storage.
    """
    try:
        validation_result = await asyncio.to_thread(
            validate_custom_configs_in_storage,
            run_name = req.run_name,
            experiment_type = req.experiment_type,
        )
        return validation_result
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
    
    
# ---------- Run MIRA Workflows ----------
@app.get("/run/MIRA", response_model=Dict[str, Any], summary="Run MIRA assembly via Docker (Part 3)", tags=["MIRA Workflows"])
async def run_mira(req: RunRequest = Depends()):
    """
    Launch the MIRA assembly for a given sequencing run via Docker.
    Returns status and process ID (PID) of the running MIRA process.
    """
    try:
        result = await asyncio.to_thread(
            run_mira_docker,
            run_name        = req.run_name,
            experiment_type = req.experiment_type,
        )
        return result       
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
    
     
# ---------- Cancel MIRA run ----------
@app.get("/cancel/MIRA", response_model=Dict[str, Any], summary="Cancel a MIRA run", tags=["MIRA Workflows"])
async def cancel_mira(req: RunStatusRequest = Depends()):
    """
    Send SIGTERM to the process group of the given PID and mark the run as CANCELLED.
    """
    try:
        result = await asyncio.to_thread(
            cancel_mira_run,
            pid = req.pid,
            run_name = req.run_name,
            experiment_type = req.experiment_type,
        )
        return result
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
    
    
# ---------- Check MIRA status ----------
@app.get("/MIRA/status", response_model=Dict[str, Any], summary="Check status process of a MIRA run", tags=["MIRA Workflows"])
async def get_mira_status(req: RunStatusRequest = Depends()):
    """
    Check the running status of MIRA for a given run and return
    the current status of the process.
    """
    try:
        result = await asyncio.to_thread(
            check_mira_status,
            pid = req.pid,
            run_name = req.run_name,
            experiment_type = req.experiment_type,
        )
        return result
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))   
    
    
# ---------- Pipeline DAG / status ----------
@app.get("/MIRA/DAG", response_model=Dict[str, Any], summary="Get MIRA DAG from assembly", tags=["MIRA Workflows"])
async def get_mira_dag(req: RunRequest = Depends()):
    """
    Parse the Nextflow execution trace file and .nextflow.log for a given run and return
    the pipeline DAG (workflow metadata + per-stage + per-task details).
    """
    try:
        result = await asyncio.to_thread(
            create_mira_dag,
            run_name        = req.run_name,
            experiment_type = req.experiment_type,
        )
        return result
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
    

@app.get("/MIRA/task_log", response_model=Dict[str, Any], summary="Get error log for a failed MIRA task", tags=["MIRA Workflows"])
async def get_mira_task_log(req: TaskLogRequest = Depends()):
    """
    Locate the Nextflow work directory for a single failed task (by its trace hash)
    and return its error log: relative path, filename, exit code, and error lines
    with line numbers.
    """
    try:
        result = await asyncio.to_thread(
            retrieve_task_log,
            run_name        = req.run_name,
            experiment_type = req.experiment_type,
            task_hash       = req.hash,
            stream          = req.stream,
            full            = bool(req.full),
        )
        return result
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
    

##############################################
# 
# MIRA RENAME AND COPY SECTION
# 
##############################################    

    
# ---------- Rename an existing MIRA run ----------
@app.patch("/rename/run", response_model=Dict[str, Any], summary="Rename a run (updates DB record and on-disk run directory)", tags=["MIRA Rename & Copy"])
async def rename_run(req: RenameRunRequest):
    """
    Rename an existing MIRA run. Updates the run_name in the database and renames
    the on-disk run directory (uploaded FASTQs + outputs) to match.
    """
    try:
        result = await asyncio.to_thread(
            rename_mira_run,
            run_name = req.run_name,
            experiment_type = req.experiment_type,
            new_run_name = req.new_run_name,
        )
        return result
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
    

# ---------- Copy an existing MIRA run ----------
@app.post("/copy/run", response_model=Dict[str, Any], summary="Copy a run to a new name (duplicates DB record, samplesheet, FASTQs and outputs)", tags=["MIRA Rename & Copy"])
async def copy_run(req: CopyRunRequest):
    """
    Duplicate an existing MIRA run — including its database record, samplesheet,
    and on-disk FASTQ/output files — under a new run name.
    """
    try:
        result = await asyncio.to_thread(
            copy_mira_run,
            run_name = req.run_name,
            experiment_type = req.experiment_type,
            new_run_name = req.new_run_name,
        )
        return result
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
    

##############################################
# 
# MIRA RESULTS SECTION
# 
##############################################       


# ---------- Retrieve Barcode Assignments ----------
@app.get("/retrieve/barcode_assignment", response_model=Optional[Dict[str, Any]], summary="Retrieve Barcode Assignments", tags=["MIRA Results"])
async def get_barcode_assignment(req: RunRequest = Depends()):
    """
    Retrieve barcode assignments for a given sequencing run.
    """
    try:
        result = await asyncio.to_thread(
            retrieve_barcode_assignment, 
            run_name = req.run_name, 
            experiment_type = req.experiment_type
        )
        return result
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
    
    
# ---------- Retrieve QC statement ----------
@app.get("/retrieve/qc_statement", response_model=Optional[Dict[str, Any]], summary="Retrieve QC Statement", tags=["MIRA Results"])
async def get_qc_statement(req: RunRequest = Depends()):
    """
    Retrieve QC statement for a given sequencing run.
    """
    try:
        result = await asyncio.to_thread(
            retrieve_qc_statement,
            run_name = req.run_name, 
            experiment_type = req.experiment_type
        )
        return result
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
    
    
# ---------- Retrieve Quality Control Decisions ----------
@app.get("/retrieve/quality_control_decisions", response_model=Optional[Dict[str, Any]], summary="Retrieve Quality Control Decisions", tags=["MIRA Results"])
async def get_quality_control_decisions(req: RunRequest = Depends()):
    """
    Retrieve quality control decisions for a given sequencing run.
    """
    try:
        result = await asyncio.to_thread(
            retrieve_quality_control_decisions,
            run_name = req.run_name, 
            experiment_type = req.experiment_type
        )
        return result
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))   
     

# ---------- Retrieve MIRA Summary ----------
@app.get("/retrieve/mira_summary", response_model=Optional[List[Dict[str, Any]]], summary="Retrieve MIRA Summary", tags=["MIRA Results"])
async def get_mira_summary(req: RunRequest = Depends()):
    """
    Retrieve MIRA summary (irma_summary.json) for a given sequencing run.
    """
    try:
        result = await asyncio.to_thread(
            retrieve_mira_summary,
            run_name = req.run_name,
            experiment_type = req.experiment_type
        )
        return result
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
    
    
# ---------- Retrieve Coverage Table----------
@app.get("/retrieve/coverage_table", response_model=Optional[List[Dict[str, Any]]], summary="Retrieve Coverage Table", tags=["MIRA Results"])
async def get_coverage(req: RunRequest = Depends()):
    """
    Retrieve coverage table for a given sequencing run.
    """
    try:
        result = await asyncio.to_thread(
            retrieve_coverage_table,
            run_name = req.run_name, 
            experiment_type = req.experiment_type
        )
        return result
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))   
    
    
# ---------- Retrieve Coverage Heatmap ----------
@app.get("/retrieve/coverage_heatmap", response_model=Optional[Dict[str, Any]], summary="Retrieve Coverage Heatmap", tags=["MIRA Results"])
async def get_coverage_heatmap(req: RunRequest = Depends()):
    """
    Retrieve coverage heatmap for a given sequencing run.
    """
    try:
        result = await asyncio.to_thread(
            retrieve_coverage_heatmap,
            run_name = req.run_name, 
            experiment_type = req.experiment_type
        )
        return result
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))  
    
     
# ---------- Retrieve Sample Coverage List ----------
@app.get("/retrieve/sample_coverage_list", response_model=Optional[Dict[str, Any]], summary="Retrieve Sample Coverage List", tags=["MIRA Results"])
async def get_sample_coverage_list(req: RunRequest = Depends()):
    """
    Retrieve sample coverage list for a given sequencing run.
    """
    try:
        result = await asyncio.to_thread(
            retrieve_sample_coverage_list,
            run_name = req.run_name, 
            experiment_type = req.experiment_type
        )
        return result
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
    

# ---------- Retrieve Sample Coverage Sankey Figure ----------
@app.get("/retrieve/sample_coverage_sankeyfig", response_model=Optional[Dict[str, Any]], summary="Retrieve Sample Coverage Sankey Figure", tags=["MIRA Results"])
async def get_sample_coverage_sankeyfig(
    req: RunRequest = Depends(),
    sample_id: str = Query(..., description="Sample ID to retrieve the coverage sankey figure for"),
):
    """
    Retrieve sample coverage sankey figure for a given sequencing run and sample.
    """
    try:
        result = await asyncio.to_thread(
            retrieve_sample_coverage_sankeyfig,
            run_name = req.run_name, 
            experiment_type = req.experiment_type,
            sample_id = sample_id,
        )
        return result
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
    

# ---------- Retrieve Sample Coverage Plot ----------
@app.get("/retrieve/sample_coverage_plot", response_model=Optional[Dict[str, Any]], summary="Retrieve Sample Segment Coverage Plot", tags=["MIRA Results"])
async def get_sample_coverage_plot(
    req: RunRequest = Depends(),
    sample_id: str = Query(..., description="Sample ID to retrieve the segment coverage plot for"),
):
    """
    Retrieve sample segment coverage plot for a given sequencing run and sample.
    """
    try:
        result = await asyncio.to_thread(
            retrieve_sample_coverage_plot,
            run_name = req.run_name, 
            experiment_type = req.experiment_type,
            sample_id = sample_id,
        )
        return result
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    

# ---------- Retrieve Sample Combined (linear) Coverage Plot ----------
@app.get("/retrieve/sample_coverage_linearfig", response_model=Optional[Dict[str, Any]], summary="Retrieve Sample Combined Coverage Plot", tags=["MIRA Results"])
async def get_sample_coverage_linearfig(
    req: RunRequest = Depends(),
    sample_id: str = Query(..., description="Sample ID to retrieve the combined coverage plot for"),
):
    """
    Retrieve sample combined (all-segment) coverage plot for a given sequencing run and sample.
    """
    try:
        result = await asyncio.to_thread(
            retrieve_sample_coverage_linearfig,
            run_name = req.run_name,
            experiment_type = req.experiment_type,
            sample_id = sample_id,
        )
        return result
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
    
    
# ---------- Retrieve variants ----------
@app.get("/retrieve/variants", response_model=Optional[List[Dict[str, Any]]], summary="Retrieve Variants", tags=["MIRA Results"])
async def get_variants(req: RunRequest = Depends()):
    """
    Retrieve variants for a given sequencing run.
    """
    try:
        result = await asyncio.to_thread(
            retrieve_variants,
            run_name = req.run_name, 
            experiment_type = req.experiment_type
        )
        return result
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
    
    
# ---------- Retrieve minor snvs ----------
@app.get("/retrieve/minor_snvs", response_model=Optional[List[Dict[str, Any]]], summary="Retrieve Minor SNVs", tags=["MIRA Results"])
async def get_minor_snvs(req: RunRequest = Depends()):
    """
    Retrieve minor snvs for a given sequencing run.
    """
    try:
        result = await asyncio.to_thread(
            retrieve_minor_snvs,
            run_name = req.run_name, 
            experiment_type = req.experiment_type
        )
        return result
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
    
    
# ---------- Retrieve indels ----------
@app.get("/retrieve/indels", response_model=Optional[List[Dict[str, Any]]], summary="Retrieve Indels", tags=["MIRA Results"])
async def get_indels(req: RunRequest = Depends()):
    """
    Retrieve indels for a given sequencing run.
    """
    try:
        result = await asyncio.to_thread(
            retrieve_indels,
            run_name = req.run_name, 
            experiment_type = req.experiment_type
        )
        return result
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
    

# ---------- Retrieve Failed Amended Consensus ----------
@app.get("/retrieve/failed_amended_consensus", response_model=Optional[Dict[str, Any]], summary="Retrieve Failed Amended Consensus", tags=["MIRA Results"])
async def get_failed_amended_consensus(req: RunRequest = Depends()):
    """
    Retrieve failed amended consensus for a given sequencing run.
    """
    try:
        result = await asyncio.to_thread(
            retrieve_failed_amended_consensus,
            run_name = req.run_name, 
            experiment_type = req.experiment_type
        )
        return {"location": result}
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
    

# ---------- Retrieve Passed Amended Consensus ----------
@app.get("/retrieve/passed_amended_consensus", response_model=Optional[Dict[str, Any]], summary="Retrieve Passed Amended Consensus", tags=["MIRA Results"])
async def get_passed_amended_consensus(req: RunRequest = Depends()):
    """
    Retrieve passed amended consensus for a given sequencing run.
    """
    try:
        result = await asyncio.to_thread(
            retrieve_passed_amended_consensus,
            run_name = req.run_name, 
            experiment_type = req.experiment_type
        )
        return {"location": result}
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
    

# ---------- Retrieve AA Failed Fasta Location ----------
@app.get("/retrieve/failed_amino_acid_consensus", response_model=Optional[Dict[str, Any]], summary="Retrieve Failed Amino Acid Consensus", tags=["MIRA Results"])
async def get_failed_amino_acid_consensus(req: RunRequest = Depends()):
    """
    Retrieve failed amino acid consensus for a given sequencing run.
    """
    try:
        result = await asyncio.to_thread(
            retrieve_failed_amino_acid_consensus,
            run_name = req.run_name, 
            experiment_type = req.experiment_type
        )
        return {"location": result}
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
    

# ---------- Retrieve AA Passed Fasta Location ----------
@app.get("/retrieve/passed_amino_acid_consensus", response_model=Optional[Dict[str, Any]], summary="Retrieve Passed Amino Acid Consensus", tags=["MIRA Results"])
async def get_passed_amino_acid_consensus(req: RunRequest = Depends()):
    """
    Retrieve passed amino acid consensus for a given sequencing run.
    """
    try:
        result = await asyncio.to_thread(
            retrieve_passed_amino_acid_consensus,
            run_name = req.run_name, 
            experiment_type = req.experiment_type
        )
        return {"location": result}
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))      
      

# ---------- Retrieve Nextclade Fasta Location ----------
@app.get("/retrieve/nextclade_aligned_fasta", response_model=Optional[Dict[str, Any]], summary="Retrieve Nextclade Aligned Fasta", tags=["MIRA Results"])
async def get_nextclade_aligned_fasta(req: RunRequest = Depends()):
    """
    Retrieve Nextclade aligned fasta for a given sequencing run.
    """
    try:
        result = await asyncio.to_thread(
            retrieve_nextclade_aligned_fasta,
            run_name = req.run_name, 
            experiment_type = req.experiment_type
        )
        return {"location": result}
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
    

##############################################
# 
# MIRA DOWNLOADS SECTION
# 
##############################################        


# ---------- Download NT Passed FASTA ----------
@app.get("/download/nt_passed_fasta", summary="Download NT Passed FASTA", tags=["MIRA Downloads"])
async def download_nt_passed_fasta(req: RunRequest = Depends()):
    try:
        path = await asyncio.to_thread(retrieve_passed_amended_consensus, req.run_name, req.experiment_type)
        if not path or not os.path.exists(path):
            raise HTTPException(status_code=404, detail="NT passed FASTA not found")
        return FileResponse(path=path, filename=f"{req.run_name}_nt_passed.fasta", media_type="application/octet-stream", content_disposition_type="attachment")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

# ---------- Download NT Failed FASTA ----------
@app.get("/download/nt_failed_fasta", summary="Download NT Failed FASTA", tags=["MIRA Downloads"])
async def download_nt_failed_fasta(req: RunRequest = Depends()):
    try:
        path = await asyncio.to_thread(retrieve_failed_amended_consensus, req.run_name, req.experiment_type)
        if not path or not os.path.exists(path):
            raise HTTPException(status_code=404, detail="NT failed FASTA not found")
        return FileResponse(path=path, filename=f"{req.run_name}_nt_failed.fasta", media_type="application/octet-stream", content_disposition_type="attachment")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    
# ---------- Download AA Passed FASTA ----------
@app.get("/download/aa_passed_fasta", summary="Download AA Passed FASTA", tags=["MIRA Downloads"])
async def download_aa_passed_fasta(req: RunRequest = Depends()):
    try:
        path = await asyncio.to_thread(retrieve_passed_amino_acid_consensus, req.run_name, req.experiment_type)
        if not path or not os.path.exists(path):
            raise HTTPException(status_code=404, detail="AA passed FASTA not found")
        return FileResponse(path=path, filename=f"{req.run_name}_aa_passed.fasta", media_type="application/octet-stream", content_disposition_type="attachment")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------- Download AA Failed FASTA ----------
@app.get("/download/aa_failed_fasta", summary="Download AA Failed FASTA", tags=["MIRA Downloads"])
async def download_aa_failed_fasta(req: RunRequest = Depends()):
    try:
        path = await asyncio.to_thread(retrieve_failed_amino_acid_consensus, req.run_name, req.experiment_type)
        if not path or not os.path.exists(path):
            raise HTTPException(status_code=404, detail="AA failed FASTA not found")
        return FileResponse(path=path, filename=f"{req.run_name}_aa_failed.fasta", media_type="application/octet-stream", content_disposition_type="attachment")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------- Download Custom Primer Config ----------
@app.get("/download/custom_primer_config", summary="Download Custom Primer Config", tags=["MIRA Downloads"])
async def download_custom_primer_config(req: RunRequest = Depends()):
    try:
        pathogen = req.experiment_type.split("-")[0]
        instrument = req.experiment_type.split("-")[-1]
        path = os.path.join(_DEFAULT_MIRA_STORAGE_PATH, pathogen, instrument, req.run_name, CUSTOM_PRIMER_CONFIG_FILENAME)
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="Custom primer config file not found in storage. File may have been moved or deleted. Please re-upload a new custom primer config file if needed or turn off custom primer config.")
        return FileResponse(path=path, filename=CUSTOM_PRIMER_CONFIG_FILENAME, media_type="application/octet-stream", content_disposition_type="attachment")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------- Download Custom IRMA Config ----------
@app.get("/download/custom_irma_config", summary="Download Custom IRMA Config", tags=["MIRA Downloads"])
async def download_custom_irma_config(req: RunRequest = Depends()):
    try:
        pathogen = req.experiment_type.split("-")[0]
        instrument = req.experiment_type.split("-")[-1]
        path = os.path.join(_DEFAULT_MIRA_STORAGE_PATH, pathogen, instrument, req.run_name, CUSTOM_IRMA_CONFIG_FILENAME)
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="Custom IRMA config file not found in storage. File may have been moved or deleted. Please re-upload a new custom IRMA config file if needed or turn off custom IRMA config.")
        return FileResponse(path=path, filename=CUSTOM_IRMA_CONFIG_FILENAME, media_type="application/octet-stream", content_disposition_type="attachment")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------- Download Custom QC Settings ----------
@app.get("/download/custom_qc_settings", summary="Download Custom QC Settings", tags=["MIRA Downloads"])
async def download_custom_qc_settings(req: RunRequest = Depends()):
    try:
        pathogen = req.experiment_type.split("-")[0]
        instrument = req.experiment_type.split("-")[-1]
        path = os.path.join(_DEFAULT_MIRA_STORAGE_PATH, pathogen, instrument, req.run_name, CUSTOM_QC_SETTINGS_FILENAME)
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="Custom QC settings file not found in storage. File may have been moved or deleted. Please re-upload a new custom QC settings file if needed or turn off custom QC settings.")
        return FileResponse(path=path, filename=CUSTOM_QC_SETTINGS_FILENAME, media_type="application/octet-stream", content_disposition_type="attachment")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------- Download Nextclade FASTA (single file by key) ----------
@app.get("/download/nextclade_fasta", summary="Download Nextclade FASTA", tags=["MIRA Downloads"])
async def download_nextclade_fasta(req: DownloadFastaRequest = Depends()):
    try:
        files = await asyncio.to_thread(retrieve_nextclade_aligned_fasta, req.run_name, req.experiment_type)
        if not files:
            raise HTTPException(status_code=404, detail=f"No Nextclade FASTA files found for run '{req.run_name}' and experiment type '{req.experiment_type}' and key '{req.key}'.")
        all_keys = list(files.keys())
        path = files.get(req.key) if req.key else None
        if not path or not os.path.exists(path):
            raise HTTPException(status_code=404, detail=f"Invalid fasta keys. Available keys: {all_keys}")
        safe_key = req.key if req.key else all_keys[0]
        return FileResponse(path=path, filename=f"{req.run_name}_nextclade_{safe_key}.fasta", media_type="application/octet-stream", content_disposition_type="attachment")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------- Export MIRA Reports ----------
@app.get("/download/mira_reports", summary="Export MIRA Reports", tags=["MIRA Downloads"])
async def download_mira_reports(req: RunRequest = Depends()):
    """
    Zip all files in the run's mira_reports directory and return as a downloadable .zip archive.
    """
    try:
        pathogen   = req.experiment_type.split("-")[0]
        instrument = req.experiment_type.split("-")[-1]
        mira_report_dir = os.path.join(
            _DEFAULT_MIRA_STORAGE_PATH, pathogen, instrument,
            req.run_name, "outputs", "aggregate_outputs", "mira-reports"
        )
        if not os.path.isdir(mira_report_dir):
            raise HTTPException(status_code=404, detail=f"No report directory found for run '{req.run_name}'.")
        report_files = [
            f for f in os.listdir(mira_report_dir)
            if os.path.isfile(os.path.join(mira_report_dir, f))
        ]
        if not report_files:
            raise HTTPException(status_code=404, detail=f"No report files found for run '{req.run_name}'.")
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for fname in sorted(report_files):
                zf.write(os.path.join(mira_report_dir, fname), arcname=fname)
        zip_buffer.seek(0)
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{req.run_name}_mira_reports.zip"'},
        )
    except HTTPException:
        raise
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))


##############################################
# 
# MIRA DELETE SECTION
# 
##############################################


# ---------- Delete a single sample from a run's samplesheet ----------
@app.delete("/delete/sample", response_model=Dict[str, Any], summary="Remove a sample from a run's samplesheet", tags=["MIRA Delete"])
async def delete_sample(req: DeleteSampleRequest):
    """
    Remove a single sample row from the ONT or Illumina samplesheet of an existing run in the database.
    """
    try:
        result = await asyncio.to_thread(
            delete_sample_from_run,
            run_name = req.run_name,
            experiment_type = req.experiment_type,
            sample_id = req.sample_id,
            fastq = req.fastq,
            fastq_1 = req.fastq_1,
            fastq_2 = req.fastq_2,
        )
        return result
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))

# ---------- Delete an existing MIRA run ----------
@app.delete("/delete/run", response_model=Dict[str, Any], summary="Delete a run from database and disk records", tags=["MIRA Delete"])
async def delete_run(req: RunRequest):
    """
    Remove a run's assembly record (and its samplesheet rows) from the database.
    Files on disk (uploaded FASTQs, pipeline outputs) are also deleted.
    """
    try:
        result = await asyncio.to_thread(
            delete_mira_run,
            run_name = req.run_name,
            experiment_type = req.experiment_type,
        )
        return result
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))    
    
############################################## 
#
# SEQSENDER SECTION
# 
##############################################

# ---------- List all submissions ----------
@app.get("/seqsender/version", response_model=Dict[str, str], summary="Get SeqSender version", tags=["SeqSender Utils"])
async def get_seqsender_version():
    try:
        version = _get_seqsender_version()
        return {"version": version}
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))

# Upload config file to SeqSender storage location
@app.post("/upload/seqsender/config", response_model=Dict[str, Any], summary="Upload a config file to SeqSender storage location", tags=["SeqSender Workflows"])
async def upload_seqsender_config(
    submission_name: str = Form("", description="Name of the submission."),
    organism: Literal[tuple(organisms)] = Form(..., description="Type of organisms to submit."),
    config_file: UploadFile = File(..., description="Config file to upload.")
):
    """
    Upload a config file to the SeqSender storage location for a given submission.
    """
    try:
        # Make sure the uploaded file is a valid config file (e.g., check extension or content)
        if not config_file.filename.endswith(".yaml") and not config_file.filename.endswith(".yml"):
            raise ValueError(f"Config file '{config_file.filename}' must be a .yaml or .yml file.")
        # Define the storage directory based on submission name and organism
        submission_dir = os.path.realpath(os.path.join(_DEFAULT_SEQSENDER_STORAGE_PATH, organism))
        submission_name_dir = os.path.realpath(os.path.join(submission_dir, submission_name))
        os.makedirs(submission_name_dir, exist_ok=True)
        # Standardize the filename 
        filename = CONFIG_FILENAME
        dest_file_path = os.path.join(submission_name_dir, filename)
        # Copy config file to the destination file path
        config_file.file.seek(0)
        with open(dest_file_path, "wb") as buf:
            shutil.copyfileobj(config_file.file, buf)
        # Return success message with file path and name
        return {
            "status": "success",
            "message": f"Config file '{config_file.filename}' has been uploaded successfully.",
            "file_path": dest_file_path,
            "file_name": filename
        }
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
    

# Upload metadata file to SeqSender storage location
@app.post("/upload/seqsender/metadata", response_model=Dict[str, Any], summary="Upload a metadata file to SeqSender storage location", tags=["SeqSender Workflows"])
async def upload_seqsender_metadata(
    submission_name: str = Form("", description="Name of the submission."),
    organism: Literal[tuple(organisms)] = Form(..., description="Type of organisms to submit."),
    metadata_file: UploadFile = File(..., description="Metadata file to upload.")
):
    """
    Upload a metadata file to the SeqSender storage location for a given submission.
    """
    try:
        # Make sure the uploaded file is a valid metadata file (e.g., check extension or content)
        if not metadata_file.filename.endswith(".csv") and not metadata_file.filename.endswith(".csv"):
            raise ValueError(f"Metadata file '{metadata_file.filename}' must be a .csv file.")
        # Define the storage directory based on submission name and organism
        submission_dir = os.path.realpath(os.path.join(_DEFAULT_SEQSENDER_STORAGE_PATH, organism))
        submission_name_dir = os.path.realpath(os.path.join(submission_dir, submission_name))
        os.makedirs(submission_name_dir, exist_ok=True)
        # Standardize the filename
        filename = METADATA_FILENAME
        dest_file_path = os.path.join(submission_name_dir, filename)
        metadata_file.file.seek(0)
        with open(dest_file_path, "wb") as buf:
            shutil.copyfileobj(metadata_file.file, buf)
        # Return success message with file path and name
        return {
            "status": "success",
            "message": f"Metadata file '{metadata_file.filename}' has been uploaded successfully.",
            "file_path": dest_file_path,
            "file_name": filename
        }
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))    
    

# Upload fasta file to SeqSender storage location
@app.post("/upload/seqsender/fasta", response_model=Dict[str, Any], summary="Upload a fasta file to SeqSender storage location", tags=["SeqSender Workflows"])
async def upload_seqsender_fasta(
    submission_name: str = Form("", description="Name of the submission."),
    organism: Literal[tuple(organisms)] = Form(..., description="Type of organisms to submit."),
    fasta_file: UploadFile = File(..., description="Fasta file to upload.")
):
    """
    Upload a fasta file to the SeqSender storage location for a given submission.
    """
    try:
        # Make sure the uploaded file is a valid fasta file (e.g., check extension or content)
        if not fasta_file.filename.endswith(".fasta") and not fasta_file.filename.endswith(".fa") and not fasta_file.filename.endswith(".fna"):
            raise ValueError(f"Fasta file '{fasta_file.filename}' must be a .fasta, .fa, or .fna file.")
        # Define the storage directory based on submission name and organism
        submission_dir = os.path.realpath(os.path.join(_DEFAULT_SEQSENDER_STORAGE_PATH, organism))
        submission_name_dir = os.path.realpath(os.path.join(submission_dir, submission_name))
        os.makedirs(submission_name_dir, exist_ok=True)
        # Standardize the filename
        filename = FASTA_FILENAME
        dest_file_path = os.path.join(submission_name_dir, filename)
        fasta_file.file.seek(0)
        with open(dest_file_path, "wb") as buf:
            shutil.copyfileobj(fasta_file.file, buf)
        # Return success message with file path and name
        return {
            "status": "success",
            "message": f"Fasta file '{fasta_file.filename}' has been uploaded successfully.",
            "file_path": dest_file_path,
            "file_name": filename
        }
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err)) 
    

# Upload GISAID CLI file to SeqSender storage location
@app.post("/upload/seqsender/gisaid_cli", response_model=Dict[str, Any], summary="Upload a GISAID CLI file to SeqSender storage location", tags=["SeqSender Workflows"])
async def upload_seqsender_gisaid_cli(
    organism: Literal[tuple(organisms)] = Form(..., description="Type of organisms to submit."),
    gisaid_cli_file: UploadFile = File(..., description="Gisaid CLI file to upload.")
):
    """
    Upload a GISAID CLI file to the SeqSender storage location for a given submission.
    """
    try:
        # Define the storage directory based on submission name and organism
        submission_dir = os.path.realpath(os.path.join(_DEFAULT_SEQSENDER_STORAGE_PATH, organism))
        submission_gisaid_cli_dir = os.path.realpath(os.path.join(submission_dir, "gisaid_cli"))
        os.makedirs(submission_gisaid_cli_dir, exist_ok=True)
        # Standardize the filename
        filename = organism.lower()+"CLI"
        dest_file_path = os.path.join(submission_gisaid_cli_dir, filename)
        # Copy GISAID CLI file to the destination file path
        gisaid_cli_file.file.seek(0)
        with open(dest_file_path, "wb") as buf:
            shutil.copyfileobj(gisaid_cli_file.file, buf)
        # Return success message with file path and name
        return {
            "status": "success",
            "message": f"GISAID CLI file '{gisaid_cli_file.filename}' has been uploaded successfully.",
            "file_path": dest_file_path,
            "file_name": filename
        }
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err)) 
    

# Upload raw reads files to SeqSender storage location
@app.post("/upload/seqsender/raw_reads", response_model=Dict[str, Any], summary="Upload raw reads files to SeqSender storage location", tags=["SeqSender Workflows"])
async def upload_seqsender_raw_reads(
    submission_name: str = Form("", description="Name of the submission."),
    organism: Literal[tuple(organisms)] = Form(..., description="Type of organisms to submit."),
    raw_read_files: List[UploadFile] = File(default=[], description="One or more .fastq/.fastq.gz/.fq/.fq.gz files to upload."),
):
    """
    Upload raw reads files to the SeqSender storage location for a given submission.
    """
    try:
        # Define the storage directory based on submission name and organism
        submission_dir = os.path.realpath(os.path.join(_DEFAULT_SEQSENDER_STORAGE_PATH, organism))
        submission_name_dir = os.path.realpath(os.path.join(submission_dir, submission_name))
        submission_raw_reads_dir = os.path.realpath(os.path.join(submission_name_dir, "raw_reads"))
        os.makedirs(submission_raw_reads_dir, exist_ok=True)
        # Copy raw reads file to the destination file path
        uploaded_files = []
        for raw_read_file in raw_read_files:
            raw_read_file.file.seek(0)
            filename = raw_read_file.filename
            dest_file_path = os.path.join(submission_raw_reads_dir, filename)
            with open(dest_file_path, "wb") as buf:
                shutil.copyfileobj(raw_read_file.file, buf)
            uploaded_files.append({"file_path": dest_file_path, "file_name": filename})
        # Return success message with file paths and names
        return {
            "status": "success",
            "message": f"Raw reads files have been uploaded successfully.",
            "files": uploaded_files
        }
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))     
    

# Upload GFF file to SeqSender storage location
@app.post("/upload/seqsender/gff", response_model=Dict[str, Any], summary="Upload a GFF file to SeqSender storage location", tags=["SeqSender Workflows"])
async def upload_seqsender_gff(
    submission_name: str = Form("", description="Name of the submission."),
    organism: Literal[tuple(organisms)] = Form(..., description="Type of organisms to submit."),
    gff_file: UploadFile = File(..., description="GFF file to upload.")
):
    """
    Upload a GFF file to the SeqSender storage location for a given submission.
    """
    try:
        # Make sure the uploaded file is a valid GFF file (e.g., check extension or content)
        if not gff_file.filename.endswith(".gff") and not gff_file.filename.endswith(".gff3"):
            raise ValueError(f"GFF file '{gff_file.filename}' must have a .gff or .gff3 extension.")
        # Define the storage directory
        submission_dir = os.path.realpath(os.path.join(_DEFAULT_SEQSENDER_STORAGE_PATH, organism))
        submission_name_dir = os.path.realpath(os.path.join(submission_dir, submission_name))
        os.makedirs(submission_name_dir, exist_ok=True)
        # Standardize the filename
        filename = GFF_FILENAME
        dest_file_path = os.path.join(submission_name_dir, filename)
        # Copy GFF file to the destination file path
        gff_file.file.seek(0)
        with open(dest_file_path, "wb") as buf:
            shutil.copyfileobj(gff_file.file, buf)
        # Return success message with file path and name
        return {
            "status": "success",
            "message": f"GFF file '{gff_file.filename}' has been uploaded successfully.",
            "file_path": dest_file_path,
            "file_name": filename
        }
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err)) 
    

# ---------- Create SeqSender submission ----------
@app.post("/create/submission", response_model=Dict[str, Any], summary="Create a SeqSender submission", tags=["SeqSender Workflows"])
async def create_submission(req: CreateSubmissionRequest):
    """
    Create a SeqSender submission for a given submission name, organism, database, and submission type. 
    The submission will be created using the provided config file, metadata file, fasta file, and optionally GISAID CLI and GFF files. 
    The function will return a list of messages indicating the success or failure of each step in the submission process.
    """
    try:
        # Get NCBI Submitter Info if provided, else set to None
        if req.ncbi_submitter_info is not None:
            ncbi_submitter_info = pl.DataFrame([req.ncbi_submitter_info.model_dump()])
        else:
            ncbi_submitter_info = None
        # Get GISAID Submitter Info if provided, else set to None
        if req.gisaid_submitter_info is not None:
            gisaid_submitter_info = pl.DataFrame([req.gisaid_submitter_info.model_dump()])
        else:
            gisaid_submitter_info = None
        # Create the submission in a separate thread to avoid blocking the event loop
        result = await asyncio.to_thread(
            create_seqsender_submission,
            submission_name = req.submission_name,
            organism = req.organism,
            database = req.database,
            submission_type = req.submission_type,
            ncbi_submitter_info = ncbi_submitter_info,
            gisaid_submitter_info = gisaid_submitter_info,
            gff_file = req.gff_file,
            table2asn= req.table2asn,
            ncbi_publication_title = req.ncbi_publication_title,
            ncbi_publication_status = req.ncbi_publication_status,
            ncbi_release_date = req.ncbi_release_date,
        )
        return result
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))       
      

@app.get("/validate/seqsender/files", response_model=Dict[str, Any], summary="Validate files for an existing SeqSender submission", tags=["SeqSender Workflows"])
async def validate_submission_files(
    submission_name: str = Query(..., description="Name of the submission."),
    organism: Literal[tuple(organisms)] = Query(..., description="Type of organisms to submit."),
    database: List[Literal[tuple(database_targets)]] = Query(..., description="One or more databases to submit to."),
    submission_type: Literal[tuple(submission_types)] = Query(..., description="Type of submission."),
    gff_file: bool = Query(False, description="Whether a stored GFF file is required."),
):
    try:
        return await asyncio.to_thread(
            validate_seqsender_uploaded_files,
            submission_name=submission_name,
            organism=organism,
            database=database,
            submission_type=submission_type,
            require_gff=gff_file,
        )
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
   

# Submit a submission to NCBI or GISAID using SeqSender
@app.post("/submit/submission", response_model=Dict[str, Any], summary="Submit a SeqSender submission to NCBI or GISAID", tags=["SeqSender Workflows"])
async def submit_submission(req: SubmissionRequest):
    """
    Submit a SeqSender submission to NCBI or GISAID for a given submission name, organism, database, and submission type. 
    The function will return a dictionary containing the details of the submission process.
    """
    try:
        result = await asyncio.to_thread(
            submit_ncbi_submission,
            submission_name = req.submission_name,
            organism = req.organism,
            database = req.database,
            submission_type = req.submission_type
        )
        return result
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))


# Create the per-database submission files for a stored submission without submitting to any portal
@app.post("/create/submission/files", response_model=Dict[str, Any], summary="Create SeqSender submission files without submitting", tags=["SeqSender Workflows"])
async def create_submission_files(req: SubmissionRequest):
    """
    Generate the per-database submission files (BioSample/SRA/GenBank/GISAID) for a stored
    submission using SeqSender's "prep" command, without launching an actual submission to
    any portal. Returns a dictionary containing the status, message, and created file locations.
    """
    try:
        result = await asyncio.to_thread(
            prep_seqsender_submission,
            submission_name = req.submission_name,
            organism = req.organism,
            database = req.database,
            submission_type = req.submission_type
        )
        return result
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))

 
@app.get("/check/submission/process", response_model=Dict[str, Any], summary="Check a running SeqSender submission", tags=["SeqSender Workflows"])
async def get_seqsender_process_status(
    submission_name: str = Query(..., description="Name of the submission."),
    organism: Literal[tuple(organisms)] = Query(..., description="Organism for which sequences are being sent."),
    database: List[Literal[tuple(database_targets)]] = Query(..., description="One or more submission databases."),
    submission_type: Literal[tuple(submission_types)] = Query(..., description="Type of submission."),
    pid: int = Query(..., gt=0, description="Process ID returned when the submission was launched."),
):
    try:
        return await asyncio.to_thread(
            retrieve_seqsender_process_status,
            submission_name=submission_name,
            organism=organism,
            database=database,
            submission_type=submission_type,
            pid=pid,
        )
    except (ValueError, FileNotFoundError) as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))


# Check status of a SeqSender submission
@app.get("/check/submission/status", response_model=Dict[str, Any], summary="Check submission status for a given organism and database", tags=["SeqSender Workflows"])
async def monitor_submission_status(
    submission_name: str = Query(..., description="Name of the submission."),
    organism: Literal[tuple(organisms)] = Query(..., description="Organism for which to send sequences."),
    database: List[Literal[tuple(database_targets)]] = Query(..., description="One or more databases to submit to."),
    submission_type: Literal[tuple(submission_types)] = Query(..., description="Type of submission."),
):
    try:
        status = await asyncio.to_thread(
            check_seqsender_submission,
            submission_name=submission_name,
            organism=organism,
            database=database,
            submission_type=submission_type
        )
        return status
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Manage the hourly submission status schedule
@app.get("/cron/status", response_model=Dict[str, Any], summary="Get the hourly submission status schedule", tags=["SeqSender Workflows"])
async def get_status_update_cron():
    try:
        return await asyncio.to_thread(get_status_update_schedule)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/cron/update/status", response_model=Dict[str, Any], summary="Create or update the hourly submission status schedule", tags=["SeqSender Workflows"])
async def create_status_update_cron(req: StatusUpdateCronRequest):
    try:
        schedule = await asyncio.to_thread(save_status_update_schedule, req.interval_hours)
        start_status_update_scheduler()
        wake_status_update_scheduler()
        return {
            "message": "Hourly submission status updates scheduled.",
            "schedule": schedule,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Delete the hourly submission status schedule
@app.delete("/cron/delete/status", response_model=Dict[str, Any], summary="Remove the hourly submission status schedule", tags=["SeqSender Workflows"])
async def delete_status_update_cron():
    try:
        await asyncio.to_thread(delete_status_update_schedule)
        wake_status_update_scheduler()
        return {"message": "Hourly submission status updates disabled."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Check status of a SeqSender submission
@app.get("/load/submission/status", response_model=Dict[str, Any], summary="Load submission status for a given organism and database", tags=["SeqSender Workflows"])
async def retrieve_submission_status(
    submission_name: str = Query(..., description="Name of the submission."),
    organism: Literal[tuple(organisms)] = Query(..., description="Organism for which to send sequences."),
    database: List[Literal[tuple(database_targets)]] = Query(..., description="One or more databases to submit to."),
    submission_type: Literal[tuple(submission_types)] = Query(..., description="Type of submission."),
):
    try:
        status = await asyncio.to_thread(
            load_submission_status,
            submission_name=submission_name,
            organism=organism,
            database=database,
            submission_type=submission_type
        )
        return status
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    
# ---------- List all submissions ----------
@app.get("/list/submitters", response_model=ListSubmitterResponse, summary="List all submitters", tags=["Submitter Utils"])
async def get_submitters(
    submission_portal: Optional[Literal[tuple(submission_portals)]] = Query(None, description="Submission portal (NCBI or GISAID).")
):
    """
    Return a list of submitters in the database, optionally filtered by submission_portal
    ("NCBI" or "GISAID"), including saved passwords so users can verify or update them.
    """
    try:
        db_submitter_tbl = lookup_tbl_in_database(
            db_tbl_name = ["submitter"],
            return_var  = ["*"],
            filter_coln_var = ["submission_portal"] if submission_portal else None,
            filter_coln_val = {"submission_portal": [submission_portal]} if submission_portal else None,
            filter_var_by = ["AND"] if submission_portal else None
        )
        if db_submitter_tbl.shape[0] == 0:
            return {"SubmitterInfo": []}
        else:
            return {"SubmitterInfo": db_submitter_tbl.to_dicts()}
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))


@app.get("/retrieve/submitter", response_model=ListSubmitterResponse, summary="Retrieve information about a given submitter", tags=["Submitter Utils"])
async def get_submitter_info(
    submitter_name: str = Query(..., description="Name of the submitter."),
    submission_portal: Literal[tuple(submission_portals)] = Query(..., description="Submission portal (NCBI or GISAID).")
):
    """
    Return a submitter matching the given name and submission portal, including the saved
    password so the user can verify or update it.
    """
    try:
        db_submitter_tbl = lookup_tbl_in_database(
            db_tbl_name = ["submitter"],
            return_var  = ["*"],
            filter_coln_var = ["submitter_name", "submission_portal"],
            filter_coln_val = {"submitter_name": [submitter_name], "submission_portal": [submission_portal]},
            filter_var_by = ["AND", "AND"],
        )
        if db_submitter_tbl.shape[0] == 0:
            return {"SubmitterInfo": []}
        else:
            return {"SubmitterInfo": db_submitter_tbl.to_dicts()}
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))    


# Save (create or update) a submitter's credentials without creating a submission
@app.post("/save/submitter", response_model=Dict[str, Any], summary="Save a submitter's credentials for future use", tags=["Submitter Utils"])
async def save_submitter_endpoint(req: SubmitterInfo):
    """
    Save (insert or update) a submitter's credentials for a given portal (NCBI or GISAID) so
    they can be reused on future submissions without needing to submit a full submission.
    """
    try:
        submitter_tbl = pl.DataFrame([req.model_dump()])
        result = await asyncio.to_thread(save_submitter, submitter_tbl)
        return result
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))


# ---------- Delete a saved submitter ----------
@app.delete("/delete/submitter", response_model=Dict[str, Any], summary="Delete a saved submitter's credentials", tags=["Submitter Utils"])
async def delete_submitter_endpoint(req: DeleteSubmitterRequest):
    """
    Remove a saved submitter's credentials (identified by name + submission portal) from the database.
    """
    try:
        result = await asyncio.to_thread(
            delete_submitter,
            submitter_name = req.submitter_name,
            submission_portal = req.submission_portal,
        )
        return result
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))


@app.get("/list/submissions", response_model=ListSubmissionResponse, summary="List all submissions", tags=["Submission Utils"])
async def get_submissions():
    """
    Return a list of submissions in database.
    """
    # Query for all assembly runs
    try:
        db_submission_tbl = lookup_tbl_in_database(
            db_tbl_name = ["submission"],
            return_var  = ["*"]
        )
        # If no submissions found, return an empty list
        if db_submission_tbl.shape[0] == 0:
            return {"submission_info": []}
        else:
            return {"submission_info": db_submission_tbl.to_dicts()}
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))    

    
# ---------- Retrieve SeqSender submission details ----------    
@app.get("/retrieve/submission", response_model=Optional[Dict[str, Any]], summary="Retrieve SeqSender submission details", tags=["Submission Utils"])
async def get_submission_info(
    submission_name: str = Query(..., description="Name of the submission."),
    organism: Literal[tuple(organisms)] = Query(..., description="Type of organisms to submit."),
    database: List[Literal[tuple(database_targets)]] = Query(..., description="One or more databases to submit to."),
    submission_type: Literal[tuple(submission_types)] = Query(..., description="Type of submission.")
):
    """
    Retrieve SeqSender submission details for a given submission name, organism, database, and submission type. 
    The function will return a list of dictionaries containing the details of the submission.
    """
    try:
        result = await asyncio.to_thread(
            retrieve_submission,
            submission_name = submission_name,
            organism = organism,
            database = database,
            submission_type = submission_type
        )
        return result
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))    


# ---------- Copy an existing SeqSender submission ----------
@app.post("/copy/submission", response_model=Dict[str, Any], summary="Copy a SeqSender submission to a new name", tags=["Submission Utils"])
async def copy_submission(req: CopySubmissionRequest):
    """
    Duplicate an existing SeqSender submission — including its database rows and
    on-disk submission folder (config, metadata, FASTA, raw reads, etc.) — under a new name.
    """
    try:
        result = await asyncio.to_thread(
            copy_seqsender_submission,
            submission_name = req.submission_name,
            organism = req.organism,
            new_submission_name = req.new_submission_name,
        )
        return result
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))


# ---------- Update a SeqSender submission's comments ----------
@app.patch("/update/submission/comments", response_model=Dict[str, Any], summary="Update the comments for a SeqSender submission's database row", tags=["Submission Utils"])
async def update_submission_comments(req: UpdateSubmissionCommentsRequest):
    """
    Update the free-text comments field for a single database row of a stored submission.
    """
    try:
        result = await asyncio.to_thread(
            update_seqsender_submission_comments,
            submission_name = req.submission_name,
            organism = req.organism,
            database = req.database,
            submission_type = req.submission_type,
            comments = req.comments,
        )
        return result
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))


# ---------- Update a SeqSender submission's status report messages ----------
@app.patch("/update/submission/status_report/messages", response_model=Dict[str, Any], summary="Update the user-edited messages in a SeqSender submission's status report", tags=["Submission Utils"])
async def update_submission_status_report_messages(req: UpdateSubmissionStatusReportMessagesRequest):
    """
    Persist edited Message values from the status report table back into the stored
    submission_status_report.csv for one database, keyed by each row's sample_name.
    """
    try:
        result = await asyncio.to_thread(
            update_seqsender_submission_status_report_messages,
            submission_name = req.submission_name,
            organism = req.organism,
            database = req.database,
            submission_type = req.submission_type,
            messages = req.messages,
        )
        return result
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))


# ---------- Delete an existing SeqSender submission ----------
@app.delete("/delete/submission", response_model=Dict[str, Any], summary="Delete a SeqSender submission from database and disk records", tags=["Submission Utils"])
async def delete_submission(req: DeleteSubmissionRequest):
    """
    Remove a submission's database rows (every database target) and its on-disk
    submission folder (config, metadata, FASTA, raw reads, etc.).
    """
    try:
        result = await asyncio.to_thread(
            delete_seqsender_submission,
            submission_name = req.submission_name,
            organism = req.organism,
        )
        return result
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))


@app.get("/retrieve/config", response_model=Optional[Dict[str, Any]], summary="Retrieve SeqSender config file location", tags=["SeqSender Results"])
async def get_config(
    submission_name: str = Query(..., description="Name of the submission."),
    organism: Literal[tuple(organisms)] = Query(..., description="Organism for which to send sequences."),
    database: List[Literal[tuple(database_targets)]] = Query(..., description="One or more databases to submit to."),
    submission_type: Literal[tuple(submission_types)] = Query(..., description="Type of submission."),
):
    """
    Retrieve SeqSender config file location for a given submission name, organism, database, and submission type. 
    The function will return a dictionary containing the details of the config file location.
    """
    try:
        result = await asyncio.to_thread(
            retrieve_seqsender_config,
            submission_name = submission_name,
            organism = organism,
            database = database,
            submission_type = submission_type
        )
        return result
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
    
    
@app.get("/retrieve/metadata", response_model=Optional[Dict[str, Any]], summary="Retrieve SeqSender metadata file location", tags=["SeqSender Results"])
async def get_metadata(
    submission_name: str = Query(..., description="Name of the submission."),
    organism: Literal[tuple(organisms)] = Query(..., description="Organism for which to send sequences."),
    database: List[Literal[tuple(database_targets)]] = Query(..., description="One or more databases to submit to."),
    submission_type: Literal[tuple(submission_types)] = Query(..., description="Type of submission."),
):
    """
    Retrieve SeqSender metadata file location for a given submission name, organism, database, and submission type. 
    The function will return a list of dictionaries containing the details of the metadata file location.
    """
    try:
        result = await asyncio.to_thread(
            retrieve_seqsender_metadata,
            submission_name = submission_name,
            organism = organism,
            database = database,
            submission_type = submission_type
        )
        return result
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
    
    
@app.get("/retrieve/fasta", response_model=Optional[Dict[str, Any]], summary="Retrieve SeqSender FASTA file location", tags=["SeqSender Results"])
async def get_fasta(
    submission_name: str = Query(..., description="Name of the submission."),
    organism: Literal[tuple(organisms)] = Query(..., description="Organism for which to send sequences."),
    database: List[Literal[tuple(database_targets)]] = Query(..., description="One or more databases to submit to."),
    submission_type: Literal[tuple(submission_types)] = Query(..., description="Type of submission."),
):
    """
    Retrieve SeqSender FASTA file location for a given submission name, organism, database, and submission type. 
    The function will return a dictionary containing the details of the FASTA file location.
    """
    try:
        result = await asyncio.to_thread(
            retrieve_seqsender_fasta,
            submission_name = submission_name,
            organism = organism,
            database = database,
            submission_type = submission_type
        )
        return result
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))


@app.get("/retrieve/gff", response_model=Optional[Dict[str, Any]], summary="Retrieve SeqSender GFF file location", tags=["SeqSender Results"])
async def get_gff(
    submission_name: str = Query(..., description="Name of the submission."),
    organism: Literal[tuple(organisms)] = Query(..., description="Organism for which to send sequences."),
    database: List[Literal[tuple(database_targets)]] = Query(..., description="One or more databases to submit to."),
    submission_type: Literal[tuple(submission_types)] = Query(..., description="Type of submission."),
):
    """
    Retrieve SeqSender GFF file location for a given submission name, organism, database, and submission type. 
    The function will return a dictionary containing the details of the GFF file location.
    """
    try:
        result = await asyncio.to_thread(
            retrieve_seqsender_gff,
            submission_name = submission_name,
            organism = organism,
            database = database,
            submission_type = submission_type
        )
        return result
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
    

@app.get("/retrieve/table2asn", response_model=Optional[Dict[str, Any]], summary="Retrieve SeqSender table2asn file location", tags=["SeqSender Results"])
async def get_table2asn(
    submission_name: str = Query(..., description="Name of the submission."),
    organism: Literal[tuple(organisms)] = Query(..., description="Organism for which to send sequences."),
    database: List[Literal[tuple(database_targets)]] = Query(..., description="One or more databases to submit to."),
    submission_type: Literal[tuple(submission_types)] = Query(..., description="Type of submission."),
):
    """
    Retrieve SeqSender table2asn file location for a given submission name, organism, database, and submission type. 
    The function will return a dictionary containing the details of the table2asn file location.
    """
    try:
        result = await asyncio.to_thread(
            retrieve_seqsender_table2asn,
            submission_name = submission_name,
            organism = organism,
            database = database,
            submission_type = submission_type
        )
        return result
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))  
    
      
@app.get("/retrieve/gisaid_cli", response_model=Optional[Dict[str, Any]], summary="Retrieve SeqSender GISAID CLI file location", tags=["SeqSender Results"])
async def get_gisaid_cli(
    submission_name: str = Query(..., description="Name of the submission."),
    organism: Literal[tuple(organisms)] = Query(..., description="Organism for which to send sequences."),
    database: List[Literal[tuple(database_targets)]] = Query(..., description="One or more databases to submit to."),
    submission_type: Literal[tuple(submission_types)] = Query(..., description="Type of submission."),
):
    """
    Retrieve SeqSender GISAID CLI file location for a given submission name, organism, database, and submission type. 
    The function will return a dictionary containing the details of the GISAID CLI file location.
    """
    try:
        result = await asyncio.to_thread(
            retrieve_seqsender_gisaid_cli,
            submission_name = submission_name,
            organism = organism,
            database = database,
            submission_type = submission_type
        )
        return result
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))      
    

@app.get("/retrieve/submission_log", response_model=Optional[Dict[str, Any]], summary="Retrieve SeqSender submission log location", tags=["SeqSender Results"])
async def get_submission_log(
    submission_name: str = Query(..., description="Name of the submission."),
    organism: Literal[tuple(organisms)] = Query(..., description="Organism for which to send sequences."),
    database: List[Literal[tuple(database_targets)]] = Query(..., description="One or more databases to submit to."),
    submission_type: Literal[tuple(submission_types)] = Query(..., description="Type of submission."),
):
    """
    Retrieve SeqSender submission log location for a given submission name, organism, database, and submission type. 
    The function will return a dictionary containing the details of the submission log location.
    """
    try:
        result = await asyncio.to_thread(
            retrieve_seqsender_submission_log,
            submission_name = submission_name,
            organism = organism,
            database = database,
            submission_type = submission_type
        )
        return result
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
    

@app.get("/retrieve/submission_status", response_model=Optional[Dict[str, Any]], summary="Retrieve SeqSender submission status file location", tags=["SeqSender Results"])
async def get_submission_status(
    submission_name: str = Query(..., description="Name of the submission."),
    organism: Literal[tuple(organisms)] = Query(..., description="Organism for which to send sequences."),
    database: List[Literal[tuple(database_targets)]] = Query(..., description="One or more databases to submit to."),
    submission_type: Literal[tuple(submission_types)] = Query(..., description="Type of submission."),
):
    """
    Retrieve SeqSender submission status file location for a given submission name, organism, database, and submission type. 
    The function will return a dictionary containing the details of the submission status file location.
    """
    try:
        result = await asyncio.to_thread(
            retrieve_seqsender_status_report,
            submission_name = submission_name,
            organism = organism,
            database = database,
            submission_type = submission_type
        )
        return result
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))    
    

# Download config template
@app.get("/download/seqsender/config_template", response_model=Dict[str, Any], summary="Download config template for a given organism and database", tags=["SeqSender Downloads"])
async def download_config_template():
    """
    Download config template for a given organism and database. 
    The function will return a dictionary containing the details of the config template file location.
    """
    if not os.path.exists(CONFIG_TEMPLATE_PATH):
        raise HTTPException(status_code=404, detail=f"Config template not found.")
    return FileResponse(path=CONFIG_TEMPLATE_PATH, filename="config_template.yaml", media_type="application/octet-stream", content_disposition_type="attachment")


# Download metadata template 
@app.get("/download/seqsender/metadata_template", summary="Download a SeqSender-generated metadata template for a given organism and database", tags=["SeqSender Downloads"])
async def download_metadata_template(
    organism: Literal[tuple(organisms)] = Query(..., description="Organism for which to generate the metadata template."),
    database: List[Literal[tuple(database_targets)]] = Query(..., description="One or more databases the metadata template should cover."),
):
    """
    Generate (via SeqSender's own `test_data` command) and download a metadata template
    shaped for the selected organism and database targets.
    """
    try:
        file_path = await asyncio.to_thread(
            retrieve_seqsender_metadata_template,
            organism = organism,
            database = database,
        )
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
    return FileResponse(path=file_path, filename=f"{organism.lower()}_metadata_template.csv", media_type="application/octet-stream", content_disposition_type="attachment")


# Download config file for a given organism and database
@app.get("/download/seqsender/config", response_model=Dict[str, Any], summary="Download config file for a given organism and database", tags=["SeqSender Downloads"])
async def download_config(
    submission_name: str = Query(..., description="Name of the submission."),
    organism: Literal[tuple(organisms)] = Query(..., description="Organism for which to send sequences."),
    database: List[Literal[tuple(database_targets)]] = Query(..., description="One or more databases to submit to."),
    submission_type: Literal[tuple(submission_types)] = Query(..., description="Type of submission."),
):
    """
    Download config file for a given organism and database. 
    The function will return a dictionary containing the details of the config file location.
    """
    file_path = await asyncio.to_thread(
        retrieve_seqsender_config,
        submission_name = submission_name,
        organism = organism,
        database = database,
        submission_type = submission_type
    )
    if file_path is None or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"Config file not found.")
    return FileResponse(path=file_path, filename=f"{submission_name}_{CONFIG_FILENAME}", media_type="application/octet-stream", content_disposition_type="attachment") 


# Download metadata file for a given organism and database
@app.get("/download/seqsender/metadata", response_model=Dict[str, Any], summary="Download metadata file for a given organism and database", tags=["SeqSender Downloads"])
async def download_metadata(
    submission_name: str = Query(..., description="Name of the submission."),
    organism: Literal[tuple(organisms)] = Query(..., description="Organism for which to send sequences."),
    database: List[Literal[tuple(database_targets)]] = Query(..., description="One or more databases to submit to."),
    submission_type: Literal[tuple(submission_types)] = Query(..., description="Type of submission."),
):
    """
    Download metadata file for a given organism and database. 
    The function will return a dictionary containing the details of the metadata file location.
    """
    try:
        file_path = await asyncio.to_thread(
            retrieve_seqsender_metadata,
            submission_name = submission_name,
            organism = organism,
            database = database,
            submission_type = submission_type
        )
        if file_path is None or not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"Metadata file not found.")
        return FileResponse(path=file_path, filename=f"{submission_name}_{METADATA_FILENAME}", media_type="application/octet-stream", content_disposition_type="attachment") 
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Download fasta file for a given organism and database
@app.get("/download/seqsender/fasta", response_model=Dict[str, Any], summary="Download fasta file for a given organism and database", tags=["SeqSender Downloads"])
async def download_fasta(
    submission_name: str = Query(..., description="Name of the submission."),
    organism: Literal[tuple(organisms)] = Query(..., description="Organism for which to send sequences."),
    database: List[Literal[tuple(database_targets)]] = Query(..., description="One or more databases to submit to."),
    submission_type: Literal[tuple(submission_types)] = Query(..., description="Type of submission."),
):
    """
    Download fasta file for a given organism and database. 
    The function will return a dictionary containing the details of the fasta file location.
    """
    try:
        file_path = await asyncio.to_thread(
            retrieve_seqsender_fasta,
            submission_name = submission_name,
            organism = organism,
            database = database,
            submission_type = submission_type
        )
        if file_path is None or not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"FASTA file not found.")
        return FileResponse(path=file_path, filename=f"{submission_name}_{FASTA_FILENAME}", media_type="application/octet-stream", content_disposition_type="attachment") 
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Download all raw read files for a given submission as a ZIP archive
@app.get("/download/seqsender/raw_reads", summary="Download raw read files for a given submission", tags=["SeqSender Downloads"])
async def download_raw_reads(
    submission_name: str = Query(..., description="Name of the submission."),
    organism: Literal[tuple(organisms)] = Query(..., description="Organism for which to send sequences."),
    database: List[Literal[tuple(database_targets)]] = Query(..., description="One or more databases to submit to."),
    submission_type: Literal[tuple(submission_types)] = Query(..., description="Type of submission."),
):
    try:
        file_paths = await asyncio.to_thread(
            retrieve_seqsender_raw_reads,
            submission_name = submission_name,
            organism = organism,
            database = database,
            submission_type = submission_type
        )

        # Create a temporary ZIP file to store the raw read files
        temp_file = tempfile.NamedTemporaryFile(prefix="seqsender_raw_reads_", suffix=".zip", delete=False)
        temp_file.close()
        try:
            with zipfile.ZipFile(temp_file.name, "w", compression=zipfile.ZIP_STORED) as archive:
                for file_path in file_paths:
                    archive.write(file_path, arcname=os.path.basename(file_path))
        except Exception:
            os.unlink(temp_file.name)
            raise

        # Return the ZIP file as a response
        return FileResponse(
            path=temp_file.name,
            filename=f"{submission_name}_raw_reads.zip",
            media_type="application/zip",
            content_disposition_type="attachment",
            background=BackgroundTask(os.unlink, temp_file.name)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Download gff file for a given organism and database
@app.get("/download/seqsender/gff", response_model=Dict[str, Any], summary="Download gff file for a given organism and database", tags=["SeqSender Downloads"])
async def download_gff(
    submission_name: str = Query(..., description="Name of the submission."),
    organism: Literal[tuple(organisms)] = Query(..., description="Organism for which to send sequences."),
    database: List[Literal[tuple(database_targets)]] = Query(..., description="One or more databases to submit to."),
    submission_type: Literal[tuple(submission_types)] = Query(..., description="Type of submission."),
):
    """
    Download gff file for a given organism and database. 
    The function will return a dictionary containing the details of the gff file location.
    """
    try:
        file_path = await asyncio.to_thread(
            retrieve_seqsender_gff,
            submission_name = submission_name,
            organism = organism,
            database = database,
            submission_type = submission_type
        )
        if file_path is None or not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"GFF file not found.")
        return FileResponse(path=file_path, filename=f"{submission_name}_{GFF_FILENAME}", media_type="application/octet-stream", content_disposition_type="attachment") 
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Download table2asn file for a given organism and database
@app.get("/download/seqsender/table2asn", response_model=Dict[str, Any], summary="Download table2asn file for a given organism and database", tags=["SeqSender Downloads"])
async def download_table2asn(
    submission_name: str = Query(..., description="Name of the submission."),
    organism: Literal[tuple(organisms)] = Query(..., description="Organism for which to send sequences."),
    database: List[Literal[tuple(database_targets)]] = Query(..., description="One or more databases to submit to."),
    submission_type: Literal[tuple(submission_types)] = Query(..., description="Type of submission."),
):
    """
    Download table2asn file for a given organism and database. 
    The function will return a dictionary containing the details of the table2asn file location.
    """
    try:
        file_path = await asyncio.to_thread(
            retrieve_seqsender_table2asn,
            submission_name = submission_name,
            organism = organism,
            database = database,
            submission_type = submission_type
        )
        if file_path is None or not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"table2asn file not found.")
        return FileResponse(path=file_path, filename=f"{submission_name}_{TABLE2ASN_FILENAME}", media_type="application/octet-stream", content_disposition_type="attachment") 
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))