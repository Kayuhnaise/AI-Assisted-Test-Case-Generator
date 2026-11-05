FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y build-essential git lcov flex bison perl \
    libreadline-dev zlib1g-dev libicu-dev pkg-config && rm -rf /var/lib/apt/lists/*

RUN useradd -m pguser
USER pguser
WORKDIR /home/pguser
RUN for attempt in 1 2 3; do \
      if git -c http.version=HTTP/1.1 clone --depth 1 --branch REL_17_STABLE \
        https://git.postgresql.org/git/postgresql.git; then \
        exit 0; \
      fi; \
      rm -rf postgresql; \
      sleep "$attempt"; \
    done; \
    echo "PostgreSQL source clone failed after 3 attempts" >&2; \
    exit 1
WORKDIR /home/pguser/postgresql
RUN ./configure --enable-coverage --enable-debug --enable-cassert \
      --prefix=/home/pguser/pg-cov CFLAGS="-O0" \
    && make -j$(nproc) && make install