## This is the hack start script for reading raw eye tracking data
## by Linger Xu -- txu@indiana.edu | linger.xt@gmail.com
## date 08/20/2019

setwd("C:/Dropbox/_codes/peekbank-hack/EtDS_tobii/import_scripts")
rm(list=ls())

set_workingdir <- function() {
  dir_current <- dirname(rstudioapi::getSourceEditorContext()$path)
  setwd(dir_current)
}

file_raw <- "../raw_data/tobii-sample.tsv"
raw_data <- read.table(file = file_raw, sep = '\t', header = TRUE)

## do mapping
#df_xy_data <- map_columns(raw_data = raw_data, raw_format = "tobii", table_type = "xy_data")
#df_aoi_data <- map_columns(raw_data = raw_data, raw_format = "tobii", table_type = "aoi_data")

# Setup
options(scipen=999)  # turn off scientific notation like 1e+06
library(ggplot2)
data("midwest", package = "ggplot2")  # load the data
# midwest <- read.csv("http://goo.gl/G1K41K") # alt source 

# Init Ggplot
ggplot(midwest, aes(x=area, y=poptotal))  # area and poptotal are columns in 'midwest'