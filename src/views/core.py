import flet as ft
import yaml
from pathlib import Path
import os

# Tokens de Cores do Vault (Dark Minimalista)
COLORS = {
    "bg": "#0c0c0e",
    "surface": "#141417",
    "border": "#232328",
    "gold": "#c5a059",
    "muted": "#7a7885",
    "text": "#e2e1e8",
    "card_hover": "#1a1a1f"
}

FONTS = {
    'serif': 'Cormorant Garamond',
    'sans': 'Montserrat',
    'mono': 'JetBrains Mono',
}

def main(page: ft.Page):
    try:
        texts_file_path = Path('src') / 'assets' / 'texts.yaml'
        fonts_path = Path('src') / 'assets' / 'fonts'

        if texts_file_path.exists():
            with open(texts_file_path, 'r', encoding='utf-8') as file:
                TEXTS = yaml.safe_load(file)
        else:
            TEXTS = {'app': {'name': 'HYPOMNEMATA', 'version': 'v2.5'}}

        if fonts_path.exists():
            page.fonts = {
                'Cormorant Garamond': str(fonts_path / 'Cormorant_Garamond' / 'CormorantGaramond-VariableFont_wght.ttf'),
                'Montserrat': str(fonts_path / 'Montserrat' / 'Montserrat-VariableFont_wght.ttf'),
                'JetBrains Mono': str(fonts_path / 'JetBrains_Mono' / 'JetBrainsMono-VariableFont_wght.ttf'),
            }
        else:
            page.fonts = {}
    except Exception as e:
        TEXTS = {'app': {'name': 'HYPOMNEMATA', 'version': 'v2.5'}}
        page.fonts = {}

    page.theme = ft.Theme(font_family=FONTS['serif'])
    page.title = f"{TEXTS.get('app', {}).get('name', 'HYPOMNEMATA')} {TEXTS.get('app', {}).get('version', 'v2.5')}"
    page.padding = 0
    page.window.width = 1200
    page.window.height = 750
    page.window.resizable = True

    view_title = ft.Text("Catálogo de Obras & Livros", size=24, weight=ft.FontWeight.W_300, color="white", font_family=FONTS['serif'])
    view_subtitle = ft.Text("Registros bibliográficos primários do acervo local.", size=12, color=COLORS['muted'], font_family=FONTS['sans'])
    
    content_area = ft.Container(expand=True, padding=20)

    def update_view(title, subtitle, content):
        view_title.value = title
        view_subtitle.value = subtitle
        content_area.content = content
        page.update()

    def get_biblioteca_view():
        return ft.Column([
            ft.Container(
                content=ft.Row([
                    ft.Column([
                        ft.Text("LIVRO // 1982", size=9, color=COLORS['gold'], font_family=FONTS['mono']),
                        ft.Text("L'herméneutique du sujet: Cours au Collège de France", size=18, color="white", font_family=FONTS['serif']),
                        ft.Text("Michel Foucault", size=12, color=COLORS['muted'], font_family=FONTS['sans']),
                    ], expand=True),
                    ft.ElevatedButton("Síntese IA", icon=ft.Icons.AUTO_AWESOME, color=COLORS['gold'], bgcolor=COLORS['bg'])
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                padding=15, 
                bgcolor=COLORS['surface'], 
                border=ft.Border(
                    top=ft.BorderSide(1, COLORS['border']),
                    bottom=ft.BorderSide(1, COLORS['border']),
                    left=ft.BorderSide(1, COLORS['border']),
                    right=ft.BorderSide(1, COLORS['border'])
                ), 
                border_radius=8
            ),
            ft.Container(
                content=ft.Row([
                    ft.Column([
                        ft.Text("LIVRO // 1976", size=9, color=COLORS['gold'], font_family=FONTS['mono']),
                        ft.Text("La volonté de savoir: Histoire de la sexualité I", size=18, color="white", font_family=FONTS['serif']),
                        ft.Text("Michel Foucault", size=12, color=COLORS['muted'], font_family=FONTS['sans']),
                    ], expand=True),
                    ft.ElevatedButton("Síntese IA", icon=ft.Icons.AUTO_AWESOME, color=COLORS['gold'], bgcolor=COLORS['bg'])
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                padding=15, 
                bgcolor=COLORS['surface'], 
                border=ft.Border(
                    top=ft.BorderSide(1, COLORS['border']),
                    bottom=ft.BorderSide(1, COLORS['border']),
                    left=ft.BorderSide(1, COLORS['border']),
                    right=ft.BorderSide(1, COLORS['border'])
                ), 
                border_radius=8
            )
        ], spacing=10, scroll=ft.ScrollMode.AUTO)

    def get_excertos_view():
        return ft.Column([
            ft.Container(
                content=ft.Column([
                    ft.Text("#FOU-82-01 // FOUCAULT", size=10, color=COLORS['gold'], font_family=FONTS['mono']),
                    ft.Text('"O cuidado de si constituiu não apenas um princípio, mas uma atitude permanente..."', italic=True, size=14, color=COLORS['text'])
                ]),
                padding=15, 
                bgcolor=COLORS['surface'], 
                border=ft.Border(
                    top=ft.BorderSide(1, COLORS['border']),
                    bottom=ft.BorderSide(1, COLORS['border']),
                    left=ft.BorderSide(1, COLORS['border']),
                    right=ft.BorderSide(1, COLORS['border'])
                ), 
                border_radius=8
            ),
            ft.Container(
                content=ft.Column([
                    ft.Text("#FOU-76-02 // FOUCAULT", size=10, color=COLORS['gold'], font_family=FONTS['mono']),
                    ft.Text('"O poder não se toma, o poder se exerce a partir de inúmeros pontos..."', italic=True, size=14, color=COLORS['text'])
                ]),
                padding=15, 
                bgcolor=COLORS['surface'], 
                border=ft.Border(
                    top=ft.BorderSide(1, COLORS['border']),
                    bottom=ft.BorderSide(1, COLORS['border']),
                    left=ft.BorderSide(1, COLORS['border']),
                    right=ft.BorderSide(1, COLORS['border'])
                ), 
                border_radius=8
            )
        ], spacing=10, scroll=ft.ScrollMode.AUTO)

    def get_taxonomia_view():
        return ft.Container(
            content=ft.Column([
                ft.Text("Mapa Ontológico do Vault", size=20, color="white", font_family=FONTS['serif']),
                ft.Text("Categorias indexadas e remissões cruzadas no acervo:", size=12, color=COLORS['muted']),
                ft.Row([
                    ft.Container(content=ft.Text("#hermeneutica (14)", size=11, color=COLORS['gold'], font_family=FONTS['mono']), padding=8, bgcolor=COLORS['bg'], border=ft.Border(top=ft.BorderSide(1, COLORS['border']), bottom=ft.BorderSide(1, COLORS['border']), left=ft.BorderSide(1, COLORS['border']), right=ft.BorderSide(1, COLORS['border'])), border_radius=4),
                    ft.Container(content=ft.Text("#cuidado_de_si (22)", size=11, color=COLORS['gold'], font_family=FONTS['mono']), padding=8, bgcolor=COLORS['bg'], border=ft.Border(top=ft.BorderSide(1, COLORS['border']), bottom=ft.BorderSide(1, COLORS['border']), left=ft.BorderSide(1, COLORS['border']), right=ft.BorderSide(1, COLORS['border'])), border_radius=4),
                    ft.Container(content=ft.Text("#biopoder (9)", size=11, color=COLORS['gold'], font_family=FONTS['mono']), padding=8, bgcolor=COLORS['bg'], border=ft.Border(top=ft.BorderSide(1, COLORS['border']), bottom=ft.BorderSide(1, COLORS['border']), left=ft.BorderSide(1, COLORS['border']), right=ft.BorderSide(1, COLORS['border'])), border_radius=4),
                    ft.Container(content=ft.Text("#subjetivacao (17)", size=11, color=COLORS['gold'], font_family=FONTS['mono']), padding=8, bgcolor=COLORS['bg'], border=ft.Border(top=ft.BorderSide(1, COLORS['border']), bottom=ft.BorderSide(1, COLORS['border']), left=ft.BorderSide(1, COLORS['border']), right=ft.BorderSide(1, COLORS['border'])), border_radius=4),
                ], wrap=True, spacing=10)
            ], spacing=15),
            padding=20, 
            bgcolor=COLORS['surface'], 
            border=ft.Border(
                top=ft.BorderSide(1, COLORS['border']),
                bottom=ft.BorderSide(1, COLORS['border']),
                left=ft.BorderSide(1, COLORS['border']),
                right=ft.BorderSide(1, COLORS['border'])
            ), 
            border_radius=8
        )

    def get_ia_view():
        chat_output = ft.Column([], spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)
        query_field = ft.TextField(label="Digite uma questão de pesquisa...", border_color=COLORS['border'], focused_border_color=COLORS['gold'], text_size=12, expand=True)

        def handle_query(e):
            if not query_field.value.strip():
                return
            user_msg = query_field.value
            chat_output.controls.append(
                ft.Container(content=ft.Text(f"Q: {user_msg}", color=COLORS['text'], size=12), padding=10, bgcolor=COLORS['bg'], border_radius=6)
            )
            ai_resp = f"Síntese Gemini 3-Flash para: '{user_msg}' baseada nos registros de Foucault e hermenêutica do sujeito."
            chat_output.controls.append(
                ft.Container(content=ft.Text(f"Gemini: {ai_resp}", color=COLORS['gold'], size=12), padding=10, bgcolor=COLORS['card_hover'], border_radius=6)
            )
            query_field.value = ""
            page.update()

        return ft.Container(
            content=ft.Column([
                ft.Text("Assistente de Pesquisa & Síntese (Gemini)", size=20, color="white", font_family=FONTS['serif']),
                ft.Container(
                    content=chat_output, 
                    height=350, 
                    padding=10, 
                    bgcolor=COLORS['bg'], 
                    border=ft.Border(
                        top=ft.BorderSide(1, COLORS['border']),
                        bottom=ft.BorderSide(1, COLORS['border']),
                        left=ft.BorderSide(1, COLORS['border']),
                        right=ft.BorderSide(1, COLORS['border'])
                    ), 
                    border_radius=8
                ),
                ft.Row([
                    query_field,
                    ft.ElevatedButton("Consultar", icon=ft.Icons.AUTO_AWESOME, bgcolor=COLORS['gold'], color="black", on_click=handle_query)
                ], spacing=10)
            ], spacing=15),
            padding=20, 
            bgcolor=COLORS['surface'], 
            border=ft.Border(
                top=ft.BorderSide(1, COLORS['border']),
                bottom=ft.BorderSide(1, COLORS['border']),
                left=ft.BorderSide(1, COLORS['border']),
                right=ft.BorderSide(1, COLORS['border'])
            ), 
            border_radius=8
        )

    def create_nav_button(label, icon, tab_key):
        def handle_click(e):
            if tab_key == 'biblioteca':
                update_view("Catálogo de Obras & Livros", "Registros bibliográficos primários do acervo local.", get_biblioteca_view())
            elif tab_key == 'excertos':
                update_view("Cadernos & Excertos Reunidos", "Banco unificado de citações e anotações por obra.", get_excertos_view())
            elif tab_key == 'taxonomia':
                update_view("Taxonomia & Grafo de Conceitos", "Ontologia de tags, relações e remissões cruzadas.", get_taxonomia_view())
            elif tab_key == 'ia':
                update_view("Assistente de Pesquisa & Síntese (Gemini)", "Consulta inteligente ao acervo bibliográfico.", get_ia_view())

        icon_ref = ft.Icon(icon, size=16, color=COLORS['gold'])
        text_ref = ft.Text(label, size=13, color=COLORS['text'], font_family=FONTS['sans'])

        btn_container = ft.Container(
            content=ft.Row([
                ft.Row([icon_ref, text_ref], spacing=10),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=12,
            ink=True,
            border_radius=ft.BorderRadius(top_right=4, bottom_right=4, top_left=0, bottom_left=0),
        )

        def handle_hover(e):
            if e.data == 'true':
                btn_container.bgcolor = "#5a5a75"  # Fundo consideravelmente mais claro, com alto contraste e brilho evidente
                btn_container.border = ft.Border(left=ft.BorderSide(4.0, "#ffffff"))  # Borda lateral grossa com brilho branco intenso
                icon_ref.color = "#ffffff"  # Ícone em branco puro
                text_ref.color = "#ffffff"  # Texto em branco puro
            else:
                btn_container.bgcolor = None
                btn_container.border = None
                icon_ref.color = COLORS['gold']
                text_ref.color = COLORS['text']
            btn_container.update()

        btn_container.on_click = handle_click
        btn_container.on_hover = handle_hover
        return btn_container

    content_area.content = get_biblioteca_view()

    page.add(
        ft.Row(
            expand=True,
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
            controls=[
                # Sidebar Esquerda
                ft.Container(
                    content=ft.Column([
                        # Topo Branding
                        ft.Container(
                            content=ft.Column([
                                ft.Row([
                                    ft.Container(width=8, height=8, bgcolor=COLORS['gold'], border_radius=4),
                                    ft.Text("HYPOMNEMATA", size=16, weight=ft.FontWeight.W_400, color="white", font_family=FONTS['serif'])
                                ], spacing=8),
                                ft.Text("Vault v2.5 // Gemini AI Active", size=9, color=COLORS['muted'], font_family=FONTS['mono'])
                            ], spacing=6),
                            padding=20, 
                            border=ft.Border(bottom=ft.BorderSide(1, COLORS['border']))
                        ),
                        # Navegação
                        ft.Container(
                            content=ft.Column([
                                ft.Text("MÓDULOS DO SISTEMA", size=9, color=COLORS['muted'], font_family=FONTS['mono']),
                                create_nav_button("01. Obras & Livros", ft.Icons.BOOK_OUTLINED, 'biblioteca'),
                                create_nav_button("02. Cadernos & Excertos", ft.Icons.NOTE_OUTLINED, 'excertos'),
                                create_nav_button("03. Taxonomia & Conceitos", ft.Icons.HUB_OUTLINED, 'taxonomia'),
                                create_nav_button("04. Assistente IA (Gemini)", ft.Icons.AUTO_AWESOME, 'ia'),
                            ], spacing=4),
                            padding=15, expand=True
                        ),
                        # Rodapé Sidebar
                        ft.Container(
                            content=ft.Row([
                                ft.Text("GEMINI: 3-FLASH", size=9, color=COLORS['muted'], font_family=FONTS['mono']),
                                ft.Text("● READY", size=9, color="#34d399", font_family=FONTS['mono'])
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            padding=15, 
                            border=ft.Border(top=ft.BorderSide(1, COLORS['border']))
                        )
                    ], spacing=0),
                    width=300,
                    bgcolor=COLORS['surface'],
                    border=ft.Border(right=ft.BorderSide(1, COLORS['border']))
                ),
                # Área Principal Direita
                ft.Container(
                    content=ft.Column([
                        # Header da Área Principal
                        ft.Container(
                            content=ft.Row([
                                ft.Column([view_title, view_subtitle], spacing=2),
                                ft.Row([
                                    ft.TextField(hint_text="Filtrar por autor...", prefix_icon=ft.Icons.SEARCH, text_size=12, width=240, border_color=COLORS['border']),
                                    ft.ElevatedButton("Cadastrar Obra", icon=ft.Icons.ADD, bgcolor=COLORS['gold'], color="black")
                                ], spacing=12)
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            padding=20, height=80,
                            bgcolor=COLORS['surface'],
                            border=ft.Border(bottom=ft.BorderSide(1, COLORS['border']))
                        ),
                        # Miolo Dinâmico
                        content_area
                    ], spacing=0),
                    expand=True,
                    bgcolor=COLORS['bg']
                )
            ]
        )
    )

if __name__ == '__main__':
    ft.app(target=main)