import re
import os
import uuid
import smtplib
import mimetypes
import streamlit as st
import pandas as pd
from PIL import Image
from datetime import datetime
from email import encoders
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from streamlit_drawable_canvas import st_canvas

# --- Files & schema ---
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

# --- Email helper with attachments and proper multipart/alternative nesting ---
def send_job_email(job_id, cust_email, html_body, sig_path, left_path):
    sender      = st.secrets["email"]["user"]
    password    = st.secrets["email"]["password"]
    smtp_server = st.secrets["email"]["smtp_server"]
    smtp_port   = st.secrets["email"]["smtp_port"]
    recipients  = ["mhunter4coffee@gmail.com"]
    if cust_email:
        recipients.append(cust_email)

    # Outer mixed container
    msg = MIMEMultipart("mixed")
    msg["Subject"] = f"Service Job Confirmation – {job_id}"
    msg["From"]    = sender
    msg["To"]      = ", ".join(recipients)

    # Create the alternative part (plain + html)
    alt = MIMEMultipart("alternative")
    # Plain‐text fallback
    text = re.sub(r"<br\s*/?>", "\n", re.sub(r"<.*?>", "", html_body))
    alt.attach(MIMEText(text, "plain"))
    alt.attach(MIMEText(html_body, "html"))
    # Attach the alternative part to the main message
    msg.attach(alt)

    # Attach signature image
    if sig_path and os.path.exists(sig_path):
        ctype, _ = mimetypes.guess_type(sig_path)
        maintype, subtype = ctype.split("/",1)
        with open(sig_path, "rb") as f:
            part = MIMEBase(maintype, subtype)
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", 'attachment; filename="signature.png"')
        msg.attach(part)

    # Attach machine-left multimedia
    if left_path and os.path.exists(left_path):
        ctype, _ = mimetypes.guess_type(left_path)
        maintype, subtype = ctype.split("/",1)
        with open(left_path, "rb") as f:
            part = MIMEBase(maintype, subtype)
            part.set_payload(f.read())
        encoders.encode_base64(part)
        filename = os.path.basename(left_path)
        part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
        msg.attach(part)

    # Send
    with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
        server.login(sender, password)
        server.sendmail(sender, recipients, msg.as_string())

# --- Brands & Models ---
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
brands_no_other = sorted(b for b in coffee_brands if b!="Other")
brand_order     = brands_no_other + ["Other"]
for b in coffee_brands:
    ms = sorted(m for m in coffee_brands[b] if m!="Other")
    if "Other" in coffee_brands[b]:
        ms.append("Other")
    coffee_brands[b] = ms

current_year = datetime.now().year
years = list(range(1970, current_year+1))[::-1]

# -------------------- CUSTOMER SELECTION --------------------
cust_list = customers["Company Name"].tolist()
sel_cust  = st.selectbox("Select customer", ["Add new..."] + cust_list)

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
            errs.append("Enter a valid address.")
        if not re.match(r'^\d{3}-\d{3}-\d{4}$', phone):
            errs.append("Phone must be 000-000-0000.")
        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
            errs.append("Enter a valid email.")

        if not errs:
            map_url = f"https://www.google.com/maps/search/{addr.replace(' ','+')}"
            st.markdown(f"[Preview on Google Maps]({map_url})")

        if st.form_submit_button("Save Customer") and not errs:
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
    cust_row = customers[customers["Company Name"]==sel_cust].iloc[0]
    st.subheader("Customer Information")
    st.text_input("Company Name", value=cust_row.get("Company Name",""), disabled=True)
    st.text_input("Contact Name", value=cust_row.get("Contact Name",""), disabled=True)
    st.text_input("Address",      value=cust_row.get("Address",""),      disabled=True)
    st.text_input("Phone",        value=cust_row.get("Phone",""),        disabled=True)
    st.text_input("Email",        value=cust_row.get("Email",""),        disabled=True)

    # -------------------- MACHINE SELECTION --------------------
    customer_id = cust_row["ID"]
    existing    = machines[machines["Customer ID"]==customer_id]
    labels      = [f"{r.Brand} ({r.Model})" for _,r in existing.iterrows()]
    machine_ids = existing["ID"].tolist()
    sel_machine = st.selectbox("Select machine", ["Add new..."] + labels)

    if sel_machine == "Add new...":
        # brand/model selectors outside form
        for k in ("brand_sel","prev_brand","model_sel","custom_brand","custom_model"):
            st.session_state.setdefault(k, "")

        brand = st.selectbox("Brand*", [""]+brand_order, key="brand_sel")
        if brand != st.session_state.prev_brand:
            st.session_state.prev_brand   = brand
            st.session_state.model_sel    = ""
            st.session_state.custom_model = ""
            st.session_state.custom_brand = ""

        custom_brand = st.text_input("Enter new brand*", key="custom_brand") if brand=="Other" else ""
        opts = coffee_brands.get(brand, ["Other"] if brand=="Other" else [])
        model = st.selectbox("Model*", [""]+opts, key="model_sel")
        custom_model = st.text_input("Enter new model*", key="custom_model") if model=="Other" else ""

        with st.form("new_machine"):
            year   = st.selectbox("Year*", [""]+[str(y) for y in years], key="year")
            serial = st.text_input("Serial Number (optional)", key="serial")
            obs    = st.text_area("Observations (optional)", key="obs")
            photo  = st.file_uploader("Machine photo*", type=["jpg","png"], key="photo")

            errs=[]
            fb = custom_brand.strip() if brand=="Other" else brand
            fm = custom_model.strip() if model=="Other" else model
            if not fb: errs.append("Brand is required.")
            if not fm: errs.append("Model is required.")
            if not st.session_state.year: errs.append("Year is required.")
            if not photo: errs.append("Photo is required.")

            sub2 = st.form_submit_button("Save Machine")
            if sub2 and not errs:
                mid = str(uuid.uuid4())
                path = f"{mid}_machine.png"
                Image.open(photo).save(path)
                new = pd.DataFrame([{
                    "ID": mid, "Customer ID": customer_id,
                    "Brand": fb, "Model": fm, "Year": st.session_state.year,
                    "Serial Number": serial,
                    "Photo Path": path, "Observations": obs
                }])
                machines = pd.concat([machines, new], ignore_index=True)
                machines.to_csv(MACHINES_FILE, index=False)
                st.success("Machine saved! Reload to select.")
                st.stop()

    else:
        # --- VIEW MACHINE INFO ---
        idx  = labels.index(sel_machine)
        mrow = existing.iloc[idx]
        st.subheader("Machine Information")
        st.text_input("Brand",         value=mrow.get("Brand",""),         disabled=True)
        st.text_input("Model",         value=mrow.get("Model",""),         disabled=True)
        st.text_input("Year",          value=mrow.get("Year",""),          disabled=True)
        st.text_input("Serial Number", value=mrow.get("Serial Number",""), disabled=True)
        st.text_area("Observations",   value=mrow.get("Observations",""),   disabled=True)
        pp = mrow.get("Photo Path","")
        if pp and os.path.exists(pp):
            st.image(pp, caption="Machine Photo", width=200)

        # -------------------- JOB FORM --------------------
        st.subheader("Log a Job")
        with st.form("log_job"):
            technician = st.selectbox("Technician*", ["Adonai Garcia","Miki Horvath"])
            job_date   = st.date_input("Date*", datetime.now())
            travel     = st.number_input("Travel Time (min)*", 0, step=1)
            time_in    = st.time_input("Time In*")
            time_out   = st.time_input("Time Out*")
            desc       = st.text_area("Job Description*")
            parts      = st.text_area("Parts Used (optional)")
            comments   = st.text_area("Additional Comments (optional)")
            found      = st.file_uploader("Machine as Found* (jpg/png/mp4)")
            left       = st.file_uploader("Machine as Left* (jpg/png/mp4)")
            employee   = st.text_input("Employee Full Name*")
            sigimg     = st_canvas(
                fill_color="rgba(255,255,255,1)", stroke_width=2,
                stroke_color="#000", background_color="#fff",
                height=100, width=300, drawing_mode="freedraw", key="sig"
            )

            st.markdown(
                "**By submitting this form, I acknowledge that I have reviewed and verified "
                "the accuracy of all information provided above.**"
            )

            if st.form_submit_button("Submit Job"):
                required = all([
                    technician, desc.strip(), employee.strip(),
                    found, left, sigimg.image_data is not None
                ])
                if not required:
                    st.error("Please complete all required fields and upload files.")
                else:
                    job_id = str(uuid.uuid4())
                    sig_path = f"{job_id}_signature.png"
                    Image.fromarray(sigimg.image_data).save(sig_path)
                    fpath = f"{job_id}_found.{found.name.rsplit('.',1)[-1]}"
                    open(fpath,"wb").write(found.read())
                    lpath = f"{job_id}_left.{left.name.rsplit('.',1)[-1]}"
                    open(lpath,"wb").write(left.read())

                    newj = pd.DataFrame([{
                        "Job ID": job_id,
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
                    jobs = pd.concat([jobs, newj], ignore_index=True)
                    jobs.to_csv(JOBS_FILE, index=False)
                    st.success("Job logged successfully!")

                    # Build professional HTML email
                    html = f"""
<p>Dear Customer,</p>
<p>Thank you for choosing <strong>Machine Hunter</strong> for your service needs. Below are the details of your recent service job:</p>
<p><strong>Job ID:</strong> {job_id}</p>
<p><strong>Customer:</strong> {sel_cust}</p>
<p><strong>Machine:</strong> {sel_machine}</p>
<p><strong>Employee:</strong> {employee}</p>
<p><strong>Technician:</strong> {technician}</p>
<p><strong>Date:</strong> {job_date}</p>
<p><strong>Travel Time:</strong> {travel} minutes</p>
<p><strong>Time In:</strong> {time_in}</p>
<p><strong>Time Out:</strong> {time_out}</p>
<p><strong>Description:</strong> {desc}</p>
{f"<p><strong>Parts Used:</strong> {parts}</p>" if parts else ""}
{f"<p><strong>Additional Comments:</strong> {comments}</p>" if comments else ""}
<p>Please find attached your employee’s signature and a multimedia file of the machine as it was left by our technician.</p>
<p>We appreciate your business and look forward to serving you again.</p>
<p>Sincerely,<br/>Machine Hunter Service Team</p>
"""

                    cust_email = cust_row.get("Email","")
                    send_job_email(job_id, cust_email, html, sig_path, lpath)

                    # Preview
                    st.markdown("### Preview")
                    st.write(f"Customer: {sel_cust}")
                    st.write(f"Machine: {sel_machine}")
                    st.write(f"Employee: {employee}")
                    st.write(f"Technician: {technician}")
                    st.write(f"Date: {job_date}")
                    st.write(f"Travel Time: {travel} minutes")
                    st.write(f"Time In: {time_in}   Time Out: {time_out}")
                    st.write(f"Description: {desc}")
                    if parts:    st.write(f"Parts Used: {parts}")
                    if comments: st.write(f"Additional Comments: {comments}")
                    st.image(sig_path, caption="Signature", width=150)
                    if os.path.exists(fpath):
                        if fpath.endswith(".mp4"): st.video(fpath)
                        else:                      st.image(fpath, caption="As Found", width=150)
                    if os.path.exists(lpath):
                        if lpath.endswith(".mp4"): st.video(lpath)
                        else:                      st.image(lpath, caption="As Left", width=150)

# --- Admin Tabs ---
tab1,tab2,tab3 = st.tabs(["All Jobs","All Customers","All Machines"])
with tab1: st.header("All Job Logs");   st.dataframe(jobs)
with tab2: st.header("All Customers");  st.dataframe(customers)
with tab3: st.header("All Machines");   st.dataframe(machines)
