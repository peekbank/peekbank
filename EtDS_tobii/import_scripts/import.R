## This is the hack start script for reading raw eye tracking data
## by Linger Xu -- txu@indiana.edu | linger.xt@gmail.com
## date 08/19/2019

setwd("C:/Dropbox/_codes/peekbank-hack/EtDS_tobii/import_scripts")
rm(list=ls())

###############################
## FUNCTION -- tobii_to_[**]() 
## ** can be xy, aoi, trial, participants, 
###############################
raw_to_processed <- function(module) {
  dir_raw <- "../raw_data"
  dir_save <- "../processed_data"
  file_raw <- file.path(dir_raw, "tobii-sample.tsv")
  file_header <- "import_header.csv"
  
  ## STEP 0. read in raw datafiles and the column names
  df_header <- read.csv(file=file_header, header=TRUE, sep=",")
  df_raw <- read.table(file = file_raw, sep = '\t', header = TRUE)
  colnames_raw <- colnames(df_raw)
  
  ## search through raw data table and find desired columns, 
  ## if they did not exist, then just create an empty column with NA values
  colnames_fetch <- as.vector(
    df_header[[
      paste(module, "_tobii", sep="")]])
  colnames_save <- as.vector(
    df_header[[
      paste(module, "_save", sep="")]])
  
  ## create new data table
  df_save <- data.frame(
    matrix(
      ncol = length(colnames_save), nrow = nrow(df_raw)))
  colnames(df_save) <- colnames_save
  
  for (i in 1:length(colnames_fetch)) {
    if (colnames_fetch[i] %in% colnames_raw) {
      df_save[i] = df_raw[colnames_fetch[i]]
    } else {
      cat(colnames_fetch[i], "does not exist in the raw data file", file_raw, "\n")
    }
  }
  
  ## write new data table as csv file
  if (!file.exists(dir_save)) {
    dir.create(dir_save)
  }
  
  write.csv(df_save, file.path(
    dir_save, paste(module, ".csv", sep="")), row.names=FALSE)
  
  return(dir_save)
}

## main starts here
raw_to_processed(module = "xy_data")
raw_to_processed(module = "aoi_data")
