## This is the hack start script for reading raw eye tracking data
## by Linger Xu -- txu@indiana.edu | linger.xt@gmail.com
## date 08/20/2019

rm(list=ls())
source("../../../peekds/R/readers.R")
#dir_current <- dirname(sys.frame(1)$ofile)
#setwd(dir_current)
#setwd("C:/Dropbox/_codes/peekbank-hack/EtDS_tobii/import_scripts")

# TASK 1: needs to change tobii interface to allow for multiple file reads
dir_raw <- "../raw_data/tobii-sample.tsv"
process_tobii(dir_raw = dir_raw)
