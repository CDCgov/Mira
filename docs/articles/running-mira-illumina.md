# 

## Running MIRA-CLI with Illumina Data

![](images/mira-logo-midjourney_20230526_rmbkgnd.png)

*This documentation assumes you have the four required Docker containers
(**IRMA**, **DAIS-Ribosome**, **spyne**, and **MIRA**) already running.
If not, please start with [getting
started](https://cdcgov.github.io/MIRA/articles/getting-started.md) and
[MIRA
install](https://cdcgov.github.io/MIRA/articles/mira-installation.md)
instructions.*

------------------------------------------------------------------------

## Stage your demultiplexed data

- In your “FLU_SC2_SEQUENCING” folder, make a folder for your run. It is
  very helpful to name your runs with a consistent naming system, such
  as “YEAR-MONTH-DATE-FLOWCELL_ID”, ie. 2022-11-13-ABC1234.

***DO NOT PUT SPACES OR SLASHES IN YOU RUN FOLDER NAMES!***

![](images/mira_run_directory_structure.png)

- Copy the run’s demultiplexed fastqs into the RUN-FOLDER.
  - Create another folder inside your RUN-FOLDER called “fastqs” and
    copy the folder containing demultiplexed fastqs into this newly
    created fastqs folder so that the folder structure is
    FLU_SC2_SEQUENCING/RUN-FOLDER/fastqs/demultiplexed-fastqs/sample-reads.fastq.
    There will be two fastq files per sample.

![](images/mira_run_directory_structure_fastq_illumina.PNG)

  
**This screenshot shows “Ubuntu-18.04” but many users just see “Ubuntu”.
This can vary, particularly if you happen to have multiple Ubuntu
versions installed. If you have multiple Ubunut distributions installed,
move the fastqs to whichever “Ubuntu” contains FLU_SC2_SEQUENCING within
home\>USERNAME\>FLU_SC2_SEQUENCING**

------------------------------------------------------------------------

## Run genome assembly with MIRA

### Start the containers

- Open Docker Desktop and navigate to the `Containers` tab on the left
  sidebar. Assure that the following containers are running or run each
  of them:
  1.  irma
  2.  dais
  3.  spyne
  4.  MIRA

### Open MIRA

- Run MIRA by clicking the blue link “8020:8050”. This will open MIRA
  into your default internet browser. You can “bookmark” this site in
  your browser.

  ![](images/mira_docker_rolleddown.png)

### Select runs, data type, and enter sample information

- Click the `REFRESH RUN LISTING` button and select your run from the
  dropdown box.

  ![](images/mira_run_selection.png)

  - Next, click the box that say “What kind of data is this” and select
    Flu-Illumina or SC2-Whole-Genome-Illumina

  ![](images/mira_whatkindofdata.png)

- If you select SC2-Whole-Genome-Illumina, a new box will appear for you
  to select your primer schema/amplicon approach

  - *NOTE: MIRA Whole Genome Illumina module’s primer trimming has been
    tested and optimized for xGen primer panel. We cannot guarantee
    perfect trimming for other panels.*

  ![](images/mira_whatkindofdata_illumina.PNG)

- Next, click `DOWNLOAD SAMPLESHEET TEMPLATE` and open the resulting
  Excel spreadsheet

  ![](images/mira_samplesheet_barcode_entry.png)

- Your samplenames will be inferred from the fastq filenames in your
  fastq directory. **Do not change these sample names**

  - If you do not see a sample that you expect, this is because that
    sample name does not have a fastq to process.
  - Sample names should only be numbers, letters, dashes, and
    underscores (“-” or “\_“). **Do not use any other characters such as
    “/”.**

- Next, select your `Sample Type`. Most of your sample’s are test
  samples, so each row defaults to `test`, but select `- control` or
  `+ control` for your **negative** and **positive** controls
  respectively.

- Save your samplesheet with changes in Excel

- Back in MIRA, Click the “Drag and Drop your Samplesheet” to select
  your filled-in samplesheet.

  - A table in the application should now appear with your samples!

  ![](images/mira_dash_table_illumina.PNG)

### Start Genome Assembly

- Now select `UNLOCK ASSEMBLY BUTTON` and click `START GENOME ASSEMBLY`.
  Now is a good time to go have a coffee.
  - *ESPECIALLY for Whole-Genome SARS-CoV-2: covering a 30kb genome with
    up to 200,000 short reads can take a very long time to process.*

  - Click on the toggle button `Watch IRMA Progress`. Assembly will take
    some time, how long exactly is dependent on your sample number, the
    number of raw sequencing reads, and the power of your computer.
    ![](images/mira_run_status.png)

7.  When IRMA has finished, it will say “IRMA is finished” and you can
    now click on “DISPLAY IRMA RESULTS”.

    ![](images/mira_display_results.png)

------------------------------------------------------------------------

## Review IRMA results

1.  Review the distribution of reads assigned to each barcode. The ideal
    result would be a similar number of reads assigned to each test and
    positive control. However, it is ok to not have similar read numbers
    per sample. Samples with a low proportion of reads may indicate
    higher Ct of starting material or less performant PCR during library
    preparation. What is most important for sequencing assembly is raw
    count of reads and their quality.

    ![](images/mira_barcode_distribution.png)

2.  Review the “Automatic Quality Control Decisions” heatmap. In
    addition to IRMA’s built in quality control, MIRA requires a minimum
    median coverage of 100x, a minimum coverage of the reference length
    of 90%, and less than 10 minor variants \>=5%. These are marked in
    yellow to orange according to the number of these failure types.
    Samples that failed to generate any assembly are marked in red. In
    addition, premature stop codons are flagged in yellow. CDC does not
    submit sequences with premature stop codons, particularly in HA, NA
    or SARS-CoV-2 Spike. Outside of those genes, premature stop codons
    near the end of the gene may be ok for submission. Hover your mouse
    over the figure to see individual results.

    |  |  |
    |----|----|
    | ![Light yellow](images/mira_auto_qc_heatmap_paleyellow.png) | ![Yellow](images/mira_auto_qc_heatmap_yellow.png) |
    | ![Orange](images/mira_auto_qc_heatmap_orange.png) | ![Red](images/mira_auto_qc_heatmap_red.png) |
    | – | – |

3.  Review `Irma Summary`. This summarizes the above information, as
    well as detailed read assignment to specific referencs, in a table.
    Columns can be sorted and filtered, ie. `>1000`. Click `Export` to
    save this as an Excel file.

    ![](images/mira_irma_summary.png)

4.  Review genome coverage depth. The heatmap summarizes the mean
    coverage per sample per gene. All the images in MIRA can be
    interacted with. Click the gray buttons on the top right of the
    images. The camera icon will save the image. Clicking on a sample in
    the heatmap, or selecting one in the drop down menu will display two
    plots. On the left is a “sankey plot” that shows the number of reads
    assigned to the barcode, how many of those passed IRMA’s QC, and how
    many are assigned to each gene reference. The plot on the right
    shows the sample’s complete coverage per gene. Try toggling the
    `log y --- linear y` button. In log space, you likely need to reset
    the view by clicking the gray button in the top right that looks
    like an X inside of a box. You can also try panning and zooming the
    plot.

    ![](images/mira_coverage_heatmap.png)![](images/mira_coverage.png)![](images/mira_coverage_zooming.png)![](images/mira_coverage_zoomed.png)

5.  Inspect amino acid variants against popular reference sequences.

    ![](images/mira_aa_vars.png)

Here, you may see some mutations that do not match Amino Acid letters.

### Special translated characters

Translation produces standard amino acid codes with the two non-standard
exceptions (. and ~) listed below. The translation engine stops when it
encounters a stop codon, but corrects itself to continue in-frame when a
frameshift is encountered.

| Character | Interpretation                  |
|-----------|---------------------------------|
| .         | Missing alignment data          |
| \-        | Gap in alignment (ex: deletion) |
| ~         | Partial codon (ex: frameshift)  |
| X         | Ambiguous codon translation     |

  

6.  Inspect minor variation at single nucleotides, insertions and
    deletions *relative to the sample’s generated consensus sequence.*
    These tables are for your own usage and not necessary to review in
    detail. They can be sorted and filtered and exported to excel sheets
    for further analyses.

    ![](images/mira_minor_vars.png)

    - Minor variants greater than 5% frequency are shown
    - Indels greater than 20% frequency are shown

------------------------------------------------------------------------

## Save your sequences in a fasta file

- Export IRMA’s *amended consensus* nucleotide sequences and amino acid
  fasta files. This includes only those passing MIRA’s QC criteria and
  are ready for submission to public databases!

  ![](images/mira_fasta_dl.png)

  - The `DOWNLOAD FASTAS` button will only return passing samples. To
    investigate failed sequences, click the `DOWNLOAD FAILED FASTAS`
    button. Do not submit failed samples to public repositories!

  - You can open and view these Amino Acid and Nucleotide fastas in any
    sequence viewing application ![](images/mira_fastas.png)

------------------------------------------------------------------------

------------------------------------------------------------------------

### Wow! You are doing such great work. Time to share your sequences with the world by uploading to GISAID and/or NCBI and to start analyzing your own data!

- GISAID: <https://gisaid.org/>
- NCBI-Genbank: <https://www.ncbi.nlm.nih.gov/genbank/>
- NCBI-BLAST: <https://blast.ncbi.nlm.nih.gov/Blast.cgi>
- Nextclade: <https://clades.nextstrain.org/>
