"""Archivos inofensivos de prueba (los 'ejecutables' son solo texto)."""
import io
import os
import zipfile
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
print(os.listdir(d))
