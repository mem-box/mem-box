FROM mcr.microsoft.com/devcontainers/python:3.11

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set uv to use system python
ENV UV_SYSTEM_PYTHON=1