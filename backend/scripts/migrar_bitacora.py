"""Importa una bitácora Excel desde la línea de comandos (misma lógica que la página "Importar bitácora").

Uso (dentro del contenedor api):
    python -m scripts.migrar_bitacora /datos/BITACORA.xlsx --simular
    python -m scripts.migrar_bitacora /datos/BITACORA.xlsx                       # solo casos nuevos
    python -m scripts.migrar_bitacora /datos/BITACORA.xlsx --modo actualizar     # nuevos + actualiza importados
    python -m scripts.migrar_bitacora /datos/BITACORA_NOC.xlsx --hoja NOC --solo-casos
"""
import argparse
import sys

from app.db import SessionLocal
from app.importacion import MODOS, ErrorImportacion, importar
from app.main import inicializar


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("archivo")
    ap.add_argument("--hoja", default="BITACORA", help="Hoja con los casos (BITACORA o NOC)")
    ap.add_argument("--servicio", choices=["SOC", "NOC"], help="Servicio por defecto (si no, se deduce de la hoja)")
    ap.add_argument("--modo", choices=MODOS, default="solo_nuevos")
    ap.add_argument("--reemplazar", action="store_true", help="Igual a --modo reemplazar")
    ap.add_argument("--solo-casos", action="store_true", help="No cargar clientes de INFORMACION ni base de conocimiento")
    ap.add_argument("--simular", action="store_true", help="Hace todo y al final deshace (no guarda)")
    a = ap.parse_args()

    inicializar()
    print(f"Leyendo {a.archivo} ...")
    with SessionLocal() as db:
        try:
            r = importar(db, a.archivo, a.hoja, a.servicio, "reemplazar" if a.reemplazar else a.modo,
                         cargar_catalogos=not a.solo_casos)
        except ErrorImportacion as e:
            sys.exit(f"Error: {e}")
        kb = r["base_conocimiento_nuevos"]
        print(f"  Base de conocimiento nueva: {kb['con_plantilla']} con plantilla, {kb['reglas_fortisiem']} reglas FortiSIEM")
        print(f"  Clientes nuevos: {len(r['clientes_nuevos'])} · Analistas nuevos: {len(r['analistas_nuevos'])}")
        for d in r["detalle"]:
            print(f"  {d['total']:>6}  {d['concepto']}")
        print(f"  Siguiente número: {r['siguiente_numero']}")
        if a.simular:
            db.rollback()
            print("Simulación: no se guardó nada.")
        else:
            db.commit()
            print(f"Listo. Casos en la base de datos: {r['total_casos']}")


if __name__ == "__main__":
    main()
