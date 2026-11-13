# Diretrizes de Engenharia Flet (Hupomnemata)

Sempre que manipular ou criar código relacionado a interfaces Flet neste repositório:

1. **Versão Flet**: O projeto utiliza `flet==0.86.5`. Observe as convenções desta versão (`ft.Colors.with_opacity`, `ft.Event`, herança de `ft.Container`/`ft.Column` em vez de `ft.UserControl`).
2. **Padrão UI Kit**: Utilize as convenções visuais e funções utilitárias de [ui_kit.py](file:///home/jpomena/Documents/repos/hupomnemata/src/views/ui_kit.py):
   - Função de escala: `s(px)` para dimensionamentos em pixels.
   - Opacidade de cores: `alpha(color, opacity)`.
   - Tipografia: `ui_text(...)` para garantir fontes Montserrat/Cormorant e tracking unificado.
   - Ícones: `fa_icon(...)` para ícones do FontAwesome.
3. **Integridade de Renderização**:
   - Nunca chame `control.update()` em controles desacoplados da árvore (`control.page is None`).
   - Evite `expand=True` dentro de eixos roláveis irrestritos para não violar as asserções de layout do Flutter.
   - Delegue I/O e computação demorada para fora da thread principal de eventos Flet.
4. **Camadas Arquiteturais**:
   - A camada de Views nunca deve executar comandos de banco de dados diretamente; acione sempre o respectivo Controller ou Service.
