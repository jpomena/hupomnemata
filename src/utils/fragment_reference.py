from src.contracts import FragmentRecord


def fragment_abnt_notation(fragment: FragmentRecord) -> str:
    author = fragment['citation_author'] or fragment['work_title']
    citation = f"{author}, {fragment['display_year']}"
    location_type = fragment['location_type']
    location_value = fragment['location_value']
    if location_type and location_value:
        prefixes = {
            'Página': 'p.',
            'Capítulo': 'cap.',
            'Seção': 'seção',
            'Localizador/posição': 'localizador',
        }
        location = (
            f"{prefixes[location_type]} {location_value}"
            if location_type in prefixes
            else location_value
        )
        citation = f'{citation}, {location}'
    return f'({citation})'
