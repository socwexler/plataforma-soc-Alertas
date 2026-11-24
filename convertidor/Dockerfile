# Convertidor de documentos (Gotenberg: LibreOffice para Word -> PDF y Chromium para HTML -> PDF)
# con las fuentes corporativas de la plantilla (Lato y Montserrat, licencia OFL).
FROM gotenberg/gotenberg:8
USER root
COPY fuentes/*.ttf /usr/local/share/fonts/wexler/
COPY 99-wexler.conf /etc/fonts/conf.d/99-wexler.conf
RUN fc-cache -f
USER gotenberg
