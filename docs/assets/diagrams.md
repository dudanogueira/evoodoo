# Diagramas e Arquitetura 📊

Esta página contém diagramas explicativos da arquitetura e fluxos do Discuss Hub.

## 🏗️ Arquitetura Geral

```mermaid
graph TB
    subgraph "External Services"
        WA[WhatsApp]
        TG[Telegram]
        API[Evolution API]
        CLOUD[WhatsApp Cloud]
    end

    subgraph "Discuss Hub Core"
        WH[Webhook Controller]
        CONN[Connector Model]
        PM[Plugin Manager]

        subgraph "Plugins"
            PE[Evolution Plugin]
            PC[Cloud Plugin]
            PN[NotificaMe Plugin]
            PX[Custom Plugin]
        end
    end

    subgraph "Odoo Core"
        DC[Discuss Channel]
        MM[Mail Message]
        RP[Res Partner]
        BA[Base Automation]
    end

    subgraph "External Tools"
        N8N[N8N Workflows]
        WF[Webhook Flows]
    end

    WA --> API
    API --> WH
    CLOUD --> WH
    TG --> WH

    WH --> CONN
    CONN --> PM
    PM --> PE
    PM --> PC
    PM --> PN
    PM --> PX

    PE --> DC
    PC --> DC
    PN --> DC
    PX --> DC

    DC --> MM
    MM --> RP
    MM --> BA

    N8N --> WF
    WF --> WH

    BA --> CONN
```

## 🔄 Fluxo de Mensagens Recebidas

```mermaid
sequenceDiagram
    participant WA as WhatsApp
    participant API as Evolution API
    participant WH as Webhook Controller
    participant CONN as Connector
    participant PLUGIN as Plugin
    participant CHANNEL as Discuss Channel
    participant MSG as Mail Message

    WA->>API: Mensagem recebida
    API->>WH: POST /webhook/discuss_hub/uuid
    WH->>CONN: find connector by uuid
    CONN->>PLUGIN: get_plugin()
    PLUGIN->>PLUGIN: process_payload()
    PLUGIN->>CHANNEL: find_or_create_channel()
    PLUGIN->>MSG: create message
    MSG->>CHANNEL: notify participants
    CHANNEL-->>WA: Read receipt (opcional)
```

## 📤 Fluxo de Mensagens Enviadas

```mermaid
sequenceDiagram
    participant USER as Usuário Odoo
    participant CHANNEL as Discuss Channel
    participant AUTO as Base Automation
    participant CONN as Connector
    particle PLUGIN as Plugin
    participant API as Evolution API
    participant WA as WhatsApp

    USER->>CHANNEL: Digita mensagem
    CHANNEL->>AUTO: Trigger on message create
    AUTO->>CONN: outgo_message()
    CONN->>PLUGIN: outgo_message()
    PLUGIN->>API: POST /message/sendText
    API->>WA: Envia mensagem
    WA-->>API: Confirmação
    API-->>PLUGIN: Response
    PLUGIN-->>CONN: Result
```

## 🔌 Ciclo de Vida do Plugin

```mermaid
stateDiagram-v2
    [*] --> Init: Connector Created
    Init --> Loading: get_plugin()
    Loading --> Ready: Plugin Loaded
    Ready --> Processing: Webhook Received
    Processing --> Ready: Success
    Processing --> Error: Exception
    Error --> Ready: Error Handled
    Ready --> Stopping: Connector Disabled
    Stopping --> [*]: Plugin Unloaded

    Ready --> StatusCheck: get_status()
    StatusCheck --> Ready: Status Updated

    Ready --> Sending: outgo_message()
    Sending --> Ready: Message Sent
    Sending --> Error: Send Failed
```

## 📱 Arquitetura do Plugin Evolution

```mermaid
graph TD
    subgraph "WhatsApp Ecosystem"
        WA[WhatsApp Mobile]
        WEB[WhatsApp Web]
    end

    subgraph "Evolution API"
        INST[Instance Manager]
        SESS[Session Handler]
        WS[WebSocket Manager]
        QR[QR Code Generator]
    end

    subgraph "Evolution Plugin"
        STATUS[Status Monitor]
        PROC[Payload Processor]
        SENDER[Message Sender]
        CONTACT[Contact Sync]
    end

    subgraph "Odoo Integration"
        CONN[Connector Model]
        CHAN[Discuss Channels]
        PART[Partners/Contacts]
    end

    WA <--> INST
    WEB <--> INST
    INST --> SESS
    SESS --> WS
    SESS --> QR

    WS --> STATUS
    WS --> PROC
    STATUS --> CONN
    PROC --> CHAN
    PROC --> PART

    SENDER --> INST
    CONTACT --> PART
```

## 🌐 Fluxo de Webhooks N8N

```mermaid
flowchart TD
    START([Webhook Recebido]) --> VALIDATE{Validar Payload}
    VALIDATE -->|Válido| ROUTE[Rotear por Tipo]
    VALIDATE -->|Inválido| ERROR[Log Error & Exit]

    ROUTE --> MSG[Processar Mensagem]
    ROUTE --> STATUS[Atualizar Status]
    ROUTE --> CONTACT[Sincronizar Contato]

    MSG --> CHANNEL{Canal Existe?}
    CHANNEL -->|Não| CREATE[Criar Canal]
    CHANNEL -->|Sim| UPDATE[Usar Canal Existente]

    CREATE --> NOTIFY[Notificar Usuários]
    UPDATE --> NOTIFY

    STATUS --> QRCODE{QR Code?}
    QRCODE -->|Sim| DISPLAY[Exibir QR Code]
    QRCODE -->|Não| CONTINUE[Continuar Fluxo]

    CONTACT --> PARTNER{Partner Existe?}
    PARTNER -->|Não| CREATEP[Criar Partner]
    PARTNER -->|Sim| UPDATEP[Atualizar Partner]

    NOTIFY --> END([Finalizar])
    DISPLAY --> END
    CONTINUE --> END
    CREATEP --> END
    UPDATEP --> END
    ERROR --> END
```

## 🔒 Fluxo de Autenticação

```mermaid
sequenceDiagram
    participant USER as Usuário
    participant ODOO as Odoo Connector
    participant PLUGIN as Evolution Plugin
    participant API as Evolution API
    participant WA as WhatsApp

    USER->>ODOO: Criar Connector
    ODOO->>PLUGIN: get_status()
    PLUGIN->>API: GET /instance/status

    alt Instance Not Found
        API-->>PLUGIN: 404 Not Found
        PLUGIN->>API: POST /instance/create
        API-->>PLUGIN: Instance Created
        PLUGIN->>API: GET /instance/status
    end

    API-->>PLUGIN: Status + QR Code
    PLUGIN-->>ODOO: Display QR
    ODOO-->>USER: Show QR Code

    USER->>WA: Scan QR Code
    WA->>API: Authentication
    API->>PLUGIN: Webhook: connection.update
    PLUGIN->>ODOO: Status: Connected
    ODOO-->>USER: Connection Successful
```

## 📊 Modelo de Dados

```mermaid
erDiagram
    CONNECTOR {
        id integer
        name string
        type string
        enabled boolean
        url string
        api_key string
        uuid string
    }

    CHANNEL {
        id integer
        name string
        discuss_hub_connector_id integer
        discuss_hub_outgoing_destination string
    }

    MESSAGE {
        id integer
        body text
        model string
        res_id integer
        discuss_hub_message_id string
        author_id integer
    }

    PARTNER {
        id integer
        name string
        phone string
        email string
        image_1920 binary
    }

    CONNECTOR ||--o{ CHANNEL : "manages"
    CHANNEL ||--o{ MESSAGE : "contains"
    PARTNER ||--o{ MESSAGE : "authors"
    PARTNER ||--o{ CHANNEL : "participates"
```

---

## 🎨 Configuração do Mermaid

Para visualização adequada no Obsidian, instale o plugin "Mermaid" e configure:

```json
{
  "theme": "default",
  "themeVariables": {
    "primaryColor": "#4f46e5",
    "primaryTextColor": "#1f2937",
    "primaryBorderColor": "#6b7280",
    "lineColor": "#9ca3af",
    "sectionBkColor": "#f9fafb",
    "altSectionBkColor": "#ffffff",
    "gridColor": "#e5e7eb"
  }
}
```

---

## 🔗 Links Relacionados

- [[README|Documentação Principal]]
- [[Plugin Development|Desenvolvimento de Plugins]]
- [[Evolution Plugin|Plugin Evolution]]
- [[Troubleshooting|Solução de Problemas]]

---

_Última atualização: 24 de Setembro de 2025_
