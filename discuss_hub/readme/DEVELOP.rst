# Running tests

To run the tests, You can use Docker to set up an Odoo instance with the
necessary dependencies.

```bash
docker compose run --rm odoo odoo --dev=all --db-filter='^test_only$' -d test_only --stop-after-init --test-enable --without-demo=all -i discuss_hub --test-tags /discuss_hub
```

# Run pre-commit locally without changing the addon README:
```bash
SKIP="oca-gen-addon-readme" pre-commit run --all-files --show-diff-on-failure --color=always
```

# Run shell to play with the code
```bash
docker compose run --rm odoo odoo shell -d odoo
```

# N8N

to export N8N Flows:
```
docker compose exec -u node -it n8n sh -c "n8n export:workflow --all > /n8n-workflows.yaml"
```

and to import and enable all workflows:
```
docker compose exec -u node -it n8n sh -c "n8n import:workflow --input=/n8n-workflows.yaml"
docker compose exec -u node -it n8n sh -c "n8n update:workflow --all --active=true"
```