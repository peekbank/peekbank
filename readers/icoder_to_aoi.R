library(janitor); library(tidyverse)

remove_repeat_headers <- function(d, idx_var) {
  d[d[,idx_var] != idx_var,]
}

sampling_rate <- 33

# read raw icoder files (is it one file per participant or aggregated?)
d_raw_path <- "sample_data/datawiz_icoder_preprocessed/pomper_saffran_2016_raw_datawiz.txt"
d_raw <- readr::read_delim(d_raw_path, delim = "\t")

# remove any column with all NAs (these are columns where there were variable names but no eye tracking data)
d_filtered <- d_raw %>% select_if(~sum(!is.na(.)) > 0)

# Create clean column headers --------------------------------------------------
d_processed <-  d_filtered %>% 
  remove_repeat_headers(idx_var = "Months") %>% 
  janitor::clean_names() 

# Relabel time bins --------------------------------------------------
old_names <- colnames(d_processed)
metadata_names <- old_names[!str_detect(old_names,"x\\d|f\\d")]
pre_dis_names <- old_names[str_detect(old_names, "x\\d")]
post_dis_names  <- old_names[str_detect(old_names, "f\\d")]

pre_dis_names_clean <- seq(from = length(pre_dis_names) * sampling_rate,  
                           to = sampling_rate,
                           by = -sampling_rate) * -1

post_dis_names_clean <-  post_dis_names %>% str_remove("f")

colnames(d_processed) <- c(metadata_names, pre_dis_names_clean, post_dis_names_clean)

# Convert to long format --------------------------------------------------

# TODO: test that this returns the expected number of rows

# get idx of first time series
first_t_idx <- length(metadata_names) + 1             # this returns a numeric
last_t_idx <- colnames(d_processed) %>% dplyr::last() # this returns a string 
d_tidy <- d_processed %>% tidyr::gather(t, aoi, first_t_idx:last_t_idx) # but gather() still works

# recode 0, 1, ., - as distracter, target, other, NA [check in about this]
# this leaves NA as NA 
d_tidy_final <- d_tidy %>% 
  mutate(aoi_new = case_when(
    aoi == "0" ~ "distractor",
    aoi == "1" ~ "target",
    aoi == "0.5" ~ "center",
    aoi == "." ~ "other",
    aoi == "-" ~ "other"
  ))

# write AOI table

write()

# write Participants table

# write Trials table

# write Dataset table

