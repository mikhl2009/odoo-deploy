FROM odoo:18.0

USER root

# Install WooCommerce sync Python dependencies
RUN pip3 install --no-cache-dir filetype phonenumbers woocommerce

# Kopiera OCA community-moduler
COPY custom_addons/ /mnt/extra-addons/

# Kopiera dina egna moduler
COPY my_addons/ /mnt/extra-addons/

# Kopiera konfiguration
COPY config/odoo.conf /etc/odoo/odoo.conf

USER odoo
