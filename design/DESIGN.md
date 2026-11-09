# Design · Hupomnēmata (v2)

Sistema de design travado para o app. Toda tela nova ou redesenhada lê este arquivo
antes de virar código. O protótipo navegável está em `design/prototype/index.html`
(abrir com um servidor estático na raiz do repo, porque ele carrega as fontes de
`assets/fonts/`). A v1, mais editorial, ficou em `design/prototype/index.v1.html`
só como histórico.

## Para quem é

Pesquisador acadêmico brasileiro (pós-graduação, humanidades e direito) que lê,
ficha e escreve com ABNT. Usa o app por horas seguidas, em janela grande de desktop.

Tom: **ferramenta profissional com alma de biblioteca**. A interface fala como
software sério (Linear, Attio, Zotero moderno): densa, previsível, igual em todas as
telas. A identidade literária aparece só onde o usuário lê: títulos de página,
citações, sínteses e caderno.

## Princípios

1. **Toda tela tem a mesma estrutura.** Barra de título → cabeçalho de página (título,
   descrição, ações à direita) → barra de ferramentas (busca, filtros, contagem) →
   conteúdo. Ação primária sempre no canto direito do cabeçalho.
2. **Montserrat para a interface, Cormorant só para leitura.** A serifa aparece no
   título da página (H1), no título da obra no painel, no título de ideia e em todo
   texto lido: citações, sínteses, epígrafe. Tabela, lista, navegação, rótulos e
   números ficam em Montserrat.
3. **Sem rótulo em caixa alta.** Títulos de seção ficam em Montserrat 12/600 com
   capitalização normal. Nada de letra espaçada em maiúsculas.
4. **Números em Montserrat tabular**, nunca em mono e nunca em serifa gigante.
   A JetBrains Mono fica só para atalhos de teclado (`kbd`).
5. **Tabela de dados para coleções**, com colunas ordenáveis, seleção por checkbox
   e barra de ações em lote. Painel de detalhes à direita, com abas. Modal só para
   criar.
6. **Sem animação de entrada de página.** Movimento só em sobreposições (menu,
   diálogo, paleta, aviso), de 100 a 280 ms.
7. **Dourado só onde há decisão:** ação primária, item ativo, foco, checkbox marcado,
   seleção em lote. Nunca em título ou ícone decorativo.
8. **Excluir com desfazer, não com confirmação.** O aviso com “Desfazer” fica 6 s
   visível.
9. **Funções que ainda não existem** aparecem desabilitadas, com o selo neutro
   “Planejado”.
10. **Dados reais e honestos:** contagens e datas vêm do banco. Nada inventado.

## Cores

Hex para o `params.json` (o Flet não usa OKLCH). Os valores OKLCH estão em
`design/prototype/tokens.css`.

| Token | Escuro | Claro | Uso |
|---|---|---|---|
| `chrome` | `#09090b` | `#f2f0ec` | sidebar, barra de título, coluna de roteiro |
| `canvas` (`bg`) | `#0d0d10` | `#fcfbf9` | área de conteúdo |
| `surface` | `#141417` | `#fefefc` | cards, painel de detalhes, diálogo |
| `hover` | `#19191d` | `#f0eeea` | hover de linha e de botão |
| `selected` | `#1f1f24` | `#ebe7de` | linha aberta, item ativo |
| `rule` (`border`) | `#232328` | `#e1dfdb` | divisórias de 1 px |
| `rule_2` | `#303035` | `#cdcac5` | borda de controle |
| `ink` (`text`) | `#e6e5eb` | `#1d1d21` | texto principal |
| `ink_2` (`muted`) | `#a5a3ad` | `#525259` | texto secundário |
| `ink_3` | `#818189` | `#686870` | rótulos, metadados, ícones |
| `gold` | `#c5a059` | `#896200` | ação primária, ativo, foco |
| `gold_hover` | `#d4b06d` | `#765000` | hover do primário |
| `on_gold` | `#0c0c0e` | `#fefefc` | texto sobre o dourado |
| `danger` | `#e66e68` | `#b02a2d` | excluir |
| `ok` | `#6ebf8c` | `#156f41` | “Banco local”, confirmação |

Tons de seleção usam o dourado a 10–12 % de opacidade (`accent-wash`).

## Tipografia

| Papel | Fonte | Tamanho / peso |
|---|---|---|
| Wordmark | Ancient Geek | 17 / 400, só na barra de título |
| H1 de página | Cormorant Garamond | 30 / 600 |
| Título no painel e de ideia | Cormorant Garamond | 24 / 600 |
| Citação | Cormorant Garamond | 18 / 500, entrelinha 1.5, `lining-nums` |
| Síntese, epígrafe | Cormorant Garamond | 16–17 (itálico só na epígrafe) |
| UI e células | Montserrat | 13 / 500, tracking -0.006em |
| Título de card e de seção | Montserrat | 13 / 600 |
| Rótulo, cabeçalho de coluna, metadado | Montserrat | 12 / 500–600 |
| KPI | Montserrat | 24 / 600, tabular, tracking -0.02em |
| Badge | Montserrat | 11 / 600 |
| Atalho | JetBrains Mono | 10.5 |

No Flet: tirar o `letter_spacing=2` de `view_styles.py`. O rótulo do campo fica
acima do campo.

## Ícones

**Font Awesome Free 6.7.2.** Usar `fa-regular` quando existir na versão gratuita
(pasta, arquivo, comentário, lixeira, copiar, marcador, calendário), senão
`fa-solid`. Tamanho 14 px na interface e 12,5 px em botões pequenos. Ícone nunca
substitui rótulo em ação primária.

Mapa usado no protótipo (a lista completa está no objeto `FA` em `index.html`):
Início `house`, Acervo `book`, Fragmentos `quote-left`, Compilações `folder-open`,
Estruturas `diagram-project`, Nous `brain`, Configurações `gear`, Buscar
`magnifying-glass`, Copiar `copy`, Excluir `trash-can`, Mais `ellipsis`, Tema
`circle-half-stroke`.

No Flet: registrar `fa-solid-900.ttf` e `fa-regular-400.ttf` em `page.fonts` e
desenhar o ícone com `ft.Text(chr(codepoint), font_family="FA Solid")`, ou usar os
SVGs de `@fortawesome/fontawesome-free/svgs` com `ft.Image`. A licença dos ícones é
CC BY 4.0 e a das fontes é SIL OFL, então manter o aviso de licença junto dos
arquivos.

## Espaço, forma, controles

- Escala de 4 pt: 2, 4, 8, 12, 16, 24, 32, 48, 64.
- Raios: 4 (badge, kbd, checkbox), 6 (botão, campo, item), 8 (card, menu), 10 (diálogo).
- Alturas: barra de título 40, controle 32 (pequeno 28), linha de tabela 40,
  item de navegação 30, cabeçalho de card 44.
- Sombras só em sobreposições (menu, diálogo, paleta, aviso).
- Filtro inativo: botão tracejado “+ Tipo”. Filtro ativo: chip sólido com valor em
  dourado e botão de remover.

## Shell

- **Barra de título (40):** wordmark, voltar e avançar (⌘[ e ⌘]), breadcrumb e os
  controles da janela, que é sem moldura.
- **Sidebar (240):**
  - no topo, “Buscar ⌘K” e o botão `+` de nova obra;
  - grupo sem título (Início, Acervo 29, Fragmentos 47);
  - grupo **Compilações** (projetos + Todas, com `+`);
  - grupo **Explorar** (Estruturas de Saber, Nous);
  - no rodapé, Configurações e uma linha de status “Banco local” com o botão de tema.

## Telas

### Início
1. **Cabeçalho**: “Gabinete de Leitura”, com Novo fragmento e Nova obra.
2. **Faixa de 4 KPIs clicáveis**: Obras, Fragmentos, Compilações e Obras sem
   fragmentos (ordena o Acervo).
3. **Duas colunas.**
   - Esquerda: **Compilações em andamento** (tabela) e **Atividade recente** (obras e
     fragmentos por data de cadastro, agrupados por dia).
   - Direita: **Acervo por tipo** (barras neutras), **Atalhos** e a epígrafe.

### Acervo
- **Cabeçalho**: Importar (desabilitado, Planejado) e Nova obra.
- **Barra de ferramentas**: busca, filtros Tipo e Compilação, e a contagem.
- **Tabela**: checkbox, Título (com o subtítulo em cinza na mesma linha), Autoria,
  Tipo, Ano, Frag. e Adicionada.
  - Todas as colunas ordenam ao clicar.
  - Obras filhas aparecem recuadas sob a mãe.
  - As colunas somem por largura (container query).
- **Seleção**: marcar linhas troca a barra de ferramentas pela barra de lote
  (Copiar referências, Adicionar à compilação, Excluir, Limpar seleção).
- **Painel de detalhes** (380):
  - cabeçalho com o selo do tipo, anterior e próxima, e fechar;
  - título, subtítulo, autoria e ano;
  - botões Editar, Fragmento e `⋯` (copiar, adicionar, duplicar, excluir);
  - abas **Visão geral** (Referência ABNT com Copiar, Propriedades, Síntese do Nous) e
    **Fragmentos**.
- **Teclado**: ↑↓ navega, espaço marca, Enter abre, ⌘C copia a referência e Esc
  fecha.

### Fragmentos
- **Barra de ferramentas**: segmentado Todos / Citações / Comentários, filtro de
  texto, contagem e “Recolher tudo”.
- **Grupos por obra** em card, que recolhem.
- **Linha de fragmento**: ícone do tipo; citação em Cormorant 18 ou comentário em
  Montserrat 13 `ink_2`; metadados (tipo, localizador, data) e selo da compilação.
  As ações aparecem no hover ou no foco.

### Compilação
- **Cabeçalho**: nome, descrição e selos (obras, fragmentos, ideias, atualizada em),
  com Copiar esqueleto e `⋯`.
- **Abas**: Visão geral, Obras e fragmentos, Caderno de trabalho.
- **Caderno**, em três colunas:
  - **Roteiro** (248, fundo `chrome`): ideias numeradas, com destaque que acompanha a
    rolagem, e a fila “A organizar”;
  - **Escrita** (até 700): título da ideia com número, linha “Ideia central” e blocos
    de fragmento (cabeçalho com obra, tipo, copiar e `⋯`; citação; rodapé com a nota
    de articulação);
  - **Lateral** (320): “Copiar esqueleto com referências”, referências ABNT numeradas
    e obras do projeto.
- **Visão geral**: tabela do roteiro, card Detalhes e card “Excluir compilação”
  (zona de risco).

### Nova obra (diálogo de 1040 × 740)
- **Tipos** em lista agrupada com busca.
- **Formulário** em seções com a legenda à esquerda.
- **Rodapé fixo**: prévia ABNT ao vivo, Cancelar e “Salvar no acervo” (⌘↵).
- **Validação ao salvar**: o campo fica com borda vermelha, a mensagem aparece abaixo
  e o foco vai para o primeiro erro. O botão mostra “Salvando” enquanto grava.

### Paleta ⌘K
Busca obras, fragmentos e ações (inclui “Ir para…” e “Alternar tema”).

### Fora desta rodada
Estruturas de Saber, Nous e Configurações herdam o shell e os tokens, mas o conteúdo
dessas telas não foi redesenhado.

## Port para Flet: onde mexer

| Arquivo | Mudança |
|---|---|
| `src/configs/params.json` | cores da tabela acima, `sidebar_width` 240, `card_radius` 8, alturas de controle |
| `assets/fonts/` | adicionar `fa-solid-900.ttf` e `fa-regular-400.ttf` (Font Awesome Free) |
| `src/utils/ft_icons.py` | mapa de nomes para codepoints do Font Awesome |
| `src/utils/view_styles.py` | tirar `letter_spacing=2`; rótulo acima; borda 1 px; foco dourado |
| `src/views/core_composer.py` | barra de título (histórico + breadcrumb), cabeçalho de página padrão, paleta ⌘K via `page.on_keyboard_event` |
| `src/views/sidebar.py` | grupos, contadores, compilações aninhadas, status + tema no rodapé |
| `src/views/dashboard.py` | KPIs + duas colunas |
| `src/views/works.py` | tabela (`ft.DataTable` ou linhas em `ListView`), filtros, seleção em lote, painel |
| `src/views/work_details_popup.py` | vira o painel de detalhes, sem popup |
| `src/views/fragments.py` | grupos recolhíveis, segmentado |
| `src/views/compilation_hub/*` | sai do `AlertDialog` e vira tela com abas; caderno em 3 colunas |
| `src/views/work_insert_modal*.py` | tipos em lista + seções + prévia ABNT + validação ao salvar |

Ordem sugerida: tokens, ícones e estilos → shell → Acervo → Fragmentos → Compilação
→ Nova obra → Início.
