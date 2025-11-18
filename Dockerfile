FROM python:3.13-slim

# Setăm directorul de lucru
WORKDIR /app

# Instalăm dependențele de sistem necesare pentru mysqlclient
RUN apt-get update && apt-get install -y \
    build-essential \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copiem requirements și le instalăm
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiem restul proiectului
COPY . .

# Comanda default
CMD ["gunicorn", "manage:app", "--bind", "0.0.0.0:8000"]
