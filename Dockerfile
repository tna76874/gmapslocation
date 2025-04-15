# Use official Python 3.12 image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy only requirements to install dependencies first (to cache better)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app (excluding 'data' via .dockerignore)
COPY . .

# Define default command
CMD ["python", "cli.py", "--update", "--upload"]
