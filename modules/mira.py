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
                    href="#irma_head",
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
                    href="#alleles_head",
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
                        id="watch_irma_progress", label="Watch MIRA Progress", value=True,
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
                        id="seq_organism",
                        label=ui.HTML("<span style='color:red'>*</span>Select an Organism:"),
                        choices=seq_organisms,
                        selected=None,
                        multiple=False,
                        width="100%",
                        remove_button=None,
                        options=None,
                    ),
                ),
                ui.column(6, 
                    ui.input_selectize(
                        id="seq_experiment_type",
                        label=ui.HTML("<span style='color:red'>*</span>Select an Instructment Type:"),
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
                    ui.tags.h3("IRMA Progress"),
                ),
                ui.column(12,
                    ui.output_ui(
                        id="irma_progress",
                        inline=False,
                        container=False,
                        fill=True,
                        fillable=False,
                    ),
                ),
                class_="irma-progress-content content-container", id="irma-progress-content",
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
                    ui.tags.h3("MIRA Summary", id="irma_head"),
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
                    ui.tags.h3("Minor SNVs", id="alleles_head"),
                    output_widget(id="minor_alleles_table"),
                    class_="snvs-container content-container", id="snvs-container",
                ),                 
                ui.column(12, 
                    ui.tags.h3("Minor Insertions and Deletions", id="indels_head"),
                    output_widget(id="indels_table"),
                    class_="indels-container content-container", id="indels-container",
                ),                 
                ui.row(
                    ui.column(12, 
                        ui.tags.h3("Download Passed Fastas", id="dl_fastas"),
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
                        ui.tags.h3("Download Failed Fastas", id="dl_fastas"),
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
def mira_server(input, output, session, data_root, samplesheet_html_tbl, spyne_command_type):
  
    # Create local variable to store irma progress and its completion status
    track_irma_progress = None
    irma_assembly_task = None
  
    # Create reative value to store status of irma
    irma_completion_status = reactive.value()
    
    # Create reative value to store error message
    start_assembly_counter = reactive.value()
    
    # Create reative value to store error message
    samplesheet_tbl_message = reactive.value()
    
    # Reactive value to store indels
    irma_progress_message = reactive.Value() 
    
    # Create reative value to store error message
    coverage_error_message = reactive.value() 
    
    # Reactive value to track if download is triggered
    orig_samplesheet_tbl = reactive.Value(pd.DataFrame())  
    
    # Reactive value to store barcode assignment
    barcode_dist_file = reactive.Value() 
    
    # Reactive value to QC statement
    qc_statement_file = reactive.Value() 
    
    # Reactive value to store pass/fail samples
    quality_control_file = reactive.Value() 
    
    # Reactive value to store summary
    irma_summary_file = reactive.Value() 
    
    # Reactive value to store coverage table
    coverage_heatmap_file = reactive.Value() 
    
    # Reactive value to store coverage table
    coverage_sample_file = reactive.Value() 
    
    # Reactive value to store minor variants
    mira_variants_file = reactive.Value() 
            
    # Reactive value to store single coverage lot
    mira_snvs_file = reactive.Value() 

    # Reactive value to store indels
    mira_indels_file = reactive.Value() 
    
    # Reactive values to store fasta files
    passed_nt_file = reactive.Value()
    passed_aa_file = reactive.Value()
    failed_nt_file = reactive.Value()
    failed_aa_file = reactive.Value()
        
    # Observe sequencing run selection
    @reactive.effect
    @reactive.event(input.seq_run, ignore_none=False, ignore_init=False)
    async def _():
        # Get selected sequencing run
        selected_run = input.seq_run()
        # Extract run organism
        check_run_organism = re.compile(r"^(rsv|sc2-spike|sc2|flu)(-|_)", re.IGNORECASE).match(selected_run)
        # Update organism
        if check_run_organism:
            pattern = check_run_organism.group(1)
            matched_organisms = {i: i for i in seq_organisms.keys() if re.match(pattern, i, re.IGNORECASE)}
            selected_organism = seq_organisms[list(matched_organisms.keys())[0]] if len(matched_organisms) > 0 else input.seq_organism()
        else:
            selected_organism = input.seq_organism()
        # Update organism
        ui.update_selectize(
            id="seq_organism",
            selected=selected_organism,
            session=session,
        )
        # Define samplesheet file
        samplesheet_file = f"{data_root}/{selected_run}/samplesheet.csv"
        # Get samplesheet
        ss_df, selected_experiment_type = parse_samplesheet(samplesheet_file = samplesheet_file)
        # Update samplesheet
        orig_samplesheet_tbl.set(ss_df)   
        # Update experiment types
        if selected_organism == 'SC2-Spike-Only':
            ui.update_selectize(
                id="seq_experiment_type",
                choices={"ONT": "ONT"},
                selected=["ONT"],
                session=session,
            )
        else:
            ui.update_selectize(
                id="seq_experiment_type",
                choices=seq_experiment_types,
                selected=selected_experiment_type if selected_experiment_type in seq_experiment_types.keys() else seq_experiment_types[list(seq_experiment_types.keys())[0]],
                session=session,
            )
        # Update amplicon library
        if selected_organism == 'SC2-Whole-Genome' and selected_experiment_type == 'Illumina':
            ui.update_selectize(
                id="seq_amplicon_library",
                choices=sc2_amplicon_libraries,
                session=session,
            )
            await session.send_custom_message(
                "toggleAmpliconContent", {"id": "amplicon-library-container", "visible": True, "label": "For Illumina SC2, Which Primer Schema Was Used?"}
            )
        elif selected_organism == 'RSV' and selected_experiment_type == 'Illumina':
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
        # Reset irma progress and its message
        nonlocal track_irma_progress
        track_irma_progress = None
        irma_progress_message.set('Press the <span class="text-info text-emphasis">"START GENOME ASSEMBLY"</span> button to start the assembly process!')
        # Reset assembly task
        nonlocal irma_assembly_task
        irma_assembly_task = None
        # Reset assembly counter 
        start_assembly_counter.set("")
        # Reset assembly completion status
        irma_completion_status.set("")
        # Update result files
        barcode_dist_file.set(f"{data_root}/{selected_run}/dash-json/barcode_distribution.json")
        qc_statement_file.set(f"{data_root}/{selected_run}/dash-json/qc_statement.json")
        quality_control_file.set(f"{data_root}/{selected_run}/dash-json/pass_fail_heatmap.json")
        irma_summary_file.set(f"{data_root}/{selected_run}/dash-json/irma_summary.json")
        coverage_heatmap_file.set(f"{data_root}/{selected_run}/dash-json/heatmap.json")
        coverage_sample_file.set(f"{data_root}/{selected_run}/dash-json/reads.json")
        mira_variants_file.set(f"{data_root}/{selected_run}/dash-json/dais_vars.json")
        mira_snvs_file.set(f"{data_root}/{selected_run}/dash-json/alleles.json")
        mira_indels_file.set(f"{data_root}/{selected_run}/dash-json/indels.json")
        passed_nt_file.set(f"{data_root}/{selected_run}/amended_consensus.fasta")
        passed_aa_file.set(f"{data_root}/{selected_run}/amino_acid_consensus.fasta")
        failed_nt_file.set(f"{data_root}/{selected_run}/failed_amended_consensus.fasta")
        failed_aa_file.set(f"{data_root}/{selected_run}/failed_amino_acid_consensus.fasta")
        
    # Observe organism selection
    @reactive.effect
    @reactive.event(input.seq_organism, ignore_none=True, ignore_init=True)
    async def _():
        # Get inputs
        selected_organism = input.seq_organism()
        selected_experiment_type = input.seq_experiment_type()
        if selected_organism == 'SC2-Spike-Only':
            ui.update_selectize(
                id="seq_experiment_type",
                choices={"ONT": "ONT"},
                selected=["ONT"],
                session=session,
            )
        else:
            ui.update_selectize(
                id="seq_experiment_type",
                choices=seq_experiment_types,
                selected=selected_experiment_type if selected_experiment_type in seq_experiment_types.keys() else seq_experiment_types[list(seq_experiment_types.keys())[0]],
                session=session,
            )
         # Update amplicon library
        if selected_organism == 'SC2-Whole-Genome' and selected_experiment_type == 'Illumina':
            ui.update_selectize(
                id="seq_amplicon_library",
                choices=sc2_amplicon_libraries,
                session=session,
            )
            await session.send_custom_message(
                "toggleAmpliconContent", {"id": "amplicon-library-container", "visible": True, "label": "For Illumina SC2, Which Primer Schema Was Used?"}
            )
        elif selected_organism == 'RSV' and selected_experiment_type == 'Illumina':
            ui.update_selectize(
                id="seq_amplicon_library",
                choices=rsv_amplicon_libraries,
                session=session,
            )
            await session.send_custom_message(
                "toggleAmpliconContent", {"id": "amplicon-library-container", "visible": True, "label": "For Illumina RSV, Which Primer Schema Was Used?"}
            )
        else:
            await session.send_custom_message(
                "toggleAmpliconContent", {"id": "amplicon-library-container", "invisible": False, "label": ""}
            )
  
    # Observe organism selection
    @reactive.effect
    @reactive.event(input.seq_experiment_type, ignore_none=True, ignore_init=True)
    async def _():
        # Get inputs
        selected_organism = input.seq_organism()
        selected_experiment_type = input.seq_experiment_type()
        selected_amplicon_library = input.seq_amplicon_library()
        # Update amplicon library
        if selected_organism == 'SC2-Whole-Genome' and selected_experiment_type == 'Illumina':
            ui.update_selectize(
                id="seq_amplicon_library",
                choices=sc2_amplicon_libraries,
                selected=selected_amplicon_library if selected_amplicon_library in sc2_amplicon_libraries.keys() else sc2_amplicon_libraries[list(sc2_amplicon_libraries.keys())[0]],
                session=session,
            )
            await session.send_custom_message(
                "toggleAmpliconContent", {"id": "amplicon-library-container", "visible": True, "label": "For Illumina SC2, Which Primer Schema Was Used?"}
            )
        elif selected_organism == 'RSV' and selected_experiment_type == 'Illumina':
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
            selected_organism = input.seq_organism()
            ss_df, selected_experiment_type = parse_samplesheet(samplesheet_file = file[0]["datapath"])
            # Update experiment type
            if not ss_df.empty:
                if selected_organism == 'SC2-Spike-Only':
                    ui.update_selectize(
                        id="seq_experiment_type",
                        choices={"ONT": "ONT"},
                        selected=["ONT"],
                        session=session,
                    )
                else:
                    ui.update_selectize(
                        id="seq_experiment_type",
                        choices=seq_experiment_types,
                        selected=selected_experiment_type if selected_experiment_type in seq_experiment_types.keys() else seq_experiment_types[list(seq_experiment_types.keys())[0]],
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
          
    # Observe when watch irma progress is selected
    @reactive.effect
    @reactive.event(input.watch_irma_progress, ignore_none=False, ignore_init=False)
    async def watch_btn_click():
        if input.watch_irma_progress():
            await session.send_custom_message(
                "toggleContent", {"id": "irma-progress-content", "visible": True}
            )
        else:
            await session.send_custom_message(
                "toggleContent", {"id": "irma-progress-content", "visible": False}
            )

    # Display IRMA progress
    @output
    @render.ui
    def irma_progress():
        req(input.watch_irma_progress(), irma_progress_message.get())
        return ui.HTML(irma_progress_message.get())
        
    # Display IRMA progress
    @reactive.effect
    def get_irma_progress():
        reactive.invalidate_later(3)
        nonlocal track_irma_progress
        req(track_irma_progress == True)
        counter = start_assembly_counter.get()
        seq_run = input.seq_run()          
        if counter == "start":
            logs = glob(f"{data_root}/{seq_run}/logs/*irma*out.log")
            if os.path.exists(f"{data_root}/{seq_run}/.snakemake") and len(logs) == 0:
                irma_progress_message.set("Data processing has started, please wait...")
                return
            if (len(glob(f"{data_root}/{seq_run}/spyne_logs.tar.gz")) == 1) and (len(glob(f"{data_root}/{seq_run}/dash-json")) == 0):
                irma_progress_message.set("The sequencing run has failed. Please contact us at IDSeqsupport@cdc.gov!")
                irma_completion_status.set("fail")
                track_irma_progress = False
                return
            if (len(glob(f"{data_root}/{seq_run}/spyne_logs.tar.gz")) == 1) and len(glob(f"{data_root}/{seq_run}/dash-json")) == 1:
                irma_progress_message.set("MIRA has finished running! Resulting figures and tables will be displayed below.")
                irma_completion_status.set("success")
                track_irma_progress = False
            if len(logs) > 0:
                log_dic = {}
                for l in logs:
                    sample = l.split("/")[-1].split(".")[0]
                    with open(l, "r") as d:
                        log_dic[sample] = "".join(d.readlines())
                finished_samples = [i for i in log_dic.keys() if "finished!" in log_dic[i].lower()]
                running_samples = {
                    i: f"  ".join(j.split("\t"))
                    for i, j in log_dic.items()
                    if i not in finished_samples
                }
                df = pd.DataFrame.from_dict(running_samples, orient="index")
                if not df.empty:
                    df = df.reset_index()
                    df.replace(to_replace=r'\n', value='<br>', regex=True, inplace=True)
                    df.columns = ["Sample", "IRMA Stage"]
                    irma_progress_message.set(
                        ui.HTML(f"<p>MIRA Finished Samples: {', '.join(finished_samples)}</p>") +
                        ui.HTML(df.to_html(index=False, escape=False, justify="left", table_id="irma_progress_tbl"))
                    )
        elif counter == "stop":
            irma_progress_message.set('MIRA run is interrupted.')
            irma_completion_status.set("interrupted")
            track_irma_progress = False
        
    # Trigger the assembly button 
    @reactive.effect
    @reactive.event(input.trigger_assembly_button, ignore_none=True, ignore_init=True)
    async def _():
            samplesheet_tbl_id = session.ns("samplesheet_tbl")
            assembly_btn_id = session.ns("start_assembly_button")
            await session.send_custom_message(
                "triggerAssemblyBtn", {"assembly_btn_id": assembly_btn_id, "samplesheet_tbl_id": samplesheet_tbl_id}
            )
            
    # Stop the assembly button 
    @reactive.effect
    @reactive.event(input.stop_assembly_button, ignore_none=True, ignore_init=True)
    async def stop_assembly_task():
        nonlocal irma_assembly_task
        counter = start_assembly_counter.get()
        # Get assembly counter    
        if counter == "start":
            # Wait for assembly worker to run for 5 seconds before attempt to stop the process
            await asyncio.sleep(5)               
            # Cancel the task if it exists
            if irma_assembly_task.pid is None:
                print(f"Cancel the assembly task with PID: {irma_assembly_task.pid}")
                os.kill(irma_assembly_task.pid, signal.SIGKILL)
                # Wait until process is completed
                await irma_assembly_task.wait()            
            # Set assembly counter to stop
            start_assembly_counter.set("stop")
            # Hide assembly content
            await session.send_custom_message(
                "toggleAssemblyContent", {"id": "mira-assembly-content", "visible": False}
            )
            # Enable assembly button again
            seq_run_id = session.ns("seq_run")
            assembly_btn_id = session.ns("trigger_assembly_button")
            await session.send_custom_message(
                "disableAssemblyBtn", {"seq_run_id": seq_run_id, "assembly_btn_id": assembly_btn_id, "disabled": False}
            )
            # Return message
            samplesheet_tbl_message.set("The assembly run has been interrupted.")
        else:
            # Return message
            samplesheet_tbl_message.set("There is no assembly running in progress.")

    # Start the assembly task when assembly button was clicked
    @ui.bind_task_button(button_id="start_assembly_button")
    @reactive.extended_task
    async def start_assembly_task(data_root, seq_run, organism, experiment_type, amplicon_library, spyne_command_type):
        nonlocal track_irma_progress
        nonlocal irma_assembly_task
        # Construct the command to run IRMA
        if spyne_command_type == "docker":
            docker_cmd = "docker exec -it spyne bash /spyne/MIRA.sh "
            docker_cmd += f"-s /data/{seq_run}/samplesheet.csv "
            docker_cmd += f"-r /data/{seq_run} "
        elif spyne_command_type == "bash":
            docker_cmd = "bash /spyne/MIRA.sh "
            docker_cmd += f"-s {data_root}/{seq_run}/samplesheet.csv "
            docker_cmd += f"-r {data_root}/{seq_run} "            
        docker_cmd += f"-e {organism}-{experiment_type} "
        docker_cmd += "-a "
        if organism in ["SC2-Whole-Genome", "RSV"] and experiment_type == "Illumina":
            docker_cmd += f"-p {amplicon_library} "
        docker_cmd += f"-c CLEANUP-FOOTPRINT"
        # Start subproccess to run IRMA
        irma_assembly_task = await asyncio.create_subprocess_shell(docker_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        print(f"Start the assembly task with PID: {irma_assembly_task.pid}")
        # Let the worker run for 3 seconds
        await asyncio.sleep(3)
        # Start tracking irma progress and start assembly counter
        track_irma_progress = True
        start_assembly_counter.set("start")  
        # Enable the stop button once task is running
        stop_btn_id = session.ns("stop_assembly_button")
        await session.send_custom_message(
            "disableBtn", {"id": stop_btn_id, "disabled": False}
        )
        # return
        return irma_assembly_task
      
    # Observe once start_assembly_task() is completed
    @reactive.effect
    async def _():
        reactive.invalidate_later(3)
        req(irma_completion_status.get() in ["success", "fail"])
        # Show the assembly content
        await session.send_custom_message(
            "toggleAssemblyContent", {"id": "mira-assembly-content", "visible": True}
        )
        # Enable the assembly button again
        seq_run_id = session.ns("seq_run")
        assembly_btn_id = session.ns("trigger_assembly_button")
        await session.send_custom_message(
            "disableAssemblyBtn", {"seq_run_id": seq_run_id, "assembly_btn_id": assembly_btn_id, "disabled": False}
        )
        # Update result files
        selected_run = input.seq_run()
        barcode_dist_file.set(f"{data_root}/{selected_run}/dash-json/barcode_distribution.json")
        qc_statement_file.set(f"{data_root}/{selected_run}/dash-json/qc_statement.json")
        quality_control_file.set(f"{data_root}/{selected_run}/dash-json/pass_fail_heatmap.json")
        irma_summary_file.set(f"{data_root}/{selected_run}/dash-json/irma_summary.json")
        coverage_heatmap_file.set(f"{data_root}/{selected_run}/dash-json/heatmap.json")
        coverage_sample_file.set(f"{data_root}/{selected_run}/dash-json/reads.json")
        mira_variants_file.set(f"{data_root}/{selected_run}/dash-json/dais_vars.json")
        mira_snvs_file.set(f"{data_root}/{selected_run}/dash-json/alleles.json")
        mira_indels_file.set(f"{data_root}/{selected_run}/dash-json/indels.json")
        passed_nt_file.set(f"{data_root}/{selected_run}/amended_consensus.fasta")
        passed_aa_file.set(f"{data_root}/{selected_run}/amino_acid_consensus.fasta")
        failed_nt_file.set(f"{data_root}/{selected_run}/failed_amended_consensus.fasta")
        failed_aa_file.set(f"{data_root}/{selected_run}/failed_amino_acid_consensus.fasta")
        # Update message accordingly to success or fail
        if irma_completion_status.get() == "success":
            samplesheet_tbl_message.set("")
        elif irma_completion_status.get() == "fail":
            samplesheet_tbl_message.set("The sequencing run has failed or was canceled. Please re-run the assembly again. If the problem persists, please contact us at IDSeqsupport@cdc.gov!")
        # Reset the completion status    
        irma_completion_status.set("")
  
    # Observe when start_assembly_button is clicked
    @reactive.effect
    @reactive.event(input.start_assembly_button, ignore_none=True, ignore_init=True)
    async def start_assembly_click():
        # Get inputs
        selected_run = input.seq_run()
        selected_organism = input.seq_organism()
        selected_experiment_type = input.seq_experiment_type()
        selected_amplicon_library = input.seq_amplicon_library()
        ss_html_tbl = samplesheet_html_tbl.get()
        # Check seq_run
        if not selected_run:
            samplesheet_tbl_message.set("Please select a sequencing run to start the assembly!")
            return
        # Check seq_organism
        if not selected_organism:
            samplesheet_tbl_message.set("Please select an organism to start the assembly!")
            return
        # Check experiment types
        if not selected_experiment_type:
            samplesheet_tbl_message.set("Please select an experiment type to start the assembly!")
            return
        # Check amplicon library
        if selected_organism in ["SC2-Spike-Only", "RSV"] and selected_experiment_type.upper() == "ILLUMINA" and not selected_amplicon_library:
            samplesheet_tbl_message.set(f"For {selected_organism} {selected_experiment_type}, please select a Primer Schema to start the assembly!")
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
        # Check column names for each experiment type
        if "ONT" in selected_experiment_type.upper() and any([col not in ss_df.columns for col in ont_ss_colnames]):
            samplesheet_tbl_message.set(f"Invalid Samplesheet for a Nanopore run!! Please reload the Samplesheet with the required column names: {ont_ss_colnames}")
            return
        elif "ILLUMINA" in selected_experiment_type.upper() and any([col not in ss_df.columns for col in illumina_ss_colnames]):
            samplesheet_tbl_message.set(f"Invalid Samplesheet for an Illumina run!! Please reload the Samplesheet with the required column names: {illumina_ss_colnames}")
            return
        # Check for duplicated
        if True in list(ss_df["Sample ID"].duplicated(keep=False)):
            duplicated_ids = list(ss_df["Sample ID"].loc[ss_df["Sample ID"].duplicated(keep=False) == True])
            samplesheet_tbl_message.set(f"No duplicated Sample IDs allowed. Duplicates = {duplicated_ids}")
            return
        # Check for white spaces
        if True in list(ss_df["Sample ID"].str.contains(r"\s")):
            ids_with_spaces = list(ss_df["Sample ID"].loc[ss_df["Sample ID"].str.contains(r"\s") == True])
            samplesheet_tbl_message.set(f"No spaces allowed in Sample IDs. Offenders = {ids_with_spaces}")
            return
        # Check for forward or backward slashes
        if True in list(ss_df["Sample ID"].str.contains(r"[\\/]")):
            ids_with_slashes = list(ss_df["Sample ID"].loc[ss_df["Sample ID"].str.contains(r"[\\/]") == True])
            samplesheet_tbl_message.set(f"No forward slashes ('/') or backward slashes ('\\') allowed in Sample IDs. Offenders = {ids_with_slashes}")
            return
        # Check sample type (- control, + control, test, etc)
        if True in list(~ss_df["Sample Type"].isin(sample_type_options)):
            id_list = list(ss_df["Sample ID"].loc[~ss_df["Sample Type"].isin(sample_type_options)])
            samplesheet_tbl_message.set(f"Invalid Sample Type for Sample ID = {id_list}. Options are {sample_type_options}")
            return   
        # Create place holder to check sample files
        check_sample_files = []
        # Check if sample id folder exists for ILLUMINA 
        if "ILLUMINA" in selected_experiment_type.upper():
            for id in ss_df["Sample ID"]:
               sample_file = glob(f"{data_root}/{selected_run}/fastq*/{id}*R[12]*fastq*")
               if len(sample_file) < 2:
                    check_sample_files.append(True)
               else:
                    check_sample_files.append(False)
        # Check if barcode id folder exists for ONT 
        elif "ONT" in selected_experiment_type.upper():
            for id in ss_df["Barcode #"]:
               sample_file = glob(f"{data_root}/{selected_run}/fastq_pass/{id}/*fastq*")
               if len(sample_file) == 0:
                    check_sample_files.append(True)
               else:
                    check_sample_files.append(False)
        # Check sample files
        if True in check_sample_files and "ILLUMINA" in selected_experiment_type.upper():
              id_list = list(ss_df["Sample ID"].loc[check_sample_files])
              samplesheet_tbl_message.set(f"Cannot find {selected_experiment_type} fastq files for Sample ID = {id_list}. Make sure fastq files have both R1 and R2 for paired-end run. Please check your run folder again!")
              return 
        elif True in check_sample_files and "ONT" in selected_experiment_type.upper():
              id_list = list(ss_df["Barcode #"].loc[check_sample_files])
              samplesheet_tbl_message.set(f"Cannot find {selected_experiment_type} fastq files for Barcoder # = {id_list}. Please check your run folder again!")
              return    
        # Save the final validated samplesheet
        ss_df.to_csv(f"{data_root}/{selected_run}/samplesheet.csv", index=False)
        # Remove empty generated samplesheet. The real samplesheet is saved as samplesheet.csv
        if len(glob(f"{data_root}/{selected_run}/{selected_run}_samplesheet.xlsx")) > 0:
            os.remove(f"{data_root}/{selected_run}/{selected_run}_samplesheet.xlsx") 
        # Remove fastas from run folder to re-start and track the assembly process again
        fasta_files = glob(f"{data_root}/{selected_run}/*amended_consensus.fasta") + glob(f"{data_root}/{selected_run}/*amino_acid_consensus.fasta")
        if len(fasta_files) > 0:
            for i in fasta_files:
                os.remove(i) 
        # Reset message and result files  
        irma_progress_message.set("Preparing data files. Please wait...")
        samplesheet_tbl_message.set("")
        barcode_dist_file.set("")
        qc_statement_file.set("")
        quality_control_file.set("")
        irma_summary_file.set("")
        coverage_heatmap_file.set("")
        coverage_sample_file.set("")
        mira_variants_file.set("")
        mira_snvs_file.set("")
        mira_indels_file.set("")
        passed_nt_file.set("")
        passed_aa_file.set("")
        failed_nt_file.set("")
        failed_aa_file.set("")
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
        # Start the assembly task as a background process
        start_assembly_task(data_root=data_root, seq_run=selected_run, organism=selected_organism, experiment_type=selected_experiment_type, amplicon_library=selected_amplicon_library, spyne_command_type=spyne_command_type)
        
    # Display barcode distribution plot
    @output
    @render_widget
    async def demux_fig():
        # Get reactive input
        json_file = barcode_dist_file.get()
        # Re-create widget if the json file changes
        with reactive.isolate():        
            # If file exists, read in the file
            if os.path.exists(json_file):
                await session.send_custom_message(
                    "toggleContent", {"id": "barcode-container", "visible": True}
                )
                # Load json as dict
                with open(json_file, 'r') as file:
                    plot_data = json.load(file)
                # Remove heatmapgl from plot data as heatmapgl is deprecated and no longer used in plotly
                try:
                    del plot_data["layout"]["template"]["data"]["heatmapgl"]
                except KeyError:
                    print("heatmapgl does not exist in plot data.")
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
        # Get reactive input
        json_file = qc_statement_file.get()
        # Re-create widget if the json file changes
        with reactive.isolate():
            # Read in the file
            if os.path.exists(json_file):
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
        # Get reactive input
        json_file = quality_control_file.get()
        # Re-create widget if the json file changes
        with reactive.isolate():
            # If file exists, read in the file
            if os.path.exists(json_file):
                await session.send_custom_message(
                    "toggleContent", {"id": "pass-fail-container", "visible": True}
                )
                # Load json as dict
                with open(json_file, 'r') as file:
                    plot_data = json.load(file)
                # Remove heatmapgl from plot data as heatmapgl is deprecated and no longer used in plotly
                try:
                    del plot_data["layout"]["template"]["data"]["heatmapgl"]
                except KeyError:
                    print("heatmapgl does not exist in plot data.")
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
        # Get reactive input
        json_file = irma_summary_file.get()
        # Re-create widget if the json file changes
        with reactive.isolate():
            # Read in the file
            if os.path.exists(json_file):
                await session.send_custom_message(
                    "toggleContent", {"id": "irma-summary-container", "visible": True}
                )
                # Load json as dict
                df = pd.read_json(json_file, orient="split")
                # Display df if not empty
                if not df.empty:
                    seq_run = input.seq_run()
                    styled_df = fill_irma_summary_tbl(df=df, n_bins=8, columns="all")
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
                    return ITable(
                        styled_df, classes="display nowrap compact",
                        columnDefs=[{"width":"auto", "targets":"_all"}],
                        style="width:100%;", showIndex=False, allow_html=True, select=True, scrollX=True, scrollY=tbl_height, scrollCollapse=True, paging=False, search=True, buttons=[{"extend": "csvHtml5", "filename": f"{seq_run}_irma_summary"}, {"extend": "excelHtml5", "filename": f"{seq_run}_irma_summary"}])
                else:
                    df = pd.DataFrame([{"WARNINGS": "Cannot found IRMA Summary for this sequencing run."}])
                    return ITable(df, columnDefs=[{"targets":"_all", "className":"dt-center"}], showIndex=False, select=False, allow_html=True, style="width:100%;", scrollX=False, scrollY=False, scrollCollapse=False, paging=False, search=False)
            else:
                await session.send_custom_message(
                    "toggleContent", {"id": "irma-summary-container", "visible": False}
                )
                return

    # Output coverage heatmap
    @output
    @render_widget
    async def coverage_heatmap():
        # Get reactive input
        json_file = coverage_heatmap_file.get()
        # Re-create widget if the json file changes
        with reactive.isolate():
            # If file exists, read in the file
            if os.path.exists(json_file):
                await session.send_custom_message(
                    "toggleContent", {"id": "coverage-heatmap-container", "visible": True}
                )
                # Load json as dict
                with open(json_file, 'r') as file:
                    plot_data = json.load(file)
                # Remove heatmapgl from plot data as heatmapgl is deprecated and no longer used in plotly
                try:
                    del plot_data["layout"]["template"]["data"]["heatmapgl"]
                except KeyError:
                    print("heatmapgl does not exist in plot data.")
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
        # Get reactive input
        json_file = coverage_sample_file.get()
        # Re-create widget if the json file changes
        with reactive.isolate():
            # If file exists, read in the file
            if os.path.exists(json_file):
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
    async def coverage_sample_sankeyfig():
        # Get reactive inputs
        seq_run = input.seq_run()
        sample_id = input.coverage_sample_id()
        # Re-create widget if the input changes
        with reactive.isolate():
            json_file = f"{data_root}/{seq_run}/dash-json/readsfig_{sample_id}.json"
            # If file exists, read in the file
            if os.path.exists(json_file):
                # Load json as dict
                with open(json_file, 'r') as file:
                    plot_data = json.load(file)
                # Remove heatmapgl from plot data as heatmapgl is deprecated and no longer used in plotly
                try:
                    del plot_data["layout"]["template"]["data"]["heatmapgl"]
                except KeyError:
                    print("heatmapgl does not exist in plot data.")
                # Convert dictionary to Plotly figure
                fig = pio.from_json(pio.to_json(plot_data))
                return fig
            else:
                return

    # Display coverage plot for each sample id
    @output
    @render_widget
    async def coverage_sample_fig():
        # Get reactive inputs
        seq_run = input.seq_run()
        sample_id = input.coverage_sample_id()
        # Re-create widget if the input changes
        with reactive.isolate():
            y_axis_type = "linear"
            json_file = f"{data_root}/{seq_run}/dash-json/coveragefig_{sample_id}_{y_axis_type}.json"
            # If file exists, read in the file
            if os.path.exists(json_file):
                # Load json as dict
                with open(json_file, 'r') as file:
                    plot_data = json.load(file)
                # Remove heatmapgl from plot data as heatmapgl is deprecated and no longer used in plotly
                try:
                    del plot_data["layout"]["template"]["data"]["heatmapgl"]
                except KeyError:
                    print("heatmapgl does not exist in plot data.")
                # Convert dictionary to Plotly figure
                fig = pio.from_json(pio.to_json(plot_data))
                return fig
            else:
                return

    # Output variants table
    @output
    @render_widget
    async def variants_table():
        # Get reactive input
        json_file = mira_variants_file.get()
        # Re-create widget if the json file changes
        with reactive.isolate():
            # Read in the file
            if os.path.exists(json_file):
                await session.send_custom_message(
                    "toggleContent", {"id": "variants-container", "visible": True}
                )
                # Load json as dict
                df = pd.read_json(json_file, orient="split")
                # Display df if not empty
                if not df.empty:
                    seq_run = input.seq_run()
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
                    return ITable(df, classes="display nowrap compact", columnDefs=[{"width":"auto", "targets":"_all"}], style="width:100%;", showIndex=False, allow_html=True, select=True, scrollX=True, scrollY=tbl_height, scrollCollapse=True, paging=False, search=True, buttons=[{"extend": "csvHtml5", "filename": f"{seq_run}_variants_tbl"}, {"extend": "excelHtml5", "filename": f"{seq_run}_variants_tbl"}])
                else:
                    df = pd.DataFrame([{"WARNINGS": "There are no AA Variants found for this sequencing run."}])
                    return ITable(df, columnDefs=[{"targets":"_all", "className":"dt-center"}], showIndex=False, select=False, allow_html=True, style="width:100%;", scrollX=False, scrollY=False, scrollCollapse=False, paging=False, search=False)
            else:
                await session.send_custom_message(
                    "toggleContent", {"id": "variants-container", "visible": False}
                )
                return

    # Output minor alleles table
    @output
    @render_widget
    async def minor_alleles_table():
        # Get reactive input
        json_file = mira_snvs_file.get()
        # Re-create widget if the json file changes
        with reactive.isolate():
            # Read in the file
            if os.path.exists(json_file):
                await session.send_custom_message(
                    "toggleContent", {"id": "snvs-container", "visible": True}
                )
                # Load json as dict
                df = pd.read_json(json_file, orient="split")
                # Display df if not empty
                if not df.empty:
                    seq_run = input.seq_run()
                    # Determine the height of table based on number of rows
                    if df.shape[0] > 5:
                        height = 550
                        tbl_height = str(height - 200) + "px"
                    else:
                        height = 250
                        tbl_height = str(height - 100) + "px"
                    # Update table height
                    tbl_id = session.ns("minor_alleles_table")
                    await session.send_custom_message(
                        "resizeITable", {"tbl_id": tbl_id, "height": height}
                    )
                    # Return table
                    return ITable(df, classes="display nowrap compact", columnDefs=[{"width":"100%", "targets":"_all"}], style="width:100%; height:100%;", showIndex=False, allow_html=True, select=True, scrollX=True, scrollY=tbl_height, scrollCollapse=True, paging=False, search=True, buttons=[{"extend": "csvHtml5", "filename": f"{seq_run}_snvs_tbl"}, {"extend": "excelHtml5", "filename": f"{seq_run}_snvs_tbl"}])
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
        # Get reactive input
        json_file = mira_indels_file.get()
        # Re-create widget if the json file changes
        with reactive.isolate():
            # Read in the file
            if os.path.exists(json_file):
                await session.send_custom_message(
                    "toggleContent", {"id": "indels-container", "visible": True}
                )
                # Load json as dict
                df = pd.read_json(json_file, orient="split")
                # Display df if not empty
                if not df.empty:
                    seq_run = input.seq_run()
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
                    return ITable(df, classes="display nowrap compact", columnDefs=[{"width":"auto", "targets":"_all"}], style="width: 100%; height:100%;", showIndex=False, allow_html=True, select=True, scrollX=False, scrollY=tbl_height, scrollCollapse=True, paging=False, search=True, buttons=[{"extend": "csvHtml5", "filename": f"{seq_run}_indels_tbl"}, {"extend": "excelHtml5", "filename": f"{seq_run}_indels_tbl"}])
                else:
                    df = pd.DataFrame([{"WARNINGS": "There are no <span class='fw-bold text-primary'>Minor Indels and Deletions</span> found for this sequencing run."}])
                    return ITable(df, columnDefs=[{"targets":"_all", "className":"dt-center"}], showIndex=False, select=False, allow_html=True, style="width: 100%;", scrollX=False, scrollY=False, scrollCollapse=False, paging=False, search=False)
            else:
                await session.send_custom_message(
                    "toggleContent", {"id": "indels-container", "visible": False}
                )
                return

    # Check fasta files
    @reactive.effect
    async def check_fasta_files():
        # Get inputs
        passed_nt_fasta = passed_nt_file.get()
        passed_aa_fasta = passed_aa_file.get()
        failed_nt_fasta = failed_nt_file.get()
        failed_aa_fasta = failed_aa_file.get()
        # Check passed fastas
        if not os.path.exists(passed_nt_fasta) and not os.path.exists(passed_aa_fasta):
            await session.send_custom_message(
                "toggleContent", {"id": "download-passed-fasta-container", "visible": False}
            )
        else:
            await session.send_custom_message(
                "toggleContent", {"id": "download-passed-fasta-container", "visible": True}
            )
            if not os.path.exists(passed_nt_fasta):
                # Enable assembly button again
                btn_id = session.ns("download_passed_nt_fasta")
                await session.send_custom_message(
                    "toggleContent", {"id": btn_id, "visible": False}
                )
            if not os.path.exists(passed_aa_fasta):
                btn_id = session.ns("download_passed_aa_fasta")
                await session.send_custom_message(
                    "toggleContent", {"id": btn_id, "visible": False}
                )
        # Check failed fastas
        if not os.path.exists(failed_nt_fasta) and not os.path.exists(failed_aa_fasta) :
            await session.send_custom_message(
                "toggleContent", {"id": "download-failed-fasta-container", "visible": False}
            )
        else:
            await session.send_custom_message(
                "toggleContent", {"id": "download-failed-fasta-container", "visible": True}
            )
            if not os.path.exists(failed_nt_fasta):
                # Enable assembly button again
                btn_id = session.ns("download_failed_nt_fasta")
                await session.send_custom_message(
                    "toggleContent", {"id": btn_id, "visible": False}
                )
            if not os.path.exists(failed_aa_fasta):
                btn_id = session.ns("download_failed_aa_fasta")
                await session.send_custom_message(
                    "toggleContent", {"id": btn_id, "visible": False}
                )

    # Download passed nt fasta
    @render.download
    def download_passed_nt_fasta():
        # Get inputs
        fasta_file = passed_nt_file.get()
        return fasta_file

    # Download passed aa fasta
    @render.download
    def download_passed_aa_fasta():
        # Get inputs
        fasta_file = passed_aa_file.get()
        return fasta_file

    # Download failed nt fasta
    @render.download
    def download_failed_nt_fasta():
        # Get inputs
        fasta_file = failed_nt_file.get()
        return fasta_file

    # Download failed aa fasta
    @render.download
    def download_failed_aa_fasta():
        # Get inputs
        fasta_file = failed_aa_file.get()
        return fasta_file



