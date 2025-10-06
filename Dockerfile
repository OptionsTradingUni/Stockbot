FROM python:3.12-slim

WORKDIR /app

# Copy only the requirements file first to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code
COPY . .

# ... (rest of your Dockerfile)

# Use the shell form to allow environment variable substitution
CMD gunicorn web_server:app --bind 0.0.0.0:$PORT
