FROM odoo:18.0

USER root

# Kopiera OCA community-moduler
COPY custom_addons/ /mnt/extra-addons/

# Kopiera dina egna moduler
COPY my_addons/ /mnt/extra-addons/

# Kopiera konfiguration
COPY config/odoo.conf /etc/odoo/odoo.conf

USER od

oo
