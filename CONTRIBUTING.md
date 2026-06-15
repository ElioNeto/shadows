# 🤝 Contribuindo com o Shadows

Obrigado por considerar contribuir com o **Shadows**! Este documento contém as diretrizes para contribuir com o projeto.

## 📋 Código de Conduta

Este projeto segue um [Código de Conduta](CODE_OF_CONDUCT.md). Ao participar, você concorda em respeitá-lo.

## 🐛 Reportando Bugs

Antes de reportar um bug:

1. **Verifique se já não foi reportado** — busque nas [issues](https://github.com/ElioNeto/shadows/issues) existentes
2. **Use o template de bug** — ao criar uma nova issue, preencha todas as informações solicitadas
3. **Seja específico** — inclua passos para reproduzir, logs, versão do SO, ambiente (X11/Wayland)

### Informações úteis para reportar bugs

- Versão do Shadows (`python main.py --version`)
- Distribuição Linux e versão
- Ambiente gráfico (X11 ou Wayland)
- Logs de execução com `--verbose`
- Print da tela (se aplicável e seguro)

## 💡 Sugerindo Funcionalidades

1. Abra uma [issue](https://github.com/ElioNeto/shadows/issues) descrevendo a funcionalidade
2. Explique o **problema** que você quer resolver
3. Descreva a **solução** que você imagina
4. Liste **alternativas** que você considerou

## 🔧 Desenvolvimento

### Setup do Ambiente

```bash
# Clone o repositório
git clone https://github.com/ElioNeto/shadows.git
cd shadows

# Crie um virtual environment
python3 -m venv venv
source venv/bin/activate

# Instale dependências do sistema
sudo bash scripts/setup-system-deps.sh

# Instale dependências Python
pip install -e ".[dev]"
```

### Padrões de Código

- **Python 3.10+** com type hints (`from __future__ import annotations`)
- Siga o estilo existente do código (PEP 8 com algumas adaptações)
- **Docstrings** em todos os módulos, classes e métodos públicos
- Use `nomes_em_snake_case` para funções e variáveis
- Use `NomesEmPascalCase` para classes
- Mantenha a cobertura de testes > 80%

### Testes

```bash
# Executar todos os testes
pytest

# Com cobertura
pytest --cov=shadows

# Testes específicos
pytest tests/test_detector.py -v
```

### Commits

- Use mensagens claras e descritivas em **inglês** ou **português**
- Comece com um verbo no imperativo: "Add", "Fix", "Refactor", "Update"
- Referencie issues quando aplicável: `git commit -m "Fix #12: resolve crash on Wayland detection"`
- Mantenha commits atômicos (uma mudança por commit)

### Pull Requests

1. Crie um **fork** do repositório
2. Crie um **branch** para sua feature: `git checkout -b feat/minha-feature`
3. Faça suas alterações seguindo os padrões de código
4. Escreva ou atualize **testes** conforme necessário
5. Execute os testes localmente: `pytest`
6. Faça o **commit** e **push** para seu fork
7. Abra um **Pull Request** contra o branch `main`

### Estrutura de Branches

| Prefixo | Uso |
|---------|-----|
| `feat/` | Novas funcionalidades |
| `fix/` | Correções de bugs |
| `refactor/` | Refatoração de código |
| `docs/` | Documentação |
| `test/` | Testes |
| `chore/` | Tarefas de manutenção |

### Revisão de Código

- Todos os PRs precisam de pelo menos uma aprovação
- Revise com atenção: segurança, performance, legibilidade
- Seja respeitoso e construtivo nos comentários

## 🧪 Ambiente de Testes

O Shadows é testado nos seguintes ambientes:

- **Ubuntu 22.04+** / **Debian 12+** (X11 + Wayland)
- **Fedora 38+** (Wayland)
- **Arch Linux** (X11 + Wayland)

## 📦 Publicação

1. Atualize a versão em `pyproject.toml` e `CHANGELOG.md`
2. Crie uma tag: `git tag v1.0.0`
3. Push da tag: `git push origin v1.0.0`
4. O CI criará o release automaticamente

## ❓ Dúvidas?

Abra uma [discussion](https://github.com/ElioNeto/shadows/discussions) ou entre em contato pelos canais do projeto.

---

<p align="center">
  <a href="README.md">← Voltar ao README</a>
</p>
