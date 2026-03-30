import streamlit as st
import pandas as pd
import json
import re

st.set_page_config(layout="wide")

def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', s)]

def load_data():
    try:
        with open("input.json", "r") as f:
            return json.load(f)
    except:
        st.error("Error loading input.json")
        st.stop()

def calculate_attainment(data, co_po_file, questions_file):

    # ==============================
    # LOAD CO-PO CSV
    # ==============================
    if co_po_file is not None:
        co_po_df = pd.read_csv(co_po_file)

        st.header("📄 CO-PO Mapping (Uploaded File)")
        st.dataframe(co_po_df)

        co_po_mapping = {}
        for _, row in co_po_df.iterrows():
            co = row["CO"]
            co_po_mapping[co] = {}
            for col in co_po_df.columns[1:]:
                co_po_mapping[co][col] = row[col]
    else:
        st.warning("Please upload CO-PO CSV")
        return None, None, None, None

    # ==============================
    # LOAD QUESTIONS CSV
    # ==============================
    if questions_file is not None:
        questions_df = pd.read_csv(questions_file)

        st.header("📄 Questions (Uploaded File)")
        st.dataframe(questions_df)

        questions = []
        for _, row in questions_df.iterrows():
            questions.append({
                "id": row["QID"],
                "text": row["Question"],
                "co": row["CO"],
                "marks": row["Marks"]
            })
    else:
        st.warning("Please upload Questions CSV")
        return None, None, None, None

    CO_ids = sorted(list(set([q["co"] for q in questions])), key=natural_sort_key)

    st.header("1. Enter Student Marks")

    input_method = st.radio(
        "Select mark input method:",
        ('Manual Entry (Table)', 'Upload CSV File')
    )

    marks_df = pd.DataFrame()

    if input_method == 'Upload CSV File':
        uploaded_file = st.file_uploader("Upload Marks CSV", type="csv")

        if uploaded_file is not None:
            marks_df = pd.read_csv(uploaded_file)

            st.header("📄 Uploaded Marks File")
            st.dataframe(marks_df)
        else:
            return None, None, None, None

    else:
        num_students = st.number_input("Enter number of students:", min_value=1, value=1)

        question_cols = [q["id"] for q in questions]

        initial_data = []
        for i in range(num_students):
            row = {"Student": f"Student_{i+1}"}
            for q in question_cols:
                row[q] = 0.0
            initial_data.append(row)

        marks_df = st.data_editor(pd.DataFrame(initial_data), num_rows="dynamic")

    st.header("2. Marks Table")
    st.dataframe(marks_df)

    # ==============================
    # STUDENT → CO TABLE
    # ==============================
    co_scores = {co: [] for co in CO_ids}

    for _, row in marks_df.iterrows():
        for co in CO_ids:
            rel_q = [q for q in questions if q["co"] == co]
            vals = [row[q["id"]] for q in rel_q]
            avg = sum(vals) / len(vals) if vals else 0
            co_scores[co].append(avg)

    co_df = pd.DataFrame(co_scores)
    co_df.insert(0, "Student", marks_df["Student"])

    st.header("3. Student CO Table")
    st.dataframe(co_df)

    # ==============================
    # CO ATTAINMENT
    # ==============================
    co_attainment = {}
    co_table = []

    st.header("4. CO Attainment")

    for co in CO_ids:
        rel_q = [q for q in questions if q["co"] == co]
        max_marks = rel_q[0]["marks"]
        target = 0.6 * max_marks

        achieved = sum(co_df[co] >= target)
        total = len(co_df)

        direct = (achieved / total) * 100 if total else 0
        indirect = 50
        final = (0.8 * direct) + (0.2 * indirect)

        co_attainment[co] = final
        co_table.append([co, direct, indirect, final])

    co_table_df = pd.DataFrame(co_table, columns=["CO", "Direct %", "Indirect %", "Final %"])

    st.dataframe(co_table_df)

    # ==============================
    # PO ATTAINMENT
    # ==============================
    POs = set()
    for co in co_po_mapping:
        POs.update(co_po_mapping[co].keys())

    po_table = []

    st.header("5. PO Attainment")

    for po in sorted(POs, key=natural_sort_key):
        num = 0
        den = 0

        for co in CO_ids:
            if co in co_po_mapping and po in co_po_mapping[co]:
                w = co_po_mapping[co][po]
                num += co_attainment[co] * w
                den += w

        val = num / den if den else 0
        po_table.append([po, val])

    po_df = pd.DataFrame(po_table, columns=["PO", "Attainment %"])

    st.dataframe(po_df)

    return marks_df, co_df, co_table_df, po_df


def main():
    st.title("🎓 NBA CO-PO Attainment System")

    data = load_data()

    st.sidebar.header("📂 Upload Files")

    co_po_file = st.sidebar.file_uploader("Upload CO-PO CSV", type="csv")
    questions_file = st.sidebar.file_uploader("Upload Questions CSV", type="csv")

    st.sidebar.header("📘 Course Info")
    st.sidebar.write(data.get("course_details", {}))

    calculate_attainment(data, co_po_file, questions_file)


if __name__ == "__main__":
    main()
