# Import future annotations for Pydantic models
from __future__ import annotations
from typing import List, Optional, Literal, Dict, Any

# General python packages
import re

# Python packages to work with data frame
import polars as pl

# Import local utils functions
from .conn_handler import init_connection

# Function to check database table
def check_db_table(db_tbl_name: List[str]) -> List[str]:

    # Check db_tbl_name
    if not isinstance(db_tbl_name, list) or len(db_tbl_name) == 0:
        raise ValueError("'db_tbl_name' must be a list and cannot be empty.")

    # Establish database connection
    connection = None
    try:
        connection = init_connection()
        cursor = connection.cursor()

        # Check if table exists in SQLite
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?;",
            (db_tbl_name[0],),
        )
        if cursor.fetchone() is None:
            raise ValueError(f"'{db_tbl_name[0]}' table does not exist in the database.")

        # Get column names via PRAGMA (no full table scan)
        cursor.execute(f'PRAGMA table_info("{db_tbl_name[0]}");')
        return [row[1] for row in cursor.fetchall()]
    except Exception as err:
        raise Exception(f"SQLite Error: {err}") from err
    finally:
        if connection:
            connection.close()

# Function to ingest table to database
def insert_tbl_to_database(db_tbl_name: List[str], table: pl.DataFrame) -> None:

    # Check if db_tbl_name exists in the database
    db_colnames = check_db_table(db_tbl_name=db_tbl_name)

    # Check if table is a non-empty DataFrame
    if not isinstance(table, pl.DataFrame):
        raise ValueError("'table' must be a Polars DataFrame.")
    if table.shape[0] == 0:
        raise ValueError("'table' is empty. Nothing to insert.")

    # Check if all columns in the table exist in the database table
    missing = [col for col in table.columns if col not in db_colnames]
    if missing:
        raise ValueError(f"The following column(s) do not exist in '{db_tbl_name[0]}': {missing}")

    # Build parameterized INSERT to prevent SQL injection (SQLite: "col", ? placeholders)
    _nan_vals = {"nan", "nat", "null", "none"}
    columns      = ", ".join(f'"{col}"' for col in table.columns)
    placeholders = ", ".join("?" * len(table.columns))
    sql_statement = f'INSERT INTO "{db_tbl_name[0]}" ({columns}) VALUES ({placeholders})'
    rows = [
        tuple(
            None if (val == "" or str(val).strip().lower() in _nan_vals) else val
            for val in table.row(i)
        )
        for i in range(table.shape[0])
    ]

    # Establish database connection and execute
    connection = None
    try:
        connection = init_connection()
        connection.executemany(sql_statement, rows)
        connection.commit()
    except Exception as err:
        if connection:
            connection.rollback()
        raise Exception(f"SQLite Error: {err}") from err
    finally:
        if connection:
            connection.close()
  
# Function to lookup/query values in database
def lookup_tbl_in_database(
    db_tbl_name: List[str],
    return_var: List[str] = ["*"],
    filter_coln_var: Optional[List[str]] = None,
    filter_coln_val: Optional[Dict[str, Any]] = None,
    filter_var_by: Optional[List[str]] = None,
    exclude_coln_var: Optional[List[str]] = None,
    exclude_coln_val: Optional[Dict[str, Any]] = None,
) -> pl.DataFrame:
    """
    Query a SQLite table and return matching rows as a Polars DataFrame.
    Returns an empty DataFrame when no rows match — use .is_empty() to check existence.
    """
    # Check if db_tbl_name exists in the database
    db_colnames = check_db_table(db_tbl_name=db_tbl_name)

    # Validate return_var
    if not isinstance(return_var, list) or len(return_var) == 0:
        raise ValueError("'return_var' must be a non-empty list.")

    # Validate filter columns
    if filter_coln_var is not None:
        if not isinstance(filter_coln_var, list):
            raise ValueError("'filter_coln_var' must be a list.")
        if filter_coln_val is None or not isinstance(filter_coln_val, dict):
            raise ValueError("'filter_coln_val' must be a dict when 'filter_coln_var' is provided.")
        if len(filter_coln_var) != len(filter_coln_val):
            raise ValueError("'filter_coln_var' and 'filter_coln_val' must have the same length.")
        if any(var not in filter_coln_val for var in filter_coln_var):
            raise ValueError("Every entry in 'filter_coln_var' must have a matching key in 'filter_coln_val'.")
        if len(filter_coln_var) > 1:
            if not filter_var_by or not isinstance(filter_var_by, list):
                raise ValueError("'filter_var_by' is required when more than one filter column is given.")
            if any(op.upper() not in ("AND", "OR") for op in filter_var_by):
                raise ValueError("'filter_var_by' entries must be 'AND' or 'OR'.")
        missing = [c for c in filter_coln_var if c not in db_colnames]
        if missing:
            raise ValueError(f"Column(s) not found in '{db_tbl_name[0]}': {missing}")

    # Validate exclude columns
    if exclude_coln_var is not None:
        if not isinstance(exclude_coln_var, list):
            raise ValueError("'exclude_coln_var' must be a list.")
        if exclude_coln_val is None or not isinstance(exclude_coln_val, dict):
            raise ValueError("'exclude_coln_val' must be a dict when 'exclude_coln_var' is provided.")
        if any(c not in db_colnames for c in exclude_coln_var):
            raise ValueError(f"Some exclude columns not found in '{db_tbl_name[0]}'.")
        if any(var not in exclude_coln_val for var in exclude_coln_var):
            raise ValueError("Every entry in 'exclude_coln_var' must have a matching key in 'exclude_coln_val'.")

    # Build WHERE clause
    where_parts: List[str] = []
    if filter_coln_var:
        for i, col in enumerate(filter_coln_var):
            vals = ", ".join(f"'{str(v).strip().lower()}'" for v in filter_coln_val[col])
            part = f'trim(lower("{col}")) IN ({vals})'
            where_parts.append(f"{filter_var_by[i - 1].upper()} {part}" if i > 0 else part)
    if exclude_coln_var and exclude_coln_val:
        for col in exclude_coln_var:
            vals = ", ".join(f"'{str(v).strip().lower()}'" for v in exclude_coln_val[col])
            part = f'trim(lower("{col}")) NOT IN ({vals})'
            where_parts.append(f"AND {part}" if where_parts else part)
    where_clause = ("WHERE " + " ".join(where_parts)) if where_parts else ""

    # Build SELECT clause
    select_cols = ", ".join(col if col == "*" else f'"{col}"' for col in return_var)
    sql = f'SELECT DISTINCT {select_cols}\nFROM "{db_tbl_name[0]}"\n{where_clause}'.strip()
    sql = re.sub(r"'nan'|'NaN'|'NaT'|'null'|'none'", "NULL", sql, flags=re.IGNORECASE)

    # Execute and return
    connection = None
    try:
        connection = init_connection()
        df = pl.read_database(query=sql, connection=connection, infer_schema_length=None)
    except Exception as err:
        raise Exception(f"SQLite Error: {err}") from err
    finally:
        if connection:
            connection.close()

    # Return dataframe
    return df
    
# Update specific rows from a table in the database
def update_tbl_in_database(
    db_tbl_name: List[str], 
    table: pl.DataFrame,
    filter_coln_var: List[str], 
    filter_coln_val: Dict[str, Any], 
    filter_var_by: Optional[List[str]] = None,
) -> None:

    # Check if db_tbl_name exists in the database
    db_colnames = check_db_table(db_tbl_name=db_tbl_name)

    # Check filter_coln_var
    if not isinstance(filter_coln_var, list) or len(filter_coln_var) == 0:
        raise ValueError(f"{'filter_coln_var'} must be list and cannot be empty.")

    # Check filter_coln_val
    if not isinstance(filter_coln_val, dict) or len(filter_coln_val) == 0:
        raise ValueError(f"{'filter_coln_val'} must a dictionary with names or labels that match the values of 'filter_coln_var'.")

    # Check filter_var_by
    if (len(filter_coln_var) > 1 and filter_var_by is None) or (len(filter_coln_var) > 1 and filter_var_by is not None and not isinstance(filter_var_by, list)):
        raise ValueError("{'filter_var_by'} must be list containing a list of AND/OR logical operators.")

    # Check if all columns in the filter list exist in the database table
    if not all(col in db_colnames for col in filter_coln_var):
        raise ValueError(f"The following column(s) does not exist in the '{db_tbl_name}' table of the database: {[col for col in filter_coln_var if col not in db_colnames]}")

    # Check filter_coln_var and filter_coln_val
    if len(filter_coln_var) != len(filter_coln_val):
        raise ValueError("The length of 'filter_coln_var' must equal to the length of 'filter_coln_val'.")
    elif any([var not in filter_coln_val.keys() for var in filter_coln_var]):
        raise ValueError("'filter_coln_val' must a dictionary with names or labels that match the values of 'filter_coln_var'.")
    elif len(filter_coln_var) > 1 and len(filter_var_by) < len(filter_coln_var):
        raise ValueError("The length of 'filter_var_by' must equal to the length of 'filter_coln_var'.")
    elif len(filter_coln_var) > 1 and any([val.upper() not in ["OR", "AND"] for val in filter_var_by]):
        raise ValueError("'filter_var_by' must contain a list of AND/OR logical operators.")
    else:
        # Create a place hodler to store the where clause to look up values
        where_clause = ""
        for s in range(len(filter_coln_var)):
            where_clause += 'trim(lower("{variable}")) IN ({values})'.format(variable=filter_coln_var[s], values=", ".join(["'"+str(val).strip().lower()+"'" for val in filter_coln_val[filter_coln_var[s]]]))
            if s < (len(filter_coln_var) - 1):
                where_clause += " " + str(filter_var_by[s]) + " "
            else:
                where_clause = f"WHERE {where_clause}"

    # Create a place holder to create all inserting values
    column_var = table.columns
    _nan_vals = {"nan", "nat", "null", "none"}

    # Build SET clause and SQL statement once (same structure for every row)
    set_clause = ", ".join(f'"{col}" = ?' for col in column_var)
    sql_statement = f'UPDATE "{db_tbl_name[0]}"\nSET {set_clause}\n{where_clause}'

    # Build all parameter rows upfront
    all_params = [
        tuple(
            None if (val == "" or val is None or str(val).strip().lower() in _nan_vals) else val
            for val in table.row(i)
        )
        for i in range(table.shape[0])
    ]

    # Establish database connection and execute
    connection = None
    try:
        connection = init_connection()
        connection.executemany(sql_statement, all_params)
        connection.commit()
    except Exception as err:
        if connection:
            connection.rollback()
        raise Exception(f"SQLite Error: {err}") from err
    finally:
        if connection:
            connection.close()

# Delete specific rows from a table in the database
def delete_val_in_database(
    db_tbl_name: List[str], 
    delete_coln_var: List[str], 
    delete_coln_val: Dict[str, Any], 
    delete_var_by: Optional[List[str]] = None,
) -> None:
  
    # Check if db_tbl_name exists in the database
    db_colnames = check_db_table(db_tbl_name=db_tbl_name)   
    
    # Check delete_coln_var
    if not isinstance(delete_coln_var, list) or len(delete_coln_var) == 0:
        raise ValueError(f"'delete_coln_var' must be a list and cannot be empty.")

    # Check delete_coln_val
    if not isinstance(delete_coln_val, dict) or len(delete_coln_val) == 0:
        raise ValueError(f"'delete_coln_val' must be a dictionary with names or labels that match the values of 'delete_coln_var'.")
        
    # Check delete_var_by
    if (len(delete_coln_var) > 1 and delete_var_by is None) or (len(delete_coln_var) > 1 and delete_var_by is not None and not isinstance(delete_var_by, list)):
        raise ValueError(f"'delete_var_by' must be a list containing a list of AND/OR logical operators.")
        
    # Check if all columns in the filter list exist in the database table
    if not all(col in db_colnames for col in delete_coln_var):
        raise ValueError(f"The following column(s) does not exist in the '{db_tbl_name}' table of the database: {[col for col in delete_coln_var if col not in db_colnames]}")
        
    # Check delete_coln_var and delete_coln_val
    if len(delete_coln_var) != len(delete_coln_val):
        raise ValueError("The length of 'delete_coln_var' must equal to the length of 'delete_coln_val'.")
    elif any([var not in delete_coln_val.keys() for var in delete_coln_var]):
        raise ValueError("'delete_coln_val' must a dictionary with names or labels that match the values of 'delete_coln_var'.")
    elif len(delete_coln_var) > 1 and len(delete_var_by) < len(delete_coln_var):
        raise ValueError("The length of 'delete_var_by' must equal to the length of 'delete_coln_var'.")
    elif len(delete_coln_var) > 1 and any([val.upper() not in ["OR", "AND"] for val in delete_var_by]):
        raise ValueError("'delete_var_by' must contain a list of AND/OR logical operators.")
    else:        
        # Create a place hodler to store the where clause to look up values
        where_clause = ""
        for s in range(len(delete_coln_var)):
            where_clause += 'trim(lower("{variable}")) IN ({values})'.format(variable=delete_coln_var[s], values=", ".join(["'"+str(val).strip().lower()+"'" for val in delete_coln_val[delete_coln_var[s]]]))
            if s < (len(delete_coln_var) - 1):
                where_clause += " " + str(delete_var_by[s]) + " "
            else:
                where_clause = f"WHERE {where_clause}"
      
    # SQL statement   
    sql_statement = 'DELETE FROM "{table_name}"\n{where_clause}'.format(table_name=db_tbl_name[0], where_clause=where_clause)
    # Establish database connection
    connection = None
    
    # Execute SQL statement
    try:
        connection = init_connection()
        connection.execute(sql_statement)
        connection.commit()
    except Exception as err:
        if connection:
            connection.rollback()
        raise Exception(f"SQLite Error: {err}") from err
    finally:
        if connection:
            connection.close()