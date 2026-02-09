FROM odoo:18.0

USER root

COPY docker-entrypoint-deps.sh /usr/local/bin/docker-entrypoint-deps.sh
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3-full python3-venv \
    && python3 -m venv /opt/odoo-venv \
    && /opt/odoo-venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/odoo-venv/bin/pip install --no-cache-dir filetype phonenumbers woocommerce \
    && chmod +x /usr/local/bin/docker-entrypoint-deps.sh \
    && rm -rf /var/lib/apt/lists/*

ENV ODOO_VENV=/opt/odoo-venv

COPY scripts/patch_woocommerce_connector.py /usr/local/bin/patch_woocommerce_connector.py

# Kopiera OCA community-moduler
COPY custom_addons/ /mnt/extra-addons/
RUN python3 /usr/local/bin/patch_woocommerce_connector.py

# Kopiera dina egna moduler
COPY my_addons/ /mnt/extra-addons/

# Kopiera konfiguration
COPY config/odoo.conf /etc/odoo/odoo.conf

ENTRYPOINT ["/usr/local/bin/docker-entrypoint-deps.sh"]

USER odoo
