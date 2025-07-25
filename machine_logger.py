import re
import streamlit as st
import pandas as pd
import uuid
from PIL import Image
from streamlit_drawable_canvas import st_canvas
import os
from datetime import datetime

# --- File names and columns ---
CUSTOMERS_FILE = "customers.csv"
MACHINES_FILE = "machines.csv"
JOBS_FILE = "jobs.csv"

CUSTOMERS_COLUMNS = ["ID", "Company Name", "Contact Name", "Address", "Phone", "Email"]
MACHINES_COLUMNS = ["ID", "Customer ID", "Brand", "Model", "Year", "Serial Number", "Photo Path", "Observations"]
JOBS_COLUMNS = [
    "Job ID", "Customer ID", "Machine ID", "Employee Name", "Technician",
    "Date", "Travel Time (min)", "Time In", "Time Out", "Job Description",
    "Parts Used", "Additional Comments",
    "Machine as Found Path", "Machine as Left Path", "Signature Path"
]

def load_df(filename, columns):
    if os.path.exists(filename):
        return pd.read_csv(filename)
    else:
        return pd.DataFrame(columns=columns)

customers = load_df(CUSTOMERS_FILE, CUSTOMERS_COLUMNS)
machines = load_df(MACHINES_FILE, MACHINES_COLUMNS)
jobs = load_df(JOBS_FILE, JOBS_COLUMNS)

st.title("Coffee Machine Service Logger")

# ------------------ Coffee brands and models ------------------
coffee_brands = {
    "Bezzera": ["BZ10", "Magica", "Matrix", "DUO", "Mitica"],
    "Breville": ["Barista Express", "Barista Pro", "Oracle Touch", "Duo Temp", "Infuser"],
    "Carimali": ["Armonia Ultra", "BlueDot", "CA1000", "Optima", "SolarTouch"],
    "Cimbali": ["M21 Junior", "M39", "M100", "M200", "S20"],
    "DeLonghi": ["Dedica", "Dinamica", "Eletta", "La Specialista", "Magnifica", "Primadonna"],
    "ECM": ["Barista", "Classika", "Elektronika", "Synchronika", "Technika"],
    "Faema": ["E61", "Emblema", "E98 UP", "Teorema", "X30"],
    "Franke": ["A300", "A600", "A800", "S200", "S700"],
    "Gaggia": ["Accademia", "Anima", "Babila", "Cadorna", "Classic"],
    "Jura": ["ENA 8", "Giga X8", "Impressa XJ9", "WE8", "Z10"],
    "Krups": ["EA82", "EA89", "Evidence", "Essential", "Quattro Force"],
    "La Marzocco": ["GB5", "GS3", "Linea Mini", "Linea PB", "Strada"],
    "La Spaziale": ["Dream", "S1 Mini Vivaldi II", "S2", "S8", "S9"],
    "Miele": ["CM5300", "CM6150", "CM6350", "CM6360", "CM7750"],
    "Nuova Simonelli": ["Appia", "Aurelia", "Musica", "Oscar", "Talento"],
    "Philips": ["2200 Series", "3200 Series", "5000 Series", "LatteGo", "Saeco Xelsis"],
    "Quick Mill": ["Alexia", "Andreja", "Pegaso", "Silvano", "Vetrano"],
    "Rancilio": ["Classe 11", "Classe 5", "Classe 9", "Egro One", "Silvia"],
    "Rocket Espresso": ["Appartamento", "Cronometro", "Giotto", "Mozzafiato", "R58"],
    "Saeco": ["Aulika", "Incanto", "Lirika", "PicoBaristo", "Royal"],
    "Schaerer": ["Coffee Art Plus", "Coffee Club", "Prime", "Soul", "Touch"],
    "Siemens": ["EQ.3", "EQ.6", "EQ.9", "Surpresso", "TE653"],
    "Victoria Arduino": ["Adonis", "Black Eagle", "Eagle One", "Mythos One", "Venus"],
    "WMF": ["1100 S", "1500 S+", "5000 S+", "9000 S+", "Espresso"],
    "Other": ["Other"]
}
# Alphabetize brands (except "Other" last) and models
brands_no_other = sorted([b for b in coffee_brands if b != "Other"])
brand_list_ordered = brands_no_other + ["Other"]
for k in coffee_brands:
    if "Other" in coffee_brands[k]:
        ms = sorted([m for m in coffee_brands[k] if m != "Other"]) + ["Other"]
        coffee_brands[k] = ms
    else:
        coffee_brands[k] = sorted(coffee_brands[k])

current_year = datetime.now().year
years = list(range(1970, current_year + 1))[::-1]  # latest year first

# -------------------- CUSTOMER FORM --------------------
customer_options = customers["Company Name"].tolist()
selected_customer = st.selectbox("Select customer", ["Add new..."] + customer_options)

if selected_customer == "Add new...":
    with st.form("new_customer"):
        cname = st.text_input("Company Name*")
        contact = st.text_input("Contact Name*")
        address = st.text_input("Address* (e.g. 123 Main St, City)")
        phone = st.text_input("Phone* (000-000-0000)")
        email = st.text_input("Email* (you@example.com)")

        # --- Validation ---
        errors = []
        if cname.strip() == "":
            errors.append("Company Name is required.")
        if contact.strip() == "":
            errors.append("Contact Name is required.")
        if not re.match(r'.+\d+.+', address) or len(address.split()) < 3:
            errors.append("Please enter a real address (e.g. 123 Main St, City).")
        if not re.match(r'^\d{3}-\d{3}-\d{4}$', phone):
            errors.append("Phone must be in format 000-000-0000.")
        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
            errors.append("Enter a valid email address (e.g. you@email.com).")

        map_url = ""
        if len(errors) == 0:
            map_url = f"https://www.google.com/maps/search/{address.replace(' ', '+')}"
            st.markdown(f"**[Preview on Google Maps]({map_url})**")

        submitted = st.form_submit_button("Save Customer")

        if submitted:
            if errors:
                st.error("\n".join(errors))
            else:
                cid = str(uuid.uuid4())
                new_row = pd.DataFrame([{
                    "ID": cid,
                    "Company Name": cname,
                    "Contact Name": contact,
                    "Address": address,
                    "Phone": phone,
                    "Email": email
                }])
                customers = pd.concat([customers, new_row], ignore_index=True)
                customers.to_csv(CUSTOMERS_FILE, index=False)
                st.success("Customer saved! Please reload to select.")
                st.stop()  # Prevent rest of form from loading

else:
    # -------------------- MACHINE FORM --------------------
    customer_id = customers[customers["Company Name"] == selected_customer]["ID"].values[0]
    machines_for_customer = machines[machines["Customer ID"] == customer_id]
    machine_labels = [f"{row.Brand} ({row.Model})" for _, row in machines_for_customer.iterrows()]
    machine_ids = machines_for_customer["ID"].tolist()
    selected_machine_label = st.selectbox("Select machine", ["Add new..."] + machine_labels)

    if selected_machine_label == "Add new...":
        if "selected_brand" not in st.session_state:
            st.session_state.selected_brand = ""
        if "selected_model" not in st.session_state:
            st.session_state.selected_model = ""
        if "custom_brand" not in st.session_state:
            st.session_state.custom_brand = ""
        if "custom_model" not in st.session_state:
            st.session_state.custom_model = ""

        def reset_model_custom():
            st.session_state.selected_model = ""
            st.session_state.custom_model = ""

        with st.form("new_machine"):
            # Brand select (blank default, "Other" last)
            brand = st.selectbox(
                "Brand*", 
                [""] + brand_list_ordered, 
                index=0 if st.session_state.selected_brand == "" else brand_list_ordered.index(st.session_state.selected_brand)+1,
                key="brand_select", 
                on_change=reset_model_custom
            )
            custom_brand = ""
            if brand == "Other":
                custom_brand = st.text_input("Enter new brand*", key="custom_brand")
            else:
                st.session_state.custom_brand = ""

            # Model dynamic select (blank default, "Other" last)
            model_options = []
            if brand and brand in coffee_brands:
                models_no_other = sorted([m for m in coffee_brands[brand] if m != "Other"])
                model_options = models_no_other + (["Other"] if "Other" in coffee_brands[brand] else [])
            elif brand == "Other":
                model_options = ["Other"]  # Only "Other" for brand Other

            model = st.selectbox(
                "Model*", 
                [""] + model_options, 
                index=0 if st.session_state.selected_model == "" else model_options.index(st.session_state.selected_model)+1 if st.session_state.selected_model in model_options else 0,
                key="model_select"
            )
            custom_model = ""
            if model == "Other":
                custom_model = st.text_input("Enter new model*", key="custom_model")
            else:
                st.session_state.custom_model = ""

            year = st.selectbox("Year*", [""] + [str(y) for y in years])
            serial = st.text_input("Serial Number (optional)")
            obs = st.text_area("Observations (optional)")
            photo = st.file_uploader("Upload machine photo*", type=["jpg", "jpeg", "png"])

            errors = []
            # Require brand or custom_brand
            final_brand = brand
            if not brand:
                errors.append("Brand is required.")
            elif brand == "Other" and not custom_brand.strip():
                errors.append("Please enter a new brand.")
            elif brand == "Other":
                final_brand = custom_brand.strip()

            # Require model or custom_model
            final_model = model
            if not model:
                errors.append("Model is required.")
            elif model == "Other" and not custom_model.strip():
                errors.append("Please enter a new model.")
            elif model == "Other":
                final_model = custom_model.strip()

            if not year:
                errors.append("Year is required.")
            if not photo:
                errors.append("Photo is required.")

            submitted = st.form_submit_button("Save Machine")
            if submitted:
                if errors:
                    st.error("\n".join(errors))
                else:
                    mid = str(uuid.uuid4())
                    photo_path = ""
                    if photo:
                        img = Image.open(photo)
                        photo_path = f"{mid}_machine.png"
                        img.save(photo_path)
                    new_machine_row = pd.DataFrame([{
                        "ID": mid,
                        "Customer ID": customer_id,
                        "Brand": final_brand,
                        "Model": final_model,
                        "Year": year,
                        "Serial Number": serial,
                        "Photo Path": photo_path,
                        "Observations": obs
                    }])
                    machines = pd.concat([machines, new_machine_row], ignore_index=True)
                    machines.to_csv(MACHINES_FILE, index=False)
                    st.success("Machine saved! Please reload to select.")
                    st.stop()
    elif machine_labels:
        idx = machine_labels.index(selected_machine_label)
        selected_machine_id = machine_ids[idx]

        # -------------------- JOB FORM --------------------
        st.subheader("Log a Job")

        with st.form("log_job"):
            employee = st.text_input("Employee Name")
            technician = st.selectbox("Technician", ["Adonai Garcia", "Miki Horvath"])
            job_date = st.date_input("Date", datetime.now())
            travel_time = st.number_input("Travel Time (minutes)", min_value=0, step=1)
            time_in = st.time_input("Time In")
            time_out = st.time_input("Time Out")
            desc = st.text_area("Job Description")
            parts = st.text_area("Parts Used (optional)", placeholder="Describe parts used, if any...")
            comments = st.text_area("Additional Comments (optional)")
            machine_found = st.file_uploader("Machine as Found (upload photo/video)", type=["jpg", "jpeg", "png", "mp4"])
            machine_left = st.file_uploader("Machine as Left (upload photo/video)", type=["jpg", "jpeg", "png", "mp4"])
            st.write("Draw signature below then click Submit:")
            signature_image = st_canvas(
                fill_color="rgba(255,255,255,1)",
                stroke_width=2,
                stroke_color="#000",
                background_color="#fff",
                height=100,
                width=300,
                drawing_mode="freedraw",
                key="signature"
            )

            submitted = st.form_submit_button("Submit Job")
            required_fields = all([
                employee, technician, job_date, travel_time, time_in, time_out, desc
            ])
            if submitted and required_fields:
                job_id = str(uuid.uuid4())
                sig_path = ""
                if signature_image.image_data is not None:
                    sig_img = Image.fromarray(signature_image.image_data)
                    sig_path = f"{job_id}_signature.png"
                    sig_img.save(sig_path)
                found_path = ""
                if machine_found:
                    ext = machine_found.name.split(".")[-1].lower()
                    found_path = f"{job_id}_found.{ext}"
                    with open(found_path, "wb") as f:
                        f.write(machine_found.read())
                left_path = ""
                if machine_left:
                    ext = machine_left.name.split(".")[-1].lower()
                    left_path = f"{job_id}_left.{ext}"
                    with open(left_path, "wb") as f:
                        f.write(machine_left.read())
                new_job_row = pd.DataFrame([{
                    "Job ID": job_id,
                    "Customer ID": customer_id,
                    "Machine ID": selected_machine_id,
                    "Employee Name": employee,
                    "Technician": technician,
                    "Date": str(job_date),
                    "Travel Time (min)": int(travel_time),
                    "Time In": str(time_in),
                    "Time Out": str(time_out),
                    "Job Description": desc,
                    "Parts Used": parts,
                    "Additional Comments": comments,
                    "Machine as Found Path": found_path,
                    "Machine as Left Path": left_path,
                    "Signature Path": sig_path
                }])
                jobs = pd.concat([jobs, new_job_row], ignore_index=True)
                jobs.to_csv(JOBS_FILE, index=False)
                st.success("Job logged successfully!")

                # Show preview
                st.markdown("### Preview")
                st.write(f"Customer: {selected_customer}")
                st.write(f"Machine: {selected_machine_label}")
                st.write(f"Employee: {employee}")
                st.write(f"Technician: {technician}")
                st.write(f"Date: {job_date}")
                st.write(f"Travel Time: {travel_time} min")
                st.write(f"Time In: {time_in}")
                st.write(f"Time Out: {time_out}")
                st.write(f"Job Description: {desc}")
                if parts: st.write(f"Parts Used: {parts}")
                if comments: st.write(f"Additional Comments: {comments}")
                if sig_path:
                    st.image(sig_path, caption="Signature", width=150)
                if found_path and os.path.exists(found_path):
                    if found_path.endswith(".mp4"):
                        st.video(found_path, format="video/mp4")
                    else:
                        st.image(found_path, caption="Machine as Found", width=150)
                if left_path and os.path.exists(left_path):
                    if left_path.endswith(".mp4"):
                        st.video(left_path, format="video/mp4")
                    else:
                        st.image(left_path, caption="Machine as Left", width=150)

# --- At the very END of your file ---

tab1, tab2, tab3 = st.tabs(["All Jobs", "All Customers", "All Machines"])

with tab1:
    st.header("All Job Logs")
    st.dataframe(jobs)
    # Show images/videos for last job as an example
    if not jobs.empty:
        last = jobs.iloc[-1]
        sig_path = last.get("Signature Path", "")
        if isinstance(sig_path, str) and sig_path and os.path.exists(sig_path):
            st.image(sig_path, caption="Last Job Signature", width=200)
        found_path = last.get("Machine as Found Path", "")
        if isinstance(found_path, str) and found_path and os.path.exists(found_path):
            if found_path.endswith(".mp4"):
                st.video(found_path, format="video/mp4")
            else:
                st.image(found_path, caption="Machine as Found", width=200)
        left_path = last.get("Machine as Left Path", "")
        if isinstance(left_path, str) and left_path and os.path.exists(left_path):
            if left_path.endswith(".mp4"):
                st.video(left_path, format="video/mp4")
            else:
                st.image(left_path, caption="Machine as Left", width=200)

with tab2:
    st.header("All Customers")
    st.dataframe(customers)

with tab3:
    st.header("All Machines")
    st.dataframe(machines)
