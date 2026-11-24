"""Ubicación de los países en el mapa de la presentación (latitud, longitud del centro del país)."""
from ..normalizacion import clave

ORIGEN = {"pais": "Colombia", "lat": 4.6, "lon": -74.1}

_COORD = {
    # América
    "Estados Unidos": (39.8, -98.6), "Canadá": (56.0, -106.0), "México": (23.6, -102.5), "Guatemala": (15.5, -90.3),
    "Belice": (17.2, -88.6), "Honduras": (14.8, -86.6), "El Salvador": (13.7, -88.9), "Nicaragua": (12.9, -85.0),
    "Costa Rica": (9.8, -84.0), "Panamá": (8.5, -80.1), "Cuba": (21.5, -79.0), "Jamaica": (18.1, -77.3), "Haití": (19.0, -72.6),
    "República Dominicana": (18.8, -70.2), "Puerto Rico": (18.2, -66.4), "Bahamas": (24.7, -77.8), "Barbados": (13.2, -59.5),
    "Trinidad y Tobago": (10.5, -61.3), "Antigua y Barbuda": (17.1, -61.8), "Curazao": (12.2, -69.0), "Aruba": (12.5, -70.0),
    "Venezuela": (7.1, -66.2), "Ecuador": (-1.5, -78.4), "Perú": (-9.6, -75.0), "Bolivia": (-16.7, -64.7), "Brasil": (-10.8, -53.0),
    "Paraguay": (-23.2, -58.4), "Uruguay": (-32.8, -56.0), "Argentina": (-35.4, -65.2), "Chile": (-33.5, -70.7),
    "Guyana": (4.8, -58.9), "Surinam": (4.1, -55.9), "Guayana Francesa": (3.9, -53.1), "Bermudas": (32.3, -64.8),
    "Islas Caimán": (19.3, -81.3), "Islas Vírgenes Británicas": (18.4, -64.6), "Islas Vírgenes de los Estados Unidos": (18.3, -64.9),
    "Dominica": (15.4, -61.4), "Santa Lucía": (13.9, -61.0), "Granada": (12.1, -61.7), "Martinica": (14.6, -61.0),
    "Guadalupe": (16.2, -61.5), "Groenlandia": (65.5, -42.0), "Colombia": (4.6, -74.1),
    # Europa
    "Reino Unido": (53.8, -1.9), "Irlanda": (53.2, -8.0), "Francia": (46.6, 2.5), "España": (40.2, -3.6), "Portugal": (39.6, -8.0),
    "Alemania": (51.1, 10.4), "Países Bajos": (52.2, 5.5), "Bélgica": (50.6, 4.7), "Luxemburgo": (49.8, 6.1), "Suiza": (46.8, 8.2),
    "Austria": (47.6, 14.1), "Italia": (42.8, 12.6), "Malta": (35.9, 14.4), "Mónaco": (43.7, 7.4), "Andorra": (42.5, 1.6),
    "San Marino": (43.9, 12.5), "Liechtenstein": (47.2, 9.6), "Dinamarca": (56.0, 9.6), "Noruega": (61.2, 9.0), "Suecia": (62.0, 15.5),
    "Finlandia": (63.5, 26.2), "Islandia": (64.9, -18.6), "Estonia": (58.7, 25.5), "Letonia": (56.9, 24.9), "Lituania": (55.3, 23.9),
    "Polonia": (52.1, 19.4), "República Checa": (49.8, 15.3), "Chequia": (49.8, 15.3), "Eslovaquia": (48.7, 19.5), "Hungría": (47.2, 19.4),
    "Rumania": (45.9, 25.0), "Bulgaria": (42.8, 25.2), "Grecia": (39.1, 22.9), "Serbia": (44.2, 20.8), "Croacia": (45.1, 15.6),
    "Eslovenia": (46.1, 14.8), "Bosnia y Herzegovina": (44.2, 17.8), "Montenegro": (42.8, 19.3), "Albania": (41.1, 20.0),
    "Macedonia del Norte": (41.6, 21.7), "Kosovo": (42.6, 20.9), "Moldavia": (47.2, 28.5), "Ucrania": (49.0, 31.4),
    "Bielorrusia": (53.5, 28.0), "Rusia": (58.0, 60.0), "Turquía": (39.1, 35.2), "Chipre": (35.0, 33.2), "Gibraltar": (36.1, -5.3),
    "Jersey": (49.2, -2.1), "Guernsey": (49.5, -2.6), "Isla de Man": (54.2, -4.5), "Islas Feroe": (62.0, -6.9),
    # Asia
    "China": (35.5, 103.8), "Hong Kong": (22.3, 114.2), "Macao": (22.2, 113.5), "Taiwán": (23.7, 121.0), "Japón": (36.5, 138.3),
    "Corea del Sur": (36.4, 127.9), "Corea del Norte": (40.2, 127.2), "Mongolia": (46.8, 103.1), "India": (22.5, 79.5),
    "Pakistán": (29.9, 69.3), "Bangladés": (23.8, 90.3), "Nepal": (28.2, 84.0), "Bután": (27.4, 90.4), "Sri Lanka": (7.7, 80.7),
    "Maldivas": (3.2, 73.2), "Birmania": (21.2, 96.5), "Tailandia": (15.1, 101.0), "Laos": (18.5, 103.8), "Camboya": (12.6, 105.0),
    "Vietnam": (15.9, 106.6), "Malasia": (4.1, 102.2), "Singapur": (1.35, 103.8), "Indonesia": (-2.5, 117.8), "Filipinas": (12.2, 122.0),
    "Brunéi": (4.5, 114.7), "Timor Oriental": (-8.8, 125.8), "Kazajistán": (48.2, 67.0), "Uzbekistán": (41.6, 63.5),
    "Turkmenistán": (39.0, 59.5), "Kirguistán": (41.4, 74.6), "Tayikistán": (38.8, 71.0), "Afganistán": (33.8, 66.0),
    "Irán": (32.5, 54.3), "Irak": (33.0, 43.7), "Siria": (35.0, 38.5), "Líbano": (33.9, 35.9), "Israel": (31.4, 35.0),
    "Palestina": (31.9, 35.2), "Jordania": (31.2, 36.8), "Arabia Saudita": (24.1, 44.5), "Kuwait": (29.3, 47.6), "Baréin": (26.0, 50.5),
    "Catar": (25.3, 51.2), "Emiratos Árabes Unidos": (23.9, 54.3), "Omán": (20.6, 56.1), "Yemen": (15.9, 47.6),
    "Armenia": (40.3, 44.9), "Georgia": (42.2, 43.5), "Azerbaiyán": (40.3, 47.7),
    # África
    "Egipto": (26.5, 29.9), "Libia": (27.0, 18.0), "Túnez": (34.1, 9.6), "Argelia": (28.2, 2.6), "Marruecos": (31.9, -6.3),
    "Mauritania": (20.3, -10.3), "Malí": (17.4, -3.5), "Níger": (17.4, 9.4), "Chad": (15.4, 18.6), "Sudán": (16.0, 30.0),
    "Sudán del Sur": (7.3, 30.2), "Etiopía": (8.6, 39.6), "Eritrea": (15.4, 38.8), "Yibuti": (11.7, 42.6), "Somalia": (5.4, 46.0),
    "Kenia": (0.6, 37.8), "Uganda": (1.3, 32.4), "Ruanda": (-2.0, 29.9), "Burundi": (-3.4, 29.9), "Tanzania": (-6.3, 34.8),
    "Senegal": (14.4, -14.5), "Gambia": (13.4, -15.4), "Guinea": (10.4, -10.9), "Guinea-Bisáu": (12.0, -14.9), "Sierra Leona": (8.6, -11.8),
    "Liberia": (6.4, -9.3), "Costa de Marfil": (7.6, -5.6), "Burkina Faso": (12.3, -1.8), "Ghana": (7.9, -1.2), "Togo": (8.5, 1.0),
    "Benín": (9.6, 2.3), "Nigeria": (9.6, 8.1), "Camerún": (5.7, 12.7), "Gabón": (-0.6, 11.8), "Congo": (-0.8, 15.2),
    "República Democrática del Congo": (-2.9, 23.6), "República Centroafricana": (6.6, 20.5), "Guinea Ecuatorial": (1.7, 10.3),
    "Angola": (-12.3, 17.5), "Zambia": (-13.5, 27.8), "Malaui": (-13.2, 34.3), "Mozambique": (-17.3, 35.5), "Zimbabue": (-19.0, 29.9),
    "Botsuana": (-22.2, 23.8), "Namibia": (-22.1, 17.2), "Sudáfrica": (-29.0, 25.1), "Lesoto": (-29.6, 28.2), "Esuatini": (-26.6, 31.5),
    "Madagascar": (-19.4, 46.7), "Mauricio": (-20.3, 57.6), "Seychelles": (-4.7, 55.5), "Mayotte": (-12.8, 45.2), "Reunión": (-21.1, 55.5),
    "Comoras": (-11.9, 43.9), "Cabo Verde": (15.1, -23.6),
    # Oceanía
    "Australia": (-25.7, 134.5), "Nueva Zelanda": (-41.8, 172.8), "Papúa Nueva Guinea": (-6.5, 145.2), "Fiyi": (-17.8, 178.0),
    "Nueva Caledonia": (-21.3, 165.7), "Guam": (13.4, 144.8), "Polinesia Francesa": (-17.7, -149.4), "Samoa": (-13.8, -172.1),
}
# Como los entrega FortiSIEM (en inglés) cuando no están traducidos en paises.py
_ALIAS = {
    "aruba": "Aruba", "guyana": "Guyana", "suriname": "Surinam", "french guiana": "Guayana Francesa", "bermuda": "Bermudas",
    "cayman islands": "Islas Caimán", "virgin islands british": "Islas Vírgenes Británicas", "british virgin islands": "Islas Vírgenes Británicas",
    "virgin islands u s": "Islas Vírgenes de los Estados Unidos", "dominica": "Dominica", "saint lucia": "Santa Lucía", "grenada": "Granada",
    "martinique": "Martinica", "guadeloupe": "Guadalupe", "greenland": "Groenlandia", "macao": "Macao", "macau": "Macao", "nepal": "Nepal",
    "bhutan": "Bután", "sri lanka": "Sri Lanka", "maldives": "Maldivas", "myanmar": "Birmania", "laos": "Laos",
    "lao people s democratic republic": "Laos", "brunei darussalam": "Brunéi", "brunei": "Brunéi", "timor leste": "Timor Oriental",
    "turkmenistan": "Turkmenistán", "kyrgyzstan": "Kirguistán", "tajikistan": "Tayikistán", "afghanistan": "Afganistán",
    "syrian arab republic": "Siria", "montenegro": "Montenegro", "kosovo": "Kosovo", "andorra": "Andorra", "san marino": "San Marino",
    "liechtenstein": "Liechtenstein", "macedonia": "Macedonia del Norte", "mauritania": "Mauritania", "mali": "Malí", "niger": "Níger",
    "chad": "Chad", "eritrea": "Eritrea", "djibouti": "Yibuti", "somalia": "Somalia", "uganda": "Uganda", "burundi": "Burundi",
    "tanzania": "Tanzania", "tanzania united republic of": "Tanzania", "gambia": "Gambia", "guinea": "Guinea", "sierra leone": "Sierra Leona",
    "liberia": "Liberia", "ivory coast": "Costa de Marfil", "cote d ivoire": "Costa de Marfil", "burkina faso": "Burkina Faso",
    "togo": "Togo", "benin": "Benín", "cameroon": "Camerún", "gabon": "Gabón", "congo": "Congo",
    "congo the democratic republic of the": "República Democrática del Congo", "democratic republic of the congo": "República Democrática del Congo",
    "central african republic": "República Centroafricana", "equatorial guinea": "Guinea Ecuatorial", "angola": "Angola", "zambia": "Zambia",
    "malawi": "Malaui", "mozambique": "Mozambique", "botswana": "Botsuana", "namibia": "Namibia", "lesotho": "Lesoto",
    "swaziland": "Esuatini", "eswatini": "Esuatini", "madagascar": "Madagascar", "reunion": "Reunión", "comoros": "Comoras",
    "cape verde": "Cabo Verde", "cabo verde": "Cabo Verde", "papua new guinea": "Papúa Nueva Guinea", "fiji": "Fiyi",
    "new caledonia": "Nueva Caledonia", "guam": "Guam", "french polynesia": "Polinesia Francesa", "samoa": "Samoa",
    "bolivia plurinational state of": "Bolivia", "venezuela bolivarian republic of": "Venezuela", "moldova republic of": "Moldavia",
    "palestinian territory occupied": "Palestina", "palestine state of": "Palestina", "taiwan province of china": "Taiwán",
    "macedonia the former yugoslav republic of": "Macedonia del Norte", "the netherlands": "Países Bajos",
}


def _normal(s: str) -> str:
    return " ".join("".join(ch if ch.isalnum() else " " for ch in clave(s)).split())


_INDICE = {_normal(k): (k, v) for k, v in _COORD.items()}
_INDICE |= {_normal(a): (es, _COORD[es]) for a, es in _ALIAS.items()}


def ubicar(paises: list[dict]) -> tuple[list[dict], list[str]]:
    """Agrega lat/lon a [{pais, total}]. Devuelve (ubicados, nombres sin ubicación conocida)."""
    ok, sin = [], []
    for p in paises:
        r = _INDICE.get(_normal(p["pais"]))
        if r:
            ok.append({"pais": r[0], "total": p["total"], "lat": r[1][0], "lon": r[1][1]})
        else:
            sin.append(p["pais"])
    return ok, sin
