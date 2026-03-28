import streamlit as st
import pandas as pd
import json
import re

st.set_page_config(layout="wide")

def natural_sort_key(s):
    """Key for natural sorting strings containing numbers (e.g., PO1, PO10, PO2)."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', s)]

def load_data():
    try:
        with open("input.json", "r") as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        st.error("input.json not found. Please ensure it's in the same directory.")
        st.stop()
    except json.JSONDecodeError:
        st.error("Error decoding input.json. Please check its format.")
        st.stop()

def calculate_attainment(data):
    questions = data.get("questions", [])
    co_po_mapping = data.get("co_po_mapping", {})

    if not questions or not co_po_mapping:
        st.warning("Questions or CO-PO mapping not found in input.json. Cannot proceed with calculations.")
        return None, None, None, None

    # Extract COs dynamically from questions
    CO_ids = sorted(list(set([q["co"] for q in questions])), key=natural_sort_key)

    st.header("1. Enter Student Marks")

    input_method = st.radio(
        "Select mark input method:",
        ('Manual Entry (Table)', 'Upload CSV File')
    )

    marks_df = pd.DataFrame() # Initialize empty DataFrame

    if input_method == 'Upload CSV File':
        st.info("Please upload a CSV file with 'Student' as the first column and question IDs (e.g., 'Q1', 'Q2') as subsequent columns, containing marks.")
        uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

        if uploaded_file is not None:
            try:
                uploaded_marks_df = pd.read_csv(uploaded_file)

                # Validate columns
                required_cols = ["Student"] + [q["id"] for q in questions]
                if not all(col in uploaded_marks_df.columns for col in required_cols):
                    st.error(f"CSV file must contain columns: {', '.join(required_cols)}")
                    return None, None, None, None

                # Validate marks range
                for q in questions:
                    max_mark = float(q["marks"])
                    if not (uploaded_marks_df[q["id"]] >= 0).all() or not (uploaded_marks_df[q["id"]] <= max_mark).all():
                        st.error(f"Marks for {q["id"]} must be between 0 and {max_mark}.")
                        return None, None, None, None

                marks_df = uploaded_marks_df[required_cols].copy()
                st.success("CSV file uploaded and validated successfully!")
                st.dataframe(marks_df)

            except Exception as e:
                st.error(f"Error processing CSV file: {e}")
                return None, None, None, None
        else:
            st.info("Waiting for CSV file upload.")
            return None, None, None, None # Don't proceed if no file is uploaded yet

    else: # Manual Entry (Table)
        num_students = st.number_input("Enter number of students:", min_value=1, value=1, step=1)

        # Prepare initial DataFrame for st.data_editor
        question_cols = [q["id"] for q in questions]
        initial_marks_data = []
        for i in range(num_students):
            student_name = f"Student_{i+1}"
            row = {"Student": student_name}
            for q_id in question_cols:
                row[q_id] = 0.0 # Default value
            initial_marks_data.append(row)

        # Use session state to persist data_editor's content
        if "marks_editor_df" not in st.session_state or len(st.session_state.marks_editor_df) != num_students:
            st.session_state.marks_editor_df = pd.DataFrame(initial_marks_data)
        else:
            # Adjust existing DataFrame if number of students changes
            if len(st.session_state.marks_editor_df) > num_students:
                st.session_state.marks_editor_df = st.session_state.marks_editor_df.head(num_students)
            elif len(st.session_state.marks_editor_df) < num_students:
                # Add new student rows with default marks
                current_students = len(st.session_state.marks_editor_df)
                for i in range(current_students, num_students):
                    new_student_name = f"Student_{i+1}"
                    new_row = {"Student": new_student_name}
                    for q_id in question_cols:
                        new_row[q_id] = 0.0
                    st.session_state.marks_editor_df = pd.concat([st.session_state.marks_editor_df, pd.DataFrame([new_row])], ignore_index=True)

        # Data editor for marks input
        st.write("Enter marks for each student per question. Max marks are shown below the table for reference.")
        marks_df = st.data_editor(
            st.session_state.marks_editor_df,
            column_config={
                "Student": st.column_config.TextColumn(
                    "Student",
                    help="Student ID",
                    disabled=True,
                ),
                **{q["id"]: st.column_config.NumberColumn(
                    q["id"],
                    help=f"Marks for {q["id"]} (Max: {q["marks"]})",
                    min_value=0.0,
                    max_value=float(q["marks"]),
                    step=0.5,
                    format="%.1f",
                ) for q in questions}
            },
            num_rows="dynamic",
            key="marks_input_editor"
        )

        # Display max marks for reference below the editor
        st.write("**Max Marks per Question:**")
        max_marks_display = {q["id"]: q["marks"] for q in questions}
        st.dataframe(pd.DataFrame([max_marks_display]))

    # Proceed only if marks_df is not empty after either method
    if marks_df.empty:
        return None, None, None, None

    st.header("2. Marks Table")
    st.dataframe(marks_df)

    # Student -> CO Table
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

    # CO Attainment
    co_attainment = {}
    co_table_data = []

    st.header("4. CO Attainment")
    for co in CO_ids:
        rel_q = [q for q in questions if q["co"] == co]
        if rel_q:
            max_marks_for_co = max([q["marks"] for q in rel_q])
            target = 0.6 * max_marks_for_co # 60% attainment target
            achieved = sum(co_df[co] >= target) # Check against avg CO score for each student
            total = len(co_df)

            direct = (achieved / total) * 100 if total > 0 else 0
            indirect = 50 # Default indirect attainment
            final = (0.8 * direct) + (0.2 * indirect)

            co_attainment[co] = final
            co_table_data.append([co, f"{direct:.2f}%", f"{indirect:.2f}%", f"{final:.2f}%"])
        else:
            co_attainment[co] = 0.0
            co_table_data.append([co, "0.00%", "0.00%", "0.00%"])

    co_df_table = pd.DataFrame(co_table_data, columns=["CO", "Direct %", "Indirect %", "Final %"])
    st.dataframe(co_df_table)

    # PO Attainment
    POs = set()
    for co_key in co_po_mapping:
        POs.update(co_po_mapping[co_key].keys())

    sorted_POs = sorted(list(POs), key=natural_sort_key)
    po_attainment_values = {}

    st.header("5. PO Attainment")
    for po in sorted_POs:
        num = 0
        den = 0
        for co in CO_ids:
            # Ensure CO exists in co_po_mapping and PO exists within that CO
            if co in co_po_mapping and po in co_po_mapping[co]:
                w = co_po_mapping[co][po]
                num += co_attainment.get(co, 0) * w
                den += w

        val = num / den if den else 0
        po_attainment_values[po] = f"{val:.2f}%"

    # Create a single-row DataFrame with POs as columns
    po_df = pd.DataFrame([po_attainment_values])
    st.dataframe(po_df)

    return marks_df, co_df, co_df_table, po_df

def main():
    st.title("NBA-based CO/PO Attainment Calculator")

    data = load_data()

    if not data:
        return

    course_details = data.get("course_details", {})
    COs_list = data.get("course_outcomes", [])
    co_po_mapping = data.get("co_po_mapping", {})
    questions = data.get("questions", [])

    st.sidebar.header("Course Information")
    st.sidebar.write(f"**Department:** {course_details.get('department', 'N/A')}")
    st.sidebar.write(f"**Semester:** {course_details.get('semester', 'N/A')}")
    st.sidebar.write(f"**Subject:** {course_details.get('course_name', 'N/A')}")

    st.sidebar.header("Course Outcomes")
    for co in COs_list:
        st.sidebar.write(f"**{co['id']}**: {co['statement']}")

    st.sidebar.header("CO-PO Mapping")
    if co_po_mapping:
        st.sidebar.dataframe(pd.DataFrame(co_po_mapping).T.fillna(0).astype(int))
    else:
        st.sidebar.info("CO-PO mapping not available.")

    st.sidebar.header("Generated Questions")
    if questions:
        q_df = pd.DataFrame(questions)
        st.sidebar.dataframe(q_df[['id', 'text', 'co', 'marks']])
    else:
        st.sidebar.info("No questions available.")


    marks_df, co_df, co_df_table, po_df = calculate_attainment(data)


if __name__ == "__main__":
    main()
