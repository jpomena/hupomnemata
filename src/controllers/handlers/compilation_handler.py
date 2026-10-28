"""Handler para operações de compilações, seções do caderno e vínculos."""

import flet as ft

from src.contracts import CompilationPayload, FragmentRecord
from src.utils.error_log import log_exception
from src.views.fragments import FragmentsComposer
from src.views.core_composer import CoreComposer


class CompilationControllerMixin:
    """Orquestra projetos/compilações, seções do esqueleto e fragmentos associados."""

    def search_compilation_works(
        self,
        query: str,
    ) -> list[tuple[int, str]]:
        try:
            return self.service.search_works(query, include_partial=True)
        except Exception as error:
            log_exception('Falha ao buscar obras para compilações', error)
            self.show_message(
                f'Não foi possível buscar obras no Acervo.\n\n{error}',
                self.view_config.colors['text'],
            )
            return []

    def create_compilation(
        self,
        payload: CompilationPayload,
    ) -> int | None:
        try:
            compilation_id = self.compilation_service.create(payload)
        except (ValueError, TypeError) as error:
            self.show_message(str(error), self.view_config.colors['text'])
            return None
        except Exception as error:
            log_exception('Falha ao criar compilação', error)
            self.show_message(
                f'Não foi possível criar a compilação.\n\n{error}',
                self.view_config.colors['text'],
            )
            return None

        self.show_message(
            'Compilação criada.', self.view_config.colors['gold']
        )
        return compilation_id

    def update_compilation(
        self,
        compilation_id: int,
        payload: CompilationPayload,
    ) -> bool:
        try:
            self.compilation_service.update(compilation_id, payload)
        except (ValueError, TypeError) as error:
            self.show_message(str(error), self.view_config.colors['text'])
            return False
        except Exception as error:
            log_exception('Falha ao atualizar compilação', error)
            self.show_message(
                f'Não foi possível atualizar a compilação.\n\n{error}',
                self.view_config.colors['text'],
            )
            return False

        self.show_message(
            'Compilação atualizada.', self.view_config.colors['gold']
        )
        return True

    def delete_compilation(self, compilation_id: int) -> bool:
        try:
            self.compilation_service.delete(compilation_id)
        except (ValueError, TypeError) as error:
            self.show_message(str(error), self.view_config.colors['text'])
            return False
        except Exception as error:
            log_exception('Falha ao excluir compilação', error)
            self.show_message(
                f'Não foi possível excluir a compilação.\n\n{error}',
                self.view_config.colors['text'],
            )
            return False

        self.show_message(
            'Compilação excluída.', self.view_config.colors['gold']
        )
        return True

    def add_work_to_compilation(
        self,
        compilation_id: int,
        bib_res_id: int,
    ) -> bool:
        try:
            self.compilation_service.add_work(compilation_id, bib_res_id)
        except (ValueError, TypeError) as error:
            self.show_message(str(error), self.view_config.colors['text'])
            return False
        except Exception as error:
            log_exception('Falha ao adicionar obra à compilação', error)
            self.show_message(
                f'Não foi possível adicionar a obra.\n\n{error}',
                self.view_config.colors['text'],
            )
            return False

        self.show_message(
            'Obra adicionada à compilação.', self.view_config.colors['gold']
        )
        return True

    def remove_work_from_compilation(
        self,
        compilation_id: int,
        bib_res_id: int,
    ) -> bool:
        try:
            self.compilation_service.remove_work(compilation_id, bib_res_id)
        except (ValueError, TypeError) as error:
            self.show_message(str(error), self.view_config.colors['text'])
            return False
        except Exception as error:
            log_exception('Falha ao remover obra da compilação', error)
            self.show_message(
                f'Não foi possível remover a obra.\n\n{error}',
                self.view_config.colors['text'],
            )
            return False

        self.show_message(
            'Obra removida da compilação.', self.view_config.colors['gold']
        )
        return True

    def reorder_compilation_works(
        self,
        compilation_id: int,
        ordered_resource_ids: list[int],
    ) -> bool:
        try:
            self.compilation_service.reorder_works(
                compilation_id,
                ordered_resource_ids,
            )
        except (ValueError, TypeError) as error:
            self.show_message(str(error), self.view_config.colors['text'])
            return False
        except Exception as error:
            log_exception('Falha ao ordenar obras da compilação', error)
            self.show_message(
                f'Não foi possível ordenar as obras.\n\n{error}',
                self.view_config.colors['text'],
            )
            return False

        return True

    def set_compilation_fragment_membership(
        self,
        compilation_id: int,
        fragment_id: int,
        selected: bool,
    ) -> bool:
        try:
            if selected:
                self.compilation_service.add_fragment(
                    compilation_id,
                    fragment_id,
                )
            else:
                self.compilation_service.remove_fragment(
                    compilation_id,
                    fragment_id,
                )
        except (ValueError, TypeError) as error:
            self.show_message(str(error), self.view_config.colors['text'])
            return False
        except Exception as error:
            log_exception(
                'Falha ao atualizar vínculo de fragmento da compilação',
                error,
            )
            self.show_message(
                f'Não foi possível atualizar o fragmento.\n\n{error}',
                self.view_config.colors['text'],
            )
            return False

        return True

    def update_compilation_fragment_note(
        self,
        compilation_id: int,
        fragment_id: int,
        note: str | None,
    ) -> bool:
        try:
            self.compilation_service.update_fragment_note(
                compilation_id,
                fragment_id,
                note,
            )
        except (ValueError, TypeError) as error:
            self.show_message(str(error), self.view_config.colors['text'])
            return False
        except Exception as error:
            log_exception(
                'Falha ao salvar nota do fragmento no caderno',
                error,
            )
            self.show_message(
                f'Não foi possível salvar a nota.\n\n{error}',
                self.view_config.colors['text'],
            )
            return False
        return True

    def create_compilation_section(
        self,
        compilation_id: int,
        title: str,
        central_idea: str | None,
    ) -> int | None:
        try:
            section_id = self.compilation_service.create_section(
                compilation_id,
                title,
                central_idea,
            )
        except (ValueError, TypeError) as error:
            self.show_message(str(error), self.view_config.colors['text'])
            return None
        except Exception as error:
            log_exception('Falha ao criar seção do caderno', error)
            self.show_message(
                f'Não foi possível criar a seção.\n\n{error}',
                self.view_config.colors['text'],
            )
            return None
        return section_id

    def update_compilation_section(
        self,
        compilation_id: int,
        section_id: int,
        title: str,
        central_idea: str | None,
    ) -> bool:
        try:
            self.compilation_service.update_section(
                compilation_id,
                section_id,
                title,
                central_idea,
            )
        except (ValueError, TypeError) as error:
            self.show_message(str(error), self.view_config.colors['text'])
            return False
        except Exception as error:
            log_exception('Falha ao atualizar seção do caderno', error)
            self.show_message(
                f'Não foi possível atualizar a seção.\n\n{error}',
                self.view_config.colors['text'],
            )
            return False
        return True

    def delete_compilation_section(
        self,
        compilation_id: int,
        section_id: int,
    ) -> bool:
        try:
            self.compilation_service.delete_section(compilation_id, section_id)
        except (ValueError, TypeError) as error:
            self.show_message(str(error), self.view_config.colors['text'])
            return False
        except Exception as error:
            log_exception('Falha ao remover seção do caderno', error)
            self.show_message(
                f'Não foi possível remover a seção.\n\n{error}',
                self.view_config.colors['text'],
            )
            return False
        return True

    def reorder_compilation_sections(
        self,
        compilation_id: int,
        section_ids: list[int],
    ) -> bool:
        try:
            self.compilation_service.reorder_sections(
                compilation_id,
                section_ids,
            )
        except (ValueError, TypeError) as error:
            self.show_message(str(error), self.view_config.colors['text'])
            return False
        except Exception as error:
            log_exception('Falha ao ordenar seções do caderno', error)
            self.show_message(
                f'Não foi possível ordenar as seções.\n\n{error}',
                self.view_config.colors['text'],
            )
            return False
        return True

    def assign_compilation_fragment_to_section(
        self,
        compilation_id: int,
        fragment_id: int,
        section_id: int | None,
    ) -> bool:
        try:
            self.compilation_service.assign_fragment_to_section(
                compilation_id,
                fragment_id,
                section_id,
            )
        except (ValueError, TypeError) as error:
            self.show_message(str(error), self.view_config.colors['text'])
            return False
        except Exception as error:
            log_exception('Falha ao mover fragmento entre seções', error)
            self.show_message(
                f'Não foi possível mover o fragmento.\n\n{error}',
                self.view_config.colors['text'],
            )
            return False
        return True

    def reorder_compilation_section_fragments(
        self,
        compilation_id: int,
        section_id: int,
        fragment_ids: list[int],
    ) -> bool:
        try:
            self.compilation_service.reorder_section_fragments(
                compilation_id,
                section_id,
                fragment_ids,
            )
        except (ValueError, TypeError) as error:
            self.show_message(str(error), self.view_config.colors['text'])
            return False
        except Exception as error:
            log_exception('Falha ao ordenar fragmentos na seção', error)
            self.show_message(
                f'Não foi possível ordenar os fragmentos.\n\n{error}',
                self.view_config.colors['text'],
            )
            return False
        return True

    async def copy_compilation_caderno(self, text: str) -> None:
        try:
            await self.page.clipboard.set(text)
        except Exception as error:
            log_exception('Falha ao copiar caderno de trabalho', error)
            self.show_message(
                f'Não foi possível copiar o caderno.\n\n{error}',
                self.view_config.colors['text'],
            )
            return
        self.show_message('Caderno copiado.', self.view_config.colors['gold'])

    def open_compilation_work_insert(self, compilation_id: int) -> None:
        def add_created_work(resource_id: int, title: str) -> None:
            del title
            self._add_created_compilation_work(compilation_id, resource_id)

        modal = CoreComposer.compose_work_insert_modal(
            page=self.page,
            config=self.view_config,
            on_save=lambda form_data: (
                self.submission_controller.handle_work_submission(
                    form_data,
                    on_created=add_created_work,
                )
            ),
            search_authors=self.search_authors,
            search_works=self.search_works,
            on_create_parent_work=self.open_parent_work,
        )
        self.page.show_dialog(modal)

    def _add_created_compilation_work(
        self,
        compilation_id: int,
        resource_id: int,
    ) -> None:
        if self.add_work_to_compilation(compilation_id, resource_id):
            self.refresh_compilation_hub(compilation_id)

    def open_compilation_work_edit(
        self,
        compilation_id: int,
        resource_id: int,
    ) -> None:
        resource = next(
            (
                work
                for work in self.service.list_works()
                if work.id == resource_id
            ),
            None,
        )
        if resource is None:
            self.show_message(
                'A obra da compilação não está mais disponível.',
                self.view_config.colors['text'],
            )
            return
        self.open_work_edit(resource, compilation_id=compilation_id)

    def _compilation_work_options(
        self,
        compilation_id: int,
    ) -> list[tuple[int, str]]:
        compilation = next(
            (
                record
                for record in self.compilation_service.list_compilations()
                if record['id'] == compilation_id
            ),
            None,
        )
        if compilation is None:
            raise ValueError('A compilação não está mais disponível.')
        return [
            (work['id'], work['title'])
            for work in compilation['works']
        ]

    def _open_compilation_fragment_composer(
        self,
        compilation_id: int,
    ):
        work_options = self._compilation_work_options(compilation_id)
        allowed_work_ids = {resource_id for resource_id, _ in work_options}

        def search_allowed_works(query: str) -> list[tuple[int, str]]:
            return [
                match
                for match in self.search_fragment_works(query)
                if match[0] in allowed_work_ids
            ]

        composer = FragmentsComposer(
            page=self.page,
            config=self.view_config,
            fragments=[],
            search_works=search_allowed_works,
            on_save=lambda fragment_id, data: (
                self.save_compilation_fragment(
                    compilation_id,
                    fragment_id,
                    data,
                )
            ),
            on_delete=self.delete_fragment,
            on_copy_reference=self.copy_reference,
            allowed_work_ids=allowed_work_ids,
        )
        self.compilation_fragment_composer = composer
        return composer, work_options

    def open_compilation_fragment_create(
        self,
        compilation_id: int,
        resource_id: int,
    ) -> None:
        composer, work_options = self._open_compilation_fragment_composer(
            compilation_id
        )
        title = next(
            (
                title
                for option_id, title in work_options
                if option_id == resource_id
            ),
            None,
        )
        if title is None:
            self.show_message(
                'Inclua a obra na compilação antes de criar um fragmento.',
                self.view_config.colors['text'],
            )
            return
        composer.open_create_for_work(resource_id, title)

    def open_compilation_fragment_edit(
        self,
        compilation_id: int,
        fragment: FragmentRecord,
    ) -> None:
        composer = self._open_compilation_fragment_composer(
            compilation_id
        )[0]
        composer.open_edit_fragment(fragment)

    def refresh_compilation_hub(self, compilation_id: int) -> None:
        application = getattr(self, 'application', None)
        if application is not None:
            application.refresh_compilation_hub(compilation_id)

    def close_dialog(self, modal: ft.AlertDialog) -> None:
        modal.open = False
        self.page.update()
