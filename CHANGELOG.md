# 📋 Changelog

Todas as mudanças notáveis no **Shadows** serão documentadas aqui.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e este projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

---

## [1.0.0] — 2025-06-15

### ✨ Adicionado

#### 🕵️ Detecção de Screen Sharing
- **4 camadas de detecção**: processos, PipeWire (Wayland), DBus portal, X11 atoms
- Monitoramento em tempo real com timers configuráveis (2-5s)
- Detecção de ~60 aplicativos conhecidos (Zoom, Teams, OBS, Discord, etc.)
- Detecção de navegadores com flags de captura (Chrome, Firefox, Brave, etc.)
- Indicador visual na barra de ferramentas com estado "Protegido" / "Compartilhando"

#### 🔐 Cofre Criptografado
- Criptografia AES-256-GCM com PBKDF2 (600.000 iterações)
- Suporte a criação e gerenciamento de notas
- Títulos criptografados separadamente para exibição segura
- Sistema de login com criação de senha mestra na primeira execução
- Troca de senha mestra
- Exportação de notas para `.txt` / `.md`
- Arquivos corrompidos são isolados automaticamente

#### 🎨 Interface Gráfica
- Tema escuro Fusion com paleta personalizada (#1a1a2e, #e94560)
- Editor de notas com busca e lista lateral
- Barra de ferramentas com ações rápidas
- **Ícone na bandeja do sistema** com menu contextual
- Overlay de privacidade com gradiente e efeito visual
- Botão "Revelar" com confirmação de segurança
- Barra de status com contagem de notas e estado de compartilhamento
- Atalhos de teclado (Ctrl+N, Ctrl+S, Ctrl+F, Ctrl+I, Delete, Escape)
- Minimizar para bandeja em vez de fechar

#### 🤖 Assistente IA
- **Tradutor integrado** para 16 idiomas
- **Assistente conversacional** com contexto das notas (RAG)
- 4 provedores suportados: Ollama, OpenAI, Gemini, OpenCode
- Detecção automática de provedores via variáveis de ambiente
- Configurações persistentes em `~/.shadows/settings.json`
- Painel IA com chat, toggle rápido e configuração dedicada

#### 🐧 Infraestrutura Linux
- Script de instalação de dependências para 4 distribuições
- Suporte a X11 e Wayland
- Integração com PipeWire e DBus para detecção
- CLI com `--detect` para verificação one-shot
- Instalação via pip (`shadows` command)

### 🛠️ Técnico
- Projeto estruturado com `pyproject.toml` e `setuptools`
- Type hints em todo o código
- Testes unitários com pytest (detector + storage)
- Logging estruturado com níveis DEBUG/INFO
- Cobertura de código mensurada via pytest-cov

---

## [0.1.0] — 2025-01-15

### ✨ Adicionado

- Protótipo inicial do detector de screen sharing
- Estrutura básica do projeto com PyQt5
- CLI experimental com `--detect`

---

> **Nota:** Versões anteriores a 1.0.0 são internas e não possuem changelog completo.

<!-- Links -->
[1.0.0]: https://github.com/ElioNeto/shadows/releases/tag/v1.0.0
[0.1.0]: https://github.com/ElioNeto/shadows/releases/tag/v0.1.0
