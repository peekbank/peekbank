## Load packages
library(here)
library(tidyverse)
library(janitor)
library(reader)

#Specify file
file_name <- "Reflook4_2 (2)_052212_2_2133 Samples.txt"

#Define root path
project_root <- here::here()
#build file path
file_path <- fs::path(project_root,"sample_data","smi_raw",file_name)


#specify delimiter
sep <- get.delim(file_path, comment="#")

#read in data
data <-  
  read_delim(
    file_path,
    comment="#",
    delim=sep
  )

#clean data names
data <- data %>%
  clean_names()

#select column names for xy file
data <-  data %>%
  select(
    raw_t = "time",
    lx = "l_por_x_px",
    rx = "r_por_x_px",
    ly = "l_por_y_px",
    ry = "r_por_y_px",
    trial_id = "trial"
)

  
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
    t = round((data$raw_t - data$raw_t[1])/1000000, 3)
    )

data$diff_t <- c(0,diff(data$raw_t))

# Redefine coordinate origin (0,0)
# SMI starts from top left
# Here we convert the origin of the x,y coordinate to be bottom left (by "reversing" y-coordinate origin)
x.max = 1920
y.max=1080

data <- data %>%
  mutate(
    y = y.max - y
  )

