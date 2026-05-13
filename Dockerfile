# Dockerfile for GPRD Analysis Environment
# Global Procurement Research Dataset - Causal Analysis Toolkit

FROM continuumio/miniconda3:23.5.2-0

LABEL maintainer="Abduxoliq Ashuraliyev <Jack00040008@outlook.com>"
LABEL description="Reproducible environment for GPRD procurement analysis"
LABEL version="1.0.0"

# Set working directory
WORKDIR /workspace

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Copy environment file
COPY environment.yml /workspace/environment.yml

# Create conda environment
RUN conda env create -f environment.yml && \
    conda clean -afy

# Activate environment by default
SHELL ["conda", "run", "-n", "procurement-rdd", "/bin/bash", "-c"]

# Copy project files
COPY . /workspace/

# Install package in development mode
RUN pip install -e .

# Set environment variables
ENV GPRD_DATA_DIR=/workspace/data
ENV GPRD_CACHE_DIR=/workspace/.cache

# Default command
CMD ["snakemake", "--cores", "4", "--help"]
