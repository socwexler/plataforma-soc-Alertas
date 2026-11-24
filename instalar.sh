#!/usr/bin/env bash
# Instalación de la Plataforma SOC en un servidor Linux.
#   ./instalar.sh --revisar   solo revisa el servidor; no cambia nada
#   ./instalar.sh             crea .env (si no existe), compila, levanta y comprueba
# No instala paquetes, no borra datos y no toca otros contenedores.
set -euo pipefail
cd "$(dirname "$0")"

ok()    { printf '  [ok] %s\n' "$1"; }
aviso() { printf '  [!]  %s\n' "$1"; }
falla() { printf '  [X]  %s\n' "$1"; ERRORES=$((ERRORES + 1)); }
ERRORES=0
PUERTO=$(grep -s '^WEB_PORT=' .env | cut -d= -f2 || true); PUERTO=${PUERTO:-${WEB_PORT:-8080}}

echo "== Revisión del servidor"
. /etc/os-release 2>/dev/null && ok "Sistema: ${PRETTY_NAME:-Linux} ($(uname -m))"
[ "$(uname -m)" = "x86_64" ] || aviso "Arquitectura no probada: $(uname -m)"
if command -v docker >/dev/null; then
  ok "$(docker --version)"
  if docker info >/dev/null 2>&1; then
    ok "Docker responde con este usuario"
    if docker compose version >/dev/null 2>&1; then ok "$(docker compose version)"; else falla "Falta el plugin docker compose"; fi
    docker ps --format '       en uso: {{.Names}} {{.Ports}}'
    if docker volume inspect plataforma-soc_pgdata >/dev/null 2>&1; then
      aviso "Ya existe una base de datos de esta plataforma (se conserva)"
      [ -f .env ] || falla "Existe la base pero no el .env: una clave nueva no abriría esa base. Recupere el .env anterior"
    fi
  else
    falla "Docker no responde con este usuario (¿falta sudo o el grupo docker?)"
  fi
else
  falla "Docker no está instalado"
fi
RAM=$(free -m 2>/dev/null | awk '/^Mem:/{print $2}'); LIBRE=$(free -m 2>/dev/null | awk '/^Mem:/{print $7}')
if [ "${RAM:-0}" -ge 3500 ]; then ok "RAM: ${RAM} MB (disponible ${LIBRE} MB)"; else aviso "RAM: ${RAM:-?} MB; se recomiendan 4 GB"; fi
DISCO=$(df -Pm . | awk 'NR==2{print $4}')
if [ "${DISCO:-0}" -ge 15000 ]; then ok "Disco libre: ${DISCO} MB"; else aviso "Disco libre: ${DISCO} MB; se recomiendan 15 GB"; fi
if ss -ltn 2>/dev/null | awk '{print $4}' | grep -qE "[:.]${PUERTO}\$"; then
  if docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^plataforma-soc-web'; then ok "Puerto ${PUERTO}: lo usa esta misma plataforma"
  else falla "Puerto ${PUERTO} ocupado. Ejecute con otro: WEB_PORT=8090 ./instalar.sh"; fi
else ok "Puerto ${PUERTO} libre"; fi
for u in https://registry-1.docker.io/v2/ https://pypi.org/simple/pip/ https://registry.npmjs.org/react http://deb.debian.org/debian/; do
  if curl -s -o /dev/null --max-time 10 "$u"; then ok "Salida a $u"; else aviso "Sin salida a $u (hace falta para compilar)"; fi
done

if [ "${1:-}" = "--revisar" ]; then echo; echo "Solo revisión: no se cambió nada. Errores: ${ERRORES}"; exit 0; fi
if [ "$ERRORES" -gt 0 ]; then echo; echo "Hay ${ERRORES} error(es). No se instaló nada."; exit 1; fi

echo "== Configuración"
if [ -f .env ]; then
  ok ".env existente: se conserva"
else
  aleatoria() { head -c 64 /dev/urandom | sha256sum | cut -c1-"$1"; }
  umask 077
  sed -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(aleatoria 40)|" \
      -e "s|^JWT_SECRET=.*|JWT_SECRET=$(aleatoria 64)|" \
      -e "s|^ADMIN_PASSWORD=.*|ADMIN_PASSWORD=$(aleatoria 20)|" \
      -e "s|^WEB_PORT=.*|WEB_PORT=${PUERTO}|" .env.example > .env.nuevo
  mv .env.nuevo .env
  ok ".env creado con claves aleatorias (solo lo lee este usuario)"
fi
mkdir -p datos

echo "== Compilando y levantando (la primera vez tarda varios minutos)"
docker compose up -d --build

echo "== Comprobaciones"
for _ in $(seq 1 60); do curl -fs -o /dev/null "http://127.0.0.1:${PUERTO}/api/salud" && break; sleep 3; done
if curl -fs "http://127.0.0.1:${PUERTO}/api/salud" >/dev/null; then ok "La aplicación responde"; else falla "La aplicación no responde"; fi
sql() { docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "$1"' _ "$1" 2>/dev/null; }
VER=$(sql 'select version_num from alembic_version' || true)
if [ "$VER" = "0012" ]; then ok "Esquema de base de datos en 0012"; else falla "Esquema: '${VER}' (se esperaba 0012)"; fi
TAC=$(sql 'select count(*) from tacticas' || true)
if [ "$TAC" = "14" ]; then ok "Catálogo MITRE cargado"; else falla "Catálogo MITRE: '${TAC}' (se esperaban 14)"; fi
USU=$(grep '^ADMIN_USUARIO=' .env | cut -d= -f2)
# la clave va por la entrada estándar: no queda en el historial ni en la lista de procesos
COD=$(grep '^ADMIN_PASSWORD=' .env | cut -d= -f2- | tr -d '\n' | curl -s -o /dev/null -w '%{http_code}' \
      --data-urlencode "username=${USU}" --data-urlencode "password@-" "http://127.0.0.1:${PUERTO}/api/auth/login" || true)
if [ "$COD" = "200" ]; then ok "Ingreso del administrador"; else aviso "Ingreso del administrador: ${COD} (normal si ya cambió la clave)"; fi
if docker compose exec -T api python -c "import httpx; httpx.get('http://convertidor:3000/health', timeout=20).raise_for_status()" 2>/dev/null; then
  ok "Convertidor de PDF"; else falla "El convertidor de PDF no responde"; fi

echo
if [ "$ERRORES" -eq 0 ]; then
  echo "Instalación correcta: http://$(hostname -I | awk '{print $1}'):${PUERTO}"
  echo "Usuario: ${USU}. Para ver la clave:  grep ADMIN_PASSWORD $(pwd)/.env"
else
  echo "Terminó con ${ERRORES} error(es). Revise:  docker compose logs --tail 50"; exit 1
fi
