from collections.abc import Iterable

from sqlalchemy import or_, select, delete
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.sql.schema import ScalarElementColumnDefault

from src.contracts import (
    AuthorReference,
    AuthorSearchResult,
    WorkCreationPayload,
)
from src.domains import (
    AcademicMonograph,
    Author,
    Authorship,
    AudioDocument,
    BibliographicResource,
    CorrespondenceMonograph,
    EditorialMonograph,
    JournalArticle,
    Magazine,
    MonographicProceedings,
    PeriodicalCollection,
    PeriodicalProceedings,
    MusicalScore,
    WorkMixin,
)
from src.utils.error_log import log_exception
from src.utils.normalizers import CoreNormalizer


class WorkRepository:
    """Persiste um recurso bibliografico e sua obra especifica."""

    def __init__(
        self,
        session: Session,
        normalizer: CoreNormalizer | None = None,
    ):
        self.session = session
        self.normalizer = normalizer or CoreNormalizer()

    @staticmethod
    def _parse_parent_resource_id(value: object) -> int:
        if isinstance(value, bool):
            raise ValueError('O identificador da obra-pai é inválido.')
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError as error:
                raise ValueError(
                    'O identificador da obra-pai é inválido.'
                ) from error
        raise ValueError('O identificador da obra-pai é inválido.')

    def _resolve_parent_resource(
        self,
        work_model: type[WorkMixin],
        work_data: dict[str, object],
        resource_id: int | None = None,
    ) -> BibliographicResource | None:
        magazine_child = work_model in {
            JournalArticle,
            PeriodicalCollection,
        }
        if magazine_child:
            work_data['is_partial'] = True
        if not work_data.get('is_partial'):
            return None

        parent_id = work_data.get('parent_bibliographic_resource_id')
        if parent_id is None:
            raise ValueError(
                'Selecione uma obra-pai para cadastrar uma parte.'
            )
        parent_resource = self.session.get(
            BibliographicResource,
            self._parse_parent_resource_id(parent_id),
        )
        if parent_resource is None or parent_resource.id == resource_id:
            raise ValueError(
                'A obra-pai deve existir e ser do tipo documental esperado.'
            )

        parent_work = parent_resource.specific_work
        expected_parent_model = Magazine if magazine_child else work_model
        if type(parent_work) is not expected_parent_model:
            raise ValueError(
                'A obra-pai deve existir e ser do tipo documental esperado.'
            )
        if getattr(parent_work, 'is_partial', False):
            raise ValueError(
                'A obra-pai selecionada já é parte de outra obra.'
            )
        if isinstance(parent_work, AudioDocument):
            work_data['carrier_type'] = parent_work.carrier_type
            work_data['publication_place'] = parent_work.publication_place
            work_data['publisher'] = parent_work.publisher
            work_data['display_year'] = parent_work.display_year
            work_data['date_anchor'] = parent_work.date_anchor
            work_data['date_precision'] = parent_work.date_precision
        elif isinstance(parent_work, MusicalScore):
            work_data['publication_place'] = parent_work.publication_place
            work_data['publisher'] = parent_work.publisher
            work_data['display_year'] = parent_work.display_year
            work_data['date_anchor'] = parent_work.date_anchor
            work_data['date_precision'] = parent_work.date_precision
            work_data['instrumentation'] = parent_work.instrumentation
        elif isinstance(parent_work, EditorialMonograph):
            self._inherit_parent_fields(
                parent_work,
                work_data,
                {
                    'display_year', 'date_anchor', 'date_precision',
                    'publication_place', 'publisher', 'responsibilities',
                    'edition', 'page_quantity', 'volumes', 'illustrations',
                    'dimensions', 'translation_notes', 'original_full_title',
                    'collection_name', 'collection_number', 'isbn',
                    'additional_notes', 'url', 'viewed_at',
                },
            )
        elif isinstance(parent_work, AcademicMonograph):
            self._inherit_parent_fields(
                parent_work,
                work_data,
                {
                    'display_year', 'date_anchor', 'date_precision',
                    'publication_place', 'page_quantity', 'thesis_type',
                    'education_level', 'course', 'faculty', 'defense_year',
                    'additional_notes', 'url', 'viewed_at',
                },
            )
        elif isinstance(parent_work, CorrespondenceMonograph):
            self._inherit_parent_fields(
                parent_work,
                work_data,
                {
                    'display_year', 'date_anchor', 'date_precision',
                    'publication_place', 'recipient', 'correspondence_type',
                    'additional_notes', 'url', 'viewed_at',
                },
            )
        elif isinstance(
            parent_work, (MonographicProceedings, PeriodicalProceedings)
        ):
            inherited_fields = {
                'display_year', 'date_anchor', 'date_precision',
                'event_name', 'event_number', 'event_year', 'event_place',
                'publication_place', 'publisher', 'publication_year',
                'page_quantity',
            }
            if isinstance(parent_work, MonographicProceedings):
                inherited_fields.update({'isbn', 'published'})
            else:
                inherited_fields.update({
                    'vol_or_year', 'number', 'start_page', 'end_page',
                    'publication_date', 'issn',
                })
            self._inherit_parent_fields(
                parent_work,
                work_data,
                inherited_fields,
            )
        return parent_resource

    @staticmethod
    def _inherit_parent_fields(
        parent_work: WorkMixin,
        work_data: dict[str, object],
        field_names: set[str],
    ) -> None:
        for field_name in field_names:
            work_data[field_name] = getattr(parent_work, field_name)

    @staticmethod
    def _sync_magazine_fields(
        work_model: type[WorkMixin],
        work_data: dict[str, object],
        parent_resource: BibliographicResource | None,
    ) -> None:
        if work_model not in {JournalArticle, PeriodicalCollection}:
            return
        if parent_resource is None:
            raise ValueError('Selecione uma revista para esta obra.')
        magazine = parent_resource.specific_work
        if not isinstance(magazine, Magazine):
            raise ValueError('A obra-pai selecionada não é uma revista.')
        if work_model is PeriodicalCollection:
            work_data['title'] = magazine.title
        work_data['journal_title'] = magazine.title
        work_data['publication_place'] = magazine.publication_place

    def create(
        self,
        payload: WorkCreationPayload,
        author_ids: dict[int, int] | None = None,
    ) -> BibliographicResource:
        work_model = payload['work_model']
        author_names = payload['author_names']
        resource_data = payload['resource_data']
        work_data = dict(payload['work_data'])
        relationship_name = payload['relationship_name']

        parent_resource = self._resolve_parent_resource(
            work_model, work_data
        )
        self._sync_magazine_fields(
            work_model, work_data, parent_resource
        )

        resource = BibliographicResource(**resource_data)
        work = work_model(**work_data)
        setattr(resource, relationship_name, work)
        if resource.specific_work is None:
            raise ValueError(
                'Uma BibliographicResource precisa ter um specific_work '
                'associado antes de ser persistida.'
            )
        self.session.add(resource)

        attached_author_ids: set[int] = set()
        for index, author_reference in enumerate(author_names):
            author_id = (author_ids or {}).get(index)
            if author_reference['id'] is not None:
                author_id = author_reference['id']
            author = (
                self._author_by_id(author_id)
                if author_id is not None
                else self._find_or_create_author(author_reference)
            )
            if author.id in attached_author_ids:
                continue
            resource.authorships.append(Authorship(author=author))
            attached_author_ids.add(author.id)

        try:
            self.session.commit()
        except Exception as error:
            log_exception("Falha ao persistir recurso e autores", error)
            self.session.rollback()
            raise
        self.session.refresh(resource)
        return resource

    def update(
        self,
        resource_id: int,
        payload: WorkCreationPayload,
    ) -> BibliographicResource:
        """Update a resource and its authors without changing its identity."""
        resource = self.session.get(BibliographicResource, resource_id)
        if resource is None:
            raise ValueError('A obra que você tentou editar não existe mais.')

        work_model = payload['work_model']
        work = resource.specific_work
        if work is None:
            raise ValueError(
                'A obra que você tentou editar não possui detalhes.'
            )
        if type(work) is not work_model:
            raise ValueError(
                'O tipo documental da obra não pode ser alterado durante '
                'a edição.'
            )

        work_data = dict(payload['work_data'])
        parent_resource = self._resolve_parent_resource(
            work_model, work_data, resource_id=resource_id
        )
        self._sync_magazine_fields(
            work_model, work_data, parent_resource
        )

        previous_author_ids = {
            authorship.author_id for authorship in resource.authorships
        }
        column_keys = {column.key for column in work.__mapper__.column_attrs}
        for key, value in work_data.items():
            if key in column_keys:
                column = work.__mapper__.columns[key]
                if value is None and not column.nullable:
                    default = column.default
                    if not isinstance(
                        default, ScalarElementColumnDefault
                    ):
                        raise ValueError(
                            f'O campo {key.replace("_", " ")} é obrigatório.'
                        )
                    value = default.arg
                setattr(work, key, value)
        if 'is_partial' in column_keys and not work_data.get('is_partial'):
            for key in (
                'parent_bibliographic_resource_id',
                'part_start_page',
                'part_end_page',
                'part_volume',
                'part_chapter',
                'consult_start_year',
                'consult_end_year',
            ):
                if key in column_keys:
                    setattr(work, key, None)

        desired_authors: dict[int, Author] = {}
        for author_reference in payload['author_names']:
            author_id = author_reference['id']
            author = (
                self._author_by_id(author_id)
                if author_id is not None
                else self._find_or_create_author(author_reference)
            )
            desired_authors[author.id] = author

        current_authorships = {
            authorship.author_id: authorship
            for authorship in resource.authorships
        }
        for author_id, authorship in current_authorships.items():
            if author_id not in desired_authors:
                resource.authorships.remove(authorship)
        for author_id, author in desired_authors.items():
            if author_id not in current_authorships:
                resource.authorships.append(Authorship(author=author))

        try:
            self.session.flush()
            for author_id in previous_author_ids:
                remaining_authorship = self.session.scalar(
                    select(Authorship.id)
                    .where(Authorship.author_id == author_id)
                    .limit(1)
                )
                if remaining_authorship is None:
                    self.session.execute(
                        delete(Author).where(Author.id == author_id)
                    )
            self.session.commit()
        except Exception as error:
            log_exception("Falha ao atualizar obra e autores", error)
            self.session.rollback()
            raise

        self.session.refresh(resource)
        return resource

    def _find_or_create_author(self, reference: AuthorReference) -> Author:
        if reference['corporation']:
            name = self.normalizer.legal_entity_name_normalizer(
                reference['name']
            )
            elements = {
                'given_names': name,
                'last_name': name,
                'given_names_initials': '',
                'last_name_initial': '',
            }
        else:
            parsed = self.normalizer.natural_name_parser(reference['name'])
            elements = {
                'given_names': parsed.given_names,
                'last_name': parsed.last_name,
                'given_names_initials': parsed.given_names_initials,
                'last_name_initial': parsed.last_name_initial,
            }

        jurisdiction = None
        jurisdiction_name = (reference.get('jurisdiction_name') or '').strip()
        if jurisdiction_name:
            jurisdiction = self._find_or_create_author({
                'name': jurisdiction_name,
                'id': reference.get('jurisdiction_id'),
                'corporation': True,
                'acronym': None,
                'jurisdiction_id': None,
                'jurisdiction_name': None,
            })

        statement = select(Author).where(
            Author.given_names == elements['given_names'],
            Author.last_name == elements['last_name'],
        )
        author = self.session.scalars(statement).first()
        if author is not None:
            if (
                jurisdiction is not None
                and author.jurisdiction_id != jurisdiction.id
            ):
                author.jurisdiction = jurisdiction
            return author

        author = Author(
            given_names=elements['given_names'],
            last_name=elements['last_name'],
            given_names_initials=elements['given_names_initials'],
            last_name_initial=elements['last_name_initial'],
            corporation=reference['corporation'],
            acronym=reference['acronym'],
            jurisdiction=jurisdiction,
        )
        self.session.add(author)
        self.session.flush()
        return author

    def find_possible_duplicate_authors(self, name: str) -> list[Author]:
        """Retorna homônimos parciais que precisam de confirmação humana."""
        elements = self.normalizer.natural_name_parser(name)
        if not elements.given_names:
            return []
        first_given_name = elements.given_names.split(maxsplit=1)[0]
        statement = select(Author).where(
            Author.last_name == elements.last_name,
            or_(
                Author.given_names == first_given_name,
                Author.given_names.like(f'{first_given_name} %'),
            ),
            Author.given_names != elements.given_names,
        ).order_by(Author.given_names)
        return list(self.session.scalars(statement))

    def search_authors(
        self, query: str, limit: int = 8
    ) -> list[AuthorSearchResult]:
        """Busca autores existentes pelo nome para o formulario."""
        query = query.strip()
        if not query:
            return []
        statement = (
            select(Author)
            .where(
                or_(
                    Author.given_names.ilike(f"%{query}%"),
                    Author.last_name.ilike(f"%{query}%"),
                    Author.acronym.ilike(f"%{query}%"),
                )
            )
            .order_by(Author.last_name, Author.given_names)
            .limit(limit)
        )
        return [
            {
                'id': author.id,
                'name': (
                    author.given_names
                    if author.corporation
                    else f"{author.given_names} {author.last_name}"
                ),
                'corporation': author.corporation,
                'acronym': author.acronym,
            }
            for author in self.session.scalars(statement)
        ]

    def list_works(self) -> list[BibliographicResource]:
        """Lista todas as obras cadastradas, da mais recente à mais antiga."""
        statement = (
            select(BibliographicResource)
            .options(
                selectinload(BibliographicResource.authorships)
                .selectinload(Authorship.author)
                .selectinload(Author.jurisdiction),
                selectinload(BibliographicResource.editorial_monograph),
                selectinload(BibliographicResource.academic_monograph),
                selectinload(BibliographicResource.correspondence_monograph),
                selectinload(BibliographicResource.periodical_collection),
                selectinload(BibliographicResource.magazine),
                selectinload(BibliographicResource.journal_article),
                selectinload(BibliographicResource.newspaper_article),
                selectinload(BibliographicResource.monographic_proceeding),
                selectinload(BibliographicResource.periodical_proceeding),
                selectinload(BibliographicResource.patent),
                selectinload(BibliographicResource.statute),
                selectinload(BibliographicResource.caselaw),
                selectinload(BibliographicResource.audiovisual_document),
                selectinload(BibliographicResource.audio_document),
                selectinload(BibliographicResource.visual_document),
                selectinload(BibliographicResource.three_dimensional_document),
                selectinload(BibliographicResource.cartographic_document),
                selectinload(BibliographicResource.musical_score),
                selectinload(
                    BibliographicResource.miscellaneous_digital_document
                ),
            )
            .order_by(BibliographicResource.id.desc())
        )
        works = list(self.session.scalars(statement))
        for resource in works:
            for authorship in resource.authorships:
                author = authorship.author
                if author.jurisdiction_id is not None:
                    _ = author.jurisdiction
            work = resource.specific_work
            if work is None:
                continue
            _ = work.bibliographic_resource
            _ = work.authors
            if getattr(work, 'is_partial', False):
                parent = getattr(work, 'parent_bibliographic_resource', None)
                if parent is not None:
                    parent.id
                    parent.specific_work
        return works

    def get_work_title(self, resource_id: int) -> str | None:
        """Return a work title without exposing lazy relations to callers."""
        resource = self.session.get(BibliographicResource, resource_id)
        if resource is None or resource.specific_work is None:
            return None
        return resource.specific_work.title

    def search_works(
        self,
        query: str,
        work_model: type[WorkMixin] | None = None,
        limit: int = 8,
    ) -> list[BibliographicResource]:
        """Busca obras pelo titulo para seletores relacionados."""
        query = query.strip().casefold()
        if not query:
            return []
        matches = []
        for resource in self.list_works():
            work = resource.specific_work
            if (
                work is not None
                and (work_model is None or type(work) is work_model)
                and not getattr(work, 'is_partial', False)
                and query in work.title.casefold()
            ):
                matches.append(resource)
                if len(matches) == limit:
                    break
        return matches

    def _author_by_id(self, author_id: int) -> Author:
        author = self.session.get(Author, author_id)
        if author is None:
            raise ValueError('O autor selecionado não está mais disponível.')
        return author

    def create_many(
        self, payloads: Iterable[WorkCreationPayload]
    ) -> list[BibliographicResource]:
        return [self.create(payload) for payload in payloads]

    def remove_work(self, work: BibliographicResource) -> None:
        author_ids = list(
            self.session.scalars(
                select(Authorship.author_id).where(
                    Authorship.bib_res_id == work.id
                )
            )
        )

        try:
            self.session.execute(
                delete(BibliographicResource).where(
                    BibliographicResource.id == work.id
                )
            )

            for author_id in author_ids:
                remaining_authorship = self.session.scalar(
                    select(Authorship.id)
                    .where(Authorship.author_id == author_id)
                    .limit(1)
                )
                if remaining_authorship is None:
                    self.session.execute(
                        delete(Author).where(Author.id == author_id)
                    )

            self.session.commit()
        except Exception as error:
            log_exception("Falha ao excluir obra e autores órfãos", error)
            self.session.rollback()
            raise
