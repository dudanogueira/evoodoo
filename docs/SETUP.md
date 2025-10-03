# Documentação do Discuss Hub - Configuração

## Sobre esta Documentação

Esta documentação foi criada para ser **otimizada para Obsidian** e inclui:

- **Links bidirecionais** com `[[Nome do Arquivo]]`
- **Suporte multi-idioma** (Português e Inglês)
- **Diagramas Mermaid** para visualização de arquitetura
- **Estrutura modular** para fácil navegação
- **Tags e metadados** para organização

## Como Usar no Obsidian

1. **Abra o Obsidian**
2. **Open folder as vault** → Selecione a pasta `docs/`
3. **Instalar plugins recomendados**:
   - Mermaid (para diagramas)
   - Advanced Tables (para tabelas)
   - Tag Wrangler (para gerenciar tags)

## Estrutura

```
docs/
├── README.md                    # Índice principal
├── .obsidian/                   # Configurações do Obsidian
│   ├── app.json                 # Configurações da aplicação
│   └── workspace.json           # Layout do workspace
├── pt-br/                       # Documentação em português
│   ├── README.md               # Documentação principal PT-BR
│   ├── Evolution Plugin.md     # Plugin Evolution
│   ├── Plugin Development.md   # Guia de desenvolvimento
│   └── Troubleshooting.md      # Solução de problemas
├── en/                          # Documentação em inglês
│   ├── README.md               # Main documentation EN
│   ├── Evolution Plugin.md     # Evolution Plugin
│   └── Plugin Development.md   # Development guide
└── assets/                      # Recursos compartilhados
    └── diagrams.md             # Diagramas Mermaid
```

## Convenções

### Links Internos

- Use `[[Nome do Arquivo]]` para links entre documentos
- Use `[[Nome do Arquivo#Seção]]` para links para seções específicas
- Use `[[Nome do Arquivo|Texto do Link]]` para texto customizado

### Idiomas

- Arquivos em português: pasta `pt-br/`
- Arquivos em inglês: pasta `en/`
- Recursos compartilhados: pasta `assets/`

### Emojis e Icons

- 📚 Documentação
- 🔥 Recursos principais/populares
- 🛠️ Desenvolvimento/Técnico
- 🔧 Troubleshooting/Debug
- ⚡ Quick Start/Performance
- 🔐 Segurança
- 🌐 Links externos/Web

### Tags

Use tags para categorizar conteúdo:

- `#DiscussHub` - Tag principal do projeto
- `#Plugin` - Relacionado a plugins
- `#Development` - Desenvolvimento
- `#API` - Referência de API
- `#Troubleshooting` - Solução de problemas

## Manutenção

### Atualizações

- **Sempre** atualize ambos os idiomas (PT-BR e EN)
- **Verifique** links internos após renomear arquivos
- **Teste** diagramas Mermaid após mudanças
- **Mantenha** consistência na estrutura

### Versionamento

- Inclua data de atualização no final de cada documento
- Use versionamento semântico para mudanças importantes
- Documente breaking changes claramente

### Contribuições

1. Crie branch para documentação: `docs/nova-feature`
2. Atualize ambos os idiomas
3. Teste no Obsidian antes do PR
4. Inclua screenshots se necessário

## Configurações Recomendadas do Obsidian

### Plugins Essenciais

- **Mermaid**: Renderização de diagramas
- **Table Editor**: Edição de tabelas
- **Tag Wrangler**: Gerenciamento de tags
- **Advanced Tables**: Tabelas avançadas
- **Templater**: Templates para novos documentos

### Configurações de Aparência

- **Theme**: Default ou Minimal
- **Line Numbers**: Habilitado para código
- **Readable Line Length**: Habilitado
- **Spell Check**: Habilitado (EN + PT-BR)

### Atalhos Úteis

- `Ctrl+O`: Quick Switcher (abrir arquivo)
- `Ctrl+Shift+F`: Busca global
- `Ctrl+G`: Abrir graph view
- `Ctrl+E`: Alternar edit/preview mode

## Backup e Sincronização

### Git

- **Sempre** fazer commit das mudanças na documentação
- **Usar** mensagens de commit descritivas
- **Incluir** arquivos `.obsidian/` no controle de versão

### Obsidian Sync (Opcional)

- Configure Obsidian Sync para sincronizar entre dispositivos
- Exclua arquivos temporários do sync
- Mantenha backup local regular

---

_Configuração criada em: 24 de Setembro de 2025_
