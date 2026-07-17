FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/workspace

WORKDIR /workspace

# Runtime library needed by LightGBM/XGBoost wheels.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock.txt requirements.tsfresh.txt /tmp/
RUN pip install --upgrade pip \
    && pip install -r /tmp/requirements.lock.txt \
    && pip install -r /tmp/requirements.tsfresh.txt

COPY . /workspace
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /workspace
USER appuser

CMD ["bash"]
