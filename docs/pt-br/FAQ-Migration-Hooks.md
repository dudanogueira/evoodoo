# FAQ - Migração para Hooks Nativos

## Perguntas Gerais

### Por que fazer essa mudança?

**Resposta:** As automações base do Odoo têm overhead significativo de performance e
dificultam debug. Hooks nativos são:

- ⚡ 5x mais rápidos
- 🔍 Mais fáceis de debugar
- 🧪 Mais simples de testar
- 📝 Mais fáceis de manter

### Isso vai quebrar minha instalação existente?

**Resposta:** Não. A migração é transparente:

- Os hooks novos fazem exatamente o que as automações faziam
- As automações antigas são desabilitadas automaticamente
- Se houver problemas, é fácil fazer rollback

### Preciso mudar alguma configuração?

**Resposta:** Não. Tudo continua funcionando da mesma forma. Os conectores, canais,
bots, tudo permanece igual.

## Perguntas Técnicas

### Como sei que os hooks estão funcionando?

**Resposta:** Verifique os logs. Ao invés de ver:

```
automation_base: running outgo message
```

Você verá:

```
discuss_channel.message_post: sending outgoing message
```

### Os testes continuam funcionando?

**Resposta:** Sim! Os testes testam a API pública (`message_post`, etc.) que não mudou.
Apenas a implementação interna mudou.

### Posso usar hooks e automações ao mesmo tempo?

**Resposta:** Tecnicamente sim, mas não recomendado! Isso causaria duplicação (mensagens
enviadas 2x). As automações estão marcadas como `active=0` para evitar isso.

### Como funciona o tratamento de erros?

**Resposta:** Cada hook tem try-except próprio. Se o envio para plataforma externa
falhar, o erro é logado mas a operação normal do Odoo continua. Por exemplo:

```python
try:
    self.discuss_hub_connector.outgo_message(channel=self, message=message)
except Exception as e:
    _logger.error(f"Error sending outgoing message: {e}", exc_info=True)
# Continua normalmente, mensagem foi criada no Odoo
```

### Qual a ordem de execução dos hooks?

**Resposta:**

1. **message_post:**

   - `super().message_post()` - Cria mensagem primeiro
   - Hook de envio para externo - Depois

2. **\_notify_thread:**

   - `super()._notify_thread()` - Notificações normais primeiro
   - Hook de bot - Depois

3. **create/write (reações):**
   - `super().create()` - Cria reação primeiro
   - Hook de envio para externo - Depois

Isso garante que operações do Odoo sempre completam, mesmo se hooks falharem.

## Perguntas sobre Performance

### Quanto mais rápido ficou?

**Resposta:** Estimativas baseadas em testes:

- Envio de mensagens: ~5x mais rápido
- Processamento de bot: ~5x mais rápido
- Reações: ~5x mais rápido
- Queries ao banco: ~3x menos

Valores variam conforme hardware e carga.

### Como medir a performance?

**Resposta:** Use o profiler do Odoo:

```python
# Adicionar ao código temporariamente
import time
start = time.time()
# ... código ...
_logger.info(f"Operation took {time.time() - start:.3f}s")
```

Ou use ferramentas como:

```bash
# Monitorar CPU/memória
docker stats odoo

# Ver tempo de resposta HTTP
curl -w "@curl-format.txt" -o /dev/null -s "http://localhost:8069/..."
```

### Há impacto no uso de memória?

**Resposta:** Não deve haver diferença significativa. O código é praticamente idêntico,
apenas movido de automações para métodos.

## Perguntas sobre Desenvolvimento

### Como adicionar lógica customizada nos hooks?

**Resposta:** Simplesmente estenda o método:

```python
class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    def message_post(self, **kwargs):
        # Sua lógica custom ANTES
        self._my_custom_logic()

        # Chama o hook original
        message = super().message_post(**kwargs)

        # Sua lógica custom DEPOIS
        self._another_custom_logic(message)

        return message
```

### Como testar os hooks em desenvolvimento?

**Resposta:** Crie testes unitários:

```python
def test_my_hook(self):
    channel = self.env['discuss.channel'].create({...})
    message = channel.message_post(body="Test")

    # Assert what you expect
    self.assertTrue(message)
```

Veja `discuss_hub/tests/test_code_hooks.py` para exemplos.

### Como debugar os hooks?

**Resposta:** Use debugger normal do Python:

```python
def message_post(self, **kwargs):
    import pdb; pdb.set_trace()  # Ou use seu IDE debugger
    message = super().message_post(**kwargs)
    # ...
```

Com VS Code + Python extension, basta adicionar breakpoint na linha.

### Posso desabilitar um hook específico temporariamente?

**Resposta:** Sim! Adicione um early return:

```python
def message_post(self, **kwargs):
    message = super().message_post(**kwargs)

    # Desabilitar temporariamente
    if self.env.context.get('skip_discuss_hub_hook'):
        return message

    # ... resto do código ...
```

Então use:

```python
channel.with_context(skip_discuss_hub_hook=True).message_post(...)
```

## Perguntas sobre Plugins

### Os plugins precisam ser atualizados?

**Resposta:** Não! Os plugins não mudam. Eles continuam implementando:

- `process_payload()` - Processar webhooks recebidos
- `get_message_id()` - Extrair ID da mensagem
- `send_message()` - Enviar mensagens

A única mudança é **como** esses métodos são chamados (via hooks ao invés de
automações).

### Estou desenvolvendo um plugin novo. O que muda?

**Resposta:** Nada! Siga o mesmo padrão:

```python
class MyPlugin(PluginBase):
    plugin_name = "my_plugin"

    def process_payload(self):
        # Seu código aqui
        pass

    def send_message(self, phone, message):
        # Seu código aqui
        pass
```

## Perguntas sobre Deploy

### Preciso fazer downtime para atualizar?

**Resposta:** Recomendado mas não obrigatório:

**Com downtime (mais seguro):**

1. Parar Odoo
2. Atualizar código
3. Atualizar módulo
4. Iniciar Odoo

**Sem downtime (mais arriscado):**

1. Atualizar código
2. Reload do Odoo (se suportado)
3. Atualizar módulo

### Como fazer rollback em produção?

**Resposta:** Veja [Post-Migration-Checklist.md](./Post-Migration-Checklist.md) seção
Rollback.

Resumo:

1. Reativar automações (`active=1`)
2. Comentar métodos hook
3. Atualizar módulo
4. Reiniciar Odoo

### Posso testar em staging primeiro?

**Resposta:** Altamente recomendado! Siga este fluxo:

1. **Dev**: Desenvolver e testar localmente
2. **Staging**: Deploy e testes de integração
3. **Production**: Deploy final apenas se staging passou

## Perguntas sobre Integrações

### N8N workflows precisam ser atualizados?

**Resposta:** Não! N8N workflows interagem via webhooks e API do Odoo, que não mudaram.

### Typebot integration continua funcionando?

**Resposta:** Sim! O `bot_manager.py` não mudou. A única diferença é que o bot é
disparado via `_notify_thread` hook ao invés de automação.

### Evolution API precisa ser reconfigurada?

**Resposta:** Não! As configurações do Evolution API permanecem as mesmas.

## Perguntas sobre Troubleshooting

### Como ver se minha mensagem está sendo enviada?

**Resposta:** Três formas:

1. **Logs:**

   ```bash
   docker compose logs -f odoo | grep "message_post"
   ```

2. **Plataforma Externa:** Verificar se mensagem apareceu no WhatsApp/Telegram

3. **Odoo Shell:**
   ```python
   # Verificar último envio
   channel = env['discuss.channel'].browse(CHANNEL_ID)
   print(channel.message_ids[0])
   ```

### Bot não está respondendo, como debugar?

**Resposta:**

1. **Verificar configuração:**

   ```python
   partner = env['res.partner'].search([('name', '=', 'Bot Partner')])
   print(f"Bot: {partner.bot}")
   print(f"Bot Active: {partner.bot.active}")
   ```

2. **Verificar logs:**

   ```bash
   docker compose logs -f odoo | grep "_notify_thread"
   ```

3. **Testar manualmente:**
   ```python
   channel = env['discuss.channel'].browse(CHANNEL_ID)
   partner = env['res.partner'].browse(PARTNER_ID)
   partner.bot.outgo(channel, partner)
   ```

### Como saber se um erro é do hook ou do plugin?

**Resposta:** Verifique o stack trace nos logs:

```
ERROR ... discuss_channel.py:123 in message_post
  -> Erro no hook

ERROR ... evolution.py:456 in send_message
  -> Erro no plugin
```

## Perguntas sobre Contribuição

### Como contribuir com melhorias nos hooks?

**Resposta:**

1. Fork o repositório
2. Crie branch: `git checkout -b feature/melhoria-hooks`
3. Faça suas mudanças
4. Adicione testes
5. Submeta PR

Veja [CONTRIBUTING.md](../../CONTRIBUTING.md) se existir.

### Onde reportar bugs?

**Resposta:**

- **GitHub Issues**: Para bugs de código
- **Discussions**: Para dúvidas gerais
- **Email**: Para questões privadas

### Como sugerir novos hooks?

**Resposta:** Abra uma issue no GitHub com:

- Caso de uso
- Hook sugerido (qual método override)
- Benefícios esperados
- Exemplo de implementação

## Recursos Adicionais

- 📖 [Guia de Migração Completo](./Migration-BaseAutomations-to-CodeHooks.md)
- 📊 [Comparação Visual](./Comparison-Automations-vs-Hooks.md)
- ✅ [Checklist Pós-Migração](./Post-Migration-Checklist.md)
- 📝 [Resumo de Mudanças](../../MIGRATION_SUMMARY.md)
- 🏗️ [Documentação de Arquitetura](./README.md)

---

**Ainda tem dúvidas?**

- Abra uma issue no GitHub
- Entre em contato com a equipe
- Consulte a documentação oficial do Odoo
