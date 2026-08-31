from typing import List, Optional, Tuple

from langchain_core.messages import HumanMessage, SystemMessage

from agents.compound_mapper.academic_index import ACADEMIC_INDEX
from agents.compound_mapper.compound_mapper_prompt import (
    SYSTEM_PROMPT_COMPOUND_MAPPER,
    human_prompt_compound_mapper,
)
from agents.compound_mapper.matcher import match_component, split_components
from agents.compound_mapper.unmapped_log import log_unmapped
from llm.client import fallback_client, FALLBACK_ORDER
from models.compound_mapper import CompoundMapperModel


def _scientific_names_to_map(state) -> List[Tuple[str, Optional[str]]]:
    """Return (scientific_name, source_product) pairs to map: the extractor's direct
    scientific_name on the direct path, or the deduplicated scientific_name values off
    the matched commercial rows on the retrieval path. A scientific_name repeated
    across several rows is mapped once, attributed to the first row it appeared on."""
    direct = state.get("scientific_name")
    if direct:
        return [(direct, None)]

    pairs: List[Tuple[str, Optional[str]]] = []
    seen = set()
    for row in state.get("context") or []:
        scientific_name = row.get("scientific_name")
        if not scientific_name or scientific_name in seen:
            continue
        seen.add(scientific_name)
        pairs.append((scientific_name, row.get("commercial_name_en")))

    return pairs


def compound_mapper(state):
    scientific_name_sources = _scientific_names_to_map(state)
    if not scientific_name_sources:
        return {"compound_mappings": []}

    slots: List[dict] = []
    pending_indices: List[int] = []

    for scientific_name, source_product in scientific_name_sources:
        for component_info in split_components(scientific_name):
            outcome = match_component(component_info)
            slot = {"component": outcome["component"], "source_product": source_product}
            if outcome["matched"] is None:
                slot["candidates"] = outcome["candidates"]
                pending_indices.append(len(slots))
            else:
                slot["generic_name"] = outcome["generic_name"]
                slot["matched"] = outcome["matched"]
            slots.append(slot)

    if pending_indices:
        pending_slots = [slots[i] for i in pending_indices]

        message = [
            SystemMessage(content=SYSTEM_PROMPT_COMPOUND_MAPPER),
            HumanMessage(content=human_prompt_compound_mapper(pending_slots)),
        ]
        raw_result = fallback_client.constrained_invoke(
            message=message,
            fallback_order=FALLBACK_ORDER,
            constraine_model=CompoundMapperModel,
        )
        validated = CompoundMapperModel.model_validate(
            raw_result, context={"valid_generic_names": ACADEMIC_INDEX.valid_generic_names}
        )
        by_component = {mapping.component: mapping for mapping in validated.mappings}

        for index in pending_indices:
            slot = slots[index]
            mapping = by_component.get(slot["component"])
            if mapping is None:
                slot["generic_name"] = None
                slot["matched"] = False
            else:
                slot["generic_name"] = mapping.generic_name
                slot["matched"] = mapping.matched

    mappings = []
    for slot in slots:
        matched = bool(slot.get("matched"))
        if not matched:
            log_unmapped(slot["component"], slot.get("source_product"))
        mappings.append(
            {
                "component": slot["component"],
                "generic_name": slot.get("generic_name"),
                "matched": matched,
                "source_product": slot.get("source_product"),
            }
        )

    return {"compound_mappings": mappings}
