[![Version](https://img.shields.io/pypi/v/genepattern-notebook.svg)](https://pypi.python.org/pypi/galaxy-galahad)
[![Documentation Status](https://img.shields.io/badge/docs-latest-brightgreen.svg?style=flat)](https://www.g2nb.org/basic-features/)
[![Docker Pulls](https://img.shields.io/docker/pulls/g2nb/lab.svg)](https://hub.docker.com/r/g2nb/lab/)

# Galahad

Connect to the [Galaxy platform](https://usegalaxy.org/) within Jupyter notebooks by means of user-friendly interactive widgets

### **Prerequisites**

* JupyterLab >= 3.6.0
* ipywidgets >= 8.0.0

# Docker

A Docker image with galahad and the full JupyterLab stack is available through DockerHub.

```bash
docker pull g2nb/lab
docker run --rm -p 8888:8888 g2nb/lab
```

# Installation

> pip install galaxy-galahad

Full installation instructions for casual use are detailed on the 
[g2nb website](https://docs.g2nb.org/en/latest/local-installation/). Users should 
also consider the [g2nb Workspace](https://workspace.g2nb.org), which 
provides an install-free cloud deployment of the full suite of g2nb tools, including Galahad.
