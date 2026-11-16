# Образ шлюза: nginx завершает TLS и распределяет запросы между репликами
# клиентской и серверной частей.
ARG BASE_REGISTRY=docker.io/library
FROM ${BASE_REGISTRY}/nginx:1.30.6-alpine
ARG APP_VERSION=0.0.0-dev
LABEL org.opencontainers.image.title="bank-payments-gateway" \
      org.opencontainers.image.version="${APP_VERSION}"
COPY nginx.conf /etc/nginx/nginx.conf
RUN rm -f /etc/nginx/conf.d/default.conf
USER nginx
EXPOSE 8443
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD ["wget", "-q", "--no-check-certificate", "-O", "/dev/null", "https://127.0.0.1:8443/healthz"]
