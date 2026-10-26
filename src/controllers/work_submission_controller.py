from collections.abc import Callable

import flet as ft

from src.contracts import WorkCreationPayload
from src.domains import Author
from src.services.work_service import WorkService
from src.services.work_form_service import WorkFormService
from src.utils.error_log import log_exception
from src.utils.types import ViewConfig
from src.views.core_composer import CoreComposer
from src.views.work_insert_specs import (
    ALWAYS_PARTIAL_TYPES,
    DEFAULTED_FIELDS,
    PARTIAL_FORM_FIELDS,
    WORK_TYPES,
)


class WorkSubmissionController:
    """Coordinates form submission and duplicate-author resolution."""

    def __init__(
        self,
        page: ft.Page,
        config: ViewConfig,
        service: WorkService,
        form_service: WorkFormService,
        show_message: Callable[[str, str], None],
        close_insert_work: Callable[[], None],
    ) -> None:
        self.page = page
        self.config = config
        self.service = service
        self.form_service = form_service
        self.show_message = show_message
        self.close_insert_work = close_insert_work
        self._pending_payload: WorkCreationPayload | None = None
        self._pending_author_ids: dict[int, int] = {}
        self._new_author_indexes: set[int] = set()
        self._pending_on_created: Callable[[int, str], None] | None = None
        self._pending_on_deferred_close: Callable[[], None] | None = None
        self.multiple_authors_modal: ft.AlertDialog | None = None

    def handle_work_submission(
        self,
        form_data: dict[str, object],
        on_created: Callable[[int, str], None] | None = None,
        on_deferred_close: Callable[[], None] | None = None,
    ) -> bool:
        missing_fields = self._missing_required_fields(form_data)
        if missing_fields:
            self.show_message(
                'Preencha os campos obrigatórios: '
                + ', '.join(missing_fields)
                + '.',
                self.config.colors['text'],
            )
            return False

        try:
            self._pending_payload = self.form_service.prepare_payload(
                form_data
            )
            self._pending_author_ids.clear()
            self._new_author_indexes.clear()
            self._pending_on_created = on_created
            self._pending_on_deferred_close = on_deferred_close
            return self._continue_pending_submission(close_form=False)
        except (ValueError, TypeError) as error:
            log_exception('Dados inválidos no cadastro de obra', error)
            self.show_message(str(error), self.config.colors['text'])
            return False
        except Exception as error:
            log_exception('Falha ao preparar o cadastro de obra', error)
            self.show_message(
                f'Não foi possível salvar a obra.\n\n{error} ',
                self.config.colors['text'],
            )
            return False

    @staticmethod
    def _missing_required_fields(
        form_data: dict[str, object],
    ) -> list[str]:
        work_type = str(form_data.get('work_type', ''))
        spec = next(
            (item for item in WORK_TYPES if item.key == work_type),
            None,
        )
        if spec is None:
            return ['tipo de obra']

        missing = []
        is_partial = (
            bool(form_data.get('is_partial'))
            or work_type in ALWAYS_PARTIAL_TYPES
        )
        partial_form_fields = PARTIAL_FORM_FIELDS.get(work_type)
        for field in spec.fields:
            if (
                is_partial
                and partial_form_fields is not None
                and field.key not in partial_form_fields
            ):
                continue
            if (
                work_type == 'musical_score'
                and is_partial
                and field.key == 'physical_description'
            ):
                continue
            if not field.required:
                continue
            if (
                (
                    work_type == 'audio_document'
                    and form_data.get('is_partial')
                    and field.key in {
                        'authors',
                        'carrier_type',
                        'date_anchor',
                        'publication_place',
                        'publisher',
                    }
                )
                or (
                    work_type == 'musical_score'
                    and form_data.get('is_partial')
                    and field.key == 'date_anchor'
                )
            ):
                continue
            if field.key in DEFAULTED_FIELDS.get(work_type, set()):
                continue
            value = form_data.get(field.key)
            if field.key == 'date_anchor' and (
                form_data.get('date_precision') == 'Data desconhecida'
            ):
                continue
            if value is None or (
                isinstance(value, str) and not value.strip()
            ):
                missing.append(field.label.rstrip(' *'))

        if (
            is_partial
        ) and not form_data.get('parent_bibliographic_resource_id'):
            missing.append('Obra-pai')
        if (
            work_type == 'audio_document'
            and form_data.get('is_partial')
            and not str(form_data.get('part_identifier', '')).strip()
        ):
            missing.append('Identificador da parte')
        multimedia_types = {
            'audiovisual_document',
            'audio_document',
            'musical_score',
            'visual_document',
            'cartographic_document',
            'three_dimensional_document',
        }
        if (
            work_type in multimedia_types
            and form_data.get('url')
            and not form_data.get('viewed_at')
        ):
            missing.append('Data de acesso')
        if (
            work_type in {'monographic_proceedings', 'periodical_proceedings'}
            and form_data.get('url')
            and not form_data.get('viewed_at')
        ):
            missing.append('Data de acesso')
        if (
            work_type == 'audio_document'
            and not form_data.get('is_partial')
            and not form_data.get('url')
            and not str(form_data.get('carrier_type', '')).strip()
        ):
            missing.append('Tipo de suporte')
        if (
            work_type == 'audio_document'
            and not form_data.get('is_partial')
            and any(
                marker in str(form_data.get('carrier_type', '')).casefold()
                for marker in ('podcast', 'online', 'on-line', 'streaming')
            )
            and not form_data.get('url')
        ):
            missing.append('URL')
        if (
            work_type in {'monographic_proceedings', 'periodical_proceedings'}
            and is_partial
        ):
            if not str(form_data.get('part_start_page', '')).strip():
                missing.append('Página inicial da parte')
            if not str(form_data.get('part_end_page', '')).strip():
                missing.append('Página final da parte')
        return missing

    def _continue_pending_submission(self, close_form: bool) -> bool:
        if self._pending_payload is None:
            return False

        try:
            result = self.service.resolve_and_create(
                self._pending_payload,
                author_ids=self._pending_author_ids,
                new_author_indexes=self._new_author_indexes,
            )
            if result['requires_choice'] is True:
                self._show_multiple_authors_modal(
                    result['index'],
                    result['candidates'],
                )
                return False
            created_work = (result['resource_id'], result['work_title'])
        except (ValueError, TypeError) as error:
            log_exception('Dados inválidos ao persistir uma obra', error)
            self._clear_pending_submission()
            self.show_message(str(error), self.config.colors['text'])
            return False
        except Exception as error:
            log_exception('Falha ao persistir uma obra', error)
            self._clear_pending_submission()
            self.show_message(
                f'Não foi possível salvar a obra.\n\n{error}',
                self.config.colors['text'],
            )
            return False

        on_created = self._pending_on_created
        on_deferred_close = self._pending_on_deferred_close
        self._clear_pending_submission()
        if close_form:
            if on_deferred_close is not None:
                on_deferred_close()
            else:
                self.close_insert_work()
        if on_created is not None:
            on_created(*created_work)
        self.show_message(
            'Obra adicionada ao acervo.', self.config.colors['gold']
        )
        return True

    def _show_multiple_authors_modal(
        self, index: int, candidates: list[Author]
    ) -> None:
        self.multiple_authors_modal = (
            CoreComposer.compose_multiple_authors_modal(
                authors=candidates,
                on_select=lambda author_id: self._select_existing_author(
                    index, author_id
                ),
                on_create_new=lambda: self._create_new_author(index),
                on_cancel=self._clear_pending_submission,
                config=self.config,
            )
        )
        self.page.show_dialog(self.multiple_authors_modal)

    def _select_existing_author(self, index: int, author_id: int) -> None:
        self._pending_author_ids[index] = author_id
        self._continue_pending_submission(close_form=True)

    def _create_new_author(self, index: int) -> None:
        self._new_author_indexes.add(index)
        self._continue_pending_submission(close_form=True)

    def _clear_pending_submission(self) -> None:
        self._pending_payload = None
        self._pending_author_ids.clear()
        self._new_author_indexes.clear()
        self._pending_on_created = None
        self._pending_on_deferred_close = None
