
###########################    Description    ##################################
# Global values for MIRA APP
################################################################################

# Options for assembly
seq_organisms = {"FLU": "FLU", 
                 "RSV": "RSV", 
                 "SC2-Whole-Genome": "SC2-Whole-Genome", 
                 "SC2-Spike-Only": "SC2-Spike-Only"}
                 
seq_experiment_types = {"Illumina": "Illumina", "ONT": "ONT"}

sc2_amplicon_libraries = {"": "None",
                          "articv3": "Artic V3", 
                          "articv4": "Artic V4", 
                          "articv4.1": "Artic V4.1", 
                          "articv5.3.2": "Artic V5.3.2", 
                          "qiagen": "Qiagen QIAseq", 
                          "swift": "xGen™ SARS-CoV-2 Amplicon Panel", 
                          "swift_211206": "xGen™ SARS-CoV-2 Amplicon Panel (CDC customized)", 
                          "varSkip": "VarSkip"}
                          
rsv_amplicon_libraries = {"RSV_CDC_8amplicon_230901": "RSV CDC 8 amplicon 230901", 
                          "dong_et_al": "Dong et al. 230312", 
                          "davina_nunez_wgs": "Davina-Nunez et al. - WG pools"}

# Options for sample types in samplesheet                          
sample_type_options = ["- Control", "+ Control", "Test"]
                          
# Define samplesheet column names for ONT
ont_ss_colnames = ["Barcode #", "Sample ID", "Sample Type"]

# Define samplesheet column names for ILLUMINA
illumina_ss_colnames = ["Sample ID", "Sample Type"]

