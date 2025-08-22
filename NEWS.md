
# MIRA 2.0.0

* Github Repo: https://github.com/CDCgov/MIRA
* Documentation: https://cdcgov.github.io/MIRA

### v2.0.0
- Single container distribution (previously 4 docker images)
- RSV Illumina module
- RSV Nanopore module
- Alternative Command-line interface running of MIRA
- Associated .html result files generated from command-line pipeline
- Documentation overhaul


# MIRA 1.0.0

### v1.1.4
- Empty Illumina fastq error-handling
- Illumina fastq reads less than 70 bases error-handling

### v1.1.3
- MIRA version displayed in app and in IRMA summary table (along with config)
- IRMA version bump 1.1.4
- fixed pulp version
- Turn off padding for S gene module
- Packaged fastq in irma .tar.gz
- Error fixes for single-sample runs

### v1.1.2
- Whole-Genome SC2 Nanopore module
- Illumina 2x75 support for Flu and SC2 whole-genome modules
- Java instability fixed
- New Version Checking
- Lab protocols published on documentation website
- Docker compose steps added to quickstart on documentation website
- Quality control checks for S-gene specific metrics added to Whole-Genome SC2 modules
- IRMA container V1.1.1
- [Final sorted, amended .bams](https://wonder.cdc.gov/amd/flu/irma/output.html) included in tarball. This is in addition to the F1 .bam, which is the first iteration of alignment before reference editing.
  
#### v1.1.1
- Pandas version --> 1.1.0
- Mac docs updated to show Rosetta usage in Docker Desktop
- More thorough error and status messaging during assembly

#### v1.1.0
- Illumina sequencing for WGS SC2 and Flu
- Auto-samplesheet building
- Samplesheet download/upload functionality
- Button added to refresh run listing
- Button added to download failed fastas
- Downloaded fasta for FLU now changes the flu segment numbers to the gene name
- Allow numeric samplenames, and allow "-" in sample names
- Toss broken reads for ONT fastqs
- Return only closer Flu B reference in amino acid variants table
- Better error handling for empty/failed nanopore barcodes
- Indel table filtered to >20%, Minor variant table filtered to >5%
- Archive previous run logs in the even of a re-run

