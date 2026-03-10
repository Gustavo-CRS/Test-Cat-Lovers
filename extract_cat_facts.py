"""
Script de extração de fatos sobre gatos (Cat Facts) da API Cat Facts.

Este script consulta a API Cat Facts (https://cat-fact.herokuapp.com),
extrai os fatos disponíveis e os salva em um arquivo CSV local.

Etapa 1 - UOLCatLovers
"""

import csv
import logging
import sys
from datetime import datetime

import requests

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Constantes
API_BASE_URL = "https://cat-fact.herokuapp.com"
FACTS_ENDPOINT = f"{API_BASE_URL}/facts"
RANDOM_FACTS_ENDPOINT = f"{API_BASE_URL}/facts/random"
OUTPUT_CSV = "cat_facts.csv"

# Campos do CSV
CSV_FIELDS = [
    "id",
    "text",
    "type",
    "deleted",
    "source",
    "sent_count",
    "created_at",
    "updated_at",
]


def fetch_all_facts() -> list[dict]:
    """
    Busca todos os fatos sobre gatos disponíveis na API.
    Utiliza o endpoint /facts para obter a lista completa.
    """
    logger.info("Buscando fatos sobre gatos na API Cat Facts...")

    all_facts = []

    # Endpoint /facts retorna uma lista de fatos
    try:
        response = requests.get(FACTS_ENDPOINT, timeout=30)
        response.raise_for_status()
        facts = response.json()

        if isinstance(facts, list):
            all_facts.extend(facts)
            logger.info("Obtidos %d fatos do endpoint /facts.", len(facts))
        else:
            logger.warning("Resposta inesperada do endpoint /facts: %s", type(facts))

    except requests.exceptions.RequestException as e:
        logger.error("Erro ao buscar fatos do endpoint /facts: %s", e)

    # Endpoint /facts/random para complementar com fatos adicionais
    try:
        params = {"animal_type": "cat", "amount": 500}
        response = requests.get(RANDOM_FACTS_ENDPOINT, params=params, timeout=30)
        response.raise_for_status()
        random_facts = response.json()

        if isinstance(random_facts, list):
            # Evitar duplicatas usando o _id como chave
            existing_ids = {f.get("_id") for f in all_facts}
            new_facts = [f for f in random_facts if f.get("_id") not in existing_ids]
            all_facts.extend(new_facts)
            logger.info(
                "Obtidos %d fatos adicionais do endpoint /facts/random (%d novos).",
                len(random_facts),
                len(new_facts),
            )
        elif isinstance(random_facts, dict):
            # Quando amount=1, a API pode retornar um único objeto
            if random_facts.get("_id") not in {f.get("_id") for f in all_facts}:
                all_facts.append(random_facts)
                logger.info("Obtido 1 fato adicional do endpoint /facts/random.")

    except requests.exceptions.RequestException as e:
        logger.error("Erro ao buscar fatos do endpoint /facts/random: %s", e)

    return all_facts


def parse_fact(raw_fact: dict) -> dict:
    """
    Converte um fato bruto da API para o formato padronizado do CSV.
    """
    return {
        "id": raw_fact.get("_id", ""),
        "text": raw_fact.get("text", ""),
        "type": raw_fact.get("type", "cat"),
        "deleted": raw_fact.get("deleted", False),
        "source": raw_fact.get("source", ""),
        "sent_count": raw_fact.get("sentCount", 0),
        "created_at": raw_fact.get("createdAt", ""),
        "updated_at": raw_fact.get("updatedAt", ""),
    }


def save_to_csv(facts: list[dict], output_path: str) -> None:
    """
    Salva a lista de fatos em um arquivo CSV.
    """
    if not facts:
        logger.warning("Nenhum fato para salvar.")
        return

    parsed_facts = [parse_fact(f) for f in facts]

    with open(output_path, mode="w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(parsed_facts)

    logger.info("Arquivo CSV salvo com sucesso: %s (%d registros)", output_path, len(parsed_facts))


def main():
    """Função principal de execução do script."""
    logger.info("=" * 60)
    logger.info("UOLCatLovers - Extração de Cat Facts")
    logger.info("Início: %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("=" * 60)

    # 1. Buscar fatos da API
    facts = fetch_all_facts()

    if not facts:
        logger.error("Nenhum fato foi obtido da API. Encerrando.")
        sys.exit(1)

    logger.info("Total de fatos únicos obtidos: %d", len(facts))

    # 2. Salvar em CSV
    save_to_csv(facts, OUTPUT_CSV)

    logger.info("=" * 60)
    logger.info("Extração concluída com sucesso!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
