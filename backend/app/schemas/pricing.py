from pydantic import BaseModel


class ModelPricing(BaseModel):
    provider: str
    model: str
    display_name: str = ""
    input_cost_per_million_tokens_usd: float | None
    output_cost_per_million_tokens_usd: float | None
    active: bool = False
    selectable: bool = True
    is_free: bool = False
    notes: str = ""


class PricingResult(BaseModel):
    currency: str = "USD"
    unit: str = "per_1m_tokens"
    models: list[ModelPricing]
