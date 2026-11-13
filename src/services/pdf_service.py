import hashlib
import shutil
import sys
from pathlib import Path
from typing import Any

from pypdf import PdfReader
from sqlalchemy import select

from src.db.db import SessionLocal
from src.domains import BibliographicResource, Fragment, PdfAnnotation
from src.utils.error_log import log_exception

if getattr(sys, 'frozen', False):
    _BASE_DIR = Path(sys.executable).parent
else:
    _BASE_DIR = Path(__file__).resolve().parents[2]

DEFAULT_PDF_STORAGE_DIR = _BASE_DIR / 'data' / 'storage' / 'pdfs'


class PdfService:
    """Serviço sagrado de gestão, armazenamento e anotações de arquivos PDF."""

    def __init__(
        self,
        storage_dir: Path | None = None,
        base_dir: Path | None = None,
    ) -> None:
        self.base_dir = Path(base_dir or _BASE_DIR)
        self.storage_dir = Path(storage_dir or DEFAULT_PDF_STORAGE_DIR)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def resolve_path(self, stored_path: str) -> Path:
        """Resolve o caminho absoluto a partir do valor gravado no banco."""
        p = Path(stored_path)
        if p.is_absolute():
            return p
        return self.base_dir / p

    @staticmethod
    def compute_sha256(file_path: Path) -> str:
        """Gera o hash SHA-256 criptográfico para integridade do arquivo."""
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    @staticmethod
    def extract_page_count(file_path: Path) -> int | None:
        """Extrai o número total de páginas do arquivo PDF."""
        try:
            reader = PdfReader(str(file_path))
            return len(reader.pages)
        except Exception as error:
            log_exception(f'Falha ao ler páginas do PDF {file_path}', error)
            return None

    def attach_pdf(
        self,
        bib_res_id: int,
        source_path: str | Path,
        original_filename: str | None = None,
    ) -> dict[str, Any]:
        """Copia o PDF para o repositório gerenciado e vincula à obra (1:1)."""
        src = Path(source_path).resolve()
        if not src.exists() or not src.is_file():
            raise FileNotFoundError(f'Arquivo de origem inexistente: {src}')

        if src.suffix.lower() != '.pdf':
            raise ValueError('Apenas arquivos com extensão .pdf são aceitos.')

        filename = original_filename or src.name
        sha256_hash = self.compute_sha256(src)
        page_count = self.extract_page_count(src)

        # Destino determinístico e seguro
        dest_filename = f'{bib_res_id}_{sha256_hash[:12]}.pdf'
        dest_path = self.storage_dir / dest_filename

        try:
            shutil.copy2(src, dest_path)
        except Exception as error:
            log_exception(f'Falha ao copiar PDF para {dest_path}', error)
            raise IOError(f'Não foi possível copiar o arquivo: {error}') from error

        try:
            rel_path = str(dest_path.relative_to(self.base_dir))
        except ValueError:
            rel_path = str(dest_path)

        with SessionLocal() as session:
            resource = session.get(BibliographicResource, bib_res_id)
            if resource is None:
                if dest_path.exists():
                    dest_path.unlink()
                raise ValueError(f'Obra bibliográfica {bib_res_id} não encontrada.')

            # Se havia um PDF anterior com caminho diferente, remove o arquivo órfão
            if resource.pdf_path and resource.pdf_path != rel_path:
                old_file = self.resolve_path(resource.pdf_path)
                if old_file.exists() and old_file.is_file():
                    try:
                        old_file.unlink()
                    except Exception as err:
                        log_exception('Falha ao remover PDF anterior substituído', err)

            resource.pdf_filename = filename
            resource.pdf_path = rel_path
            resource.pdf_sha256 = sha256_hash
            resource.pdf_page_count = page_count
            session.commit()

            return {
                'bib_res_id': bib_res_id,
                'pdf_filename': filename,
                'pdf_path': rel_path,
                'pdf_absolute_path': str(dest_path),
                'pdf_sha256': sha256_hash,
                'pdf_page_count': page_count,
            }

    def detach_pdf(self, bib_res_id: int, delete_file: bool = True) -> bool:
        """Desvincula o PDF da obra e opcionalmente apaga o arquivo do repositório."""
        with SessionLocal() as session:
            resource = session.get(BibliographicResource, bib_res_id)
            if resource is None:
                raise ValueError(f'Obra bibliográfica {bib_res_id} não encontrada.')

            if not resource.pdf_path:
                return False

            if delete_file:
                target_file = self.resolve_path(resource.pdf_path)
                if target_file.exists() and target_file.is_file():
                    try:
                        target_file.unlink()
                    except Exception as err:
                        log_exception(f'Falha ao deletar PDF físico {target_file}', err)

            resource.pdf_filename = None
            resource.pdf_path = None
            resource.pdf_sha256 = None
            resource.pdf_page_count = None
            session.commit()
            return True

    def get_pdf_info(self, bib_res_id: int) -> dict[str, Any] | None:
        """Retorna os metadados do PDF vinculado à obra."""
        with SessionLocal() as session:
            resource = session.get(BibliographicResource, bib_res_id)
            if resource is None or not resource.pdf_path:
                return None

            abs_path = self.resolve_path(resource.pdf_path)
            return {
                'bib_res_id': resource.id,
                'pdf_filename': resource.pdf_filename,
                'pdf_path': resource.pdf_path,
                'pdf_absolute_path': str(abs_path),
                'pdf_sha256': resource.pdf_sha256,
                'pdf_page_count': resource.pdf_page_count,
                'file_exists': abs_path.exists(),
            }

    # ── Gestão de Anotações e Grifos ─────────────────────────────

    def list_annotations(
        self, bib_res_id: int, page_number: int | None = None
    ) -> list[dict[str, Any]]:
        """Lista todas as anotações do PDF, opcionalmente filtrando por página."""
        with SessionLocal() as session:
            query = select(PdfAnnotation).where(PdfAnnotation.bib_res_id == bib_res_id)
            if page_number is not None:
                query = query.where(PdfAnnotation.page_number == page_number)
            query = query.order_by(PdfAnnotation.page_number, PdfAnnotation.id)

            annotations = session.scalars(query).all()
            return [
                {
                    'id': a.id,
                    'bib_res_id': a.bib_res_id,
                    'page_number': a.page_number,
                    'selected_text': a.selected_text,
                    'note': a.note,
                    'color': a.color,
                    'rect_json': a.rect_json,
                    'fragment_id': a.fragment_id,
                    'created_at': a.created_at.isoformat() if a.created_at else None,
                }
                for a in annotations
            ]

    def save_annotation(
        self,
        bib_res_id: int,
        page_number: int,
        selected_text: str,
        rect_json: str = '[]',
        color: str = '#D97706',
        note: str | None = None,
        fragment_id: int | None = None,
    ) -> dict[str, Any]:
        """Persiste um novo grifo ou nota na página do PDF."""
        text_clean = selected_text.strip()
        if not text_clean:
            raise ValueError('O texto selecionado para o grifo não pode ser vazio.')

        with SessionLocal() as session:
            resource = session.get(BibliographicResource, bib_res_id)
            if resource is None:
                raise ValueError(f'Obra bibliográfica {bib_res_id} não encontrada.')

            annotation = PdfAnnotation(
                bib_res_id=bib_res_id,
                page_number=max(1, int(page_number)),
                selected_text=text_clean,
                rect_json=rect_json or '[]',
                color=color or '#D97706',
                note=note.strip() if note else None,
                fragment_id=fragment_id,
            )
            session.add(annotation)
            session.commit()
            session.refresh(annotation)

            return {
                'id': annotation.id,
                'bib_res_id': annotation.bib_res_id,
                'page_number': annotation.page_number,
                'selected_text': annotation.selected_text,
                'note': annotation.note,
                'color': annotation.color,
                'rect_json': annotation.rect_json,
                'fragment_id': annotation.fragment_id,
                'created_at': annotation.created_at.isoformat() if annotation.created_at else None,
            }

    def delete_annotation(self, annotation_id: int) -> bool:
        """Remove um grifo do banco de dados."""
        with SessionLocal() as session:
            annotation = session.get(PdfAnnotation, annotation_id)
            if annotation is None:
                return False
            session.delete(annotation)
            session.commit()
            return True

    def extract_as_fragment(
        self, annotation_id: int, fragment_type: str = 'quote'
    ) -> dict[str, Any]:
        """Converte uma anotação de leitura em um Fragmento oficial do Hupomnemata."""
        with SessionLocal() as session:
            annotation = session.get(PdfAnnotation, annotation_id)
            if annotation is None:
                raise ValueError(f'Anotação {annotation_id} não encontrada.')

            fragment = Fragment(
                bib_res_id=annotation.bib_res_id,
                excerpt=annotation.selected_text,
                fragment_type=fragment_type,
                location_type='Página',
                location_value=str(annotation.page_number),
                start_page=annotation.page_number,
                end_page=annotation.page_number,
            )
            session.add(fragment)
            session.flush()

            annotation.fragment_id = fragment.id
            session.commit()

            return {
                'fragment_id': fragment.id,
                'bib_res_id': fragment.bib_res_id,
                'excerpt': fragment.excerpt,
                'fragment_type': fragment.fragment_type,
                'location_type': fragment.location_type,
                'location_value': fragment.location_value,
                'annotation_id': annotation.id,
            }
