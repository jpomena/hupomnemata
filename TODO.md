# TODO — Roteiro de Desenvolvimento e Próximos Passos

## 1. Formatadores e Referências ABNT

- [x] Definir uma única entrada de formatação por tipo documental e conectá-la aos cards do acervo.
- [x] Registrar explicitamente os tipos sem formatter e impedir retorno de referências vazias.
- [x] Integrar `DigitalFormatter` ao fluxo e exportá-lo em `src/strategies/__init__.py`.
- [x] Adicionar testes de dispatch que cubram todos os tipos documentais e confirmem o roteamento correto.
- [x] Implementar e cobrir formatadores para todos os tipos documentais do acervo:
  - [x] `MonographFormatter` (livros, teses, dissertações, folhetos).
  - [x] `PeriodicalFormatter` (artigos de revista, artigos de jornal, coleções periódicas).
  - [x] `ProceedingsFormatter` (anais monográficos e periódicos).
  - [x] `LegalDocsFormatter` (legislação e jurisprudência).
  - [x] `PatentFormatter` (patentes, requerentes, concessões).
  - [x] `AudiovisualFormatter` (filmes, vídeos, suportes e dados técnicos).
  - [x] `AudioFormatter` (gravações sonoras, suportes e mídias).
  - [x] `MusicalScoreFormatter` (partituras, instrumentos, coletâneas).
  - [x] `VisualFormatter` (fotografias, gravuras, pinturas).
  - [x] `CartographicFormatter` (mapas, cartas geográficas, atlas).
  - [x] `ThreeDimensionalFormatter` (esculturas, fósseis, maquetes, artefatos 3D).
  - [x] `DigitalFormatter` (documentos e recursos eletrônicos em rede).
- [ ] Refinar casos raros de anais sem evento explícito e convenções complementares de subtítulos.

---

## 2. Reestruturação Hierárquica de Revistas

- [x] Tratar a entidade `Magazine` como agrupador guarda-chuva hierárquico em vez de obra documental avulsa.
- [x] Omitir `Magazine` do catálogo de inserção avulsa ("Nova Obra") e das contagens gerais do acervo no Dashboard e Sidebar.
- [x] Integrar a linha da revista na tabela do Acervo com banner editorial colinear (`_magazine_banner_row`).
- [x] Alinhamento do glifo com a coluna de checkboxes e do título com as obras-pai de primeiro nível.
- [x] Controles de expansão e recolhimento de artigos associados.
- [x] Busca unificada (filtragem simultânea por nome do periódico e títulos de artigos).
- [x] Ordenação hierárquica por título com primazia do periódico sobre os artigos vinculados.
- [x] Exclusão em cascata (remover uma revista apaga seus artigos subordinados) e sincronização de metadados.

---

## 3. Importação Automatizada de Metadados

- [x] Modal dedicado de importação por identificador único (DOI, ISBN, ISSN) integrado ao fluxo de cadastro de obras.
- [x] Coalescência inteligente de dados multi-provedor (Crossref, Open Library, Google Books, BrasilAPI).
- [x] Resolução de duplicidade de autores com nomes semelhantes.
- [x] Dedução automática e enriquecimento de local de publicação via catálogo canônico (`publisher_places.json`).
- [x] Preenchimento automático da data de acesso para itens digitais com URL.
- [x] Suíte de testes automatizados com mocks de rede (`test_metadata_import.py`).

---

## 4. Importação Reversa de Referências Bibliográficas

- [x] Módulo `reference_parser` para extração de campos em listas textuais de referências.
- [x] Suporte aos estilos ABNT, APA, Chicago e blocos brutos em BibTeX.
- [x] Integração com o assistente Nous para desambiguação e estruturação semântica de referências complexas.
- [x] Modal de importação reversa com interface de pré-visualização e edição dos campos antes do cadastro definitivo no Acervo.
- [x] Suíte de testes automatizados unitários e de integração (`test_reference_parser.py`, `test_reverse_import.py`).

---

## 5. Gestão de Fragmentos (Fichamento)

- [x] Associação de citações e paráfrases a obras cadastradas no Acervo.
- [x] Tipagem estrita de localizadores: página, capítulo, seção, posição e tempo (áudio/vídeo).
- [x] CRUD completo de fragmentos (criação, edição, listagem e remoção com integridade referencial).
- [x] Exclusão em cascata coerente ao remover uma obra do acervo.
- [ ] Adição de sistema de tags/etiquetas para busca transversal de fragmentos.
- [ ] Mecanismo de fichamento rápido via área de transferência (clipboard watcher).

---

## 6. Compilações e Caderno de Escrita

- [x] Criação de compilações com nome, descrição e reordenação manual de obras.
- [x] Vinculação de obras e fragmentos existentes a múltiplos projetos sem redundância interna.
- [x] Hub da Compilação com métricas, visualização aninhada e busca de obras/fragmentos.
- [x] Criação de obras e fragmentos diretamente a partir do hub com vinculação automática.
- [x] Caderno de trabalho com esqueleto de escrita articulado:
  - [x] Organização em seções/ideias com ordenação manual.
  - [x] Caixa de entrada "A organizar" para fragmentos vinculados.
  - [x] Registro de ideia central e notas de articulação por seção.
  - [x] Cópia formatada do texto articulado completo com referências bibliográficas ABNT.
- [ ] Exportação de compilações completas para arquivos Markdown, LaTeX e DOCX.

---

## 7. Experiência Visual e Design System

- [x] Consolidação da biblioteca de componentes `ui_kit` e tokens canônicos de espaçamento e tipografia.
- [x] Suporte refinado aos temas Claro e Escuro com paleta acadêmica sóbria (ouro, cromo e surface).
- [x] Diferenciação estrutural dos cabeçalhos das telas com plano de fundo em `surface` e linha divisória inferior.
- [x] Cabeçalho da tabela do Acervo com acabamento em `chrome`, divisor inferior dourado e realce da coluna ativa de ordenação.
- [x] Hover states refinados em cards, linhas de tabela e elementos interativos.
- [x] Ajuste e respiro vertical nos contadores (KPIs) do Dashboard.

---

## 8. Próximas Funcionalidades Planejadas

- [ ] **Exportação Abrangente**:
  - Exportação de obras e referências em formatos de intercâmbio bibliográfico (BibTeX, RIS, CSL-JSON).
- [ ] **Grafo Conceitual (Malha de Conhecimento)**:
  - Integração nativa da visualização interativa da malha conceitual na interface desktop (atualmente prototipada em `data/knowledge_mesh.html`).
- [ ] **Taxonomia Transversal**:
  - Sistema de etiquetas (tags) unificado para obras, fragmentos e ideias.
- [ ] **Portabilidade de Dados**:
  - Mecanismo de exportação/importação de backups e migração do caminho do banco SQLite para o diretório padrão de dados do usuário do sistema operacional (AppData/XDG).
