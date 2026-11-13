import json
from typing import Any


def generate_pdf_viewer_html(
    pdf_base64: str,
    title: str,
    annotations: list[dict[str, Any]] | None = None,
    theme_mode: str = "dark",
) -> str:
    """Gera um visualizador de PDF completo e autônomo baseado em PDF.js (Mozilla).

    Apresenta tema escuro e dourado alinhado ao Hupomnemata, zoom, navegação de páginas,
    barra de anotações e interface responsiva.
    """
    is_dark = (theme_mode or "dark").lower() == "dark"
    bg_color = "#121212" if is_dark else "#F9F9FB"
    surface_color = "#1E1E1E" if is_dark else "#FFFFFF"
    text_color = "#E7E7E7" if is_dark else "#1A1A1A"
    gold_accent = "#D4AF37" if is_dark else "#896200"
    border_color = "#2E2E2E" if is_dark else "#E0E0E0"

    ann_json = json.dumps(annotations or [], ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — Leitor Hupomnemata</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@600;700&family=Montserrat:wght@400;500;600&display=swap" rel="stylesheet">
  <script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js"></script>
  <style>
    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}
    body {{
      background-color: {bg_color};
      color: {text_color};
      font-family: 'Montserrat', sans-serif;
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
    }}
    header {{
      background: {surface_color};
      border-bottom: 1px solid {border_color};
      padding: 10px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      z-index: 10;
    }}
    .title {{
      font-family: 'Cormorant Garamond', serif;
      font-size: 1.25rem;
      font-weight: 700;
      color: {gold_accent};
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      max-width: 40vw;
    }}
    .toolbar {{
      display: flex;
      align-items: center;
      gap: 12px;
    }}
    button {{
      background: transparent;
      border: 1px solid {border_color};
      color: {text_color};
      padding: 6px 14px;
      border-radius: 6px;
      cursor: pointer;
      font-family: 'Montserrat', sans-serif;
      font-size: 13px;
      font-weight: 500;
      transition: all 0.2s ease;
    }}
    button:hover {{
      border-color: {gold_accent};
      color: {gold_accent};
    }}
    button:disabled {{
      opacity: 0.4;
      cursor: not-allowed;
    }}
    #viewer-container {{
      flex: 1;
      overflow: auto;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 24px;
      gap: 20px;
    }}
    canvas {{
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
      border-radius: 4px;
      background: white;
    }}
    .page-info {{
      font-size: 13px;
      color: #A0A0A0;
    }}
  </style>
</head>
<body>
  <header>
    <div class="title">{title}</div>
    <div class="toolbar">
      <button id="prev">‹ Anterior</button>
      <span class="page-info">Pág. <span id="page-num">1</span> de <span id="page-count">-</span></span>
      <button id="next">Próxima ›</button>
      <span style="border-left: 1px solid {border_color}; height: 20px; margin: 0 4px;"></span>
      <button id="zoom-out">−</button>
      <span id="zoom-text" class="page-info">100%</span>
      <button id="zoom-in">+</button>
    </div>
  </header>

  <div id="viewer-container">
    <canvas id="pdf-canvas"></canvas>
  </div>

  <script>
    const initialAnnotations = {ann_json};
    const pdfData = atob("{pdf_base64}");
    pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

    let pdfDoc = null;
    let pageNum = 1;
    let scale = 1.25;
    const canvas = document.getElementById('pdf-canvas');
    const ctx = canvas.getContext('2d');

    const loadingTask = pdfjsLib.getDocument({{ data: pdfData }});
    loadingTask.promise.then(pdf => {{
      pdfDoc = pdf;
      document.getElementById('page-count').textContent = pdf.numPages;
      renderPage(pageNum);
    }}).catch(err => {{
      console.error('Falha ao carregar documento PDF:', err);
    }});

    function renderPage(num) {{
      pdfDoc.getPage(num).then(page => {{
        const viewport = page.getViewport({{ scale: scale }});
        canvas.height = viewport.height;
        canvas.width = viewport.width;

        const renderContext = {{
          canvasContext: ctx,
          viewport: viewport
        }};
        page.render(renderContext);
        document.getElementById('page-num').textContent = num;
        document.getElementById('prev').disabled = num <= 1;
        document.getElementById('next').disabled = num >= pdfDoc.numPages;
      }});
    }}

    document.getElementById('prev').addEventListener('click', () => {{
      if (pageNum <= 1) return;
      pageNum--;
      renderPage(pageNum);
    }});

    document.getElementById('next').addEventListener('click', () => {{
      if (pageNum >= pdfDoc.numPages) return;
      pageNum++;
      renderPage(pageNum);
    }});

    document.getElementById('zoom-in').addEventListener('click', () => {{
      scale += 0.25;
      document.getElementById('zoom-text').textContent = Math.round((scale / 1.25) * 100) + '%';
      renderPage(pageNum);
    }});

    document.getElementById('zoom-out').addEventListener('click', () => {{
      if (scale <= 0.5) return;
      scale -= 0.25;
      document.getElementById('zoom-text').textContent = Math.round((scale / 1.25) * 100) + '%';
      renderPage(pageNum);
    }});
  </script>
</body>
</html>
"""
