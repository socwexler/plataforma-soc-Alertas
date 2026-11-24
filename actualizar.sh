#!/usr/bin/env bash
# Instala o actualiza la Plataforma SOC desde el paquete, conservando claves (.env) y base de datos.
#   sudo bash actualizar.sh <paquete.tar.gz> <sha256>
# Antes de cambiar nada: verifica el paquete y respalda la base. La carpeta anterior se guarda, no se borra.
set -euo pipefail
PAQ=${1:?falta el paquete}; SHA=${2:?falta el sha256}
BASE=${BASE:-/opt}; DEST="$BASE/plataforma-soc"; SELLO=$(date +%Y%m%d_%H%M%S); NUEVA="$BASE/plataforma-soc.nueva"
para() { echo "  [X]  $1"; echo "No se cambió nada."; exit 1; }

echo "== Estado actual"
echo "$SHA  $PAQ" | sha256sum -c --status - || para "El paquete no es el esperado: $(sha256sum "$PAQ" | cut -c1-16)…"
echo "  [ok] Paquete verificado"
for d in "$BASE"/plataforma-soc*; do
  if [ -d "$d" ]; then printf '       %s  esquema %s  .env: %s\n' "$d" "$(grep -oE '"00[0-9]{2}"' "$d/instalar.sh" 2>/dev/null | head -1 || true)" "$([ -f "$d/.env" ] && echo si || echo no)"; fi
done
docker ps -a --filter name=plataforma-soc --format '       {{.Names}}: {{.Status}}'
HAY_BASE=no; if docker volume inspect plataforma-soc_pgdata >/dev/null 2>&1; then HAY_BASE=si; fi
echo "       Base de datos existente: $HAY_BASE"

# Claves actuales: las de la carpeta en uso o, si no las tiene, las de la anterior más reciente
ENV=""
if [ -f "$DEST/.env" ]; then ENV="$DEST/.env"; else ENV=$(ls -t "$BASE"/plataforma-soc*/.env 2>/dev/null | head -1 || true); fi
if [ "$HAY_BASE" = si ]; then
  [ -n "$ENV" ] || para "Existe la base de datos, pero no aparece su .env. Sin él no se puede abrir"
  ORIGEN=$(dirname "$ENV")
  echo "== Respaldo de la base"
  (cd "$ORIGEN" && docker compose up -d db >/dev/null 2>&1) || para "No se pudo levantar la base para respaldarla"
  for i in $(seq 1 30); do docker exec plataforma-soc-db-1 sh -c 'pg_isready -q -U "$POSTGRES_USER"' && break; sleep 2; done
  umask 077; mkdir -p "$BASE/respaldos-soc"; R="$BASE/respaldos-soc/antes_${SELLO}.dump"
  docker exec plataforma-soc-db-1 sh -c 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' > "$R" || para "Falló el respaldo"
  docker exec -i plataforma-soc-db-1 pg_restore -l < "$R" >/dev/null || para "El respaldo no se puede leer"
  echo "  [ok] $R ($(du -h "$R" | cut -f1))"
fi

echo "== Archivos nuevos"
[ ! -e "$NUEVA" ] || mv -T "$NUEVA" "$NUEVA.$SELLO"
umask 022; mkdir "$NUEVA"
tar -xzf "$PAQ" -C "$NUEVA" --strip-components=1 --no-same-owner
[ -x "$NUEVA/instalar.sh" ] || para "El paquete no trae instalar.sh"
if [ -n "$ENV" ]; then (umask 077; cp "$ENV" "$NUEVA/.env"); echo "  [ok] Claves conservadas"; else echo "  [ok] Instalación nueva: se crearán las claves"; fi
if [ -d "$DEST/datos" ]; then cp -a "$DEST/datos" "$NUEVA/"; fi
if [ -d "$DEST" ]; then mv -T "$DEST" "$DEST.anterior_$SELLO"; echo "  [ok] Carpeta anterior guardada en $DEST.anterior_$SELLO"; fi
mv -T "$NUEVA" "$DEST"
cd "$DEST"
exec ./instalar.sh
