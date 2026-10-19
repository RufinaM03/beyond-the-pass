FROM node:24.15.0-bookworm-slim@sha256:4e6b70dd6cbfc88c8157ba19aa3d9f9cce6ba4703576d55459e45efcbc9c5f5d AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/index.html ./
COPY frontend/src ./src
RUN npm run build

FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258 AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
    TMPDIR=/tmp/btp TEMP=/tmp/btp TMP=/tmp/btp SQLITE_TMPDIR=/tmp/btp \
    BTP_RELEASE_DESCRIPTOR=/app/release/descriptor.json BTP_FRONTEND_DIR=/app/frontend/dist \
    BTP_ALLOW_FIXTURE=0
WORKDIR /app
COPY requirements-data.lock requirements-model.lock requirements-app.lock ./
RUN python -m pip install --no-cache-dir --only-binary=:all: --index-url https://pypi.org/simple -r requirements-app.lock && python -m pip check
COPY backend ./backend
COPY pipeline ./pipeline
COPY scripts ./scripts
COPY tools ./tools
COPY release ./release
COPY package-manifest.json ./
ARG ARTIFACT_MODE=release
ARG ARTIFACT_VERSION
ARG CODE_VERSION
RUN python -m scripts.package_release validate-bundle --mode "$ARTIFACT_MODE" --context /app --code-version "$CODE_VERSION" --artifact-version "$ARTIFACT_VERSION"
COPY --from=frontend /build/dist ./frontend/dist
RUN groupadd --gid 10001 btp && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin btp && mkdir -p /tmp/btp && chown 10001:10001 /tmp/btp && chmod -R a-w /app && chmod 1777 /tmp/btp
ENV BTP_CODE_VERSION=$CODE_VERSION
LABEL org.opencontainers.image.title="Beyond the Pass" \
      org.opencontainers.image.revision="$CODE_VERSION" \
      io.btp.artifact.release="$ARTIFACT_VERSION" \
      io.btp.artifact.kind="$ARTIFACT_MODE" \
      io.btp.platform="linux/amd64"
USER 10001:10001
EXPOSE 8000
STOPSIGNAL SIGTERM
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/ready',timeout=4).close()"]
CMD ["python", "-m", "uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--timeout-graceful-shutdown", "20"]
