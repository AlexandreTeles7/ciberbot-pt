# 🛡️ CiberBot PT

Bot que recolhe todos os dias as novidades de cibersegurança (ataques, vulnerabilidades, alertas), **traduz para português de Portugal o que estiver em inglês** e publica um resumo ordenado por relevância em quatro canais: **Telegram, email, Discord e uma página web** com arquivo diário.

Corre sozinho no GitHub Actions (grátis, sem servidor). Não tem dependências externas: só Python 3.11+.

## Como funciona

```
fontes (RSS, CISA KEV, NVD) → filtra últimas 36 h e o que já foi enviado → pontua e remove duplicados
→ traduz EN→PT-PT (API da Claude) → resumo diário → Telegram · Email · Discord · Página web
```

**Secções do resumo:** Em Portugal · Vulnerabilidades exploradas ativamente · Vulnerabilidades críticas recentes · Ataques e notícias.

**Fontes incluídas** (editáveis em `config.toml`):

| Fonte | Idioma | Notas |
|---|---|---|
| CNCS — Alertas de Segurança | PT | feed confirmado através de um agregador de RSS |
| Segurança Informática (blogue) | PT | feed WordPress padrão, **por confirmar** |
| CISA KEV | EN | exploração ativa confirmada; indica se é usada em ransomware |
| NVD (NIST) | EN | só CVE com gravidade crítica |
| BleepingComputer, The Hacker News, Krebs on Security | EN | URLs públicos habituais, **por confirmar** |

Se uma fonte falhar, as outras continuam e a falha aparece nas notas da edição.

## Instalação (≈ 15 minutos)

1. **Repositório.** Cria um repositório no GitHub e carrega estes ficheiros. Para o site grátis (GitHub Pages) o repositório tem de ser público; o resumo só contém informação pública.
2. **Tradução.** Cria uma chave da API da Claude e guarda-a em *Settings → Secrets and variables → Actions → New repository secret* com o nome `ANTHROPIC_API_KEY`. Sem chave, o bot funciona mas os itens em inglês ficam assinalados como «Em inglês».
3. **Canais** (cada um só fica ativo se tiver os seus segredos; usa os mesmos nomes de `.env.example`):
   - **Telegram:** fala com o `@BotFather`, cria um bot e guarda o token em `TELEGRAM_BOT_TOKEN`. Envia uma mensagem ao bot (ou adiciona-o a um grupo) e abre `https://api.telegram.org/bot<TOKEN>/getUpdates` para encontrares `"chat":{"id": ...}`; guarda esse número em `TELEGRAM_CHAT_ID`.
   - **Discord:** no canal, *Editar canal → Integrações → Webhooks → Novo webhook → Copiar URL* para `DISCORD_WEBHOOK_URL`.
   - **Email:** `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_DE` e `EMAIL_PARA` (vários destinatários separados por vírgula). No Gmail usa `smtp.gmail.com`, porta `587` e uma *palavra-passe de aplicação*.
   - **Página web:** *Settings → Pages → Deploy from a branch → `main` / pasta `/docs`*. Depois põe o endereço do site em `url_publica` no `config.toml` para aparecer nas mensagens.
4. **Primeira execução.** *Actions → Resumo diário → Run workflow*. A partir daí corre todos os dias às 07:00 UTC (07:00 no inverno, 08:00 no verão em Lisboa; o GitHub pode atrasar alguns minutos). Para mudar a hora, edita o `cron` em `.github/workflows/diario.yml`.

## Experimentar sem configurar nada

```bash
python3 -m ciberbot demo                       # pré-visualização com dados de exemplo, sem rede (abre previsao/index.html)
python3 -m unittest discover -s tests          # testes
python3 -m ciberbot run --dry-run              # com fontes reais, sem enviar nada nem gravar estado
python3 -m ciberbot run --canais telegram      # só um canal
```

Na `demo`, as traduções são escritas à mão (`tests/fixtures/demo_pt.json`) para mostrar o aspeto final; no uso real vêm da API.

## Personalizar (`config.toml`)

- **Fontes:** acrescenta blocos `[[fontes]]`. `idioma = "pt"` não traduz; `"en"` traduz. `palavras_obrigatorias` filtra feeds generalistas.
- **Relevância:** `[palavras_chave]` define os termos que fazem subir um item (por exemplo «zero-day» ou «ransomware»), e `peso` define a importância de cada fonte.
- **Tamanho:** `max_itens`, `[limites]` por secção e `janela_horas`.
- **Modelo de tradução:** `[traducao] modelo` (ou a variável `CIBERBOT_MODELO`). O custo depende do volume; `lote` e `resumo_max_caracteres` ajudam a controlá-lo.

## Segurança e limites

- Todo o texto vindo da internet é escapado antes de entrar em HTML, Telegram, Discord ou email; só se aceitam ligações `http(s)`; o Discord nunca menciona ninguém (`allowed_mentions` vazio).
- O prompt de tradução trata o conteúdo como dados e ignora instruções lá escritas; mesmo assim, o resultado é só texto e nunca é executado.
- Segredos só existem nas variáveis de ambiente; as mensagens de erro não os incluem.
- A tradução é automática: confirma os detalhes críticos na fonte original (o link vai sempre com cada item).
- O GitHub pode desativar agendamentos em repositórios sem atividade durante muito tempo; se acontecer, reativa em *Actions*.
- Não inclui (ainda) o modo «perguntar ao bot». Dá para acrescentar um comando `/pesquisar` ao Telegram sobre o mesmo núcleo.

## Estrutura

```
ciberbot/            código (fontes.py, pontuacao.py, traducao.py, edicao.py, estado.py, cli.py, canais/)
config.toml          fontes, limites e palavras-chave
.github/workflows/   agendamento diário
docs/                site gerado (GitHub Pages)
state/vistos.json    memória do que já foi enviado
tests/               testes e dados de exemplo
```
