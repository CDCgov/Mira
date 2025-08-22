
# -*- coding: utf-8 -*-

# Run this app with `python app.py` and
# visit http://127.0.0.1:8050/ in your web browser.

# Import shiny packages
from shiny import *
from shinyswatch import theme

# Import async packages
import asyncio
      
# Import Python packages
import os
from pathlib import Path

# Import local modules
from modules import home, mira, upload, about

# Import utils app functions
from utils.app_functions import *

# Import utils global variables
from utils.global_var import *

# Parse arguments package
import argparse

# Function to launch MIRA app
def mira_app(config):
    
    # Parse config variables
    # config = get_config(config_file=f"{os.path.dirname(os.path.realpath(__file__))}/config/dev-config.yaml")
    data_root = config["DATA_ROOT"]
    debug = True if config["DEBUG"] == True else False
    deploy = True if config["DEPLOY"] == True else False
    
    # Determine whether to run SPYNE using bash or a docker container
    if not os.path.exists(data_root):
        print(f"ERROR: There is NO DATA_ROOT file or directory at '{data_root}'", file=sys.stderr)
        sys.exit(1)
        
    # Determine whether to run SPYNE using bash or a docker container
    if deploy == True:
        spyne_command_type = "bash"
    else:
        spyne_command_type = "docker"
    
    # Define page styling, description, and javascript dependencies
    page_dependencies = ui.tags.head(
        ui.tags.link(rel="stylesheet", type="text/css", href="css/layout.css"),
        ui.tags.link(rel="stylesheet", type="text/css", href="css/style.css"),
    
        ui.tags.script(src="javascript/index.js"),
    
        ui.tags.link(rel="icon", href="favicon.ico"),
    
        ui.tags.meta(name="description", content="MIRA: Influenza, RSV, and SARS-CoV-2 Assembly and Curation"),
        ui.tags.meta(name="theme-color", content="#000000"),
        ui.tags.meta(name="apple-mobile-web-app-status-bar-style", content="#000000"),
        ui.tags.meta(name="apple-mobile-web-app-capable", content="yes"),
        ui.tags.meta(name="viewport", content="width=device-width, initial-scale=1"),
    )
    
    # Define page top header
    page_header = ui.tags.div(
        ui.tags.div(
            ui.tags.a(
                ui.tags.img(
                    src="logo/apple-touch-icon-60x60.png",
                    width="45",
                    height="42"
                ),
                ui.tags.span(
                  "MIRA",
                  class_="logo-title"
                ),
                href="https://github.com/CDCgov/MIRA",
                target="_blank",
                class_="logo-link",
            ),
            class_="navigation-logo", id="navbar-logo",
        ),
        ui.tags.div(
            ui.input_action_button(
                id="tab_home",
                label="HOME",
                class_="navbar-button",
            ),
            ui.input_action_button(
                id="tab_mira",
                label="MIRA",
                class_="navbar-button active",
            ),
            ui.input_action_button(
                id="tab_upload",
                label="UPLOAD",
                class_="navbar-button",
            ),
            ui.input_action_button(
                id="tab_about",
                label="ABOUT",
                class_="navbar-button",
            ),
            class_="navigation-tabs", id="navbar-tabs",
        ),
        ui.tags.div(
            ui.tags.a(
                ui.HTML('<svg xmlns="http://www.w3.org/2000/svg" width="22" height="25" fill="currentcolor" class="bi bi-github" viewBox="0 0 16 16"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27s1.36.09 2 .27c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8"/></svg>'),
                href="https://github.com/CDCgov/MIRA",
                target="_blank",
                class_="navbar-info",
            ),
            ui.input_action_link(
                id="info_icon",
                label=None,
                icon=ui.HTML('<svg xmlns="http://www.w3.org/2000/svg" width="22" height="25" fill="currentColor" class="bi bi-bell" viewBox="0 0 16 16"><path d="M8 16a2 2 0 0 0 2-2H6a2 2 0 0 0 2 2M8 1.918l-.797.161A4 4 0 0 0 4 6c0 .628-.134 2.197-.459 3.742-.16.767-.376 1.566-.663 2.258h10.244c-.287-.692-.502-1.49-.663-2.258C12.134 8.197 12 6.628 12 6a4 4 0 0 0-3.203-3.92zM14.22 12c.223.447.481.801.78 1H1c.299-.199.557-.553.78-1C2.68 10.2 3 6.88 3 6c0-2.42 1.72-4.44 4.005-4.901a1 1 0 1 1 1.99 0A5 5 0 0 1 13 6c0 .88.32 4.2 1.22 6"/></svg>'),
                class_="navbar-info",
            ),
            class_="navigation-info", id="navbar-info",
        ),
        class_="navbar navbar-top page-header bg-dark", id="navbar-container",
    )
    
    # Define HOME UI
    home_ui = ui.tags.div(
        home.home_ui(id="home"),
        id="home-container",
        class_="page-main main-invisible",
    )
    
    # Define MIRA UI
    mira_ui = ui.tags.div(
        mira.mira_ui(id="mira", data_root=data_root),
        id="mira-container",
        class_="page-main main-visible",
    )
    
    # Define UPLOAD UI
    upload_ui = ui.tags.div(
        upload.upload_ui(id="upload"),
        id="upload-container",
        class_="page-main main-invisible",
    )
    
    # Define ABOUT UI
    about_ui = ui.tags.div(
        about.about_ui(id="about"),
        id="about-container",
        class_="page-main main-invisible",
    )
    
    # Define PAGE LAYOUT
    page_layout = ui.tags.div(
        page_header,
        home_ui,
        mira_ui,
        upload_ui,
        about_ui,
        class_="page-layout"
    )
    
    # Define FINAL APP LAYOUT
    app_ui = ui.page_fluid(
        page_dependencies,
        page_layout,
        title=f"MIRA v{get_version()}",
        theme=theme.lux
    )
    
    # Define SERVER LOGIC
    def server(input: Inputs, output: Outputs, session: Session):
    
        # Access the module's id
        print(f"Session Id: {session.id} started.", file=sys.stdout)
        print(f"Session PID: {os.getpid()}", file=sys.stdout)
        
        # Show notifications
        check_deployment_version(config=config)
    
        # Observe when notification icon is clicked
        @reactive.Effect
        @reactive.event(input.info_icon)
        def _():
            show_info_modal()
    
        # Observe when home tab button is clicked
        @reactive.Effect
        @reactive.event(input.tab_home)
        async def _():
            await session.send_custom_message(
                "toggleActiveTab", {"activeTab": "home"}
            )
    
        # Observe when mira tab button is clicked
        @reactive.Effect
        @reactive.event(input.tab_mira)
        async def _():
            await session.send_custom_message(
                "toggleActiveTab", {"activeTab": "mira"}
            )
    
        # Observe when upload tab button is clicked
        @reactive.Effect
        @reactive.event(input.tab_upload)
        async def _():
            await session.send_custom_message(
                "toggleActiveTab", {"activeTab": "upload"}
            )
    
        # Observe when about tab button is clicked
        @reactive.Effect
        @reactive.event(input.tab_about)
        async def _():
            await session.send_custom_message(
                "toggleActiveTab", {"activeTab": "about"}
            )
    
        # Create reative value to store html samplesheet tbl returned from javascript
        samplesheet_html_tbl = reactive.value("")
    
        # Get samplesheet html table from javascript
        @reactive.effect
        @reactive.event(input.samplesheet_html, ignore_none=False, ignore_init=False)
        def _():
            # Handle the value sent from JavaScript
            value = input.samplesheet_html()
            samplesheet_html_tbl.set(value)
    
        # MIRA Server
        mira.mira_server(id="mira", data_root=data_root, samplesheet_html_tbl=samplesheet_html_tbl, spyne_command_type=spyne_command_type)
    
    # Set up location of styling worksheet and static files
    www_dir = Path(__file__).parent / "www"
    
    # Run app with static files
    app = App(app_ui, server, static_assets = www_dir, debug=debug)

    # Return app
    return app

# Main class to launch MIRA
if __name__ == "__main__":

    """
    Argument parser to setup and launch MIRA Dashboard
    """
    parser = argparse.ArgumentParser(description="Launch MIRA Dashboard")
    parser.add_argument("--host",
        help="The address that the app should listen on. Default 127.0.0.1",
    	type=str,
      	default="127.0.0.1")
    parser.add_argument("--port",
        help="The port that the app should listen on. Set to 0 to use a random port. Default 8050",
        type=int,
        default=8050)
    parser.add_argument("--config_file",
        help="Config file for the app",
        type=str,
        required=True)

    # Get arguments
    args = parser.parse_args()

    # Parse config file
    config = get_config(config_file=args.config_file)

    # Get mira app
    app = mira_app(config=config)

    # Run app
    run_app(app, app_dir=".", reload=False, launch_browser=True, host=args.host, port=args.port)
    
    
