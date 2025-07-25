import re
import streamlit as st
import pandas as pd
import uuid
from PIL import Image
from streamlit_drawable_canvas import st_canvas
import os
from datetime import datetime

# --- File names & columns ---
CUSTOMERS_FILE = "customers.csv"
MACHINES_FILE  = "machines.csv"
JOBS_FILE      = "jobs.csv"

CUSTOMERS_COLUMNS = ["ID","Company Name","Contact Name","Address","Phone","Email"]
MACHINES_COLUMNS  = ["ID","Customer ID","Brand","Model","Year","Serial Number","Photo Path","Observations"]
JOBS_COLUMNS      = [
    "Job ID","Customer ID","Machine ID","Employee Name","Technician",
    "Date","Travel Time (min)","Time In","Time Out","Job Description",
    "Parts Used","Additional Comments",
    "Machine as Found Path","Machine as Left Path","Signature Path"
]

def load_df(path, cols):
    return pd.read_csv(path) if os.path.exists(path) else pd.DataFrame(columns=cols)

customers = load_df(CUSTOMERS_FILE, CUSTOMERS_COLUMNS)
machines  = load_df(MACHINES_FILE,  MACHINES_COLUMNS)
jobs      = load_df(JOBS_FILE,      JOBS_COLUMNS)

st.title("Coffee Machine Service Logger")

# --- Brands & Models Data ---
coffee_brands = {
    "Bezzera": ["BZ10","DUO","Magica","Matrix","Mitica"],
    "Breville": ["Barista Express","Barista Pro","Duo Temp","Infuser","Oracle Touch"],
    "Carimali": ["Armonia Ultra","BlueDot","CA1000","Optima","SolarTouch"],
    "Cimbali": ["M21 Junior","M39","M100","M200","S20"],
    "DeLonghi": ["Dedica","Dinamica","Eletta","La Specialista","Magnifica","Primadonna"],
    "ECM": ["Barista","Classika","Elektronika","Synchronika","Technika"],
    "Faema": ["E61","Emblema","E98 UP","Teorema","X30"],
    "Franke": ["A300","A600","A800","S200","S700"],
    "Gaggia": ["Accademia","Anima","Babila","Cadorna","Classic"],
    "Jura": ["ENA 8","Giga X8","Impressa XJ9","WE8","Z10"],
    "Krups": ["EA82","EA89","Evidence","Essential","Quattro Force"],
    "La Marzocco": ["GB5","GS3","Linea Mini","Linea PB","Strada"],
    "La Spaziale": ["Dream","S1 Mini Vivaldi II","S2","S8","S9"],
    "Miele": ["CM5300","CM6150","CM6350","CM6360","CM7750"],
    "Nuova Simonelli": ["Appia","Aurelia","Musica","Oscar","Talento"],
    "Philips": ["2200 Series","3200 Series","5000 Series","LatteGo","Saeco Xelsis"],
    "Quick Mill": ["Alexia","Andreja","Pegaso","Silvano","Vetrano"],
    "Rancilio": ["Classe 11","Classe 5","Classe 9","Egro One","Silvia"],
    "Rocket Espresso": ["Appartamento","Cronometro","Giotto","Mozzafiato","R58"],
    "Saeco": ["Aulika","Incanto","Lirika","PicoBaristo","Royal"],
    "Schaerer": ["Coffee Art Plus","Coffee Club","Prime","Soul","Touch"],
    "Siemens": ["EQ.3","EQ.6","EQ.9","Surpresso","TE653"],
    "Victoria Arduino": ["Adonis","Black Eagle","Eagle One","Mythos One","Venus"],
    "WMF": ["1100 S","1500 S+","5000 S+","9000 S+","Espresso"],
    "Other": ["Other"]
}
brands_no_other = sorted([b for b in coffee_brands if b!="Other"])
brand_order     = brands_no_other + ["Other"]
for b in coffee_brands:
    ms = sorted([m for m in coffee_brands[b] if m!="Other"])
    if "Other" in coffee_brands[b]:
        ms.append("Other")
    coffee_brands[b] = ms

# Year options
current_year = datetime.now().year
years = list(range(1970, current_year+1))[::-1]

# -------------------- CUSTOMER FORM --------------------
cust_names = customers["Company Name"].tolist()
sel_cust   = st.selectbox("Select customer", ["Add new..."] + cust_names)

if sel_cust == "Add new...":
    with st.form("new_customer"):
        cname   = st.text_input("Company Name*")
        contact = st.text_input("Contact Name*")
        addr    = st.text_input("Address* (e.g. 123 Main St, City)")
        phone   = st.text_input("Phone* (000-000-0000)")
        email   = st.text_input("Email* (you@example.com)")

        errs = []
        if not cname.strip(): errs.append("Company Name required.")
        if not contact.strip(): errs.append("Contact Name required.")
        if not re.match(r'.+\d+.+', addr) or len(addr.split())<3:
            errs.append("Enter a real address.")
        if not re.match(r'^\d{3}-\d{3}-\d{4}$', phone):
            errs.append("Phone must be 000-000-0000.")
        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
            errs.append("Enter a valid email.")

        if not errs:
            map_url = f"https://www.google.com/maps/search/{addr.replace(' ','+')}"
            st.markdown(f"[Preview on Google Maps]({map_url})")

        submitted = st.form_submit_button("Save Customer")
        if submitted and not errs:
            cid = str(uuid.uuid4())
            new = pd.DataFrame([{
                "ID": cid,
                "Company Name": cname,
                "Contact Name": contact,
                "Address": addr,
                "Phone": phone,
                "Email": email
            }])
            customers = pd.concat([customers, new], ignore_index=True)
            customers.to_csv(CUSTOMERS_FILE, index=False)
            st.success("Customer saved! Reload to select.")
            st.stop()

else:
    # --- VIEW SELECTED CUSTOMER INFO ---
    cust_row = customers.loc[customers["Company Name"] == sel_cust].iloc[0]
    st.subheader("Customer Information")
    st.text_input("Company Name", value=cust_row.get("Company Name",""), disabled=True)
    st.text_input("Contact Name", value=cust_row.get("Contact Name",""), disabled=True)
    st.text_input("Address",      value=cust_row.get("Address",""),      disabled=True)
    st.text_input("Phone",        value=cust_row.get("Phone",""),        disabled=True)
    st.text_input("Email",        value=cust_row.get("Email",""),        disabled=True)

    # -------------------- MACHINE FORM --------------------
    customer_id    = cust_row["ID"]
    existing       = machines[machines["Customer ID"] == customer_id]
    machine_labels = [f"{r.Brand} ({r.Model})" for _, r in existing.iterrows()]
    machine_ids    = existing["ID"].tolist()

    selected_label = st.selectbox("Select machine", ["Add new..."] + machine_labels)

    if selected_label == "Add new...":
        # --- BRAND & MODEL SELECTORS outside the form ---
        for key in ("brand_select","prev_brand","model_select","custom_brand","custom_model"):
            if key not in st.session_state:
                st.session_state[key] = ""

        brand = st.selectbox(
            "Brand*",
            [""] + brand_order,
            key="brand_select"
        )
        if brand != st.session_state.prev_brand:
            st.session_state.prev_brand     = brand
            st.session_state.model_select   = ""
            st.session_state.custom_model   = ""
            st.session_state.custom_brand   = ""

        custom_brand = ""
        if brand == "Other":
            custom_brand = st.text_input("Enter new brand*", key="custom_brand")

        model_opts = coffee_brands.get(brand, ["Other"] if brand=="Other" else [])
        model = st.selectbox(
            "Model*",
            [""] + model_opts,
            key="model_select"
        )
        custom_model = ""
        if model == "Other":
            custom_model = st.text_input("Enter new model*", key="custom_model")

        # --- REST OF FORM ---
        with st.form("new_machine"):
            year   = st.selectbox("Year*", [""] + [str(y) for y in years], key="year")
            serial = st.text_input("Serial Number (optional)", key="serial")
            obs    = st.text_area("Observations (optional)", key="obs")
            photo  = st.file_uploader("Machine photo*", type=["jpg","png"], key="photo")

            errs=[]
            final_brand = custom_brand.strip() if brand=="Other" else brand
            final_model = custom_model.strip()  if model=="Other" else model
            if not final_brand: errs.append("Brand is required.")
            if not final_model: errs.append("Model is required.")
            if not st.session_state.year: errs.append("Year is required.")
            if not photo: errs.append("Photo is required.")

            submitted = st.form_submit_button("Save Machine")
            if submitted:
                if errs:
                    st.error("\n".join(errs))
                else:
                    mid = str(uuid.uuid4())
                    path = f"{mid}_machine.png"
                    Image.open(photo).save(path)
                    row = pd.DataFrame([{
                        "ID": mid,
                        "Customer ID": customer_id,
                        "Brand": final_brand,
                        "Model": final_model,
                        "Year": st.session_state.year,
                        "Serial Number": serial,
                        "Photo Path": path,
                        "Observations": obs
                    }])
                    machines = pd.concat([machines, row], ignore_index=True)
                    machines.to_csv(MACHINES_FILE, index=False)
                    st.success("Machine saved! Reload to select.")
                    st.stop()

    else:
        # --- VIEW MACHINE INFO ---
        idx  = machine_labels.index(selected_label)
        mrow = existing.iloc[idx]

        st.subheader("Machine Information")
        st.text_input("Brand",         value=mrow.get("Brand",""),         disabled=True)
        st.text_input("Model",         value=mrow.get("Model",""),         disabled=True)
        st.text_input("Year",          value=mrow.get("Year",""),          disabled=True)
        st.text_input("Serial Number", value=mrow.get("Serial Number",""), disabled=True)
        st.text_area("Observations",    value=mrow.get("Observations",""),  disabled=True)
        photo_path = mrow.get("Photo Path","")
        if isinstance(photo_path, str) and os.path.exists(photo_path):
            st.image(photo_path, caption="Machine Photo", width=200)

        # --- JOB LOGGING FORM ---
        st.subheader("Log a Job")
        with st.form("log_job"):
            employee   = st.text_input("Employee Name")
            technician = st.selectbox("Technician", ["Adonai Garcia","Miki Horvath"])
            job_date   = st.date_input("Date", datetime.now())
            travel     = st.number_input("Travel Time (min)", 0, step=1)
            time_in    = st.time_input("Time In")
            time_out   = st.time_input("Time Out")
            desc       = st.text_area("Job Description")
            parts      = st.text_area("Parts Used (optional)")
            comments   = st.text_area("Additional Comments (optional)")
            found      = st.file_uploader("Machine as Found", type=["jpg","png","mp4"])
            left       = st.file_uploader("Machine as Left",  type=["jpg","png","mp4"])
            sigimg     = st_canvas(
                            fill_color="rgba(255,255,255,1)",
                            stroke_width=2, stroke_color="#000",
                            background_color="#fff", height=100, width=300,
                            drawing_mode="freedraw", key="signature"
                         )

            submitted = st.form_submit_button("Submit Job")
            if submitted and all([employee, technician, job_date, travel, time_in, time_out, desc]):
                jid = str(uuid.uuid4())
                sig_path = ""
                if sigimg.image_data is not None:
                    im = Image.fromarray(sigimg.image_data)
                    sig_path = f"{jid}_signature.png"; im.save(sig_path)

                fpath = ""
                if found:
                    ext = found.name.rsplit(".",1)[-1]
                    fpath = f"{jid}_found.{ext}"
                    open(fpath,"wb").write(found.read())

                lpath = ""
                if left:
                    ext = left.name.rsplit(".",1)[-1]
                    lpath = f"{jid}_left.{ext}"
                    open(lpath,"wb").write(left.read())

                new_job = pd.DataFrame([{
                    "Job ID": jid,
                    "Customer ID": customer_id,
                    "Machine ID": machine_ids[idx],
                    "Employee Name": employee,
                    "Technician": technician,
                    "Date": str(job_date),
                    "Travel Time (min)": int(travel),
                    "Time In": str(time_in),
                    "Time Out": str(time_out),
                    "Job Description": desc,
                    "Parts Used": parts,
                    "Additional Comments": comments,
                    "Machine as Found Path": fpath,
                    "Machine as Left Path": lpath,
                    "Signature Path": sig_path
                }])
                jobs = pd.concat([jobs, new_job], ignore_index=True)
                jobs.to_csv(JOBS_FILE, index=False)
                st.success("Job logged successfully!")

                st.markdown("### Preview")
                st.write(f"Customer: {sel_cust}")
                st.write(f"Machine: {selected_label}")
                st.write(f"Employee: {employee}")
                st.write(f"Technician: {technician}")
                st.write(f"Date: {job_date}")
                st.write(f"Travel Time: {travel} min")
                st.write(f"Time In: {time_in}  Time Out: {time_out}")
                st.write(f"Job Description: {desc}")
                if parts:    st.write(f"Parts Used: {parts}")
                if comments: st.write(f"Additional Comments: {comments}")
                if sig_path: st.image(sig_path, caption="Signature", width=150)
                if fpath and os.path.exists(fpath):
                    if fpath.endswith(".mp4"): st.video(fpath)
                    else:                      st.image(fpath, caption="Found", width=150)
                if lpath and os.path.exists(lpath):
                    if lpath.endswith(".mp4"): st.video(lpath)
                    else:                      st.image(lpath, caption="Left", width=150)

# --- Admin Tabs ---
tab1,tab2,tab3 = st.tabs(["All Jobs","All Customers","All Machines"])
with tab1:
    st.header("All Job Logs");      st.dataframe(jobs)
with tab2:
    st.header("All Customers");     st.dataframe(customers)
with tab3:
    st.header("All Machines");      st.dataframe(machines)
