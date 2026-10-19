# Hupomnēmata

Hupomnēmata e um gerenciador pessoal de referencias, citacoes e notas de
leitura, com foco inicial em referencias bibliograficas no formato ABNT.

O projeto ainda esta em fase de prototipo. A interface principal ja existe em
Flet, o cadastro de obras ja passa pelo controller e pela camada de repositorio,
e os primeiros formatadores implementados cobrem monografias e periodicos.

## Escopo Atual

- Cadastro local de obras bibliograficas.
- Persistencia em SQLite via SQLAlchemy.
- Modelagem de diferentes tipos documentais.
- Cadastro de revistas sem autoria obrigatória, vinculadas a artigos e
  coleções periódicas.
- Formatacao ABNT inicial para monografias.
- Formatacao ABNT inicial para periodicos.
- Interface desktop com Flet.

Alguns menus e cards da interface ainda sao lembretes visuais de funcionalidades
planejadas, como importacao de metadados, fichamento rapido, exportacao e grafo
conceitual.

## Requisitos

- Python 3.12 ou superior.
- Ambiente virtual Python recomendado.

## Instalacao

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

- `main.py`: ponto de entrada da aplicacao Flet.
- `src/controllers`: orquestracao dos fluxos da aplicacao.
- `src/views`: composicao da interface.
- `src/domains`: modelos de dominio e mapeamentos SQLAlchemy.
- `src/contracts.py`: estruturas de dados compartilhadas entre camadas.
- `src/repositories`: persistencia e recuperacao de dados.
- `src/strategies`: formatadores de referências.
- `src/utils`: tipos auxiliares e utilitarios compartilhados.
- `src/configs`: textos, cores, tipografia e parametros de UI.
- `tests`: testes automatizados.

## Fluxo entre camadas

As views compoem a interface e enviam eventos por callbacks, sem importar
formatters nem repositórios; contratos compartilhados ficam em
`src/contracts.py`. O `CoreController` coordena as telas e seleciona o
formatter adequado para cada obra. O `WorkSubmissionController` cuida do fluxo
de cadastro e resolução de autores duplicados. O `WorkFormService` converte os
valores dos formulários em payloads de domínio, o `WorkService` coordena as
operações de obras e o `WorkRepository` concentra o acesso ao SQLAlchemy.

## Status dos Formatadores

Existem formatters para monografias, periodicos, anais, documentos legais e
documentos digitais, todos selecionados pelo controller no fluxo do acervo.
Patentes e documentos multimidia ainda precisam de formatters dedicados. A
cobertura automatizada tambem precisa ser ampliada para alem de monografias e
periodicos. Consulte [TODO.md](./TODO.md) para a lista priorizada de proximos
passos.

## Observacoes de Desenvolvimento

Durante o prototipo, o banco SQLite fica em `src/db/hupomnemata.db`. Em uma
versao distribuivel, o ideal e mover os dados do usuario para uma pasta externa
ao codigo fonte, mantendo o repositorio apenas com codigo, configuracoes e
migracoes.

Excecoes tratadas pela aplicacao, inclusive as exibidas na interface, sao
registradas com traceback em `logs/hupomnemata.txt` para auditoria. A pasta de
logs e ignorada pelo Git.
