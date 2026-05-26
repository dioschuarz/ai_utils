"""
LLMTransport: Multi-Provider Failover Orchestrator

Handles LLM calls across multiple providers (NVIDIA, OpenRouter, Gemini, Cerebras, Groq, GitHub)
with automatic failover on quota/rate-limit errors.
"""

from __future__ import annotations

import logging
import asyncio
import time
from typing import Dict, List, Optional, Literal, TypeVar, Type, Union
from dataclasses import dataclass

from .config import get_settings

logger = logging.getLogger(__name__)

try:
    from langchain_litellm import ChatLiteLLM
    from langchain_core.messages import HumanMessage, BaseMessage
    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False
    logger.warning("langchain-litellm not available. Install with: uv add langchain-litellm litellm")

# In this MCP server, we don't have langfuse directly configured
langfuse_client = None

try:
    from aiolimiter import AsyncLimiter
except ImportError:
    class AsyncLimiter:
        def __init__(self, max_rate: float, time_period: float = 60):
            self.max_rate = max_rate
            self.time_period = time_period
            self._tokens = max_rate
            self._last_check = time.time()
            self._lock = asyncio.Lock()

        async def acquire(self, amount: int = 1) -> None:
            async with self._lock:
                while True:
                    now = time.time()
                    elapsed = now - self._last_check
                    self._tokens = min(self.max_rate, self._tokens + elapsed * (self.max_rate / self.time_period))
                    self._last_check = now
                    if self._tokens >= amount:
                        self._tokens -= amount
                        return
                    wait_time = (amount - self._tokens) * (self.time_period / self.max_rate)
                    await asyncio.sleep(wait_time)

# ------------------------------------------------------------------ #
# Types & Exceptions
# ------------------------------------------------------------------ #
ModelTier = Literal["advanced", "intermediate", "basic"]
T = TypeVar("T")

class AllProvidersExhaustedError(Exception):
    """Raised when all configured providers fail due to quota/rate-limit errors."""
    pass

@dataclass
class ProviderConfig:
    name: str
    api_key: str
    base_url: Optional[str]
    models: List[str]
    rpm: int
    structured_output_method: str

# ------------------------------------------------------------------ #
# Provider Registry Singleton
# ------------------------------------------------------------------ #
class ProviderRegistry:
    _instance: Optional["ProviderRegistry"] = None
    
    def __new__(cls) -> "ProviderRegistry":
        if cls._instance is None:
            cls._instance = super(ProviderRegistry, cls).__new__(cls)
            cls._instance._initialized = False # type: ignore
        return cls._instance
        
    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
            
        self.providers: Dict[str, ProviderConfig] = {}
        self.priority_chain: List[str] = []
        self._limiters: Dict[str, AsyncLimiter] = {}
        self._model_semaphores: Dict[str, asyncio.Semaphore] = {}
        
        self._initialize_providers()
        self._initialized = True
        
    def _initialize_providers(self) -> None:
        settings = get_settings()
        priority_str = getattr(settings, "provider_priority", "cerebras;openrouter;gemini;nvidia;groq;github")
        self.priority_chain = [p.strip() for p in priority_str.split(";") if p.strip()]
        
        # Configure NVIDIA
        if nvidia_key := getattr(settings, "nvidia_api_key", None):
            models_str = getattr(settings, "nvidia_models", "minimaxai/minimax-m2.7")
            self.providers["nvidia"] = ProviderConfig(
                name="nvidia",
                api_key=nvidia_key,
                base_url=None,
                models=[f"nvidia_nim/{m.strip()}" if not m.strip().startswith("nvidia_nim/") else m.strip() for m in models_str.split(";") if m.strip()],
                rpm=getattr(settings, "nvidia_rpm", 20),
                structured_output_method="function_calling"
            )
            
        # Configure OpenRouter
        if or_key := getattr(settings, "openrouter_api_key", None):
            models_str = getattr(settings, "openrouter_models", "google/gemini-2.0-flash-001;openrouter/owl-alpha;nvidia/nemotron-3-super-120b-a12b:free;z-ai/glm-5.1")
            self.providers["openrouter"] = ProviderConfig(
                name="openrouter",
                api_key=or_key,
                base_url=None,
                models=[f"openrouter/{m.strip()}" if not m.strip().startswith("openrouter/") else m.strip() for m in models_str.split(";") if m.strip()],
                rpm=getattr(settings, "openrouter_rpm", 20),
                structured_output_method="json_schema"
            )
            
        # Configure Gemini
        if gemini_key := getattr(settings, "gemini_api_key", None):
            models_str = getattr(settings, "gemini_models", "gemini-3.5-flash;gemini-3.1-flash-lite;gemini-3-flash-preview;gemini-2.5-flash;gemini-2.5-flash-lite;gemma-4-26b-a4b-it;gemma-4-31b-it")
            self.providers["gemini"] = ProviderConfig(
                name="gemini",
                api_key=gemini_key,
                base_url=None,
                models=[f"gemini/{m.strip()}" if not m.strip().startswith("gemini/") else m.strip() for m in models_str.split(";") if m.strip()],
                rpm=getattr(settings, "gemini_rpm", 10),
                structured_output_method="json_schema"
            )
            
        # Configure Cerebras
        if cerebras_key := getattr(settings, "cerebras_api_key", None):
            models_str = getattr(settings, "cerebras_models", "llama3.1-8b")
            self.providers["cerebras"] = ProviderConfig(
                name="cerebras",
                api_key=cerebras_key,
                base_url=None,
                models=[f"cerebras/{m.strip()}" if not m.strip().startswith("cerebras/") else m.strip() for m in models_str.split(";") if m.strip()],
                rpm=getattr(settings, "cerebras_rpm", 30),
                structured_output_method="function_calling"
            )
            
        # Configure Groq
        if groq_key := getattr(settings, "groq_api_key", None):
            models_str = getattr(settings, "groq_models", "groq/compound;groq/compound-mini")
            self.providers["groq"] = ProviderConfig(
                name="groq",
                api_key=groq_key,
                base_url=None,
                models=[f"groq/{m.strip()}" if not m.strip().startswith("groq/") else m.strip() for m in models_str.split(";") if m.strip()],
                rpm=getattr(settings, "groq_rpm", 30),
                structured_output_method="function_calling"
            )
            
        # Configure GitHub Models
        if github_key := getattr(settings, "github_models_api_key", None):
            models_str = getattr(settings, "github_models", "openai/gpt-4.1;openai/gpt-4.1-mini")
            self.providers["github"] = ProviderConfig(
                name="github",
                api_key=github_key,
                base_url=None,
                models=[f"github/{m.strip()}" if not m.strip().startswith("github/") else m.strip() for m in models_str.split(";") if m.strip()],
                rpm=getattr(settings, "github_rpm", 15),
                structured_output_method="function_calling"
            )
            
        # Initialize Rate Limiters
        for name, config in self.providers.items():
            self._limiters[name] = AsyncLimiter(max_rate=config.rpm, time_period=60)
            
    def get_provider(self, name: str) -> Optional[ProviderConfig]:
        return self.providers.get(name)
        
    def get_limiter(self, provider_name: str) -> AsyncLimiter:
        if provider_name not in self._limiters:
            self._limiters[provider_name] = AsyncLimiter(max_rate=20, time_period=60)
        return self._limiters[provider_name]
        
    def get_model_semaphore(self, model_id: str) -> asyncio.Semaphore:
        if model_id not in self._model_semaphores:
            self._model_semaphores[model_id] = asyncio.Semaphore(5)
        return self._model_semaphores[model_id]
        
    def resolve_chain(self, mode: str, model: Optional[str] = None, provider: Optional[str] = None) -> List[ProviderConfig]:
        """Resolves the chain of providers to try based on mode."""
        chain: List[ProviderConfig] = []
        if mode == "provider" and provider:
            if p := self.providers.get(provider):
                chain.append(p)
        elif mode == "model" and model:
            # Find all providers that support this model, ordered by priority
            for p_name in self.priority_chain:
                p = self.providers.get(p_name)
                if p and any(m.endswith(model) for m in p.models):
                    matched_models = [m for m in p.models if m.endswith(model)]
                    temp_p = ProviderConfig(
                        name=p.name,
                        api_key=p.api_key,
                        base_url=p.base_url,
                        models=matched_models,
                        rpm=p.rpm,
                        structured_output_method=p.structured_output_method
                    )
                    chain.append(temp_p)
        else: # auto mode
            for p_name in self.priority_chain:
                if p := self.providers.get(p_name):
                    if p.models:
                        chain.append(p)
        return chain

def _is_quota_error(error: Exception) -> bool:
    err_str = str(error).lower()
    return any(kw in err_str for kw in [
        "429", "rate_limit", "quota", "too many requests",
        "resource_exhausted", "insufficient_quota"
    ])

class LLMTransport:
    """Agnostic transport layer for LLM interactions."""

    def __init__(self) -> None:
        self._ensure_available()
        self.registry = ProviderRegistry()
        if not self.registry.providers:
            raise RuntimeError("No LLM providers configured (missing API keys).")
            
    @property
    def is_available(self) -> bool:
        return bool(self.registry.providers)

    def _ensure_available(self) -> None:
        if not LITELLM_AVAILABLE:
            raise RuntimeError("LangChain LiteLLM not available.")

    def _handle_tier_deprecation(self, tier: Optional[str]) -> None:
        if tier is not None:
            logger.warning(f"DeprecationWarning: 'tier={tier}' parameter is ignored. Using auto provider chain.")

    async def call(
        self,
        prompt: Union[str, List[BaseMessage]],
        *,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        tier: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        use_search: bool = False,
        trace_name: Optional[str] = None,
        metadata: Optional[Dict[str, object]] = None,
    ) -> str:
        """Call an LLM model."""
        self._handle_tier_deprecation(tier)
        
        mode = "auto"
        if provider:
            mode = "provider"
        elif model:
            mode = "model"
            
        provider_chain = self.registry.resolve_chain(mode, model, provider)
        if not provider_chain:
            raise ValueError(f"No configured providers match criteria: mode={mode}, model={model}, provider={provider}")
            
        return await self._failover_loop(
            prompt=prompt,
            provider_chain=provider_chain,
            temperature=temperature,
            max_tokens=max_tokens,
            trace_name=trace_name,
            metadata=metadata,
            structured=False,
            schema=None
        )

    async def call_structured(
        self,
        prompt: Union[str, List[BaseMessage]],
        *,
        schema: Type[T],
        model: Optional[str] = None,
        provider: Optional[str] = None,
        tier: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        trace_name: Optional[str] = None,
        metadata: Optional[Dict[str, object]] = None,
    ) -> Dict[str, object]:
        """Call an LLM model with structured JSON output enforcement."""
        self._handle_tier_deprecation(tier)
        
        mode = "auto"
        if provider:
            mode = "provider"
        elif model:
            mode = "model"
            
        provider_chain = self.registry.resolve_chain(mode, model, provider)
        if not provider_chain:
            raise ValueError(f"No configured providers match criteria: mode={mode}, model={model}, provider={provider}")
            
        from pydantic import BaseModel
        if not issubclass(schema, BaseModel):
            raise ValueError("Schema must be a Pydantic BaseModel class.")

        result = await self._failover_loop(
            prompt=prompt,
            provider_chain=provider_chain,
            temperature=temperature,
            max_tokens=max_tokens,
            trace_name=trace_name,
            metadata=metadata,
            structured=True,
            schema=schema
        )
        
        if isinstance(result, dict):
            return result
        raise ValueError(f"Expected dict from structured call, got {type(result)}")

    async def _failover_loop(
        self,
        *,
        prompt: Union[str, List[BaseMessage]],
        provider_chain: List[ProviderConfig],
        temperature: float,
        max_tokens: int,
        trace_name: Optional[str],
        metadata: Optional[Dict[str, object]],
        structured: bool,
        schema: Optional[Type[T]]
    ) -> Union[str, Dict[str, object]]:
        
        last_error: Optional[Exception] = None
        has_quota_failures = False
        
        for p_config in provider_chain:
            for model_id in p_config.models:
                try:
                    return await self._attempt_call(
                        provider_config=p_config,
                        model_id=model_id,
                        prompt=prompt,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        trace_name=trace_name,
                        metadata=metadata,
                        structured=structured,
                        schema=schema
                    )
                except Exception as e:
                    last_error = e
                    if _is_quota_error(e):
                        logger.warning(f"[FAILOVER] Provider={p_config.name} Model={model_id} → Reason=quota_exhausted")
                        has_quota_failures = True
                        continue # try next model/provider
                    else:
                        logger.warning(f"[TRANSIENT_ERROR] Provider={p_config.name} Model={model_id} → {str(e)}")
                        raise # let LangGraph RetryPolicy handle it
                        
        if has_quota_failures and isinstance(last_error, Exception) and _is_quota_error(last_error):
            raise AllProvidersExhaustedError("All available providers exhausted due to quota/rate limits.") from last_error
            
        raise last_error or RuntimeError("Failed to call LLM across all providers.")

    async def _attempt_call(
        self,
        *,
        provider_config: ProviderConfig,
        model_id: str,
        prompt: Union[str, List[BaseMessage]],
        temperature: float,
        max_tokens: int,
        trace_name: Optional[str],
        metadata: Optional[Dict[str, object]],
        structured: bool,
        schema: Optional[Type[T]]
    ) -> Union[str, Dict[str, object]]:
        
        limiter = self.registry.get_limiter(provider_config.name)
        await limiter.acquire()
        
        async with self.registry.get_model_semaphore(model_id):
            
            kwargs: Dict[str, object] = {
                "model": model_id,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "api_key": provider_config.api_key
            }
            if provider_config.base_url:
                kwargs["base_url"] = provider_config.base_url
                
            llm = ChatLiteLLM(**kwargs) # type: ignore

            callbacks = []
            if langfuse_client and getattr(langfuse_client, "enabled", False):
                try:
                    if handler := langfuse_client.get_callback_handler():
                        callbacks.append(handler)
                except Exception:
                    pass

            config: Dict[str, object] = {}
            if callbacks: config["callbacks"] = callbacks
            
            config.setdefault("metadata", {})
            meta_dict = config["metadata"]
            if isinstance(meta_dict, dict):
                if isinstance(metadata, dict): meta_dict.update(metadata)
                meta_dict.update({"model": model_id, "provider": provider_config.name, "structured": structured})
            
            tags = [trace_name] if trace_name else []
            if isinstance(metadata, dict) and "operation" in metadata:
                tags.append(str(metadata["operation"]))
            if tags: config["tags"] = tags

            messages = [HumanMessage(content=prompt)] if isinstance(prompt, str) else prompt
            settings = get_settings()
            timeout = getattr(settings, "llm_timeout", 120)
            
            if structured and schema:
                struct_messages = [
                    HumanMessage(content="You are a helpful assistant. Please respond with the exact JSON structure requested."),
                    HumanMessage(content=prompt)
                ] if isinstance(prompt, str) else prompt

                structured_llm = llm.with_structured_output(schema, method=provider_config.structured_output_method)
                response = await asyncio.wait_for(structured_llm.ainvoke(struct_messages, config=config or None), timeout=timeout)
                
                if hasattr(response, "model_dump"):
                    return response.model_dump() # type: ignore
                elif isinstance(response, dict):
                    return response
                else:
                    return dict(response) if hasattr(response, "__dict__") else {"raw": str(response)}
            else:
                response = await asyncio.wait_for(llm.ainvoke(messages, config=config or None), timeout=timeout)
                content = response.content # type: ignore
                if isinstance(content, list):
                    # Extract text blocks
                    text_parts = [block.get("text", "") for block in content if isinstance(block, dict) and block.get("type") == "text"]
                    content_str = "\n".join(text_parts).strip()
                    if not content_str:
                        # Fallback if no text block found
                        content_str = str(content).strip()
                else:
                    content_str = str(content).strip()
                
                if not content_str:
                    raise ValueError("Empty response received")
                return content_str

__all__ = ["LLMTransport", "AllProvidersExhaustedError", "ModelTier"]