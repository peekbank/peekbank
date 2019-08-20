## Load packages
library(here)
library(tidyverse)
library(reader)

#general parameters
max_lines_subj_search <- 40 #maybe change this value?
subid_name <- "Subject"
x.max <- 1680
y.max <- 1050
left_x_col_name = "L POR X [px]"
right_x_col_name = "R POR X [px]"
left_y_col_name = "L POR Y [px]"
right_y_col_name = "R POR Y [px]"

#Specify file 
file_name <- "Reflook4_2 (2)_052212_2_2133 Samples.txt"
#file_name <- "SAN-071218-01-eye_data Samples.txt"

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

#read in data
data <-  
  read_delim(
    file_path,
    comment="##",
    delim=sep
  )

#select rows and column names for xy file
data <-  data %>%
  filter(Type=="SMP") %>%
  select(
    raw_t = "Time",
    lx = left_x_col_name,
    rx = right_x_col_name,
    ly = left_y_col_name,
    ry = right_y_col_name,
    trial_id = "Trial"
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
     select(
       -rx, -ry, -lx, -ly
     )

## Convert time into ms starting from 0
data <- data %>% 
  mutate(
    t = round((data$raw_t - data$raw_t[1])/1000, 3)
    )

# Redefine coordinate origin (0,0)
# SMI starts from top left
# Here we convert the origin of the x,y coordinate to be bottom left (by "reversing" y-coordinate origin)
data <- data %>%
  mutate(
    y = y.max - y
  )

#extract final columns
data <- data %>%
  select(sub_id,x,y,t,trial_id)

#Write data
write_csv(data,path=fs::path(project_root,"data","etds_smi_raw","processed_data","xy_data.csv"))