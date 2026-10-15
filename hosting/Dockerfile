FROM node:22-slim
WORKDIR /app
COPY hosting/server.js /app/server.js
COPY site /site
ENV SITE_ROOT=/site NODE_ENV=production
USER node
CMD ["node","/app/server.js"]
