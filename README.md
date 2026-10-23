
# Hupomnēmata

O Hupomnēmata é um gerenciador pessoal de referências, citações e notas de leitura, com foco inicial em referências bibliográficas no formato ABNT.

O projeto ainda está em fase de protótipo. A interface principal já existe em Flet, o cadastro de obras já passa pelo controller e pela camada de repositório, e os primeiros formatadores implementados cobrem monografias e periódicos.

## Escopo Atual

* Cadastro local de obras bibliográficas.
* Cadastro de obras com autoria opcional; sem autor, a referência começa pelo título.
* Opção por obra para preservar a grafia original do título nas referências.
* Cadastro de citações e comentários vinculados às obras do Acervo.
* Organização de obras em compilações com nome, descrição opcional e ordem manual.
* Localização tipada de fragmentos, com página, capítulo, seção, localizador/posição ou tempo.
* Persistência em SQLite via SQLAlchemy.
* Modelagem de diferentes tipos documentais.
* Cadastro de revistas sem autoria obrigatória, vinculadas a artigos e coleções periódicas.
* Formatação ABNT inicial para monografias.
* Formatação ABNT inicial para periódicos.
* Interface desktop com Flet.

Citações exigem um tipo e um valor de localização; comentários podem ser registrados sem localização. O cadastro de fragmentos permite criar, listar, editar e excluir registros. Ao excluir uma obra, seus fragmentos também são removidos.

Compilações funcionam como projetos de pesquisa ou escrita: uma obra pode participar de várias compilações, sem duplicação dentro do mesmo projeto. O dashboard permite buscar por nome ou descrição e abrir o hub de cada projeto, com abas para editar seus dados e organizar obras e fragmentos. Os fragmentos das obras vinculadas aparecem aninhados por obra. No caderno de trabalho, o usuário transforma a seleção de fragmentos em um esqueleto de escrita: organiza-os em seções/ideias, registra a ideia central e notas de articulação, e copia o conjunto com suas referências formatadas. Fragmentos selecionados que ainda não foram organizados ficam em “A organizar”; mover um fragmento entre ideias não cria duplicatas. A seleção e as notas continuam específicas de cada compilação. O usuário pode reordenar ideias; remover uma delas devolve seus fragmentos a “A organizar” sem desfazer a seleção. O hub também permite criar e editar obras e fragmentos; fragmentos criados ali são vinculados automaticamente e só podem pertencer a obras do projeto. A exclusão de uma compilação ou a remoção de uma obra dela remove apenas os vínculos do projeto, preservando as obras e os fragmentos no Acervo. Ao excluir uma obra do Acervo, seus fragmentos e vínculos com compilações também são removidos.

Alguns menus e cards da interface ainda são lembretes visuais de funcionalidades planejadas, como importação de metadados, fichamento rápido, exportação e grafo conceitual.

## Requisitos

* Python 3.12 ou superior.
* Ambiente virtual Python recomendado.

## Instalação

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

```

## Executando

```powershell
.\.venv\Scripts\python.exe main.py

```

## Testes

```powershell
.\.venv\Scripts\python.exe -m pytest -q

```

## Estrutura

* `main.py`: ponto de entrada da aplicação Flet.
* `src/controllers`: orquestração dos fluxos da aplicação.
* `src/views`: composição da interface.
* `src/domains`: modelos de domínio e mapeamentos SQLAlchemy.
* `src/contracts.py`: estruturas de dados compartilhadas entre camadas.
* `src/repositories`: persistência e recuperação de dados.
* `src/strategies`: formatadores de referências.
* `src/utils`: tipos auxiliares e utilitários compartilhados.
* `src/configs`: textos, cores, tipografia e parâmetros de UI.
* `tests`: testes automatizados.

## Fluxo entre Camadas

As views compõem a interface e enviam eventos por callbacks, sem importar formatters nem repositórios; contratos compartilhados ficam em `src/contracts.py`. O `CoreController` coordena as telas e seleciona o formatter adequado para cada obra. O `WorkSubmissionController` cuida do fluxo de cadastro e resolução de autores duplicados. O `WorkFormService` converte os valores dos formulários em payloads de domínio, o `WorkService` coordena as operações de obras e o `WorkRepository` concentra o acesso ao SQLAlchemy. O `FragmentService` e o `FragmentRepository` coordenam e persistem citações e comentários associados ao Acervo. O `CompilationService` e o `CompilationRepository` gerenciam os projetos, seus vínculos ordenáveis com as obras, as seções do esqueleto e os fragmentos selecionados, distribuídos e anotados no caderno de trabalho; o `CompilationHubComposer` apresenta o hub de cada projeto.

## Status dos Formatadores

Todos os tipos de obra possuem formatadores já construídos. Ainda precisam de testagem mais extensiva, mas aparentam já ter nível de uso. A cobertura automatizada também precisa ser ampliada para além de monografias e periódicos. Consulte TODO.md para a lista priorizada de próximos passos.

## Observações de Desenvolvimento

Durante o protótipo, o banco SQLite fica em `src/db/hupomnemata.db`. Em uma versão distribuível, o ideal é mover os dados do usuário para uma pasta externa ao código-fonte, mantendo o repositório apenas com código, configurações e migrações.

Exceções tratadas pela aplicação, inclusive as exibidas na interface, são registradas com traceback em `logs/hupomnemata.txt` para auditoria. A pasta de logs é ignorada pelo Git.

---