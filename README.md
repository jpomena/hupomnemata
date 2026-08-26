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
- `src/repositories`: persistencia e recuperacao de dados.
- `src/strategies`: normalizadores e formatadores.
- `src/utils`: tipos auxiliares e utilitarios compartilhados.
- `src/configs`: textos, cores, tipografia e parametros de UI.
- `tests`: testes automatizados.

## Status dos Formatadores

Ja existem testes para os formatadores de monografias e periodicos. Os demais
tipos documentais estao modelados, mas ainda precisam de formatadores dedicados
antes de serem considerados completos.

## Observacoes de Desenvolvimento

Durante o prototipo, o banco SQLite fica em `src/db/hupomnemata.db`. Em uma
versao distribuivel, o ideal e mover os dados do usuario para uma pasta externa
ao codigo fonte, mantendo o repositorio apenas com codigo, configuracoes e
migracoes.
