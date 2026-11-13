# Flet Architecture & Engineering Reference (v0.86+)

Guia de referência técnica profunda para desenvolvimento com Flet no Hupomnemata.

## 1. Modelo de Renderização e Ciclo de Vida

O Flet opera acoplando o runtime Python ao renderizador Flutter via canal de comunicação RPC/WebSockets.

### Ciclo de Montagem
1. **Instanciação**: O controle Python é alocado em memória. `control.page` é `None`. Chamar `control.update()` neste estado dispara erro.
2. **Anexação**: O controle é adicionado à lista de filhos de um elemento já montado (ou à `page.controls`).
3. **Renderização Inicial**: `page.update()` envia o diff estrutural para o client Flutter.
4. **Mutação**: Atributos dos controles são alterados em memória Python. `control.update()` ou `page.update()` empurra os deltas para a viewport.
5. **Descarte (Unmount)**: O controle é removido da lista de filhos. Event listeners associados devem ser cancelados para prevenir vazamento de memória.

## 2. Layout, Constraints e Flexbox

### Hierarquia de Contêineres
- **`ft.Column` / `ft.Row`**:
  - `alignment`: Distribuição ao longo do eixo principal (`MainAxisAlignment.START`, `CENTER`, `SPACE_BETWEEN`, etc.).
  - `vertical_alignment`: Alinhamento transversal (`CrossAxisAlignment.START`, `CENTER`, `STRETCH`, etc.).
  - `scroll`: Deve ser explicitamente definido (`ScrollMode.AUTO`, `ADAPTIVE`) se houver risco de overflow vertical.
- **Armadilha do `expand=True`**:
  - Se um controle com `expand=True` ou `expand=1` for inserido dentro de um contêiner que não possui restrição finita de altura (por exemplo, uma `ft.Column` rolável sem altura definida), o Flutter gera falha de asserção de layout infinito (`RenderFlex children have non-zero flex but incoming height constraints are unbounded`).
  - Solução: Use dimensões explícitas (`height`), contêiner delimitador ou evite `expand` dentro de eixos com rolagem irrestrita.

### Responsividade
- **`ft.ResponsiveRow`**:
  - Utiliza grid de 12 colunas baseado em breakpoints do Flutter (`xs`, `sm`, `md`, `lg`, `xl`).
  - Cada controle filho define seu dicionário `col`: `col={"sm": 12, "md": 6, "xl": 4}`.

## 3. Padrões Específicos do Hupomnemata

### Escala Dinâmica e Tipografia
O repositório implementa suporte a fator de zoom/escala de DPI customizado pelo usuário via `set_scale`:
- **`s(pixels)`**: Sempre multiplique dimensões manuais pela função de escala `s()`.
- **Cores**: Use a paleta de `ViewConfig.colors` (ex.: `config.colors["primary"]`, `config.colors["surface"]`).
- **Transparência**: `alpha(color, opacity)` chama internamente `ft.Colors.with_opacity(opacity, color)`.

### Modais e Diálogos
Para diálogos em tela cheia ou caixas de confirmação:
```python
dialog = ft.AlertDialog(
    modal=True,
    title=ui_text(config, "Confirmação", size=16, weight=W600),
    content=ui_text(config, "Deseja prosseguir com a operação?"),
    actions=[
        ft.TextButton("Cancelar", on_click=lambda e: _close_dialog(dialog, page)),
        ft.ElevatedButton("Confirmar", on_click=lambda e: _confirm_action(dialog, page)),
    ],
    actions_alignment=ft.MainAxisAlignment.END,
)

def _close_dialog(dlg: ft.AlertDialog, page: ft.Page):
    dlg.open = False
    page.update()

page.overlay.append(dialog)
dialog.open = True
page.update()
```

## 4. Otimização de Performance

1. **Evitar Atualizações Prematuras**: Modifique todas as propriedades necessárias no bloco lógico e invoque `page.update()` apenas uma vez ao final.
2. **Listas Longas**: Utilize `ft.ListView` com `item_extent` quando os itens possuírem altura fixa para habilitar virtualização do Flutter.
3. **Operações Assíncronas**: Para leitura de banco de dados (`work_service.get_works()`, etc.), use threads de background para não travar a animação de cliques e digitação do usuário.
