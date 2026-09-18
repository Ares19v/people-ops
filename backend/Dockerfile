FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl build-essential && \
    rm -rf /var/lib/apt/lists/*

# Install uv for ultra-fast dependency installation
RUN pip install --no-cache-dir uv

# Copy dependency specifications
COPY pyproject.toml .

# Install dependencies using uv
RUN uv pip install --system -r <(python -c '
import tomllib
with open("pyproject.toml", "rb") as f:
    d = tomllib.load(f)
deps = d["project"]["dependencies"]
print("\n".join(deps))
')

# Copy application source code
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
