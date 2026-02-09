FROM odoo:18.0

USER root

# Uppgradera pip först
RUN pip3 install --upgrade pip

# Extra Python-paket för OCA-moduler och WooCommerce
RUN pip3 install --no-cache-dir woocommerce && \
    pip3 install --no-cache-dir python-barcode && \
    pip3 install --no-cache-dir qrcode pillow && \
    pip3 install --no-cache-dir phonenumbers && \
    pip3 install --no-cache-dir openupgradelib

# Kopiera OCA community-moduler
COPY custom_addons/ /mnt/extra-addons/

# Kopiera dina egna moduler
COPY my_addons/ /mnt/extra-addons/

# Kopiera konfiguration
COPY config/odoo.conf /etc/odoo/odoo.conf

USER odoo
