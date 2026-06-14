"""Curated LLM models exposed by the app UI."""

from dataclasses import dataclass

from app.core.config import Settings

OPENROUTER_PROVIDER = "openrouter"
OPENAI_PROVIDER = "openai"

PROVIDER_DISPLAY_NAMES = {
    OPENROUTER_PROVIDER: "OpenRouter",
    OPENAI_PROVIDER: "OpenAI",
}

PROVIDER_API_KEY_ENV = {
    OPENROUTER_PROVIDER: "JEAI_OPENROUTER_API_KEY",
    OPENAI_PROVIDER: "JEAI_OPENAI_API_KEY",
}


@dataclass(frozen=True)
class OpenRouterModel:
    id: str
    name: str
    input_cost_per_million: float
    output_cost_per_million: float
    is_free: bool = False
    notes: str = ""


OPENROUTER_MODELS: tuple[OpenRouterModel, ...] = (
    OpenRouterModel(
        id="nex-agi/nex-n2-pro:free",
        name="Nex AGI: Nex-N2-Pro (free)",
        input_cost_per_million=0.0,
        output_cost_per_million=0.0,
        is_free=True,
        notes="Free OpenRouter model with JSON and tool-call support.",
    ),
    OpenRouterModel(
        id="nvidia/nemotron-3-ultra-550b-a55b:free",
        name="NVIDIA: Nemotron 3 Ultra (free)",
        input_cost_per_million=0.0,
        output_cost_per_million=0.0,
        is_free=True,
        notes="Free OpenRouter model; good general fallback for text scenarios.",
    ),
    OpenRouterModel(
        id="nvidia/nemotron-3-super-120b-a12b:free",
        name="NVIDIA: Nemotron 3 Super 120B A12B (free)",
        input_cost_per_million=0.0,
        output_cost_per_million=0.0,
        is_free=True,
        notes="Free OpenRouter model; large NVIDIA Nemotron MoE with strong general reasoning.",
    ),
    OpenRouterModel(
        id="google/gemma-4-26b-a4b-it:free",
        name="Google: Gemma 4 26B A4B IT (free)",
        input_cost_per_million=0.0,
        output_cost_per_million=0.0,
        is_free=True,
        notes="Free OpenRouter model; Google's open Gemma weights, instruction-tuned.",
    ),
    OpenRouterModel(
        id="google/gemma-4-31b-it:free",
        name="Google: Gemma 4 31B IT (free)",
        input_cost_per_million=0.0,
        output_cost_per_million=0.0,
        is_free=True,
        notes="Free OpenRouter model; larger Gemma variant for more complex prompts.",
    ),
    OpenRouterModel(
        id="openai/gpt-oss-120b:free",
        name="OpenAI: gpt-oss-120b (free)",
        input_cost_per_million=0.0,
        output_cost_per_million=0.0,
        is_free=True,
        notes="Free OpenRouter model; OpenAI's open-weight model, large variant.",
    ),
    OpenRouterModel(
        id="openai/gpt-oss-20b:free",
        name="OpenAI: gpt-oss-20b (free)",
        input_cost_per_million=0.0,
        output_cost_per_million=0.0,
        is_free=True,
        notes="Free OpenRouter model; OpenAI's open-weight model, smaller/faster variant.",
    ),
)


@dataclass(frozen=True)
class ReferenceModel:
    provider: str
    id: str
    name: str
    input_cost_per_million: float
    output_cost_per_million: float
    notes: str = ""


@dataclass(frozen=True)
class DirectOpenAIModel:
    id: str
    api_model: str
    name: str
    input_cost_per_million: float
    output_cost_per_million: float
    notes: str = ""


def provider_display_name(provider: str) -> str:
    return PROVIDER_DISPLAY_NAMES[provider]


def provider_api_key_env(provider: str) -> str:
    return PROVIDER_API_KEY_ENV[provider]


def provider_api_key(provider: str, settings: Settings) -> str | None:
    if provider == OPENROUTER_PROVIDER:
        return settings.openrouter_api_key
    if provider == OPENAI_PROVIDER:
        return settings.openai_api_key
    raise ValueError(f"Unknown LLM provider: {provider}")


def is_provider_configured(provider: str, settings: Settings) -> bool:
    return bool(provider_api_key(provider, settings))


def provider_disabled_note(provider: str) -> str:
    return f"Set {provider_api_key_env(provider)} to enable."


def selectable_notes(notes: str, provider: str, settings: Settings) -> str:
    if is_provider_configured(provider, settings):
        return notes
    return f"{notes} {provider_disabled_note(provider)}"


DIRECT_OPENAI_MODELS: tuple[DirectOpenAIModel, ...] = (
    DirectOpenAIModel(
        id="openai:gpt-5.5",
        api_model="gpt-5.5",
        name="GPT-5.5",
        input_cost_per_million=5.00,
        output_cost_per_million=30.00,
        notes="Direct OpenAI API model. Requires JEAI_OPENAI_API_KEY.",
    ),
    DirectOpenAIModel(
        id="openai:gpt-5.4",
        api_model="gpt-5.4",
        name="GPT-5.4",
        input_cost_per_million=2.50,
        output_cost_per_million=15.00,
        notes="Direct OpenAI API model. Requires JEAI_OPENAI_API_KEY.",
    ),
    DirectOpenAIModel(
        id="openai:gpt-5.4-mini",
        api_model="gpt-5.4-mini",
        name="GPT-5.4 mini",
        input_cost_per_million=0.75,
        output_cost_per_million=4.50,
        notes="Direct OpenAI API model. Requires JEAI_OPENAI_API_KEY.",
    ),
    DirectOpenAIModel(
        id="openai:gpt-5.4-nano",
        api_model="gpt-5.4-nano",
        name="GPT-5.4 nano",
        input_cost_per_million=0.20,
        output_cost_per_million=1.25,
        notes="Direct OpenAI API model. Requires JEAI_OPENAI_API_KEY.",
    ),
    DirectOpenAIModel(
        id="openai:gpt-4.1-mini",
        api_model="gpt-4.1-mini",
        name="GPT-4.1 mini",
        input_cost_per_million=0.40,
        output_cost_per_million=1.60,
        notes="Direct OpenAI API model. Requires JEAI_OPENAI_API_KEY.",
    ),
    DirectOpenAIModel(
        id="openai:gpt-4.1",
        api_model="gpt-4.1",
        name="GPT-4.1",
        input_cost_per_million=2.00,
        output_cost_per_million=8.00,
        notes="Direct OpenAI API model. Requires JEAI_OPENAI_API_KEY.",
    ),
    DirectOpenAIModel(
        id="openai:gpt-4o-mini",
        api_model="gpt-4o-mini",
        name="GPT-4o mini",
        input_cost_per_million=0.15,
        output_cost_per_million=0.60,
        notes="Direct OpenAI API model. Requires JEAI_OPENAI_API_KEY.",
    ),
    DirectOpenAIModel(
        id="openai:gpt-4o",
        api_model="gpt-4o",
        name="GPT-4o",
        input_cost_per_million=2.50,
        output_cost_per_million=10.00,
        notes="Direct OpenAI API model. Requires JEAI_OPENAI_API_KEY.",
    ),
)


# List prices for popular commercial models, shown in the pricing modal for
# cost comparison only. These are not routed through OpenRouter and are not
# selectable as a run's model.
COMMERCIAL_REFERENCE_MODELS: tuple[ReferenceModel, ...] = (
    ReferenceModel(
        provider="Anthropic",
        id="anthropic/claude-opus-4",
        name="Claude Opus 4",
        input_cost_per_million=15.00,
        output_cost_per_million=75.00,
    ),
    ReferenceModel(
        provider="Anthropic",
        id="anthropic/claude-sonnet-4",
        name="Claude Sonnet 4",
        input_cost_per_million=3.00,
        output_cost_per_million=15.00,
    ),
    ReferenceModel(
        provider="Anthropic",
        id="anthropic/claude-haiku-4",
        name="Claude Haiku 4",
        input_cost_per_million=0.80,
        output_cost_per_million=4.00,
    ),
    ReferenceModel(
        provider="Google",
        id="google/gemini-2.5-pro",
        name="Gemini 2.5 Pro",
        input_cost_per_million=1.25,
        output_cost_per_million=10.00,
    ),
    ReferenceModel(
        provider="Google",
        id="google/gemini-2.5-flash",
        name="Gemini 2.5 Flash",
        input_cost_per_million=0.30,
        output_cost_per_million=2.50,
    ),
    ReferenceModel(
        provider="Google",
        id="google/gemini-2.0-flash",
        name="Gemini 2.0 Flash",
        input_cost_per_million=0.10,
        output_cost_per_million=0.40,
    ),
)


def find_openrouter_model(model_id: str) -> OpenRouterModel | None:
    return next((model for model in OPENROUTER_MODELS if model.id == model_id), None)


def find_direct_openai_model(model_id: str) -> DirectOpenAIModel | None:
    return next((model for model in DIRECT_OPENAI_MODELS if model.id == model_id), None)


def model_provider(model_id: str, settings: Settings) -> str | None:
    if find_openrouter_model(model_id) is not None or model_id == settings.llm_model:
        return OPENROUTER_PROVIDER
    if (
        find_direct_openai_model(model_id) is not None
        or model_id == f"openai:{settings.openai_model}"
    ):
        return OPENAI_PROVIDER
    return None


def is_model_provider_configured(model_id: str, settings: Settings) -> bool:
    provider = model_provider(model_id, settings)
    return provider is not None and is_provider_configured(provider, settings)


def model_costs(model_id: str, default_input: float, default_output: float) -> tuple[float, float]:
    openrouter_model = find_openrouter_model(model_id)
    if openrouter_model is not None:
        return openrouter_model.input_cost_per_million, openrouter_model.output_cost_per_million
    openai_model = find_direct_openai_model(model_id)
    if openai_model is not None:
        return openai_model.input_cost_per_million, openai_model.output_cost_per_million
    return default_input, default_output


def has_known_pricing(model_id: str, settings: Settings) -> bool:
    """True if `model_id` has explicit pricing data: either a curated OpenRouter
    model, or the operator-configured default model (priced via
    JEAI_OPENROUTER_*_COST_PER_MILLION). Direct OpenAI rows use the
    `openai:<model>` namespace."""
    return (
        find_openrouter_model(model_id) is not None
        or find_direct_openai_model(model_id) is not None
        or model_id == settings.llm_model
        or model_id == f"openai:{settings.openai_model}"
    )
