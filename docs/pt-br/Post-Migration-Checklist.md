# Checklist de Verificação Pós-Migração

Use este checklist após atualizar o Discuss Hub para a versão com hooks nativos.

## ✅ Pré-Requisitos

- [ ] Backup do banco de dados realizado
- [ ] Código atualizado (git pull)
- [ ] Docker containers reconstruídos (se necessário)

## 🔧 Passos de Migração

### 1. Atualizar Código

```bash
cd /Users/dudanogueira/dev/discuss_hub
git pull origin 18.0
```

### 2. Rebuild Containers (se houver mudanças no Dockerfile)

```bash
docker compose -f compose-dev.yaml down
docker compose -f compose-dev.yaml up -d --build
```

### 3. Atualizar Módulo

```bash
# Opção 1: Via UI
# Apps -> Discuss Hub -> Upgrade

# Opção 2: Via CLI
docker compose -f compose-dev.yaml exec odoo odoo -u discuss_hub --stop-after-init
docker compose -f compose-dev.yaml restart odoo
```

## 🔍 Verificações

### 1. Verificar Automações Inativas

```bash
# Acessar Odoo UI
# Ir em: Configurações -> Técnico -> Automação -> Ações Automatizadas
# Buscar: "discuss_hub"
```

- [ ] Automação "discuss_hub message outgo" está INATIVA ou mostra (DEPRECATED)
- [ ] Automação "discuss_hub reaction outgo" está INATIVA ou mostra (DEPRECATED)
- [ ] Automação "discuss_hub bot outgo" está INATIVA ou mostra (DEPRECATED)

### 2. Verificar Logs

```bash
# Acompanhar logs do Odoo
docker compose -f compose-dev.yaml logs -f odoo
```

Procure por estas mensagens nos logs:

- [ ] `discuss_channel.message_post: sending outgoing message` (quando enviar mensagem)
- [ ] `discuss_channel._notify_thread: processing bot` (quando bot processar mensagem)
- [ ] `mail_message_reaction.create: connector` (quando adicionar reação)

**NÃO** deve aparecer mais:

- [ ] ❌ `automation_base: running outgo message`
- [ ] ❌ `automation_base: connector:... reaction`

### 3. Testes Funcionais

#### 3.1 Mensagem Odoo → Externa

- [ ] Abrir canal conectado ao WhatsApp/Telegram
- [ ] Enviar mensagem de teste
- [ ] Verificar que mensagem aparece na plataforma externa
- [ ] Verificar log mostra: `discuss_channel.message_post:`

#### 3.2 Mensagem Externa → Odoo

- [ ] Enviar mensagem do WhatsApp/Telegram
- [ ] Verificar que mensagem aparece no Odoo
- [ ] Verificar criação do canal (se novo contato)
- [ ] Verificar que webhook foi processado corretamente

#### 3.3 Bot Automation

- [ ] Configurar bot para um parceiro
- [ ] Enviar mensagem para canal com esse parceiro
- [ ] Verificar que bot responde automaticamente
- [ ] Verificar log mostra: `discuss_channel._notify_thread:`

#### 3.4 Reações

- [ ] Encontrar mensagem vinda de plataforma externa
- [ ] Adicionar reação (emoji) no Odoo
- [ ] Verificar que reação aparece na plataforma externa
- [ ] Verificar log mostra: `mail_message_reaction.create:`

### 4. Testes de Performance

```bash
# Enviar 10 mensagens rapidamente e verificar performance
```

- [ ] Mensagens são enviadas sem delay perceptível
- [ ] Sem erros nos logs
- [ ] Uso de CPU normal (não há picos)

### 5. Testes de Error Handling

#### 5.1 Conector Desabilitado

- [ ] Desabilitar conector
- [ ] Tentar enviar mensagem
- [ ] Verificar que mensagem é criada no Odoo normalmente
- [ ] Verificar que não há erro de execução

#### 5.2 API Externa Offline

- [ ] Parar Evolution API / plataforma externa
- [ ] Enviar mensagem do Odoo
- [ ] Verificar que erro é logado mas não quebra
- [ ] Verificar mensagem foi criada no Odoo

## 🧪 Testes Automatizados

```bash
# Rodar suite de testes
docker compose -f compose-dev.yaml exec odoo python -m pytest discuss_hub/tests/test_code_hooks.py -v

# Rodar todos os testes do módulo
docker compose -f compose-dev.yaml exec odoo odoo -d odoo --test-enable --stop-after-init -u discuss_hub
```

- [ ] `test_message_post_hook_triggers_outgo_message` - PASSOU
- [ ] `test_message_post_without_connector_does_not_fail` - PASSOU
- [ ] `test_bot_automation_hook_triggers_on_notify` - PASSOU
- [ ] `test_reaction_create_hook_triggers_outgo_reaction` - PASSOU
- [ ] `test_reaction_without_external_id_does_not_trigger_hook` - PASSOU
- [ ] `test_error_in_hook_does_not_break_normal_flow` - PASSOU

## 📊 Monitoramento

### Métricas a Observar (Primeiros 24h)

```bash
# Monitorar logs continuamente
docker compose -f compose-dev.yaml logs -f odoo | tee migration_logs.txt
```

- [ ] Taxa de erro mantém-se igual ou menor
- [ ] Tempo de resposta de envio de mensagens menor ou igual
- [ ] Sem memory leaks (uso de memória estável)
- [ ] Webhooks processados com sucesso

### Queries Úteis para Logs

```bash
# Ver apenas logs de hooks
docker compose -f compose-dev.yaml logs odoo | grep "discuss_channel\|mail_message_reaction"

# Ver apenas erros
docker compose -f compose-dev.yaml logs odoo | grep ERROR

# Contar mensagens processadas
docker compose -f compose-dev.yaml logs odoo | grep "message_post:" | wc -l
```

## 🚨 Problemas Conhecidos e Soluções

### Problema: Mensagens não enviando para plataforma externa

**Sintomas:**

- Mensagens criadas no Odoo
- Não aparecem na plataforma externa
- Sem erros nos logs

**Verificar:**

1. Canal tem `discuss_hub_connector` configurado?

   ```python
   # No shell do Odoo
   channel = env['discuss.channel'].browse(CHANNEL_ID)
   print(channel.discuss_hub_connector)
   ```

2. Conector está habilitado?

   ```python
   print(channel.discuss_hub_connector.enabled)
   ```

3. Plugin está funcionando?
   ```python
   print(channel.discuss_hub_connector.get_status())
   ```

### Problema: Bot não respondendo

**Sintomas:**

- Mensagens recebidas
- Bot não dispara

**Verificar:**

1. Parceiro tem bot configurado?

   ```python
   partner = env['res.partner'].browse(PARTNER_ID)
   print(partner.bot)
   ```

2. Bot está ativo?

   ```python
   print(partner.bot.active)
   ```

3. Verificar logs para `_notify_thread`:
   ```bash
   docker compose -f compose-dev.yaml logs odoo | grep "_notify_thread"
   ```

### Problema: Reações não sincronizando

**Sintomas:**

- Reação adicionada no Odoo
- Não aparece na plataforma externa

**Verificar:**

1. Mensagem tem `discuss_hub_message_id`?

   ```python
   message = env['mail.message'].browse(MESSAGE_ID)
   print(message.discuss_hub_message_id)
   ```

2. Plugin suporta reações?
   ```python
   # Verificar se método exists
   connector = env['discuss_hub.connector'].browse(CONNECTOR_ID)
   print(hasattr(connector, 'outgo_reaction'))
   ```

## 🔄 Rollback (Se Necessário)

Se encontrar problemas críticos:

### 1. Reverter Código

```bash
git checkout HEAD~1  # ou commit específico anterior
```

### 2. Reativar Automações

```bash
# Editar discuss_hub/datas/base_automation.xml
# Mudar active=0 para active=1 em todas as automações
```

### 3. Comentar Hooks

```python
# Em discuss_hub/models/discuss_channel.py
# Comentar os métodos:
# - message_post
# - _notify_thread

# Em discuss_hub/models/mail_message_reaction.py
# Comentar arquivo inteiro ou mover para .bak
```

### 4. Atualizar Módulo

```bash
docker compose -f compose-dev.yaml exec odoo odoo -u discuss_hub --stop-after-init
docker compose -f compose-dev.yaml restart odoo
```

## ✅ Sign-off

Após completar todos os checks acima:

- [ ] Todas as verificações passaram
- [ ] Testes automatizados executados com sucesso
- [ ] Funcionalidades testadas manualmente
- [ ] Performance igual ou melhor que antes
- [ ] Logs mostram nova implementação funcionando
- [ ] Nenhum erro crítico encontrado
- [ ] Stakeholders notificados sobre atualização

**Data:** **\*\***\_\_\_**\*\*** **Verificado por:** **\*\***\_\_\_**\*\***
**Ambiente:** [ ] Dev [ ] Staging [ ] Production **Notas adicionais:**

---

---

---

---

## 📚 Documentação Relacionada

- [Guia de Migração Completo (PT-BR)](./Migration-BaseAutomations-to-CodeHooks.md)
- [Comparação Visual](./Comparison-Automations-vs-Hooks.md)
- [README Atualizado](./README.md)
- [Resumo de Migração](../../MIGRATION_SUMMARY.md)
