# Import future annotations for Pydantic models
from __future__ import annotations
import os
import os
from typing import List, Optional, Literal, Dict, Any

# Import polars
import polars as pl

# Import local schema modules
from .schema_validator import (
    _DEFAULT_SEQSENDER_STORAGE_PATH,
    CONFIG_FILENAME,
    METADATA_FILENAME,
    FASTA_FILENAME,
    GFF_FILENAME,
    TABLE2ASN_FILENAME,
    SUBMISSION_LOG_FILENAME,
    SUBMISSION_STATUS_REPORT_FILENAME,
    validate_tbl,
    submission_db_schema,
    submission_pa_schema,
)

# Import local sqlite modules
from .sqlite_handler import (
    lookup_tbl_in_database,
    insert_tbl_to_database,
)

# Import local utils
from .utils import (
    _cast_expr,
    compare_and_update_db_table,
)

# Function to update the submission worksheet in the database with the provided submission information
def update_submission_in_database(
    submission_name: str,
    organism: str,
    database: List[str],
    submission_type: str,
    submission_tbl: pl.DataFrame,
    return_tbl: bool = False
) -> Optional[pl.DataFrame]:
    """
    Update the submission worksheet in the database with the provided submission information.
    
    Args:
        submission_name (str): Name of the submission.
        organism (str): Type of organism.
        database (List[str]): List of databases to submit to.
        submission_type (str): Type of submissions: Test or Production.
        submission_tbl (pl.DataFrame): Submission table containing submission information.
        return_tbl (bool, optional): Whether to return the updated submission table. Defaults to False.

    Returns:
        Optional[pl.DataFrame]: Updated submission table if return_tbl is True, otherwise None.
    """
    try:
        # Check if submission for this submission_name exists in database
        db_submission_tbl = lookup_tbl_in_database(
            db_tbl_name = ["submission"],
            return_var = ["*"],
            filter_coln_var = ["submission_name", "organism", "database", "submission_type"],
            filter_coln_val = {"submission_name": [submission_name], "organism": [organism], "database": [database], "submission_type": [submission_type]},
            filter_var_by = ["AND", "AND", "AND", "AND"]
        )
        # Make sure db table match the schema data types
        db_submission_tbl = db_submission_tbl.with_columns([
            _cast_expr(col, submission_db_schema.columns[col].dtype.type) for col in submission_db_schema.columns
        ])
        # Validate db table against the schema
        db_submission_tbl = validate_tbl(db_submission_tbl, submission_db_schema, "submission")
        # Make sure submission table match the schema data types
        submission_tbl = submission_tbl.with_columns([
            _cast_expr(col, submission_pa_schema.columns[col].dtype.type) for col in submission_pa_schema.columns
        ])
        # Validate submission table against the schema
        submission_tbl = validate_tbl(submission_tbl, submission_pa_schema, "submission")
        # Check if db_submission_tbl is empty, if so insert new submission_tbl to database
        if db_submission_tbl.is_empty():
            insert_tbl_to_database(
                db_tbl_name = ["submission"],
                table = submission_tbl
            )
        else:
            # Compare and update database table
            compare_and_update_db_table(
                unique_cols = ["submission_name", "organism", "database", "submission_type"],
                compare_tbl = submission_tbl,
                db_tbl = db_submission_tbl,
                db_tbl_name = "submission"
            )    
    except ValueError as err:
        raise ValueError(str(err))
    except Exception as err:
        raise Exception(str(err))
    # Whether to return database table
    if return_tbl:
        db_submission_tbl = lookup_tbl_in_database(
            db_tbl_name = ["submission"],
            return_var = ["*"],
            filter_coln_var = ["submission_name", "organism", "database", "submission_type"],
            filter_coln_val = {"submission_name": [submission_name], "organism": [organism], "database": [database], "submission_type": [submission_type]},
            filter_var_by = ["AND", "AND", "AND", "AND"]
        )
        return db_submission_tbl
    else:
        return None
    

# Retrieve submission information from the database for a given submission name, organism, database, and submission type
def retrieve_submission(
    submission_name: str,
    organism: str,
    database: List[str],
    submission_type: str
) -> Dict[str, Any]:
    """
    Retrieve submission information from the database for a given submission name, organism, database, and submission type.
    
    Args:
        submission_name (str): Name of the submission.
        organism (str): Type of organism.
        database (List[str]): List of databases to submit to.
        submission_type (str): Type of submissions: Test or Production.

    Returns:
        Dict[str, Any]: Dictionary containing the status, message, and submission information.
    """
    try:
        # Check if submission for this submission_name exists in database
        db_submission_tbl = lookup_tbl_in_database(
            db_tbl_name = ["submission"],
            return_var = ["*"],
            filter_coln_var = ["submission_name", "organism", "database", "submission_type"],
            filter_coln_val = {"submission_name": [submission_name], "organism": [organism], "database": [database], "submission_type": [submission_type]},
            filter_var_by = ["AND", "AND", "AND", "AND"]
        )
        if db_submission_tbl.is_empty():
            return {
                "submission_info": None,
                "message": f"Submission '{submission_name}' does not exist in the database.",
            }
        else:
            return {
                "submission_info": db_submission_tbl.to_dicts(),
                "message": f"Submission '{submission_name}' has been successfully retrieved.",
            }
    except ValueError as err:
        raise ValueError(str(err))
    except Exception as err:
        raise Exception(str(err))


# Create a SeqSender submission for a given submission name, organism, database, and submission type
def create_seqsender_submission(
    submission_name: str,
    organism: str,
    database: List[str],
    submission_type: str,
    database_status: List[str],
    gff_file: Optional[bool] = False,
    table2asn: Optional[bool] = False,
) -> Dict[str, Any]:
    try:
        # Create submission table
        submission_tbl = pl.DataFrame({
            "submission_name": [submission_name],
            "organism": [organism],
            "database": [database],
            "database_status": [database_status],
            "submission_type": [submission_type],
            "gff_file": [gff_file],
            "table2asn": [table2asn],
        })
        # Define the submission directory
        submission_dir = os.path.realpath(os.path.join(_DEFAULT_SEQSENDER_STORAGE_PATH, organism))
        submission_name_dir = os.path.join(submission_dir, submission_name)
        # Check if config, metadata, and fasta files exist in the submission directory
        config_file_path = os.path.join(submission_name_dir, CONFIG_FILENAME)
        if not os.path.exists(config_file_path):
            raise ValueError(f"Config file '{CONFIG_FILENAME}' does not exist in submission directory '{submission_name_dir}'.")
        metadata_file_path = os.path.join(submission_name_dir, METADATA_FILENAME)
        if not os.path.exists(metadata_file_path):
            raise ValueError(f"Metadata file '{METADATA_FILENAME}' does not exist in submission directory '{submission_name_dir}'.")
        fasta_file_path = os.path.join(submission_name_dir, FASTA_FILENAME)
        if not os.path.exists(fasta_file_path):
            raise ValueError(f"FASTA file '{FASTA_FILENAME}' does not exist in submission directory '{submission_name_dir}'.")
        # If gff file is true, check if it exists
        if gff_file:
            gff_file_path = os.path.join(submission_name_dir, GFF_FILENAME)
            if not os.path.exists(gff_file_path):
                raise ValueError(f"GFF file '{GFF_FILENAME}' does not exist in submission directory '{submission_name_dir}'.")
        # If table2asn is true, check if it exists
        if table2asn:
            table2asn_file_path = os.path.join(submission_name_dir, "table2asn")
            if not os.path.exists(table2asn_file_path):
                raise ValueError(f"Table2asn file 'table2asn' does not exist in submission directory '{submission_name_dir}'.")
        # If GISAID is in the database list, check if gisaid cli file exists
        if "GISAID" in database:
            gisaid_cli_file_path = os.path.join(submission_dir, "gisaid_cli")
            if not os.path.exists(gisaid_cli_file_path):
                raise ValueError(f"GISAID CLI does not exist in submission directory '{submission_name_dir}'.")
        # Update submission worksheet in database
        db_submission_tbl = update_submission_in_database(
            submission_name = submission_name,
            organism = organism,
            database = database,
            submission_type = submission_type,
            submission_tbl = submission_tbl,
            return_tbl = True
        )
        # Return
        return {
            "status":  "success",
            "message": f"Submission '{submission_name}' has been successfully created.",
            "submission_info": db_submission_tbl.to_dicts(),
        }
    except ValueError as err:
        raise ValueError(str(err))
    except Exception as err:
        raise Exception(str(err))
    

# Retrieve submission config file for a given submission name, organism, database, and submission type
def retrieve_seqsender_config(
    submission_name: str,
    organism: str,
    database: List[str],
    submission_type: str
) -> Dict[str, Any]:
    """
    Retrieve submission config for a given submission name, organism, database, and submission type.
    
    Args:
        submission_name (str): Name of the submission.
        organism (str): Type of organism.
        database (List[str]): List of databases to submit to.
        submission_type (str): Type of submissions: Test or Production.

    Returns:
        str: Path to the submission config file.
    """
    try:
        # Check if submission for this submission_name exists in database
        db_submission_tbl = lookup_tbl_in_database(
            db_tbl_name = ["submission"],
            return_var = ["*"],
            filter_coln_var = ["submission_name", "organism", "database", "submission_type"],
            filter_coln_val = {"submission_name": [submission_name], "organism": [organism], "database": [database], "submission_type": [submission_type]},
            filter_var_by = ["AND", "AND", "AND", "AND"]
        )
        if db_submission_tbl.shape[0] == 0:
           raise ValueError(f"Submission '{submission_name}' does not exist in the database.")
        # Retrieve config file path
        submission_dir = os.path.realpath(os.path.join(_DEFAULT_SEQSENDER_STORAGE_PATH, organism))
        submission_name_dir = os.path.join(submission_dir, submission_name)
        config_file_path = os.path.join(submission_name_dir, CONFIG_FILENAME)
        if not os.path.exists(config_file_path):
            raise ValueError(f"Config file '{CONFIG_FILENAME}' does not exist in submission directory '{submission_name_dir}'.")
        # Return file path
        return config_file_path
    except ValueError as err:
        raise ValueError(str(err))
    except Exception as err:
        raise Exception(str(err))
    

# Retrieve submission metadata for a given submission name, organism, database, and submission type
def retrieve_seqsender_metadata(
    submission_name: str,
    organism: str,
    database: List[str],
    submission_type: str
) -> Dict[str, Any]:
    """
    Retrieve submission metadata for a given submission name, organism, database, and submission type.
    
    Args:
        submission_name (str): Name of the submission.
        organism (str): Type of organism.
        database (List[str]): List of databases to submit to.
        submission_type (str): Type of submissions: Test or Production.

    Returns:
        str: Path to the submission metadata file.
    """
    try:
        # Check if submission for this submission_name exists in database
        db_submission_tbl = lookup_tbl_in_database(
            db_tbl_name = ["submission"],
            return_var = ["*"],
            filter_coln_var = ["submission_name", "organism", "database", "submission_type"],
            filter_coln_val = {"submission_name": [submission_name], "organism": [organism], "database": [database], "submission_type": [submission_type]},
            filter_var_by = ["AND", "AND", "AND", "AND"]
        )
        if db_submission_tbl.shape[0] == 0:
           raise ValueError(f"Submission '{submission_name}' does not exist in the database.")
        # Retrieve metadata file path
        submission_dir = os.path.realpath(os.path.join(_DEFAULT_SEQSENDER_STORAGE_PATH, organism))
        submission_name_dir = os.path.join(submission_dir, submission_name)
        metadata_file_path = os.path.join(submission_name_dir, METADATA_FILENAME)
        if not os.path.exists(metadata_file_path):
            raise ValueError(f"Metadata file '{METADATA_FILENAME}' does not exist in submission directory '{submission_name_dir}'.")
        # Return file path
        return metadata_file_path
    except ValueError as err:
        raise ValueError(str(err))
    except Exception as err:
        raise Exception(str(err))

    
# Retrieve submission fasta file for a given submission name, organism, database, and submission type
def retrieve_seqsender_fasta(
    submission_name: str,
    organism: str,
    database: List[str],
    submission_type: str
) -> Dict[str, Any]:
    """
    Retrieve submission fasta file for a given submission name, organism, database, and submission type.
    
    Args:
        submission_name (str): Name of the submission.
        organism (str): Type of organism.
        database (List[str]): List of databases to submit to.
        submission_type (str): Type of submissions: Test or Production.

    Returns:
        str: Path to the submission fasta file.
    """
    try:
        # Check if submission for this submission_name exists in database
        db_submission_tbl = lookup_tbl_in_database(
            db_tbl_name = ["submission"],
            return_var = ["*"],
            filter_coln_var = ["submission_name", "organism", "database", "submission_type"],
            filter_coln_val = {"submission_name": [submission_name], "organism": [organism], "database": [database], "submission_type": [submission_type]},
            filter_var_by = ["AND", "AND", "AND", "AND"]
        )
        if db_submission_tbl.shape[0] == 0:
           raise ValueError(f"Submission '{submission_name}' does not exist in the database.")
        # Retrieve metadata file path
        submission_dir = os.path.realpath(os.path.join(_DEFAULT_SEQSENDER_STORAGE_PATH, organism))
        submission_name_dir = os.path.join(submission_dir, submission_name)
        fasta_file_path = os.path.join(submission_name_dir, FASTA_FILENAME)
        if not os.path.exists(fasta_file_path):
            raise ValueError(f"Fasta file '{FASTA_FILENAME}' does not exist in submission directory '{submission_name_dir}'.")
        # Return file path
        return fasta_file_path
    except ValueError as err:
        raise ValueError(str(err))
    except Exception as err:
        raise Exception(str(err))   


# Retrieve gff file for a given submission name, organism, database, and submission type
def retrieve_seqsender_gff(
    submission_name: str,
    organism: str,
    database: List[str],
    submission_type: str
) -> Dict[str, Any]:
    """
    Retrieve submission gff file for a given submission name, organism, database, and submission type.
    
    Args:
        submission_name (str): Name of the submission.
        organism (str): Type of organism.
        database (List[str]): List of databases to submit to.
        submission_type (str): Type of submissions: Test or Production.

    Returns:
        str: Path to the submission gff file.
    """
    try:
        # Check if submission for this submission_name exists in database
        db_submission_tbl = lookup_tbl_in_database(
            db_tbl_name = ["submission"],
            return_var = ["*"],
            filter_coln_var = ["submission_name", "organism", "database", "submission_type"],
            filter_coln_val = {"submission_name": [submission_name], "organism": [organism], "database": [database], "submission_type": [submission_type]},
            filter_var_by = ["AND", "AND", "AND", "AND"]
        )
        if db_submission_tbl.shape[0] == 0:
           raise ValueError(f"Submission '{submission_name}' does not exist in the database.")
        # Retrieve metadata file path
        submission_dir = os.path.realpath(os.path.join(_DEFAULT_SEQSENDER_STORAGE_PATH, organism))
        submission_name_dir = os.path.join(submission_dir, submission_name)
        gff_file_path = os.path.join(submission_name_dir, GFF_FILENAME)
        if not os.path.exists(gff_file_path):
            raise ValueError(f"GFF file '{GFF_FILENAME}' does not exist in submission directory '{submission_name_dir}'.")
        # Return file path
        return gff_file_path
    except ValueError as err:
        raise ValueError(str(err))
    except Exception as err:
        raise Exception(str(err))   


# Retrieve table2asn file for a given submission name, organism, database, and submission type
def retrieve_seqsender_table2asn(
    submission_name: str,
    organism: str,
    database: List[str],
    submission_type: str
) -> Dict[str, Any]:
    """
    Retrieve submission table2asn file for a given submission name, organism, database, and submission type.
    
    Args:
        submission_name (str): Name of the submission.
        organism (str): Type of organism.
        database (List[str]): List of databases to submit to.
        submission_type (str): Type of submissions: Test or Production.

    Returns:
        str: Path to the submission table2asn file.
    """
    try:
        # Check if submission for this submission_name exists in database
        db_submission_tbl = lookup_tbl_in_database(
            db_tbl_name = ["submission"],
            return_var = ["*"],
            filter_coln_var = ["submission_name", "organism", "database", "submission_type"],
            filter_coln_val = {"submission_name": [submission_name], "organism": [organism], "database": [database], "submission_type": [submission_type]},
            filter_var_by = ["AND", "AND", "AND", "AND"]
        )
        if db_submission_tbl.shape[0] == 0:
           raise ValueError(f"Submission '{submission_name}' does not exist in the database.")
        # Retrieve metadata file path
        submission_dir = os.path.realpath(os.path.join(_DEFAULT_SEQSENDER_STORAGE_PATH, organism))
        submission_name_dir = os.path.join(submission_dir, submission_name)
        table2asn_file_path = os.path.join(submission_name_dir, TABLE2ASN_FILENAME)
        if not os.path.exists(table2asn_file_path):
            raise ValueError(f"Table2asn file '{TABLE2ASN_FILENAME}' does not exist in submission directory '{submission_name_dir}'.")
        # Return file path
        return table2asn_file_path
    except ValueError as err:
        raise ValueError(str(err))
    except Exception as err:
        raise Exception(str(err))   
    

# Retrieve gisaid cli file for a given submission name, organism, database, and submission type
def retrieve_seqsender_gisaid_cli(
    submission_name: str,
    organism: str,
    database: List[str],
    submission_type: str
) -> Dict[str, Any]:
    """
    Retrieve submission GISAID CLI file for a given submission name, organism, database, and submission type.
    
    Args:
        submission_name (str): Name of the submission.
        organism (str): Type of organism.
        database (List[str]): List of databases to submit to.
        submission_type (str): Type of submissions: Test or Production.

    Returns:
        Dict[str, Any]: Dictionary containing the details of the submission GISAID CLI file location.
    """
    try:
        # Check if submission for this submission_name exists in database
        db_submission_tbl = lookup_tbl_in_database(
            db_tbl_name = ["submission"],
            return_var = ["*"],
            filter_coln_var = ["submission_name", "organism", "database", "submission_type"],
            filter_coln_val = {"submission_name": [submission_name], "organism": [organism], "database": [database], "submission_type": [submission_type]},
            filter_var_by = ["AND", "AND", "AND", "AND"]
        )
        if db_submission_tbl.shape[0] == 0:
           raise ValueError(f"Submission '{submission_name}' does not exist in the database.")
        # Retrieve metadata file path
        submission_dir = os.path.realpath(os.path.join(_DEFAULT_SEQSENDER_STORAGE_PATH, organism))
        GISAID_CLI_FILENAME = organism.lower() + "CLI"
        gisaid_cli_file_path = os.path.join(submission_dir, GISAID_CLI_FILENAME)
        if not os.path.exists(gisaid_cli_file_path):
            raise ValueError(f"GISAID CLI file '{GISAID_CLI_FILENAME}' does not exist in submission directory '{submission_dir}'.")
        # Return file path
        return {"gisaid_cli_file_path": gisaid_cli_file_path}
    except ValueError as err:
        raise ValueError(str(err))
    except Exception as err:
        raise Exception(str(err))

    
# Retrieve submission log file for a given submission name, organism, database, and submission type
def retrieve_seqsender_submission_log(
    submission_name: str,
    organism: str,
    database: List[str],
    submission_type: str
) -> Dict[str, Any]:
    """
    Retrieve submission log file for a given submission name, organism, database, and submission type.
    
    Args:
        submission_name (str): Name of the submission.
        organism (str): Type of organism.
        database (List[str]): List of databases to submit to.
        submission_type (str): Type of submissions: Test or Production.

    Returns:
        str: Path to the submission log file.
    """
    try:
        # Check if submission for this submission_name exists in database
        db_submission_tbl = lookup_tbl_in_database(
            db_tbl_name = ["submission"],
            return_var = ["*"],
            filter_coln_var = ["submission_name", "organism", "database", "submission_type"],
            filter_coln_val = {"submission_name": [submission_name], "organism": [organism], "database": [database], "submission_type": [submission_type]},
            filter_var_by = ["AND", "AND", "AND", "AND"]
        )
        if db_submission_tbl.shape[0] == 0:
           raise ValueError(f"Submission '{submission_name}' does not exist in the database.")
        # Retrieve metadata file path
        submission_dir = os.path.realpath(os.path.join(_DEFAULT_SEQSENDER_STORAGE_PATH, organism))
        submission_name_dir = os.path.join(submission_dir, submission_name)
        submission_log_file_path = os.path.join(submission_name_dir, SUBMISSION_LOG_FILENAME)
        if not os.path.exists(submission_log_file_path):
            return None
        else:
            return submission_log_file_path
    except ValueError as err:
        raise ValueError(str(err))
    except Exception as err:
        raise Exception(str(err))
    

# Retrieve submission status report file for a given submission name, organism, database, and submission type
def retrieve_seqsender_submission_status(
    submission_name: str,
    organism: str,
    database: List[str],
    submission_type: str
) -> Dict[str, Any]:
    """
    Retrieve submission status report file for a given submission name, organism, database, and submission type.
    
    Args:
        submission_name (str): Name of the submission.
        organism (str): Type of organism.
        database (List[str]): List of databases to submit to.
        submission_type (str): Type of submissions: Test or Production.

    Returns:
        str: Path to the submission status report file.
    """
    try:
        # Check if submission for this submission_name exists in database
        db_submission_tbl = lookup_tbl_in_database(
            db_tbl_name = ["submission"],
            return_var = ["*"],
            filter_coln_var = ["submission_name", "organism", "database", "submission_type"],
            filter_coln_val = {"submission_name": [submission_name], "organism": [organism], "database": [database], "submission_type": [submission_type]},
            filter_var_by = ["AND", "AND", "AND", "AND"]
        )
        if db_submission_tbl.shape[0] == 0:
           raise ValueError(f"Submission '{submission_name}' does not exist in the database.")
        # Retrieve metadata file path
        submission_dir = os.path.realpath(os.path.join(_DEFAULT_SEQSENDER_STORAGE_PATH, organism))
        submission_name_dir = os.path.join(submission_dir, submission_name)
        submission_status_report_file_path = os.path.join(submission_name_dir, SUBMISSION_STATUS_REPORT_FILENAME)
        if not os.path.exists(submission_status_report_file_path):
            return None
        else:
            return submission_status_report_file_path
    except ValueError as err:
        raise ValueError(str(err))
    except Exception as err:
        raise Exception(str(err))