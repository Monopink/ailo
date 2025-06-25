# frontend/web_dev/Dockerfile

# Use the official Nginx image from Docker Hub
FROM nginx:alpine

# Remove the default nginx index.html
RUN rm /usr/share/nginx/html/index.html

# Copy our custom index.html to the Nginx html directory
COPY ./index.html /usr/share/nginx/html 