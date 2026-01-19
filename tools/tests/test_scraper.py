"""Testes para o scraper e-SAJ."""

import asyncio
import json
from pathlib import Path
import sys

# Adicionar o diretório tools ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from esaj_scraper import EsajScraper

# Números de processo para teste
TEST_PROCESSOS = [
    "1002589-56.2018.8.26.0053",
    "1061517-43.2024.8.26.0100",
    "1090340-03.2019.8.26.0100",
]


async def test_single_process():
    """Testa extração de um único processo."""
    print("=" * 80)
    print("TESTE 1: Extração de processo único")
    print("=" * 80)
    
    scraper = EsajScraper()
    numero = TEST_PROCESSOS[0]
    
    print(f"\nTestando com número: {numero}\n")
    
    processo = await scraper.scrape(numero)
    resultado = processo.to_json_dict()
    
    print(f"Status: {resultado['metadata']['status']}")
    print(f"Número do processo: {resultado['informacoes_principais']['numero_processo']}")
    print(f"Classe: {resultado['informacoes_principais'].get('classe', 'N/A')}")
    print(f"Partes encontradas: {len(resultado['partes'])}")
    print(f"Movimentações encontradas: {len(resultado['movimentacoes'])}")
    print(f"Petições encontradas: {len(resultado['peticoes'])}")
    print(f"Incidentes encontrados: {len(resultado['incidentes'])}")
    
    if resultado['metadata']['status'] == 'error':
        print(f"\nErro: {resultado['metadata'].get('erro', 'Erro desconhecido')}")
    
    # Salvar resultado em arquivo
    output_file = Path(__file__).parent / f"test_result_{numero.replace('.', '_').replace('-', '_')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(resultado, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\nResultado salvo em: {output_file}")
    print("\n")


async def test_multiple_processes():
    """Testa extração de múltiplos processos."""
    print("=" * 80)
    print("TESTE 2: Extração de múltiplos processos")
    print("=" * 80)
    
    scraper = EsajScraper()
    
    print(f"\nTestando com {len(TEST_PROCESSOS)} processos:\n")
    for num in TEST_PROCESSOS:
        print(f"  - {num}")
    print()
    
    processos = await scraper.scrape_multiple(TEST_PROCESSOS)
    
    print("\nResultados:\n")
    for i, processo in enumerate(processos):
        resultado = processo.to_json_dict()
        print(f"Processo {i+1}: {TEST_PROCESSOS[i]}")
        print(f"  Status: {resultado['metadata']['status']}")
        print(f"  Número: {resultado['informacoes_principais']['numero_processo']}")
        print(f"  Partes: {len(resultado['partes'])}")
        print(f"  Movimentações: {len(resultado['movimentacoes'])}")
        if resultado['metadata']['status'] == 'error':
            print(f"  Erro: {resultado['metadata'].get('erro', 'N/A')}")
        print()
    
    # Salvar resultados em arquivo
    output_file = Path(__file__).parent / "test_results_multiple.json"
    resultados = [p.to_json_dict() for p in processos]
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(resultados, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"Resultados salvos em: {output_file}")
    print("\n")


async def test_all_processes_individually():
    """Testa cada processo individualmente e salva resultados."""
    print("=" * 80)
    print("TESTE 3: Teste individual de cada processo")
    print("=" * 80)
    
    scraper = EsajScraper()
    
    for i, numero in enumerate(TEST_PROCESSOS, 1):
        print(f"\n{'=' * 80}")
        print(f"Processo {i}/{len(TEST_PROCESSOS)}: {numero}")
        print('=' * 80)
        
        processo = await scraper.scrape(numero)
        resultado = processo.to_json_dict()
        
        print(f"\nStatus: {resultado['metadata']['status']}")
        
        if resultado['metadata']['status'] == 'success':
            info = resultado['informacoes_principais']
            print(f"Número: {info['numero_processo']}")
            print(f"Classe: {info.get('classe', 'N/A')}")
            print(f"Assunto: {info.get('assunto', 'N/A')}")
            print(f"Foro: {info.get('foro', 'N/A')}")
            print(f"Vara: {info.get('vara', 'N/A')}")
            print(f"Juiz: {info.get('juiz', 'N/A')}")
            print(f"Partes: {len(resultado['partes'])}")
            if resultado['partes']:
                for parte in resultado['partes']:
                    print(f"  - {parte['tipo_participacao']}: {parte['nome']}")
                    for adv in parte['advogados']:
                        print(f"    Advogado: {adv['nome']}")
                        if adv.get('oab'):
                            print(f"      OAB: {adv['oab']}")
            print(f"Movimentações: {len(resultado['movimentacoes'])}")
            print(f"Petições: {len(resultado['peticoes'])}")
            print(f"Incidentes: {len(resultado['incidentes'])}")
        else:
            print(f"Erro: {resultado['metadata'].get('erro', 'Erro desconhecido')}")
        
        # Salvar resultado individual
        output_file = Path(__file__).parent / f"test_result_{i}_{numero.replace('.', '_').replace('-', '_')}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(resultado, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"\nResultado salvo em: {output_file}")
    
    print("\n" + "=" * 80)
    print("Todos os testes concluídos!")
    print("=" * 80 + "\n")


async def main():
    """Executa todos os testes."""
    print("\n")
    print("=" * 80)
    print("TESTES DO SCRAPER E-SAJ")
    print("=" * 80)
    print("\n")
    
    try:
        # Executar teste individual
        await test_single_process()
        
        # Executar teste com múltiplos processos
        await test_multiple_processes()
        
        # Executar todos os processos individualmente
        await test_all_processes_individually()
        
    except KeyboardInterrupt:
        print("\n\nTestes interrompidos pelo usuário.")
    except Exception as e:
        print(f"\n\nErro durante os testes: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())






