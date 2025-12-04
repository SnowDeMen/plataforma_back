# 🚀 Guía de Despliegue

Guía completa para desplegar el backend en diferentes entornos.

---

## 📋 Tabla de Contenidos

1. [Preparación](#preparación)
2. [Desarrollo Local](#desarrollo-local)
3. [Staging/Testing](#stagingtesting)
4. [Producción](#producción)
5. [Docker](#docker)
6. [Cloud Providers](#cloud-providers)

---

## 🔧 Preparación

### Requisitos Previos

- Python 3.10 o superior
- pip (gestor de paquetes)
- Base de datos (SQLite para dev, PostgreSQL para prod)
- Cuenta de OpenAI (para AutoGen)

### Variables de Entorno Requeridas

```env
# Esenciales
APP_NAME="Sistema de Agentes AutoGen"
SECRET_KEY=<generar-clave-segura>
OPENAI_API_KEY=<tu-api-key>

# Base de datos
DATABASE_URL=<url-de-tu-base-de-datos>

# Opcional pero recomendado
ENVIRONMENT=production
DEBUG=False
LOG_LEVEL=INFO
```

### Generar SECRET_KEY

```bash
# Python
python -c "import secrets; print(secrets.token_urlsafe(32))"

# OpenSSL
openssl rand -base64 32
```

---

## 💻 Desarrollo Local

### Opción 1: Entorno Virtual (Recomendado)

```bash
# 1. Clonar repositorio
git clone <url-repositorio>
cd generacion_entrenamientos

# 2. Crear entorno virtual
python -m venv venv

# 3. Activar entorno virtual
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# 4. Instalar dependencias
pip install -r requirements.txt

# 5. Configurar variables de entorno
cp .env.example .env
# Editar .env con tus valores

# 6. Inicializar base de datos
python scripts/init_db.py

# 7. Ejecutar servidor
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Opción 2: Sin Entorno Virtual (No Recomendado)

```bash
pip install -r requirements.txt
cp .env.example .env
python scripts/init_db.py
uvicorn main:app --reload
```

### Verificar Instalación

```bash
# Health check
curl http://localhost:8000/health

# Documentación
# Abrir en navegador: http://localhost:8000/docs
```

---

## 🧪 Staging/Testing

### Configuración

```bash
# .env para staging
ENVIRONMENT=staging
DEBUG=False
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db_staging
LOG_LEVEL=INFO
```

### Despliegue

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Configurar variables de entorno
export $(cat .env | xargs)  # Linux/Mac
# o configurar en el servidor

# 3. Inicializar base de datos
python scripts/init_db.py

# 4. Ejecutar con Gunicorn + Uvicorn
gunicorn main:app \
  --workers 2 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile - \
  --error-logfile -
```

### Testing en Staging

```bash
# Ejecutar todos los tests
pytest

# Tests de integración
pytest tests/integration/

# Tests E2E
pytest tests/e2e/
```

---

## 🏭 Producción

### Configuración Recomendada

```env
# .env para producción
APP_NAME="Sistema de Agentes AutoGen"
APP_VERSION="1.0.0"
ENVIRONMENT=production
DEBUG=False

# Servidor
HOST=0.0.0.0
PORT=8000

# Base de datos PostgreSQL
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/dbname

# Seguridad (IMPORTANTE: Cambiar estos valores)
SECRET_KEY=<generar-clave-segura-de-32-caracteres>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# CORS (ajustar según tu frontend)
CORS_ORIGINS=["https://tu-dominio.com"]

# AutoGen
OPENAI_API_KEY=<tu-api-key-de-produccion>
AUTOGEN_MODEL=gpt-4
AUTOGEN_TEMPERATURE=0.7
AUTOGEN_MAX_TOKENS=2000

# Logging
LOG_LEVEL=WARNING
LOG_FILE=/var/log/autogen-backend/app.log

# Rate limiting
RATE_LIMIT_PER_MINUTE=60
```

### Instalación en Servidor

```bash
# 1. Actualizar sistema
sudo apt update && sudo apt upgrade -y

# 2. Instalar Python 3.10+
sudo apt install python3.10 python3.10-venv python3-pip -y

# 3. Crear usuario para la aplicación
sudo useradd -m -s /bin/bash autogen
sudo su - autogen

# 4. Clonar repositorio
git clone <url-repositorio>
cd generacion_entrenamientos

# 5. Crear entorno virtual
python3.10 -m venv venv
source venv/bin/activate

# 6. Instalar dependencias
pip install -r requirements.txt

# 7. Configurar variables de entorno
nano .env
# Copiar y editar valores de producción

# 8. Crear directorios necesarios
mkdir -p logs

# 9. Inicializar base de datos
python scripts/init_db.py
```

### Ejecutar con Systemd

Crear archivo de servicio: `/etc/systemd/system/autogen-backend.service`

```ini
[Unit]
Description=AutoGen Backend API
After=network.target

[Service]
Type=notify
User=autogen
Group=autogen
WorkingDirectory=/home/autogen/generacion_entrenamientos
Environment="PATH=/home/autogen/generacion_entrenamientos/venv/bin"
ExecStart=/home/autogen/generacion_entrenamientos/venv/bin/gunicorn main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --access-logfile /var/log/autogen-backend/access.log \
    --error-logfile /var/log/autogen-backend/error.log \
    --log-level warning

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Activar servicio:

```bash
# Recargar systemd
sudo systemctl daemon-reload

# Iniciar servicio
sudo systemctl start autogen-backend

# Habilitar inicio automático
sudo systemctl enable autogen-backend

# Ver estado
sudo systemctl status autogen-backend

# Ver logs
sudo journalctl -u autogen-backend -f
```

### Nginx como Reverse Proxy

Configuración de Nginx: `/etc/nginx/sites-available/autogen-backend`

```nginx
server {
    listen 80;
    server_name tu-dominio.com;

    # Redirigir a HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name tu-dominio.com;

    # Certificados SSL (usar Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/tu-dominio.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/tu-dominio.com/privkey.pem;

    # Configuración SSL
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Logs
    access_log /var/log/nginx/autogen-backend-access.log;
    error_log /var/log/nginx/autogen-backend-error.log;

    # Proxy a la aplicación
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # WebSocket support (para futuro)
    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

Activar configuración:

```bash
# Crear enlace simbólico
sudo ln -s /etc/nginx/sites-available/autogen-backend /etc/nginx/sites-enabled/

# Verificar configuración
sudo nginx -t

# Recargar Nginx
sudo systemctl reload nginx
```

### SSL con Let's Encrypt

```bash
# Instalar Certbot
sudo apt install certbot python3-certbot-nginx -y

# Obtener certificado
sudo certbot --nginx -d tu-dominio.com

# Renovación automática (ya configurada)
sudo certbot renew --dry-run
```

---

## 🐳 Docker

### Dockerfile

Crear `Dockerfile` en la raíz del proyecto:

```dockerfile
FROM python:3.10-slim

# Variables de entorno
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Directorio de trabajo
WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements
COPY requirements.txt .

# Instalar dependencias Python
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copiar código
COPY . .

# Crear usuario no-root
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Exponer puerto
EXPOSE 8000

# Comando de inicio
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose

Crear `docker-compose.yml`:

```yaml
version: '3.8'

services:
  # Base de datos PostgreSQL
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: autogen_db
      POSTGRES_USER: autogen_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U autogen_user"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Backend API
  api:
    build: .
    environment:
      DATABASE_URL: postgresql+asyncpg://autogen_user:${DB_PASSWORD}@db:5432/autogen_db
      SECRET_KEY: ${SECRET_KEY}
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      ENVIRONMENT: production
      DEBUG: "False"
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - ./logs:/app/logs
    restart: unless-stopped

volumes:
  postgres_data:
```

### Comandos Docker

```bash
# Construir imagen
docker build -t autogen-backend .

# Ejecutar contenedor
docker run -d \
  --name autogen-backend \
  -p 8000:8000 \
  --env-file .env \
  autogen-backend

# Con Docker Compose
docker-compose up -d

# Ver logs
docker-compose logs -f api

# Detener
docker-compose down

# Reconstruir
docker-compose up -d --build
```

---

## ☁️ Cloud Providers

### AWS (EC2 + RDS)

#### 1. Crear RDS (PostgreSQL)

```bash
# Desde AWS Console o CLI
aws rds create-db-instance \
  --db-instance-identifier autogen-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --master-username admin \
  --master-user-password <password> \
  --allocated-storage 20
```

#### 2. Crear EC2

```bash
# Lanzar instancia EC2 (Ubuntu 22.04)
# Configurar Security Group:
# - Puerto 22 (SSH)
# - Puerto 80 (HTTP)
# - Puerto 443 (HTTPS)

# Conectar por SSH
ssh -i tu-clave.pem ubuntu@<ip-publica>

# Seguir pasos de "Producción" arriba
```

#### 3. Configurar

```bash
# Instalar dependencias
sudo apt update
sudo apt install python3.10 python3-pip nginx -y

# Clonar y configurar proyecto
# ... (ver sección Producción)

# Configurar DATABASE_URL con endpoint de RDS
DATABASE_URL=postgresql+asyncpg://admin:password@<rds-endpoint>:5432/autogen_db
```

### Heroku

```bash
# 1. Instalar Heroku CLI
curl https://cli-assets.heroku.com/install.sh | sh

# 2. Login
heroku login

# 3. Crear app
heroku create tu-app-autogen

# 4. Agregar PostgreSQL
heroku addons:create heroku-postgresql:mini

# 5. Configurar variables de entorno
heroku config:set SECRET_KEY=<tu-secret-key>
heroku config:set OPENAI_API_KEY=<tu-api-key>
heroku config:set ENVIRONMENT=production

# 6. Crear Procfile
echo "web: uvicorn main:app --host 0.0.0.0 --port \$PORT" > Procfile

# 7. Deploy
git push heroku main

# 8. Ver logs
heroku logs --tail
```

### DigitalOcean (App Platform)

```bash
# 1. Crear app.yaml
cat > app.yaml << EOF
name: autogen-backend
services:
- name: api
  github:
    repo: tu-usuario/tu-repo
    branch: main
  build_command: pip install -r requirements.txt
  run_command: uvicorn main:app --host 0.0.0.0 --port 8080
  environment_slug: python
  instance_count: 1
  instance_size_slug: basic-xxs
  envs:
  - key: SECRET_KEY
    value: \${SECRET_KEY}
  - key: OPENAI_API_KEY
    value: \${OPENAI_API_KEY}
  - key: DATABASE_URL
    value: \${db.DATABASE_URL}
databases:
- name: db
  engine: PG
  version: "15"
EOF

# 2. Deploy desde CLI o Web UI
doctl apps create --spec app.yaml
```

### Railway

```bash
# 1. Instalar Railway CLI
npm install -g @railway/cli

# 2. Login
railway login

# 3. Inicializar proyecto
railway init

# 4. Agregar PostgreSQL
railway add

# 5. Configurar variables
railway variables set SECRET_KEY=<tu-secret-key>
railway variables set OPENAI_API_KEY=<tu-api-key>

# 6. Deploy
railway up
```

---

## 🔍 Monitoreo y Logs

### Logs en Producción

```bash
# Ver logs del servicio
sudo journalctl -u autogen-backend -f

# Ver logs de Nginx
sudo tail -f /var/log/nginx/autogen-backend-access.log
sudo tail -f /var/log/nginx/autogen-backend-error.log

# Ver logs de la aplicación
tail -f logs/app.log
```

### Monitoreo con Prometheus (Opcional)

```bash
# Instalar prometheus-fastapi-instrumentator
pip install prometheus-fastapi-instrumentator

# Agregar a main.py
from prometheus_fastapi_instrumentator import Instrumentator

Instrumentator().instrument(app).expose(app)
```

---

## 🔄 Actualización y Mantenimiento

### Actualizar Aplicación

```bash
# 1. Conectar al servidor
ssh usuario@servidor

# 2. Ir al directorio
cd /home/autogen/generacion_entrenamientos

# 3. Activar entorno virtual
source venv/bin/activate

# 4. Obtener últimos cambios
git pull origin main

# 5. Actualizar dependencias (si es necesario)
pip install -r requirements.txt

# 6. Ejecutar migraciones (si hay)
alembic upgrade head

# 7. Reiniciar servicio
sudo systemctl restart autogen-backend

# 8. Verificar
sudo systemctl status autogen-backend
```

### Backup de Base de Datos

```bash
# PostgreSQL
pg_dump -h localhost -U autogen_user autogen_db > backup_$(date +%Y%m%d).sql

# Restaurar
psql -h localhost -U autogen_user autogen_db < backup_20240101.sql
```

---

## ✅ Checklist de Despliegue

### Pre-Despliegue
- [ ] Variables de entorno configuradas
- [ ] SECRET_KEY generada y segura
- [ ] Base de datos creada
- [ ] CORS configurado correctamente
- [ ] Tests pasando
- [ ] Documentación actualizada

### Despliegue
- [ ] Código desplegado
- [ ] Dependencias instaladas
- [ ] Base de datos inicializada
- [ ] Servicio iniciado
- [ ] Nginx configurado (si aplica)
- [ ] SSL configurado

### Post-Despliegue
- [ ] Health check funcionando
- [ ] API respondiendo correctamente
- [ ] Logs configurados
- [ ] Monitoreo activo
- [ ] Backup configurado
- [ ] Documentación de producción actualizada

---

## 🆘 Troubleshooting

### Error: "ModuleNotFoundError"
```bash
# Verificar entorno virtual activado
which python
# Debe mostrar ruta del venv

# Reinstalar dependencias
pip install -r requirements.txt
```

### Error: "Database connection failed"
```bash
# Verificar DATABASE_URL
echo $DATABASE_URL

# Probar conexión
psql $DATABASE_URL

# Verificar que PostgreSQL esté corriendo
sudo systemctl status postgresql
```

### Error: "Port already in use"
```bash
# Encontrar proceso usando el puerto
sudo lsof -i :8000

# Matar proceso
sudo kill -9 <PID>
```

### Servicio no inicia
```bash
# Ver logs detallados
sudo journalctl -u autogen-backend -n 100 --no-pager

# Verificar permisos
ls -la /home/autogen/generacion_entrenamientos

# Verificar configuración
sudo systemctl cat autogen-backend
```

---

## 📞 Soporte

Para problemas de despliegue:
1. Revisar logs del servicio
2. Verificar configuración de variables de entorno
3. Consultar documentación de tu proveedor cloud
4. Revisar la sección de troubleshooting

---

¡Feliz despliegue! 🚀

