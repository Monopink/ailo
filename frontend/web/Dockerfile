# Use an official Node.js runtime as a parent image
FROM node:18-alpine

# Set the working directory in the container
WORKDIR /app

# Set build-time arguments
ARG VITE_LEANCLOUD_APP_ID
# Note: VITE_LEANCLOUD_APP_KEY is a frontend public key, not a secret
ARG VITE_LEANCLOUD_APP_KEY
ARG VITE_LEANCLOUD_SERVER_URL
ARG VITE_API_BASE_URL
ARG VITE_APP_VERSION

# Set as environment variables
ENV VITE_LEANCLOUD_APP_ID=$VITE_LEANCLOUD_APP_ID
# Note: This is a frontend public key, exposed to browsers
ENV VITE_LEANCLOUD_APP_KEY=$VITE_LEANCLOUD_APP_KEY
ENV VITE_LEANCLOUD_SERVER_URL=$VITE_LEANCLOUD_SERVER_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_APP_VERSION=$VITE_APP_VERSION

# Copy package.json and package-lock.json to the working directory
COPY package*.json ./

# Install project dependencies
RUN npm install

# Copy the rest of the application's source code to the working directory
COPY . .

# Expose the port the app runs on
EXPOSE 5173

# Command to run the application in development mode with hot-reloading
CMD ["npm", "run", "dev", "--", "--host"] 