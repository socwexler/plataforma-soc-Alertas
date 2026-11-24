#!/usr/bin/env bash
# Prueba completa en un entorno Docker aparte (proyecto soc-prueba, puerto 8099). No toca la plataforma local.
#   bash pruebas/correr.sh            instala una copia limpia, corre todo y la elimina
#   bash pruebas/correr.sh --dejar    la deja encendida en http://127.0.0.1:8099 para verla
set -u
# Necesita los insumos reales fuera del repositorio: bitácora, CSV y control.json (carpeta superior o SOC_INSUMOS).
P=$(cd "$(dirname "$0")" && pwd); C=$(dirname "$P"); R=${SOC_INSUMOS:-$(dirname "$C")}; PUERTO=8099
XLSX=$(ls "$R"/BITACORA*.xlsx 2>/dev/null | head -1)
[ -n "$XLSX" ] && [ -f "$R/control.json" ] || { echo "Faltan la bitácora o control.json en $R (o defina SOC_INSUMOS)"; exit 1; }
if [ -n "$(docker ps -aq --filter name=soc-prueba-)" ]; then echo "Ya existe soc-prueba. Elimínelo con: docker compose -p soc-prueba down -v"; exit 1; fi
T=$(cygpath -u "${TEMP:-/tmp}" 2>/dev/null || echo "${TMPDIR:-/tmp}"); D=$(mktemp -d "$T/soc_prueba_XXXXXX")
limpiar() {
  if [ "${1:-}" = "--dejar" ]; then echo "Queda en http://127.0.0.1:$PUERTO (copia en $D)"; return; fi
  docker rm -f soc-prueba-sim >/dev/null 2>&1
  docker compose -p soc-prueba down -v >/dev/null 2>&1
  case "$D" in */soc_prueba_??????) rm -rf "$D";; esac
}
trap 'limpiar "${DEJAR:-}"' EXIT
DEJAR=${1:-}

mkdir "$D/plataforma-soc"; tar --exclude='./.env' --exclude='./.git' --exclude='./pruebas' --exclude='__pycache__' --exclude='node_modules' -C "$C" -cf - . | tar xf - -C "$D/plataforma-soc"
cp "$XLSX" "$D/b.xlsx"; mkdir -p "$D/sal" "$D/plataforma-soc/datos"; [ ! -f "$R/clientes.json" ] || cp "$R/clientes.json" "$D/plataforma-soc/datos/"
cd "$D/plataforma-soc" || exit 1
sed -i 's/^name: plataforma-soc/name: soc-prueba/' docker-compose.yml
sed -i 's/plataforma-soc_pgdata/soc-prueba_pgdata/; s/\^plataforma-soc-web/^soc-prueba-web/' instalar.sh
free() { printf 'Mem: 8000 1 1 1 1 5000\n'; }; ss() { :; }; hostname() { echo 127.0.0.1; }; export -f free ss hostname
echo "== Instalación limpia"
WEB_PORT=$PUERTO bash instalar.sh > "$D/instalar.log" 2>&1 || { grep -E '\[X\]|rror' "$D/instalar.log" | tail; echo "FALLÓ la instalación"; exit 1; }
grep -E 'Esquema|correcta' "$D/instalar.log"

# rutas en formato de Windows para node
w() { cygpath -m "$1" 2>/dev/null || echo "$1"; }
E=$(w "$D/plataforma-soc/.env"); FALLOS=0; export SOC_CONTROL; SOC_CONTROL=$(w "$R/control.json")
prueba() { # nombre, argumentos…
  echo "== $1"; local s; s=$(node "$(w "$P")/$1.mjs" "$PUERTO" "$E" "${@:2}" 2>&1); echo "$s" | grep -E '\[X\]|FALLOS|TODO BIEN|totales|rror' | cut -c1-300
  echo "$s" | grep -q 'TODO BIEN' || FALLOS=$((FALLOS + 1))
}
prueba e2e "$(w "$D/b.xlsx")" "$(w "$R")"          # importación e informes: va primero, exige base vacía
prueba e2e_pres "$(w "$P")" "$(w "$D/sal")"        # logos, boletines y presentación
prueba e2e_anular "$(w "$D/b.xlsx")"
prueba e2e_baja
prueba e2e_adj "$(w "$P")" "$(w "$D/sal")"
prueba e2e_estado "$(w "$P")"
prueba e2e_roles
prueba e2e_correo "$(w "$D/sal")"
# simuladores de GLPI, FortiSIEM y correo en la red de la copia; no salen a Internet
docker run -d --rm --name soc-prueba-sim --network soc-prueba_default --network-alias sim -v "$(w "$P/simuladores.py"):/s.py:ro" soc-prueba-api python -u //s.py >/dev/null && sleep 3
MSYS_NO_PATHCONV=1 prueba e2e_config
echo; if [ "$FALLOS" = 0 ]; then echo "PRUEBAS CORRECTAS"; else echo "PRUEBAS CON FALLOS: $FALLOS"; exit 1; fi
