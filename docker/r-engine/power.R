#!/usr/bin/env Rscript
# JSON-in / JSON-out rpact wrapper (RFC-0003 §5.4).
# Reads one JSON object from stdin: {"method": ..., <params>}; writes {"outputs":..., "achieved":...,
# "rpact_version":...} to stdout. The canonical, regulatory-validated sample-size engine.

suppressMessages({
  library(jsonlite)
  library(rpact)
})

req <- fromJSON(file("stdin"))
beta <- 1 - req$power

out <- list(rpact_version = as.character(packageVersion("rpact")))

if (req$method == "two_sample_means") {
  r <- getSampleSizeMeans(
    alternative = req$delta, stDev = req$sd,
    alpha = req$alpha, beta = beta, sided = req$sides,
    allocationRatioPlanned = req$ratio
  )
  n1 <- ceiling(as.numeric(r$numberOfSubjects1))
  n2 <- ceiling(as.numeric(r$numberOfSubjects2))
  out$outputs <- list(n1 = n1, n2 = n2, n_total = n1 + n2)
  out$achieved <- list(achieved_power = round(req$power, 4))

} else if (req$method == "two_proportions") {
  r <- getSampleSizeRates(
    pi1 = req$p1, pi2 = req$p2,
    alpha = req$alpha, beta = beta, sided = req$sides,
    allocationRatioPlanned = req$ratio
  )
  n1 <- ceiling(as.numeric(r$numberOfSubjects1))
  n2 <- ceiling(as.numeric(r$numberOfSubjects2))
  out$outputs <- list(n1 = n1, n2 = n2, n_total = n1 + n2)
  out$achieved <- list(achieved_power = round(req$power, 4))

} else if (req$method == "survival_logrank") {
  ratio <- req$allocation / (1 - req$allocation)
  r <- getSampleSizeSurvival(
    hazardRatio = req$hazard_ratio,
    alpha = req$alpha, beta = beta, sided = req$sides,
    allocationRatioPlanned = ratio
  )
  events <- ceiling(as.numeric(r$maxNumberOfEvents))
  out$outputs <- list(events_total = events)
  out$achieved <- list(achieved_power = round(req$power, 4))

} else {
  write(toJSON(list(error = paste("unknown method", req$method)), auto_unbox = TRUE), stderr())
  quit(status = 1)
}

cat(toJSON(out, auto_unbox = TRUE, digits = 10))
