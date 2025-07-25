import re
import os
import uuid
import streamlit as st
import pandas as pd
from PIL import Image
from streamlit_drawable_canvas import st_canvas
from datetime import datetime

# --- File names & schema ---
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

# --- Coffee brands & models ---
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
# Alphabetize brands/models, Other last
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
    with st.form("new_customer_form"):
        cname   = st.text_input("Company Name*")
        contact = st.text_input("Contact Name*")
        addr    = st.text_input("Address* (e.g. 123 Main St, City)")
        phone   = st.text_input("Phone* (000-000-0000)")
        email   = st.text_input("Email* (you@example.com)")

        errors = []
        if not cname.strip():   errors.append("Company Name required.")
        if not contact.strip(): errors.append("Contact Name required.")
        if not re.match(r'.+\d+.+', addr) or len(addr.split())<3:
            errors.append("Enter a real address.")
        if not re.match(r'^\d{3}-\d{3}-\d{4}$', phone):
            errors.append("Phone must be 000-000-0000.")
        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
            errors.append("Enter a valid email.")

        if not errors:
            map_url = f"https://www.google.com/maps/search/{addr.replace(' ','+')}"
            st.markdown(f"[Preview on Google Maps]({map_url})")

        submitted = st.form_submit_button("Save Customer")
        if submitted and not errors:
            cid = str(uuid.uuid4())
            row = pd.DataFrame([{
                "ID": cid,
                "Company Name": cname,
                "Contact Name": contact,
                "Address": addr,
                "Phone": phone,
                "Email": email
            }])
            customers = pd.concat([customers, row], ignore_index=True)
            customers.to_csv(CUSTOMERS_FILE, index=False)
            st.success("Customer saved! Reload to select.")
            st.stop()

else:
    # -------------------- MACHINE FORM --------------------
    cid = customers.loc[customers["Company Name"] == sel_cust, "ID"].iat[0]
    cust_machines = machines[machines["Customer ID"] == cid]
    labels        = [f"{r.Brand} ({r.Model})" for _,r in cust_machines.iterrows()]
    ids           = cust_machines["ID"].tolist()

    # Session flags
    if "prev_machine"     not in st.session_state: st.session_state.prev_machine = None
    if "edit_machine"     not in st.session_state: st.session_state.edit_machine = False
    if "job_mode"         not in st.session_state: st.session_state.job_mode     = False

    # Choose or add
    if cust_machines.empty:
        st.info("No machines for this customer—add one below.")
        do_add = True
        selected_machine = None
    else:
        selected_machine = st.selectbox("Select machine", ["Add new..."] + labels)
        do_add = (selected_machine == "Add new...")

    # Reset modes when selection changes
    if selected_machine != st.session_state.prev_machine:
        st.session_state.prev_machine   = selected_machine
        st.session_state.edit_machine   = False
        st.session_state.job_mode       = False

    # --- ADD NEW MACHINE FORM ---
    if do_add:
        with st.form("add_machine_form"):
            st.info("Add a new machine")
            brand = st.selectbox("Brand*", [""]+brand_order, key="new_brand")
            custom_brand = st.text_input("Enter new brand*", key="new_custom_brand") if brand=="Other" else ""
            opts = coffee_brands.get(brand, ["Other"] if brand=="Other" else [])
            model = st.selectbox("Model*", [""]+opts, key="new_model")
            custom_model = st.text_input("Enter new model*", key="new_custom_model") if model=="Other" else ""
            year   = st.selectbox("Year*", [""]+[str(y) for y in years], key="new_year")
            serial = st.text_input("Serial Number (optional)", key="new_serial")
            obs    = st.text_area("Observations (optional)", key="new_obs")
            photo  = st.file_uploader("Upload machine photo*", type=["jpg","png"], key="new_photo")

            errs = []
            fb = custom_brand.strip() if brand=="Other" else brand
            fm = custom_model.strip() if model=="Other" else model
            if not fb: errs.append("Brand is required.")
            if not fm: errs.append("Model is required.")
            if not st.session_state.new_year: errs.append("Year is required.")
            if not photo: errs.append("Photo is required.")

            sub2 = st.form_submit_button("Save Machine")
            if sub2 and not errs:
                mid = str(uuid.uuid4())
                path = f"{mid}_machine.png"
                Image.open(photo).save(path)
                row = pd.DataFrame([{
                    "ID": mid,
                    "Customer ID": cid,
                    "Brand": fb,
                    "Model": fm,
                    "Year": st.session_state.new_year,
                    "Serial Number": serial,
                    "Photo Path": path,
                    "Observations": obs
                }])
                machines = pd.concat([machines, row], ignore_index=True)
                machines.to_csv(MACHINES_FILE, index=False)
                st.success("Machine saved! Reload to select.")
                st.stop()

    else:
        # --- VIEW DETAILS & Continue/Edit ---
        idx  = labels.index(selected_machine)
        mrow = cust_machines.iloc[idx]

        if not st.session_state.edit_machine and not st.session_state.job_mode:
            st.text_input("Brand", value=mrow.get("Brand",""), disabled=True)
            st.text_input("Model", value=mrow.get("Model",""), disabled=True)
            st.text_input("Year", value=mrow.get("Year",""), disabled=True)
            st.text_input("Serial Number", value=mrow.get("Serial Number",""), disabled=True)
            st.text_area("Observations", value=mrow.get("Observations",""), disabled=True)
            pp = mrow.get("Photo Path","")
            if isinstance(pp,str) and os.path.exists(pp):
                st.image(pp, caption="Machine Photo", width=200)
            c1,c2 = st.columns(2)
            if c1.button("Continue to Job"): st.session_state.job_mode = True
            if c2.button("Edit Machine"):   st.session_state.edit_machine = True

        # --- EDIT MACHINE FORM (active inputs) ---
        if st.session_state.edit_machine:
            with st.form("edit_machine_form"):
                st.info("Edit machine details")
                brand = st.selectbox(
                    "Brand*", [""]+brand_order,
                    index=(brand_order.index(mrow["Brand"])+1)
                          if mrow["Brand"] in brand_order else 0,
                    key="edit_brand"
                )
                cb = st.text_input("Enter new brand*", key="edit_custom_brand") if brand=="Other" else ""
                opts = coffee_brands.get(brand, ["Other"] if brand=="Other" else [])
                model = st.selectbox(
                    "Model*", [""]+opts,
                    index=(opts.index(mrow["Model"])+1) if mrow["Model"] in opts else 0,
                    key="edit_model"
                )
                cm = st.text_input("Enter new model*", key="edit_custom_model") if model=="Other" else ""
                year = st.selectbox(
                    "Year*", [""]+[str(y) for y in years],
                    index=(years.index(int(mrow["Year"]))+1)
                          if str(mrow["Year"]) in [str(y) for y in years] else 0,
                    key="edit_year"
                )
                serial = st.text_input(
                    "Serial Number (optional)",
                    value=mrow.get("Serial Number",""),
                    key="edit_serial"
                )
                obs = st.text_area(
                    "Observations (optional)",
                    value=mrow.get("Observations",""),
                    key="edit_obs"
                )
                photo = st.file_uploader(
                    "Upload new machine photo (leave empty to keep)",
                    type=["jpg","png"], key="edit_photo"
                )

                errs = []
                fb = cb.strip() if brand=="Other" else brand
                fm = cm.strip() if model=="Other" else model
                if not fb: errs.append("Brand is required.")
                if not fm: errs.append("Model is required.")
                if not st.session_state.edit_year: errs.append("Year is required.")

                sub3 = st.form_submit_button("Save Changes")
                if sub3 and not errs:
                    machines.loc[machines["ID"]==mrow["ID"],
                                 ["Brand","Model","Year","Serial Number","Observations"]] = [
                        fb, fm,
                        st.session_state.edit_year,
                        serial, obs
                    ]
                    if photo:
                        path = f"{mrow['ID']}_machine.png"
                        Image.open(photo).save(path)
                        machines.loc[machines["ID"]==mrow["ID"], "Photo Path"] = path
                    machines.to_csv(MACHINES_FILE, index=False)
                    st.success("Machine updated!")
                    st.session_state.edit_machine = False
                    st.experimental_rerun()

        # --- JOB FORM ---
        if st.session_state.job_mode and not st.session_state.edit_machine:
            st.subheader("Log a Job")
            with st.form("log_job_form"):
                employee   = st.text_input("Employee Name")
                technician = st.selectbox("Technician", ["Adonai Garcia","Miki Horvath"])
                job_date   = st.date_input("Date", datetime.now())
                travel     = st.number_input("Travel Time (min)", 0, step=1)
                t_in       = st.time_input("Time In")
                t_out      = st.time_input("Time Out")
                desc       = st.text_area("Job Description")
                parts      = st.text_area("Parts Used (optional)")
                comments   = st.text_area("Additional Comments (optional)")
                found      = st.file_uploader("Machine as Found", type=["jpg","png","mp4"])
                left       = st.file_uploader("Machine as Left", type=["jpg","png","mp4"])
                st.write("Draw signature:")
                sigimg     = st_canvas(
                                fill_color="rgba(255,255,255,1)",
                                stroke_width=2, stroke_color="#000",
                                background_color="#fff", height=100, width=300,
                                drawing_mode="freedraw", key="sig"
                            )

                submit_job = st.form_submit_button("Submit Job")
                if submit_job:
                    jid = str(uuid.uuid4())
                    sigpth = ""
                    if sigimg.image_data is not None:
                        im = Image.fromarray(sigimg.image_data)
                        sigpth = f"{jid}_signature.png"; im.save(sigpth)
                    fpth=""
                    if found:
                        ext=found.name.split(".")[-1]; fpth=f"{jid}_found.{ext}"
                        open(fpth,"wb").write(found.read())
                    lpth=""
                    if left:
                        ext=left.name.split(".")[-1]; lpth=f"{jid}_left.{ext}"
                        open(lpth,"wb").write(left.read())
                    newj = pd.DataFrame([{
                        "Job ID": jid, "Customer ID": cid, "Machine ID": mrow["ID"],
                        "Employee Name": employee, "Technician": technician,
                        "Date": str(job_date), "Travel Time (min)": int(travel),
                        "Time In": str(t_in), "Time Out": str(t_out),
                        "Job Description": desc, "Parts Used": parts,
                        "Additional Comments": comments,
                        "Machine as Found Path": fpth,
                        "Machine as Left Path": lpth,
                        "Signature Path": sigpth
                    }])
                    jobs = pd.concat([jobs, newj], ignore_index=True)
                    jobs.to_csv(JOBS_FILE, index=False)
                    st.success("Job logged successfully!")
                    st.markdown("### Preview")
                    st.write(f"Customer: {sel_cust}")
                    st.write(f"Machine: {selected_machine}")
                    st.write(f"Employee: {employee}")
                    st.write(f"Technician: {technician}")
                    st.write(f"Date: {job_date}")
                    st.write(f"Travel Time: {travel} min")
                    st.write(f"Time In: {t_in}  Time Out: {t_out}")
                    st.write(f"Job Description: {desc}")
                    if parts:    st.write(f"Parts Used: {parts}")
                    if comments: st.write(f"Additional Comments: {comments}")
                    if sigpth:   st.image(sigpth, caption="Signature", width=150)
                    if fpth and os.path.exists(fpth):
                        if fpth.endswith(".mp4"): st.video(fpth)
                        else: st.image(fpth, caption="Machine as Found", width=150)
                    if lpth and os.path.exists(lpth):
                        if lpth.endswith(".mp4"): st.video(lpth)
                        else: st.image(lpth, caption="Machine as Left", width=150)

# --- Admin Tabs ---
tab1, tab2, tab3 = st.tabs(["All Jobs","All Customers","All Machines"])
with tab1:
    st.header("All Job Logs");   st.dataframe(jobs)
with tab2:
    st.header("All Customers");  st.dataframe(customers)
with tab3:
    st.header("All Machines");   st.dataframe(machines)
