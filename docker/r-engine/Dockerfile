# Pinned R engine for RFC-0003 (RFC-0000 §6 version pinning).
# Base and packages are pinned so sample-size computations are reproducible across machines.
FROM rocker/r-ver:4.4.2

# Pin packages reproducibly via a Posit Package Manager dated snapshot (the date pins versions).
# rpact is the engine power.R uses; gsDesign is omitted here because it drags the full ggplot2
# source-compile tree on arm64. Add it back when group-sequential boundary plots are needed.
ARG PPM_SNAPSHOT=2025-01-15

RUN R -q -e "options(repos = c(CRAN = 'https://packagemanager.posit.co/cran/${PPM_SNAPSHOT}'), Ncpus = 4); \
          install.packages(c('jsonlite', 'rpact')); \
          stopifnot(all(c('jsonlite','rpact') %in% rownames(installed.packages())))"

COPY power.R /opt/clinique/power.R

# No ENTRYPOINT: the adapter invokes `Rscript /opt/clinique/power.R` explicitly.
CMD ["Rscript", "/opt/clinique/power.R"]
