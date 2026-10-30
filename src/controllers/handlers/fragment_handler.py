"""Handler para operações e persistência de fragmentos e citações."""

from src.utils.error_log import log_exception


class FragmentControllerMixin:
    """Gerencia a criação, atualização e exclusão de citações e fragmentos textuais."""

    def save_fragment(
        self,
        fragment_id: int | None,
        data: dict[str, object],
    ) -> bool:
        try:
            if fragment_id is None:
                self.fragment_service.create(data)
                message = 'Fragmento cadastrado.'
            else:
                self.fragment_service.update(fragment_id, data)
                message = 'Fragmento atualizado.'

            bib_res_id = data.get('bib_res_id')
            if bib_res_id and hasattr(self, 'knowledge_service'):
                try:
                    self.knowledge_service.revectorize_work(int(bib_res_id))
                except Exception:
                    pass
        except (ValueError, TypeError) as error:
            self.show_message(str(error), self.view_config.colors['text'])
            return False
        except Exception as error:
            log_exception('Falha ao salvar fragmento', error)
            self.show_message(
                f'Não foi possível salvar o fragmento.\n\n{error}',
                self.view_config.colors['text'],
            )
            return False

        self.navigate('Fragmentos')
        self.show_message(message, self.view_config.colors['gold'])
        return True

    def save_compilation_fragment(
        self,
        compilation_id: int,
        fragment_id: int | None,
        data: dict[str, object],
    ) -> bool:
        try:
            payload = self.fragment_service._payload(data)
            if fragment_id is None:
                self.compilation_service.create_fragment(
                    compilation_id,
                    payload,
                )
                message = 'Fragmento cadastrado na compilação.'
            else:
                if not self.compilation_service.contains_work(
                    compilation_id,
                    payload['bib_res_id'],
                ):
                    raise ValueError(
                        'A obra do fragmento deve pertencer à compilação.'
                    )
                self.fragment_service.update(fragment_id, payload)
                message = 'Fragmento atualizado.'

            if hasattr(self, 'knowledge_service'):
                try:
                    self.knowledge_service.revectorize_work(int(payload['bib_res_id']))
                except Exception:
                    pass
        except (ValueError, TypeError) as error:
            self.show_message(str(error), self.view_config.colors['text'])
            return False
        except Exception as error:
            log_exception(
                'Falha ao salvar fragmento pela compilação',
                error,
            )
            self.show_message(
                f'Não foi possível salvar o fragmento.\n\n{error}',
                self.view_config.colors['text'],
            )
            return False

        self.refresh_compilation_hub(compilation_id)
        self.show_message(message, self.view_config.colors['gold'])
        return True

    def delete_fragment(self, fragment_id: int) -> None:
        try:
            bib_res_id = self.fragment_service.delete(fragment_id)
            if bib_res_id and hasattr(self, 'knowledge_service'):
                try:
                    self.knowledge_service.revectorize_work(int(bib_res_id))
                except Exception:
                    pass
        except Exception as error:
            log_exception('Falha ao excluir fragmento', error)
            self.show_message(
                f'Não foi possível excluir o fragmento.\n\n{error}',
                self.view_config.colors['text'],
            )
            return

        self.navigate('Fragmentos')
        self.show_message(
            'Fragmento excluído.', self.view_config.colors['gold']
        )

    def search_fragment_works(self, query: str) -> list[tuple[int, str]]:
        try:
            return self.service.search_works(query, include_partial=True)
        except Exception as error:
            log_exception('Falha ao buscar obras para fragmentos', error)
            self.show_message(
                f'Não foi possível buscar obras no Acervo.\n\n{error}',
                self.view_config.colors['text'],
            )
            return []
