# Образ клиентской части: статические файлы одностраничного приложения под nginx.
ARG BASE_REGISTRY=docker.io/library
FROM ${BASE_REGISTRY}/nginx:1.30.6-alpine
ARG APP_VERSION=0.0.0-dev
LABEL org.opencontainers.image.title="bank-payments-frontend" \
      org.opencontainers.image.version="${APP_VERSION}"
COPY nginx.conf /etc/nginx/nginx.conf
COPY src/ /usr/share/nginx/html/
# Версия сборки подставляется в страницу, чтобы её было видно в интерфейсе
RUN sed -i "s/__APP_VERSION__/${APP_VERSION}/g" /usr/share/nginx/html/index.html \
 && rm -f /etc/nginx/conf.d/default.conf
USER nginx
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD ["wget", "-q", "-O", "/dev/null", "http://127.0.0.1:8080/healthz"]
