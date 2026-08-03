"""
Loads business config and builds a context string the LLM uses
to answer customer questions accurately (no hallucinated hours/prices).
"""
import yaml
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_context(config: dict) -> str:
    """Flatten config into plain text the LLM can ground its answers on."""
    biz = config["business"]
    lines = [
        f"Business name: {biz['name']}",
        f"Hours: {biz['hours']}",
        f"Location: {biz['location']}",
        f"Contact number: {biz['contact_number']}",
        f"Services offered: {', '.join(biz['services'])}",
        "",
        "Frequently asked questions:",
    ]
    for faq in config.get("faqs", []):
        lines.append(f"Q: {faq['question']}\nA: {faq['answer']}")
    return "\n".join(lines)


if __name__ == "__main__":
    cfg = load_config()
    print(build_context(cfg))
