FROM python:3.10-slim

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and startup script
COPY . .

# Make startup script executable
RUN chmod +x startup.sh

# Expose port (Azure App Service defaults to 80/8080 or respects PORT)
EXPOSE 8000

# Start command
CMD ["./startup.sh"]
