# Use a base image with Python and other dependencies
FROM python:3.10

# Set the working directory inside the container
WORKDIR /app

# Copy requirements file and install dependencies
COPY python/baseline-system/requirements.txt .
RUN pip install -r requirements.txt

# Copy the system script into the container
COPY python/baseline-system/system.py .

# Set the command to run your system script
CMD ["python", "system.py"]
