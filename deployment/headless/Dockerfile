# syntax=docker/dockerfile:1@sha256:4edf897a3ffa55b89f906fc8cc78afdb3f1834cc9c7083565e611a8a7d5fe99e
# Task1-verified Debian amd64 and native Beads identities. No executor/auth here.
FROM debian:trixie-slim@sha256:7378260c0a098d27ac206225db5e7d92b8c7c84ea7afccc86eeb513756bbd392
# Immutable signed package snapshot; no mutable apt sources or latest downloads.
RUN rm /etc/apt/sources.list.d/debian.sources && printf '%s\n' \
    'deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/20261104T212339Z trixie main' \
    'deb [check-valid-until=no] http://snapshot.debian.org/archive/debian-security/20261104T212339Z trixie-security main' \
    > /etc/apt/sources.list && apt-get update && apt-get install -y --no-install-recommends \
    python3=3.13.5-1 git=1:2.47.3-0+deb13u1 libc6=2.41-12+deb13u4 ca-certificates=20250419+deb13u1 \
    && rm -rf /var/lib/apt/lists/*
ADD --checksum=sha256:175c26904bde3ff9168d2282ff6b56f17b17f60c22fa5acb3dacc9fb3465303a \
    https://github.com/gastownhall/beads/releases/download/v1.3.4/beads_1.3.4_linux_amd64.tar.gz /tmp/beads.tar.gz
RUN tar -xzf /tmp/beads.tar.gz -C /usr/local/bin bd \
    && echo '9185e9798ba044b288e781f7d57f28a48f558654e94572473e49991826e69930  /usr/local/bin/bd' | sha256sum -c - \
    && rm /tmp/beads.tar.gz && mkdir -p /data/beads /data/runtime/home /app
ENV PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app HOME=/data/runtime/home
WORKDIR /app
COPY task_tower/ /app/task_tower/
ENTRYPOINT ["python3", "-m", "task_tower.service.cli", "--config", "/data/runtime/service.json", "--container-network"]
