"""Periodos de informe según el día de corte de cada cliente (16 = del 16 al 15, 25 = del 25 al 24, 1 = mes calendario)."""
from datetime import date, timedelta

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]
MESES_CORTOS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def _mes_siguiente(anio: int, mes: int) -> tuple[int, int]:
    return (anio + 1, 1) if mes == 12 else (anio, mes + 1)


def periodo(anio: int, mes: int, dia_corte: int) -> tuple[date, date]:
    """Periodo que empieza en el mes indicado. Ej.: (2026, 10, 16) -> 16-oct-2026 al 15-nov-2026."""
    dia = max(1, min(dia_corte or 1, 28))
    inicio = date(anio, mes, dia)
    a, m = _mes_siguiente(anio, mes)
    return inicio, date(a, m, dia) - timedelta(days=1)


def ultimos(inicio: date, dia_corte: int, n: int = 3) -> list[tuple[date, date]]:
    """Los n periodos que terminan en el periodo de `inicio`, del más antiguo al más reciente."""
    salida = []
    anio, mes = inicio.year, inicio.month
    for _ in range(n):
        salida.append(periodo(anio, mes, dia_corte))
        anio, mes = (anio - 1, 12) if mes == 1 else (anio, mes - 1)
    return list(reversed(salida))


def etiqueta(inicio: date, fin: date) -> str:
    """'16 de octubre al 15 de noviembre de 2026' o 'Octubre de 2026' si es mes calendario."""
    if inicio.day == 1 and fin.month == inicio.month:
        return f"{MESES[inicio.month - 1].capitalize()} de {inicio.year}"
    anio_ini = f" de {inicio.year}" if inicio.year != fin.year else ""
    return f"{inicio.day} de {MESES[inicio.month - 1]}{anio_ini} al {fin.day} de {MESES[fin.month - 1]} de {fin.year}"


def etiqueta_corta(inicio: date, fin: date) -> str:
    """'16 oct – 15 nov' o 'oct 2026' (para ejes de gráficos)."""
    if inicio.day == 1 and fin.month == inicio.month:
        return f"{MESES_CORTOS[inicio.month - 1]} {inicio.year}"
    return f"{inicio.day} {MESES_CORTOS[inicio.month - 1]} – {fin.day} {MESES_CORTOS[fin.month - 1]}"


def nombre_informe(inicio: date) -> str:
    """Mes con el que se nombra el informe: el mes en que empieza el periodo."""
    return f"{MESES[inicio.month - 1].capitalize()} {inicio.year}"
