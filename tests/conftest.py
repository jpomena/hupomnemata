"""Fixtures globais canônicas para a suíte de testes do Hupomnemata."""

import pytest
from sqlalchemy import create_engine

from src.configs.settings import (
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
from src.db import db as db_module
from src.utils.types import ViewConfig


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
    """Inicializa banco SQLite isolado em memória com StaticPool para altíssima performance."""
    from sqlalchemy.pool import StaticPool
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    db_module.engine = engine
    db_module.SessionLocal.configure(bind=engine)
    db_module.Base.metadata.create_all(bind=engine)
    yield engine
    db_module.Base.metadata.drop_all(bind=engine)
    engine.dispose()
