
FROM node:24-alpine

# Create a program variable
ENV DASHBOARD_DIR=/MIRA-frontend

# Set up volume directory
VOLUME ${DASHBOARD_DIR}

# Set up working directory 
WORKDIR ${DASHBOARD_DIR}

# Copy source code
COPY . ${DASHBOARD_DIR}

# Install dependencies listed in package-lock.json and clean npm cache
RUN npm ci && npm cache clean --force

# Expose app to port 5175
EXPOSE 5175

# Start the Vite dev server
ENTRYPOINT ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5175"]

