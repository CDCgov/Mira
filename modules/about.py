# Import shiny packages
from shiny import *

# Import utils app functions
from utils.app_functions import *

# Import utils global variables
from utils.global_var import *

# Create UI layout
@module.ui
def about_ui():
    return ui.row(
        ui.column(3,
            ui.div(
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
                ui.tags.hr(),
                ui.tags.br(),
                ui.tags.h3("About", style="""font-weight: 700;font-family: "Georgia", "Times",  Serif;"""),
                ui.HTML(
                  """
                  <b>MIRA</b> a bioinformatics pipeline that assembles Influenza genomes, 
                  SARS-CoV-2 genomes, the SARS-CoV-2 spike-gene and RSV genomes when given 
                  the raw fastq files and a samplesheet. MIRA can assemble reads from both 
                  Illumina and OxFord Nanopore sequencing machines.
                  """
                ),
                ui.tags.hr(),
                ui.HTML(
                  """
                  <i>Coming soon, MIRA will automate sequence submission to NCBI’s </i><b>Genbank</b>, <b>BioSample</b>, 
                  and <b>SRA</b>, as well as <b>GISAID</b>.
                  """
                ),
                class_="sidebar-description",
            ),
            class_="main-sidebar", id="about-sidebar",
        ),
        ui.column(9,
            ui.HTML("This is the <b>ABOUT</b> tab."),
            class_="main-main", id="about-main",
        ),
        class_="main-layout",
    )

# Define server logic
@module.server
def about_server(input, output, session):
  
    # Access the module's id
    print(f"Session ID: {session.id}")
    
