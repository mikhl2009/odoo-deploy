FROM odoo:18.0

USER root

COPY docker-entrypoint-deps.sh /usr/local/bin/docker-entrypoint-deps.sh
RUN apt-get update \
    && apt-get install -y --no-install-recommends git python3-full python3-venv \
    && python3 -m venv /opt/odoo-venv \
    && /opt/odoo-venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/odoo-venv/bin/pip install --no-cache-dir filetype phonenumbers woocommerce python-barcode packaging paramiko openupgradelib \
    && chmod +x /usr/local/bin/docker-entrypoint-deps.sh \
    && rm -rf /var/lib/apt/lists/*

ENV ODOO_VENV=/opt/odoo-venv

COPY scripts/patch_woocommerce_connector.py /usr/local/bin/patch_woocommerce_connector.py

# Kopiera OCA community-moduler
COPY custom_addons/ /mnt/extra-addons/
RUN if [ ! -f /mnt/extra-addons/multi-company/purchase_sale_inter_company/__manifest__.py ]; then \
      rm -rf /mnt/extra-addons/multi-company && \
      git clone --depth 1 --branch 18.0 https://github.com/OCA/multi-company.git /mnt/extra-addons/multi-company; \
    fi
RUN python3 /usr/local/bin/patch_woocommerce_connector.py

# Kopiera dina egna moduler
COPY my_addons/ /mnt/extra-addons/

# Kopiera konfiguration
COPY config/odoo.conf /etc/odoo/odoo.conf

ENTRYPOINT ["/usr/local/bin/docker-entrypoint-deps.sh"]

USER odoo
