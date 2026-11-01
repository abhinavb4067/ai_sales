FROM node:20-slim AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
# VITE_* vars are baked into the static bundle at build time, not read at
# container runtime — pass them as build args in CI/CD, not via `docker run -e`.
ARG VITE_API_BASE_URL
ARG VITE_WHATSAPP_META_APP_ID
ARG VITE_WHATSAPP_META_CONFIG_ID
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_WHATSAPP_META_APP_ID=$VITE_WHATSAPP_META_APP_ID \
    VITE_WHATSAPP_META_CONFIG_ID=$VITE_WHATSAPP_META_CONFIG_ID
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
