# Checklist de Fumaça — Hupomnemata

Executar após cada ciclo de correção que toque banco, credenciais ou UI.
Marque apenas o que foi observado; qualquer falha vira item no TODO.

## 1. Inicialização e dados

- [ ] `python main.py` abre a janela sem erro no terminal.
- [ ] O banco é criado em `%LOCALAPPDATA%\Hupomnemata\hupomnemata.db`
      (ou `$XDG_DATA_HOME/hupomnemata/`), **fora** da árvore do repositório.
- [ ] Na primeira execução com banco legado, `src/db/hupomnemata.db` é copiado
      para o novo destino e permanece intacto no lugar.
- [ ] Existe `backups/` no diretório de dados; se houve reparo, há um
      `fk_quarantine_*.jsonl` com registros completos.
- [ ] Segunda execução não repete a migração nem cria novo backup.

## 2. Integridade

- [ ] Abrir o Acervo: as 18 obras (ou o total esperado) aparecem.
- [ ] Remover uma obra de teste com fragmentos: fragmentos e associações somem.
- [ ] Abrir o leitor de PDF em janela separada enquanto a janela principal
      está aberta: nenhum `database is locked`.
- [ ] Salvar uma anotação no leitor e confirmar que ela aparece na janela
      principal após fechar/reabrir o leitor.
- [ ] `PRAGMA integrity_check` = `ok` e `PRAGMA foreign_key_check` vazio
      (via script ou cliente SQLite).

## 3. Credenciais

- [ ] Configurações → Nous: salvar uma chave Gemini.
- [ ] O arquivo `user_preferences.json` **não** contém a chave em texto puro.
- [ ] A chave aparece no Windows Credential Manager (ou Keychain/Secret Service)
      como serviço `hupomnemata`, usuário `gemini_api_key`.
- [ ] “Testar conexão” do Nous retorna sucesso (ou erro de rede claro).
- [ ] Google Drive: autenticar, sincronizar, sair. `token.json` não deve
      permanecer no diretório de configuração após a autenticação.

## 4. Importação e formatação

- [ ] Importar DOI `10.1038/nature.2014.14583` → modal pré-preenchido como
      artigo de revista.
- [ ] Importar ISBN `9788575594841` → livro com editora/dados corretos.
- [ ] Importar ISSN `0101-3300` → coleção periódica com revista vinculada.
- [ ] Copiar referência ABNT de um livro, de um artigo e de uma obra sem autor.
- [ ] Importação reversa de um bloco ABNT com 3 referências: prévia e cadastro.

## 5. Experiência visual

- [ ] Alternar tema claro/escuro: cabeçalhos, tabela do acervo e sidebar coerentes.
- [ ] Alterar escala manual (0,80–1,40) e reiniciar: escala preservada.
- [ ] Abrir “Estruturas de Saber”: grafo renderiza, zoom/pan funcionam e o tema
      do HTML exportado coincide com o do app.
- [ ] Abrir o leitor de PDF: barra, paginação, zoom e marcações legíveis nos
      dois temas.

## 6. Thread-safety da interface

- [ ] Gerar síntese de uma obra no Nous: snackbar aparece, lista atualiza e a janela
      permanece responsiva (sem congelamento).
- [ ] Processar lote no Nous: barra de progresso avança e pode ser observada em
      tempo real.
- [ ] Importação reversa: rótulo/barra de progresso avançam por referência e a
      fase final renderiza uma única vez, sem `RuntimeError`.
- [ ] Sincronização e autenticação do Google Drive em Configurações: status
      atualiza durante a operação e o modal de conflito abre corretamente.
- [ ] Nenhum `page.update()` chamado de thread de trabalho aparece no log.

## 7. Qualidade automatizada

```powershell
python -m pytest -q
python -m flake8 src tests main.py
```
