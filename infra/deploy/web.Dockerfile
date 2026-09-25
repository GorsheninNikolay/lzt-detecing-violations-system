FROM nginx:1.27-alpine
COPY infra/deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY web/dist/ /usr/share/nginx/html/
