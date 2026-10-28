"""Especificações para documentos multimídia, artísticos, sonoros e digitais."""

import flet as ft
from .base import FieldSpec, PUBLICATION, _spec

MISC_DIGITAL_SPEC = _spec(
    "miscellaneous_digital_document",
    "Documento digital",
    "Documento digital diverso",
    ft.Icons.INSERT_DRIVE_FILE_OUTLINED,
    FieldSpec(
        key="version", label="Versão", hint="Ex.: 2", kind="number"
    ),
    FieldSpec(
        key="publication_place",
        label="Local de publicação (se houver)",
        hint="Ex.: São Paulo",
        required=False
    ),
    FieldSpec(key="additional_notes", label="Notas adicionais")
)

AUDIOVISUAL_SPEC = _spec(
    "audiovisual_document",
    "Audiovisual",
    "Filme, vídeo ou gravação",
    ft.Icons.VIDEO_LIBRARY_OUTLINED,
    FieldSpec(
        key="carrier_type",
        label="Tipo de suporte",
        hint="Ex.: DVD",
        required=True
    ),
    FieldSpec(
        key="seconds",
        label="Duração em segundos",
        hint="Ex.: 5400",
        kind="number",
        required=True,
    ),
    FieldSpec(key="sound", label="Possui som", kind="checkbox"),
    FieldSpec(key="colorized", label="Colorizado", kind="checkbox"),
    *PUBLICATION,
    FieldSpec(
        key="responsibilities",
        label="Responsabilidades (direção, produção etc.)",
        kind="responsibilities",
    ),
    FieldSpec(key="additional_notes", label="Notas adicionais")
)

AUDIO_SPEC = _spec(
    "audio_document",
    "Áudio",
    "Disco, podcast ou gravação sonora",
    ft.Icons.AUDIOTRACK,
    FieldSpec(
        key="carrier_type",
        label="Tipo de suporte (obrigatório se não houver URL)",
        required=False,
    ),
    FieldSpec(
        key="seconds",
        label="Duração em segundos (se houver)",
        hint="Ex.: 1034",
        kind="number",
        required=False,
    ),
    FieldSpec(
        key="physical_details",
        label="Detalhes físicos (se houver)",
        hint="Ex.: 33 rpm, estéreo",
    ),
    FieldSpec(
        key="additional_notes",
        label="Notas adicionais",
        hint="Ex.: App Google Play Livros",
    ),
    FieldSpec(
        key="responsibilities",
        label="Responsabilidades (compositor, intérprete, ledor etc.)",
        kind="responsibilities",
    ),
    FieldSpec(
        key="authors",
        label="Autoria (se houver; para audiolivro)",
        hint="Autor da obra, como indicado no audiolivro",
        required=False,
    ),
    *PUBLICATION
)

MUSICAL_SCORE_SPEC = _spec(
    "musical_score",
    "Partitura",
    "Partitura ou obra musical",
    ft.Icons.MUSIC_NOTE,
    FieldSpec(
        key="instrumentation",
        label="Instrumentação",
        hint="Ex.: piano e voz (não repetir se já constar no título)",
        required=False,
    ),
    FieldSpec(
        key="author_role",
        label="Função da autoria (se houver)",
        hint="Ex.: comp. ou ed.",
    ),
    FieldSpec(
        key="physical_description",
        label="Descrição física",
        hint="Ex.: 1 partitura (86 p.) + 1 parte (34 p.)",
        required=True,
    ),
    FieldSpec(key="authors", label="Compositor(es), se houver"),
    *PUBLICATION,
    FieldSpec(key="additional_notes", label="Notas adicionais")
)

VISUAL_SPEC = _spec(
    "visual_document",
    "Documento visual",
    "Fotografia, cartaz ou imagem",
    ft.Icons.IMAGE_OUTLINED,
    FieldSpec(
        key="physical_description",
        label="Especificação do suporte",
        hint="Ex.: 3 fotografias, color., 10 cm x 8 cm",
        required=True,
    ),
    FieldSpec(key="additional_notes", label="Notas adicionais"),
)

CARTOGRAPHIC_SPEC = _spec(
    "cartographic_document",
    "Cartográfico",
    "Mapa, atlas ou carta",
    ft.Icons.MAP_OUTLINED,
    FieldSpec(
        key="edition", label="Edição", hint="Ex.: 2", kind="number"
    ),
    FieldSpec(
        key="physical_description",
        label="Descrição física",
        hint="Ex.: xiv, 135 p., il. col., 30 cm",
        required=True,
    ),
    *PUBLICATION,
    FieldSpec(
        key="additional_notes",
        label="Elementos complementares",
        hint="Ex.: escala, coordenadas, cores ou outras representações",
    ),
)

THREE_DIMENSIONAL_SPEC = _spec(
    "three_dimensional_document",
    "Tridimensional",
    "Objeto tridimensional",
    ft.Icons.VIEW_IN_AR,
    FieldSpec(
        key="manufacturing_place",
        label="Local (se houver)",
        hint="Ex.: Portugal",
    ),
    FieldSpec(
        key="manufacturer",
        label="Produtor ou fabricante (se houver)",
        hint="Ex.: Editora Abril",
    ),
    FieldSpec(
        key="physical_description",
        label="Descrição física",
        hint=(
            "Ex.: 1 escultura, estruturas tensionadas,"
            " color., 400 x 250 x 250 cm"
        ),
        required=True,
    ),
    FieldSpec(key="additional_notes", label="Elementos complementares"),
)
