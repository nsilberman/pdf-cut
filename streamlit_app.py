import streamlit as st
import fitz  # PyMuPDF
import tempfile
import os
import pandas as pd
from pathlib import Path

st.title("📚 Découpe et correction des copies élèves")

# Répertoire de stockage des copies découpées
COPIES_DIR = Path("copies")
COPIES_DIR.mkdir(exist_ok=True)
CORRECTIONS_CSV = Path("corrections.csv")

uploaded_file = st.file_uploader("Dépose ton fichier PDF avec toutes les copies scannées", type="pdf")

# Fonction pour découper une page A3 en deux A4 (horizontal split)
def split_page_vertically(page):
    rect = page.rect
    width = rect.width
    height = rect.height

    left_half = fitz.Rect(0, 0, width / 2, height)
    right_half = fitz.Rect(width / 2, 0, width, height)

    return left_half, right_half

def process_pdf(input_pdf_path):
    doc = fitz.open(input_pdf_path)
    pages_par_copie_pdf = 4
    total_pages = len(doc)
    nombre_copies = total_pages // pages_par_copie_pdf

    for i in range(nombre_copies):
        new_doc = fitz.open()
        start = i * pages_par_copie_pdf

        a3_recto = doc[start]
        a3_verso = doc[start + 1]
        qcm_page = doc[start + 2]

        left_recto, right_recto = split_page_vertically(a3_recto)
        left_verso, right_verso = split_page_vertically(a3_verso)

        # Ordre logique correct : 1, 2, 3, 4 manuscrites, puis QCM
        ordered_clips = [right_recto, left_verso, right_verso, left_recto]
        ordered_sources = [a3_recto, a3_verso, a3_verso, a3_recto]

        for crop_rect, base_page in zip(ordered_clips, ordered_sources):
            pix = base_page.get_pixmap(clip=crop_rect, dpi=100)
            img_pdf = fitz.open()
            img_pdf.insert_page(-1, width=crop_rect.width, height=crop_rect.height)
            img_page = img_pdf[-1]
            img_page.insert_image(img_page.rect, pixmap=pix)
            new_doc.insert_pdf(img_pdf)

        new_doc.insert_pdf(doc, from_page=start + 2, to_page=start + 2)

        output_path = COPIES_DIR / f"copie_{i+1}.pdf"
        new_doc.save(output_path, deflate=True)
        new_doc.close()

# Partie 1 : Découpage si fichier uploadé
if uploaded_file:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name

    st.info("📄 Découpage en cours...")
    process_pdf(tmp_path)
    st.success("✅ Découpage terminé. Copies stockées dans le dossier 'copies'.")

# Partie 2 : Sélection et affichage des copies stockées
copie_files = sorted(COPIES_DIR.glob("copie_*.pdf"))

if copie_files:
    selected_file = st.selectbox("📂 Choisis une copie à corriger", copie_files)

    if selected_file:
        st.info(f"Affichage de : {selected_file.name}")
        with open(selected_file, "rb") as f:
            st.download_button("📥 Télécharger cette copie", f, file_name=selected_file.name)
            base64_pdf = f.read()
            st.download_button("🔍 Voir dans le navigateur", base64_pdf, file_name=selected_file.name)
            st.components.v1.iframe(src=selected_file.as_posix(), height=800)

        st.markdown("---")
        st.subheader("✏️ Correction de la copie")
        note_qcm = st.number_input("Note QCM", min_value=0.0, max_value=10.0, step=0.5)
        note_manu = st.number_input("Note manuscrit", min_value=0.0, max_value=10.0, step=0.5)
        commentaire = st.text_area("Commentaire global")

        if st.button("✅ Enregistrer la correction"):
            new_data = pd.DataFrame([{ 
                "copie": selected_file.name, 
                "note_qcm": note_qcm, 
                "note_manu": note_manu, 
                "commentaire": commentaire
            }])

            if CORRECTIONS_CSV.exists():
                old_data = pd.read_csv(CORRECTIONS_CSV)
                all_data = pd.concat([old_data, new_data], ignore_index=True)
            else:
                all_data = new_data

            all_data.to_csv(CORRECTIONS_CSV, index=False)
            st.success("✅ Correction enregistrée !")

# Partie 3 : Affichage du tableau de synthèse des corrections
if CORRECTIONS_CSV.exists():
    st.markdown("---")
    st.subheader("📊 Synthèse des corrections enregistrées")
    corrections_df = pd.read_csv(CORRECTIONS_CSV)
    st.dataframe(corrections_df)
    st.download_button("📥 Télécharger toutes les corrections (CSV)", corrections_df.to_csv(index=False).encode("utf-8"), file_name="corrections.csv", mime="text/csv")
