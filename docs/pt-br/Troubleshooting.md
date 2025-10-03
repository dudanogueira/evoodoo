# Troubleshooting - Guia de Solução de Problemas 🔧

## 📋 Índice

- [[#Problemas de Instalação]]
- [[#Problemas de Conexão]]
- [[#Problemas com Mensagens]]
- [[#Problemas com Plugins]]
- [[#Problemas de Performance]]
- [[#Debug e Logs]]
- [[#Comandos Úteis]]
- [[#FAQ]]

---

## 🚀 Problemas de Instalação

### ❌ Docker não inicia

**Sintomas**: Containers não sobem ou falham na inicialização

**Soluções**:

```bash
# Verificar se Docker está rodando
docker ps

# Verificar logs dos containers
docker compose logs

# Limpar containers antigos
docker compose down -v
docker system prune -af

# Reiniciar serviços
docker compose -f compose-dev.yaml up -d --force-recreate
```

### ❌ Erro de dependências Python

**Sintomas**: `ModuleNotFoundError` ou erros de import

**Soluções**:

```bash
# Reconstruir imagem do Odoo
docker compose build odoo --no-cache

# Instalar dependências manualmente
docker compose exec odoo pip install -r requirements.txt

# Verificar se módulo está no addons path
docker compose exec odoo odoo shell -c "import discuss_hub"
```

### ❌ Banco de dados não conecta

**Sintomas**: `FATAL: password authentication failed`

**Soluções**:

```bash
# Verificar variáveis de ambiente
cat .env | grep PG

# Resetar banco
docker compose down -v
docker compose up -d db
# Aguardar inicialização completa
docker compose up -d odoo
```

---

## 🔗 Problemas de Conexão

### ❌ Webhook não recebe dados

**Sintomas**: Mensagens não aparecem no Odoo

**Diagnóstico**:

```bash
# Testar webhook manualmente
curl -X POST http://localhost:8069/webhook/discuss_hub/SEU_UUID \
  -H "Content-Type: application/json" \
  -d '{"event": "test", "data": {"message": "teste"}}'

# Verificar logs em tempo real
docker compose logs -f odoo | grep discuss_hub

# Verificar se connector está habilitado
echo "SELECT name, enabled, uuid FROM discuss_hub_connector;" | \
docker compose exec -T db psql -U odoo -d odoo
```

**Soluções**:

- Confirmar URL do webhook na API externa
- Verificar se UUID do connector está correto
- Confirmar que connector está `enabled=True`
- Testar conectividade de rede

### ❌ Evolution API não conecta

**Sintomas**: Status sempre "not_found" ou "error"

**Verificações**:

```bash
# Testar API diretamente
curl -H "apikey: SEU_TOKEN" \
  "https://sua-evolution-api.com/instance/status/INSTANCIA"

# Verificar se Evolution API está rodando
docker ps | grep evolution

# Logs da Evolution API
docker logs evolution-api-container
```

**Soluções**:

- Confirmar que Evolution API está acessível
- Verificar URL (sem trailing slash)
- Confirmar API Key válida
- Testar criar instância manualmente

### ❌ QR Code não aparece

**Sintomas**: Campo QR Code vazio no connector

**Soluções**:

```python
# No shell do Odoo, forçar refresh do status
connector = env['discuss_hub.connector'].browse(ID_DO_CONNECTOR)
status = connector.get_status()
print(status)

# Recriar instância se necessário
plugin = connector.get_plugin()
plugin.restart_instance()
```

---

## 💬 Problemas com Mensagens

### ❌ Mensagens não são enviadas

**Sintomas**: Erro ao enviar mensagens do Odoo

**Diagnóstico**:

```python
# No shell do Odoo
channel = env['discuss.channel'].search([('name', 'ilike', 'NOME_DO_CANAL')])
message = env['mail.message'].search([('res_id', '=', channel.id)], limit=1)
connector = channel.discuss_hub_connector

# Testar envio manual
result = connector.outgo_message(channel, message)
print(result)
```

**Soluções**:

- Verificar se canal tem `discuss_hub_outgoing_destination`
- Confirmar que connector está habilitado
- Testar API externa manualmente
- Verificar logs de erro

### ❌ Mensagens duplicadas

**Sintomas**: Mesma mensagem aparece várias vezes

**Soluções**:

```sql
-- Verificar mensagens duplicadas
SELECT discuss_hub_message_id, COUNT(*)
FROM mail_message
WHERE discuss_hub_message_id IS NOT NULL
GROUP BY discuss_hub_message_id
HAVING COUNT(*) > 1;

-- Limpar duplicatas (CUIDADO!)
DELETE FROM mail_message
WHERE id NOT IN (
    SELECT MIN(id)
    FROM mail_message
    GROUP BY discuss_hub_message_id
);
```

### ❌ Caracteres especiais quebrados

**Sintomas**: Emojis ou acentos não aparecem corretamente

**Soluções**:

```bash
# Verificar encoding do banco
docker compose exec db psql -U odoo -c "SHOW server_encoding;"

# Deve ser UTF8
# Se não for, recriar banco com encoding correto

# Verificar locale no container
docker compose exec odoo locale
```

---

## 🔌 Problemas com Plugins

### ❌ Plugin não carrega

**Sintomas**: `Plugin not found` ou erro de import

**Verificações**:

```python
# No shell do Odoo, testar import manual
try:
    from odoo.addons.discuss_hub.models.plugins import meu_plugin
    print("Plugin importado com sucesso")
except ImportError as e:
    print(f"Erro de import: {e}")

# Verificar se arquivo existe
import os
plugin_path = "/mnt/extra-addons/discuss_hub/models/plugins/meu_plugin.py"
print(f"Arquivo existe: {os.path.exists(plugin_path)}")
```

**Soluções**:

- Verificar sintaxe do arquivo Python
- Confirmar que `plugin_name` está definido
- Verificar se está no diretório correto
- Reiniciar servidor Odoo após mudanças

### ❌ Método não implementado

**Sintomas**: `NotImplementedError` ao usar plugin

**Soluções**:

```python
# Verificar se plugin implementa métodos obrigatórios
plugin = connector.get_plugin()

# Métodos obrigatórios
required_methods = [
    'get_status',
    'process_payload',
    'get_message_id',
    'get_contact_name',
    'get_contact_identifier'
]

for method in required_methods:
    if not hasattr(plugin, method):
        print(f"Método {method} não implementado")
```

### ❌ Plugin com erro interno

**Sintomas**: Exceções não tratadas no plugin

**Debug**:

```python
# Ativar modo debug detalhado
import logging
logging.getLogger('odoo.addons.discuss_hub').setLevel(logging.DEBUG)

# Testar métodos individualmente
try:
    status = plugin.get_status()
    print(f"Status: {status}")
except Exception as e:
    print(f"Erro no get_status: {e}")
    import traceback
    traceback.print_exc()
```

---

## ⚡ Problemas de Performance

### ❌ Webhook muito lento

**Sintomas**: Demora para processar mensagens

**Otimizações**:

```python
# Otimizar busca de partners
# Em vez de:
partner = env['res.partner'].search([('phone', '=', phone)])

# Use:
partner = env['res.partner'].search([
    ('phone', '=', phone)
], limit=1)  # Limite a busca

# Cache de channels
channel_cache = {}
def get_channel_cached(identifier):
    if identifier not in channel_cache:
        channel_cache[identifier] = env['discuss.channel'].search([
            ('discuss_hub_outgoing_destination', '=', identifier)
        ], limit=1)
    return channel_cache[identifier]
```

### ❌ Muitas conexões de banco

**Sintomas**: Erro "too many connections"

**Soluções**:

```bash
# Configurar pool de conexões no Odoo
# odoo.conf
[options]
db_maxconn = 64
max_cron_threads = 2

# Monitorar conexões ativas
docker compose exec db psql -U odoo -c "
SELECT count(*) as connections, state
FROM pg_stat_activity
GROUP BY state;
"
```

### ❌ Processamento em lote lento

**Sintomas**: Demora para sincronizar muitos contatos

**Otimizações**:

```python
# Processar em lotes menores
def process_contacts_batch(contacts, batch_size=50):
    for i in range(0, len(contacts), batch_size):
        batch = contacts[i:i + batch_size]
        env.cr.savepoint()  # Criar savepoint
        try:
            for contact in batch:
                process_single_contact(contact)
            env.cr.commit()  # Commit do lote
        except Exception as e:
            env.cr.rollback()  # Rollback do lote
            _logger.error(f"Erro no lote {i}-{i+batch_size}: {e}")
```

---

## 🔍 Debug e Logs

### 📋 Configuração de Logging

```python
# No código Python
import logging

# Logger específico do módulo
_logger = logging.getLogger(__name__)

# Diferentes níveis
_logger.debug("Informação de debug")     # Só em modo debug
_logger.info("Informação geral")         # Sempre visível
_logger.warning("Aviso importante")      # Destacado
_logger.error("Erro recuperável")        # Erro mas continua
_logger.exception("Erro com traceback")  # Inclui stack trace
```

### 📊 Comandos de Log

```bash
# Logs em tempo real
docker compose logs -f odoo

# Logs filtrados por módulo
docker compose logs odoo | grep discuss_hub

# Logs com timestamp
docker compose logs -t odoo

# Últimas 100 linhas
docker compose logs --tail=100 odoo

# Logs de container específico
docker compose logs evolution-api
docker compose logs n8n
docker compose logs db
```

### 🔧 Ativando Debug Mode

```bash
# Via parâmetro na URL
http://localhost:8069/?debug=1

# Via código Python
env.registry.in_debug_mode = True

# Via configuração do Odoo
# odoo.conf
[options]
log_level = debug
log_handler = :INFO,werkzeug:CRITICAL,odoo.service.server:INFO
```

---

## 🛠️ Comandos Úteis

### Docker Commands

```bash
# Status dos containers
docker compose ps

# Reiniciar serviço específico
docker compose restart odoo

# Reconstruir sem cache
docker compose build --no-cache

# Shell do container
docker compose exec odoo bash
docker compose exec db psql -U odoo

# Limpar tudo
docker compose down -v
docker system prune -af
docker volume prune -f
```

### Odoo Commands

```bash
# Shell interativo
docker compose exec odoo odoo shell -d odoo

# Atualizar módulo
docker compose exec odoo odoo -u discuss_hub -d odoo --stop-after-init

# Instalar módulo
docker compose exec odoo odoo -i discuss_hub -d odoo --stop-after-init

# Executar testes
docker compose exec odoo odoo --test-enable --test-tags /discuss_hub -d test_db --stop-after-init
```

### Database Commands

```bash
# Conectar ao PostgreSQL
docker compose exec db psql -U odoo -d odoo

# Queries úteis
SELECT * FROM discuss_hub_connector;
SELECT * FROM discuss_channel WHERE discuss_hub_connector IS NOT NULL;
SELECT * FROM mail_message WHERE discuss_hub_message_id IS NOT NULL;

# Backup do banco
docker compose exec db pg_dump -U odoo odoo > backup.sql

# Restaurar backup
docker compose exec -T db psql -U odoo odoo < backup.sql
```

### N8N Commands

```bash
# Exportar workflows
docker compose exec -u node n8n sh -c "n8n export:workflow --all > /n8n-workflows.yaml"

# Importar workflows
docker compose exec -u node n8n sh -c "n8n import:workflow --input=/n8n-workflows.yaml"

# Ativar workflows
docker compose exec -u node n8n sh -c "n8n update:workflow --all --active=true"
```

---

## ❓ FAQ (Perguntas Frequentes)

### Q: Como resetar completamente o ambiente?

```bash
docker compose down -v
docker system prune -af
docker compose -f compose-dev.yaml up -d
```

### Q: Como migrar configurações para novo servidor?

```bash
# Exportar dados do connector
docker compose exec db pg_dump -U odoo -t discuss_hub_connector odoo > connectors.sql

# No novo servidor
docker compose exec -T db psql -U odoo odoo < connectors.sql
```

### Q: Como testar plugin sem afetar produção?

```python
# Criar connector de teste
test_connector = env['discuss_hub.connector'].create({
    'name': 'test_instance',
    'type': 'meu_plugin',
    'enabled': False,  # Desabilitado para não processar webhooks
    'url': 'https://test-api.com',
    'api_key': 'test_key'
})

# Testar métodos manualmente
plugin = test_connector.get_plugin()
status = plugin.get_status()
```

### Q: Como monitorar performance dos webhooks?

```python
# Adicionar timing nos plugins
import time

def process_payload(self, payload):
    start_time = time.time()
    try:
        result = self._process_main_logic(payload)
        duration = time.time() - start_time
        _logger.info(f"Payload processed in {duration:.3f}s")
        return result
    except Exception as e:
        duration = time.time() - start_time
        _logger.error(f"Payload failed after {duration:.3f}s: {e}")
        raise
```

### Q: Como fazer backup dos dados de mensagens?

```bash
# Backup completo das mensagens
docker compose exec db pg_dump -U odoo \
  --table=mail_message \
  --table=discuss_channel \
  --table=res_partner \
  odoo > messages_backup.sql
```

### Q: Como configurar múltiplos conectores do mesmo tipo?

```python
# Cada connector deve ter name único
connector1 = env['discuss_hub.connector'].create({
    'name': 'whatsapp_vendas',    # Nome único
    'type': 'evolution',
    'url': 'https://api1.evolution.com',
    'api_key': 'key1'
})

connector2 = env['discuss_hub.connector'].create({
    'name': 'whatsapp_suporte',   # Nome único diferente
    'type': 'evolution',
    'url': 'https://api2.evolution.com',
    'api_key': 'key2'
})
```

---

## 📞 Quando Solicitar Ajuda

Se após seguir este guia você ainda tiver problemas:

1. **Colete informações**:

   - Versão do Discuss Hub
   - Logs de erro completos
   - Configuração do connector (sem API keys)
   - Passos para reproduzir o problema

2. **Abra uma issue**: [GitHub Issues](https://github.com/discusshub/discuss_hub/issues)

3. **Use o template**:

   ```markdown
   **Descrição do Problema**: [Descreva o que está acontecendo]

   **Passos para Reproduzir**:

   1. [Primeiro passo]
   2. [Segundo passo]

   **Comportamento Esperado**: [O que deveria acontecer]

   **Logs de Erro**:
   ```

   [Cole os logs aqui]

   ```

   **Ambiente**:
   - Odoo Version: [ex: 18.0]
   - Discuss Hub Version: [ex: 18.0.0.0.10]
   - Plugin: [ex: evolution]
   - Docker/Native: [ex: Docker]
   ```

---

## 🔗 Links Relacionados

- [[README|Documentação Principal]]
- [[Evolution Plugin|Plugin Evolution]]
- [[Plugin Development|Desenvolvimento de Plugins]]
- [[API Reference|Referência da API]]

---

_Última atualização: 24 de Setembro de 2025_
