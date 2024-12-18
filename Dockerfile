FROM python:3.9-slim

WORKDIR /app

# Copy the project files into the container
COPY . .

# Install system dependencies and create a virtual environment
RUN apt-get update && \
    apt-get install -y gcc libpq-dev && \
    python -m venv venv && \
    venv/bin/pip install --upgrade pip && \
    venv/bin/pip install -r requirements.txt || \
    (tail -n 10 /var/log/apt/term.log && tail -n 10 /var/log/apt/history.log)


# Set the environment variable to use the virtual environment
ENV PATH="/app/venv/bin:$PATH"

# Command to run the app using gunicorn
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:$PORT"]



