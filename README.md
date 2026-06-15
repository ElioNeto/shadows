
<h1 align="center">🛡️ Shadows</h1>

<p align="center">
  <em>Proteja seu conteúdo durante compartilhamento de tela</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/versão-1.0.0-blue" alt="Versão">
  <img src="https://img.shields.io/badge/python-≥3.10-blue" alt="Python">
  <img src="https://img.shields.io/badge/licença-MIT-green" alt="Licença">
  <img src="https://img.shields.io/badge/plataforma-Linux-red" alt="Linux">
  <img src="https://img.shields.io/badge/interface-PyQt5-orange" alt="PyQt5">
</p>

---

## 📋 Sobre

**Shadows** é um aplicativo desktop para Linux que **detecta automaticamente quando você está compartilhando ou gravando a tela** e oculta conteúdo sensível para proteger sua privacidade durante apresentações, reuniões e gravações.

Combinando um cofre criptografado de notas e credenciais com um sistema de detecção multi-camadas, o Shadows garante que suas informações particulares nunca apareçam acidentalmente em uma transmissão.

---

## ✨ Funcionalidades

### 🕵️ Detecção de Compartilhamento em Tempo Real
O Shadows monitora continuamente o sistema usando **4 camadas de detecção**:

| Camada | Método | Plataforma |
|--------|--------|------------|
| **1. Processos** | Escaneia processos em busca de apps conhecidos (Zoom, Teams, OBS, Discord, etc.) | X11 + Wayland |
| **2. PipeWire** | Analisa `pw-dump` em busca de nós de captura de tela | Wayland |
| **3. DBus** | Consulta o portal `org.freedesktop.portal.ScreenCast` | Wayland |
| **4. X11** | Inspeciona janelas via `xprop` e `xdotool` | X11 |

Quando o compartilhamento é detectado, uma **overlay de privacidade** cobre automaticamente o conteúdo sensível.

### 🔐 Cofre Criptografado
- Armazenamento seguro de notas e credenciais
- Criptografia **AES-256-GCM** (padrão militar)
- Protegido por **senha mestra**
- Cada nota é criptografada individualmente
- Títulos são criptografados separadamente para exibição segura na lista

### 🤖 Assistente IA
- **Tradução integrada** de notas entre 16 idiomas
- **Assistente conversacional** para consultar suas notas (RAG)
- Provedores suportados:
  - **Ollama** (local, gratuito, padrão)
  - **OpenAI** (GPT-4o, GPT-4o-mini)
  - **Gemini** (Google)
  - **OpenCode Gateway** (gratuito)

### 🎨 Interface Moderna
- Tema escuro Fusion com paleta personalizada
- Busca e organização de notas
- Indicador visual de compartilhamento
- **Ícone na bandeja do sistema** para operação discreta
- Atalhos de teclado (`Ctrl+N`, `Ctrl+S`, `Ctrl+F`, `Ctrl+I`)
- Exportação de notas para `.txt` / `.md`

---

## 🚀 Instalação

### Pré-requisitos

- **Linux** (X11 ou Wayland)
- **Python ≥ 3.10**
- **pip**

### 1. Instalar dependências do sistema

```bash
sudo bash scripts/setup-system-deps.sh
```

O script detecta automaticamente sua distribuição e instala os pacotes necessários:

- Ubuntu/Debian, Fedora, Arch Linux, openSUSE

> **Dependências principais:** PyQt5, psutil, cryptography, dbus-python, xdotool, PipeWire, WirePlumber

### 2. Instalar pacotes Python

```bash
pip install -r requirements.txt
```

Ou instale o pacote em modo editável:

```bash
pip install -e .
```

---

## 🏃 Uso

### Interface Gráfica

```bash
python main.py
```

Ou após instalação:

```bash
shadows
```

Na **primeira execução**, você criará uma senha mestra para seu cofre.

### Modo Detect (one-shot)

```bash
python main.py --detect
```

Escaneia o sistema uma vez e exibe o resultado no terminal — útil para scripts ou verificação rápida.

### Ajuda

```bash
python main.py --help
```

---

## ⌨️ Atalhos de Teclado

| Atalho | Ação |
|--------|------|
| `Ctrl+N` | Nova nota |
| `Ctrl+S` | Salvar nota |
| `Ctrl+F` | Buscar notas |
| `Ctrl+I` | Alternar painel IA |
| `Delete` | Excluir nota |
| `Escape` | Minimizar para bandeja |

---

## ⚙️ Configuração da IA

O Shadows detecta automaticamente provedores de IA do ambiente:

- **`OPENAI_API_KEY`** — usa OpenAI (ou OpenRouter)
- **`GOOGLE_API_KEY`** / **`GEMINI_API_KEY`** — usa Gemini
- **`TEAMCODE_API_KEY`** — usa o gateway gratuito do OpenCode

Para usar **Ollama** (local), nenhuma chave é necessária — apenas tenha o servidor rodando:

```bash
ollama pull llama3.2
ollama serve
```

As configurações podem ser ajustadas na interface em **⚙ IA** (painel de configurações).

---

## 🧪 Testes

```bash
pytest
```

Para testes com cobertura:

```bash
pytest --cov=shadows
```

---

## 📁 Estrutura do Projeto

```
shadows-app/
├── main.py                  # Ponto de entrada principal / CLI
├── pyproject.toml           # Configuração do projeto
├── requirements.txt         # Dependências Python
├── scripts/
│   └── setup-system-deps.sh # Instalador de dependências do SO
├── shadows/
│   ├── __init__.py          # Metadados do pacote
│   ├── __main__.py          # Entry point `python -m shadows`
│   ├── ai.py                # Tradução e assistente IA (Ollama, OpenAI, Gemini, OpenCode)
│   ├── detector.py          # Detector multi-camadas de screen sharing
│   ├── overlay.py           # Overlay de privacidade
│   ├── storage.py           # Cofre criptografado AES-256-GCM
│   └── ui.py                # Interface gráfica (PyQt5)
└── tests/
    ├── test_detector.py     # Testes do detector
    └── test_storage.py      # Testes do cofre
```

---

## 🛡️ Como Funciona a Proteção

1. O **detector** monitora o sistema em intervalos regulares (2-5 segundos)
2. Ao identificar compartilhamento de tela, emite um sinal
3. A **overlay de privacidade** cobre imediatamente o conteúdo do cofre
4. O conteúdo permanece oculto até que o compartilhamento termine
5. Opção "Revelar" disponível com confirmação para uso consciente

---

## 🔒 Segurança

- **Criptografia:** AES-256-GCM com PBKDF2 (600.000 iterações)
- **Armazenamento:** Cada nota é um arquivo individual criptografado
- **Senha mestra:** Protege todo o cofre; sem ela, os dados são ilegíveis
- **Modo de bloqueio:** Trava o cofre e retorna à tela de login
- **Detecção de corrupção:** Arquivos corrompidos são isolados automaticamente

---

## 📄 Licença

Distribuído sob a licença MIT. Veja o arquivo `LICENSE` para mais informações.

---

<p align="center">
  Feito com ❤️ para privacidade digital
</p>
