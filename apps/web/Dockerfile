FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
FROM node:22-alpine AS builder
WORKDIR /app
ARG OPENMUSE_API_INTERNAL=http://api:8000
ENV OPENMUSE_API_INTERNAL=$OPENMUSE_API_INTERNAL
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build
FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV OPENMUSE_API_INTERNAL=http://api:8000
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
EXPOSE 3000
CMD ["node", "server.js"]
