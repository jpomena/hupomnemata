# Hupomnēmata

O **Hupomnēmata** é um ambiente pessoal e integrado de pesquisa, gestão bibliográfica em conformidade com as normas ABNT, fichamento de leitura (citações e paráfrases) e estruturação de cadernos de escrita/compilações, com suporte a inteligência artificial (Nous) e interface desktop de alta fidelidade desenvolvida em Flet.

Inspirado no conceito clássico foucaultiano dos *hupomnēmata* — os cadernos de anotações que serviam à constituição de si e à organização do pensamento —, o sistema reúne o rigor da catalogação acadêmica e a fluidez necessária para a redação de trabalhos científicos, ensaios e monografias.

---

## Funcionalidades e Escopo Atual

### 1. Acervo Bibliográfico e Formatação ABNT
* **Catálogo Multidocumental Extensivo**: Suporte a 18 tipos documentais cadastráveis, incluindo monografias, dissertações e teses, artigos de periódicos e jornais, anais de eventos, correspondências, legislação, jurisprudência, patentes, partituras, gravações sonoras, audiovisuais, documentos visuais, cartográficos, tridimensionais e digitais.
* **Formatadores ABNT Canônicos**: Mecanismo modular de formatação para todos os tipos do acervo, cobrindo autoria individual, múltipla e institucional, obras anônimas ou sem autor (entrada por título com destaque tipográfico) e controle para preservação da grafia original do título.
* **Reestruturação Hierárquica de Revistas**: Os periódicos (`Magazine`) atuam como entidades agrupadoras guarda-chuva diretamente na tabela do Acervo. Exibem banner editorial com alinhamento milimétrico, expansão/recolhimento de artigos, busca combinada (título do periódico e título do artigo) e ordenação hierárquica primária pelo nome da revista, sem inflar a contagem de obras avulsas do acervo.

### 2. Importação Automatizada de Metadados
* **Importação por Identificadores**: Cadastro instantâneo via DOI, ISBN e ISSN diretamente pelo modal de inserção de obras.
* **Coalescência Multi-Provedor**: Consulta orquestrada a múltiplos serviços públicos e acadêmicos (Crossref, Open Library, Google Books e BrasilAPI).
* **Enriquecimento Canônico**: Resolução automática de duplicidade de autores, dedução de local de publicação baseada em dicionário canônico de editoras (`publisher_places.json`) e atribuição padrão de data de visualização para documentos digitais.

### 3. Importação Reversa de Referências Bibliográficas (via Nous)
* **Parser de Referências em Texto Bruto**: Mecanismo híbrido de extração (regras sintáticas/expressões regulares e estruturação semântica assistida pelo assistente Nous).
* **Compatibilidade Normativa**: Processamento de referências nos formatos ABNT, APA, Chicago e blocos BibTeX brutos.
* **Modal de Prévia e Ajustes**: Revisão interativa dos campos extraídos antes da persistência no banco de dados.

### 4. Gestão de Fragmentos (Fichamento Acadêmico)
* **Citações e Paráfrases**: Registro de excertos textuais e paráfrases vinculados às obras do Acervo.
* **Localização Tipada**: Especificação rigorosa de localizador (página, capítulo, seção, posição e marcação temporal para mídia contínua).
* **Integridade Relacional**: Exclusão em cascata (remover uma obra remove com segurança seus fragmentos associados).

### 5. Compilações e Caderno de Escrita
* **Projetos de Pesquisa**: Organização de obras e fragmentos em projetos temáticos, sem duplicações por compilação.
* **Hub da Compilação**: Painel dedicado com métricas do projeto, listagem de obras e fragmentos aninhados, e filtros de busca.
* **Caderno de Trabalho (Esqueleto de Escrita)**:
  * Agrupamento de fragmentos selecionados em ideias/seções temáticas com ordenação manual.
  * Seção temporária "A organizar" para alocação fluida de trechos.
  * Registro de ideia central e notas de articulação por seção.
  * Cópia articulada do texto completo acompanhado das respectivas referências ABNT formatadas.

### 6. Experiência Visual e Design System Acadêmico
* **Paleta Nobre**: Suporte integral a temas Claro e Escuro, com contrastes elegantes em tons dourados (`gold`), cromados (`chrome`) e superfícies texturizadas.
* **Hierarquia Estrutural**: Cabeçalhos soberanos demarcados com sutil elevação em `surface` e borda divisória inferior em todas as telas principais (Dashboard, Acervo, Fragmentos, Compilações e Hubs).
* **Gabinete de Leitura (Dashboard)**: Faixa de KPIs clicáveis para navegação direta aos fluxos do sistema, com espaçamento vertical harmônico, acompanhamento de compilações em andamento, atividade recente e distribuição documental do acervo.
* **Tabela do Acervo Otimizada**: Cabeçalho destacado em cromo com divisor dourado, realce visual na coluna ativa de ordenação, hover refinado e paginação/rolagem suave.

---

## Requisitos

* Python 3.12 ou superior (testado e homologado em Python 3.14).
* Ambiente virtual Python recomendado.

---

## Instalação e Execução

1. **Clonar o repositório e criar o ambiente virtual:**
   ```powershell
   git clone https://github.com/jpomena/hupomnemata.git
   cd hupomnemata
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. **Instalar as dependências:**
   ```powershell
   pip install -r requirements.txt
   ```

3. **Iniciar a aplicação:**
   ```powershell
   python main.py
   ```

---

## Testes Automatizados

A suíte de testes cobre formatadores, validações de domínio, repositórios, serviços de metadados, parsers de referências e fluxos visuais Flet:

```powershell
python -m pytest
```

Atualmente, **343 testes automatizados** garantem a integridade operacional e visual do sistema.

---

## Estrutura do Projeto

* `main.py`: Ponto de entrada da aplicação Flet.
* `src/controllers`: Orquestração de fluxos de navegação e submissão de dados.
* `src/views`: Interfaces Flet, componentes modulares (`ui_kit`), modais de importação e telas principais.
* `src/domains`: Entidades de domínio e mapeamentos relacionais SQLAlchemy.
* `src/contracts.py`: Dataclasses e contratos compartilhados entre camadas.
* `src/repositories`: Camada de persistência em SQLite.
* `src/services`: Regras de negócio, coalescência de metadados (`metadata_service`), integração Nous (`nous_service`) e gerenciamento de compilações.
* `src/strategies`: Formatadores bibliográficos segundo normas ABNT.
* `src/utils`: Parsers de referência (`reference_parser`), formatadores de datas e manipuladores de estilo.
* `src/configs`: Textos, paletas de cores (`colors.yaml`), tipografia e parâmetros visuais.
* `tests`: Suíte completa de testes automatizados unitários e de integração.

---

## Arquitetura e Fluxo de Dados

As views operam de modo puramente declarativo e reativo, interagindo com os controladores exclusivamente via callbacks e estruturas de dados de `src/contracts.py`.

```
[View / Flet UI] ──(Callbacks / Contracts)──> [Controllers]
                                                    │
                 ┌──────────────────────────────────┴──────────────────────────────────┐
                 ▼                                                                     ▼
           [Services]                                                            [Strategies]
  (Metadata, Nous, Submissions)                                            (Formatadores ABNT)
                 │
                 ▼
          [Repositories]
                 │
                 ▼
       [SQLite / SQLAlchemy]
```

---

## Observações de Desenvolvimento

* **Banco de Dados**: Em ambiente de desenvolvimento, o arquivo SQLite reside em `src/db/hupomnemata.db`.
* **Auditoria de Logs**: Exceções tratadas e diagnósticos de execução são registrados com stack trace completo em `logs/hupomnemata.txt`.
