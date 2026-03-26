# Import async packages
import asyncio

# Import shiny packages
from shiny import *
from shinywidgets import *
from itables.widget import ITable

# Import python packages
import io
import re
import os
import json
import pandas as pd
import plotly.io as pio
import plotly.graph_objects as go

# Import specific python package functions
from glob import glob
from pathlib import Path

# Import utils app functions
from utils.app_functions import *

# Import utils global variables
from utils.global_var import *

# Create UI layout
@module.ui
def mira_ui(data_root):
  
    # Define parameters for MIRA assembly
    seq_runs = {i: i for i in sorted(os.listdir(data_root)) if "." not in i}
    
    # Return UI
    return ui.row(
        ui.column(3,
            ui.tags.div(
                ui.tags.a(
                    ui.tags.img(
                        src="logo/apple-touch-icon-152x152.png",
                    ),
                    href="https://cdcgov.github.io/MIRA/articles/running-mira-dd-ont.html",
                    target="_blank",
                ),
                class_="sidebar-logo",
            ),
            ui.tags.p(
                f"MIRA v{get_version()}",
                class_="sidebar-title"
            ), 
            ui.tags.div(
                "Influenza, SARS-CoV-2, and RSV sequence assembly with ",
                ui.tags.a(
                    "IRMA",
                    href="https://bmcgenomics.biomedcentral.com/articles/10.1186/s12864-016-3030-6",
                    target="_blank",
                    class_="text-info text-emphasis",
                ),
                ui.HTML(" the <b class='text-info text-emphasis'>I</b>terative <b class='text-info text-emphasis'>R</b>efinement <b class='text-info text-emphasis'>M</b>eta <b class='text-info text-emphasis'>A</b>ssembler."),
                class_="sidebar-description",
            ),
            ui.tags.hr(),
            ui.tags.br(),
            ui.tags.h4("Table of contents:"),
            ui.tags.div(
                ui.tags.a(
                    "Samplesheet",
                    href="#samplesheet_head",
                    external_link=True,
                ),
                class_="toc-link",
            ),
            ui.tags.div(
                ui.tags.a(
                    "Barcode Assignment",
                    href="#demux_head",
                ),
                class_="toc-link",
            ),
            ui.tags.div(
                ui.tags.a(
                    "Automatic QC",
                    href="#auto_qc_head",
                ),
                class_="toc-link",
            ),
            ui.tags.div(
                ui.tags.a(
                    "MIRA Summary",
                    href="#mira_head",
                ),
                class_="toc-link",
            ),
            ui.tags.div(
                ui.tags.a(
                    "Reference Coverage",
                    href="#coverage_head",
                ),
                class_="toc-link",
            ),
            ui.tags.div(
                ui.tags.a(
                    "Reference Variants",
                    href="#variants_head",
                ),
                class_="toc-link",
            ),
            ui.tags.div(
                ui.tags.a(
                    "Minor SNVs",
                    href="#minor_variants_head",
                ),
                class_="toc-link",
            ),
            ui.tags.div(
                ui.tags.a(
                    "Minor Indels",
                    href="#indels_head",
                ),
                class_="toc-link",
            ),
            ui.tags.div(
                ui.tags.a(
                    "Download Fastas",
                    href="#dl_fastas",
                ),
                class_="toc-link",
            ),
            ui.tags.br(),
            class_="main-sidebar", id="mira-sidebar",
        ),
        ui.column(9,
            ui.row(
                ui.column(12,
                    ui.input_switch(
                        id="watch_mira_progress", label="Watch MIRA Progress", value=True,
                    ),
                ),
                class_="watch-progress-widget-container content-container",
            ),
            ui.row(
                ui.column(6, 
                    ui.input_selectize(
                        id="seq_run",
                        label=ui.HTML("<span style='color:red'>*</span>Select a Sequencing Run:"),
                        choices=seq_runs,
                        selected=None,
                        multiple=False,
                        width="100%",
                        remove_button=None,
                        options=None,
                    ),
                ),
                ui.column(6, 
                    ui.input_task_button(
                        id="refresh_run_listing",
                        label="Refresh Run Listing",
                        label_busy='Refreshing...',
                        icon=ui.HTML('<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-arrow-clockwise" viewBox="0 0 16 16"><path fill-rule="evenodd" d="M8 3a5 5 0 1 0 4.546 2.914.5.5 0 0 1 .908-.417A6 6 0 1 1 8 2z"/><path d="M8 4.466V.534a.25.25 0 0 1 .41-.192l2.36 1.966c.12.1.12.284 0 .384L8.41 4.658A.25.25 0 0 1 8 4.466"/></svg>'),
                        class_="btn-primary refresh-btn",
                    ),
                ),
                class_="sequencing-run-container content-container",
            ),
            ui.row(
                ui.column(6, 
                    ui.input_selectize(
                        id="seq_experiment_type",
                        label=ui.HTML("<span style='color:red'>*</span>Select an Experiment Type:"),
                        choices=seq_experiment_types,
                        selected=None,
                        multiple=False,
                        width="100%",
                        remove_button=None,
                        options=None,
                    ),
                ),
                class_="organisms-experiment-types-container content-container"
            ),  
            ui.row(
                ui.column(12, 
                    ui.input_selectize(
                        id="seq_amplicon_library",
                        label=ui.HTML("<span style='color:red'>*</span><span id='seq_amplicon_library_label'></span>"),
                        choices=[],
                        selected=None,
                        multiple=False,
                        width="100%",
                        remove_button=None,
                        options=None,
                    ),
                ),
                class_="amplicon-library-container main-invisible content-container", id="amplicon-library-container",
            ),
            ui.row(
                ui.column(6, 
                    ui.input_selectize(
                        id="parquet_files",
                        label=ui.HTML("<span style='color:red'>*</span>Make Parquet Files:"),
                        choices={"False": False, "True": True},
                        selected=False,
                        multiple=False,
                        width="100%",
                        remove_button=None,
                        options=None,
                    ),
                ),
                ui.column(6, 
                    ui.input_selectize(
                        id="run_nextclade",
                        label=ui.HTML("<span style='color:red'>*</span>Run Nextclade:"),
                        choices={ "True": True, "False": False},
                        selected=False,
                        multiple=False,
                        width="100%",
                        remove_button=None,
                        options=None,
                    ),
                ),
                class_="boolean-option-types-container content-container"
            ),
            ui.row(
                ui.column(6, 
                    ui.input_numeric(
                        id="subsample_reads",
                        label=ui.HTML("<span style='color:red'>*</span>Subsample Reads:"),
                        value=None,
                        min=0,
                        max=None,
                        step=1,
                        width="100%",
                    ),
                ),
                class_="numeric-input-container content-container"
            ),
            ui.row(
                ui.column(12, 
                    ui.tags.h3("Samplesheet", id="samplesheet_head"),
                    class_="samplesheet-title-container content-container",
                ),
                ui.column(12,
                    ui.input_task_button(
                        id="generate_samplesheet_xl",
                        label=" Download Samplesheet Template",
                        label_busy='PREPARING SAMPLESHEET...',
                        icon=ui.HTML('<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="currentColor" class="bi bi-download" viewBox="0 0 16 16"><path d="M.5 9.9a.5.5 0 0 1 .5.5v2.5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-2.5a.5.5 0 0 1 1 0v2.5a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2v-2.5a.5.5 0 0 1 .5-.5"/><path d="M7.646 11.854a.5.5 0 0 0 .708 0l3-3a.5.5 0 0 0-.708-.708L8.5 10.293V1.5a.5.5 0 0 0-1 0v8.793L5.354 8.146a.5.5 0 1 0-.708.708z"/></svg>'),
                        width="auto",
                        class_="btn-primary download-btn",
                    ),
                    ui.download_button(
                        id="download_ss",
                        label=" Download Samplesheet Template",
                        icon=ui.HTML('<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="currentColor" class="bi bi-download" viewBox="0 0 16 16"><path d="M.5 9.9a.5.5 0 0 1 .5.5v2.5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-2.5a.5.5 0 0 1 1 0v2.5a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2v-2.5a.5.5 0 0 1 .5-.5"/><path d="M7.646 11.854a.5.5 0 0 0 .708 0l3-3a.5.5 0 0 0-.708-.708L8.5 10.293V1.5a.5.5 0 0 0-1 0v8.793L5.354 8.146a.5.5 0 1 0-.708.708z"/></svg>'),
                        label_busy='PREPARING SAMPLESHEET...',
                        width="auto",
                        class_="btn-primary download-btn invisible",
                    ),
                    class_="samplesheet-download-btn-container content-container",
                ),
                ui.column(12,
                    ui.input_file(
                        id="upload_ss",
                        label=None,
                        multiple=True,
                        accept=[".csv", ".xlsx"],
                        button_label=ui.HTML("Drag and Drop your <b>Samplesheet</b> here or Click and Select a File to upload."),
                        placeholder=None,
                        width="100%",
                    ),
                    class_="samplesheet-upload-container content-container",
                ),
                ui.column(12,
                    ui.output_data_frame(id="samplesheet_tbl"), 
                    class_="samplesheet-tbl-container content-container",
                ),
                ui.column(12,
                    ui.output_ui(
                        id="samplesheet_error",
                        inline=False,
                        container=False,
                        fill=False,
                        fillable=False,
                    ),                     
                    class_="samplesheet-error-container content-container",
                ),
                class_="samplesheet-container",
            ),
            ui.row(
                ui.column(12,
                    ui.input_action_button(
                        id="trigger_assembly_button",
                        label="Start Genome Assembly",
                        label_busy="Start Genome Assembly...",
                        icon=ui.HTML('<i class="fa fa-refresh fa-spin display-none" id="assembly-loading-icon"></i><svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="currentColor" class="bi bi-play" id="assembly-play-icon" viewBox="0 0 16 16"><path d="M10.804 8 5 4.633v6.734zm.792-.696a.802.802 0 0 1 0 1.392l-6.363 3.692C4.713 12.69 4 12.345 4 11.692V4.308c0-.653.713-.998 1.233-.696z"/></svg>'),
                        width="auto",
                        class_="btn-primary download-btn",
                    ),                
                    ui.input_task_button(
                        id="stop_assembly_button",
                        label="Stop Genome Assembly",
                        label_busy="Stop Genome Assembly...",
                        icon=ui.HTML('<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="currentColor" class="bi bi-stop" viewBox="0 0 16 16"><path d="M3.5 5A1.5 1.5 0 0 1 5 3.5h6A1.5 1.5 0 0 1 12.5 5v6a1.5 1.5 0 0 1-1.5 1.5H5A1.5 1.5 0 0 1 3.5 11zM5 4.5a.5.5 0 0 0-.5.5v6a.5.5 0 0 0 .5.5h6a.5.5 0 0 0 .5-.5V5a.5.5 0 0 0-.5-.5z"/></svg>'),
                        width="auto",
                        class_="btn-primary download-btn",
                    ),
                    ui.input_task_button(
                        id="start_assembly_button",
                        label="Start Genome Assembly",
                        label_busy="Start Genome Assembly...",
                        icon=ui.HTML('<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="currentColor" class="bi bi-play" viewBox="0 0 16 16"><path d="M10.804 8 5 4.633v6.734zm.792-.696a.802.802 0 0 1 0 1.392l-6.363 3.692C4.713 12.69 4 12.345 4 11.692V4.308c0-.653.713-.998 1.233-.696z"/></svg>'),
                        width="auto",
                        class_="btn-primary download-btn invisible",
                    ),
                    class_="assembly-buttons",
                ), 
                class_="assembly-buttons-container content-container",
            ),
            ui.row(
                ui.column(12, 
                    ui.tags.h3("MIRA Progress"),
                ),
                ui.column(12,
                    ui.output_ui(
                        id="mira_progress",
                        inline=False,
                        container=False,
                        fill=True,
                        fillable=False,
                    ),
                ),
                class_="mira-progress-content content-container",
            ), 
            ui.row(
                ui.column(12, 
                    ui.tags.h3("Barcode Assignment", id="demux_head"),
                    output_widget(id="demux_fig"),
                    class_="barcode-container content-container", id="barcode-container",
                ),
                ui.column(12, 
                    ui.tags.h3("Automatic Quality Control Decisions", id="auto_qc_head"),
                    ui.output_ui(
                        id="irma_neg_statement",
                        inline=False,
                        container=False,
                        fill=False,
                        fillable=False,
                    ),
                    output_widget(id="pass_fail_heatmap"),
                    class_="pass-fail-container content-container", id="pass-fail-container",
                ), 
                ui.column(12, 
                    ui.tags.h3("MIRA Summary", id="mira_head"),
                    output_widget(id="irma_summary"),
                    class_="irma-summary-container content-container", id="irma-summary-container",
                ),                 
                ui.column(12, 
                    ui.tags.h3("Reference Coverage", id="coverage_head"),
                    output_widget(id="coverage_heatmap"),
                    class_="coverage-heatmap-container content-container", id="coverage-heatmap-container",
                ),
                ui.row(
                    ui.column(12, 
                        ui.output_ui(
                            id="coverage_sample",
                            inline=False,
                            container=False,
                            fill=False,
                            fillable=False,
                        ),
                    ),
                    ui.column(12,
                        ui.output_ui(
                            id="coverage_error",
                            inline=False,
                            container=False,
                            fill=False,
                            fillable=False,
                        ),
                    ),
                    ui.column(4, 
                        output_widget(id="coverage_sample_sankeyfig"),   
                    ),
                    ui.column(8, 
                        output_widget(id="coverage_sample_fig"),  
                    ),
                    class_="coverage-container content-container", id="coverage-container",
                ),                
                ui.column(12, 
                    ui.tags.h3("Reference Variants", id="variants_head"),
                    ui.tags.p(
                      "Non-amino-acid variants ",
                      ui.HTML("<a class='text-info' href='https://cdcgov.github.io/MIRA/articles/running-mira.html#special-translated-characters' target='_blank'>key</a>"),
                    ),
                    ui.tags.p(
                      "Influenza References and ", 
                      ui.HTML("<a class='text-info' href='https://cdcgov.github.io/MIRA/articles/sequence-qc.html#amino-acid-variant-references' target='_blank'>Candidate Vaccine Viruses (CVVs)</a>"),
                    ),
                    output_widget(id="variants_table"),
                    class_="variants-container content-container", id="variants-container",
                ),                 
                ui.column(12, 
                    ui.tags.h3("Minor SNVs", id="minor_variants_head"),
                    output_widget(id="minor_variants_table"),
                    class_="snvs-container content-container", id="snvs-container",
                ),                 
                ui.column(12, 
                    ui.tags.h3("Minor Insertions and Deletions", id="indels_head"),
                    output_widget(id="indels_table"),
                    class_="indels-container content-container", id="indels-container",
                ),                 
                ui.row(
                    ui.column(12, 
                        ui.tags.h3("Download Passed Fastas", id="dl_passed_fastas"),
                    ), 
                    ui.column(12,
                        ui.download_button(
                            id="download_passed_nt_fasta",
                            label=" Download Passed NT",
                            width="auto",
                            icon=ui.HTML('<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="currentColor" class="bi bi-download" viewBox="0 0 16 16"><path d="M.5 9.9a.5.5 0 0 1 .5.5v2.5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-2.5a.5.5 0 0 1 1 0v2.5a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2v-2.5a.5.5 0 0 1 .5-.5"/><path d="M7.646 11.854a.5.5 0 0 0 .708 0l3-3a.5.5 0 0 0-.708-.708L8.5 10.293V1.5a.5.5 0 0 0-1 0v8.793L5.354 8.146a.5.5 0 1 0-.708.708z"/></svg>'),
                            class_="btn-primary download-btn",
                        ),
                        ui.download_button(
                            id="download_passed_aa_fasta",
                            label=" Download Passed AA",
                            width="auto",
                            icon=ui.HTML('<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="currentColor" class="bi bi-download" viewBox="0 0 16 16"><path d="M.5 9.9a.5.5 0 0 1 .5.5v2.5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-2.5a.5.5 0 0 1 1 0v2.5a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2v-2.5a.5.5 0 0 1 .5-.5"/><path d="M7.646 11.854a.5.5 0 0 0 .708 0l3-3a.5.5 0 0 0-.708-.708L8.5 10.293V1.5a.5.5 0 0 0-1 0v8.793L5.354 8.146a.5.5 0 1 0-.708.708z"/></svg>'),
                            class_="btn-primary download-btn",
                        ),
                        class_="download-passed-fasta-btns", 
                    ),
                    class_="download-passed-fasta-container content-container", id="download-passed-fasta-container",
                ),
                ui.row(
                    ui.column(12,
                        ui.tags.h3("Download Failed Fastas", id="dl_failed_fastas"),
                    ),
                    ui.column(12,
                        ui.download_button(
                            id="download_failed_nt_fasta",
                            label=" Download Failed NT",
                            width="auto",
                            icon=ui.HTML('<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="currentColor" class="bi bi-download" viewBox="0 0 16 16"><path d="M.5 9.9a.5.5 0 0 1 .5.5v2.5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-2.5a.5.5 0 0 1 1 0v2.5a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2v-2.5a.5.5 0 0 1 .5-.5"/><path d="M7.646 11.854a.5.5 0 0 0 .708 0l3-3a.5.5 0 0 0-.708-.708L8.5 10.293V1.5a.5.5 0 0 0-1 0v8.793L5.354 8.146a.5.5 0 1 0-.708.708z"/></svg>'),
                            class_="btn-primary download-btn",
                        ),
                        ui.download_button(
                            id="download_failed_aa_fasta",
                            label=" Download Failed AA",
                            width="auto",
                            icon=ui.HTML('<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="currentColor" class="bi bi-download" viewBox="0 0 16 16"><path d="M.5 9.9a.5.5 0 0 1 .5.5v2.5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-2.5a.5.5 0 0 1 1 0v2.5a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2v-2.5a.5.5 0 0 1 .5-.5"/><path d="M7.646 11.854a.5.5 0 0 0 .708 0l3-3a.5.5 0 0 0-.708-.708L8.5 10.293V1.5a.5.5 0 0 0-1 0v8.793L5.354 8.146a.5.5 0 1 0-.708.708z"/></svg>'),
                            class_="btn-primary download-btn",
                        ),
                        class_="download-failed-fasta-btns", 
                    ),
                    class_="download-failed-fasta-container content-container", id="download-failed-fasta-container",
                ), 
                class_="mira-assembly-content", id="mira-assembly-content",
            ),
            class_="main-main", id="mira-main",
        ),
        class_="main-layout",
    )

# Define server logic
@module.server
def mira_server(input, output, session, data_root, samplesheet_html_tbl, command_type):
  
    # Create local variable to store mira progress and its completion status
    track_mira_progress = None
    nextflow_mira_log = os.path.realpath(f"{data_root}/nextflow_mira.log")

    # Clean to re-stage log file
    open(nextflow_mira_log, "w").close()
  
    # Create reative value to store status of mira
    mira_progress_log = reactive.Value("")
    
    # Create reative value to store error message
    start_assembly_counter = reactive.value()
    
    # Create reative value to store error message
    samplesheet_tbl_message = reactive.value()
    
    # Reactive value to store indels
    mira_progress_message = reactive.Value("") 
    
    # Create reative value to store error message
    coverage_error_message = reactive.value() 
    
    # Reactive value to track if download is triggered
    orig_samplesheet_tbl = reactive.Value(pd.DataFrame())  
    
    # Log catching
    log_buffer = []
    
    # Reactive value to track assembly completion
    assembly_completed = reactive.Value(0)
    
    # Add a reactive value to track if assembly is running
    assembly_running = reactive.Value(False)
    
    # Store the last known file states to detect actual changes
    last_file_states = reactive.Value({})
    
    # Reactive poll to check for file changes - only update when files actually change
    @reactive.poll(
        lambda: 2 if assembly_running.get() else 10,  # Poll every 2 sec during assembly, 10 sec otherwise
        1
    )
    def check_files_exist():
        selected_run = input.seq_run()
        if not selected_run:
            return {}
        
        current_states = {
            'barcode': os.path.exists(f"{data_root}/{selected_run}/mira_results/aggregate_outputs/dash-json/barcode_distribution.json"),
            'qc_statement': os.path.exists(f"{data_root}/{selected_run}/mira_results/aggregate_outputs/dash-json/qc_statement.json"),
            'pass_fail': os.path.exists(f"{data_root}/{selected_run}/mira_results/aggregate_outputs/dash-json/pass_fail_heatmap.json"),
            'irma_summary': os.path.exists(f"{data_root}/{selected_run}/mira_results/aggregate_outputs/dash-json/irma_summary.json"),
            'heatmap': os.path.exists(f"{data_root}/{selected_run}/mira_results/aggregate_outputs/dash-json/heatmap.json"),
            'reads': os.path.exists(f"{data_root}/{selected_run}/mira_results/aggregate_outputs/dash-json/reads.json"),
            'variants': os.path.exists(f"{data_root}/{selected_run}/mira_results/aggregate_outputs/dash-json/dais_vars.json"),
            'snvs': os.path.exists(f"{data_root}/{selected_run}/mira_results/aggregate_outputs/dash-json/minor_variants.json"),
            'indels': os.path.exists(f"{data_root}/{selected_run}/mira_results/aggregate_outputs/dash-json/indels.json"),
            'passed_nt': os.path.exists(f"{data_root}/{selected_run}/mira_results/aggregate_outputs/mira-reports/mira_{selected_run}_amended_consensus.fasta"),
            'passed_aa': os.path.exists(f"{data_root}/{selected_run}/mira_results/aggregate_outputs/mira-reports/mira_{selected_run}_amino_acid_consensus.fasta"),
            'failed_nt': os.path.exists(f"{data_root}/{selected_run}/mira_results/aggregate_outputs/mira-reports/mira_{selected_run}_failed_amended_consensus.fasta"),
            'failed_aa': os.path.exists(f"{data_root}/{selected_run}/mira_results/aggregate_outputs/mira-reports/mira_{selected_run}_failed_amino_acid_consensus.fasta"),
        }
        
        # Check if states have actually changed
        last_states = last_file_states.get()
        if current_states != last_states:
            last_file_states.set(current_states)
            return current_states
        
        # Return cached states if nothing changed
        return last_states
        
    # Observe sequencing run selection
    @reactive.effect
    @reactive.event(input.seq_run, ignore_none=False, ignore_init=False)
    async def _():
        # Get selected sequencing run
        selected_run = input.seq_run()
        # Extract Experiment type
        selected_seq_experiment_type = input.seq_experiment_type()
        # Define samplesheet file
        samplesheet_file = f"{data_root}/{selected_run}/samplesheet.csv"
        # Get samplesheet
        ss_df, selected_experiment_type = parse_samplesheet(samplesheet_file = samplesheet_file)
        # Update samplesheet
        orig_samplesheet_tbl.set(ss_df)   
        # Update amplicon library
        if selected_experiment_type == 'SC2-Whole-Genome-Illumina':
            ui.update_selectize(
                id="seq_amplicon_library",
                choices=sc2_amplicon_libraries,
                session=session,
            )
            await session.send_custom_message(
                "toggleAmpliconContent", {"id": "amplicon-library-container", "visible": True, "label": "For Illumina SC2, Which Primer Schema Was Used?"}
            )
        elif selected_experiment_type == 'RSV-Illumina':
            ui.update_selectize(
                id="seq_amplicon_library",
                choices=rsv_amplicon_libraries,
                session=session,
            )
            await session.send_custom_message(
                "toggleAmpliconContent", {"id": "amplicon-library-container", "visible": True, "label": "For Illumina RSV, Which Primer Schema Was Used?"}
            )
        # Reset error message
        samplesheet_tbl_message.set("")
        coverage_error_message.set("")
        # Reset mira progress and its message
        nonlocal track_mira_progress
        track_mira_progress = None
        mira_progress_message.set('Press the <span class="text-info text-emphasis">"START GENOME ASSEMBLY"</span> button to start the assembly process!')
        # Reset assembly counter 
        start_assembly_counter.set("")
        # Reset assembly completion status
        mira_progress_log.set("")
        # Reset file states
        last_file_states.set({})
        # Trigger refresh of outputs
        assembly_completed.set(assembly_completed.get() + 1)
  
    # Observe Exp Type selection
    @reactive.effect
    @reactive.event(input.seq_experiment_type, ignore_none=True, ignore_init=True)
    async def _():
        # Get inputs
        # Extract Experiment type
        selected_seq_experiment_type = input.seq_experiment_type()
        selected_amplicon_library = input.seq_amplicon_library()
        # Update amplicon library
        if selected_seq_experiment_type == 'SC2-Whole-Genome-Illumina':
            ui.update_selectize(
                id="seq_amplicon_library",
                choices=sc2_amplicon_libraries,
                selected=selected_amplicon_library if selected_amplicon_library in sc2_amplicon_libraries.keys() else sc2_amplicon_libraries[list(sc2_amplicon_libraries.keys())[0]],
                session=session,
            )
            await session.send_custom_message(
                "toggleAmpliconContent", {"id": "amplicon-library-container", "visible": True, "label": "For Illumina SC2, Which Primer Schema Was Used?"}
            )
        elif selected_seq_experiment_type == 'RSV-Illumina':
            ui.update_selectize(
                id="seq_amplicon_library",
                choices=rsv_amplicon_libraries,
                selected=selected_amplicon_library if selected_amplicon_library in rsv_amplicon_libraries.keys() else rsv_amplicon_libraries[list(rsv_amplicon_libraries.keys())[0]],
                session=session,
            )
            await session.send_custom_message(
                "toggleAmpliconContent", {"id": "amplicon-library-container", "visible": True, "label": "For Illumina RSV, Which Primer Schema Was Used?"}
            )
        else:
            await session.send_custom_message(
                "toggleAmpliconContent", {"id": "amplicon-library-container", "invisible": False, "label": ""}
            )
            
    # Create a get_run_listing() task when refresh run listing button is clicked
    @ui.bind_task_button(button_id="refresh_run_listing")
    @reactive.extended_task
    async def get_run_listing():
        await  asyncio.sleep(1)
        return {i: i for i in sorted(os.listdir(data_root)) if "." not in i}

    # Start get_run_listing() task when refresh run listing button is clicked
    @reactive.effect
    @reactive.event(input.refresh_run_listing, ignore_none=True, ignore_init=True)
    def _():
        get_run_listing()

    # Update sequencing runs once get_run_listing() task is completed
    @reactive.effect
    def _():
        run_listings = get_run_listing.result()
        if run_listings:
            selected_run = input.seq_run()
            ui.update_selectize(
                id="seq_run",
                choices=run_listings,
                selected=selected_run if selected_run in run_listings.keys() else run_listings[list(run_listings.keys())[0]]
            )

    # Create a get_samplesheet() task when generate xl button is clicked
    @ui.bind_task_button(button_id="generate_samplesheet_xl")
    @reactive.extended_task
    async def get_samplesheet(data_root, seq_run, experiment_type):
        await asyncio.sleep(1)
        return generate_samplesheet_xl(data_root=data_root, seq_run=seq_run, experiment_type=experiment_type)

    # Start get_samplesheet() task when generate xl button is clicked
    @reactive.effect
    @reactive.event(input.generate_samplesheet_xl, ignore_none=True, ignore_init=True)
    async def _():
        seq_run = input.seq_run()
        experiment_type = input.seq_experiment_type()
        # Check sequencing run
        if not seq_run:
            samplesheet_tbl_message.set("Please select a sequencing run to generate the samplesheet")
            return
        # Check experiment type
        if not experiment_type:
            samplesheet_tbl_message.set("Please select an experiment type to generate the samplesheet")
            return
        # Reset message
        samplesheet_tbl_message.set("")  
        # Create samplesheet
        get_samplesheet(data_root=data_root, seq_run=seq_run, experiment_type=experiment_type)

    # After get_samplesheet() task is completed, trigger the download samplesheet button
    @reactive.effect
    async def check_samplesheet():
        samplesheet_file = get_samplesheet.result()
        if samplesheet_file and os.path.exists(samplesheet_file):
            download_btn_id = session.ns("download_ss")
            await session.send_custom_message(
                "triggerBtn", {"id": download_btn_id}
            )
            
    # Output error message if there is any
    @render.ui
    def samplesheet_error():
        req(samplesheet_tbl_message.get())
        return ui.TagList(
            ui.tags.p(
                ui.HTML(samplesheet_tbl_message.get()),
                class_="error-message",
            ),
        )

    # Download samplesheet template
    @render.download()
    def download_ss():
        samplesheet_file = get_samplesheet.result()
        return samplesheet_file

    # Observe when upload samplesheet is clicked on
    @reactive.effect
    @reactive.event(input.upload_ss, ignore_none=True, ignore_init=True)
    def _():
        # Reset error message
        samplesheet_tbl_message.set("")
        # Parse samplesheet
        file: list[FileInfo] | None = input.upload_ss()
        # Check input file
        if file is None:
            ss_df = pd.DataFrame()
        elif Path(file[0]["datapath"]).suffix in [".csv", ".xls", ".xlsx"]:
            selected_seq_experiment_type = input.seq_experiment_type()
            ss_df, selected_experiment_type = parse_samplesheet(samplesheet_file = file[0]["datapath"])
            # Update experiment type
            if not ss_df.empty:
                ui.update_selectize(
                    id="seq_experiment_type",
                    choices=seq_experiment_type,
                    selected=selected_experiment_type if selected_experiment_type in seq_experiment_type.keys() else seq_experiment_type[list(seq_experiment_type.keys())[0]],
                    session=session,
                )
            else:
                selected_experiment_type = input.seq_experiment_type()
                required_ss_colnames = illumina_ss_colnames if selected_experiment_type.upper() == "ILLUMINA" else ont_ss_colnames
                samplesheet_tbl_message.set(f"Invalid Samplesheet for {selected_experiment_type}. The samplesheet requires the following column names: {required_ss_colnames} and cannot be empty.")
                ss_df = pd.DataFrame()
        else:
            samplesheet_tbl_message.set("Invalid file type.")
            ss_df = pd.DataFrame()
        # Store samplesheet table
        orig_samplesheet_tbl.set(ss_df)
        
    # Output samplesheet
    @output
    @render.data_frame
    def samplesheet_tbl():
        df = orig_samplesheet_tbl()
        if not df.empty:
            return render.DataGrid(df, editable=True, width="100%", height="auto", filters=False)
        elif df.empty and not df.columns.empty:
            return render.DataGrid(df, editable=True, width="100%", height="auto", filters=False)
        else:
            return
          
    # Observe when watch mira progress is selected
    @reactive.effect
    @reactive.event(input.watch_mira_progress, ignore_none=False, ignore_init=False)
    async def watch_btn_click():
        if input.watch_mira_progress():
            await session.send_custom_message(
                "toggleContent", {"id": "mira-progress-content", "visible": True}
            )
        else:
            await session.send_custom_message(
                "toggleContent", {"id": "mira-progress-content", "visible": False}
            )
        
    # Trigger the assembly button 
    @reactive.effect
    @reactive.event(input.trigger_assembly_button, ignore_none=True, ignore_init=True)
    async def _():
            samplesheet_tbl_id = session.ns("samplesheet_tbl")
            assembly_btn_id = session.ns("start_assembly_button")
            await session.send_custom_message(
                "triggerAssemblyBtn", {"assembly_btn_id": assembly_btn_id, "samplesheet_tbl_id": samplesheet_tbl_id}
            )
    
    # Start the assembly task when assembly button was clicked
    @ui.bind_task_button(button_id="start_assembly_button")
    @reactive.extended_task
    async def start_assembly_task(data_root, seq_run, experiment_type, amplicon_library, parquet_files, nextclade, subsample_reads, command_type,nextflow_mira_log):
        # Construct the command
        command = f"python3 -u {os.path.dirname(os.path.realpath(__file__))}/../utils/run_mira_nf.py "
        command += f"--data_root '{data_root}' "
        command += f"--seq_run '{seq_run}' "
        command += f"--experiment_type '{experiment_type}' "
        command += f"--amplicon_library '{amplicon_library}' "
        command += f"--parquet_files '{parquet_files}' "
        command += f"--nextclade '{nextclade}' "
        command += f"--subsample_reads '{subsample_reads}' "
        command += f"--command_type '{command_type}' "
        command += f"--log_file '{nextflow_mira_log}'"
        print(command)

        # Start subprocess
        mira_assembly_task = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        print(f"Start the assembly task with PID: {mira_assembly_task.pid}")

        # Stream output instead of blocking communicate()
        async def stream_output(stream, label):
            while True:
                line = await stream.readline()
                if not line:
                    break
                log_buffer.append(line.decode(errors="ignore"))

        # Run both stdout + stderr streaming concurrently
        await asyncio.gather(
            stream_output(mira_assembly_task.stdout, "STDOUT"),
            stream_output(mira_assembly_task.stderr, "STDERR"),
        )

        # Wait for process to finish
        await mira_assembly_task.wait()

        # Return exit code
        return mira_assembly_task.returncode
        
    # After start_assembly_task() is completed, return results
    @reactive.effect
    async def check_mira_progress_task():
        exit_code = start_assembly_task.result()
        # Check exit code
        if exit_code in [0, 1]:
            nonlocal track_mira_progress
            track_mira_progress = False 
            assembly_running.set(False)  # Stop frequent polling
            
            # Update progress log
            if os.path.exists(nextflow_mira_log):
                with open(nextflow_mira_log, 'r') as file:
                    lines = file.readlines()        
                mira_progress_log.set("".join(lines))
            # Return message base on exit code
            if exit_code == 1:
                mira_progress_message.set("<p class='error-message'>An error has occurred. Please see the logs below for more details.</p>")
            elif exit_code  == 0:
                mira_progress_message.set("<p class='success-message'>The update process has been completed. Please see logs below for additional details.</p>")

            # Re-enable buttons and show results
            seq_run_id = session.ns("seq_run")
            assembly_btn_id = session.ns("trigger_assembly_button")
            await session.send_custom_message(
                "disableAssemblyBtn", {"seq_run_id": seq_run_id, "assembly_btn_id": assembly_btn_id, "disabled": False}
            )
            
            # Show assembly content
            await session.send_custom_message(
                "toggleAssemblyContent", {"id": "mira-assembly-content", "visible": True}
            )
            
            # Force a final file check
            last_file_states.set({})
            
            # Small delay to ensure files are written
            await asyncio.sleep(1)
            
            # Trigger file updates
            assembly_completed.set(assembly_completed.get() + 1)
    
    @reactive.effect
    def update_log_ui():
        reactive.invalidate_later(0.5)

        _ = mira_progress_log.get()

        if log_buffer:
            current = mira_progress_log.get()
            new_text = "".join(log_buffer)

            log_buffer.clear()

            mira_progress_log.set(current + new_text)

    # Output delete error message 
    @output
    @render.ui
    def mira_progress():
        return ui.tags.pre(
            mira_progress_log.get(),
            style="""
                background-color: #ffffff;
                color: #333333;
                padding: 12px;
                height: 500px;
                overflow-y: auto;
                font-family: monospace;
                font-size: 13px;
                white-space: pre-wrap;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
            """
        )
  
    # Observe when start_assembly_button is clicked
    @reactive.effect
    @reactive.event(input.start_assembly_button, ignore_none=True, ignore_init=True)
    async def start_assembly_click():
        # Get inputs
        selected_run = input.seq_run()
        selected_seq_experiment_type = input.seq_experiment_type()
        selected_experiment_type = input.seq_experiment_type()
        selected_amplicon_library = input.seq_amplicon_library()
        selected_parquet_files = input.parquet_files()
        selected_run_nextclade = input.run_nextclade()
        selected_subsample_reads = input.subsample_reads()
        if selected_subsample_reads is None:
            selected_subsample_reads = 0
        ss_html_tbl = samplesheet_html_tbl.get()
        # Check seq_run
        if not selected_run:
            samplesheet_tbl_message.set("Please select a sequencing run to start the assembly!")
            return
        # Check experiment types
        if not selected_experiment_type:
            samplesheet_tbl_message.set("Please select an experiment type to start the assembly!")
            return
        # Check amplicon library
        if selected_experiment_type in ["SC2-WholeGenome-Illumina", "RSV-Illumina"] and not selected_amplicon_library:
            samplesheet_tbl_message.set(f"For {selected_experiment_type}, please select a Primer Schema to start the assembly!")
            return
        # Convert HTML table to DataFrame
        try:
            ss_df = pd.read_html(io.StringIO(ss_html_tbl))
        except Exception as e:
            samplesheet_tbl_message.set("Please upload a samplesheet to start the assembly")
            return
        # Replace all NaN values with an empty string 
        ss_df = ss_df[0].fillna("")
        # Convert all values as string and trim trailing whitespace 
        ss_df = ss_df.astype(str).apply(lambda x: x.str.strip())
        # Check if any cells contains NaN or empty string
        if ss_df.isnull().values.any() or ss_df.eq("").any().any():
            samplesheet_tbl_message.set("Samplesheet cannot contain any empty values")
            return
        # Check for duplicated
        if True in list(ss_df["sample_id"].duplicated(keep=False)):
            duplicated_ids = list(ss_df["sample_id"].loc[ss_df["sample_id"].duplicated(keep=False) == True])
            samplesheet_tbl_message.set(f"No duplicated sample_ids allowed. Duplicates = {duplicated_ids}")
            return
        # Check for white spaces
        if True in list(ss_df["sample_id"].str.contains(r"\s")):
            ids_with_spaces = list(ss_df["sample_id"].loc[ss_df["sample_id"].str.contains(r"\s") == True])
            samplesheet_tbl_message.set(f"No spaces allowed in sample_ids. Offenders = {ids_with_spaces}")
            return
        # Check for forward or backward slashes
        if True in list(ss_df["sample_id"].str.contains(r"[\\/]")):
            ids_with_slashes = list(ss_df["sample_id"].loc[ss_df["sample_id"].str.contains(r"[\\/]") == True])
            samplesheet_tbl_message.set(f"No forward slashes ('/') or backward slashes ('\\') allowed in sample_ids. Offenders = {ids_with_slashes}")
            return
        # Check sample type (- control, + control, test, etc)
        if True in list(~ss_df["sample_type"].isin(sample_type_options)):
            id_list = list(ss_df["sample_id"].loc[~ss_df["sample_type"].isin(sample_type_options)])
            samplesheet_tbl_message.set(f"Invalid sample_type for sample_id = {id_list}. Options are {sample_type_options}")
            return   
        # Save the final validated samplesheet
        ss_df.to_csv(f"{data_root}/{selected_run}/samplesheet.csv", index=False)
        # Remove empty generated samplesheet. The real samplesheet is saved as samplesheet.csv
        if len(glob(f"{data_root}/{selected_run}/{selected_run}_samplesheet.xlsx")) > 0:
            os.remove(f"{data_root}/{selected_run}/{selected_run}_samplesheet.xlsx") 
        # Remove fastas from run folder to re-start and track the assembly process again
        fasta_files = glob(f"{data_root}/{selected_run}/mira_results/aggregate_outputs/mira-reports/*amended_consensus.fasta") + glob(f"{data_root}/{selected_run}/mira_results/aggregate_outputs/mira-reports/*amino_acid_consensus.fasta")
        if len(fasta_files) > 0:
            for i in fasta_files:
                os.remove(i) 
        # Reset message and result files  
        mira_progress_message.set("Preparing data files. Please wait...")
        samplesheet_tbl_message.set("")
        # Hide the assembly content 
        await session.send_custom_message(
            "toggleAssemblyContent", {"id": "mira-assembly-content", "visible": False}
        )
        # Disable the assembly button to avoid continuous clicking
        seq_run_id = session.ns("seq_run")
        stop_btn_id = session.ns("stop_assembly_button")
        assembly_btn_id = session.ns("trigger_assembly_button")
        await session.send_custom_message(
            "disableAssemblyBtn", {"seq_run_id": seq_run_id, "assembly_btn_id": assembly_btn_id, "disabled": True}
        )
        await session.send_custom_message(
            "disableBtn", {"id": stop_btn_id, "disabled": True}
        )
        
        # Start track MIRA progress
        nonlocal track_mira_progress
        track_mira_progress = True
        assembly_running.set(True)  # Start frequent polling
        
        # Reset file states to force fresh check
        last_file_states.set({})
        
        # Start the assembly task as a background process
        start_assembly_task(data_root=data_root, seq_run=selected_run, experiment_type=selected_experiment_type, amplicon_library=selected_amplicon_library, parquet_files= selected_parquet_files, nextclade=selected_run_nextclade, subsample_reads=selected_subsample_reads, command_type=command_type, nextflow_mira_log=nextflow_mira_log)
        
    # Display barcode distribution plot
    @output
    @render_widget
    async def demux_fig():
        # Check if file exists using the poll
        files_status = check_files_exist()
        selected_run = input.seq_run()
        
        json_file = f"{data_root}/{selected_run}/mira_results/aggregate_outputs/dash-json/barcode_distribution.json"
        
        # If file exists, read in the file
        if files_status.get('barcode', False) and os.path.exists(json_file):
            await session.send_custom_message(
                "toggleContent", {"id": "barcode-container", "visible": True}
            )
            # Load json as dict
            with open(json_file, 'r') as file:
                plot_data = json.load(file)
            # Remove heatmapgl from plot data
            try:
                del plot_data["layout"]["template"]["data"]["heatmapgl"]
            except KeyError:
                pass
            # Convert dictionary to Plotly figure
            fig = pio.from_json(pio.to_json(plot_data))
            return fig
        else:
            await session.send_custom_message(
                "toggleContent", {"id": "barcode-container", "visible": False}
            )
            return 

    # Display IRMA negative statement
    @output
    @render.ui
    def irma_neg_statement():
        # Check if file exists using the poll
        files_status = check_files_exist()
        selected_run = input.seq_run()
        
        json_file = f"{data_root}/{selected_run}/mira_results/aggregate_outputs/dash-json/qc_statement.json"
        
        # Read in the file
        if files_status.get('qc_statement', False) and os.path.exists(json_file):
            # Load json as dict
            with open(json_file, "r") as file:
                qc_statement_dict = json.load(file)
            # Create place holder to store statement
            statement = []
            # Check QC statement
            for q in ["FAILS QC", "passes QC"]:
                for s, p in qc_statement_dict[q].items():
                    if q == "FAILS QC":
                        statement.extend([ui.HTML(f'<div>Your negative sample <strong class="text-danger">"{s}" FAILS QC</strong> with {p}% reads mapping to reference.</div>')])
                    else:
                        statement.extend([ui.HTML(f'<div>Your negative sample "{s}" passes QC with {p}% reads mapping to reference.</div>')])
            # Return statement
            return statement

    # Display pass/fail heatmap
    @output
    @render_widget
    async def pass_fail_heatmap():
        # Check if file exists using the poll
        files_status = check_files_exist()
        selected_run = input.seq_run()
        
        json_file = f"{data_root}/{selected_run}/mira_results/aggregate_outputs/dash-json/pass_fail_heatmap.json"
        
        # If file exists, read in the file
        if files_status.get('pass_fail', False) and os.path.exists(json_file):
            await session.send_custom_message(
                "toggleContent", {"id": "pass-fail-container", "visible": True}
            )
            # Load json as dict
            with open(json_file, 'r') as file:
                plot_data = json.load(file)
            # Remove heatmapgl from plot data
            try:
                del plot_data["layout"]["template"]["data"]["heatmapgl"]
            except KeyError:
                pass
            # Convert dictionary to Plotly figure
            fig = pio.from_json(pio.to_json(plot_data))
            return fig
        else:
            await session.send_custom_message(
                "toggleContent", {"id": "pass-fail-container", "visible": False}
            )
            return

    # Output irma summary table
    @output
    @render_widget
    async def irma_summary():
        try:
            # Check if file exists using the poll
            files_status = check_files_exist()
            selected_run = input.seq_run()
            
            json_file = f"{data_root}/{selected_run}/mira_results/aggregate_outputs/dash-json/irma_summary.json"
            
            print(f"DEBUG irma_summary: Checking file {json_file}")
            print(f"DEBUG irma_summary: files_status['irma_summary']={files_status.get('irma_summary', False)}")
            print(f"DEBUG irma_summary: os.path.exists={os.path.exists(json_file)}")
            
            # Read in the file
            if files_status.get('irma_summary', False) and os.path.exists(json_file):
                await session.send_custom_message(
                    "toggleContent", {"id": "irma-summary-container", "visible": True}
                )
                
                # Load json as dict
                try:
                    df = pd.read_json(json_file, orient="split")
                    print(f"DEBUG irma_summary: Successfully loaded JSON, shape={df.shape}")
                    print(f"DEBUG irma_summary: Columns={df.columns.tolist()}")
                    print(f"DEBUG irma_summary: First few rows:\n{df.head()}")
                except Exception as e:
                    print(f"ERROR irma_summary: Failed to load JSON: {e}")
                    import traceback
                    traceback.print_exc()
                    df = pd.DataFrame([{"ERROR": f"Failed to load data: {str(e)}"}])
                    return ITable(df, columnDefs=[{"targets":"_all", "className":"dt-center"}], showIndex=False, select=False, allow_html=True, style="width:100%;", scrollX=False, scrollY=False, scrollCollapse=False, paging=False, search=False)
                
                # Display df if not empty
                if not df.empty:
                    try:
                        print(f"DEBUG irma_summary: Calling fill_irma_summary_tbl")
                        styled_df = fill_irma_summary_tbl(df=df, n_bins=8, columns="all")
                        print(f"DEBUG irma_summary: Successfully styled dataframe")
                    except Exception as e:
                        print(f"ERROR irma_summary: Failed to style dataframe: {e}")
                        import traceback
                        traceback.print_exc()
                        # Fall back to unstyled dataframe
                        styled_df = df.astype(str)
                    
                    # Determine the height of table based on number of rows
                    if df.shape[0] > 5:
                        height = 550;
                        tbl_height = str(height - 200) + "px"
                    else:
                        height = 250
                        tbl_height = str(height - 100) + "px"
                        
                    # Update table height
                    tbl_id = session.ns("irma_summary")
                    await session.send_custom_message(
                        "resizeITable", {"tbl_id": tbl_id, "height": height}
                    )
                    
                    print(f"DEBUG irma_summary: Returning ITable")
                    return ITable(
                        styled_df, classes="display nowrap compact",
                        columnDefs=[{"width":"auto", "targets":"_all"}],
                        style="width:100%;", showIndex=False, allow_html=True, select=True, scrollX=True, scrollY=tbl_height, scrollCollapse=True, paging=False, search=True, buttons=[{"extend": "csvHtml5", "filename": f"{selected_run}_irma_summary"}, {"extend": "excelHtml5", "filename": f"{selected_run}_irma_summary"}])
                else:
                    print(f"DEBUG irma_summary: DataFrame is empty")
                    df = pd.DataFrame([{"WARNINGS": "Cannot found IRMA Summary for this sequencing run."}])
                    return ITable(df, columnDefs=[{"targets":"_all", "className":"dt-center"}], showIndex=False, select=False, allow_html=True, style="width:100%;", scrollX=False, scrollY=False, scrollCollapse=False, paging=False, search=False)
            else:
                print(f"DEBUG irma_summary: File not found or not ready, hiding container")
                await session.send_custom_message(
                    "toggleContent", {"id": "irma-summary-container", "visible": False}
                )
                return
        except Exception as e:
            print(f"ERROR irma_summary: Unexpected error in irma_summary: {e}")
            import traceback
            traceback.print_exc()
            await session.send_custom_message(
                "toggleContent", {"id": "irma-summary-container", "visible": True}
            )
            df = pd.DataFrame([{"ERROR": f"Unexpected error: {str(e)}"}])
            return ITable(df, columnDefs=[{"targets":"_all", "className":"dt-center"}], showIndex=False, select=False, allow_html=True, style="width:100%;", scrollX=False, scrollY=False, scrollCollapse=False, paging=False, search=False)

    # Output coverage heatmap
    @output
    @render_widget
    async def coverage_heatmap():
        # Check if file exists using the poll
        files_status = check_files_exist()
        selected_run = input.seq_run()
        
        json_file = f"{data_root}/{selected_run}/mira_results/aggregate_outputs/dash-json/heatmap.json"
        
        # If file exists, read in the file
        if files_status.get('heatmap', False) and os.path.exists(json_file):
            await session.send_custom_message(
                "toggleContent", {"id": "coverage-heatmap-container", "visible": True}
            )
            # Load json as dict
            with open(json_file, 'r') as file:
                plot_data = json.load(file)
            # Remove heatmapgl from plot data
            try:
                del plot_data["layout"]["template"]["data"]["heatmapgl"]
            except KeyError:
                pass
            # Convert dictionary to Plotly figure
            fig = pio.from_json(pio.to_json(plot_data))
            return fig
        else:
            await session.send_custom_message(
                "toggleContent", {"id": "coverage-heatmap-container", "visible": False}
            )
            return

    # Create coverage plot sample ids list
    @output
    @render.ui
    async def coverage_sample():
        # Check if file exists using the poll
        files_status = check_files_exist()
        selected_run = input.seq_run()
        
        json_file = f"{data_root}/{selected_run}/mira_results/aggregate_outputs/dash-json/reads.json"
        
        # If file exists, read in the file
        if files_status.get('reads', False) and os.path.exists(json_file):
            await session.send_custom_message(
                "toggleContent", {"id": "coverage-container", "visible": True}
            )
            # Load json as dict
            df = pd.read_json(json_file, orient="split")
            # Get sample ids
            samples = df["Sample"].unique().tolist()
            # Create dropdown boxes
            return ui.input_selectize(
                id="coverage_sample_id",
                label=None,
                choices=samples,
                selected=None,
                multiple=False,
                width="100%",
                remove_button=None,
                options=None,
            )
        else:
            await session.send_custom_message(
                "toggleContent", {"id": "coverage-container", "visible": False}
            )
            return

    # Observe when a sample id is selected
    @reactive.effect
    @reactive.event(input.coverage_sample_id, ignore_none=False, ignore_init=False)
    def _():
        # Get inputs
        selected_run = input.seq_run()
        selected_sample_id = input.coverage_sample_id()
        # Check seq_run
        if not selected_run:
            coverage_error_message.set("Please select a sequencing run to generate the coverage plot")
            return
        # Check seq_run
        if not selected_sample_id:
            coverage_error_message.set("Please select a sample to generate the coverage plot")
            return
        # Reset error message
        coverage_error_message.set("")

    # Output error message for coverage plot
    @render.ui
    def coverage_error():
        req(coverage_error_message.get())
        return ui.TagList(
            ui.tags.p(
                ui.HTML(coverage_error_message.get()),
                class_="error-message",
            ),
        )

    # Display coverage read coverage for each sample id
    @output
    @render_widget
    def coverage_sample_sankeyfig():
        # Get reactive inputs
        seq_run = input.seq_run()
        sample_id = input.coverage_sample_id()
        
        json_file = f"{data_root}/{seq_run}/mira_results/aggregate_outputs/dash-json/readsfig_{sample_id}.json"
        # If file exists, read in the file
        if os.path.exists(json_file):
            # Load json as dict
            with open(json_file, 'r') as file:
                plot_data = json.load(file)
            # Remove heatmapgl from plot data
            try:
                del plot_data["layout"]["template"]["data"]["heatmapgl"]
            except KeyError:
                pass
            # Convert dictionary to Plotly figure
            fig = pio.from_json(pio.to_json(plot_data))
            return fig
        else:
            return

    # Display coverage plot for each sample id
    @output
    @render_widget
    def coverage_sample_fig():
        # Get reactive inputs
        seq_run = input.seq_run()
        sample_id = input.coverage_sample_id()
        
        y_axis_type = "linear"
        json_file = f"{data_root}/{seq_run}/mira_results/aggregate_outputs/dash-json/coveragefig_{sample_id}_{y_axis_type}.json"
        # If file exists, read in the file
        if os.path.exists(json_file):
            # Load json as dict
            with open(json_file, 'r') as file:
                plot_data = json.load(file)
            # Remove heatmapgl from plot data
            try:
                del plot_data["layout"]["template"]["data"]["heatmapgl"]
            except KeyError:
                pass
            # Convert dictionary to Plotly figure
            fig = pio.from_json(pio.to_json(plot_data))
            return fig
        else:
            return

    # Output variants table
    @output
    @render_widget
    async def variants_table():
        # Check if file exists using the poll
        files_status = check_files_exist()
        selected_run = input.seq_run()
        
        json_file = f"{data_root}/{selected_run}/mira_results/aggregate_outputs/dash-json/dais_vars.json"
        
        # Read in the file
        if files_status.get('variants', False) and os.path.exists(json_file):
            await session.send_custom_message(
                "toggleContent", {"id": "variants-container", "visible": True}
            )
            # Load json as dict
            df = pd.read_json(json_file, orient="split")
            # Display df if not empty
            if not df.empty:
                # Determine the height of table based on number of rows
                if df.shape[0] > 5:
                    height = 550;
                    tbl_height = str(height - 200) + "px"
                else:
                    height = 250
                    tbl_height = str(height - 100) + "px"
                # Update table height
                tbl_id = session.ns("variants_table")
                await session.send_custom_message(
                    "resizeITable", {"tbl_id": tbl_id, "height": height}
                )
                # Return table
                return ITable(df, classes="display nowrap compact", columnDefs=[{"width":"auto", "targets":"_all"}], style="width:100%;", showIndex=False, allow_html=True, select=True, scrollX=True, scrollY=tbl_height, scrollCollapse=True, paging=False, search=True, buttons=[{"extend": "csvHtml5", "filename": f"{selected_run}_variants_tbl"}, {"extend": "excelHtml5", "filename": f"{selected_run}_variants_tbl"}])
            else:
                df = pd.DataFrame([{"WARNINGS": "There are no AA Variants found for this sequencing run."}])
                return ITable(df, columnDefs=[{"targets":"_all", "className":"dt-center"}], showIndex=False, select=False, allow_html=True, style="width:100%;", scrollX=False, scrollY=False, scrollCollapse=False, paging=False, search=False)
        else:
            await session.send_custom_message(
                "toggleContent", {"id": "variants-container", "visible": False}
            )
            return

    # Output minor vairants table
    @output
    @render_widget
    async def minor_variants_table():
        # Check if file exists using the poll
        files_status = check_files_exist()
        selected_run = input.seq_run()
        
        json_file = f"{data_root}/{selected_run}/mira_results/aggregate_outputs/dash-json/minor_variants.json"
        
        # Read in the file
        if files_status.get('snvs', False) and os.path.exists(json_file):
            await session.send_custom_message(
                "toggleContent", {"id": "snvs-container", "visible": True}
            )
            # Load json as dict
            df = pd.read_json(json_file, orient="split")
            # Display df if not empty
            if not df.empty:
                # Determine the height of table based on number of rows
                if df.shape[0] > 5:
                    height = 550
                    tbl_height = str(height - 200) + "px"
                else:
                    height = 250
                    tbl_height = str(height - 100) + "px"
                # Update table height
                tbl_id = session.ns("minor_variants_table")
                await session.send_custom_message(
                    "resizeITable", {"tbl_id": tbl_id, "height": height}
                )
                # Return table
                return ITable(df, classes="display nowrap compact", columnDefs=[{"width":"100%", "targets":"_all"}], style="width:100%; height:100%;", showIndex=False, allow_html=True, select=True, scrollX=True, scrollY=tbl_height, scrollCollapse=True, paging=False, search=True, buttons=[{"extend": "csvHtml5", "filename": f"{selected_run}_snvs_tbl"}, {"extend": "excelHtml5", "filename": f"{selected_run}_snvs_tbl"}])
            else:
                df = pd.DataFrame([{"WARNINGS": "There are no Minor SNVs found for this sequencing run."}])
                return ITable(df, columnDefs=[{"targets":"_all", "className":"dt-center"}], showIndex=False, select=False, allow_html=True, style="width:100%;", scrollX=False, scrollY=False, scrollCollapse=False, paging=False, search=False)
        else:
            await session.send_custom_message(
                "toggleContent", {"id": "snvs-container", "visible": False}
            )
            return

    # Output indels table
    @output
    @render_widget
    async def indels_table():
        # Check if file exists using the poll
        files_status = check_files_exist()
        selected_run = input.seq_run()
        
        json_file = f"{data_root}/{selected_run}/mira_results/aggregate_outputs/dash-json/indels.json"
        
        # Read in the file
        if files_status.get('indels', False) and os.path.exists(json_file):
            await session.send_custom_message(
                "toggleContent", {"id": "indels-container", "visible": True}
            )
            # Load json as dict
            df = pd.read_json(json_file, orient="split")
            # Display df if not empty
            if not df.empty:
                # Determine the height of table based on number of rows
                if df.shape[0] > 5:
                    height = 550;
                    tbl_height = str(height - 200) + "px"
                else:
                    height = 250
                    tbl_height = str(height - 100) + "px"
                # Update table height
                tbl_id = session.ns("indels_table")
                await session.send_custom_message(
                    "resizeITable", {"tbl_id": tbl_id, "height": height}
                )
                # Return table
                return ITable(df, classes="display nowrap compact", columnDefs=[{"width":"auto", "targets":"_all"}], style="width: 100%; height:100%;", showIndex=False, allow_html=True, select=True, scrollX=False, scrollY=tbl_height, scrollCollapse=True, paging=False, search=True, buttons=[{"extend": "csvHtml5", "filename": f"{selected_run}_indels_tbl"}, {"extend": "excelHtml5", "filename": f"{selected_run}_indels_tbl"}])
            else:
                df = pd.DataFrame([{"WARNINGS": "There are no <span class='fw-bold text-primary'>Minor Indels and Deletions</span> found for this sequencing run."}])
                return ITable(df, columnDefs=[{"targets":"_all", "className":"dt-center"}], showIndex=False, select=False, allow_html=True, style="width: 100%;", scrollX=False, scrollY=False, scrollCollapse=False, paging=False, search=False)
        else:
            await session.send_custom_message(
                "toggleContent", {"id": "indels-container", "visible": False}
            )
            return
    
    # Check fasta files and update visibility
    @reactive.effect
    async def check_fasta_files():
        # Check if file exists using the poll
        files_status = check_files_exist()
        
        # Check passed fastas
        if files_status.get('passed_nt', False) or files_status.get('passed_aa', False):
            await session.send_custom_message(
                "toggleContent", {"id": "download-passed-fasta-container", "visible": True}
            )
            if not files_status.get('passed_nt', False):
                btn_id = session.ns("download_passed_nt_fasta")
                await session.send_custom_message(
                    "toggleContent", {"id": btn_id, "visible": False}
                )
            if not files_status.get('passed_aa', False):
                btn_id = session.ns("download_passed_aa_fasta")
                await session.send_custom_message(
                    "toggleContent", {"id": btn_id, "visible": False}
                )
        else:
            await session.send_custom_message(
                "toggleContent", {"id": "download-passed-fasta-container", "visible": False}
            )
            
        # Check failed fastas
        if files_status.get('failed_nt', False) or files_status.get('failed_aa', False):
            await session.send_custom_message(
                "toggleContent", {"id": "download-failed-fasta-container", "visible": True}
            )
            if not files_status.get('failed_nt', False):
                btn_id = session.ns("download_failed_nt_fasta")
                await session.send_custom_message(
                    "toggleContent", {"id": btn_id, "visible": False}
                )
            if not files_status.get('failed_aa', False):
                btn_id = session.ns("download_failed_aa_fasta")
                await session.send_custom_message(
                    "toggleContent", {"id": btn_id, "visible": False}
                )
        else:
            await session.send_custom_message(
                "toggleContent", {"id": "download-failed-fasta-container", "visible": False}
            )

    # Download passed nt fasta
    @render.download
    def download_passed_nt_fasta():
        # Get inputs
        selected_run = input.seq_run()
        fasta_file = f"{data_root}/{selected_run}/mira_results/aggregate_outputs/mira-reports/mira_{selected_run}_amended_consensus.fasta"
        return fasta_file

    # Download passed aa fasta
    @render.download
    def download_passed_aa_fasta():
        # Get inputs
        selected_run = input.seq_run()
        fasta_file = f"{data_root}/{selected_run}/mira_results/aggregate_outputs/mira-reports/mira_{selected_run}_amino_acid_consensus.fasta"
        return fasta_file

    # Download failed nt fasta
    @render.download
    def download_failed_nt_fasta():
        # Get inputs
        selected_run = input.seq_run()
        fasta_file = f"{data_root}/{selected_run}/mira_results/aggregate_outputs/mira-reports/mira_{selected_run}_failed_amended_consensus.fasta"
        return fasta_file

    # Download failed aa fasta
    @render.download
    def download_failed_aa_fasta():
        # Get inputs
        selected_run = input.seq_run()
        fasta_file = f"{data_root}/{selected_run}/mira_results/aggregate_outputs/mira-reports/mira_{selected_run}_failed_amino_acid_consensus.fasta"
        return fasta_file