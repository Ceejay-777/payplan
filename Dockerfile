# Use the official Python 3.13 image
FROM python:3.13-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies (needed for some python packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the rest of your code
COPY . /app/

# Expose the port Django runs on
EXPOSE 8000

# Default command to run the server
# CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
CMD daphne -b 0.0.0.0 -p $PORT payplan.asgi:application