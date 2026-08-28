--
-- SQLite schema 
--
-- Disable foreign key checks during schema reset
PRAGMA foreign_keys=OFF;
--
--
-- Table structure for table `assembly`
--
CREATE TABLE IF NOT EXISTS assembly (
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
CREATE TABLE IF NOT EXISTS illumina_samplesheet (
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
CREATE TABLE IF NOT EXISTS ont_samplesheet (
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
