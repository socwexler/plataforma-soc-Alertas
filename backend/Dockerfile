FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/srv MPLCONFIGDIR=/tmp/matplotlib
WORKDIR /srv

# Fuentes corporativas de la plantilla (Lato, Montserrat) para los gráficos de los informes
RUN apt-get update && apt-get install -y --no-install-recommends fontconfig     && rm -rf /var/lib/apt/lists/*
COPY convertidor/fuentes/*.ttf /usr/local/share/fonts/wexler/
RUN fc-cache -f

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY backend/scripts ./scripts
COPY backend/alembic.ini ./
COPY backend/migraciones ./migraciones

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
