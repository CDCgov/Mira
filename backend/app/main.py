# Import future annotations for Pydantic models
from typing import List, Optional, Literal, Dict, Any

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
import zipfile
import requests
from datetime import datetime

# Import asyncio for running blocking operations in a thread
import asyncio

# Import polars for dataframe operations
import polars as pl

# Import schema
from .schema import (
    RunRequest,
    RunResponse,
    RunStatusRequest,
    TaskLogRequest,
    AssemblyRequest,
    DownloadFastaRequest,
    DeleteSampleRequest,
    RenameRunRequest,
    CopyRunRequest,
)

# Import schema validation
from .schema_validator import (
    _DEFAULT_MIRA_STORAGE_PATH,
    _MIRA_NF_VERSION_URL,
    _MIRA_VERSION_URL,
    _MIRA_NF_IMAGE,
    _REACT_PORT,
    validate_tbl,
    experiment_types,
    assembly_pa_schema,
    ont_samplesheet_pa_schema,
    illumina_samplesheet_pa_schema, 
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

# Import sqlite handler for database operations
from .sqlite_handler import (
    lookup_tbl_in_database,
)

# Import shared logger (INFO/DEBUG -> stdout, WARNING/ERROR/CRITICAL -> stderr)
from .logging_config import logger

# Define React base URL and internal base URL for the app
_REACT_BASE_URL = f"http://localhost:{_REACT_PORT}"
_REACT_INTERNAL_BASE_URL = f"http://127.0.0.1:{_REACT_PORT}"

# Define FastAPI app
app = FastAPI(title = "MIRA Backend")

# Compress responses >= 1 KB with gzip (reduces large JSON payloads 5-10x)
app.add_middleware(GZipMiddleware, minimum_size=1000)

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
@app.get("/list/runs", response_model=RunResponse, summary="List all assembly runs", tags=["MIRA Utils"])
async def get_runs():
    """
    Return a list of assembly runs in storage.
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
            f"primer_kmer_len='{req.primer_kmer_len if req.custom_primers and req.primer_kmer_len > 0 else ""}'\n"
            f"primer_restrict_window='{req.primer_restrict_window if req.custom_primers and req.primer_restrict_window > 0 else ""}'\n"
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
    path = await asyncio.to_thread(retrieve_passed_amended_consensus, req.run_name, req.experiment_type)
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="NT passed FASTA not found")
    return FileResponse(path=path, filename=f"{req.run_name}_nt_passed.fasta", media_type="application/octet-stream", content_disposition_type="attachment")

# ---------- Download NT Failed FASTA ----------
@app.get("/download/nt_failed_fasta", summary="Download NT Failed FASTA", tags=["MIRA Downloads"])
async def download_nt_failed_fasta(req: RunRequest = Depends()):
    path = await asyncio.to_thread(retrieve_failed_amended_consensus, req.run_name, req.experiment_type)
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="NT failed FASTA not found")
    return FileResponse(path=path, filename=f"{req.run_name}_nt_failed.fasta", media_type="application/octet-stream", content_disposition_type="attachment")

# ---------- Download AA Passed FASTA ----------
@app.get("/download/aa_passed_fasta", summary="Download AA Passed FASTA", tags=["MIRA Downloads"])
async def download_aa_passed_fasta(req: RunRequest = Depends()):
    path = await asyncio.to_thread(retrieve_passed_amino_acid_consensus, req.run_name, req.experiment_type)
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="AA passed FASTA not found")
    return FileResponse(path=path, filename=f"{req.run_name}_aa_passed.fasta", media_type="application/octet-stream", content_disposition_type="attachment")

# ---------- Download AA Failed FASTA ----------
@app.get("/download/aa_failed_fasta", summary="Download AA Failed FASTA", tags=["MIRA Downloads"])
async def download_aa_failed_fasta(req: RunRequest = Depends()):
    path = await asyncio.to_thread(retrieve_failed_amino_acid_consensus, req.run_name, req.experiment_type)
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="AA failed FASTA not found")
    return FileResponse(path=path, filename=f"{req.run_name}_aa_failed.fasta", media_type="application/octet-stream", content_disposition_type="attachment")

# ---------- Download Custom Primer Config ----------
@app.get("/download/custom_primer_config", summary="Download Custom Primer Config", tags=["MIRA Downloads"])
async def download_custom_primer_config(req: RunRequest = Depends()):
    pathogen = req.experiment_type.split("-")[0]
    instrument = req.experiment_type.split("-")[-1]
    path = os.path.join(_DEFAULT_MIRA_STORAGE_PATH, pathogen, instrument, req.run_name, CUSTOM_PRIMER_CONFIG_FILENAME)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Custom primer config file not found in storage. File may have been moved or deleted. Please re-upload a new custom primer config file if needed or turn off custom primer config.")
    return FileResponse(path=path, filename=CUSTOM_PRIMER_CONFIG_FILENAME, media_type="application/octet-stream", content_disposition_type="attachment")

# ---------- Download Custom IRMA Config ----------
@app.get("/download/custom_irma_config", summary="Download Custom IRMA Config", tags=["MIRA Downloads"])
async def download_custom_irma_config(req: RunRequest = Depends()):
    pathogen = req.experiment_type.split("-")[0]
    instrument = req.experiment_type.split("-")[-1]
    path = os.path.join(_DEFAULT_MIRA_STORAGE_PATH, pathogen, instrument, req.run_name, CUSTOM_IRMA_CONFIG_FILENAME)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Custom IRMA config file not found in storage. File may have been moved or deleted. Please re-upload a new custom IRMA config file if needed or turn off custom IRMA config.")
    return FileResponse(path=path, filename=CUSTOM_IRMA_CONFIG_FILENAME, media_type="application/octet-stream", content_disposition_type="attachment")

# ---------- Download Custom QC Settings ----------
@app.get("/download/custom_qc_settings", summary="Download Custom QC Settings", tags=["MIRA Downloads"])
async def download_custom_qc_settings(req: RunRequest = Depends()):
    pathogen = req.experiment_type.split("-")[0]
    instrument = req.experiment_type.split("-")[-1]
    path = os.path.join(_DEFAULT_MIRA_STORAGE_PATH, pathogen, instrument, req.run_name, CUSTOM_QC_SETTINGS_FILENAME)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Custom QC settings file not found in storage. File may have been moved or deleted. Please re-upload a new custom QC settings file if needed or turn off custom QC settings.")
    return FileResponse(path=path, filename=CUSTOM_QC_SETTINGS_FILENAME, media_type="application/octet-stream", content_disposition_type="attachment")

# ---------- Download Nextclade FASTA (single file by key) ----------
@app.get("/download/nextclade_fasta", summary="Download Nextclade FASTA", tags=["MIRA Downloads"])
async def download_nextclade_fasta(req: DownloadFastaRequest = Depends()):
    files = await asyncio.to_thread(retrieve_nextclade_aligned_fasta, req.run_name, req.experiment_type)
    if not files:
        raise HTTPException(status_code=404, detail=f"No Nextclade FASTA files found for run '{req.run_name}' and experiment type '{req.experiment_type}' and key '{req.key}'.")
    all_keys = list(files.keys())
    path = files.get(req.key) if req.key else None
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"Invalid fasta keys. Available keys: {all_keys}")
    safe_key = req.key if req.key else all_keys[0]
    return FileResponse(path=path, filename=f"{req.run_name}_nextclade_{safe_key}.fasta", media_type="application/octet-stream", content_disposition_type="attachment")

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

