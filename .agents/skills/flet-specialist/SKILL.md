---
name: flet-specialist
description: >-
  Especialista em desenvolvimento de interfaces com Flet (Python/Flutter), arquitetura reativa de componentes,
  gerenciamento de estado, ciclo de vida de controles e integração com o UI Kit do Hupomnemata (Flet v0.86+).
  Ative esta habilidade ao construir, refatorar, estilizar, debugar ou otimizar telas, modais e controles Flet.
---

# Flet Specialist Protocol

Este protocolo consolida as diretrizes sagradas para engenharia de interface utilizando o framework Flet no ecossistema do Hupomnemata.

## Princípios Arquiteturais Sagrados

1. **Separação Rígida de Responsabilidades**:
   - **Views (`src/views/`)**: Apenas declaração visual de controles, layout e captura de eventos do usuário.
   - **Controllers (`src/controllers/`)**: Orquestração do fluxo, manipulação do estado da view e comunicação entre serviços e interface.
   - **Services (`src/services/`)**: Regras de negócio puras, processamento de dados e transformações.
   - **Repositories (`src/repositories/`)**: Persistência e consultas diretas ao banco de dados SQLite / SQLAlchemy.

2. **Padrão de Componentização Moderna (Flet 0.86+)**:
   - Não utilize a classe legada `ft.UserControl`.
   - Crie componentes herdando diretamente de contêineres primitivos (`ft.Container`, `ft.Column`, `ft.Row`, etc.) ou por meio de funções de fábrica limpas.
   - Exemplo padrão:
     ```python
     import flet as ft
     from src.utils.types import ViewConfig

     class WorkCard(ft.Container):
         def __init__(self, config: ViewConfig, title: str, on_select: ft.ControlEventCallable = None):
             super().__init__(
                 padding=12,
                 border_radius=8,
                 bgcolor=config.colors["surface"],
                 ink=True,
                 on_click=on_select,
             )
             self.content = ft.Text(title, color=config.colors["text"])
     ```

3. **Integração com o UI Kit do Hupomnemata**:
   - Importe e aplique as rotinas de `src.views.ui_kit`:
     - `s(valor)`: Converte valores de pixels respeitando o fator de escala dinâmico da aplicação.
     - `alpha(cor, opacidade)`: Aplica transparência a hexadecimais ou cores Flet via `ft.Colors.with_opacity`.
     - `ui_text(...)`: Padronização de tipografia (Montserrat/Cormorant) com tracking e estilos predefinidos.
     - `fa_icon(...)`: Injeção de ícones FontAwesome vetorizados via codepoints.

4. **Gerenciamento de Ciclo de Vida e Atualização**:
   - **Nunca** invoque `control.update()` se o controle não estiver anexado à árvore da página (`control.page is not None`).
   - Prefira agrupar mutações de estado e chamar `page.update()` uma única vez ao final do ciclo de processamento.
   - Modais e popups devem ser gerenciados pelo overlay global da página:
     ```python
     page.overlay.append(dialog)
     dialog.open = True
     page.update()
     ```

5. **Prevenção de Travamentos de Thread**:
   - A thread da interface Flet nunca deve executar operações I/O pesadas, requisições de rede ou queries complexas de banco de forma síncrona.
   - Utilize tarefas assíncronas ou execute o processamento em threads secundárias (`threading.Thread`), disparando a atualização da UI no callback final.

Consulte a documentação técnica detalhada em [flet_architecture.md](./references/flet_architecture.md).
