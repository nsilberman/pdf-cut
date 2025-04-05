import streamlit as st
import fitz  # PyMuPDF
import tempfile
import os
import pandas as pd
from pathlib import Path
import base64
import dotenv
from anthropic import Anthropic

st.title("📚 Découpe et correction des copies élèves")

# Chargement de la clé API Claude (Anthropic)
dotenv.load_dotenv()
API_KEY = os.getenv("ANTHROPIC_API_KEY") or st.secrets.get("ANTHROPIC_API_KEY")

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

# Partie 2 : Correction avec OCR et prompt complémentaire
copie_files = sorted(COPIES_DIR.glob("copie_*.pdf"))

if copie_files:
    st.markdown("---")
    st.subheader("🧠 Lancer une correction par OCR")

    selected_file = st.selectbox("📂 Choisis une copie à analyser via OCR", copie_files, key="ocr_select")
    contexte_ia = st.text_area("📝 Ajoute un complément de contexte pour l'IA (consignes, barème, attentes...)")

    if st.button("🔍 Lancer l'analyse OCR sur cette copie"):
        if not API_KEY:
            st.error("❌ Clé API Claude manquante. Ajoute-la dans .env ou dans les secrets Streamlit.")
        else:
            st.info(f"📄 Extraction des images depuis {selected_file.name}...")
            doc = fitz.open(selected_file)
            images = []
            for page in doc:
                pix = page.get_pixmap(dpi=100)
                img_b64 = base64.b64encode(pix.tobytes("png")).decode("utf-8")
                images.append({"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": img_b64}})

            client = Anthropic(api_key=API_KEY)

            try:
                msg = client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=1500,
                    messages=[
                        {"role": "user", "content": [
                            {"type": "text", "text": contexte_ia + "\n\nÀ partir de ce retour, peux-tu me donner les 3 notes suivantes dans ce format JSON uniquement : { \"note_totale\": x, \"note_qcm\": x, \"note_manu\": x }"}
                        ] + images}
                    ]
                )
                response_text = msg.content[0].text
                st.success("✅ Analyse terminée")
                st.markdown(response_text)

                import json
                try:
                    json_part = json.loads(response_text.strip().split("\n")[-1])
                    note_totale = float(json_part.get("note_totale", 0))
                    note_qcm = float(json_part.get("note_qcm", 0))
                    note_manu = float(json_part.get("note_manu", 0))

                    st.success(f"🧮 Note détectée : {note_totale}/20 (QCM : {note_qcm}, Manuscrit : {note_manu})")

                    # Mise à jour dans le CSV
                    new_data = pd.DataFrame([{ 
                        "copie": selected_file.name, 
                        "note_totale": note_totale,
                        "note_qcm": note_qcm,
                        "note_manu": note_manu,
                        "commentaire": response_text
                    }])

                    if CORRECTIONS_CSV.exists():
                        old_data = pd.read_csv(CORRECTIONS_CSV)
                        all_data = pd.concat([old_data, new_data], ignore_index=True)
                    else:
                        all_data = new_data

                    all_data.to_csv(CORRECTIONS_CSV, index=False)
                    st.success("📥 Correction enregistrée dans le fichier CSV")

                except Exception as e:
                    st.warning(f"⚠️ Impossible de parser la réponse en JSON : {e}")

            except Exception as e:
                st.error(f"Erreur lors de l'appel à l'API Claude : {e}")

# Partie 3 : Affichage du tableau de synthèse des corrections
if CORRECTIONS_CSV.exists():
    st.markdown("---")
    st.subheader("📊 Synthèse des corrections enregistrées")
    corrections_df = pd.read_csv(CORRECTIONS_CSV)
    st.dataframe(corrections_df)
    st.download_button("📥 Télécharger toutes les corrections (CSV)", corrections_df.to_csv(index=False).encode("utf-8"), file_name="corrections.csv", mime="text/csv")
