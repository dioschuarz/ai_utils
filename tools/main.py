"""Script principal para executar o scraper e-SAJ."""

import asyncio
import sys
from esaj_scraper import EsajScraper
import json


async def main():
    """Função principal."""
    if len(sys.argv) < 2:
        print("Uso: python main.py <numero_processo> [numero_processo2] ...")
        print("\nExemplos:")
        print("  python main.py 1002589-56.2018.8.26.0053")
        print("  python main.py 1002589-56.2018.8.26.0053 1061517-43.2024.8.26.0100 1090340-03.2019.8.26.0100")
        sys.exit(1)
    
    numeros_processos = sys.argv[1:]
    scraper = EsajScraper()
    
    print(f"Extraindo dados de {len(numeros_processos)} processo(s)...\n")
    
    if len(numeros_processos) == 1:
        processo = await scraper.scrape(numeros_processos[0])
        resultado = processo.to_json_dict()
        print(json.dumps(resultado, indent=2, ensure_ascii=False, default=str))
    else:
        processos = await scraper.scrape_multiple(numeros_processos)
        resultados = [p.to_json_dict() for p in processos]
        print(json.dumps(resultados, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    asyncio.run(main())



