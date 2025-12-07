# Use the official Python image with Python 3.12 as the base image
FROM python:3.12

# Create a non-root user (Hugging Face Spaces requirement)
RUN useradd -m -u 1000 user

# Set the working directory in the container
WORKDIR /code

# Copy requirements.txt first (change ownership to user)
COPY --chown=user requirements.txt /code/requirements.txt

# Install gunicorn and any other dependencies specified in requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir gunicorn -r /code/requirements.txt

# Copy the rest of the application code (change ownership to user)
COPY --chown=user . /code

# Switch to the non-root user
USER user

# Expose the port (optional but recommended)
EXPOSE 7860

# Run the application with gunicorn
CMD ["gunicorn", "-b", "0.0.0.0:7860", "app:app"]
