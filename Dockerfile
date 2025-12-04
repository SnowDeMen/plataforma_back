# Dockerfile para el backend completo (API + MCP)
# Incluye Chrome y ChromeDriver para automatizacion de TrainingPeaks

FROM python:3.11-slim

# Evitar prompts interactivos
ENV DEBIAN_FRONTEND=noninteractive

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    unzip \
    curl \
    ca-certificates \
    # Dependencias para Chrome
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Instalar Google Chrome (metodo moderno sin apt-key)
RUN mkdir -p /etc/apt/keyrings \
    && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /etc/apt/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Configurar directorio de trabajo
WORKDIR /app

# Copiar requirements e instalar dependencias Python
COPY api/requirements.txt ./api_requirements.txt
COPY mcp/requirements.txt ./mcp_requirements.txt
RUN pip install --no-cache-dir -r api_requirements.txt \
    && pip install --no-cache-dir -r mcp_requirements.txt

# Copiar el codigo de la API
COPY api/ ./

# Copiar el modulo MCP
COPY mcp/ ./mcp/

# Crear directorios necesarios
RUN mkdir -p logs/api_logs logs/session_logs workouts

# Variables de entorno por defecto
ENV HOST=0.0.0.0
ENV PORT=8000
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Exponer puerto
EXPOSE 8000

# Healthcheck (start-period alto para dar tiempo a Chrome/Selenium de inicializar)
HEALTHCHECK --interval=30s --timeout=10s --start-period=180s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Comando de inicio
CMD ["python", "main.py"]
