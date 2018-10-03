# Initial setup (uncomment, run only once, then re-comment)
# install.packages("RHRV") # from http://rhrv.r-forge.r-project.org/
# install.packages("fpp2") # suggested from https://uc-r.github.io/ts_exploration#ts_plots
# install.packages("ggfortify") # https://cran.r-project.org/web/packages/ggfortify/vignettes/plot_ts.html

# Imports
library(ggplot2)
library(forecast)
library(fpp2)
library(ggfortify)

# Set working directory
setwd("/Users/bucci/Desktop/programming_scratch/REMO_data/")

# Read a single CSV
bpv.df <- read.csv("data/record_1537380012888_00047A8B3.csv", header=TRUE, sep=",", skip=7)

# Plot

# ts(data, start=(start_time, end_time, frequency))

bpv.ts <- ts(bpv.df["heart_rate_voltage"], start = c(2000, 1), end=c(10000), frequency = 1) # 305405 datapoints

autoplot(bpv.ts)

