FROM odoo:18.0

USER root

COPY docker-entrypoint-deps.sh /usr/local/bin/docker-entrypoint-deps.sh
RUN apt-get update \
    && apt-get install -y --no-install-recommends git python3-full python3-venv \
    && python3 -m venv /opt/odoo-venv \
    && /opt/odoo-venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/odoo-venv/bin/pip install --no-cache-dir filetype phonenumbers woocommerce python-barcode packaging "paramiko<4.0.0" openupgradelib cerberus pyquerystring parse-accept-language apispec cachetools \
    && chmod +x /usr/local/bin/docker-entrypoint-deps.sh \
    && rm -rf /var/lib/apt/lists/*

ENV ODOO_VENV=/opt/odoo-venv

COPY scripts/patch_woocommerce_connector.py /usr/local/bin/patch_woocommerce_connector.py

# Kopiera OCA community-moduler
COPY custom_addons/ /mnt/extra-addons/
RUN set -e; \
    fetch_repo() { \
      target="$1"; \
      branch="$2"; \
      url="$3"; \
      marker="$4"; \
      if [ ! -f "$marker" ]; then \
        rm -rf "$target"; \
        git clone --depth 1 --branch "$branch" "$url" "$target"; \
      fi; \
    }; \
    fetch_repo /mnt/extra-addons/multi-company 18.0 https://github.com/OCA/multi-company.git /mnt/extra-addons/multi-company/purchase_sale_inter_company/__manifest__.py; \
    fetch_repo /mnt/extra-addons/stock-logistics-warehouse 18.0 https://github.com/OCA/stock-logistics-warehouse.git /mnt/extra-addons/stock-logistics-warehouse/stock_storage_type/__manifest__.py; \
    fetch_repo /mnt/extra-addons/shopfloor-app 18.0 https://github.com/OCA/shopfloor-app.git /mnt/extra-addons/shopfloor-app/shopfloor_base/__manifest__.py; \
    fetch_repo /mnt/extra-addons/stock-logistics-shopfloor 18.0 https://github.com/OCA/stock-logistics-shopfloor.git /mnt/extra-addons/stock-logistics-shopfloor/shopfloor_reception/__manifest__.py; \
    fetch_repo /mnt/extra-addons/rest-framework 18.0 https://github.com/OCA/rest-framework.git /mnt/extra-addons/rest-framework/base_rest/__manifest__.py; \
    fetch_repo /mnt/extra-addons/connector 18.0 https://github.com/OCA/connector.git /mnt/extra-addons/connector/component/__manifest__.py; \
    fetch_repo /mnt/extra-addons/stock-logistics-tracking 18.0 https://github.com/OCA/stock-logistics-tracking.git /mnt/extra-addons/stock-logistics-tracking/stock_quant_package_dimension/__manifest__.py; \
    fetch_repo /mnt/extra-addons/web-api 18.0 https://github.com/OCA/web-api.git /mnt/extra-addons/web-api/endpoint_route_handler/__manifest__.py
RUN python3 /usr/local/bin/patch_woocommerce_connector.py

# Kopiera dina egna moduler
COPY my_addons/ /mnt/extra-addons/

# Kopiera konfiguration
COPY config/odoo.conf /etc/odoo/odoo.conf

ENTRYPOINT ["/usr/local/bin/docker-entrypoint-deps.sh"]

USER odoo
