# Robô Caracolada — gerar o app de macOS (na nuvem)

Este repositório monta o **RoboCaracolada.app** (versão Mac) automaticamente,
usando um Mac na nuvem do **GitHub Actions**. Você **não precisa ter um Mac**.

> Nenhuma senha vai pro GitHub. O login fica só no `credenciais.json`, que
> cada pessoa cria na própria máquina (veja `credenciais.exemplo.json`).

---

## Passo a passo

### 1. Conta no GitHub
É grátis: https://github.com/signup  (se já tiver, pule).

### 2. Criar um repositório
- Acesse https://github.com/new
- Nome: por exemplo `robo-caracolada`
- Pode deixar **Public**. Clique em **Create repository**.

### 3. Enviar os arquivos

**Opção A — pelo Git (recomendado; já deixei tudo commitado):**
Na pasta `RoboCaracolada-mac`, abra o terminal e rode (troque SEU-USUARIO):
```
git remote add origin https://github.com/SEU-USUARIO/robo-caracolada.git
git branch -M main
git push -u origin main
```
Na primeira vez o Git abre o navegador pra você logar no GitHub.

**Opção B — pelo site (sem Git):**
- No repositório novo, clique em **uploading an existing file** e arraste
  `robo_gui.py` e `requirements.txt`.
- Depois **Add file → Create new file**, e no nome digite exatamente:
  `.github/workflows/build-mac.yml` — cole o conteúdo do arquivo de mesmo nome.
- **Commit changes**.

### 4. Esperar o build
- Abra a aba **Actions** do repositório.
- O fluxo **"Build macOS app"** roda sozinho (~3 a 5 min). Espere ficar verde ✅.
- (Se não iniciar, clique no fluxo e em **Run workflow**.)

### 5. Baixar o app
- Clique no build concluído → seção **Artifacts** → baixe **RoboCaracolada-mac**.
- Descompacte: dentro está o **RoboCaracolada.app**.

---

## Como usar o app no Mac

1. Coloque o `RoboCaracolada.app` numa pasta (ex: Downloads) e, **ao lado dele**,
   um arquivo `credenciais.json` (copie o `credenciais.exemplo.json` e preencha),
   ou simplesmente preencha e-mail/senha na janela do app e clique em **Salvar**.

2. Como o app não tem a assinatura paga da Apple, na **primeira vez**:
   - **clique com o botão direito** no app → **Abrir** → **Abrir**; ou
   - Ajustes do Sistema → **Privacidade e Segurança** → **Abrir assim mesmo**.

3. Digite e-mail e senha da Caracolada, clique em **Salvar** e depois **Iniciar**.

---

## Detalhes técnicos

- O app é gerado para **Intel (`macos-13`)** e roda em Macs Intel e Apple Silicon
  (via Rosetta — o Mac instala sozinho se pedir).
- Para um app **nativo Apple Silicon**, troque `macos-13` por `macos-14` em
  `.github/workflows/build-mac.yml`.
- macOS runners do GitHub Actions são **grátis em repositórios públicos**.
- Pré-requisito do usuário final: ter conta na Caracolada já dentro do álbum
  "Copa SPC Brasil 2026".
