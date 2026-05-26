from pathlib import Path
from faster_whisper import WhisperModel
from docx import Document
from docx.shared import Pt

import streamlit as st
import subprocess
import platform
import os
import time

# from streamlit.runtime.scriptrunner import add_script_run_ctx


# ==========================================
# CONFIGURAÇÕES
# ==========================================

BASE_DIR = Path(__file__).parent

UPLOAD_DIR = BASE_DIR / "uploads"
TRANSCRICOES_DIR = BASE_DIR / "transcricoes"
FFMPEG_DIR = BASE_DIR / "ffmpeg"

UPLOAD_DIR.mkdir(exist_ok=True)
TRANSCRICOES_DIR.mkdir(exist_ok=True)

EXTENSOES_VIDEO = {
    ".mp4",
    ".mkv",
    ".avi",
    ".mov"
}

EXTENSOES_AUDIO = {
    ".mp3",
    ".wav",
    ".flac",
    ".ogg",
    ".m4a",
    ".aac"
}


# ==========================================
# FFMPEG LOCAL
# ==========================================

if platform.system() == "Windows":
    FFMPEG_BIN = FFMPEG_DIR / "ffmpeg.exe"
else:
    FFMPEG_BIN = FFMPEG_DIR / "ffmpeg"


# ==========================================
# CARREGAR MODELO IA
# ==========================================

@st.cache_resource
def carregar_modelo(
    nome_modelo: str
) -> WhisperModel:

    return WhisperModel(
        nome_modelo,
        device="cpu",
        compute_type="int8",
        cpu_threads=os.cpu_count()
    )


# ==========================================
# FUNÇÕES
# ==========================================

def formatar_tempo(segundos):

    horas = int(segundos // 3600)
    minutos = int((segundos % 3600) // 60)
    segundos_restantes = int(segundos % 60)

    return (
        f"{horas:02d}:"
        f"{minutos:02d}:"
        f"{segundos_restantes:02d}"
    )
    
    
def salvar_upload(arquivo) -> Path:

    caminho = UPLOAD_DIR / arquivo.name

    with open(caminho, "wb") as f:
        f.write(arquivo.getbuffer())

    return caminho


def extrair_audio_video(
    caminho_video: Path
) -> Path:
    """
    Extrai áudio MP3 de vídeos.
    """

    caminho_saida = caminho_video.with_suffix(".mp3")

    comando = [
        str(FFMPEG_BIN),
        "-y",
        "-i",
        str(caminho_video),

        "-vn",
        "-acodec", "libmp3lame",

        str(caminho_saida)
    ]

    subprocess.run(
        comando,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True
    )

    return caminho_saida


def transcrever_audio(
    caminho_audio: Path,
    barra_progresso,
    texto_status
) -> str:

    inicio_transcricao = time.time()

    segmentos_generator, info = modelo.transcribe(
        str(caminho_audio),
        language="pt",
        beam_size=1,
        vad_filter=True,
        word_timestamps=True,
        condition_on_previous_text=False
    )

    # FORÇA processamento incremental

    duracao_total = info.duration

    texto_final = []

    participante_atual = 1
    ultimo_fim = 0

    buffer_texto = []

    inicio_bloco = 0


    for segmento in segmentos_generator:
    
        texto = segmento.text.strip()

        pausa = segmento.start - ultimo_fim

        # ==========================================
        # TROCA DE PARTICIPANTE
        # ==========================================

        if pausa > 2.0:

            participante_atual += 1

            if participante_atual > 2:
                participante_atual = 1

        # ==========================================
        # INÍCIO DO BLOCO
        # ==========================================

        if not buffer_texto:
            inicio_bloco = segmento.start

        buffer_texto.append(texto)

        ultimo_fim = segmento.end

        # ==========================================
        # FINALIZAR PARÁGRAFO
        # ==========================================

        finalizar = False

        if texto.endswith((".", "!", "?")):
            finalizar = True

        if pausa > 3:
            finalizar = True

        # ==========================================
        # GERAR BLOCO
        # ==========================================

        if finalizar:

            inicio_txt = formatar_tempo(
                inicio_bloco
            )

            fim_txt = formatar_tempo(
                segmento.end
            )

            texto_bloco = " ".join(
                buffer_texto
            )

            bloco = (
                f"[{inicio_txt} → {fim_txt}]\n"
                f"Participante {participante_atual}:\n"
                f"{texto_bloco}\n"
            )

            texto_final.append(bloco)

            buffer_texto = []

        # ==========================================
        # PROGRESSO
        # ==========================================

        progresso = min(
            segmento.end / duracao_total,
            1.0
        )

        porcentagem = int(
            progresso * 100
        )

        tempo_decorrido = (
            time.time() - inicio_transcricao
        )

        velocidade = (
            segmento.end / tempo_decorrido
            if tempo_decorrido > 0
            else 0
        )

        restante_audio = (
            duracao_total - segmento.end
        )

        eta_real = (
            restante_audio / velocidade
            if velocidade > 0
            else 0
        )

        eta_minutos = int(
            eta_real // 60
        )

        eta_segundos = int(
            eta_real % 60
        )

        # ==========================================
        # ATUALIZAR BARRA
        # ==========================================

        barra_progresso.progress(
            progresso,
            text=f"Transcrevendo: {porcentagem}%"
        )

        # ==========================================
        # ATUALIZAR STATUS
        # ==========================================

        texto_status.markdown(
            f"""
            ### 🎙️ Status da Transcrição

            **🎙️ Processado:** {segmento.end:.1f}s / {duracao_total:.1f}s

            **⚡ Velocidade:** {velocidade:.1f}x 
            
            **⏳ Tempo estimado do processo:** {eta_minutos:02d}:{eta_segundos:02d}
            """
        )

        time.sleep(0.03)

    return "\n".join(texto_final)


def salvar_txt(nome: str, texto: str) -> Path:

    caminho = TRANSCRICOES_DIR / f"{nome}.txt"

    caminho.write_text(
        texto,
        encoding="utf-8"
    )

    return caminho


def salvar_docx(nome: str, texto: str) -> Path:

    caminho = TRANSCRICOES_DIR / f"{nome}.docx"

    doc = Document()

    titulo = doc.add_heading(
        "Transcrição",
        level=1
    )

    for linha in texto.split("\n"):

        p = doc.add_paragraph()

        run = p.add_run(linha)

        run.font.size = Pt(11)

        # timestamps em negrito
        if linha.startswith("["):
            run.bold = True

        # participante em azul visual
        if linha.startswith("Participante"):
            run.bold = True

    doc.save(caminho)

    return caminho


# ==========================================
# INTERFACE
# ==========================================

opcoes_modelos_IA = {
    "tiny": "Muito rápido com qualidade regular",
    "base": "Rápido e equilibrado",
    "small": "Melhor equilíbrio",
    "medium": "Alta qualidade e Lento",
    "large-v3": "Máxima qualidade e Muito lento"
}


st.set_page_config(
    page_title="Transcritor IA - MPSampaio",
    page_icon="🎙️",
    layout="centered"
)   

st.title("🎙️ Sistema de Transcrição com IA")
st.write(" ©️ by MPSampaio ")
st.write("")

modelo_escolhido = st.selectbox(
    "Escolha o modelo IA",
    options=list(opcoes_modelos_IA.keys()),
    format_func=lambda x: opcoes_modelos_IA[x],
    index=2
)

modelo = carregar_modelo(
    modelo_escolhido
)

arquivo = st.file_uploader(
    "Envie áudio ou vídeo",
    type=[
        "mp3",
        "wav",
        "m4a",
        "aac",
        "ogg",
        "flac",
        "mp4",
        "mkv",
        "avi",
        "mov",
        "ogg"
    ]
)

if arquivo:

    try:

        with st.spinner("Salvando arquivo..."):
            caminho_original = salvar_upload(arquivo)

        extensao = caminho_original.suffix.lower()

        # ==========================================
        # VÍDEO
        # ==========================================

        if extensao in EXTENSOES_VIDEO:

            with st.spinner(
                "Extraindo áudio do vídeo..."
            ):

                caminho_audio = extrair_audio_video(
                    caminho_original
                )

        # ==========================================
        # ÁUDIO
        # ==========================================

        elif extensao in EXTENSOES_AUDIO:

            caminho_audio = caminho_original

        else:

            st.error(
                "Formato não suportado."
            )

            st.stop()

        barra = st.progress(
            0,
            text=("Iniciando transcrição com IA...")
        )

        status_texto = st.empty()

        texto = transcrever_audio(
            caminho_audio,
            barra,
            status_texto
        )

        barra.progress(
            100,
            text="Transcrição concluída!"
        )

        status_texto.markdown(
            "✅ Processamento finalizado."
        )

        st.success("Transcrição concluída!")

        st.subheader("Texto Transcrito")

        st.text_area(
            "Resultado",
            texto,
            height=350
        )

        nome_base = caminho_original.stem

        txt_path = salvar_txt(
            nome_base,
            texto
        )

        docx_path = salvar_docx(
            nome_base,
            texto
        )

        # DOWNLOAD TXT
        with open(txt_path, "rb") as f:

            st.download_button(
                label="⬇️ Baixar TXT",
                data=f,
                file_name=txt_path.name,
                mime="text/plain"
            )

        # DOWNLOAD DOCX
        with open(docx_path, "rb") as f:

            st.download_button(
                label="⬇️ Baixar DOCX",
                data=f,
                file_name=docx_path.name,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )

    except FileNotFoundError:

        st.error(
            "FFmpeg não encontrado na pasta /ffmpeg"
        )

    except subprocess.CalledProcessError:

        st.error(
            "Erro ao converter mídia."
        )

    except Exception as erro:

        st.error(
            f"Erro inesperado: {erro}"
        )
        