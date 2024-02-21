# Use a base image with Python and other dependencies
FROM python:3.10

# Set the working directory inside the container
WORKDIR /app

# Copy requirements file and install dependencies
COPY python/requirements.txt .
RUN pip install -r requirements.txt

# Copy the system script into the container
COPY python/benchmark/benchmark.py .
COPY data/ /data/

# Set the command to run your system script
CMD ["python", "benchmark.py"]

