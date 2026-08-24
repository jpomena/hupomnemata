import flet as ft

def main(page: ft.Page):
    page.title = "Hupomnemata - Flet POC"
    page.bgcolor = "#F4F2EB"  # Cor de fundo "papel"
    page.padding = 40
    page.fonts = {
        "Lora": "https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,500;0,600;0,700;1,400&display=swap"
    }

    etiqueta = ft.Row(
        controls=[
            ft.Icon(ft.Icons.BOOK, size=16, color="#78716C"),
            ft.Text("MONOGRAFIA • 2000", size=12, weight=ft.FontWeight.BOLD, color="#78716C")
        ],
        spacing=8
    )

    titulos = ft.Column(
        controls=[
            ft.Text("O Senhor dos Anéis", size=24, font_family="Lora", color="#1C1917"),
            ft.Text("a Sociedade do anel", size=14, font_family="Lora", italic=True, color="#78716C")
        ],
        spacing=2
    )

    citacao = ft.Container(
        content=ft.Text(
            "TOLKIEN, J. R. R. O Senhor dos Anéis: a Sociedade do anel. São Paulo: Martins Fontes, 2000. 400 p.",
            size=14,
            font_family="Lora",
            color="#1C1917"
        ),
        bgcolor=ft.Colors.WHITE,
        padding=20,
        # CORREÇÃO: Usando ft.Border (maiúsculo)
        border=ft.Border.all(1, "#E6E2D6"),
        border_radius=4,
    )

    btn_copiar = ft.IconButton(
        icon=ft.Icons.COPY,
        icon_color="#78716C",
        tooltip="Copiar citação",
        on_click=lambda e: print("Citação copiada!") 
    )

    card_referencia = ft.Container(
        content=ft.Column(
            controls=[
                ft.Row([etiqueta, btn_copiar], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                titulos,
                ft.Container(height=10), 
                citacao
            ]
        ),
        bgcolor="#FCFBF9",
        padding=30,
        border_radius=4,
        # CORREÇÃO: Usando ft.Border (maiúsculo)
        border=ft.Border.all(1, "#E6E2D6"),
        shadow=ft.BoxShadow(
            spread_radius=1,
            blur_radius=10,
            color="#0D000000", 
            offset=ft.Offset(0, 2)
        )
    )

    page.add(card_referencia)

ft.app(target=main)
