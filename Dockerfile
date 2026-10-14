# Static hosting. Build: docker build -t polyxandria-demos .
FROM nginx:1.27-alpine
COPY . /usr/share/nginx/html
RUN rm -f /usr/share/nginx/html/Dockerfile /usr/share/nginx/html/DEPLOY.md
EXPOSE 80
