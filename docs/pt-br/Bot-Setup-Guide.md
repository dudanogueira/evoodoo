# Guia de Configuração do Bot Manager

Este guia explica como configurar corretamente o Bot Manager para que ele seja acionado
automaticamente ao receber mensagens.

## Pré-requisitos

- Conector criado e configurado (WhatsApp, Telegram, etc.)
- Acesso administrativo ao Odoo

## Passo a Passo

### 1. Criar o Bot Manager

1. Navegue para **Discuss Hub → Bots/Agents**
2. Clique em **Novo**
3. Configure os campos:

   - **Active**: ✓ (marcar como ativo)
   - **Bot Type**: Escolha entre `generic` ou `typebot`
   - **Bot URL**: URL da API do bot
   - **Bot API Key**: Chave de API (se necessário)
   - **Bot URL Timeout**: Tempo limite em segundos (padrão: 10)
   - **Respond to Internal Direct Messages**: ✓ (padrão - permite que agentes usem o bot
     via DM)
   - **On Error Message**: Mensagem a enviar em caso de erro

4. Salve o registro

### 2. Criar um Parceiro para o Bot

1. Navegue para **Contatos → Contatos**
2. Crie um novo contato ou selecione um existente
3. No formulário do parceiro:
   - **Nome**: Ex: "Bot de Atendimento"
   - **Bot Manager**: Selecione o bot criado no passo 1
4. Salve o parceiro

### 3. Configurar o Conector

1. Navegue para **Discuss Hub → Connectors**
2. Abra o conector onde deseja ativar o bot
3. Na seção de configuração:
   - **Automatic Added Partners**: Adicione o parceiro criado no passo 2
4. Salve o conector

## Como Funciona

Quando uma mensagem chega de um canal externo:

```
Webhook → Plugin → Channel.message_post()
    ↓
_notify_thread() verifica se autor é usuário INTERNO (base.group_user)
    ↓
Se NÃO for interno (externo/portal/público): processa bot
    ↓
Se houver parceiros com bot no canal: partner.bot.outgo(channel, partner)
    ↓
Bot processa e responde (com discuss_hub_skip_bot=True para evitar loop)
```

### Importante sobre Tipos de Usuário

O bot é acionado para:

- ✅ **Usuários externos** (sem conta no Odoo) → Sempre
- ✅ **Usuários portal** (clientes com acesso limitado) → Sempre
- ✅ **Usuários públicos** (acesso público) → Sempre
- ⚠️ **Usuários internos** (agentes/funcionários com `base.group_user`):
  - ✅ Em **mensagens diretas** (DM/chat com o bot) → **Configurável** (campo
    `Respond to Internal Direct Messages`)
  - ❌ Em **canais de grupo** (atendimento ao cliente) → **Nunca** (não configurável)

**Por que essa diferença?**

- Em canais de grupo (atendimento), agentes humanos conversam com clientes. Se o bot
  respondesse a cada mensagem do agente, causaria loops e confusão.
- Em mensagens diretas, agentes podem querer testar ou usar o bot diretamente. Isso é
  **configurável por bot**.

### Configuração: Respond to Internal Direct Messages

Por padrão, o bot responde a mensagens diretas de usuários internos. Você pode
desabilitar isso:

1. Abra o Bot Manager
2. Desmarque **Respond to Internal Direct Messages**
3. Salve

Quando desabilitado:

- Agentes NÃO podem enviar DM para o bot
- Apenas usuários externos/portal/público acionam o bot
- Útil para bots que só devem atender clientes

Isso evita loops infinitos onde respostas de agentes acionariam o bot em canais de
atendimento.

### Configuração de Usuários Automáticos

No conector, você pode configurar `Create User for Visitor`:

- **Do not Create User**: Visitantes não terão conta (padrão) → ✅ Bot acionado
- **Create Portal User**: Cria usuário portal para visitantes → ✅ Bot acionado
- **Create Guest User**: Cria usuário guest para visitantes (sem login, apenas chat) →
  ✅ Bot acionado

Em todos os casos, o bot será acionado pois nenhum desses é usuário interno.

### Verificação de Debug

Para verificar se o bot está sendo acionado, procure nos logs:

```bash
# Logs esperados:
discuss_channel._notify_thread: checking bot automation for [Nome do Canal]
    - channel has X partners, Y with bot configured

discuss_channel._notify_thread: processing bot for Y partners: ['Nome do Parceiro']

Bot X (generic/typebot): outgo called for channel [Nome] and partner [Nome]

Bot X (generic/typebot): processing message Y from [Autor]: [Mensagem]...
```

Se você vir:

```
discuss_channel._notify_thread: skipping bot processing - message from internal user [Nome]
```

Isso significa que a mensagem veio de um **usuário interno** (agente) e o bot não foi
acionado (comportamento esperado).

### Testando o Bot

1. **Envie uma mensagem do canal externo** (WhatsApp, Telegram, etc.)
   - ✅ Bot deve ser acionado (usuário externo em canal de grupo)
2. **Responda como agente interno no Odoo** (no canal de atendimento)
   - ❌ Bot NÃO deve ser acionado (usuário interno em canal de grupo - evita loop)
3. **Cliente responde novamente**

   - ✅ Bot deve ser acionado novamente (usuário externo)

4. **Agente envia DM direto para o bot** (com configuração habilitada)

   - ✅ Bot deve responder (usuário interno em canal tipo chat + bot configurado para
     responder)

5. **Agente envia DM direto para o bot** (com configuração desabilitada)
   - ❌ Bot NÃO responde (usuário interno + bot configurado para NÃO responder DMs
     internas)

**Tipos de Canal**:

- `channel_type='group'` → Canais de atendimento ao cliente (usuários internos **NUNCA**
  acionam bot)
- `channel_type='chat'` → Mensagens diretas/DMs (usuários internos acionam **SE**
  `respond_to_internal_direct_messages=True`)

### Solução de Problemas

#### Bot não está sendo acionado

1. **Verifique se o parceiro tem bot configurado**:
   - Abra o parceiro em Contatos
   - Confirme que o campo "Bot Manager" está preenchido
2. **Verifique se o parceiro está nos automatic_added_partners**:

   - Abra o Conector
   - Confirme que o parceiro com bot está em "Automatic Added Partners"

3. **Verifique se o bot está ativo**:

   - Abra Bots/Agents
   - Confirme que o campo "Active" está marcado

4. **Verifique os logs do Odoo**:
   ```bash
   docker compose -f compose-dev.yaml logs -f odoo
   ```

#### Bot responde mas mensagem não é enviada

- Verifique a configuração da URL do bot
- Teste a URL do bot manualmente
- Verifique os logs para erros de timeout ou conexão

## Tipos de Bot

### Generic Bot

- Envia POST HTTP com payload JSON
- Espera resposta JSON com campo `text` ou array de mensagens
- Suporta anexos (imagens, áudio, vídeo)

Exemplo de payload enviado:

```json
{
  "message_body": "Olá",
  "message_author_name": "João Silva",
  "message_author_id": 123,
  "channel_id": 456
}
```

### Typebot Bot

- Integração completa com Typebot.io
- Gerenciamento de sessões
- Suporte a conversas contextuais
- Suporte a mídias (imagens, áudio, vídeo)

## Configuração Avançada

### Múltiplos Bots

Você pode ter múltiplos parceiros com bots diferentes no mesmo canal:

1. Crie múltiplos Bot Managers
2. Crie múltiplos parceiros, cada um associado a um bot diferente
3. Adicione todos os parceiros em "Automatic Added Partners"

Quando uma mensagem chegar, **todos** os bots serão acionados em sequência.

### Bot condicional via Teams

Para distribuir mensagens entre agentes humanos e bots:

1. Configure um Routing Team com agentes
2. Configure Automatic Added Teams no conector
3. O sistema distribuirá mensagens entre agentes e bots

## Referências

- [Plugin Development](./Plugin%20Development.md)
- [Evolution Plugin](./Evolution%20Plugin.md)
- [Troubleshooting](./Troubleshooting.md)
