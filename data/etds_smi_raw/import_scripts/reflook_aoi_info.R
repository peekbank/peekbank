# load libraries
library(reshape); library(plyr); library(grid)
library(lme4); library(knitr)
library(XML); library(gridExtra)
library(magrittr); #library(langcog); 
library(stringr); library(arm)
library(directlabels); library(lazyeval) 
library(forcats); library(GGally); library(lsr)
library(effsize); library(cowplot)
library(scales); library(feather) 
library(stringr); library(pryr)
library(rstanarm);

# load tidyverse last, so no functions get masked
library(tidyverse); 

project_root <- here::here()

##also read in enough of the eye data to get the maximum x and y
max_lines_subj_search <- 40 #maybe change this value?
monitor_size <- "Calibration Area"

#add file name for eye_samples.txt
file_name <- "Reflook4_2 (2)_052212_2_2133 Samples.txt"

#build this file path
file_path <- fs::path(project_root,"data","etds_smi_raw","raw_data",file_name)

#guess delimiter
sep <- get.delim(file_path, comment="#", delims=c("\t",","),skip = max_lines_subj_search)

#get monitor size
monitor_size <- read_lines(file_path, n_max=max_lines_subj_search) %>%
  str_subset(monitor_size) %>% 
  str_extract(paste("(?<=",monitor_size,":\\t).*",sep="")) %>%
  trimws() %>%
  str_split("\t")%>%
  unlist()

#get maximum y of monitor size
y_max <- as.numeric(monitor_size[2]) ##NB this is based on one participant's data, but it's totally possible that participants were run on different monitors



xml_obj <- xmlParse(sample_file_path) %>% xmlToList(simplify = FALSE)


###Big to-do: The calculations for ymin/ymax depend on knowing the size of the monitor;
#this is hardcoded in here, but needs to be adjusted for each participant, given that they might be run on diff. monitors
#start by getting a list of the files in the current directory
#sample file for 
# sample_file_path <- 
#   fs::path(
#     project_root,
#     "data",
#     "etds_smi_raw", 
#     "raw_data", 
#     "test_aois"
#     # "o_clock_lamp (AOIs).xml"
#   )

#

get_coords_t_d <- function(xml_obj) {
  ##first get the files in the appropriate directory
  file.names <- list.files(path = fs::path(project_root, "data", "etds_smi_raw", "raw_data", "test_aois"), 
                      pattern="*.xml", full.names=FALSE, recursive=TRUE)
  
  for(file in file.names) {
    #look at xml
  }
  #what this function needs to do: 
  #take each xml file in a directory
  #read in the xml file
  #sort into target and distractor
  #get the x/y min/max
  #get the aoi_id
  #output to a df
}

#name the two sublists Target and Distractor appropriately
if(xml_obj[[1]]$Group == 'Target') {
  names(xml_obj) <- c('Target', 'Distractor')
} else {
  names(xml_obj) <- c('Distractor', 'Target')
}
x_coords <- xml_obj$Target$Points

aoi_x_min = xml_obj$Target[['Points']][[1]]$X
aoi_y_min = y_max - as.numeric(xml_obj$Target[['Points']][[2]]$Y)
aoi_x_max = xml_obj$Target[['Points']][[2]]$X
aoi_y_max = y_max - as.numeric(xml_obj$Target[['Points']][[1]]$Y)

get_coordinates <- function(xml_obj) {
  
}




