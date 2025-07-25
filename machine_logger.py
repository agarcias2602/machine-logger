import streamlit as st
import pandas as pd
import uuid
from PIL import Image
from streamlit_drawable_canvas import st_canvas
import os

# File names
CUSTOMERS_FILE = "customers.csv"
MACHINES_FILE = "machines.csv"
JOBS_FILE = "jobs.csv"

# Helpers to load or create CSVs
def load_df(filename, columns):
    if os.path.exists(filename):
        return pd.read_csv(filename)
    else:
        return pd.DataFrame(columns=columns)

customers = load_df(CUSTOMERS_FILE, ["ID", "Company Name", "Person in Charge", "Address", "Phone", "Email"])
machines = load_df(MACHINES_FILE, ["ID", "Customer ID", "Brand", "Model", "Year", "Photo Path", "Observations"])
jobs = load_df(JOBS_FILE, [
    "Job ID", "Customer ID", "Machine ID", "Employee", "Technician",
    "Description", "Checklist", "Signature Path", "Machine Photo Path"
])

st.title("Coffee Machine Service Logger")

### --- CUSTOMER MANAGEMENT ---
customer_options = customers["Company Name"].tolist()
selected_customer = st.selectbox("Select customer", ["Add new..."] + customer_options)

if selected_customer == "Add new...":
    with st.form("new_customer"):
        cname = st.text_input("Company Name")
        contact = st.text_input("Person in Charge")
        address = st.text_input("Address")
        phone = st.text_input("Phone")
        email = st.text_input("Email")
        submitted = st.form_submit_button("Save Customer")
        if submitted and cname:
            cid = str(uuid.uuid4())
            new_row = pd.DataFrame([{
                "ID": cid,
                "Company Name": cname,
                "Person in Charge": contact,
                "Address": address,
                "Phone": phone,
                "Email": email
            }])
            customers = pd.concat([customers, new_row], ignore_index=True)
            customers.to_csv(CUSTOMERS_FILE, index=False)
            st.success("Customer saved! Please reload to select.")
            st.stop()  # Prevent rest of form from loading

else:
    # --- MACHINE MANAGEMENT ---
    customer_id = customers[customers["Company Name"] == selected_customer]["ID"].values[0]
    machines_for_customer = machines[machines["Customer ID"] == customer_id]
    machine_labels = [f"{row.Brand} ({row.Model})" for _, row in machines_for_customer.iterrows()]
    machine_ids = machines_for_customer["ID"].tolist()
    selected_machine_label = st.selectbox("Select machine", ["Add new..."] + machine_labels)

    if selected_machine_label == "Add new...":
        with st.form("new_machine"):
            brand = st.text_input("Brand")
            model = st.text_input("Model")
            year = st.text_input("Year")
            obs = st.text_area("Observations")
            photo = st.file_uploader("Upload machine photo", type=["jpg", "jpeg", "png"])
            submitted = st.form_submit_button("Save Machine")
            if submitted and brand and model:
                mid = str(uuid.uuid4())
                photo_path = ""
                if photo:
                    img = Image.open(photo)
                    photo_path = f"{mid}_machine.png"
                    img.save(photo_path)
                new_machine_row = pd.DataFrame([{
                    "ID": mid,
                    "Customer ID": customer_id,
                    "Brand": brand,
                    "Model": model,
                    "Year": year,
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

        # --- JOB LOGGING FORM ---
        st.subheader("Log a Job")

        with st.form("log_job"):
            employee = st.text_input("Employee Name")
            technician = st.selectbox("Technician", ["Adonai Garcia", "Miki Horvath"])
            desc = st.text_area("Job Description")
            checklist = st.multiselect("Checklist", [
                "Brew group cleaned",
                "Grinder cleaned",
                "Descaled",
                "Tested all functions",
                "Checked/cleaned filters",
                "Inspected seals/hoses",
                "Updated software",
                "Checked for leaks",
                "Wiped down exterior"
            ])
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
            machine_photo = st.file_uploader("Upload new machine photo (optional)", type=["jpg", "jpeg", "png"])

            submitted = st.form_submit_button("Submit Job")
            if submitted and employee and technician:
                job_id = str(uuid.uuid4())
                sig_path = ""
                if signature_image.image_data is not None:
                    sig_img = Image.fromarray(signature_image.image_data)
                    sig_path = f"{job_id}_signature.png"
                    sig_img.save(sig_path)
                photo_path = ""
                if machine_photo:
                    img = Image.open(machine_photo)
                    photo_path = f"{job_id}_jobmachine.png"
                    img.save(photo_path)
                new_job_row = pd.DataFrame([{
                    "Job ID": job_id,
                    "Customer ID": customer_id,
                    "Machine ID": selected_machine_id,
                    "Employee": employee,
                    "Technician": technician,
                    "Description": desc,
                    "Checklist": ";".join(checklist),
                    "Signature Path": sig_path,
                    "Machine Photo Path": photo_path
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
                st.write(f"Description: {desc}")
                st.write(f"Checklist: {', '.join(checklist)}")
                if sig_path:
                    st.image(sig_path, caption="Signature", width=150)
                if photo_path:
                    st.image(photo_path, caption="Machine Photo", width=150)
