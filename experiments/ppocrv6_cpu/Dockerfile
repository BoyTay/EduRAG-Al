FROM python:3.11-slim

ARG PADDLE_INDEX_URL=https://www.paddlepaddle.org.cn/packages/stable/cpu/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=1 \
    PADDLE_PDX_CACHE_HOME=/opt/ppocr-cache

WORKDIR /spike

# libgomp1 is a runtime dependency of Paddle/OpenCV CPU wheels.
# fonts-dejavu-core is used only to generate the non-sensitive Vietnamese fixture.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY experiments/ppocrv6_cpu/requirements-spike.txt /tmp/requirements-spike.txt

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir \
       --index-url "${PADDLE_INDEX_URL}" paddlepaddle==3.3.0 \
    && python -m pip install --no-cache-dir \
       -r /tmp/requirements-spike.txt \
    && python -m pip check

# The GUI OpenCV wheel pinned by PaddleX links against these at import time.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY experiments/ppocrv6_cpu/smoke_test.py /spike/smoke_test.py

CMD ["python", "/spike/smoke_test.py"]
