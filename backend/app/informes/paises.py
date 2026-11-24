"""Nombres de países en español para los informes (FortiSIEM los entrega en inglés)."""
from ..normalizacion import clave

_ES = {
    "united states": "Estados Unidos", "united kingdom": "Reino Unido", "germany": "Alemania", "france": "Francia",
    "spain": "España", "italy": "Italia", "netherlands": "Países Bajos", "belgium": "Bélgica", "ireland": "Irlanda",
    "portugal": "Portugal", "switzerland": "Suiza", "austria": "Austria", "sweden": "Suecia", "norway": "Noruega",
    "finland": "Finlandia", "denmark": "Dinamarca", "iceland": "Islandia", "poland": "Polonia",
    "czech republic": "República Checa", "czechia": "Chequia", "slovakia": "Eslovaquia", "hungary": "Hungría",
    "romania": "Rumania", "bulgaria": "Bulgaria", "greece": "Grecia", "turkey": "Turquía", "turkiye": "Turquía",
    "ukraine": "Ucrania", "russia": "Rusia", "russian federation": "Rusia", "belarus": "Bielorrusia",
    "lithuania": "Lituania", "latvia": "Letonia", "estonia": "Estonia", "moldova": "Moldavia",
    "republic of moldova": "Moldavia", "serbia": "Serbia", "croatia": "Croacia", "slovenia": "Eslovenia",
    "bosnia and herzegovina": "Bosnia y Herzegovina", "albania": "Albania", "north macedonia": "Macedonia del Norte",
    "luxembourg": "Luxemburgo", "malta": "Malta", "cyprus": "Chipre", "monaco": "Mónaco", "jersey": "Jersey",
    "guernsey": "Guernsey", "isle of man": "Isla de Man", "faroe islands": "Islas Feroe", "gibraltar": "Gibraltar",
    "canada": "Canadá", "mexico": "México", "brazil": "Brasil", "argentina": "Argentina", "chile": "Chile",
    "peru": "Perú", "ecuador": "Ecuador", "venezuela": "Venezuela", "bolivia": "Bolivia", "paraguay": "Paraguay",
    "uruguay": "Uruguay", "panama": "Panamá", "costa rica": "Costa Rica", "guatemala": "Guatemala",
    "honduras": "Honduras", "el salvador": "El Salvador", "nicaragua": "Nicaragua", "cuba": "Cuba",
    "dominican republic": "República Dominicana", "puerto rico": "Puerto Rico", "jamaica": "Jamaica",
    "haiti": "Haití", "trinidad and tobago": "Trinidad y Tobago", "bahamas": "Bahamas", "belize": "Belice",
    "antigua and barbuda": "Antigua y Barbuda", "barbados": "Barbados", "curacao": "Curazao",
    "china": "China", "japan": "Japón", "republic of korea": "Corea del Sur", "korea republic of": "Corea del Sur",
    "south korea": "Corea del Sur", "north korea": "Corea del Norte", "hong kong": "Hong Kong", "taiwan": "Taiwán",
    "singapore": "Singapur", "india": "India", "pakistan": "Pakistán", "bangladesh": "Bangladés",
    "indonesia": "Indonesia", "malaysia": "Malasia", "thailand": "Tailandia", "vietnam": "Vietnam",
    "viet nam": "Vietnam", "philippines": "Filipinas", "cambodia": "Camboya", "mongolia": "Mongolia",
    "kazakhstan": "Kazajistán", "uzbekistan": "Uzbekistán", "armenia": "Armenia", "georgia": "Georgia",
    "azerbaijan": "Azerbaiyán", "iran": "Irán", "iran islamic republic of": "Irán", "iraq": "Irak",
    "israel": "Israel", "palestine": "Palestina", "jordan": "Jordania", "lebanon": "Líbano", "syria": "Siria",
    "saudi arabia": "Arabia Saudita", "united arab emirates": "Emiratos Árabes Unidos", "qatar": "Catar",
    "kuwait": "Kuwait", "bahrain": "Baréin", "oman": "Omán", "yemen": "Yemen", "egypt": "Egipto",
    "morocco": "Marruecos", "algeria": "Argelia", "tunisia": "Túnez", "libya": "Libia", "nigeria": "Nigeria",
    "south africa": "Sudáfrica", "kenya": "Kenia", "ethiopia": "Etiopía", "ghana": "Ghana", "rwanda": "Ruanda",
    "south sudan": "Sudán del Sur", "sudan": "Sudán", "zimbabwe": "Zimbabue", "guinea bissau": "Guinea-Bisáu",
    "mayotte": "Mayotte", "seychelles": "Seychelles", "mauritius": "Mauricio", "senegal": "Senegal",
    "australia": "Australia", "new zealand": "Nueva Zelanda", "colombia": "Colombia",
}


def pais_es(nombre: str | None) -> str:
    if not nombre or nombre.strip() in ("\\N", "N/A", "-"):
        return "Desconocido"
    return _ES.get(clave(nombre), nombre.strip())


def es_colombia(nombre: str | None) -> bool:
    return clave(nombre) == "colombia"
