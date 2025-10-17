# Migração de Automações Base para Hooks Nativos de Código

## Visão Geral

Este documento descreve a migração das automações base do Odoo para hooks nativos em
Python para gerenciar integrações de webhook no Discuss Hub.

## Por Que Esta Mudança?

**Benefícios dos hooks nativos de código:**

1. **Melhor Performance**: Chamadas diretas de métodos evitam overhead de avaliação de
   automações
2. **Debug Mais Fácil**: Stack traces mostram exatamente onde o código executa
3. **Melhor Controle**: Fluxo de controle explícito ao invés de gatilhos implícitos de
   automação
4. **Testes Mais Fáceis**: Pode testar métodos diretamente sem configurar contexto de
   automação
5. **Manutenibilidade**: Toda lógica em arquivos Python, mais fácil de versionar e
   revisar

**Abordagem Anterior (Automações Base):**

- Requeria arquivos XML com regras de automação
- Lógica dividida entre configuração XML e trechos de código Python
- Mais difícil de debugar (automações disparam implicitamente)
- Overhead de performance da avaliação do motor de automações

## Detalhes de Implementação

### 1. Mensagens de Saída (discuss.channel)

**Antes:** Automação base em `discuss.channel` com gatilho `on_message_sent`

**Depois:** Override do método `message_post()` no modelo `discuss.channel`

**Localização:** `discuss_hub/models/discuss_channel.py`

```python
@api.returns("mail.message", lambda value: value.id)
def message_post(self, **kwargs):
    """
    Override message_post para lidar com mensagens de saída para conectores externos.
    Isso substitui a automação base para mensagens de saída.
    """
    # Chama o método pai primeiro para criar a mensagem
    message = super().message_post(**kwargs)

    # Processa mensagem de saída para o conector
    if self.discuss_hub_connector and message:
        try:
            _logger.info(
                f"discuss_channel.message_post: enviando mensagem de saída ({message}) para {self}"
            )
            self.discuss_hub_connector.outgo_message(channel=self, message=message)
        except Exception as e:
            _logger.error(
                f"Erro ao enviar mensagem de saída para o conector: {e}", exc_info=True
            )

    return message
```

**Pontos Chave:**

- Sempre chama `super().message_post()` primeiro para manter comportamento normal do
  Odoo
- Só processa se o canal tiver um `discuss_hub_connector`
- Envolve em try-except para prevenir que erros quebrem o envio de mensagens
- Logging para debug e monitoramento

### 2. Automação de Bot (discuss.channel)

**Antes:** Automação base em `discuss.channel` com gatilho `on_message_received`

**Depois:** Override do método `_notify_thread()` no modelo `discuss.channel`

**Localização:** `discuss_hub/models/discuss_channel.py`

```python
def _notify_thread(self, message, msg_vals=False, **kwargs):
    """
    Override _notify_thread para lidar com automação de bot para mensagens recebidas.
    Isso substitui a automação base para bot outgoing.
    """
    # Chama método pai
    result = super()._notify_thread(message, msg_vals=msg_vals, **kwargs)

    # Processa automação de bot
    partners_with_bot = self.channel_partner_ids.filtered(lambda p: p.bot)
    if partners_with_bot:
        try:
            _logger.info(
                f"discuss_channel._notify_thread: processando bot para {len(partners_with_bot)} parceiros"
            )
            for partner in partners_with_bot:
                partner.bot.outgo(self, partner)
        except Exception as e:
            _logger.error(f"Erro ao processar automação de bot: {e}", exc_info=True)

    return result
```

**Pontos Chave:**

- `_notify_thread` é chamado quando mensagens são recebidas/processadas
- Sempre chama `super()._notify_thread()` primeiro
- Filtra parceiros com bots e processa cada um
- Tratamento de erro para prevenir que erros de bot quebrem o fluxo de mensagens

### 3. Reações de Saída (mail.message.reaction)

**Antes:** Automação base em `mail.message.reaction` com gatilho `on_create_or_write`

**Depois:** Override dos métodos `create()` e `write()` em novo modelo

**Localização:** `discuss_hub/models/mail_message_reaction.py` (novo arquivo)

```python
@api.model_create_multi
def create(self, vals_list):
    """
    Override create para lidar com reações de saída.
    Isso substitui o gatilho de automação base on_create_or_write.
    """
    # Chama método pai para criar a(s) reação(ões)
    reactions = super().create(vals_list)

    # Processa cada reação para notificação do conector
    for reaction in reactions:
        if reaction.message_id and reaction.message_id.discuss_hub_message_id:
            try:
                channel = self.env["discuss.channel"].search(
                    [("id", "=", reaction.message_id.res_id)], limit=1
                )
                if channel and channel.discuss_hub_connector:
                    _logger.info(
                        f"mail_message_reaction.create: connector:{channel.discuss_hub_connector} "
                        f"channel:{channel} reaction {reaction} to message {reaction.message_id}"
                    )
                    channel.discuss_hub_connector.outgo_reaction(
                        channel, reaction.message_id, reaction
                    )
            except Exception as e:
                _logger.error(
                    f"Erro ao enviar reação de saída para o conector: {e}",
                    exc_info=True,
                )

    return reactions
```

**Pontos Chave:**

- Usa decorator `@api.model_create_multi` para suportar criação em lote
- Verifica se mensagem tem `discuss_hub_message_id` (indica mensagem externa)
- Encontra o canal e conector antes de enviar reação
- Método `write()` similar para atualizações de reação

## Passos de Migração

### Para Instalações Existentes:

1. **Atualizar o código:**

   ```bash
   git pull origin 18.0
   ```

2. **Reiniciar Odoo:**

   ```bash
   docker compose -f compose-dev.yaml restart odoo
   ```

3. **Atualizar o módulo:**

   ```bash
   # Via UI: Apps -> Discuss Hub -> Atualizar
   # Ou via CLI:
   docker compose -f compose-dev.yaml exec odoo odoo -u discuss_hub --stop-after-init
   ```

4. **Verificar que automações estão desabilitadas:**

   - Ir em Configurações -> Técnico -> Automação -> Ações Automatizadas
   - Buscar por "discuss_hub"
   - Verificar que todas as três automações aparecem como "Inativo" ou "DEPRECATED"

5. **Testar funcionalidade:**
   - Enviar mensagem do Odoo para canal externo
   - Enviar mensagem de canal externo para Odoo
   - Adicionar reação a uma mensagem
   - Testar respostas de bot

### Para Novas Instalações:

Os hooks de código são automaticamente ativos. As automações base obsoletas estão
configuradas com `active=0` e não interferirão.

## Testes

### Testes Manuais:

1. **Mensagens de Saída:**

   ```
   1. Abrir canal conectado a discuss_hub connector
   2. Enviar mensagem
   3. Verificar logs para: "discuss_channel.message_post: enviando mensagem de saída"
   4. Verificar que mensagem aparece na plataforma externa (WhatsApp, Telegram, etc.)
   ```

2. **Automação de Bot:**

   ```
   1. Configurar bot para um parceiro
   2. Enviar mensagem para canal com esse parceiro
   3. Verificar logs para: "discuss_channel._notify_thread: processando bot"
   4. Verificar que resposta do bot é enviada
   ```

3. **Reações:**
   ```
   1. Encontrar mensagem de plataforma externa (tem discuss_hub_message_id)
   2. Adicionar reação no Odoo
   3. Verificar logs para: "mail_message_reaction.create: connector"
   4. Verificar que reação aparece na plataforma externa
   ```

### Testes Automatizados:

Os testes devem continuar funcionando sem mudanças, pois testam a API pública
(`message_post`, reações, etc.) que permanece a mesma.

## Resolução de Problemas

### Mensagens não enviando para plataforma externa:

1. Verificar se canal tem `discuss_hub_connector` configurado
2. Verificar logs para erros no método `message_post`
3. Verificar que conector está habilitado e configurado corretamente

### Bot não respondendo:

1. Verificar se parceiro tem bot configurado
2. Verificar logs para erros no método `_notify_thread`
3. Verificar que bot está ativo e configurado corretamente

### Reações não sincronizando:

1. Verificar se mensagem tem campo `discuss_hub_message_id` populado
2. Verificar logs para erros em `mail_message_reaction.create` ou `write`
3. Verificar que conector suporta reações

## Rollback (se necessário)

Se precisar reverter para automações base:

1. Editar `discuss_hub/datas/base_automation.xml` e configurar `active=1` para todas
   automações
2. Comentar os métodos override em:
   - `discuss_hub/models/discuss_channel.py` (`message_post` e `_notify_thread`)
   - `discuss_hub/models/mail_message_reaction.py` (arquivo inteiro)
3. Reiniciar Odoo e atualizar o módulo

## Considerações de Performance

**Melhorias esperadas:**

- Redução de uso de CPU da avaliação do motor de automações
- Envio de mensagens mais rápido (chamada direta de método vs lookup de automação)
- Redução de consultas ao banco (sem avaliação de domínio de automação)

**Monitoramento:**

- Verificar logs do Odoo para informações de timing
- Monitorar uso de memória (deve ser similar ou melhor)
- Observar novos erros nos logs

## Melhorias Futuras

Possíveis melhorias para o futuro:

1. **Processamento Assíncrono:** Usar queue jobs do Odoo para chamadas de webhook
   evitando bloqueio
2. **Processamento em Lote:** Agrupar múltiplas reações/mensagens quando possível
3. **Circuit Breaker:** Implementar lógica de retry com backoff exponencial
4. **Monitoramento:** Adicionar coleta de métricas para taxas de sucesso/falha de
   webhooks

## Referências

- [Métodos de Modelo Odoo](https://www.odoo.com/documentation/18.0/developer/reference/backend/orm.html#model)
- [Envio de Mensagens](https://www.odoo.com/documentation/18.0/developer/reference/backend/mixins.html#mail-thread)
- [Ações Automatizadas](https://www.odoo.com/documentation/18.0/applications/studio/automated_actions.html)
