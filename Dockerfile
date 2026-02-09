FROM odoo:18.0

USER root

# Extra Python-paket för OCA-moduler och WooCommerce
RUN pip3 install --no-cache-dir \
    woocommerce \
    python-barcode \
    qrcode \
    phonenumbers \
    openupgradelib

# Kopiera OCA community-moduler
COPY custom_addons/ /mnt/extra-addons/

# Kopiera dina egna moduler
COPY my_addons/ /mnt/extra-addons/

# Kopiera konfiguration
COPY config/odoo.conf /etc/odoo/odoo.conf

USER odoo
