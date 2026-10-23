from src.domains import (
    AudioDocument,
    AudiovisualDocument,
    BibliographicResource,
    CartographicDocument,
    MusicalScore,
    ThreeDimensionalDocument,
    VisualDocument,
)
from src.utils import ReferencePart, TextStyle, ViewReference
from src.utils import ABNTUtils as Utils


class AudiovisualFormatter:

    @staticmethod
    def formatter(work: AudiovisualDocument) -> ViewReference:
        parts = [
            ReferencePart(
                content=AudiovisualFormatter._format_title(
                    work.title,
                    preserve_title_spelling=work.preserve_title_spelling,
                ),
            )
        ]
        if work.subtitle:
            parts.append(ReferencePart(f': {work.subtitle}'))
        parts.append(ReferencePart('.'))

        parts.extend(
            ReferencePart(f' {role}: {names}.')
            for role, names in work.responsibilities.items()
        )
        parts.append(
            ReferencePart(
                f' {work.publication_place}: {work.publisher},'
                f' {work.display_year}.'
            )
        )
        parts.extend(AudiovisualFormatter._format_physical_description(work))

        if work.additional_notes:
            parts.append(ReferencePart(f' {work.additional_notes}.'))
        if work.url:
            if work.viewed_at is None:
                raise ValueError(
                    'Informe a data de acesso para documentos '
                    'audiovisuais on-line.'
                )
            parts.append(
                ReferencePart(
                    content=(
                        f' Disponível em: {work.url}.'
                        f' Acesso em: '
                        f'{Utils.format_abbrev_date(work.viewed_at)}.'
                    )
                )
            )

        return ViewReference(parts)

    @staticmethod
    def _format_title(
        title: str,
        preserve_title_spelling: bool = False,
    ) -> str:
        return Utils.format_title_without_author(
            title,
            preserve_title_spelling=preserve_title_spelling,
        )

    @staticmethod
    def _format_duration(seconds: int) -> str:
        minutes, remaining_seconds = divmod(seconds, 60)

        if minutes:
            duration = f'{minutes} min'
            if remaining_seconds:
                duration += f' {remaining_seconds} s'
        else:
            duration = f'{remaining_seconds} s'

        return duration

    @staticmethod
    def _format_physical_description(
        work: AudiovisualDocument,
    ) -> list[ReferencePart]:
        details = [
            f'1 {work.carrier_type} '
            f'({AudiovisualFormatter._format_duration(work.seconds)})'
        ]
        if work.sound:
            details.append('son.')
        details.append('color.' if work.colorized else 'p&b.')

        return [ReferencePart(f' {", ".join(details)}')]


class AudioFormatter:

    @staticmethod
    def formatter(work: AudioDocument) -> ViewReference:
        if work.is_partial:
            return ViewReference(AudioFormatter._format_part(work))
        return ViewReference(AudioFormatter._format_document(work))

    @staticmethod
    def _format_document(work: AudioDocument) -> list[ReferencePart]:
        parts = AudioFormatter._format_title_and_responsibilities(work)
        parts.extend(AudioFormatter._format_physical_description(work))
        parts.extend(AudioFormatter._format_publication(work))
        parts.extend(AudioFormatter._format_online_access(work))
        if work.additional_notes:
            parts.append(ReferencePart(f' {work.additional_notes}.'))
        return parts

    @staticmethod
    def _format_part(work: AudioDocument) -> list[ReferencePart]:
        parent_resource = work.parent_bibliographic_resource
        if parent_resource is None:
            raise ValueError(
                'A parte do documento sonoro precisa de uma obra-pai.'
            )
        parent = parent_resource.specific_work
        if not isinstance(parent, AudioDocument):
            raise ValueError(
                'A obra-pai de uma parte sonora deve ser um documento sonoro.'
            )
        if not work.part_identifier:
            raise ValueError(
                'A parte do documento sonoro precisa de um identificador.'
            )

        parts = AudioFormatter._format_title_and_responsibilities(
            work,
            work.part_responsibilities,
        )
        parts.append(ReferencePart(' In: ', style=TextStyle.ITALIC))
        parts.extend(AudioFormatter._format_title_and_responsibilities(parent))
        parts.extend(
            AudioFormatter._format_physical_description(
                parent,
                part_identifier=work.part_identifier,
                duration_seconds=work.seconds,
                physical_details=work.physical_details,
                allow_empty=bool(work.url or parent.url),
            )
        )
        parts.extend(AudioFormatter._format_publication(parent))
        parts.extend(AudioFormatter._format_online_access(work, parent))
        if work.additional_notes:
            parts.append(ReferencePart(f' {work.additional_notes}.'))
        return parts

    @staticmethod
    def _format_title_and_responsibilities(
        work: AudioDocument,
        responsibilities: dict[str, str] | None = None,
    ) -> list[ReferencePart]:
        author_text = Utils.fmt_authors(work.authors)
        if work.preserve_title_spelling:
            title = work.title.strip()
        elif not author_text:
            title = Utils.format_title_without_author(work.title)
        else:
            title = AudioFormatter._format_title(work.title)
        parts = []
        if 'audiolivro' in work.carrier_type.casefold():
            if author_text:
                parts.append(ReferencePart(f'{author_text} '))
        parts.append(ReferencePart(title))
        if work.subtitle:
            parts.append(ReferencePart(f': {work.subtitle}.'))
        elif not title.endswith(('.', '!', '?')):
            parts.append(ReferencePart('.'))

        assigned_responsibilities = (
            responsibilities
            if responsibilities is not None
            else work.responsibilities
        )
        parts.extend(
            ReferencePart(f' {role}: {names}.')
            for role, names in assigned_responsibilities.items()
        )
        return parts

    @staticmethod
    def _format_title(title: str) -> str:
        words = title.strip().split(maxsplit=1)
        if not words:
            return ''
        if len(words) == 1:
            return words[0].upper()
        return f'{words[0].upper()} {words[1]}'

    @staticmethod
    def _format_publication(work: AudioDocument) -> list[ReferencePart]:
        return [
            ReferencePart(
                f' {work.publication_place}: {work.publisher},'
                f' {work.display_year}.'
            )
        ]

    @staticmethod
    def _format_duration(seconds: int) -> str:
        hours, remainder = divmod(seconds, 3600)
        minutes, remaining_seconds = divmod(remainder, 60)
        duration = []
        if hours:
            duration.append(f'{hours} h')
        if minutes:
            duration.append(f'{minutes} min')
        if remaining_seconds or not duration:
            duration.append(f'{remaining_seconds} s')
        return ' '.join(duration)

    @staticmethod
    def _format_physical_description(
        work: AudioDocument,
        part_identifier: str | None = None,
        duration_seconds: int | None = None,
        physical_details: str | None = None,
        allow_empty: bool = False,
    ) -> list[ReferencePart]:
        if not work.carrier_type.strip():
            if allow_empty or work.url:
                return []
            raise ValueError(
                'O tipo de suporte do documento sonoro é obrigatório.'
            )
        carrier = work.carrier_type.strip()
        details = [
            'Podcast'
            if carrier.casefold() == 'podcast'
            else f'1 {carrier}'
        ]
        if part_identifier:
            details.append(part_identifier)
        duration = (
            duration_seconds
            if duration_seconds is not None
            else work.seconds
        )
        description = ', '.join(details)
        if duration is not None:
            description += f' ({AudioFormatter._format_duration(duration)})'

        extra_details = list(dict.fromkeys(
            detail.strip()
            for detail in (work.physical_details, physical_details)
            if detail and detail.strip()
        ))
        if extra_details:
            description += f', {", ".join(extra_details)}'
        return [ReferencePart(f' {description}.')]

    @staticmethod
    def _format_online_access(
        work: AudioDocument,
        parent: AudioDocument | None = None,
    ) -> list[ReferencePart]:
        source = (
            work
            if work.url
            else parent if parent is not None and parent.url else None
        )
        online_carrier = any(
            marker in document.carrier_type.casefold()
            for document in (work, parent)
            if document is not None
            for marker in ('podcast', 'online', 'on-line', 'streaming')
        )
        if source is None:
            if online_carrier:
                raise ValueError(
                    'Informe a URL para documentos sonoros on-line.'
                )
            return []
        if source.viewed_at is None:
            raise ValueError(
                'Informe a data de acesso para documentos sonoros on-line.'
            )
        return [
            ReferencePart(
                f' Disponível em: {source.url}.'
                f' Acesso em: {Utils.format_abbrev_date(source.viewed_at)}.'
            )
        ]


class MusicalScoreFormatter:

    @staticmethod
    def formatter(resource: BibliographicResource) -> ViewReference:
        work = resource.specific_work
        if not isinstance(work, MusicalScore):
            raise ValueError(
                'O recurso bibliográfico precisa conter uma partitura.'
            )
        if work.is_partial:
            return ViewReference(
                MusicalScoreFormatter._format_part(resource, work)
            )
        return ViewReference(
            MusicalScoreFormatter._format_document(resource, work)
        )

    @staticmethod
    def _format_document(
        resource: BibliographicResource,
        work: MusicalScore,
    ) -> list[ReferencePart]:
        parts = MusicalScoreFormatter._format_title_and_authors(
            resource, work
        )
        if work.instrumentation.strip():
            parts.append(ReferencePart(f' {work.instrumentation.strip()}.'))
        parts.extend(MusicalScoreFormatter._format_publication(work))
        if work.physical_description:
            parts.append(
                ReferencePart(f' {work.physical_description.strip()}.')
            )
        if work.additional_notes:
            parts.append(ReferencePart(f' {work.additional_notes}.'))
        parts.extend(MusicalScoreFormatter._format_online_access(work))
        return parts

    @staticmethod
    def _format_part(
        resource: BibliographicResource,
        work: MusicalScore,
    ) -> list[ReferencePart]:
        parent_resource = work.parent_bibliographic_resource
        if parent_resource is None:
            raise ValueError(
                'A parte da partitura precisa de uma obra-pai.'
            )
        parent = parent_resource.specific_work
        if not isinstance(parent, MusicalScore) or parent.is_partial:
            raise ValueError(
                'A obra-pai de uma parte deve ser uma partitura completa.'
            )

        parts = MusicalScoreFormatter._format_title_and_authors(
            resource, work
        )
        parts.append(ReferencePart(' In: ', style=TextStyle.ITALIC))
        parts.extend(
            MusicalScoreFormatter._format_title_and_authors(
                parent_resource, parent
            )
        )
        if parent.instrumentation.strip():
            parts.append(
                ReferencePart(f' {parent.instrumentation.strip()}.')
            )
        parts.extend(MusicalScoreFormatter._format_publication(parent))

        location = MusicalScoreFormatter._format_part_location(work)
        if location:
            parts.append(ReferencePart(f' {location}.'))
        if work.physical_description:
            parts.append(
                ReferencePart(f' {work.physical_description.strip()}.')
            )
        if work.additional_notes:
            parts.append(ReferencePart(f' {work.additional_notes}.'))
        parts.extend(MusicalScoreFormatter._format_online_access(work))
        return parts

    @staticmethod
    def _format_title_and_authors(
        resource: BibliographicResource,
        work: MusicalScore,
    ) -> list[ReferencePart]:
        parts = []
        authors = Utils.fmt_authors(resource.authors)
        if authors:
            if work.author_role:
                authors += f' ({work.author_role.strip()})'
            punctuation = '' if authors.endswith('.') else '.'
            parts.append(ReferencePart(f'{authors}{punctuation} '))

        title = work.title.strip()
        if not authors:
            title = Utils.format_title_without_author(
                title,
                preserve_title_spelling=work.preserve_title_spelling,
            )
        if work.subtitle:
            title += f': {work.subtitle.strip()}'
        parts.append(ReferencePart(f'{title}.'))
        return parts

    @staticmethod
    def _format_publication(work: MusicalScore) -> list[ReferencePart]:
        return [
            ReferencePart(
                f' {work.publication_place}: {work.publisher},'
                f' {work.display_year}.'
            )
        ]

    @staticmethod
    def _format_part_location(work: MusicalScore) -> str:
        location = []
        if work.part_volume:
            location.append(f'v. {work.part_volume}')
        if work.part_start_page:
            pages = work.part_start_page
            if work.part_end_page:
                pages += f'-{work.part_end_page}'
            location.append(f'p. {pages}')
        elif work.part_end_page:
            location.append(f'p. {work.part_end_page}')
        return ', '.join(location)

    @staticmethod
    def _format_online_access(work: MusicalScore) -> list[ReferencePart]:
        if not work.url:
            return []
        if work.viewed_at is None:
            raise ValueError(
                'Informe a data de acesso para partituras on-line.'
            )
        return [
            ReferencePart(
                f' Disponível em: {work.url}.'
                f' Acesso em: {Utils.format_abbrev_date(work.viewed_at)}.'
            )
        ]


class VisualFormatter:

    @staticmethod
    def formatter(work: VisualDocument) -> ViewReference:
        parts = []
        author_text = Utils.fmt_authors(work.authors)
        if author_text:
            punctuation = '' if author_text.endswith('.') else '.'
            parts.append(
                ReferencePart(f'{author_text}{punctuation} ')
            )

        title = work.title.strip() or '[Sem título]'
        if not author_text and title != '[Sem título]':
            title = Utils.format_title_without_author(
                title,
                preserve_title_spelling=work.preserve_title_spelling,
            )
        if work.subtitle:
            title += f': {work.subtitle.strip()}'
        parts.append(ReferencePart(f'{title}. {work.display_year}.'))

        physical_description = (
            work.physical_description.strip()
            if work.physical_description
            else ''
        )
        if physical_description:
            parts.append(
                ReferencePart(
                    f' {physical_description.rstrip(".")}.'
                )
            )
        if work.additional_notes:
            parts.append(
                ReferencePart(f' {work.additional_notes.strip().rstrip(".")}.')
            )
        if work.url:
            if work.viewed_at is None:
                raise ValueError(
                    'Informe a data de acesso para documentos visuais '
                    'on-line.'
                )
            parts.append(
                ReferencePart(
                    f' Disponível em: {work.url}.'
                    f' Acesso em: '
                    f'{Utils.format_abbrev_date(work.viewed_at)}.'
                )
            )
        return ViewReference(parts)


class CartographicFormatter:

    @staticmethod
    def formatter(work: CartographicDocument) -> ViewReference:
        parts = []
        author_text = Utils.fmt_authors(work.authors)
        if author_text:
            punctuation = '' if author_text.endswith('.') else '.'
            parts.append(ReferencePart(f'{author_text}{punctuation} '))

        title = work.title.strip()
        if not author_text:
            title = Utils.format_title_without_author(
                title,
                preserve_title_spelling=work.preserve_title_spelling,
            )
        if work.subtitle:
            title += f': {work.subtitle.strip()}'
        parts.append(ReferencePart(f'{title}.'))

        if work.edition is not None:
            parts.append(ReferencePart(f' {work.edition}. ed.'))

        parts.append(
            ReferencePart(
                f' {work.publication_place}: {work.publisher},'
                f' {work.display_year}.'
            )
        )
        if work.physical_description:
            parts.append(
                ReferencePart(
                    f' {work.physical_description.strip().rstrip(".")}.'
                )
            )
        if work.additional_notes:
            parts.append(
                ReferencePart(
                    f' {work.additional_notes.strip().rstrip(".")}.'
                )
            )
        if work.url:
            if work.viewed_at is None:
                raise ValueError(
                    'Informe a data de acesso para documentos '
                    'cartográficos on-line.'
                )
            parts.append(
                ReferencePart(
                    f' Disponível em: {work.url}.'
                    f' Acesso em: '
                    f'{Utils.format_abbrev_date(work.viewed_at)}.'
                )
            )
        return ViewReference(parts)


class ThreeDimensionalFormatter:

    @staticmethod
    def formatter(work: ThreeDimensionalDocument) -> ViewReference:
        parts = []
        author_text = Utils.fmt_authors(work.authors)
        if author_text:
            punctuation = '' if author_text.endswith('.') else '.'
            parts.append(ReferencePart(f'{author_text}{punctuation} '))

        title = work.title.strip()
        if not title:
            title = '[Objeto sem título]'
        elif not author_text:
            title = Utils.format_title_without_author(
                title,
                preserve_title_spelling=work.preserve_title_spelling,
            )
        if work.subtitle:
            title += f': {work.subtitle.strip()}'
        parts.append(ReferencePart(f'{title}.'))

        place = (work.manufacturing_place or '').strip()
        manufacturer = (work.manufacturer or '').strip()
        if place.casefold() == '[s.l.]':
            place = ''
        if manufacturer.casefold() == '[s.n.]':
            manufacturer = ''

        if place and manufacturer:
            publication = f'{place}: {manufacturer}, {work.display_year}.'
        elif place:
            publication = f'{place}, {work.display_year}.'
        elif manufacturer:
            publication = f'{manufacturer}, {work.display_year}.'
        else:
            publication = f'{work.display_year}.'
        parts.append(ReferencePart(f' {publication}'))

        if work.physical_description.strip():
            parts.append(
                ReferencePart(
                    f' {work.physical_description.strip().rstrip(".")}.'
                )
            )
        if work.additional_notes:
            parts.append(
                ReferencePart(f' {work.additional_notes.strip().rstrip(".")}.')
            )
        if work.url:
            if work.viewed_at is None:
                raise ValueError(
                    'Informe a data de acesso para documentos '
                    'tridimensionais on-line.'
                )
            parts.append(
                ReferencePart(
                    f' Disponível em: {work.url}.'
                    f' Acesso em: '
                    f'{Utils.format_abbrev_date(work.viewed_at)}.'
                )
            )
        return ViewReference(parts)
