"""Testes do fatiamento de ``CompilationHubCadernoMixin``."""

import src.views.compilation_hub.caderno_mixin as caderno_mixin
from src.views.compilation_hub.caderno_actions import CadernoActionsMixin
from src.views.compilation_hub.caderno_common import QUEUE_KEY, kind_label, quoted
from src.views.compilation_hub.caderno_data import CadernoDataMixin
from src.views.compilation_hub.caderno_mixin import CompilationHubCadernoMixin
from src.views.compilation_hub.caderno_outline import CadernoOutlineMixin
from src.views.compilation_hub.caderno_prompts import CadernoPromptsMixin
from src.views.compilation_hub.caderno_writing import CadernoWritingMixin
from src.views.compilation_hub.hub_composer import CompilationHubComposer


def test_caderno_mro_contains_the_five_mixins():
    assert CompilationHubCadernoMixin.__mro__[1:6] == (
        CadernoDataMixin,
        CadernoActionsMixin,
        CadernoPromptsMixin,
        CadernoOutlineMixin,
        CadernoWritingMixin,
    )


def test_each_method_lives_in_its_designated_mixin():
    expected = {
        CadernoDataMixin: (
            "_root_chapters",
            "_section_fragments",
            "_work_references",
            "_year_suffixes",
        ),
        CadernoActionsMixin: (
            "_create_section",
            "_restore_section",
            "_remove_from_caderno",
            "_copy_fragment",
            "_copy_caderno",
        ),
        CadernoPromptsMixin: (
            "_section_dialog",
            "_prompt_new_argument",
            "_prompt_link_fragment_to_section",
        ),
        CadernoOutlineMixin: (
            "_compose_outline",
            "_focus_idea",
            "_scroll_writing",
        ),
        CadernoWritingMixin: (
            "_fragment_menu",
            "_compose_fragment_block",
            "_compose_caderno",
        ),
    }
    for mixin, names in expected.items():
        for name in names:
            assert name in mixin.__dict__, f"{name} ausente em {mixin.__name__}"


def test_patch_target_stays_in_facade_module():
    # test_compilations.py patcheia ``caderno_mixin.copy_references`` e espera
    # que o handler copie o texto; por isso o método não pode migrar de módulo.
    assert "_copy_references" in CompilationHubCadernoMixin.__dict__
    assert caderno_mixin.copy_references is not None
    assert callable(caderno_mixin.copy_references)


def test_no_method_is_defined_twice_in_the_mro():
    owners: dict[str, list[str]] = {}
    for klass in CompilationHubCadernoMixin.__mro__:
        for name, value in vars(klass).items():
            if name.startswith("__") or not callable(value):
                continue
            owners.setdefault(name, []).append(klass.__name__)
    duplicated = {name: klasses for name, klasses in owners.items() if len(klasses) > 1}

    assert duplicated == {}


def test_mixins_have_no_initializer():
    for mixin in (
        CadernoDataMixin,
        CadernoActionsMixin,
        CadernoPromptsMixin,
        CadernoOutlineMixin,
        CadernoWritingMixin,
    ):
        assert "__init__" not in mixin.__dict__


def test_common_helpers_are_reexported():
    assert QUEUE_KEY == "queue"
    assert caderno_mixin.QUEUE_KEY is QUEUE_KEY
    assert caderno_mixin.kind_label is kind_label
    assert caderno_mixin.quoted is quoted


def test_hub_still_inherits_the_caderno_facade():
    assert issubclass(CompilationHubComposer, CompilationHubCadernoMixin)
