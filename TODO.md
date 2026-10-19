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

- [ ] `PatentFormatter` — requerente, representante, número, depósito e
  concessão.
- [ ] `AudiovisualFormatter` — responsabilidades, suporte, duração, som e cor.
- [ ] `AudioFormatter` — responsabilidades gerais e da parte, suporte e
  identificador da parte.
- [x] `MusicalScoreFormatter` — autoria, instrumentação, publicação,
  descrição física, partes de coletânea e acesso on-line.
- [ ] `VisualFormatter` — dados bibliográficos aplicáveis a documentos visuais.
- [ ] `CartographicFormatter` — edição e dados de publicação.
- [ ] `ThreeDimensionalFormatter` — tipo de responsabilidade e dados de
  fabricação.
- [ ] Para cada formatter novo, adicionar testes de referência completa,
  campos opcionais e combinações inválidas ou incompletas de dados.

## 4. Encerrar a etapa de referências

- [ ] Confirmar que todos os tipos cadastráveis têm formatter ligado à
  interface e coberto por testes.
- [ ] Comparar referências geradas com exemplos ABNT aprovados e documentar
  exceções por tipo documental.
- [ ] Atualizar a documentação de escopo e status dos formatters.

## 5. Retomar as funcionalidades planejadas

- [ ] Importação de metadados.
- [ ] Fichamento rápido e notas de leitura.
- [ ] Exportação de referências e dados.
- [ ] Grafo conceitual.
