--
-- SQLite schema 
--
-- Disable foreign key checks during schema reset
PRAGMA foreign_keys=OFF;
--
-- Table structure for table `submitter`
--
CREATE TABLE IF NOT EXISTS submitter (
  submitter_id              INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
  submitter_name            TEXT NOT NULL,
  submitter_password        TEXT NOT NULL,
  organism                  TEXT NOT NULL 
                            CHECK (organism IN (
                              'FLU', 'COV', 'POX', 
                              'ARBO', 'RSV', 'OTHER'
                            )),
  submission_portal         TEXT NOT NULL
                            CHECK (submission_portal IN (
                              'NCBI', 'GISAID'
                            )),
  ncbi_spuid_namespace      TEXT DEFAULT NULL,
  gisaid_client_id          TEXT DEFAULT NULL,
  ncbi_org_role             TEXT DEFAULT NULL,
  ncbi_org_type             TEXT DEFAULT NULL,
  ncbi_org_name             TEXT DEFAULT NULL,
  ncbi_org_affiliation      TEXT DEFAULT NULL,
  ncbi_org_division         TEXT DEFAULT NULL,
  ncbi_addr_street          TEXT DEFAULT NULL,
  ncbi_addr_city            TEXT DEFAULT NULL,
  ncbi_addr_state           TEXT DEFAULT NULL,
  ncbi_addr_postal_code     TEXT DEFAULT NULL,
  ncbi_addr_country         TEXT DEFAULT NULL,
  ncbi_addr_email           TEXT DEFAULT NULL,
  ncbi_addr_phone           TEXT DEFAULT NULL,
  ncbi_submitter_email      TEXT DEFAULT NULL,
  ncbi_submitter_alt_email  TEXT DEFAULT NULL,
  ncbi_submitter_first_name TEXT DEFAULT NULL,
  ncbi_submitter_last_name  TEXT DEFAULT NULL,
  created_date              TEXT DEFAULT NULL,
  updated_date              TEXT DEFAULT NULL,
  UNIQUE (submitter_name, organism, submission_portal)
);
--
-- Table structure for table `submission`
--
CREATE TABLE IF NOT EXISTS submission (
  submission_id             INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
  submission_name           TEXT NOT NULL,
  organism                  TEXT NOT NULL 
                            CHECK (organism IN (
                              'FLU', 'COV', 'POX', 
                              'ARBO', 'RSV', 'OTHER'
                            )),
  submission_portal         TEXT NOT NULL
                            CHECK (submission_portal IN (
                              'NCBI', 'GISAID'
                            )),
  database                  TEXT NOT NULL 
                            CHECK (database IN (
                              'BIOSAMPLE', 'SRA', 
                              'GENBANK', 'GISAID'
                            )),
  database_status           TEXT NOT NULL DEFAULT 'ACTIVE' 
                            CHECK (database_status IN (
                              'ACTIVE', 'INACTIVE'
                            )),
  submission_type           TEXT NOT NULL DEFAULT 'TEST' 
                            CHECK (submission_type IN (
                              'TEST', 'PRODUCTION'
                            )),  
  gff_file                  BOOLEAN NOT NULL DEFAULT 0 CHECK (gff_file IN (0, 1)),
  table2asn                 BOOLEAN NOT NULL DEFAULT 0 CHECK (table2asn IN (0, 1)),
  submitter_name            TEXT NOT NULL,
  ncbi_publication_title    TEXT DEFAULT NULL,
  ncbi_publication_status   TEXT NOT NULL DEFAULT "Unpublished" 
                            CHECK (ncbi_publication_status IN (
                              'Unpublished', 'In Press', 'Published'
                            )),
  ncbi_release_date         TEXT DEFAULT NULL,
  number_of_samples         INTEGER NOT NULL DEFAULT 0 CHECK (number_of_samples >= 0),
  ncbi_submission_id        TEXT DEFAULT NULL,
  ncbi_submission_status    TEXT DEFAULT NULL
                            CHECK (ncbi_submission_status IN (
                              'SUBMITTED', 'CREATED', 'QUEUED', 'PROCESSING', 
                              'FAILED', 'PROCESSED', 'ERROR', 'WAITING',
                              'DELETED', 'RETRIED', 'VALIDATED', 'EMAILED'
                            )),
  submission_status         TEXT NOT NULL DEFAULT 'CREATED' 
                            CHECK (submission_status IN (
                              'CREATED', 'SUBMITTED', 'PROCESSING', 'FAILED', 'COMPLETED'
                            )),
  comments                  TEXT DEFAULT NULL,
  date_submitted            TEXT DEFAULT NULL,
  date_updated              TEXT DEFAULT NULL,
  UNIQUE (submission_name, organism, database, submission_type),
  FOREIGN KEY (submitter_name, organism, submission_portal) REFERENCES submitter (submitter_name, organism, submission_portal) ON DELETE CASCADE
);

-- One application-managed hourly schedule for refreshing all submission statuses.
CREATE TABLE IF NOT EXISTS status_update_schedule (
  schedule_id       INTEGER PRIMARY KEY CHECK (schedule_id = 1),
  enabled           INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
  frequency         TEXT NOT NULL DEFAULT 'hourly' CHECK (frequency = 'hourly'),
  interval_minutes  INTEGER NOT NULL DEFAULT 60 CHECK (interval_minutes IN (60, 120, 180, 240)),
  created_at        TEXT NOT NULL,
  updated_at        TEXT NOT NULL,
  last_run_at       TEXT DEFAULT NULL,
  last_run_status   TEXT DEFAULT NULL,
  last_run_message  TEXT DEFAULT NULL
);
--
-- Table structure for table `metadata`
--
CREATE TABLE IF NOT EXISTS metadata (
  metadata_id                         INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
  submission_id                       INTEGER NOT NULL REFERENCES submission(submission_id) ON DELETE CASCADE,
  sample_number                       INTEGER NOT NULL CHECK (sample_number > 0),
  submitter_specimen_id               TEXT NOT NULL,
  collection_date                     TEXT DEFAULT NULL,
  specimen_source                     TEXT DEFAULT NULL,
  reason_for_submission               TEXT DEFAULT NULL,
  age                                 TEXT DEFAULT NULL,
  age_units                           TEXT DEFAULT NULL,
  sex                                 TEXT DEFAULT NULL,
  collection_country                  TEXT DEFAULT NULL,
  collection_state                    TEXT DEFAULT NULL,
  collection_county                   TEXT DEFAULT NULL,
  collection_city                     TEXT DEFAULT NULL,
  sars_cov_2                          TEXT DEFAULT NULL,
  influenza_a                         TEXT DEFAULT NULL,
  pdm_influenza_a                     TEXT DEFAULT NULL,
  pdm_h1                              TEXT DEFAULT NULL,
  h3                                  TEXT DEFAULT NULL,
  influenza_b                         TEXT DEFAULT NULL,
  b_vic                               TEXT DEFAULT NULL,
  b_yam                               TEXT DEFAULT NULL,
  influenza_type_subtype_lineage      TEXT DEFAULT NULL,
  passage_history                     TEXT DEFAULT NULL,
  comments                            TEXT DEFAULT NULL,
  fatal                               TEXT DEFAULT NULL,
  institution                         TEXT DEFAULT NULL,
  vaccinated                          TEXT DEFAULT NULL,
  travel_country                      TEXT DEFAULT NULL,
  travel_state                        TEXT DEFAULT NULL,
  travel_county                       TEXT DEFAULT NULL,
  travel_city                         TEXT DEFAULT NULL,
  return_date                         TEXT DEFAULT NULL,
  UNIQUE (submission_id, submitter_specimen_id)
);
--
-- Table structure for table `sender_information`
--
CREATE TABLE IF NOT EXISTS sender_information (
  sender_information_id               INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
  submission_id                       INTEGER NOT NULL REFERENCES submission(submission_id) ON DELETE CASCADE,
  sender_name                         TEXT NOT NULL,
  institution                         TEXT DEFAULT NULL,
  address_1                           TEXT DEFAULT NULL,
  address_2                           TEXT DEFAULT NULL,
  city                                TEXT DEFAULT NULL,
  state                               TEXT DEFAULT NULL,
  zip_code                            TEXT DEFAULT NULL,
  country                             TEXT DEFAULT NULL,
  phone                               TEXT DEFAULT NULL,
  email                               TEXT DEFAULT NULL,
  tracking_number                     TEXT DEFAULT NULL,
  shipment_date                       TEXT DEFAULT NULL,
  comments                            TEXT DEFAULT NULL,
  UNIQUE (submission_id, sender_name)
);
-- Re-enable foreign key checks
PRAGMA foreign_keys=ON;
--