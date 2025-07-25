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

    # attach signature
    if sig_path and os.path.exists(sig_path):
        ctype, _ = mimetypes.guess_type(sig_path)
        maintype, subtype = ctype.split("/",1)
        part = MIMEBase(maintype, subtype)
        with open(sig_path, "rb") as f:
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", 'attachment; filename="signature.png"')
        msg.attach(part)

    # attach machine-left
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

# --- Geocode addresses once ---
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

# --- Track selected customer ---
if "selected_customer" not in st.session_state:
    st.session_state.selected_customer = "Add new..."

# --- 1) DROPDOWN (with Add new...) ---
cust_list = customers["Company Name"].tolist()
dropdown_opts = ["Add new..."] + cust_list
sel_dropdown = st.selectbox("Select customer", dropdown_opts, index=0)
if sel_dropdown != st.session_state.selected_customer:
    st.session_state.selected_customer = sel_dropdown

# --- 2) MAP (Toronto GTA zoom) ---
st.markdown("## Or select a customer on the map")
m = folium.Map(location=[43.7, -79.4], zoom_start=10)
fg = folium.FeatureGroup(name="customers")
for cid, (lat, lon) in st.session_state.coords.items():
    if lat and lon:
        cname = customers.loc[customers["ID"]==cid, "Company Name"].iat[0]
        folium.Marker([lat, lon], tooltip=cname).add_to(fg)
fg.add_to(m)
Search(layer=fg, search_label="tooltip", placeholder="Search customer...", collapsed=False).add_to(m)
folium.LayerControl().add_to(m)
map_data = st_folium(m, width=700, height=400)
if map_data and map_data.get("last_object_clicked"):
    lat = map_data["last_object_clicked"]["lat"]
    lng = map_data["last_object_clicked"]["lng"]
    for cid, (clat, clon) in st.session_state.coords.items():
        if clat and clon and abs(clat - lat)<1e-4 and abs(clon - lng)<1e-4:
            cname = customers.loc[customers["ID"]==cid, "Company Name"].iat[0]
            if cname != st.session_state.selected_customer:
                st.session_state.selected_customer = cname
                st.experimental_rerun()

# --- Handle Add new... vs existing ---
sel_cust = st.session_state.selected_customer

if sel_cust == "Add new...":
    with st.form("new_customer"):
        cname   = st.text_input("Company Name*")
        contact = st.text_input("Contact Name*")
        addr    = st.text_input("Address* (e.g. 123 Main St, City)")
        phone   = st.text_input("Phone* (000-000-0000)")
        email   = st.text_input("Email* (you@example.com)")
        errs=[]
        if not cname.strip():   errs.append("Company Name required.")
        if not contact.strip(): errs.append("Contact Name required.")
        if not re.match(r'.+\d+.+', addr) or len(addr.split())<3:
            errs.append("Enter a valid address.")
        if not re.match(r'^\d{3}-\d{3}-\d{4}$', phone):
            errs.append("Phone must be 000-000-0000.")
        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
            errs.append("Enter a valid email.")
        if not errs:
            map_url=f"https://www.google.com/maps/search/{addr.replace(' ','+')}"
            st.markdown(f"[Preview on Google Maps]({map_url})")
        if st.form_submit_button("Save Customer") and not errs:
            cid=str(uuid.uuid4())
            new=pd.DataFrame([{
                "ID":cid,"Company Name":cname,"Contact Name":contact,
                "Address":addr,"Phone":phone,"Email":email
            }])
            customers=pd.concat([customers,new],ignore_index=True)
            customers.to_csv(CUSTOMERS_FILE,index=False)
            st.success("Customer saved! Reload.")
            st.stop()
else:
    # --- View existing customer info ---
    cust_row = customers[customers["Company Name"]==sel_cust].iloc[0]
    st.subheader("Customer Information")
    st.text_input("Company Name", value=cust_row.get("Company Name",""), disabled=True)
    st.text_input("Contact Name", value=cust_row.get("Contact Name",""), disabled=True)
    st.text_input("Address",      value=cust_row.get("Address",""),      disabled=True)
    st.text_input("Phone",        value=cust_row.get("Phone",""),        disabled=True)
    st.text_input("Email",        value=cust_row.get("Email",""),        disabled=True)

    # --- MACHINE SELECTION & FLOW ---
    customer_id = cust_row["ID"]
    cust_machs  = machines[machines["Customer ID"]==customer_id]
    labels      = [f"{r.Brand} ({r.Model})" for _,r in cust_machs.iterrows()]
    machine_ids = cust_machs["ID"].tolist()

    sel_machine = st.selectbox("Select machine", ["Add new..."] + labels)
    # ... (add-new and view-machine and job-logging code identical to previous version) ...
