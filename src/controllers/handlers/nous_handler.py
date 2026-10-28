"""Handler e Mixin de inteligência artificial e cognição (Menu Nous)."""

from collections.abc import Callable
from typing import Any, Dict, List, Optional, Tuple


class NousControllerMixin:
    """Mixin para operações do Menu Nous e Enriquecimento Cognitivo com IA."""

    def get_nous_api_key(self) -> str:
        """Recupera a chave de API Gemini persistida."""
        return self.nous_service.get_api_key()

    def save_nous_api_key(self, api_key: str) -> bool:
        """Persiste a chave de API do usuário."""
        return self.nous_service.save_api_key(api_key)

    def test_nous_connection(self, api_key: Optional[str] = None) -> Tuple[bool, str]:
        """Testa conectividade e validade da chave com a API Google Gemini."""
        return self.nous_service.test_connection(api_key=api_key)

    def generate_work_ai_description(self, work_id: int) -> Tuple[bool, str]:
        """Gera síntese conceitual/epistemológica para uma obra via Gemini."""
        return self.nous_service.generate_work_description(work_id)

    def override_work_description(self, work_id: int, custom_text: Optional[str]) -> bool:
        """Define ou limpa descrição personalizada de uma obra."""
        return self.nous_service.override_work_description(work_id, custom_text)

    def list_works_ai_status(self) -> List[Dict[str, Any]]:
        """Lista todas as obras e respectivos status de síntese da IA."""
        return self.nous_service.list_works_ai_status()

    def generate_batch_ai_descriptions(
        self, on_progress: Optional[Callable[[int, int, str], None]] = None
    ) -> Dict[str, Any]:
        """Gera em lote sínteses para todas as obras pendentes."""
        return self.nous_service.generate_batch_pending(on_progress=on_progress)
