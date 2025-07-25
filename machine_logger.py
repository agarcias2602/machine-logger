import re
import os
import uuid
import smtplib
import mimetypes
import streamlit as st
import pandas as pd
import folium
from PIL import Image
from datetime import datetime
from geopy.geocoders import Nominatim
from streamlit_folium import st_folium
from folium.plugins import Search
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

# --- Email helper with attachments ---
def send_job_email(job_id, cust_email, html_body, sig_path, left_path):
    sender      = st.secrets["email"]["user"]
    password    = st.secrets["email"]["password"]
    smtp_server = st.secrets["email"]["smtp_server"]
    smtp_port   = st.secrets["email"]["smtp_port"]
    recipients  = ["mhunter4coffee@gmail.com"]
    if cust_email:
        recipients.append(cust_email)

    msg = MIMEMultipart("mixed")
    msg["Subject"] = f"Service Job Confirmation – {job_id}"
    msg["From"]    = sender
    msg["To"]      = ", ".join(recipients)

    alt = MIMEMultipart("alternative")
    text = re.sub(r"<br\s*/?>", "\n", re.sub(r"<.*?>", "", html_body))
    alt.attach(MIMEText(text, "plain"))
    alt.attach(MIMEText(html_body, "html"))
    msg.attach(alt)

    if sig_path and os.path.exists(sig_path):
        ctype, _ = mimetypes.guess_type(sig_path)
        maintype, subtype = ctype.split("/",1)
        part = MIMEBase(maintype, subtype)
        with open(sig_path, "rb") as f:
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", 'attachment; filename="signature.png"')
        msg.attach(part)

    if left_path and os.path.exists(left_path):
        ctype, _ = mimetypes.guess_type(left_path)
        maintype, subtype = ctype.split("/",1)
        part = MIMEBase(maintype, subtype)
        with open(left_path, "rb") as f:
            part.set_payload(f.read())
        encoders.encode_base64(part)
        filename = os.path.basename(left_path)
        part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
        msg.attach(part)

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
brands = sorted([b for b in coffee_brands if b!="Other"]) + ["Other"]
for b in coffee_brands:
    models = sorted([m for m in coffee_brands[b] if m!="Other"])
    if "Other" in coffee_brands[b]:
        models.append("Other")
    coffee_brands[b] = models

current_year = datetime.now().year
years = list(range(1970, current_year+1))[::-1]

# --- 1) MAP SELECTION OF CUSTOMER ---
if "coords" not in st.session_state:
    geolocator = Nominatim(user_agent="machine_logger")
    coords = {}
    for _, row in customers.iterrows():
        addr = row.get("Address","")
        try:
            loc = geolocator.geocode(addr, timeout=10)
            coords[row["ID"]] = (loc.latitude, loc.longitude) if loc else (None, None)
        except:
            coords[row["ID"]] = (None, None)
    st.session_state.coords = coords

if "selected_customer" not in st.session_state:
    st.session_state.selected_customer = None

if st.session_state.selected_customer is None:
    m = folium.Map(location=[43.651070, -79.347015], zoom_start=12)
    fg = folium.FeatureGroup(name="customers")
    for cid, (lat, lon) in st.session_state.coords.items():
        if lat and lon:
            cname = customers.loc[customers["ID"]==cid, "Company Name"].iat[0]
            folium.Marker(
                [lat, lon],
                tooltip=cname
            ).add_to(fg)
    fg.add_to(m)
    Search(
        layer=fg,
        search_label="tooltip",
        placeholder="Search customer...",
        collapsed=False
    ).add_to(m)
    folium.LayerControl().add_to(m)

    st.markdown("## Select a Customer on the Map")
    map_data = st_folium(m, width=700, height=450)

    if map_data and map_data.get("last_object_clicked"):
        click = map_data["last_object_clicked"]
        for cid, (lat, lon) in st.session_state.coords.items():
            if lat and lon and abs(lat - click["lat"]) < 1e-4 and abs(lon - click["lng"]) < 1e-4:
                st.session_state.selected_customer = customers.loc[customers["ID"]==cid, "Company Name"].iat[0]
                st.experimental_rerun()
    st.stop()

# --- 2) VIEW CUSTOMER INFO ---
sel_cust = st.session_state.selected_customer
cust_row = customers.loc[customers["Company Name"]==sel_cust].iloc[0]

st.subheader("Customer Information")
st.text_input("Company Name", value=cust_row.get("Company Name",""), disabled=True)
st.text_input("Contact Name", value=cust_row.get("Contact Name",""), disabled=True)
st.text_input("Address",      value=cust_row.get("Address",""),      disabled=True)
st.text_input("Phone",        value=cust_row.get("Phone",""),        disabled=True)
st.text_input("Email",        value=cust_row.get("Email",""),        disabled=True)

# --- 3) MACHINE SELECTION & FLOW ---
customer_id = cust_row["ID"]
cust_machs  = machines[machines["Customer ID"]==customer_id]
labels      = [f"{r.Brand} ({r.Model})" for _,r in cust_machs.iterrows()]
machine_ids = cust_machs["ID"].tolist()

sel_machine = st.selectbox("Select machine", ["Add new..."] + labels)

if sel_machine=="Add new...":
    for k in ("brand_sel","prev_brand","model_sel","custom_brand","custom_model"):
        st.session_state.setdefault(k,"")
    brand = st.selectbox("Brand*", [""]+brands, key="brand_sel")
    if brand!=st.session_state.prev_brand:
        st.session_state.prev_brand=brand
        st.session_state.model_sel=""
        st.session_state.custom_model=""
        st.session_state.custom_brand=""
    custom_brand = st.text_input("Enter new brand*", key="custom_brand") if brand=="Other" else ""
    opts = coffee_brands.get(brand,["Other"] if brand=="Other" else [])
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
        if st.form_submit_button("Save Machine"):
            if errs:
                st.error("\n".join(errs))
            else:
                mid = str(uuid.uuid4()); p = f"{mid}_machine.png"
                Image.open(photo).save(p)
                new = pd.DataFrame([{
                    "ID":mid,"Customer ID":customer_id,
                    "Brand":fb,"Model":fm,"Year":st.session_state.year,
                    "Serial Number":serial,"Photo Path":p,"Observations":obs
                }])
                machines = pd.concat([machines,new],ignore_index=True)
                machines.to_csv(MACHINES_FILE,index=False)
                st.success("Machine saved! Reload to select.")
                st.stop()
else:
    idx  = labels.index(sel_machine)
    mrow = cust_machs.iloc[idx]
    st.subheader("Machine Information")
    st.text_input("Brand", value=mrow.get("Brand",""), disabled=True)
    st.text_input("Model", value=mrow.get("Model",""), disabled=True)
    st.text_input("Year", value=mrow.get("Year",""), disabled=True)
    st.text_input("Serial Number", value=mrow.get("Serial Number",""), disabled=True)
    st.text_area("Observations", value=mrow.get("Observations",""), disabled=True)
    pp = mrow.get("Photo Path","")
    if pp and os.path.exists(pp):
        st.image(pp, caption="Machine Photo", width=200)

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
            "**By submitting this form, I acknowledge that I have reviewed and verified the accuracy of all information provided above.**"
        )

        if st.form_submit_button("Submit Job"):
            req = all([
                technician, desc.strip(), employee.strip(),
                found, left, sigimg.image_data is not None
            ])
            if not req:
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
                    "Job ID":job_id,"Customer ID":customer_id,"Machine ID":machine_ids[idx],
                    "Employee Name":employee,"Technician":technician,
                    "Date":str(job_date),"Travel Time (min)":int(travel),
                    "Time In":str(time_in),"Time Out":str(time_out),
                    "Job Description":desc,"Parts Used":parts,
                    "Additional Comments":comments,
                    "Machine as Found Path":fpath,
                    "Machine as Left Path":lpath,
                    "Signature Path":sig_path
                }])
                jobs = pd.concat([jobs,newj],ignore_index=True)
                jobs.to_csv(JOBS_FILE,index=False)
                st.success("Job logged successfully!")

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
<p>Please find attached the technician’s signature and a snapshot of the machine as it was left.</p>
<p>We appreciate your business and look forward to serving you again.</p>
<p>Sincerely,<br/>Machine Hunter Service Team</p>
"""

                cust_email = cust_row.get("Email","")
                send_job_email(job_id, cust_email, html, sig_path, lpath)

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
