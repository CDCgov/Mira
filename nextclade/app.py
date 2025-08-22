# Import flask specific packages
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS, cross_origin

# Import other Python packages
import os
import sys

# Parse arguments package
import argparse

# Add parent directory to sys.path
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, parent_dir)

# Import utils app functions
from utils.app_functions import *

# Initiate application
app = Flask(__name__)

# Define global variables to store data_root
global data_root

# A custom exception class to represent specific errors in application.
class CustomAPIException(Exception):
    def __init__(self, message, status_code):
        super().__init__(message)
        self.message = message
        self.status_code = status_code

@app.errorhandler(CustomAPIException)
def handle_custom_exception(error):
    response = {
        "error": error.message,
        "status_code": error.status_code
    }
    return jsonify(response), error.status_code

@app.route("/fasta", methods=["GET"])
@cross_origin()
def get_fasta():
    # Check parameter
    try:
        seq_run = request.args["seq_run"]   
    except:
        raise CustomAPIException(message="Missing required parameter(s): seq_run", status_code=400)
    # Get fasta file
    fasta_file = f"{data_root}/{seq_run}/amended_consensus.fasta"
    # Check fasta file
    if not os.path.exists(fasta_file):
        raise CustomAPIException(message=f"Fasta does not exists at {fasta_file}", status_code=400)
    else:
        return send_file(fasta_file, as_attachment=True, download_name=f"{seq_run}_amended_consensus.fasta", mimetype='text/plain')

if __name__ == "__main__":
    """
    Argument parser to setup and launch MIRA API
    """
    parser = argparse.ArgumentParser(description="Launch MIRA API")
    parser.add_argument("--host",
        help="The address that the app should listen on. Default 0.0.0.0",
    	  type=str,
      	default="0.0.0.0")
    parser.add_argument("--port",
    		help="The port that the app should listen on. Set to 0 to use a random port. Default 5000",
    	  type=int,
    		default=5000)
    parser.add_argument("--config_file", 
        help="Config file for the app", 
        type=str,
        required=True)
        
    # Get arguments
    args = parser.parse_args()
    
    # Parse config file
    config = get_config(config_file=args.config_file)
    data_root = config["DATA_ROOT"]
    
    # Launch the API
    app.run(host=args.host, port=args.port, debug=True)
