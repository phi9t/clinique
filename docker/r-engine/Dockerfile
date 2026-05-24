# Pinned R engine for RFC-0003 (RFC-0000 §6 version pinning).
# Base and packages are pinned so sample-size computations are reproducible across machines.
FROM rocker/r-ver:4.4.2

# Pin rpact + gsDesign to exact versions via Posit Package Manager dated snapshot.
ARG PPM_SNAPSHOT=2025-01-15
ARG RPACT_VERSION=4.1.1
ARG GSDESIGN_VERSION=3.6.5

RUN R -e "options(repos = c(CRAN = 'https://packagemanager.posit.co/cran/${PPM_SNAPSHOT}')); \
          install.packages('remotes'); \
          remotes::install_version('jsonlite', upgrade='never'); \
          remotes::install_version('rpact', version='${RPACT_VERSION}', upgrade='never'); \
          remotes::install_version('gsDesign', version='${GSDESIGN_VERSION}', upgrade='never')"

COPY power.R /opt/clinique/power.R

ENTRYPOINT ["Rscript"]
CMD ["/opt/clinique/power.R"]
