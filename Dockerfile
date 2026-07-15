# Step 1: Use an official, minimal Python runtime environment
FROM python:3.12-slim

# Step 2: Establish the isolated directory inside the container
WORKDIR /code

# Step 3: Copy only the dependency manifest first to optimize caching
COPY ./requirements.txt /code/requirements.txt

# Step 4: Install packages directly inside the container environment
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Step 5: Copy the local 'app' directory into the container workspace
COPY ./app /code/app

EXPOSE 8000

# Step 6: Command to launch Uvicorn, binding to all network interfaces
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]