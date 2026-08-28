--
-- SQLite schema 
--
-- Disable foreign key checks during schema reset
PRAGMA foreign_keys=OFF;
--
-- Table structure for table `submission`
--
CREATE TABLE IF NOT EXISTS submission (
  submission_id_pk      INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
  submission_name       TEXT NOT NULL,
  organism              TEXT NOT NULL 
                        CHECK (organism IN (
                          'FLU', 'COV', 'POX', 
                          'ARBO', 'RSV', 'OTHER'
                        )),
  database              TEXT NOT NULL 
                        CHECK (database IN (
                          'BIOSAMPLE', 'SRA', 
                          'GENBANK', 'GISAID'
                        )),
  database_status       TEXT NOT NULL DEFAULT 'ACTIVE' 
                        CHECK (database_status IN (
                          'ACTIVE', 'INACTIVE'
                        )),
  submission_type      TEXT NOT NULL DEFAULT 'TEST' 
                        CHECK (submission_type IN (
                          'TEST', 'PRODUCTION'
                        )),  
  gff_file              BOOLEAN NOT NULL DEFAULT 0 CHECK (gff_file IN (0, 1)),
  table2asn             BOOLEAN NOT NULL DEFAULT 0 CHECK (table2asn IN (0, 1)),
  submission_id         TEXT DEFAULT NULL,
  submission_status     TEXT DEFAULT NULL 
                        CHECK (submission_status IN (
                          'SUBMITTED', 'CREATED', 'QUEUED', 'PROCESSING',
                          'FAILED', 'PROCESSED', 'ERROR', 'WAITING', 
                          'DELETED', 'RETIRED', 'VALIDATED', 'EMAILED'
                        )),    
  submission_date       TEXT NOT NULL DEFAULT (date('now')),
  updated_date          TEXT NOT NULL DEFAULT (date('now')),
  PRIMARY KEY (submission_id_pk),
  UNIQUE (submission_name, organism, database, submission_type)
);
-- Re-enable foreign key checks
PRAGMA foreign_keys=ON;
--