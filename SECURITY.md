# 🔒 Política de Segurança

## 🎯 Nosso Compromisso

O Shadows leva a segurança e privacidade dos usuários muito a sério. Como um aplicativo que gerencia notas e credenciais criptografadas e monitora atividades de compartilhamento de tela, mantemos padrões rigorosos de segurança.

## 🐛 Reportando Vulnerabilidades

**Se você descobrir uma vulnerabilidade de segurança, por favor, não abra uma issue pública.**

Em vez disso, reporte-a através do seguinte canal:

- **Email:** security@shadows.app
- **PGP Key:** [Disponível em breve]

### O que incluir no report

- **Tipo de vulnerabilidade** (ex: XSS, injeção, vazamento de dados, quebra de criptografia)
- **Passos para reproduzir** — seja o mais específico possível
- **Impacto potencial** — o que um atacante poderia fazer
- **Versão afetada** (comite / tag / versão)
- **Ambiente** (SO, versão do Python, X11 ou Wayland)
- **Sugestão de correção** (se aplicável)

### Processo

1. **Reporte recebido** — confirmaremos em até 48 horas
2. **Análise** — avaliaremos a gravidade e o impacto
3. **Correção** — desenvolveremos um patch no menor tempo possível
4. **Release** — publicaremos uma versão corrigida
5. **Divulgação** — anunciaremos a vulnerabilidade após a correção estar disponível

## 📋 Escopo

### Inclui
- Código-fonte do Shadows (`shadows/`, `main.py`)
- Scripts de instalação (`scripts/`)
- Dependências oficiais
- Infraestrutura do projeto (site, gateway OpenCode)

### Não inclui
- Dependências de terceiros (reporte diretamente aos mantenedores)
- Sistemas operacionais ou ambientes não suportados

## 🛡️ Práticas de Segurança

### Criptografia
- **Algoritmo:** AES-256-GCM (criptografia autenticada)
- **Derivação de chave:** PBKDF2 com 600.000 iterações e SHA-256
- **Cada nota** é criptografada individualmente com nonce único
- **Títulos** são criptografados separadamente do conteúdo

### Detecção de Compartilhamento
- Múltiplas camadas independentes de detecção
- Sem telemetria ou dados enviados para servidores externos
- Overlay de privacidade com proteção automática

### Armazenamento
- Dados armazenados localmente em `~/.shadows/`
- Chave mestra protegida por senha
- Arquivos corrompidos são isolados automaticamente

### Dependências
- Apenas bibliotecas amplamente auditadas (PyQt5, cryptography, psutil)
- Conexões de IA são feitas sob demanda e configuráveis pelo usuário

## 🔐 Divulgação Responsável

Acreditamos em divulgação responsável. Pedimos que:

- **Não explore** a vulnerabilidade além do necessário para confirmá-la
- **Não divulgue** publicamente antes da correção
- **Apague dados sensíveis** coletados durante a investigação

Em troca, nós:
- Responderemos rapidamente
- Manteremos você informado do progresso
- Creditaremos você na divulgação (se desejar)
- Trataremos o report com seriedade e respeito

## 📊 Histórico de Segurança

| Data | Tipo | Severidade | Reportado por | Status |
|------|------|------------|---------------|--------|
| — | — | — | — | Nenhum incidente registrado |

## ⚠️ Ambientes Suportados

O Shadows é suportado apenas em **Linux** com as seguintes configurações:

- **X11** (recomendado para máxima compatibilidade)
- **Wayland** (com PipeWire ≥ 0.3)
- **Python ≥ 3.10**
- Distribuições: Ubuntu, Debian, Fedora, Arch Linux, openSUSE

---

<p align="center">
  <a href="README.md">← Voltar ao README</a>
</p>
