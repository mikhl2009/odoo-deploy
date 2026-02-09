FROM odoo:18.0

USER root

COPY docker-entrypoint-deps.sh /usr/local/bin/docker-entrypoint-deps.sh
RUN chmod +x /usr/local/bin/docker-entrypoint-deps.sh

# Kopiera OCA community-moduler
COPY custom_addons/ /mnt/extra-addons/

# Kopiera dina egna moduler
COPY my_addons/ /mnt/extra-addons/

# Kopiera konfiguration
COPY config/odoo.conf /etc/odoo/odoo.conf

ENTRYPOINT ["/usr/local/bin/docker-entrypoint-deps.sh"]

USER odoo
