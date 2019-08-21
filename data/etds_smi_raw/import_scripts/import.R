## Load packages
library(here)
library(reader)
library(tidyverse)

#general parameters
max_lines_subj_search <- 40 #maybe change this value?
subid_name <- "Subject"
monitor_size <- "Calibration Area"
sample_rate <- "Sample Rate"
left_x_col_name = "L POR X [px]"
right_x_col_name = "R POR X [px]"
left_y_col_name = "L POR Y [px]"
right_y_col_name = "R POR Y [px]"
stims_to_remove_chars=c(".avi")
stims_to_keep_chars=c("_")

#Specify file 
file_name <- "Reflook4_2 (2)_052212_2_2133 Samples.txt"

#Define root path
project_root <- here::here()
#build file path
file_path <- fs::path(project_root,"data","etds_smi_raw","raw_data",file_name)

#guess delimiter
sep <- get.delim(file_path, comment="#", delims=c("\t",","),skip = max_lines_subj_search)

#read in lines to extract subject
sub_id <- read_lines(file_path, n_max=max_lines_subj_search) %>%
  str_subset(subid_name) %>% 
  str_extract(paste("(?<=",subid_name,":\\t).*",sep="")) %>%
  trimws()

monitor_size <- read_lines(file_path, n_max=max_lines_subj_search) %>%
  str_subset(monitor_size) %>% 
  str_extract(paste("(?<=",monitor_size,":\\t).*",sep="")) %>%
  trimws() %>%
  str_replace("\t", "x")

sample_rate <- read_lines(file_path, n_max=max_lines_subj_search) %>%
  str_subset(sample_rate) %>% 
  str_extract(paste("(?<=",sample_rate,":\\t).*",sep="")) %>%
  trimws()

#get maximum x-y coordinates on screen
screen_xy <- str_split(monitor_size,"x") %>%
  unlist()
x.max <- as.numeric(as.character(screen_xy[1]))
y.max <- as.numeric(as.character(screen_xy[2]))

#read in data
data <-  
  read_delim(
    file_path,
    comment="##",
    delim=sep
  )

#select rows and column names for xy file
data <-  data %>%
  filter(Type=="SMP", #remove anything that isn't actually collecting ET data
         Stimulus != "-", #remove calibration
         !grepl(paste(stims_to_remove_chars,collapse="|"), Stimulus),  #remove anything that isn't actually a trial; .avis are training or attention getters
         grepl(paste(stims_to_keep_chars,collapse="|"), Stimulus)) %>% #from here, keep only trials, which have format o_name1_name2_.jpg;
  dplyr::select(
    raw_t = "Time",
    lx = left_x_col_name,
    rx = right_x_col_name,
    ly = left_y_col_name,
    ry = right_y_col_name,
    trial_id = "Trial",
    Stimulus = Stimulus
)

## add sub_id column (extracted from data file)
data <- data %>%
  mutate(sub_id=sub_id)

#Remove out of range looks
data <- 
  data %>% 
  mutate(
    rx = if_else(rx <= 0 | rx >= x.max, NA_real_, rx),
    lx = if_else(lx <= 0 | lx >= x.max, NA_real_, lx),
    ry = if_else(ry <= 0 | ry >= y.max, NA_real_, ry),
    ly = if_else(ly <= 0 | ly >= y.max, NA_real_, ly)
  )


## Average left-right x-y coordinates
#Take one eye's measurements if we only have one; otherwise average them
data <-
    data %>%
    mutate(
      x = case_when(
        is.na(rx) & !is.na(lx) ~ lx,
        !is.na(rx) & is.na(lx) ~ rx,
        !is.na(rx) & !is.na(lx) ~ (rx + lx) / 2,
        is.na(rx) & is.na(lx) ~ NA_real_
      ),
      y = case_when(
        is.na(ry) & !is.na(ly) ~ ly,
        !is.na(ry) & is.na(ly) ~ ry,
        !is.na(ry) & !is.na(ly) ~ (ry + ly) / 2,
        is.na(ry) & is.na(ly) ~ NA_real_
      )
    ) %>%
     dplyr::select(
       -rx, -ry, -lx, -ly
     )

## Convert time into ms starting from 0
data <- data %>% 
  mutate(
    timestamp = round((data$raw_t - data$raw_t[1])/1000, 3)
    )

# Redefine coordinate origin (0,0)
# SMI starts from top left
# Here we convert the origin of the x,y coordinate to be bottom left (by "reversing" y-coordinate origin)
data <- data %>%
  mutate(
    y = y.max - y
  )

# Redefine trials based on stimuli rather than SMI output
#check if previous stimulus value is equal to current value; ifelse, trial test increases by 1
data <- data %>%
  mutate(stim_lag = lag(Stimulus), 
         temp = ifelse(Stimulus != stim_lag, 1, 0), 
         temp_id = cumsum(c(0, temp[!is.na(temp)])), 
         trial_id = 1+temp_id)

#set time to zero at the beginning of each trial
data <- data %>%
  group_by(trial_id) %>%
  mutate(t = timestamp - min(timestamp))

         
#extract final columns
data <- data %>%
  dplyr::select(sub_id,x,y,t,trial_id, Stimulus)

#Write data for x y coordinates
write_csv(data,path=fs::path(project_root,"data","etds_smi_raw","processed_data","xy_data.csv"))

##Make dataset table
dataset.data <- data.frame(id = "refword_v1", 
                           tracker = "SMI", 
                           monitor_size = monitor_size, 
                           sample_rate = sample_rate)
write_csv(dataset.data,path=fs::path(project_root,"data","etds_smi_raw","processed_data","dataset_data.csv"))
