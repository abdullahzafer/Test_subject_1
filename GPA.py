from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from datetime import datetime
import json
from io import BytesIO
import streamlit as st
import pandas as pd

from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

try:
    st.set_page_config(page_title="University GPA Calculator", page_icon="🎓", layout="wide")

    READY_RECKONER_TABLE = {
        **{m: (Decimal("4.0"), "A+", "Excellent") for m in range(95, 101)},
        **{m: (Decimal("4.0"), "A", "Very Good") for m in range(85, 95)},
        84: (Decimal("3.9"), "B+", "Good"), 83: (Decimal("3.9"), "B+", "Good"),
        82: (Decimal("3.8"), "B+", "Good"), 81: (Decimal("3.7"), "B+", "Good"),
        80: (Decimal("3.7"), "B+", "Good"), 79: (Decimal("3.6"), "B", "Good"),
        78: (Decimal("3.5"), "B", "Good"), 77: (Decimal("3.5"), "B", "Good"),
        76: (Decimal("3.4"), "B", "Good"), 75: (Decimal("3.3"), "B", "Good"),
        74: (Decimal("3.3"), "B", "Good"), 73: (Decimal("3.2"), "B", "Good"),
        72: (Decimal("3.1"), "B", "Good"), 71: (Decimal("3.1"), "B", "Good"),
        70: (Decimal("3.0"), "B", "Good"), 69: (Decimal("2.9"), "C", "Satisfactory"),
        68: (Decimal("2.8"), "C", "Satisfactory"), 67: (Decimal("2.7"), "C", "Satisfactory"),
        66: (Decimal("2.6"), "C", "Satisfactory"), 65: (Decimal("2.5"), "C", "Satisfactory"),
        64: (Decimal("2.4"), "C", "Satisfactory"), 63: (Decimal("2.3"), "C", "Satisfactory"),
        62: (Decimal("2.2"), "C", "Satisfactory"), 61: (Decimal("2.1"), "C", "Satisfactory"),
        60: (Decimal("2.0"), "C", "Satisfactory"), 59: (Decimal("1.9"), "D", "Poor"),
        58: (Decimal("1.8"), "D", "Poor"), 57: (Decimal("1.7"), "D", "Poor"),
        56: (Decimal("1.6"), "D", "Poor"), 55: (Decimal("1.5"), "D", "Poor"),
        54: (Decimal("1.4"), "D", "Poor"), 53: (Decimal("1.3"), "D", "Poor"),
        52: (Decimal("1.2"), "D", "Poor"), 51: (Decimal("1.1"), "D", "Poor"),
        50: (Decimal("1.0"), "D", "Poor"),
    }

    D0 = Decimal("0")
    D1 = Decimal("1")
    D4 = Decimal("4")

    def dec(value):
        return Decimal(str(value))

    def fmt(value):
        return str(dec(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    def round_percentage_up(value):
        value = dec(value)
        if value < 0 or value > 100:
            raise ValueError("Percentage must be between 0 and 100.")
        return int(value.to_integral_value(rounding=ROUND_CEILING))

    def evaluate_marks(obtained, maximum):
        obtained, maximum = dec(obtained), dec(maximum)
        if maximum <= 0 or obtained < 0 or obtained > maximum:
            raise ValueError("Marks must be within the valid range.")
        exact_pct = obtained / maximum * Decimal("100")
        rounded_pct = round_percentage_up(exact_pct)
        if rounded_pct < 50:
            return exact_pct, rounded_pct, D0, "F", "Fail"
        gp, letter, remarks = READY_RECKONER_TABLE[rounded_pct]
        return exact_pct, rounded_pct, gp, letter, remarks

    def evaluate_direct_gpa(gp):
        gp = dec(gp)
        if gp < 0 or gp > 4:
            raise ValueError("Lab GPA must be between 0 and 4.")
        if gp >= Decimal("3.95"):
            return "A+", "Excellent"
        if gp >= Decimal("3.7"):
            return "B+", "Good"
        if gp >= Decimal("3.0"):
            return "B", "Good"
        if gp >= Decimal("2.0"):
            return "C", "Satisfactory"
        if gp >= Decimal("1.0"):
            return "D", "Poor"
        return "F", "Fail"

    def calculate_sgpa(subjects):
        credits = D0
        quality_points = D0
        for subject in subjects:
            if subject["status"] == "Withdrawn":
                continue
            cr = dec(subject["credits"])
            gp = dec(subject["grade_point"])
            credits += cr
            quality_points += cr * gp
        sgpa = quality_points / credits if credits else D0
        return credits, quality_points, sgpa

    def make_subject(name, credits, status, raw_value=None, previous_gp=None, previous_credits=None, prior_included=False):
        credits = dec(credits)
        result = {
            "name": name.strip() or "Unnamed course", "credits": credits, "status": status,
            "raw_input": "Withdrawn", "rounded_percentage": None, "letter_grade": "W",
            "grade_point": D0, "remarks": "Withdrawn (excluded from GPA)",
            "previous_gp": D0, "previous_credits": D0, "prior_attempt_included": False,
        }
        if status == "Withdrawn":
            return result
        if credits == D1:
            gp = dec(raw_value)
            letter, remarks = evaluate_direct_gpa(gp)
            result.update(raw_input=f"Direct lab GPA: {fmt(gp)}/4.00", letter_grade=letter,
                          grade_point=gp, remarks=f"Lab ({remarks})")
        else:
            maximum = Decimal("50") if credits == Decimal("2") else Decimal("100")
            exact_pct, rounded_pct, gp, letter, remarks = evaluate_marks(raw_value, maximum)
            result.update(raw_input=f"{fmt(raw_value)}/{fmt(maximum)}", rounded_percentage=rounded_pct,
                          letter_grade=letter, grade_point=gp,
                          remarks=f"{remarks}; exact {fmt(exact_pct)}%, rounded up to {rounded_pct}%")
        if status == "Retake":
            result["previous_gp"] = dec(previous_gp or 0)
            result["previous_credits"] = dec(previous_credits if previous_credits is not None else credits)
            result["prior_attempt_included"] = bool(prior_included)
            result["remarks"] += " (retake: current attempt used for current SGPA)"
        return result

    def subject_row(subject):
        return {
            "Course": subject["name"], "Credits": float(subject["credits"]),
            "Input": subject["raw_input"], "Rounded %": subject["rounded_percentage"] if subject["rounded_percentage"] is not None else "—",
            "Grade": subject["letter_grade"], "Grade Point": fmt(subject["grade_point"]),
            "Quality Points": fmt(dec(subject["credits"]) * dec(subject["grade_point"])),
            "Remarks": subject["remarks"],
        }

    def render_course_inputs(prefix, allow_retakes=True, count_default=5):
        count = int(st.number_input("Number of courses", min_value=1, max_value=20, value=count_default, step=1, key=f"{prefix}_count"))
        subjects = []
        for i in range(count):
            st.markdown(f"**Course {i + 1}**")
            c1, c2, c3 = st.columns([2.2, 1, 1.3])
            name = c1.text_input("Course name", value=f"Course {i + 1}", key=f"{prefix}_name_{i}")
            credits = c2.number_input("Credit hours", min_value=0.5, max_value=12.0, value=3.0, step=0.5, key=f"{prefix}_credits_{i}")
            status_options = ["Regular", "Withdrawn", "Retake"] if allow_retakes else ["Regular", "Withdrawn"]
            status = c3.selectbox("Status", status_options, key=f"{prefix}_status_{i}")
            credits_d = dec(credits)
            if status == "Withdrawn":
                subjects.append(make_subject(name, credits_d, status))
                continue
            if credits_d == D1:
                raw = st.number_input("Lab GPA (out of 4.00)", min_value=0.0, max_value=4.0, value=3.0, step=0.1, key=f"{prefix}_value_{i}")
                subject = make_subject(name, credits_d, status, raw_value=raw)
            else:
                maximum = 50.0 if credits_d == Decimal("2") else 100.0
                label = "Marks out of 50" if maximum == 50 else "Marks out of 100"
                raw = st.number_input(label, min_value=0.0, max_value=maximum, value=0.0, step=0.5, key=f"{prefix}_value_{i}")
                subject = make_subject(name, credits_d, status, raw_value=raw)
            if status == "Retake":
                st.caption("The current attempt counts in this semester's SGPA. If the old attempt is already included in your previous CGPA totals, enter its grade point below so it can be removed from the cumulative calculation.")
                r1, r2, r3 = st.columns(3)
                prev_gp = r1.number_input("Previous attempt GPA", min_value=0.0, max_value=4.0, value=0.0, step=0.1, key=f"{prefix}_prev_gp_{i}")
                prev_cr = r2.number_input("Previous attempt credits", min_value=0.5, max_value=12.0, value=float(credits), step=0.5, key=f"{prefix}_prev_cr_{i}")
                included = r3.checkbox("Old attempt is in prior CGPA totals", value=True, key=f"{prefix}_prev_included_{i}")
                subject["previous_gp"] = dec(prev_gp)
                subject["previous_credits"] = dec(prev_cr)
                subject["prior_attempt_included"] = included
            subjects.append(subject)
            st.divider()
        return subjects

    def add_history(kind, payload):
        record = {"timestamp": datetime.now().astimezone().isoformat(timespec="seconds"), "type": kind, **payload}
        st.session_state.history.insert(0, record)

    def generate_single_pdf_report(item):
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), rightMargin=25, leftMargin=25, topMargin=25, bottomMargin=25)
        elements = []
        
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Heading1'],
            fontSize=15,
            textColor=colors.HexColor("#1f77b4"),
            spaceAfter=4
        )
        meta_style = ParagraphStyle(
            'MetaStyle',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor("#333333"),
            spaceAfter=10
        )
        
        timestamp = item.get("timestamp", "N/A")
        calc_type = item.get("type", "Calculation")
        
        elements.append(Paragraph(f"University GPA Report — {calc_type}", title_style))
        
        meta_text = f"<b>Timestamp:</b> {timestamp}"
        if "sgpa" in item:
            meta_text += f" | <b>SGPA:</b> {item['sgpa']} / 4.00"
        elif "cgpa_after_current" in item:
            meta_text += f" | <b>Current SGPA:</b> {item.get('current_sgpa', 'N/A')} | <b>CGPA After:</b> {item['cgpa_after_current']} / 4.00"
        elements.append(Paragraph(meta_text, meta_style))
        elements.append(Spacer(1, 5))
        
        courses = item.get("courses", [])
        if courses:
            table_data = [["Course", "Credits", "Input", "Rounded %", "Grade", "Grade Point", "Quality Points", "Remarks"]]
            for c in courses:
                table_data.append([
                    str(c.get("Course", "")),
                    str(c.get("Credits", "")),
                    str(c.get("Input", "")),
                    str(c.get("Rounded %", "")),
                    str(c.get("Grade", "")),
                    str(c.get("Grade Point", "")),
                    str(c.get("Quality Points", "")),
                    str(c.get("Remarks", ""))
                ])
            
            # Append Total / Summary as the last row of the table
            total_credits = item.get("credits", item.get("effective_credits", ""))
            total_qp = item.get("quality_points", "")
            final_score_label = f"SGPA: {item.get('sgpa', item.get('cgpa_after_current', ''))}" if ("sgpa" in item or "cgpa_after_current" in item) else "Total"
            
            table_data.append([
                "TOTAL / SUMMARY",
                str(total_credits),
                "—",
                "—",
                "—",
                "—",
                str(total_qp),
                final_score_label
            ])
            
            t = Table(table_data, hAlign='LEFT', colWidths=[120, 50, 110, 65, 45, 65, 80, 220])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1f77b4")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('ALIGN', (0, 1), (0, -1), 'LEFT'),
                ('ALIGN', (7, 1), (7, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 5),
                ('BACKGROUND', (0, 1), (-1, -2), colors.HexColor("#fdfdfd")),
                # Highlight the last summary row differently
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#eaeaea")),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#dcdcdc")),
                ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 7.5),
                ('TOPPADDING', (0, 1), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
            ]))
            elements.append(t)
            
        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()

    def grade_options_for_course(course, require_pass=True):
        if course["credits"] == D1:
            start = 10 if require_pass else 0
            return [{"gp": dec(i) / Decimal("10"), "letter": evaluate_direct_gpa(dec(i) / Decimal("10"))[0], "score": dec(i) / Decimal("4") * Decimal("100"), "display_score": f"{fmt(dec(i) / Decimal('10'))}/4.00 GPA"} for i in range(start, 41)]
        unique = {}
        for mark in range(50, 101):
            gp, letter, _ = READY_RECKONER_TABLE[mark]
            if gp not in unique:
                minimum_raw_pct = max(Decimal("0"), Decimal(mark - 1) + Decimal("0.01"))
                maximum = Decimal("50") if course["credits"] == Decimal("2") else Decimal("100")
                raw_marks = (minimum_raw_pct * maximum / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_CEILING)
                unique[gp] = {"gp": gp, "letter": letter, "score": minimum_raw_pct, "display_score": f"{fmt(raw_marks)} / {fmt(maximum)} marks (rounds up to {mark}%)"}
        options = sorted(unique.values(), key=lambda x: x["gp"])
        if require_pass:
            return options
        return [{"gp": D0, "letter": "F", "score": D0, "display_score": "Below 50% (F)"}] + options

    def build_efficient_plan(courses, required_sgpa, require_pass=True):
        if not courses:
            return [], D0
        options = [grade_options_for_course(c, require_pass=require_pass) for c in courses]
        total_credits = sum((dec(c["credits"]) for c in courses), D0)
        target_qp = dec(required_sgpa) * total_credits
        target_units = int((target_qp * Decimal("20")).to_integral_value(rounding=ROUND_CEILING))
        max_units = sum(int(dec(c["credits"]) * max(o["gp"] for o in opts) * Decimal("20")) for c, opts in zip(courses, options))
        if target_units > max_units:
            return [], Decimal(max_units) / Decimal("20")

        dp = {0: D0}
        parents = []
        for course, course_options in zip(courses, options):
            next_dp = {}
            parent = {}
            for old_units, old_cost in dp.items():
                for option_index, option in enumerate(course_options):
                    add_units = int(dec(course["credits"]) * option["gp"] * Decimal("20"))
                    new_units = old_units + add_units
                    new_cost = old_cost + option["score"]
                    if new_units not in next_dp or new_cost < next_dp[new_units]:
                        next_dp[new_units] = new_cost
                        parent[new_units] = (old_units, option_index)
            dp = next_dp
            parents.append(parent)

        feasible = [units for units in dp if units >= target_units]
        if not feasible:
            return [], Decimal(max_units) / Decimal("20")
        final_units = min(feasible, key=lambda units: (dp[units], units))
        selected = [0] * len(courses)
        units = final_units
        for index in range(len(courses) - 1, -1, -1):
            previous_units, option_index = parents[index][units]
            selected[index] = option_index
            units = previous_units

        plan = []
        for course, course_options, choice in zip(courses, options, selected):
            option = course_options[choice]
            plan.append({
                "Course": course["name"],
                "Credits": float(course["credits"]),
                "Target Grade": option["letter"],
                "Target GPA": fmt(option["gp"]),
                "Minimum Required Score": option["display_score"],
            })
        return plan, Decimal(final_units) / Decimal("20")

    if "history" not in st.session_state:
        st.session_state.history = []

    st.title("🎓 University GPA & CGPA Calculator")
    st.caption("Uses the university's ceiling rule: 64.01% becomes 65%. One-credit labs use direct GPA; two-credit subjects use marks out of 50; all other credit values use marks out of 100.")

    sgpa_tab, cgpa_tab, target_tab, history_tab, policy_tab = st.tabs(["SGPA Calculator", "CGPA & Projection", "Target Planner", "History & Export", "Grading Policy"])

    with sgpa_tab:
        st.subheader("Semester GPA (SGPA)")
        subjects = render_course_inputs("sgpa", allow_retakes=True, count_default=5)
        if st.button("Calculate SGPA", type="primary", key="calculate_sgpa"):
            total_credits, total_qp, sgpa = calculate_sgpa(subjects)
            if total_credits == 0:
                st.error("All courses are withdrawn, so there are no effective credit hours to calculate SGPA.")
            else:
                st.metric("SGPA", f"{fmt(sgpa)} / 4.00")
                m1, m2 = st.columns(2)
                m1.metric("Effective credit hours", fmt(total_credits))
                m2.metric("Quality points", fmt(total_qp))
                st.dataframe(pd.DataFrame([subject_row(s) for s in subjects]), use_container_width=True, hide_index=True)
                add_history("SGPA", {"sgpa": fmt(sgpa), "credits": fmt(total_credits), "quality_points": fmt(total_qp), "courses": [subject_row(s) for s in subjects]})
                st.success("Calculation added to this session's history.")

    with cgpa_tab:
        st.subheader("Current CGPA and future projection")
        
        cgpa_calc_mode = st.radio(
            "CGPA Calculation Mode",
            ["Detailed Course-Based Calculation", "Quick GPA-Based Calculation"],
            horizontal=True,
            key="cgpa_calc_mode"
        )
        
        st.markdown("---")
        st.markdown("#### Step 1: Prior Academic Record")
        history_mode = st.radio("How do you want to enter completed semesters?", ["Overall current CGPA + completed credits", "Semester-by-semester SGPA + credits"], horizontal=True, key="cgpa_history_mode")
        past_credits = D0
        past_qp = D0
        if history_mode == "Overall current CGPA + completed credits":
            a, b = st.columns(2)
            current_cgpa_input = a.number_input("Current CGPA (0.00–4.00)", min_value=0.0, max_value=4.0, value=0.0, step=0.01, key="overall_cgpa")
            completed_credits_input = b.number_input("Completed credit hours", min_value=0.0, max_value=300.0, value=0.0, step=0.5, key="overall_credits")
            past_credits = dec(completed_credits_input)
            past_qp = past_credits * dec(current_cgpa_input)
        else:
            sem_count = int(st.number_input("Number of completed semesters", min_value=0, max_value=12, value=2, step=1, key="cgpa_sem_count"))
            for i in range(sem_count):
                a, b = st.columns(2)
                sem_sgpa = a.number_input(f"Semester {i + 1} SGPA", min_value=0.0, max_value=4.0, value=0.0, step=0.01, key=f"past_sgpa_{i}")
                sem_credits = b.number_input(f"Semester {i + 1} credits", min_value=0.5, max_value=40.0, value=15.0, step=0.5, key=f"past_credits_{i}")
                past_credits += dec(sem_credits)
                past_qp += dec(sem_sgpa) * dec(sem_credits)

        if cgpa_calc_mode == "Detailed Course-Based Calculation":
            st.markdown("---")
            st.markdown("#### Step 2: Current Semester Courses (Detailed)")
            current_courses = render_course_inputs("cgpa_current", allow_retakes=True, count_default=5)
            
            st.markdown("---")
            st.markdown("#### Step 3: Future Projections (Optional)")
            project_count = int(st.number_input("Upcoming semesters to project after this semester", min_value=0, max_value=10, value=0, step=1, key="projection_count"))
            projections = []
            for i in range(project_count):
                a, b = st.columns(2)
                p_sgpa = a.number_input(f"Projected semester {i + 1} SGPA", min_value=0.0, max_value=4.0, value=3.0, step=0.01, key=f"project_sgpa_{i}")
                p_credits = b.number_input(f"Projected semester {i + 1} credits", min_value=0.5, max_value=40.0, value=15.0, step=0.5, key=f"project_credits_{i}")
                projections.append((dec(p_sgpa), dec(p_credits)))
                
            if st.button("Calculate CGPA & Projection (Detailed)", type="primary", key="calculate_cgpa_detailed"):
                cur_cr, cur_qp, cur_sgpa = calculate_sgpa(current_courses)
                if cur_cr <= 0:
                    st.error("The current semester has no non-withdrawn courses. Add at least one active course.")
                else:
                    replace_cr = D0
                    replace_qp = D0
                    for s in current_courses:
                        if s["status"] == "Retake" and s["prior_attempt_included"]:
                            replace_cr += dec(s["previous_credits"])
                            replace_qp += dec(s["previous_credits"]) * dec(s["previous_gp"])
                    if replace_cr > past_credits:
                        st.error("The credits marked for retake replacement exceed the completed credits.")
                    else:
                        adjusted_past_cr = past_credits - replace_cr
                        adjusted_past_qp = past_qp - replace_qp
                        if adjusted_past_qp < 0:
                            st.error("Retake replacement would make prior quality points negative.")
                        else:
                            total_cr = adjusted_past_cr + cur_cr
                            total_qp = adjusted_past_qp + cur_qp
                            current_after = total_qp / total_cr if total_cr else D0
                            st.metric("Current semester SGPA", f"{fmt(cur_sgpa)} / 4.00")
                            st.metric("CGPA after current semester", f"{fmt(current_after)} / 4.00")
                            m1, m2, m3 = st.columns(3)
                            m1.metric("Effective credits", fmt(total_cr))
                            m2.metric("Quality points", fmt(total_qp))
                            m3.metric("Credits replaced by retakes", fmt(replace_cr))
                            rows = [{"Stage": "After current semester", "Semester GPA": fmt(cur_sgpa), "Cumulative CGPA": fmt(current_after), "Total credits": fmt(total_cr)}]
                            running_cr, running_qp = total_cr, total_qp
                            for i, (p_sgpa, p_cr) in enumerate(projections, 1):
                                running_qp += p_sgpa * p_cr
                                running_cr += p_cr
                                rows.append({"Stage": f"Projected semester {i}", "Semester GPA": fmt(p_sgpa), "Cumulative CGPA": fmt(running_qp / running_cr), "Total credits": fmt(running_cr)})
                            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                            st.dataframe(pd.DataFrame([subject_row(s) for s in current_courses]), use_container_width=True, hide_index=True)
                            add_history("CGPA & Projection (Detailed)", {"current_sgpa": fmt(cur_sgpa), "cgpa_after_current": fmt(current_after), "effective_credits": fmt(total_cr), "quality_points": fmt(total_qp), "retake_replaced_credits": fmt(replace_cr), "projection": rows, "courses": [subject_row(s) for s in current_courses], "credits": fmt(total_cr)})
                            st.success("Calculation added to this session's history.")

        else:
            st.markdown("---")
            st.markdown("#### Step 2: Current Semester SGPA (Quick Mode)")
            st.info("💡 **Quick Mode Note:** Quick mode calculates your updated CGPA directly using your overall current SGPA and credit hours.")
            
            q1, q2 = st.columns(2)
            quick_sgpa_input = q1.number_input("Current semester SGPA (0.00–4.00)", min_value=0.0, max_value=4.0, value=3.00, step=0.01, key="quick_current_sgpa")
            quick_credits_input = q2.number_input("Current semester total credit hours", min_value=0.5, max_value=40.0, value=15.0, step=0.5, key="quick_current_credits")
            
            st.markdown("---")
            st.markdown("#### Step 3: Future Projections (Optional)")
            quick_project_count = int(st.number_input("Upcoming semesters to project", min_value=0, max_value=10, value=0, step=1, key="quick_projection_count"))
            quick_projections = []
            for i in range(quick_project_count):
                a, b = st.columns(2)
                qp_sgpa = a.number_input(f"Projected semester {i + 1} SGPA", min_value=0.0, max_value=4.0, value=3.0, step=0.01, key=f"quick_project_sgpa_{i}")
                qp_credits = b.number_input(f"Projected semester {i + 1} credits", min_value=0.5, max_value=40.0, value=15.0, step=0.5, key=f"quick_project_credits_{i}")
                quick_projections.append((dec(qp_sgpa), dec(qp_credits)))

            if st.button("Calculate CGPA & Projection (Quick)", type="primary", key="calculate_cgpa_quick"):
                cur_cr = dec(quick_credits_input)
                cur_sgpa = dec(quick_sgpa_input)
                cur_qp = cur_cr * cur_sgpa
                
                if cur_cr <= 0:
                    st.error("Current semester credit hours must be greater than zero.")
                else:
                    total_cr = past_credits + cur_cr
                    total_qp = past_qp + cur_qp
                    current_after = total_qp / total_cr if total_cr else D0
                    
                    st.metric("Current semester SGPA (Entered)", f"{fmt(cur_sgpa)} / 4.00")
                    st.metric("CGPA after current semester", f"{fmt(current_after)} / 4.00")
                    
                    m1, m2 = st.columns(2)
                    m1.metric("Cumulative effective credits", fmt(total_cr))
                    m2.metric("Cumulative quality points", fmt(total_qp))
                    
                    rows = [{"Stage": "After current semester", "Semester GPA": fmt(cur_sgpa), "Cumulative CGPA": fmt(current_after), "Total credits": fmt(total_cr)}]
                    running_cr, running_qp = total_cr, total_qp
                    for i, (p_sgpa, p_cr) in enumerate(quick_projections, 1):
                        running_qp += p_sgpa * p_cr
                        running_cr += p_cr
                        rows.append({"Stage": f"Projected semester {i}", "Semester GPA": fmt(p_sgpa), "Cumulative CGPA": fmt(running_qp / running_cr), "Total credits": fmt(running_cr)})
                    
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                    add_history("CGPA & Projection (Quick)", {"mode": "Quick", "current_sgpa": fmt(cur_sgpa), "cgpa_after_current": fmt(current_after), "effective_credits": fmt(total_cr), "quality_points": fmt(total_qp), "projection": rows, "credits": fmt(total_cr)})
                    st.success("Quick calculation added to this session's history.")

    with target_tab:
        st.subheader("Target SGPA / CGPA and course-level score planner")
        a, b = st.columns(2)
        target_mode = a.selectbox("Target type", ["Target SGPA this semester", "Target CGPA after this semester"], key="target_mode")
        completed_cr = b.number_input("Completed credit hours", min_value=0.0, max_value=300.0, value=0.0, step=0.5, key="target_past_credits")
        current_cgpa = st.number_input("Current CGPA (0.00–4.00)", min_value=0.0, max_value=4.0, value=0.0, step=0.01, key="target_current_cgpa")
        target_value = st.number_input("Desired target GPA (0.01–4.00)", min_value=0.01, max_value=4.0, value=3.5, step=0.01, key="target_value")
        st.markdown("#### Planned courses")
        plan_count = int(st.number_input("Number of planned courses", min_value=1, max_value=20, value=5, step=1, key="plan_count"))
        plan_courses = []
        for i in range(plan_count):
            a, b = st.columns([2, 1])
            name = a.text_input("Course name", value=f"Course {i + 1}", key=f"plan_name_{i}")
            credits = b.number_input("Credit hours", min_value=0.5, max_value=12.0, value=3.0, step=0.5, key=f"plan_credits_{i}")
            plan_courses.append({"name": name.strip() or f"Course {i + 1}", "credits": dec(credits)})
        require_pass = st.checkbox("Require at least a passing grade in every course", value=True, key="target_require_pass")
        if st.button("Build target plan", type="primary", key="build_target_plan"):
            semester_credits = sum((c["credits"] for c in plan_courses), D0)
            if semester_credits <= 0:
                st.error("Planned courses must have positive total credits.")
            else:
                if target_mode == "Target SGPA this semester":
                    required_sgpa = dec(target_value)
                else:
                    if completed_cr <= 0:
                        required_sgpa = dec(target_value)
                        st.info("No completed credits entered: the target CGPA is treated as the target SGPA for your first semester.")
                    else:
                        required_sgpa = (dec(target_value) * (dec(completed_cr) + semester_credits) - dec(current_cgpa) * dec(completed_cr)) / semester_credits
                if required_sgpa is not None:
                    st.metric("Required SGPA this semester", f"{fmt(required_sgpa)} / 4.00")
                    if required_sgpa <= 0:
                        st.success("Your existing academic standing already meets this target.")
                    elif required_sgpa > 4:
                        total_projected_credits = dec(completed_cr) + dec(semester_credits)
                        max_cgpa = (
                            (dec(current_cgpa) * dec(completed_cr) + D4 * dec(semester_credits))
                            / total_projected_credits
                            if total_projected_credits > D0
                            else D0
                        )
                        st.error("This target is mathematically impossible in one semester because the required SGPA exceeds 4.00.")
                        st.info(f"Maximum possible CGPA after this semester, assuming 4.00 SGPA: {fmt(max_cgpa)} / 4.00")
                    else:
                        plan, achieved_qp = build_efficient_plan(plan_courses, required_sgpa, require_pass=require_pass)
                        st.caption("The planner uses dynamic programming to find the minimum-sum normalized score plan.")
                        st.dataframe(pd.DataFrame(plan), use_container_width=True, hide_index=True)
                        planned_sgpa = achieved_qp / semester_credits
                        st.success(f"Plan's estimated SGPA: {fmt(planned_sgpa)} / 4.00")
                        
                        # Format planner items into courses list for individual export compatibility
                        planner_courses_rows = [{
                            "Course": p["Course"], "Credits": p["Credits"], "Input": "Target Plan", 
                            "Rounded %": "—", "Grade": p["Target Grade"], "Grade Point": p["Target GPA"], 
                            "Quality Points": fmt(dec(p["Credits"]) * dec(p["Target GPA"])), "Remarks": p["Minimum Required Score"]
                        } for p in plan]
                        add_history("Target GPA Plan", {"target_type": target_mode, "target": fmt(target_value), "required_sgpa": fmt(required_sgpa), "planned_sgpa": fmt(planned_sgpa), "courses": planner_courses_rows, "credits": fmt(semester_credits), "quality_points": fmt(achieved_qp)})

    with history_tab:
        st.subheader("Calculation history & Individual Exports")
        st.caption("Each calculation is saved below. You can download JSON, CSV, or download each calculation as its own separate PDF report with totals included.")
        if not st.session_state.history:
            st.info("No calculations have been saved in this session yet.")
        else:
            # Global Export Buttons
            st.markdown("#### Global Exports")
            g_col1, g_col2 = st.columns(2)
            with g_col1:
                json_data = json.dumps(st.session_state.history, indent=2, default=lambda x: str(x))
                st.download_button("📥 Download All History (JSON)", data=json_data, file_name="gpa_history.json", mime="application/json")
            with g_col2:
                csv_rows = []
                for item in st.session_state.history:
                    base = {k: v for k, v in item.items() if k not in ("courses", "projection")}
                    if item.get("courses"):
                        for course in item["courses"]:
                            csv_rows.append({**base, **course})
                    else:
                        csv_rows.append(base)
                st.download_button("📥 Download All History (CSV)", data=pd.DataFrame(csv_rows).to_csv(index=False), file_name="gpa_history.csv", mime="text/csv")
            
            st.markdown("---")
            st.markdown("#### Individual Calculation Reports")
            
            for idx, item in enumerate(st.session_state.history):
                timestamp = item.get("timestamp", "N/A")
                calc_type = item.get("type", "Calculation")
                summary_label = f"#{len(st.session_state.history) - idx} | {calc_type} ({timestamp})"
                if "sgpa" in item:
                    summary_label += f" — SGPA: {item['sgpa']}"
                elif "cgpa_after_current" in item:
                    summary_label += f" — CGPA After: {item['cgpa_after_current']}"
                
                with st.expander(summary_label):
                    st.write(f"**Type:** {calc_type}")
                    st.write(f"**Timestamp:** {timestamp}")
                    if "sgpa" in item:
                        st.write(f"**SGPA:** {item['sgpa']} | **Credits:** {item.get('credits', 'N/A')} | **Quality Points:** {item.get('quality_points', 'N/A')}")
                    elif "cgpa_after_current" in item:
                        st.write(f"**Current SGPA:** {item.get('current_sgpa', 'N/A')} | **CGPA After:** {item['cgpa_after_current']} | **Effective Credits:** {item.get('effective_credits', item.get('credits', 'N/A'))}")
                    
                    courses = item.get("courses", [])
                    if courses:
                        st.dataframe(pd.DataFrame(courses), use_container_width=True, hide_index=True)
                    
                    # Individual PDF Download Button for this specific item
                    pdf_bytes = generate_single_pdf_report(item)
                    safe_filename = f"gpa_report_{calc_type.lower().replace(' ', '_')}_{idx+1}.pdf"
                    st.download_button(
                        label=f"📄 Download PDF for Entry #{len(st.session_state.history) - idx}",
                        data=pdf_bytes,
                        file_name=safe_filename,
                        mime="application/pdf",
                        key=f"download_pdf_{idx}"
                    )

            if st.button("Clear session history", key="clear_history"):
                st.session_state.history = []
                st.rerun()

    with policy_tab:
        st.subheader("Ready Reckoner grading table")
        st.write("The mark conversion policy is intentionally preserved: exact percentage is converted to a whole percentage using ceiling rounding, so 64.01% becomes 65%.")
        grade_rows = [{"Rounded percentage": mark, "Grade point": fmt(gp), "Letter grade": letter, "Remarks": remarks} for mark, (gp, letter, remarks) in sorted(READY_RECKONER_TABLE.items())]
        st.dataframe(pd.DataFrame(grade_rows), use_container_width=True, hide_index=True)
        st.caption("For direct-GPA labs, 4.00 is labelled A+ for consistency.")
except Exception as error:
    st.error("The GPA calculator encountered an unexpected error. No result was produced for the failed operation.")
    with st.expander("Technical error details"):
        st.exception(error)