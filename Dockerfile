FROM python:3.12-slim

WORKDIR /app

# Copy only the requirements file first to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code
COPY . .

# The Procfile will run the correct command, so this CMD is just a fallback for local testing.
# Railway will ignore this and use your Procfile instead.
CMD ["gunicorn", "web_server:app", "--bind", "0.0.0.0:$PORT"]
