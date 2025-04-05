import streamlit as st
from PyPDF2 import PdfReader, PdfWriter
from PyPDF2.generic import RectangleObject
import tempfile
import os

st.title("📚 Découpe automatique des copies élèves")

uploaded_file = st.file_uploader("Dépose ton fichier PDF avec toutes les copies scannées", type="pdf")

# Fonction pour découper une page A3 en deux A4 (horizontal split)
def split_page_vertically(page):
    media_box = page.mediabox
    width = media_box.right
    height = media_box.top

    left_half = RectangleObject([0, 0, width / 2, height])
    right_half = RectangleObject([width / 2, 0, width, height])

    return left_half, right_half

def process_pdf(input_pdf):
    output_files = []
    reader = PdfReader(input_pdf)
    pages_par_copie_pdf = 4
    total_pages = len(reader.pages)
    nombre_copies = total_pages // pages_par_copie_pdf

    for i in range(nombre_copies):
        writer = PdfWriter()
        start = i * pages_par_copie_pdf

        a3_recto = reader.pages[start]
        a3_verso = reader.pages[start + 1]
        qcm_page = reader.pages[start + 2]

        left_recto, right_recto = split_page_vertically(a3_recto)
        left_verso, right_verso = split_page_vertically(a3_verso)

        # Ajout dans l'ordre logique : 1,2,3,4 manuscrites, puis QCM
        for crop, base_page in zip([right_recto, left_verso, right_verso, left_recto], [a3_recto]*2 + [a3_verso]*2):
            cropped = base_page
            cropped.mediabox = crop
            writer.add_page(cropped)

        writer.add_page(qcm_page)

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f"_copie_{i+1}.pdf")
        writer.write(temp_file)
        temp_file.close()
        output_files.append(temp_file.name)

    return output_files

if uploaded_file:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name

    st.info("📄 Découpage en cours...")
    result_files = process_pdf(tmp_path)

    for path in result_files:
        with open(path, "rb") as f:
            st.download_button(
                label=f"📥 Télécharger {os.path.basename(path)}",
                data=f,
                file_name=os.path.basename(path),
                mime="application/pdf"
            )
