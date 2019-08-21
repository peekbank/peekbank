#### Load packages ####
library(here)
library(tidyverse)
library(reader)
library(fs)
library(feather)

#### general parameters ####
dataset_name <- "refword_v1"
dataset_id <- 0
max_lines_search <- 40 #maybe change this value?
subid_name <- "Subject"
monitor_size <- "Calibration Area"
sample_rate <- "Sample Rate"
possible_delims <- c("\t",",")
left_x_col_name <-  "L POR X [px]"
right_x_col_name <-  "R POR X [px]"
left_y_col_name <-  "L POR Y [px]"
right_y_col_name <-  "R POR Y [px]"
stims_to_remove_chars <- c(".avi")
stims_to_keep_chars <- c("_")
trial_file_name <- "reflook_tests.csv"


#Specify file 
file_name <- "Reflook4_2 (2)_052212_2_2133 Samples.txt"

#### define directory ####
#Define root path
project_root <- here::here()
#build directory path
dir_path <- fs::path(project_root,"data","etds_smi_raw","raw_data","full_dataset")
trial_dir_path <- fs::path(project_root,"data","etds_smi_raw","raw_data")

#output path
output_path <- fs::path(project_root,"data","etds_smi_raw","processed_data")


#### generic functions ###


#function for extracting information from SMI header/ comments
extract_smi_info <- function(file_path,parameter_name) {

  info_object <- read_lines(file_path, n_max=max_lines_search) %>%
    str_subset(parameter_name) %>% 
    str_extract(paste("(?<=",parameter_name,":\\t).*",sep="")) %>%
    trimws() %>%
    str_replace("\t", "x")
  
  return(info_object)
}


#### Table 3: Trial Info ####

process_smi_trial_info <- function(file_path) {
  
  #guess delimiter
  sep <- get.delim(file_path, delims=possible_delims)
  
  #read in data
  trial_data <-  
    read_delim(
      file_path,
      delim=sep
    )
  
  #separate stimulus name for individual images (target and distracter)
  trial_data <- trial_data %>%
    mutate(stimulus_name = str_remove(Stimulus,".jpg")) %>%
    separate(stimulus_name, into=c("target_info","left_image","right_image"),sep="_",remove=F)
  
  #convert onset to ms
  trial_data <- trial_data %>%
    mutate(point_of_disambig=onset *1000)
  
  #add target/ distracter info
  trial_data <- trial_data %>%
    mutate(
      target_image = case_when(
        target_info == "o" ~ right_image,
        target_info == "t" ~ left_image
      ),
      distracter_image = case_when(
        target_info == "o" ~ left_image,
        target_info == "t" ~ right_image
      )
    ) %>%
    rename(target_side = target) %>%
    mutate(
      target_label = target_image,
      distracter_label = distracter_image
    )
  
  # rename and create some additional filler columns
  trial_data <- trial_data %>%
    mutate(trial_id=trial-1) %>%
    mutate(
      dataset=dataset_id #choose specific dataset id for now
      )
  
  #full phrase? currently unknown for refword
  trial_data$full_phrase = NA
  
  #extract relevant columns
  #keeping type and Stimulus for now for cross-checking with raw eyetracking
  trial_data <- trial_data %>%
    select(trial_id,dataset,target_image,distracter_image,target_side,target_label,distracter_label,full_phrase,point_of_disambig)
  
  return(trial_data)
  
}


#### Table 4: Dataset ####

process_smi_dataset <- function(file_path,lab_datasetid=dataset_name) {
  
  #read in lines to extract smi info
  monitor_size <- extract_smi_info(file_path,monitor_size)
  sample_rate <- extract_smi_info(file_path,sample_rate)
  
  ##Make dataset table
  dataset.data <- data.frame(
    dataset_id = dataset_id, #hard code data set id for now
    lab_datasetid = lab_datasetid, 
    tracker = "SMI", 
    monitor_size = monitor_size,
    sample_rate = sample_rate
    )
  
  return(dataset.data)
}

#### Table 1A: XY Data ####

process_smi_eyetracking_file <- function(file_path, delim_options = possible_delims,stimulus_coding="stim_column") {
  
  #guess delimiter
  sep <- get.delim(file_path, comment="#", delims=delim_options,skip = max_lines_search)
  
  #read in lines to extract smi info
  lab_subject_id <- extract_smi_info(file_path,subid_name)
  monitor_size <- extract_smi_info(file_path,monitor_size)
  sample_rate <- extract_smi_info(file_path,sample_rate)
  
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
  
  ## add lab_subject_id column (extracted from data file)
  data <- data %>%
    mutate(lab_subject_id=lab_subject_id)
  
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
  
  ##If trials are identified via a Stimulus column, determine trials and redefine time based on trial onsets
  if (stimulus_coding == "stim_column") {
    
    # Redefine trials based on stimuli rather than SMI output
    #check if previous stimulus value is equal to current value; ifelse, trial test increases by 1
    data <- data %>%
      mutate(stim_lag = lag(Stimulus), 
             temp = ifelse(Stimulus != stim_lag, 1, 0), 
             temp_id = cumsum(c(0, temp[!is.na(temp)])), 
             trial_id = temp_id)
    
    #set time to zero at the beginning of each trial
    data <- data %>%
      group_by(trial_id) %>%
      mutate(t = timestamp - min(timestamp)) %>%
      ungroup()
  }
  
  #extract final columns
  xy.data <- data %>%
    dplyr::select(lab_subject_id,x,y,t,trial_id)

  
  return(xy.data)
  
}

process_smi <- function(dir,trial_dir, file_ext = '.txt') {
  
  #list files in directory
  all_files <- list.files(path = dir, 
                          pattern = paste0('*',file_ext),
                          all.files = FALSE)
  
  #create file paths
  all_file_paths <- paste0(dir,"/",all_files,sep="")
  
  #create trial info file path
  trial_file_path <- paste0(trial_dir, "/",trial_file_name)
  
  #create trials data
  trials.data <- process_smi_trial_info(trial_file_path)
  
  #create dataset data
  dataset.data <- process_smi_dataset(all_file_paths[1])
  
  #create xy data
  xy.data <- lapply(all_file_paths,process_smi_eyetracking_file) %>%
    bind_rows() %>%
    mutate(xy_data_id = seq(0,length(lab_subject_id)-1)) %>%
    dplyr::select(xy_data_id,lab_subject_id,x,y,t,trial_id)
    
  
  #write all data
  #write_feather(dataset.data,path=paste0(output_path,"/","dataset_data.feather"))
  #write_feather(xy.data,path=paste0(output_path,"/","xy_data.feather"))
  
  write_csv(dataset.data,path=paste0(output_path,"/","dataset.csv"))
  write_csv(xy.data,path=paste0(output_path,"/","xy_data.csv"))
  write_csv(trials.data,path=paste0(output_path,"/","trials.csv"))
  
  
}



#### Run SMI ####

process_smi(dir=dir_path,trial_dir=trial_dir_path)
