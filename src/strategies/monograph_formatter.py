from src.utils import ABNTUtils as Utils
from typing import List, TYPE_CHECKING
from src.domains import (
    EditorialMonograph,
    AcademicMonograph,
    CorrespondenceMonograph
)
from src.utils import (
    ViewReference,
    TextStyle,
    ReferencePart,
)
from src.configs.settings import PHYSICAL_ATTRIBUTES

if TYPE_CHECKING:
    from src.domains import BibliographicResource


class MonographFormatter:

    @staticmethod
    def formatter(
        bibliographic_resource: BibliographicResource
    ) -> ViewReference:
        '''
        Método principal que orquestra a montagem da referência.
        Funciona como um 'sumário' do que está acontecendo.
        '''
        parts = []
        # 1. Trata recursos parciais e obtém a obra principal se necessário
        bibliographic_resource, partial_bibliographic_resource = (
            MonographFormatter._handle_partial_resource(
                bibliographic_resource, parts
            )
        )
        # 2. Valida se existe uma obra específica
        MonographFormatter._validate_specific_work(bibliographic_resource)
        # 3. Adiciona autores e título
        MonographFormatter._append_authors_and_title(
            bibliographic_resource, parts
        )
        # 4. Adiciona detalhes específicos por tipo de monografia
        MonographFormatter._append_specific_details(
            bibliographic_resource, parts
        )
        # 5. Adiciona dados de parte (se aplicável), notas e URL
        MonographFormatter._append_suffix_details(
            bibliographic_resource, partial_bibliographic_resource, parts
        )
        return ViewReference(parts=parts)

    @staticmethod
    def _handle_partial_resource(bibliographic_resource, parts):
        partial_bibliographic_resource = None
        work = bibliographic_resource.specific_work
        if work is not None and work.is_partial is True:
            partial_bibliographic_resource = bibliographic_resource
            bibliographic_resource = (
                partial_bibliographic_resource
                .specific_work.parent_bibliographic_resource
            )

            for content, style in Utils.format_part_header(
                partial_bibliographic_resource
            ):
                parts.append(ReferencePart(content=content, style=style))
            parts.append(ReferencePart(
                content='. In: ', style=TextStyle.ITALIC
            ))

        return bibliographic_resource, partial_bibliographic_resource

    @staticmethod
    def _validate_specific_work(bibliographic_resource):
        if not bibliographic_resource.specific_work:
            raise ValueError(
                f'O recurso bibliográfico ID {bibliographic_resource.id} '
                'não possui nenhuma obra específica associada.'
            )

    @staticmethod
    def _append_authors_and_title(bibliographic_resource, parts):
        parts.append(
            ReferencePart(
                content=Utils.fmt_authors(bibliographic_resource.authors)
            )
        )
        for content, style in Utils.format_title_and_subtitle(
            title=bibliographic_resource.specific_work.title,
            subtitle=bibliographic_resource.specific_work.subtitle
            if bibliographic_resource.specific_work.subtitle else None,
            title_style=TextStyle.BOLD
        ):
            parts.append(ReferencePart(content=content, style=style))

    @staticmethod
    def _append_specific_details(bibliographic_resource, parts):
        match bibliographic_resource.specific_work:
            case EditorialMonograph():
                parts.extend(
                    MonographFormatter._format_editorial_details(
                        bibliographic_resource.specific_work
                    )
                )
            case AcademicMonograph():
                parts.append(
                    MonographFormatter._format_academic_details(
                        bibliographic_resource.specific_work
                    )
                )
            case CorrespondenceMonograph():
                parts.append(
                    MonographFormatter._format_correspondence_details(
                        bibliographic_resource.specific_work
                    )
                )

    @staticmethod
    def _append_suffix_details(
        bibliographic_resource, partial_bibliographic_resource, parts
    ):
        if partial_bibliographic_resource:
            partial_work = partial_bibliographic_resource.specific_work
            parts.extend(
                MonographFormatter._format_part_details(partial_work)
            )

        work = bibliographic_resource.specific_work
        if work.additional_notes:
            parts.append(
                ReferencePart(content=f' {work.additional_notes}.')
            )

        if work.url:
            parts.append(
                ReferencePart(
                    content=(
                        ' Disponível em:'
                        f' {work.url}.'
                        ' Acesso em:'
                        f' {Utils.format_abbrev_date(work.viewed_at)}.'
                    )
                )
            )

    # ==========================================
    #           MÉTODOS AUXILIARES
    # ==========================================

    @staticmethod
    def _format_editorial_details(
        monograph: EditorialMonograph
    ) -> List[ReferencePart]:
        '''Trata todas as particularidades de
        publicação de uma Monografia Editorial.
        '''
        parts = []

        if monograph.responsibilities:
            parts.extend(
                ReferencePart(content=f' {k}: {v}.')
                for k, v in monograph.responsibilities.items()
            )

        if monograph.edition:
            parts.append(ReferencePart(content=f' {monograph.edition}ª ed.'))

        parts.append(
            ReferencePart(
                content=(
                    f' {monograph.publication_place}:'
                    f' {monograph.publisher},'
                    f' {monograph.display_year}.'
                )
            )
        )

        # Descrição física
        physical_description = []
        for attr, suffix in PHYSICAL_ATTRIBUTES.items():
            value = getattr(monograph, attr, None)
            if value:
                if isinstance(value, bool):
                    physical_description.append(suffix.strip())
                else:
                    physical_description.append(f'{value}{suffix}')

        if physical_description:
            phys_str = ', '.join(physical_description)
            parts.append(ReferencePart(content=f' {phys_str}'))
            if parts and not parts[-1].content.endswith('.'):
                parts.append(ReferencePart(content='.'))

        # Coleção
        if monograph.collection_name:
            parts.append(
                ReferencePart(content=f' ({monograph.collection_name}')
            )
            if monograph.collection_number:
                parts.append(ReferencePart(
                    content=f', {monograph.collection_number}')
                )
            parts.append(ReferencePart(content=').'))

        # Notas e ISBN
        if monograph.translation_notes:
            parts.append(
                ReferencePart(content=f' {monograph.translation_notes}.')
            )

        if monograph.original_full_title:
            parts.append(
                ReferencePart(
                    content=(
                        ' Tradução do original: '
                        f'{monograph.original_full_title}.'
                    )
                )
            )

        if monograph.isbn:
            parts.append(ReferencePart(content=f' ISBN: {monograph.isbn}.'))

        return parts

    @staticmethod
    def _format_academic_details(
        monograph: AcademicMonograph
    ) -> ReferencePart:
        return ReferencePart(
            content=(
                f' {monograph.display_year}. {monograph.page_quantity} f.'
                f' {monograph.thesis_type} ({monograph.education_level} em'
                f' {monograph.course}) — {monograph.faculty},'
                f' {monograph.publication_place}, {monograph.defense_year}'
            )
        )

    @staticmethod
    def _format_correspondence_details(
        monograph: CorrespondenceMonograph
    ) -> ReferencePart:
        correspondence_str_list = []
        if monograph.recipient:
            correspondence_str_list.append(f' {monograph.recipient}')
        correspondence_str_list.append(
            f' {monograph.publication_place},'
            f' {Utils.format_abbrev_date(monograph.date_anchor)}'
            f' {monograph.correspondence_type}.'
        )

        return (ReferencePart(
            content='. '.join(correspondence_str_list)
        ))

    @staticmethod
    def _format_part_details(p_bs) -> List[ReferencePart]:
        '''Adiciona as páginas, capítulos e
        volumes lidos no final da referência.
        '''
        parts = []
        has_prev = False

        if p_bs.part_volume:
            parts.append(ReferencePart(content=f' v. {p_bs.part_volume}'))
            has_prev = True

        if p_bs.part_chapter:
            prefix = ', cap.' if has_prev else ' Cap.'
            parts.append(
                ReferencePart(content=f'{prefix} {p_bs.part_chapter}')
            )
            has_prev = True

        if p_bs.part_start_page and p_bs.part_end_page:
            if p_bs.part_start_page != p_bs.part_end_page:
                page_range = f'{p_bs.part_start_page}–{p_bs.part_end_page}'
            else:
                page_range = f'{p_bs.part_start_page}'

            prefix = ', p.' if has_prev else ' P.'
            parts.append(ReferencePart(content=f'{prefix} {page_range}'))
        else:
            if has_prev:
                parts.append(ReferencePart(content=', não paginado'))
            else:
                parts.append(ReferencePart(content=' Não paginado'))

        if parts and not parts[-1].content.endswith('.'):
            parts.append(ReferencePart(content='.'))
        return parts
