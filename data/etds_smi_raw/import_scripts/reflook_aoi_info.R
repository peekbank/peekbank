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
library(rstanarm)
library(fs)

# load tidyverse last, so no functions get masked
library(tidyverse)
project_root <- here::here()

#sample file 
sample_file_path <- 
  fs::path(
    project_root,
    "data",
    "etds_smi_raw",
    "raw_data",
    "test_aois",
    "o_clock_lamp (AOIs).xml"
  )

xml_obj <- xmlParse(sample_file_path) %>% xmlToList()

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




