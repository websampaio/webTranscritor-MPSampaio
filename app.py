from pathlib import Path
from faster_whisper import WhisperModel
from docx import Document

import streamlit as st
import subprocess
import platform
import os
import time

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

inicio = time.time()


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

    segmentos, info = modelo.transcribe(
        str(caminho_audio),
        language="pt",
        beam_size=1 # 1=Muito rápida / 5=Mais lenta / 10=Pesada
    )

    duracao_total = info.duration

    texto_final = []

    for segmento in segmentos:

        texto_final.append(
            segmento.text.strip()
        )
        

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
        

        # ==========================================
        # TEMPO RESTANTE
        # ==========================================
   
        
        tempo_restante = (
            duracao_total - segmento.end
        )

        minutos = int(
            tempo_restante // 60
        )

        segundos = int(
            tempo_restante % 60
        )
        
        
        # ==========================================
        # TEMPO DECORRIDO
        # ==========================================

        tempo_decorrido = (
            time.time() - inicio
        )

        
        
        # ==========================================
        # VELOCIDADE REALTIME
        # ==========================================

        velocidade = (
            segmento.end / tempo_decorrido
            if tempo_decorrido > 0
            else 0
        )

        
        # ==========================================
        # ETA REAL
        # ==========================================
        
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
        # BARRA
        # ==========================================

        barra_progresso.progress(
            progresso,
            text=f"Transcrevendo: {porcentagem}%"
        )

        texto_status.text(
            f"🎙️ Processado: "
            f"{segmento.end:.1f}s / "
            f"{duracao_total:.1f}s\n"
            
            f"⏳ Tempo restante do áudio: "
            f"{minutos:02d}:{segundos:02d}s\n"

            f"⚡ Velocidade: "
            f"{velocidade:.1f}x\n"
            
            f"⏳ Tempo restante do processo: "
            f"{eta_minutos:02d}:"
            f"{eta_segundos:02d}s"
        )
        
    return " ".join(texto_final)


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

    doc.add_heading(
        "Transcrição",
        level=1
    )

    doc.add_paragraph(texto)

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

        with st.spinner("Transcrevendo com IA..."):

            barra = st.progress(
                0,
                text="Iniciando transcrição..."
            )

            status = st.empty()

            texto = transcrever_audio(
                caminho_audio,
                barra,
                status
            )

            barra.progress(
                100,
                text="Transcrição concluída!"
            )

            status.text("Processamento finalizado.")

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