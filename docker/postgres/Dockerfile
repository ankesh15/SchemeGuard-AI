FROM postgres:16-alpine AS extension
ARG PGVECTOR_VERSION=0.8.7
ARG PGVECTOR_SHA256=cac0b10c360f05b2d521200105ba3697e773d4cd3731f5a915a7e37ebe0bea85
RUN apk add --no-cache build-base curl \
    && curl --fail --location --retry 3 "https://codeload.github.com/pgvector/pgvector/tar.gz/refs/tags/v${PGVECTOR_VERSION}" -o /tmp/vector.tar.gz \
    && echo "${PGVECTOR_SHA256}  /tmp/vector.tar.gz" | sha256sum -c - \
    && mkdir /tmp/vector && tar -xzf /tmp/vector.tar.gz --strip-components=1 -C /tmp/vector \
    && make -C /tmp/vector with_llvm=no OPTFLAGS="" \
    && make -C /tmp/vector with_llvm=no install

# Keep the existing PostgreSQL major version, Alpine libc and data directory.
FROM postgres:16-alpine
COPY --from=extension /usr/local/lib/postgresql/vector.so /usr/local/lib/postgresql/vector.so
COPY --from=extension /usr/local/share/postgresql/extension/vector* /usr/local/share/postgresql/extension/
