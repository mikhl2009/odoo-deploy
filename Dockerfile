FROM odoo:18.0

USER root

# Kopiera OCA community-moduler
COPY custom_addons/ /mnt/extra-addons/

# Kopiera dina egna moduler
COPY my_addons/ /mnt/extra-addons/

# Kopiera konfiguration
COPY config/odoo.conf /etc/odoo/odoo.conf

# Copy entrypoint script for runtime Python deps installation
COPY docker-entrypoint-deps.sh /
RUN chmod +x /docker-entrypoint-deps.sh

USER odoo

# Install Python dependencies at runtime (after container starts)
ENTRYPOINT ["/docker-entrypoint-deps.sh"]
CMD ["odoo"]
