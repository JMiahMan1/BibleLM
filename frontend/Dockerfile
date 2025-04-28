# Stage 1: Build the Next.js application
FROM node:18-alpine AS builder

WORKDIR /app

# Copy package.json and lock file
COPY package*.json ./
# COPY yarn.lock ./ # Uncomment if using yarn

# Install dependencies
RUN npm install
# RUN yarn install # Uncomment if using yarn

# Copy the rest of the application code
COPY . .

# Set build-time environment variables if needed
# ARG NEXT_PUBLIC_API_URL=http://backend:8000 # Example if backend is named 'backend' in docker-compose
# ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

# Build the Next.js application
RUN npm run build
# RUN yarn build # Uncomment if using yarn

# Stage 2: Serve the application with Node.js standalone output
FROM node:18-alpine

WORKDIR /app

ENV NODE_ENV production
# Optional: Disable telemetry
ENV NEXT_TELEMETRY_DISABLED 1

# Copy necessary files from the build stage
COPY --from=builder /app/public ./public
COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static

# Set the user to non-root
USER node

EXPOSE 3000

ENV PORT 3000

# Start the application
CMD ["node", "server.js"]
