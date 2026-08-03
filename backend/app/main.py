# Import future annotations for Pydantic models
from typing import List, Optional, Literal, Dict, Any

# Import FastAPI and related packages
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, StreamingResponse

# Import general python packages
import os
import io
import json
import shutil
import zipfile

# Import asyncio for running blocking operations in a thread
import asyncio

# Import polars for dataframe operations
import polars as pl

# Import schema
from .schema import (
    RunRequest,
    RunResponse,
    RunStatusRequest,
    AssemblyRequest,
    DownloadFastaRequest,
    DeleteSampleRequest,
)

# Import schema validation
from .schema_validator import (
    _DEFAULT_MIRA_STORAGE_PATH,
    validate_tbl,
    experiment_types,
    assembly_pa_schema,
    ont_samplesheet_pa_schema,
    illumina_samplesheet_pa_schema, 
)

# Import MIRA handler 
from .mira_handler import (
    create_mira_run,
    retrieve_run,
    delete_sample_from_run,
    run_mira_docker,
    create_mira_dag,
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
    retrieve_variants,
    retrieve_minor_snvs,
    retrieve_indels,
    retrieve_failed_amino_acid_consensus,
    retrieve_passed_amino_acid_consensus,
    retrieve_failed_amended_consensus,
    retrieve_passed_amended_consensus,
    retrieve_nextclade_aligned_fasta,
    validate_samplesheet_and_fastqs_in_storage,
)

# Import sqlite handler for database operations
from .sqlite_handler import (
    lookup_tbl_in_database,
)

# Define FastAPI app
app = FastAPI(title = "MIRA Backend")

# Compress responses >= 1 KB with gzip (reduces large JSON payloads 5-10x)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# CORS for your Vite dev server + Nextclade Web (fetches input-fasta directly from the browser)
app.add_middleware(
    CORSMiddleware,
    allow_origins = [
        "http://localhost:5175",
        "http://127.0.0.1:5175",
        "http://localhost:5176",
        "http://127.0.0.1:5176",
        "https://clades.nextstrain.org",
        "https://nextclade.org",
    ],
    allow_credentials = True,
    allow_methods = ["*"],
    allow_headers = ["*"],
)

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
    
# Define function to upload fastq files to MIRA storage location
def upload_fastq_files_to_storage(
    run_name: str,  
    experiment_type: str,
    fastq_files: List[UploadFile],
) -> Dict[str, Any]:
     
    # Extract pathogen and instrument type from experiment_type
    pathogen =experiment_type.split("-")[0]
    instrument =experiment_type.split("-")[-1]
    
    # Retrieve assembly table from database
    db_assembly_tbl = lookup_tbl_in_database(
        db_tbl_name = ["assembly"],
        return_var = ["*"],
        filter_coln_var = ["run_name"],
        filter_coln_val = {"run_name": [run_name]},
        filter_var_by = ["AND"]
    )

    # Extract assembly information from assembly_tbl
    assembly_id = db_assembly_tbl.select("assembly_id").to_series()[0]

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
    fastq_files = [f for f in fastq_files if (f.filename or "").lower().endswith(".fastq.gz")]

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

# ---------- Health Check ----------
@app.get("/health", tags=["Health"], summary="Health check", response_model=Dict[str, bool])
def health():
    return {"ok": True}

##############################################
# 
# MIRA SECTION
# 
##############################################

# ---------- List all runs ----------
@app.get("/list/runs", response_model=RunResponse, summary="List all assembly runs", tags=["MIRA"])
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

# ---------- Search for a specific run----------
@app.get("/search/run", response_model=RunResponse, summary="Search for a specific assembly run", tags=["MIRA"])
async def look_up_run(req: RunRequest = Depends()):
    """
    Search for a specific assembly run based on run name and experiment type.
    """
    # Define filter variables for database query
    filter_coln_var = []; filter_coln_val = {}; filter_var_by = [];
    if req.run_name is not None:
        filter_coln_var.append("run_name")  
        filter_coln_val["run_name"] = [req.run_name]
        filter_var_by.append("AND")
    if req.experiment_type is not None:
        filter_coln_var.append("experiment_type")
        filter_coln_val["experiment_type"] = [req.experiment_type]
        filter_var_by.append("AND")
    # Query the database for assembly runs based on the provided filters
    try:
        db_assembly_tbl = lookup_tbl_in_database(
            db_tbl_name = ["assembly"],
            return_var  = ["*"],
            filter_coln_var = filter_coln_var if filter_coln_var else None,
            filter_coln_val = filter_coln_val if filter_coln_val else None,
            filter_var_by = filter_var_by if filter_var_by else None
        )
        return {"run_info": db_assembly_tbl.to_dicts()}
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
        
# ---------- Retrieve Specific Run Information ----------
@app.get("/retrieve/run", response_model=Optional[Dict[str, Any]], summary="Retrieve a run information", tags=["MIRA"])
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
    
# ---------- Validate samplesheet and all FASTQ files exist for a given sequencing run. ----------
@app.get("/validate/run", response_model=Dict[str, Any], summary="Validate samplesheet and FASTQ files exist for a given sequencing run", tags=["MIRA"])
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
    
# ---------- Delete a single sample from a run's samplesheet ----------
@app.delete("/delete/sample", response_model=Dict[str, Any], summary="Remove a sample from a run's samplesheet", tags=["MIRA"])
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

# ---------- Create a MIRA run (with file uploads) ----------
@app.post(
    "/create/run/upload",
    response_model=Dict[str, Any],
    summary="Create a MIRA run (with File Uploads, Accepted Formats: JSON/CSV/Excel for samplesheet; .fastq.gz for raw reads)",
    tags=["MIRA"],
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
                                "description": "One or more .fastq.gz files — Select `Add string item` to add another import field for additional files.",
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
    fastq_files: List[UploadFile] = File(default=[], description="One or more .fastq.gz files to upload.")
):
    """
    Submit a MIRA assembly run via **file uploads**.
    Accepted formats: JSON / CSV / Excel for assembly and samplesheet; .fastq.gz for reads.
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
@app.post("/create/run", response_model=Dict[str, Any], summary="Create a MIRA run with appropriate samplesheet (Part 1)", tags=["MIRA"])
async def create_run(req: AssemblyRequest):
    """
    Create a MIRA run via a **JSON request body**.
    Use this option when all inputs are available as structured data.
    This endpoint works together with the `/upload/fastqs` endpoint to create a complete MIRA run."""
    try:
        # Create assembly table from request data and validate it
        assembly_tbl    = pl.DataFrame({
            "run_name":          [req.run_name],
            "experiment_type":   [req.experiment_type],
            "subsample":         [req.subsample],
            "sc2_primer":        [req.sc2_primer],
            "rsv_primer":        [req.rsv_primer],
            "parquet_files":     [req.parquet_files],
            "run_nextclade":     [req.run_nextclade],
            "irma_module":       [req.irma_module],
            "custom_irma_config":[req.custom_irma_config],
            "custom_qc_settings":[req.custom_qc_settings],
            "assembly_status":   [req.assembly_status],
        })
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
    summary="Upload FASTQ files to a specific MIRA run (Part 2)", 
    tags=["MIRA"],
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
                                "description": "One or more .fastq.gz files — Select `Add string item` to add another import field for additional files.",
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
    fastq_files:     List[UploadFile]       = File(default=[], description="One or more .fastq.gz files to upload."),
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
    
# ---------- Run MIRA pipeline ----------
@app.get("/run/MIRA", response_model=Dict[str, Any], summary="Run MIRA assembly via Docker (Part 3)", tags=["MIRA"])
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
@app.get("/cancel/MIRA", response_model=Dict[str, Any], summary="Cancel a running MIRA pipeline", tags=["MIRA"])
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
@app.get("/MIRA/status", response_model=Dict[str, Any], summary="Check run process status", tags=["MIRA"])
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
@app.get("/MIRA/DAG", response_model=Dict[str, Any], summary="Get MIRA DAG from assembly", tags=["MIRA"])
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
@app.get("/retrieve/sample_coverage_plot", response_model=Optional[Dict[str, Any]], summary="Retrieve Sample Coverage Plot (Linear)", tags=["MIRA Results"])
async def get_sample_coverage_plot(
    req: RunRequest = Depends(),
    sample_id: str = Query(..., description="Sample ID to retrieve the coverage plot for"),
):
    """
    Retrieve sample coverage plot for a given sequencing run and sample.
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
# SEQSENDER SECTION
# 
##############################################

