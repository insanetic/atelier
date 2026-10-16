# The tools the paperwork engine runs with. The base image is pinned by digest and the engine
# records every tool's version in each document record, so a result can be traced to its tools.
FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258
RUN apt-get update \
 && apt-get install -y --no-install-recommends poppler-utils tesseract-ocr tesseract-ocr-deu tesseract-ocr-eng \
 && rm -rf /var/lib/apt/lists/*
ENV LC_ALL=C.UTF-8 TZ=UTC PYTHONDONTWRITEBYTECODE=1
