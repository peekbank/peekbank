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
    "sample_data",
    "smi_raw",
    "test_aois",
    "o_clock_lamp (AOIs).xml"
  )

xml_list <- xmlParse(sample_file_path) %>% xmlToList(simplify = TRUE)

get_coordinates <- function(xml_list) {
  
}




