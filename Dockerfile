FROM alpine/git AS build

# Create necessary directories
RUN mkdir -p /mnt/repositories /mnt/extra-addons
WORKDIR /mnt/repositories

# Clone the repositories and move them to the correct location
RUN git clone --single-branch --depth 1 https://github.com/dudanogueira/evoodoo \
    git clone --single-branch --depth 1 https://github.com/OCA/website \
    git clone --single-branch --depth 1 https://github.com/OCA/social \
    && mv evoodoo/evo /mnt/extra-addons/evo \
    # other modules
    && mv website/website_odoo_debranding /mnt/extra-addons/ \
    && mv social/mail_debrand /mnt/extra-addons/ \
    # remove the cloned repository
    && rm -rf /mnt/repositories

FROM odoo:18.0-20250320

# Set environment variables
ENV ODOO_USER=odoo
ENV ADDONS_DIR=/mnt/extra-addons


# Copy the built addons from the previous stage
RUN mkdir -p ${ADDONS_DIR}
COPY --from=build /mnt/extra-addons ${ADDONS_DIR}

USER root
RUN chown -R ${ODOO_USER}:${ODOO_USER} ${ADDONS_DIR}

# Switch to Odoo user
USER ${ODOO_USER}

# Set the entrypoint
ENTRYPOINT ["/entrypoint.sh"]
CMD ["odoo"]