# Stage 1: Clone required repositories and prepare addons
FROM alpine/git AS build

# Create working directories
RUN mkdir -p /mnt/repositories /mnt/extra-addons
WORKDIR /mnt/repositories

# Clone only required repos shallowly
RUN git clone --depth 1 https://github.com/OCA/website \
 && git clone --depth 1 https://github.com/OCA/social \
 && git clone --depth 1 https://github.com/camptocamp/odoo-cloud-platform \
 && git clone --depth 1 https://github.com/OCA/server-tools \
 && git clone --depth 1 https://github.com/OCA/server-env \
 && git clone --depth 1 https://github.com/OCA/helpdesk

# Move selected addons
RUN mv \
    odoo-cloud-platform/base_fileurl_field \
    odoo-cloud-platform/cloud_platform \
    odoo-cloud-platform/logging_json \
    odoo-cloud-platform/monitoring_log_requests \
    odoo-cloud-platform/monitoring_prometheus \
    odoo-cloud-platform/monitoring_statsd \
    odoo-cloud-platform/monitoring_status \
    odoo-cloud-platform/session_redis \
    odoo-cloud-platform/test_base_fileurl_field \
    server-tools/session_db \
    server-env/server_environment \
    helpdesk/helpdesk_mgmt \
    /mnt/extra-addons/

# Clean up repositories to reduce image size
RUN rm -rf /mnt/repositories

# Stage 2: Final image based on official Odoo
FROM odoo:18

COPY ./discuss_hub/ /mnt/extra-addons/discuss_hub

# Environment setup
ENV ODOO_USER=odoo \
    ADDONS_DIR=/mnt/extra-addons

# Create and copy custom addons
RUN mkdir -p ${ADDONS_DIR}
COPY --from=build /mnt/extra-addons/ ${ADDONS_DIR}/

# Install Python dependencies

USER root
RUN chown -R ${ODOO_USER}:${ODOO_USER} ${ADDONS_DIR} \
 && pip3 install --no-cache-dir --break-system-packages redis python-json-logger statsd boto

USER ${ODOO_USER}

# Entrypoint
ENTRYPOINT ["/entrypoint.sh"]
CMD ["odoo"]
