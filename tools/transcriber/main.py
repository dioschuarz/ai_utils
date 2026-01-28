# %%

#
# Configurações Iniciais
#
ARQUIVO_DE_AUDIO = "Mentoria 1 - 20260126.m4a"
PASTA_DE_NOTAS = "/content/drive/MyDrive/Notas de Reuniões/"

#
# ### Documentação com Propósito
# Este script Python tem como objetivo transcrever um arquivo de áudio para texto
# utilizando uma implementação otimizada do Whisper (faster-whisper) para máxima
# velocidade e precisão na GPU.
#
# A biblioteca `faster-whisper` oferece ganhos de performance significativos em
# relação à implementação original, utilizando menos VRAM e permitindo o
# processamento em lote para acelerar a transcrição de arquivos longos.
#

#
# ### 1. Instalação e Importações
# Instala as dependências necessárias. Trocamos a biblioteca 'whisper' original
# pela 'faster-whisper', que é significativamente mais rápida.
#
!pip install --upgrade pip -q
!pip install faster-whisper -q
!pip install ffmpeg-python -q

from faster_whisper import WhisperModel
import os
import torch

#
# ### 2. Configuração e Parâmetros
# Centraliza os parâmetros configuráveis em um único local para fácil alteração.
#
AUDIO_FILE = os.path.join(PASTA_DE_NOTAS, ARQUIVO_DE_AUDIO)

# Modelo do Whisper a ser usado. 'large-v3' oferece a máxima qualidade.
WHISPER_MODEL = "large-v3"

# Determina o dispositivo de processamento (GPU se disponível, senão CPU)
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# MELHORIA DE PERFORMANCE: Define o tipo de computação.
# Para GPUs T4, A100 (arquitetura Ampere ou mais recente), 'float16' é o ideal.
# Para GPUs mais antigas, 'int8_float16' pode ser mais rápido.
COMPUTE_TYPE = "float16" if torch.cuda.is_available() and torch.cuda.get_device_capability(0)[0] >= 7 else "int8"

print(f"Arquivo de áudio: {AUDIO_FILE}")
print(f"Dispositivo de processamento: {DEVICE}")
print(f"Tipo de computação: {COMPUTE_TYPE}")


#
# ### 2.1 (Opcional) Verificação da GPU
# Confirma que a GPU está ativa e exibe suas especificações.
#
if DEVICE == "cuda":
  !nvidia-smi

#
# ### 3. Função de Transcrição Otimizada
# Implementa a lógica de transcrição usando faster-whisper, com foco em
# velocidade e controle de alucinações.
#
def transcribe_audio_optimized(audio_path: str, model_name: str, device: str, compute_type: str) -> str:
    """
    Transcreve um arquivo de áudio usando o modelo faster-whisper otimizado.

    Args:
        audio_path (str): O caminho para o arquivo de áudio.
        model_name (str): O nome do modelo do Whisper a ser carregado.
        device (str): O dispositivo para carregar o modelo ('cuda' ou 'cpu').
        compute_type (str): O tipo de computação para inferência ('float16', 'int8', etc.).

    Returns:
        str: O texto transcrito do áudio.
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"O arquivo de áudio não foi encontrado em: {audio_path}")

    print(f"Carregando o modelo '{model_name}' do faster-whisper...")
    # Carrega o modelo otimizado
    model = WhisperModel(model_name, device=device, compute_type=compute_type)

    print("Iniciando a transcrição otimizada...")
    # O método 'transcribe' do faster-whisper retorna um iterador de segmentos
    # **CORREÇÃO**: O argumento 'batch_size' foi removido desta chamada.
    # A biblioteca gerencia o batching automaticamente.
    segments, info = model.transcribe(
        audio_path,
        language="pt",
        beam_size=5,
        no_speech_threshold=0.6,
        log_prob_threshold=-1.0,
        condition_on_previous_text=True
    )

    # Concatena os segmentos de texto transcritos
    print("Processando segmentos de áudio...")
    full_text = "".join(segment.text for segment in segments)
    print("Transcrição concluída.")

    return full_text

#
# ### 4. Execução Principal
# Chama a função de transcrição otimizada e exibe o resultado.
#
if __name__ == "__main__":
    try:
        transcribed_text = transcribe_audio_optimized(AUDIO_FILE, WHISPER_MODEL, DEVICE, COMPUTE_TYPE)
        print("\n--- Texto Transcrito ---")
        print(transcribed_text)
    except FileNotFoundError as e:
        print(f"Erro: {e}")
    except Exception as e:
        print(f"Ocorreu um erro durante a transcrição: {e}")

#
# ### 5. Salvando o Resultado em um Arquivo
# Salva o texto transcrito em um arquivo .txt para uso posterior.
#
def save_transcription(text: str, input_audio_path: str, output_dir: str):
    """
    Salva o texto em um arquivo de texto com nome derivado do arquivo de áudio.

    Args:
        text (str): O texto a ser salvo.
        input_audio_path (str): O caminho do arquivo de áudio original.
        output_dir (str): O diretório onde o arquivo de texto será salvo.
    """
    # MELHORIA DE USABILIDADE: Gera um nome de arquivo de saída baseado no de entrada.
    base_name = os.path.basename(input_audio_path)
    file_name_without_ext = os.path.splitext(base_name)[0]
    output_filename = f"{file_name_without_ext}.txt"

    # Garante que o diretório de transcrições exista
    transcription_dir = os.path.join(output_dir, "Transcrições")
    os.makedirs(transcription_dir, exist_ok=True)

    output_path = os.path.join(transcription_dir, output_filename)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"\nTexto salvo em '{output_path}'.")

if __name__ == "__main__":
    if 'transcribed_text' in locals() and transcribed_text:
        save_transcription(transcribed_text, AUDIO_FILE, PASTA_DE_NOTAS)
# %%
