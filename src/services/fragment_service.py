from collections.abc import Mapping

from src.contracts import (
    FRAGMENT_LOCATION_TYPES,
    FRAGMENT_TYPE_LABELS,
    FragmentPayload,
    FragmentRecord,
)
from src.db.db import SessionLocal
from src.repositories.fragment_repository import FragmentRepository


class FragmentService:
    """Validates and coordinates fragment operations."""

    @staticmethod
    def _resource_id(value: object) -> int:
        if isinstance(value, bool):
            raise ValueError('Selecione uma obra do Acervo.')
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError as error:
                raise ValueError(
                    'Selecione uma obra do Acervo.'
                ) from error
        raise ValueError('Selecione uma obra do Acervo.')

    @classmethod
    def _payload(
        cls,
        data: Mapping[str, object],
    ) -> FragmentPayload:
        fragment_type = data.get('fragment_type')
        if (
            not isinstance(fragment_type, str)
            or fragment_type not in FRAGMENT_TYPE_LABELS
        ):
            raise ValueError(
                'Selecione se o fragmento é citação ou comentário.'
            )

        excerpt = data.get('excerpt')
        if not isinstance(excerpt, str) or not excerpt.strip():
            raise ValueError('O conteúdo do fragmento é obrigatório.')

        raw_location_type = data.get('location_type')
        raw_location_value = data.get('location_value')
        location_type = (
            raw_location_type.strip()
            if isinstance(raw_location_type, str)
            else ''
        )
        location_value = (
            raw_location_value.strip()
            if isinstance(raw_location_value, str)
            else ''
        )

        if fragment_type == 'quote' and not (
            location_type and location_value
        ):
            raise ValueError(
                'Citações exigem o tipo e o valor da localização.'
            )
        if bool(location_type) != bool(location_value):
            raise ValueError(
                'Informe o tipo e o valor da localização, '
                'ou deixe ambos vazios.'
            )
        if location_type and location_type not in FRAGMENT_LOCATION_TYPES:
            raise ValueError('Selecione um tipo de localização válido.')
        if location_type == 'Página' and len(location_value) > 5:
            raise ValueError(
                'A localização de página deve ter no máximo 5 caracteres.'
            )
        if len(location_value) > 100:
            raise ValueError(
                'A localização deve ter no máximo 100 caracteres.'
            )

        return {
            'fragment_type': fragment_type,
            'excerpt': excerpt.strip(),
            'bib_res_id': cls._resource_id(data.get('bib_res_id')),
            'location_type': location_type or None,
            'location_value': location_value or None,
        }

    def list_fragments(self) -> list[FragmentRecord]:
        with SessionLocal() as session:
            return FragmentRepository(session).list_fragments()

    def create(self, data: Mapping[str, object]) -> int:
        payload = self._payload(data)
        with SessionLocal() as session:
            return FragmentRepository(session).create(payload)

    def update(
        self,
        fragment_id: int,
        data: Mapping[str, object],
    ) -> None:
        payload = self._payload(data)
        with SessionLocal() as session:
            FragmentRepository(session).update(fragment_id, payload)

    def delete(self, fragment_id: int) -> None:
        with SessionLocal() as session:
            FragmentRepository(session).delete(fragment_id)
