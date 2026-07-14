# 

Assembled genomes undergo two kinds of quality control. First, at the
IRMA level, reads are filtered according to length and median quality.
During the many rounds of reference editing and refinement, indels and
variants must meet additional thresholds to be incorporated. When
consensus is called, base frequency, quality, and depth are considered
before finalizing the sequence.

Second, consensus sequences undergo additional genome-level QC to ensure
completeness and suitable confidence.

## IRMA QC

### Nanopore QC thresholds

#### Flu

- Read length \>= 150
- Insertion frequency \>= 75%
- Deletion frequency \>= 75%
- Minimum coverage to call base \>= 50X depth
- Average base quality to call \>= 10
- Mixed [IUPAC](https://www.bioinformatics.org/sms/iupac.html) base when
  Minor Allele Frequency \>= 20%

#### Spike SARS-CoV-2

- Read length \>= 125
- Insertion frequency \>= 50%
- Minimum insertion coverage to call base \>= 15X depth
- Deletion frequency \>= 50%
- Minimum deletion coverage to call deletion \>= 10X depth
- Minimum coverage to call base \>= 50X depth
- Average base quality to call \>= 10
- Mixed [IUPAC](https://www.bioinformatics.org/sms/iupac.html) base when
  Minor Allele Frequency \>= 20%

#### Whole Genome SARS-CoV-2

- Read length \>= 125
- Insertion frequency \>= 50%
- Minimum insertion coverage to call base \>= 15X depth
- Deletion frequency \>= 75%
- Minimum deletion coverage to call deletion \>= 10X depth
- Minimum coverage to call base \>= 50X depth
- Average base quality to call \>= 10
- Mixed [IUPAC](https://www.bioinformatics.org/sms/iupac.html) base when
  Minor Allele Frequency \>= 20%

#### RSV

- Read length \>= 125
- Insertion frequency \>= 50%
- Minimum insertion coverage to call base \>= 20X depth
- Deletion frequency \>= 75%
- Minimum coverage to call base \>= 20X depth
- Average base quality to call \>= 10
- Mixed [IUPAC](https://www.bioinformatics.org/sms/iupac.html) base when
  Minor Allele Frequency \>= 20%

### Illumina QC thresholds

#### Flu

- Read length \>= 125 for 2x150 chemistry, \>= 70 for 2x75 chemistry
- Read median quality score \>= 30
- Insertion frequency \>= 25%
- Deletion frequency \>= 60%
- Minimum coverage to call base \>= 30X depth
- Mixed [IUPAC](https://www.bioinformatics.org/sms/iupac.html) base when
  Minor Allele Frequency \>= 20%

#### Whole Genome SARS-CoV-2

- Read length \>= 80 for 2x150 chemistry, \>=50 for 2x75 chemistry
- Read median quality score \>= 27
- Insertion frequency \>= 55%
- Minimum insertion coverage to call base \>= 15X depth (30X paired)
- Deletion frequency \>= 55%
- Minimum deletion coverage to call deletion \>= 10X depth (30X paired)
- Minimum depth to call base \>= 30X depth
- Average base quality to call \>= 15
- Mixed [IUPAC](https://www.bioinformatics.org/sms/iupac.html) base when
  Minor Allele Frequency \>= 20%

## Post-Assembly QC Curation

- Minimum median coverage of 50x for ONT, 100x for Illumina
- For SARS-CoV-2 ONT: Spike gene median coverage of 100X
- Minimum coverage of the reference length of 90%
- For SARS-CoV-2 modules: Spike gene minimum coverage length of 90%
- Less than 10 minor variants \>=5% for each Flu Segment
- Less than 20 minor variants \>=5% for SARS-CoV-2 whole-genome and ONT
  RSV
- Less than 50 variants \>=5% for Illumina RSV
- No premature stop codons in Spike (SC2), HA (Flu), NA (Flu), G (RSV),
  or F (RSV)
