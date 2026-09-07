# Manipulus ships as an image so a clone and a build is the whole install.
#
# The image carries no Magento and no store. Mount the Magento root read-only and
# point the tool at it:
#
#   docker run --rm -v /path/to/magento:/magento:ro -v "$PWD:/out" manipulus:latest \
#       plan --root /magento --theme frontend/Magento/luma --out /out/manipulus.plan.json

# Both stages are built from the same python image so the virtualenv's console script
# keeps a shebang that exists at runtime. Building on the uv image instead leaves the
# script pointing at an interpreter path the runtime stage does not have, and the
# container fails with a bare "no such file or directory".
FROM python:3.12-slim-bookworm AS build

COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv

# The virtualenv is built at the path it will be served from. A venv's console script
# hardcodes the venv path in its shebang, so building at /src/.venv and copying it to
# /opt would leave the entry point pointing at a directory the runtime stage lacks.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/manipulus

WORKDIR /src

# Dependencies resolve from the lockfile alone, so a source edit does not refetch them.
COPY pyproject.toml uv.lock README.md LICENSE ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project --no-editable

COPY src/ ./src/
# --no-editable matters: an editable install would leave the venv pointing at /src,
# which does not exist in the runtime stage.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable


FROM python:3.12-slim-bookworm AS runtime

LABEL org.opencontainers.image.title="manipulus" \
      org.opencontainers.image.description="Static RequireJS bundle planner for Magento 2" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.source="https://github.com/kingletas/manipulus"

# Nothing here needs root, and a bundle run only ever reads the mounted tree.
RUN useradd --create-home --uid 1000 manipulus

COPY --from=build --chown=manipulus:manipulus /opt/manipulus /opt/manipulus
ENV PATH="/opt/manipulus/bin:$PATH"

USER manipulus
WORKDIR /magento

ENTRYPOINT ["manipulus"]
CMD ["--help"]
