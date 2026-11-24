"""Archivos inofensivos de prueba (los 'ejecutables' son solo texto)."""
import io
import os
import struct
import zipfile
from email.message import EmailMessage
from PIL import Image
d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "archivos")
os.makedirs(d, exist_ok=True)


def z(nombre, archivos):
    with zipfile.ZipFile(os.path.join(d, nombre), "w") as f:
        for n, c in archivos.items():
            f.writestr(n, c)


z("malo.zip", {"carpeta/programa.exe": "no es un ejecutable"})
z("bueno.zip", {"log.txt": "linea"})
z("ok.docx", {"[Content_Types].xml": "<Types/>", "word/document.xml": "<a/>"})
z("macro.docx", {"[Content_Types].xml": "<Types/>", "word/vbaProject.bin": "x"})
im = Image.new("RGB", (120, 80), "red")
ex = im.getexif()
ex[0x010E] = "DATO PRIVADO"
im.save(os.path.join(d, "gps.jpg"), exif=ex)


def ole(nombre, flujos):
    """Contenedor OLE mínimo (como un .msg) con flujos cortos."""
    FIN, LIBRE, NO = 0xFFFFFFFE, 0xFFFFFFFF, 0xFFFFFFFF
    mini, minifat, ent = b"", [], []
    for n, c in flujos.items():
        k = max(1, -(-len(c) // 64)); ini = len(minifat)
        minifat += [ini + i + 1 for i in range(k - 1)] + [FIN]
        mini += c.ljust(k * 64, b"\0"); ent.append((n, 2, ini, len(c)))
    mini_s = -(-len(mini) // 512)
    def entrada(n, t, ini, tam, hijo=NO, der=NO):
        u = n.encode("utf-16-le") + b"\0\0"
        return u.ljust(64, b"\0") + struct.pack("<HBBIII", len(u), t, 1, NO, der, hijo) + b"\0" * 36 + struct.pack("<IQ", ini, tam)
    dirs = entrada("Root Entry", 5, 0, len(mini), hijo=1) + b"".join(entrada(*e, der=i + 2 if i + 1 < len(ent) else NO) for i, e in enumerate(ent))
    dirs = dirs.ljust(-(-len(dirs) // 512) * 512, b"\0"); dir_s = len(dirs) // 512
    cadena = lambda a, k: [a + i + 1 for i in range(k - 1)] + [FIN]
    fat = cadena(0, mini_s) + cadena(mini_s, dir_s) + [FIN, 0xFFFFFFFD]   # mini, directorio, minifat, fat
    cab = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\0" * 16 + struct.pack("<HHHHH", 62, 3, 0xFFFE, 9, 6) + b"\0" * 6
    cab += struct.pack("<9I", 0, 1, mini_s, 0, 4096, mini_s + dir_s, 1, FIN, 0) + struct.pack("<109I", mini_s + dir_s + 1, *[LIBRE] * 108)
    r = lambda xs: struct.pack("<128I", *xs, *[LIBRE] * (128 - len(xs)))
    with open(os.path.join(d, nombre), "wb") as f:
        f.write(cab + mini.ljust(mini_s * 512, b"\0") + dirs + r(minifat) + r(fat))


u = lambda t: t.encode("utf-16-le")
ole("respuesta.msg", {"__properties_version1.0": b"\0" * 32, "__substg1.0_0037001F": u("RE: caso"), "__substg1.0_3707001F": u("captura con un nombre bastante largo del cliente.png")})
ole("malo.msg", {"__properties_version1.0": b"\0" * 32, "__substg1.0_3707001F": u("factura con un nombre bastante largo del cliente.exe")})
ole("malo_ansi.msg", {"__properties_version1.0": b"\0" * 32, "__substg1.0_3704001E": b"factura.js\0"})
ole("word97.msg", {"WordDocument": b"\0" * 100})


def eml(nombre, adjunto=None, anidado=None):
    m = EmailMessage(); m["From"], m["To"], m["Subject"], m["Date"] = "a@cliente.example", "soc@wexler.example", "RE: caso", "Mon, 01 Jan 2024 10:00:00 -0500"
    m.set_content("Confirmado.")
    if adjunto:
        m.add_attachment(b"x", "application", "octet-stream", filename=adjunto)
    if anidado:
        m.add_attachment(anidado)
    with open(os.path.join(d, nombre), "wb") as f:
        f.write(m.as_bytes())
    return m


eml("respuesta.eml", "foto.png")
eml("malo.eml", "factura.exe")
dentro = EmailMessage(); dentro["From"], dentro["Subject"] = "x@y.example", "Alerta en sitio.com"; dentro.set_content("x")
eml("anidado.eml", anidado=dentro)
dentro.add_attachment(b"x", "application", "octet-stream", filename="pagina.html"); eml("anidado_malo.eml", anidado=dentro)
print(os.listdir(d))
