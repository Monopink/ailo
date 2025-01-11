# use python 3.11-slim as base image
FROM python:3.11-slim

# set working directory
WORKDIR /app

# copy requirements.txt to container's / directory
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy app source code to container's /app directory
COPY app /app

# mount the app directory to the container
VOLUME ["/app"]

# run the application
CMD ["python"]