################################################################################
# Script: Prepare data for analysis
################################################################################

# Load libraries
library(tidyverse)

# Load functions
source("utils/utils.R")

# Load data
data_tapmusic_raw <- read_csv("data/tap-data/TapTrialMusic.csv")

table(data_tapmusic_raw$participant_id)

# apply function to convert raw data into data ready for analysis
data_tapmusic <- prepare_trial_data(data_tapmusic_raw) %>% 
  mutate(trial_type = "music", id = paste(id, "music", sep = "_"))

