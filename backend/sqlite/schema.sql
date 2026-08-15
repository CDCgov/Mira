--
-- SQLite schema 
--

-- Disable foreign key checks during schema reset
PRAGMA foreign_keys=OFF;
--

--
-- Table structure for table `submission`
--
DROP TABLE IF EXISTS submission;
CREATE TABLE submission (
  submission_id_pk     INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
  submission_name      TEXT NOT NULL,
  organism             TEXT NOT NULL 
                        CHECK (organism IN (
                          'FLU', 'COV', 'POX', 
                          'ARBO', 'RSV', 'OTHER'
                        )),
  db                   TEXT NOT NULL 
                        CHECK (db IN (
                          'BIOSAMPLE', 'SRA', 'GENBANK-TBL2ASN', 
                          'GENBANK-FTP', 'GISAID'
                        )),
  submission_type      TEXT NOT NULL DEFAULT 'TEST' 
                          CHECK (submission_type IN (
                            'TEST', 'PRODUCTION'
                          )),
  submission_id         TEXT DEFAULT NULL,
  submission_status     TEXT DEFAULT NULL 
                          CHECK (submission_status IN (
                            'SUBMITTED', 'CREATED', 'QUEUED', 'PROCESSING',
                            'FAILED', 'PROCESSED', 'ERROR', 'WAITING', 
                            'DELETED', 'RETIRED', 'VALIDATED', 'EMAILED'
                          )),    
  submission_date       TEXT NOT NULL DEFAULT (date('now')),
  updated_date          TEXT NOT NULL DEFAULT (date('now')),
  UNIQUE (submission_name, organism, db, submission_type)
);
--
-- Table structure for table `bs_submission_status`
--
DROP TABLE IF EXISTS bs_submission_status;
CREATE TABLE bs_submission_status(
  submission_id_pk                      INTEGER NOT NULL REFERENCES submission(submission_id_pk) ON DELETE CASCADE,
  bs_sample_name                        TEXT DEFAULT NULL,
  biosample_status                      TEXT DEFAULT NULL,
  biosample_accession                   TEXT DEFAULT NULL,
  biosample_message                     TEXT DEFAULT NULL,
  UNIQUE(submission_id_pk, bs_sample_name)
);
--
-- Table structure for table `sra_submission_status`
--
DROP TABLE IF EXISTS sra_submission_status;
CREATE TABLE sra_submission_status(
  submission_id_pk                      INTEGER NOT NULL REFERENCES submission(submission_id_pk) ON DELETE CASCADE,
  sra_sample_name                       TEXT NOT NULL,
  sra_status                            TEXT DEFAULT NULL,
  sra_accession                         TEXT DEFAULT NULL,
  sra_message                           TEXT DEFAULT NULL,
  UNIQUE(submission_id_pk, sra_sample_name)
);
--
-- Table structure for table `gb_submission_status`
--
DROP TABLE IF EXISTS gb_submission_status;
CREATE TABLE gb_submission_status(
  submission_id_pk                      INTEGER NOT NULL REFERENCES submission(submission_id_pk) ON DELETE CASCADE,
  gb_sample_name                        TEXT NOT NULL,
  genbank_status                        TEXT DEFAULT NULL,
  genbank_accession                     TEXT DEFAULT NULL,
  genbank_message                       TEXT DEFAULT NULL,
  UNIQUE(submission_id_pk, gb_sample_name)
);
--
-- Table structure for table `gs_submission_status`
--
DROP TABLE IF EXISTS gs_submission_status;
CREATE TABLE gs_submission_status(  
  submission_id_pk                      INTEGER NOT NULL REFERENCES submission(submission_id_pk) ON DELETE CASCADE,
  gs_sample_name                        TEXT NOT NULL,
  gs_segment_name                       TEXT NOT NULL,
  gisaid_accession_epi_isl_id           TEXT DEFAULT NULL,
  gisaid_segment_accession_epi_isl_id   TEXT DEFAULT NULL,
  gisaid_message                        TEXT DEFAULT NULL,
  UNIQUE(submission_id_pk, gs_sample_name, gs_segment_name)
);

--
-- Table structure for table `assembly`
--
DROP TABLE IF EXISTS assembly;
CREATE TABLE assembly (
  assembly_id             INTEGER PRIMARY KEY AUTOINCREMENT,
  run_name                TEXT NOT NULL,
  alias_name              TEXT DEFAULT NULL,
  experiment_type         TEXT NOT NULL
                            CHECK (experiment_type IN (
                              'Flu-ONT',
                              'Flu-Illumina',
                              'SC2-Spike-Only-ONT',
                              'SC2-Whole-Genome-ONT',
                              'SC2-Whole-Genome-Illumina',
                              'RSV-Illumina',
                              'RSV-ONT'
                            )),
  sc2_primer              TEXT DEFAULT NULL
                            CHECK (sc2_primer IN (
                              'articv3',
                              'articv4',
                              'articv4.1',
                              'articv5.3.2',
                              'qiagen',
                              'swift',
                              'swift_211206'
                            )),
  rsv_primer              TEXT DEFAULT NULL
                            CHECK (rsv_primer IN (
                            'RSV_CDC_8amplicon_230901'
                          )),
  subsample_reads         INTEGER NOT NULL DEFAULT 0 CHECK (subsample_reads >= 0),
  custom_primers          BOOLEAN NOT NULL DEFAULT 0 CHECK (custom_primers IN (0, 1)),
  primer_kmer_len         INTEGER DEFAULT NULL CHECK (primer_kmer_len > 0),
  primer_restrict_window  INTEGER DEFAULT NULL CHECK (primer_restrict_window > 0),
  irma_module             TEXT DEFAULT NULL 
                              CHECK (irma_module IN (
                              'sensitive', 'secondary', 'utr'
                            )),
  custom_irma_config      BOOLEAN NOT NULL DEFAULT 0 CHECK (custom_irma_config IN (0, 1)),
  custom_qc_settings      BOOLEAN NOT NULL DEFAULT 0 CHECK (custom_qc_settings IN (0, 1)),
  parquet_files           BOOLEAN NOT NULL DEFAULT 0 CHECK (parquet_files IN (0, 1)),
  nextclade               BOOLEAN NOT NULL DEFAULT 1 CHECK (nextclade IN (0, 1)),  
  assembly_status         TEXT NOT NULL DEFAULT 'SUBMITTED' 
                            CHECK (assembly_status IN (
                              'SUBMITTED', 'PROCESSING', 'CANCELED',
                              'FAILED', 'COMPLETED'
                            )),
  created_at              TEXT DEFAULT CURRENT_TIMESTAMP,
  finished_at             TEXT DEFAULT NULL,
  runtime                 TEXT DEFAULT NULL,
  UNIQUE (run_name, experiment_type)
);

--
-- Table structure for table `illumina_samplesheet`
--
DROP TABLE IF EXISTS illumina_samplesheet;
CREATE TABLE illumina_samplesheet (
  assembly_id   INTEGER NOT NULL REFERENCES assembly(assembly_id) ON DELETE CASCADE,
  sample_id     TEXT NOT NULL,
  sample_type   TEXT NOT NULL CHECK (sample_type IN ('- Control', '+ Control', 'Test')),
  single_end    BOOLEAN NOT NULL DEFAULT 0 CHECK (single_end IN (0, 1)),
  fastq_1       TEXT NOT NULL,
  fastq_2       TEXT NOT NULL,
  status        TEXT NOT NULL CHECK (status IN ('Keep', 'Exclude')),
  UNIQUE (assembly_id, sample_id, sample_type, fastq_1, fastq_2)
);

--
-- Table structure for table `ont_samplesheet`
--
DROP TABLE IF EXISTS ont_samplesheet;
CREATE TABLE ont_samplesheet (
  assembly_id   INTEGER NOT NULL REFERENCES assembly(assembly_id) ON DELETE CASCADE,
  barcode       TEXT NOT NULL,
  sample_id     TEXT NOT NULL,
  sample_type   TEXT NOT NULL CHECK (sample_type IN ('- Control', '+ Control', 'Test')),
  single_end    BOOLEAN NOT NULL DEFAULT 1 CHECK (single_end IN (0, 1)),
  fastq         TEXT NOT NULL,
  status        TEXT NOT NULL CHECK (status IN ('Keep', 'Exclude')),
  UNIQUE (assembly_id, barcode, sample_id, sample_type, fastq)
);

-- Re-enable foreign key checks
PRAGMA foreign_keys=ON;
--
