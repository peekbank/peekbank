## This is the hack start script for reading raw eye tracking data
## by Linger Xu -- txu@indiana.edu | linger.xt@gmail.com
## date 08/19/2019

setwd("C:/Dropbox/_codes/peekbank-hack/EtDS_tobii/import_scripts")

rm(list=ls())
dir_raw <- "../raw_data"
dir_save <- "../processed_data"
file_raw <- file.path(dir_raw, "tobii-sample.tsv")
file_header <- "import_header.csv"

## STEP 0. read in raw datafiles and the column names
df_header <- read.csv(file=file_header, header=TRUE, sep=",")
df_raw <- read.table(file = file_raw, sep = '\t', header = TRUE)
colnames_raw <- colnames(df_raw)

###############################
## FUNCTION 1 -- tobii_to_xy() 
###############################

## search through raw data table and find desired columns, 
## if they did not exist, then just create an empty column with NA values
colnames_fetch <- as.vector(df_header[[ "xy_data_tobii"]])
colnames_xy <- as.vector(df_header[["xy_data_save"]])

## create new xy table
df_xy <- data.frame(matrix(ncol = length(colnames_xy), 
                               nrow = nrow(df_raw)))
colnames(df_xy) <- colnames_xy

for (i in 1:length(colnames_fetch)) {
  if (colnames_fetch[i] %in% colnames_raw) {
    df_xy[i] = df_raw[colnames_fetch[i]]
  } else {
    cat(colnames_fetch[i], "does not exist in the raw data file", file_raw, "\n")
  }
}

## write xy table as csv file
if (!file.exists(dir_save)) {
  dir.create(dir_save)
}

write.csv(df_xy, file.path(dir_save, "xy_data.csv"), row.names=FALSE)

###############################
## FUNCTION 2 -- tobii_to_aoi() 
###############################
colnames_fetch <- as.vector(df_header[[ "aoi_data_tobii"]])
colnames_fetch <- colnames_fetch[colnames_fetch != ""]
colnames_aoi <- as.vector(df_header[["aoi_data_save"]])
colnames_aoi <- colnames_aoi[colnames_aoi != ""]

## create new aoi table
df_aoi <- data.frame(matrix(ncol = length(colnames_aoi), 
                           nrow = nrow(df_raw)))
colnames(df_aoi) <- colnames_aoi

for (i in 1:length(colnames_fetch)) {
  if (colnames_fetch[i] %in% colnames_raw) {
    df_aoi[i] = df_raw[colnames_fetch[i]]
  } else {
    cat(colnames_fetch[i], "does not exist in the raw data file", file_raw, "\n")
  }
}

## write xy table as csv file
if (!file.exists(dir_save)) {
  dir.create(dir_save)
}

write.csv(df_aoi, file.path(dir_save, "aoi_data.csv"), row.names=FALSE)