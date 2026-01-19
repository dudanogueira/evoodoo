
<!-- /!\ Non OCA Context : Set here the badge of your runbot / runboat instance. -->
[![Pre-commit Status](https://github.com/discusshub/discuss_hub/actions/workflows/pre-commit.yml/badge.svg?branch=19.0)](https://github.com/discusshub/discuss_hub/actions/workflows/pre-commit.yml?query=branch%3A19.0)
[![Build Status](https://github.com/discusshub/discuss_hub/actions/workflows/test.yml/badge.svg?branch=19.0)](https://github.com/discusshub/discuss_hub/actions/workflows/test.yml?query=branch%3A19.0)
[![codecov](https://codecov.io/gh/discusshub/discuss_hub/branch/19.0/graph/badge.svg)](https://app.codecov.io/gh/discusshub/discuss_hub/tree/19.0)
<!-- /!\ Non OCA Context : Set here the badge of your translation instance. -->

<!-- /!\ do not modify above this line -->

# Discuss Hub

Integrate third-party message channels into Odoo's Discuss system.

## 📚 Documentation

**Complete documentation is available in multiple languages:**

- 🇧🇷 **[Documentação em Português](docs/pt-br/README.md)** - Full documentation in Brazilian Portuguese
- 🇺🇸 **[English Documentation](docs/en/README.md)** - Complete English documentation
- 📊 **[Architecture & Diagrams](docs/assets/diagrams.md)** - Technical architecture diagrams

**Quick Access:**
- [🔥 Evolution Plugin Guide](docs/pt-br/Evolution%20Plugin.md) | [English](docs/en/Evolution%20Plugin.md)
- [🛠️ Plugin Development](docs/pt-br/Plugin%20Development.md) | [English](docs/en/Plugin%20Development.md)
- [🔧 Troubleshooting](docs/pt-br/Troubleshooting.md)

[Deepwiki tech docs](https://deepwiki.com/discusshub/discuss_hub)

## QUICK START ##
```
git clone https://github.com/discusshub/discuss_hub my-project
cd my-project
docker compose -f compose-dev.yaml up -d
# wait....
sleep 30
# load workflows
docker compose -f compose-dev.yaml exec -u node -it n8n sh -c "n8n import:workflow --input=/n8n-workflows.yaml"
# activate workflows
docker compose -f compose-dev.yaml exec -u node -it n8n sh -c "n8n update:workflow --all --active=true"
# so or new workflow get registered
docker compose -f compose-dev.yaml restart n8n
# access odoo: http://localhost:8069/?debug=1
# Navigate to Discuss Hub, Connector. Click start
# Scan your whatsapp
```

Enjoy!

<!-- /!\ do not modify below this line -->

<!-- prettier-ignore-start -->

[//]: # (addons)

This part will be replaced when running the oca-gen-addons-table script from OCA/maintainer-tools.

[//]: # (end addons)

<!-- prettier-ignore-end -->
## Licenses

This repository is licensed under [AGPL-3.0](LICENSE).

However, each module may have a different license, as long as it follows the Discuss Hub Community
policy. Check each module's `__manifest__.py` file — the `license` key there explains the module's license.

----
<!-- /!\ Non OCA Context : Set here the full description of your organization. -->
## How to Configure

First, run the `compose.yaml` file included in this repository.

It contains all required services. It will start Odoo and, in the demo data,
create a sample connector.

```