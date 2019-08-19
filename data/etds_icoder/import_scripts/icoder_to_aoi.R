library(janitor); library(tidyverse)

remove_repeat_headers <- function(d, idx_var) {
  d[d[,idx_var] != idx_var,]
}
sampling_rate <- 33
read_path <- "data/icoder/raw_data"
write_path <- "data/icoder/processed_data"

# read raw icoder files (is it one file per participant or aggregated?)
d_raw <- readr::read_delim(file.path(read_path, "pomper_saffran_2016_raw_datawiz.txt"), 
                           delim = "\t")

# remove any column with all NAs (these are columns 
# where there were variable names but no eye tracking data)
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
d_tidy <- d_tidy %>% 
  mutate(aoi_new = case_when(
    aoi == "0" ~ "distractor",
    aoi == "1" ~ "target",
    aoi == "0.5" ~ "center",
    aoi == "." ~ "other",
    aoi == "-" ~ "other"
  ))

# code distracter image
d_tidy <- d_tidy %>% 
  mutate(distractor_image = ifelse(target_side == "r", 
                                   l_image, 
                                   r_image))

# create dataset variables
d_tidy <- d_tidy %>% 
  mutate(dataset = "icoder",
         tracker = "video_camera", 
         monitor = NA,
         monitor_sr = NA,
         sampling_rate = sampling_rate)

# rename variables to match schema 
#  TODO: think more about what crit_on_set
d_tidy_final <- d_tidy %>% 
  rename(trial_id = tr_num,
         age = months,
         point_of_disambiguation = crit_on_set)

#  write AOI table
d_tidy_final %>% 
  select(sub_num, t, aoi, trial_id) %>% 
  write_csv(file.path(write_path, "aoi_data.csv"))

# write Participants table
d_tidy_final %>% 
  select(sub_num, age, sex) %>% 
  write_csv(file.path(write_path, "participants.csv"))

# write Trials table
#  TODO: what is dataset? what is label? what about condition labels? what about prescreening?
d_tidy_final %>% 
  select(trial_id, dataset, order, condition, target_image, 
         distractor_image, target_side) %>% 
  write_csv(file.path(write_path, "trials.csv"))

# write Dataset table
d_tidy_final %>% 
  select(dataset, tracker, monitor_sr, sampling_rate) %>% 
  write_csv(file.path(write_path, "dataset.csv"))

# don't need to write aoi_coordinates.csv because they don't exist