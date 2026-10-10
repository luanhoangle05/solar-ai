# Backend image: generates one agent recommendation (Data -> Modeling -> Optimization -> Manager).
#
#   docker build -t solar-ai-backend .
#   docker run --rm -v "${PWD}/out:/out" solar-ai-backend
#
# The image holds the code and the small committed datasets only. It contains no
# API key and not the full 2023-2025 dataset; both are supplied at run time.

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# XGBoost needs the OpenMP runtime, which the slim base image leaves out.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first, so code changes do not reinstall them. The extra index supplies
# the CPU build of PyTorch; the default Linux wheel bundles GPU libraries this never uses.
COPY requirements.txt .
RUN pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu

COPY src ./src
COPY scripts ./scripts
COPY data/mock ./data/mock
COPY data/example ./data/example
COPY data/generated/gem_seasonal_sample ./data/generated/gem_seasonal_sample

# Run as an unprivileged user; results are written to /out, which the caller mounts.
RUN useradd --create-home --uid 10001 solar \
    && mkdir -p /out \
    && chown solar /out
USER solar
VOLUME ["/out"]

ENTRYPOINT ["python", "-m", "scripts.run_recommendation"]
CMD ["--skip-lstm", "--output", "/out/recommendation.json"]
