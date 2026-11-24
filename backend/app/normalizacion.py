"""Normalización de valores que en el Excel venían escritos de muchas formas."""
import re
import unicodedata

# Catálogo MITRE ATT&CK Enterprise: (id, nombre en español, nombre en inglés)
TACTICAS = [
    ("TA0043", "Reconocimiento", "Reconnaissance"),
    ("TA0042", "Desarrollo de recursos", "Resource Development"),
    ("TA0001", "Acceso inicial", "Initial Access"),
    ("TA0002", "Ejecución", "Execution"),
    ("TA0003", "Persistencia", "Persistence"),
    ("TA0004", "Escalada de privilegios", "Privilege Escalation"),
    ("TA0005", "Evasión de defensa", "Defense Evasion"),
    ("TA0006", "Acceso mediante credenciales", "Credential Access"),
    ("TA0007", "Descubrimiento", "Discovery"),
    ("TA0008", "Movimiento lateral", "Lateral Movement"),
    ("TA0009", "Recopilación", "Collection"),
    ("TA0011", "Comando y control", "Command and Control"),
    ("TA0010", "Exfiltración", "Exfiltration"),
    ("TA0040", "Impacto", "Impact"),
]


def clave(texto: str | None) -> str:
    """Minúsculas, sin tildes, sin signos y con espacios simples (para comparar)."""
    if not texto:
        return ""
    t = unicodedata.normalize("NFD", str(texto))
    t = "".join(c for c in t if unicodedata.category(c) != "Mn").lower()
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return t.strip()


# Variantes encontradas en la bitácora -> id de táctica.
_ALIAS = {
    "reconocimiento": "TA0043", "recononocimiento": "TA0043", "reconnaissance": "TA0043",
    "desarrollo de recursos": "TA0042", "resource development": "TA0042",
    "acceso inicial": "TA0001", "initial access": "TA0001",
    "explotacion de vulnerabilidades conocidas": "TA0001",
    "ejecucion": "TA0002", "execution": "TA0002", "user execution": "TA0002",
    "sistema infectado": "TA0002", "distribucion de malware": "TA0002",
    "persistencia": "TA0003", "persistence": "TA0003",
    "escalada de privilegios": "TA0004", "escalamiento de privilegios": "TA0004",
    "privilege escalation": "TA0004",
    "abuse elevation control mechanism sudo and sudo caching": "TA0004",
    "evasion de defensa": "TA0005", "evasion de defensas": "TA0005", "evasion": "TA0005",
    "defense evasion": "TA0005",
    "acceso mediante credenciales": "TA0006", "acceso a credenciales": "TA0006",
    "credential access": "TA0006", "abuso de autenticacion ntlm": "TA0006",
    "descubrimiento": "TA0007", "discovery": "TA0007",
    "movimiento lateral": "TA0008", "lateral movement": "TA0008",
    "recopilacion": "TA0009", "collection": "TA0009",
    "comando y control": "TA0011", "command and control": "TA0011",
    "exfiltracion": "TA0010", "exfiltration": "TA0010",
    "acceso a datos y potencial exfiltracion": "TA0010",
    "acceso no autorizado de informacion": "TA0009",
    "impacto": "TA0040", "impact": "TA0040", "interrupciones": "TA0040",
}
for _id, _es, _en in TACTICAS:
    _ALIAS.setdefault(clave(_es), _id)
    _ALIAS.setdefault(clave(_en), _id)


def tactica_id(texto: str | None) -> str | None:
    """Devuelve el id MITRE (TA00xx) para una táctica escrita libremente, o None."""
    if not texto:
        return None
    t = str(texto)
    m = re.search(r"TA\d{4}", t, re.I)
    if m:
        return m.group(0).upper()
    k = clave(t)
    if k in _ALIAS:
        return _ALIAS[k]
    # "Discovery (TA0007)", "Persistence (Persistencia)", listas "a,b" o "a / b": se toma la primera
    for parte in re.split(r"[,/(]", t):
        k = clave(parte)
        if k in _ALIAS:
            return _ALIAS[k]
    # Coincidencia por prefijo, p. ej. "acceso no autorizado a objetos privilegiados para reconnaissance..."
    for alias, tid in _ALIAS.items():
        if len(alias) > 8 and alias in k:
            return tid
    return None


def criticidad(texto: str | None) -> tuple[str | None, bool]:
    """Devuelve (criticidad normalizada, es_auditoria)."""
    k = clave(texto)
    if not k:
        return None, False
    auditoria = "auditoria" in k
    if k.startswith("crit"):
        return "Crítica", auditoria
    if k.startswith("alt") or k == "high":
        return "Alta", auditoria
    if k.startswith("med"):
        return "Media", auditoria
    if k.startswith("baj") or k == "low":
        return "Baja", auditoria
    return None, auditoria


def estado(texto: str | None) -> str:
    k = clave(texto)
    if k.startswith("con retro"):
        return "CON_RETRO"
    if k.startswith("cerrad"):
        return "CERRADO"
    return "SIN_RETRO"


def texto(valor) -> str | None:
    """Limpia saltos de línea de Excel (\\r\\n, \\r\\r\\n) y espacios sobrantes."""
    if valor is None:
        return None
    s = str(valor).replace("\r\r\n", "\n").replace("\r\n", "\n").replace("\r", "\n").strip()
    return s or None
