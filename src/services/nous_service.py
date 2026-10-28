"""Serviço de Inteligência Artificial e Cognição do Hupomnemata (Menu Nous).
Integração com Google Gemini (BYOK), descoberta dinâmica de modelos, síntese epistemológica e gestão de metadados.
"""

from collections.abc import Callable
import json
from typing import Any, Dict, List, Optional, Tuple
import httpx

from src.db.db import SessionLocal
from src.domains import BibliographicResource
from src.services.settings_service import SettingsService
from src.services.knowledge_service import KnowledgeService
from src.utils.error_log import log_exception

# Modelos conhecidos em ordem de preferência analítica
KNOWN_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite"
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-flash-latest",
    "gemini-1.5-pro",
    "gemini-1.5-pro-latest",
    "gemini-pro",
]


class NousAIService:
    """Orquestra operações de inteligência artificial, BYOK e enriquecimento de obras."""

    def __init__(
        self,
        settings_service: Optional[SettingsService] = None,
        knowledge_service: Optional[KnowledgeService] = None,
    ) -> None:
        self.settings_service = settings_service or SettingsService()
        self.knowledge_service = knowledge_service or KnowledgeService()
        self.preferred_model: str = "gemini-1.5-flash"

    def get_api_key(self) -> str:
        """Recupera a chave de API do Gemini persistida nas configurações."""
        settings = self.settings_service.load_settings()
        return getattr(settings, "gemini_api_key", "") or ""

    def save_api_key(self, api_key: str) -> bool:
        """Salva a chave de API do Gemini no arquivo de preferências do usuário."""
        settings = self.settings_service.load_settings()
        settings.gemini_api_key = api_key.strip()
        return self.settings_service.save_settings(settings)

    def discover_available_models(self, key: str) -> List[str]:
        """Consulta na API do Google quais modelos exatos estão ativos e provisionados para esta chave."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
        try:
            with httpx.Client(timeout=12.0) as client:
                if not hasattr(client, "get"):
                    return []
                res = client.get(url)
                if res.status_code == 200:
                    data = res.json()
                    models = data.get("models", [])
                    active_models = []
                    for m in models:
                        name = m.get("name", "")
                        methods = m.get("supportedGenerationMethods", [])
                        if "generateContent" in methods:
                            clean_name = name.removeprefix("models/")
                            active_models.append(clean_name)
                    return active_models
        except Exception as exc:
            log_exception("NousAIService.discover_available_models", exc)
        return []

    def get_candidate_models(self, key: str) -> List[str]:
        """Retorna a lista priorizada de modelos disponíveis para a chave informada."""
        discovered = self.discover_available_models(key)
        candidates: List[str] = []

        if discovered:
            # Ordena os modelos descobertos pela nossa ordem de preferência
            for pref in KNOWN_MODELS:
                for d in discovered:
                    if (pref == d or pref in d) and d not in candidates:
                        candidates.append(d)
            # Adiciona quaisquer outros modelos suportados retornados pelo Google
            for d in discovered:
                if d not in candidates:
                    candidates.append(d)

        # Se a descoberta remota falhar, usa lista padrão resiliente
        if not candidates:
            candidates = [
                "gemini-1.5-flash",
                "gemini-2.0-flash",
                "gemini-1.5-pro",
                "gemini-pro",
            ]

        return candidates

    def test_connection(self, api_key: Optional[str] = None) -> Tuple[bool, str]:
        """Testa se a chave de API fornecida consegue autenticar e responder no Gemini."""
        key = (api_key if api_key is not None else self.get_api_key()).strip()
        if not key:
            return False, "Nenhuma chave de API foi fornecida."

        candidates = self.get_candidate_models(key)

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": "Responda apenas a palavra: OK"}
                    ]
                }
            ],
            "generationConfig": {
                "maxOutputTokens": 10,
                "temperature": 0.1,
            },
        }

        last_error = ""
        for model in candidates:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
            try:
                with httpx.Client(timeout=15.0) as client:
                    response = client.post(url, json=payload)
                    if response.status_code == 200:
                        self.preferred_model = model
                        return True, f"Conexão com Google Gemini ({model}) estabelecida com sucesso!"
                    elif response.status_code == 404:
                        last_error = f"Modelo {model} retornou 404."
                        continue
                    elif response.status_code in {400, 401, 403}:
                        try:
                            err_data = response.json()
                            msg = err_data.get("error", {}).get("message", "Chave de API inválida.")
                        except Exception:
                            msg = f"Erro de autenticação HTTP {response.status_code}"

                        # Se for explicitamente chave inválida, encerra imediatamente
                        if "key not valid" in msg.lower() or "api_key_invalid" in msg.lower():
                            return False, f"Chave de API inválida: {msg}"

                        # Se for modelo não suportado nesta região ou cota, tenta o próximo modelo
                        last_error = f"Modelo {model}: {msg}"
                        continue
                    else:
                        last_error = f"Serviço retornou status HTTP {response.status_code}."
            except httpx.ConnectTimeout:
                return False, "Tempo de conexão esgotado ao contatar os servidores do Google."
            except httpx.RequestError as exc:
                return False, f"Erro de rede ao conectar: {exc}"
            except Exception as exc:
                log_exception("NousAIService.test_connection", exc)
                return False, f"Erro inesperado: {exc}"

        return False, last_error or "Nenhum modelo Gemini suportado respondeu com sucesso."

    def generate_work_description(self, work_id: int) -> Tuple[bool, str]:
        """Gera síntese conceitual e epistemológica de uma obra através da IA do Gemini."""
        key = self.get_api_key()
        if not key:
            return False, "Configure sua chave de API no Menu Nous (BYOK) antes de gerar."

        with SessionLocal() as session:
            resource = session.get(BibliographicResource, work_id)
            if not resource:
                return False, f"Obra #{work_id} não encontrada no acervo."

            sw = resource.specific_work
            title = getattr(sw, "title", "Obra sem título") if sw else "Obra sem título"
            subtitle = getattr(sw, "subtitle", "") if sw else ""
            year = getattr(sw, "display_year", "") if sw else ""
            abstract = getattr(sw, "abstract", "") if sw else ""
            work_type = sw.__class__.__name__ if sw else "Recurso Bibliográfico"

            author_names = []
            if hasattr(resource, "authors"):
                for a in resource.authors:
                    parts = [p for p in [getattr(a, "given_names", ""), getattr(a, "last_name", "")] if p]
                    if parts:
                        author_names.append(" ".join(parts))
            authors_str = ", ".join(author_names) if author_names else "Autoria não informada"

            prompt = (
                "Você é um assistente acadêmico e bibliográfico de alta precisão conceitual.\n"
                "Produza uma síntese conceitual e epistemológica densa, elegante e fluida "
                "(de 1 a 2 parágrafos em português do Brasil) para a seguinte obra catalogada:\n"
                f"- Título: {title}\n"
                f"- Subtítulo: {subtitle or 'Nenhum'}\n"
                f"- Autoria: {authors_str}\n"
                f"- Tipo de Obra: {work_type}\n"
                f"- Ano de Publicação: {year or 's.d.'}\n"
                f"- Resumo/Anotações existentes: {abstract or 'Nenhum'}\n\n"
                "Diretrizes de elaboração:\n"
                "1. Destaque os problemas teóricos e filosóficos nucleares investigados na obra.\n"
                "2. Evidencie os conceitos-chave, teses centrais e implicações metodológicas.\n"
                "3. Estruture o texto de modo a enriquecer uma malha de conexões conceituais com outros pensadores e fragmentos.\n"
                "4. Não use introduções descartáveis como 'Esta obra aborda...' ou tópicos em bullet points; escreva uma prosa analítica coesa.\n"
            )

            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": prompt}
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.4,
                    "maxOutputTokens": 600,
                },
            }

            candidates = self.get_candidate_models(key)
            if self.preferred_model in candidates:
                models_to_try = [self.preferred_model] + [m for m in candidates if m != self.preferred_model]
            else:
                models_to_try = candidates

            generated_text = ""
            success = False
            last_err = ""

            for model in models_to_try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
                try:
                    with httpx.Client(timeout=30.0) as client:
                        response = client.post(url, json=payload)
                        if response.status_code == 200:
                            data = response.json()
                            candidates_data = data.get("candidates", [])
                            if not candidates_data:
                                continue
                            parts = candidates_data[0].get("content", {}).get("parts", [])
                            if not parts or "text" not in parts[0]:
                                continue
                            generated_text = parts[0]["text"].strip()
                            self.preferred_model = model
                            resource.llm_description = generated_text
                            session.commit()
                            success = True
                            break
                        elif response.status_code == 404:
                            last_err = f"Modelo {model} retornou 404."
                            continue
                        else:
                            try:
                                msg = response.json().get("error", {}).get("message", response.text)
                            except Exception:
                                msg = response.text
                            return False, f"Erro da API Gemini (HTTP {response.status_code}): {msg}"
                except Exception as exc:
                    log_exception("NousAIService.generate_work_description", exc)
                    return False, f"Falha na comunicação: {exc}"

            if not success:
                return False, last_err or "Não foi possível obter resposta dos modelos Gemini."

        # Re-vetoriza a obra na malha de saberes
        try:
            self.knowledge_service.revectorize_work(work_id)
        except Exception as k_err:
            log_exception("NousAIService.revectorize_work", k_err)

        return True, generated_text

    def override_work_description(self, work_id: int, custom_text: Optional[str]) -> bool:
        """Permite ao usuário definir ou remover sua própria descrição personalizada da obra."""
        with SessionLocal() as session:
            resource = session.get(BibliographicResource, work_id)
            if not resource:
                return False
            resource.custom_description = custom_text.strip() if custom_text and custom_text.strip() else None
            session.commit()

        # Re-vetoriza para atualizar embeddings com a síntese preferida pelo usuário
        try:
            self.knowledge_service.revectorize_work(work_id)
        except Exception as k_err:
            log_exception(k_err)

        return True

    def list_works_ai_status(self) -> List[Dict[str, Any]]:
        """Retorna todas as obras com seu status de síntese e metadados."""
        with SessionLocal() as session:
            resources = list(session.query(BibliographicResource).all())
            items = []
            for res in resources:
                sw = res.specific_work
                title = getattr(sw, "title", f"Obra #{res.id}") if sw else f"Obra #{res.id}"
                year = getattr(sw, "display_year", "") if sw else ""

                author_names = []
                if hasattr(res, "authors"):
                    for a in res.authors:
                        parts = [p for p in [getattr(a, "given_names", ""), getattr(a, "last_name", "")] if p]
                        if parts:
                            author_names.append(" ".join(parts))
                authors_str = ", ".join(author_names) if author_names else "Sem autoria informada"

                has_custom = bool(res.custom_description and res.custom_description.strip())
                has_llm = bool(res.llm_description and res.llm_description.strip())

                if has_custom:
                    status_label = "Personalizada"
                    status_color = "#5A6B7C"
                elif has_llm:
                    status_label = "Síntese IA"
                    status_color = "#896200"
                else:
                    status_label = "Pendente"
                    status_color = "#86868f"

                effective = res.effective_description
                snippet = (effective[:120] + "...") if len(effective) > 120 else effective

                items.append({
                    "id": res.id,
                    "title": title,
                    "authors": authors_str,
                    "year": year,
                    "has_custom": has_custom,
                    "has_llm": has_llm,
                    "status_label": status_label,
                    "status_color": status_color,
                    "llm_description": res.llm_description or "",
                    "custom_description": res.custom_description or "",
                    "effective_description": effective,
                    "snippet": snippet,
                })
            return items

    def generate_batch_pending(
        self,
        on_progress: Optional[Callable[[int, int, str], None]] = None,
    ) -> Dict[str, Any]:
        """Gera sínteses por IA em lote para todas as obras pendentes do acervo."""
        works = self.list_works_ai_status()
        pending = [w for w in works if not w["has_llm"] and not w["has_custom"]]
        total = len(pending)

        success = 0
        failed = 0
        errors = []

        for idx, item in enumerate(pending, 1):
            w_id = item["id"]
            w_title = item["title"]
            if on_progress:
                on_progress(idx, total, w_title)

            ok, msg = self.generate_work_description(w_id)
            if ok:
                success += 1
            else:
                failed += 1
                errors.append(f"{w_title}: {msg}")

        return {
            "total": total,
            "success": success,
            "failed": failed,
            "errors": errors,
        }
