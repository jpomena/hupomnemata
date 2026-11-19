"""Fixtures globais canônicas para a suíte de testes do Hupomnemata."""

import os
import tempfile
from pathlib import Path

# Sandbox de dados **antes** de importar src.db.db: mesmo que alguma fixture
# falhe em isolar a engine, nenhum teste pode tocar o banco do usuário.
_TEST_DATA_DIR = Path(tempfile.gettempdir()) / f'hupomnemata-tests-{os.getpid()}'
os.environ.setdefault('HUPOMNEMATA_DATA_DIR', str(_TEST_DATA_DIR))

import pytest  # noqa: E402

from src.configs.settings import (  # noqa: E402
    COLORS_DARK,
    COLORS_LIGHT,
    FONT_FAMILIES,
    FONT_SIZES,
    FONT_WEIGHTS,
    ICON_SIZES,
    MAIN_VIEW_CARDS,
    PAGE_FONTS,
    TEXTS,
    UI,
)
from src.db import db as db_module  # noqa: E402
from src.db.sqlite_runtime import create_sqlite_engine  # noqa: E402
from src.utils.types import ViewConfig  # noqa: E402


@pytest.fixture
def view_config() -> ViewConfig:
    """Configuração visual canônica em tema claro para testes de interface."""
    return ViewConfig(
        colors=COLORS_LIGHT,
        page_fonts=PAGE_FONTS,
        font_families=FONT_FAMILIES,
        font_sizes=FONT_SIZES,
        icon_sizes=ICON_SIZES,
        font_weights=FONT_WEIGHTS,
        ui=UI,
        texts=TEXTS,
        core_menus={},
        main_view_cards=MAIN_VIEW_CARDS,
    )


@pytest.fixture
def dark_view_config() -> ViewConfig:
    """Configuração visual canônica em tema escuro para testes de interface."""
    return ViewConfig(
        colors=COLORS_DARK,
        page_fonts=PAGE_FONTS,
        font_families=FONT_FAMILIES,
        font_sizes=FONT_SIZES,
        icon_sizes=ICON_SIZES,
        font_weights=FONT_WEIGHTS,
        ui=UI,
        texts=TEXTS,
        core_menus={},
        main_view_cards=MAIN_VIEW_CARDS,
    )


@pytest.fixture
def clean_db():
    """Inicializa banco SQLite isolado em memória com StaticPool para altíssima performance.

    A engine anterior é restaurada ao final para que nenhum teste subsequente
    herde conexões descartadas nem reabra o banco real do projeto.
    """
    from sqlalchemy.pool import StaticPool

    original_engine = db_module.engine
    original_initialized = db_module._initialized_engine
    engine = create_sqlite_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    db_module.engine = engine
    db_module.SessionLocal.configure(bind=engine)
    db_module.Base.metadata.create_all(bind=engine)
    db_module._initialized_engine = engine
    try:
        yield engine
    finally:
        db_module.Base.metadata.drop_all(bind=engine)
        engine.dispose()
        db_module.engine = original_engine
        db_module.SessionLocal.configure(bind=original_engine)
        # Restaura exatamente o estado anterior (inclusive None).
        db_module._initialized_engine = original_initialized
