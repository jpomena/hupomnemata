# TODO — próximos passos

## 1. Consolidar o fluxo de formatação

- [X] Definir uma única entrada de formatação por tipo documental e conectá-la
  aos cards do acervo.
- [x] Registrar explicitamente os tipos sem formatter; não retornar uma
  referência vazia como se a formatação tivesse sido concluída.
- [x] Integrar `DigitalFormatter` ao fluxo e exportá-lo em
  `src/strategies/__init__.py`.
- [ ] Adicionar testes de dispatch que cubram todos os tipos documentais e
  confirmem que cada tipo chega ao formatter correspondente.

## 2. Completar e cobrir os formatters existentes

- [ ] Revisar `ProceedingsFormatter` contra exemplos de referência ABNT.
- [ ] Cobrir anais monográficos publicados e não publicados, anais periódicos,
  trabalhos parciais, paginação e ausência de obra-pai.
- [ ] Criar testes focados para `LegalDocsFormatter` e `DigitalFormatter`,
  incluindo campos opcionais, URLs e datas ausentes.
- [ ] Verificar nos formatters existentes a regra comum de títulos, autores,
  pontuação, subtítulos e campos opcionais; preservar as diferenças previstas
  para cada tipo documental.

## 3. Implementar os formatters ausentes

- [x] `PatentFormatter` — requerente, representante, número, depósito e
  concessão.
- [x] `AudiovisualFormatter` — responsabilidades, suporte, duração, som e cor.
- [x] `AudioFormatter` — responsabilidades gerais e da parte, suporte e
  identificador da parte.
- [x] `MusicalScoreFormatter` — autoria, instrumentação, publicação,
  descrição física, partes de coletânea e acesso on-line.
- [x] `VisualFormatter` — dados bibliográficos aplicáveis a documentos visuais.
- [x] `CartographicFormatter` — edição e dados de publicação.
- [x] `ThreeDimensionalFormatter` — tipo de responsabilidade e dados de
  fabricação.
- [ ] Para cada formatter novo, adicionar testes de referência completa,
  campos opcionais e combinações inválidas ou incompletas de dados.

## 4. Encerrar a etapa de referências

- [ ] Confirmar que todos os tipos cadastráveis têm formatter ligado à
  interface e coberto por testes.
- [ ] Comparar referências geradas com exemplos ABNT aprovados e documentar
  exceções por tipo documental.
- [ ] Atualizar a documentação de escopo e status dos formatters.

## 5. Implementar Fragmentos

- [x] Associar citações e comentários a obras do Acervo.
- [x] Exigir localização tipada em citações e permitir localização opcional
  em comentários.
- [x] Oferecer localizadores por página, capítulo, seção, posição e tempo.
- [x] Criar, listar, editar e excluir fragmentos; remover fragmentos junto com
  a obra associada.
- [x] Migrar citações legadas para o novo modelo sem perder seus dados.
- [ ] Adicionar tags para organizar fragmentos.

## 6. Compilações

- [x] Criar compilações com nome obrigatório e descrição opcional.
- [x] Reunir obras do Acervo em várias compilações, sem duplicatas por projeto.
- [x] Permitir adicionar, remover e reordenar obras manualmente.
- [x] Preservar obras e fragmentos ao excluir uma compilação.
- [x] Buscar compilações por nome e descrição, com sugestões de resultados.
- [x] Abrir um hub por compilação com visão geral e obras/fragmentos aninhados.
- [x] Vincular fragmentos existentes a várias compilações sem duplicatas.
- [x] Criar e editar obras e fragmentos pelo hub, restringindo fragmentos às
  obras vinculadas ao projeto.
- [x] Criar caderno de trabalho como esqueleto de escrita, com seções/ideias,
  fragmentos organizáveis, notas de articulação e cópia com referências.

## 7. Retomar outras funcionalidades planejadas

- [ ] Importação de metadados.
- [ ] Exportação de referências e dados.
- [ ] Grafo conceitual.
