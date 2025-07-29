import re
import os
import uuid
import smtplib
import mimetypes
from datetime import datetime

import streamlit as st
import pandas as pd
import folium
from PIL import Image
from geopy.geocoders import Nominatim
from streamlit_folium import st_folium
from folium.plugins import Search, LocateControl
from email import encoders
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from streamlit_drawable_canvas import st_canvas
from git import Repo  # GitPython

# -----------------------------------------------------------------------------
# 0) CONFIGURE: where to dump all media
# -----------------------------------------------------------------------------
MEDIA_ROOT = "media/customers"

# -----------------------------------------------------------------------------
# 1) STARTUP: git pull latest CSVs & media from GitHub
# -----------------------------------------------------------------------------
try:
    token     = st.secrets["github"]["token"]
    repo_name = st.secrets["github"]["repo"]
    branch    = st.secrets["github"]["branch"]
    repo      = Repo(os.getcwd())
    origin    = repo.remote(name="origin")
    origin.set_url(f"https://{token}@github.com/{repo_name}.git")
    origin.pull(refspec=f"{branch}:{branch}")
except Exception as e:
    st.warning(f"Could not git pull media & CSVs: {e}")

# -----------------------------------------------------------------------------
# 2) FILES & SCHEMA
# -----------------------------------------------------------------------------
CUSTOMERS_FILE = "customers.csv"
MACHINES_FILE  = "machines.csv"
JOBS_FILE      = "jobs.csv"

CUSTOMERS_COLUMNS = ["ID","Company Name","Contact Name","Address","Phone","Email"]
MACHINES_COLUMNS  = ["ID","Customer ID","Brand","Model","Year",
                     "Serial Number","Photo Path","Observations"]
JOBS_COLUMNS      = [
    "Job ID","Customer ID","Machine ID","Employee Name","Technician",
    "Date","Travel Time (min)","Time In","Time Out","Job Description",
    "Parts Used","Additional Comments",
    "Machine as Found Paths","Machine as Left Paths","Signature Path"
]

def load_df(path, cols):
    return pd.read_csv(path) if os.path.exists(path) else pd.DataFrame(columns=cols)

customers = load_df(CUSTOMERS_FILE, CUSTOMERS_COLUMNS)
machines  = load_df(MACHINES_FILE,  MACHINES_COLUMNS)
jobs      = load_df(JOBS_FILE,      JOBS_COLUMNS)

# -----------------------------------------------------------------------------
# 3) GIT PUSH HELPER (CSV + media)
# -----------------------------------------------------------------------------
def push_to_github(files, message):
    token      = st.secrets["github"]["token"]
    repo_name  = st.secrets["github"]["repo"]
    branch     = st.secrets["github"]["branch"]
    user_name  = st.secrets["github"]["user_name"]
    user_email = st.secrets["github"]["user_email"]

    repo   = Repo(os.getcwd())
    origin = repo.remote(name="origin")
    origin.set_url(f"https://{token}@github.com/{repo_name}.git")

    repo.config_writer().set_value("user", "name",  user_name).release()
    repo.config_writer().set_value("user", "email", user_email).release()

    repo.index.add(files)
    repo.index.commit(message)
    origin.push(refspec=f"{branch}:{branch}")

# -----------------------------------------------------------------------------
# 4) EMAIL SENDER (attaches signature only)
# -----------------------------------------------------------------------------
def send_email(recipients, subject, html_body, sig_path):
    sender      = st.secrets["email"]["user"]
    password    = st.secrets["email"]["password"]
    smtp_server = st.secrets["email"]["smtp_server"]
    smtp_port   = st.secrets["email"]["smtp_port"]

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"]    = sender
    msg["To"]      = ", ".join(recipients)

    alt = MIMEMultipart("alternative")
    # Plain‑text fallback
    text = re.sub(r"<.*?>","", html_body).replace("<br>","\n")
    alt.attach(MIMEText(text, "plain"))
    alt.attach(MIMEText(html_body, "html"))
    msg.attach(alt)

    # Attach signature image
    if sig_path and os.path.exists(sig_path):
        ctype, _ = mimetypes.guess_type(sig_path)
        maintype, subtype = ctype.split("/", 1)
        part = MIMEBase(maintype, subtype)
        with open(sig_path, "rb") as f:
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{os.path.basename(sig_path)}"')
        msg.attach(part)

    with smtplib.SMTP_SSL(smtp_server, smtp_port) as srv:
        srv.login(sender, password)
        srv.sendmail(sender, recipients, msg.as_string())

# -----------------------------------------------------------------------------
# 5) BRANDS & MODELS w/ “Other” option
# -----------------------------------------------------------------------------
base_coffee_brands = {
    "Bezzera": ["BZ10","DUO","Magica","Matrix","Mitica"],
    "Breville": ["Barista Express","Barista Pro","Duo Temp","Infuser","Oracle Touch"],
    "Carimali": ["Armonia Ultra","BlueDot","CA1000","Optima","SolarTouch"],
    "Cimbali":  ["M21 Junior","M39","M100","M200","S20"],
    "DeLonghi": ["Dedica","Dinamica","Eletta","La Specialista","Magnifica","Primadonna"],
    "ECM":      ["Barista","Classika","Elektronika","Synchronika","Technika"],
    "Faema":    ["E61","Emblema","E98 UP","Teorema","X30"],
    "Franke":   ["A300","A600","A800","S200","S700"],
    "Gaggia":   ["Accademia","Anima","Babila","Cadorna","Classic"],
    "Jura":     ["ENA 8","Giga X8","Impressa XJ9","WE8","Z10"],
    "Krups":    ["EA82","EA89","Evidence","Essential","Quattro Force"],
    "La Marzocco": ["GB5","GS3","Linea Mini","Linea PB","Strada"],
    "La Spaziale": ["Dream","S1 Mini Vivaldi II","S2","S8","S9"],
    "Miele":    ["CM5300","CM6150","CM6350","CM6360","CM7750"],
    "Nuova Simonelli": ["Appia","Aurelia","Musica","Oscar","Talento"],
    "Philips":  ["2200 Series","3200 Series","5000 Series","LatteGo","Saeco Xelsis"],
    "Quick Mill": ["Alexia","Andreja","Pegaso","Silvano","Vetrano"],
    "Rancilio": ["Classe 11","Classe 5","Classe 9","Egro One","Silvia"],
    "Rocket Espresso": ["Appartamento","Cronometro","Giotto","Mozzafiato","R58"],
    "Saeco":    ["Aulika","Incanto","Lirika","PicoBaristo","Royal"],
    "Schaerer": ["Coffee Art Plus","Coffee Club","Prime","Soul","Touch"],
    "Siemens":  ["EQ.3","EQ.6","EQ.9","Surpresso","TE653"],
    "Victoria Arduino": ["Adonis","Black Eagle","Eagle One","Mythos One","Venus"],
    "WMF":      ["1100 S","1500 S+","5000 S+","9000 S+","Espresso"]
}
coffee_brands = {}
for b, models in base_coffee_brands.items():
    m = sorted(models)
    if "Other" not in m:
        m.append("Other")
    coffee_brands[b] = m
coffee_brands["Other"] = ["Other"]
brands = sorted(list(base_coffee_brands.keys())) + ["Other"]

current_year = datetime.now().year
years = list(range(1970, current_year+1))[::-1]

# -----------------------------------------------------------------------------
# 6) GEOCODE once per customer
# -----------------------------------------------------------------------------
if "coords" not in st.session_state:
    locator = Nominatim(user_agent="machine_logger")
    cs = {}
    for _, r in customers.iterrows():
        try:
            loc = locator.geocode(r["Address"], timeout=10)
            cs[r["ID"]] = (loc.latitude, loc.longitude) if loc else (None, None)
        except:
            cs[r["ID"]] = (None, None)
    st.session_state.coords = cs

# -----------------------------------------------------------------------------
# 7) APP STATE
# -----------------------------------------------------------------------------
if "mode" not in st.session_state:
    st.session_state.mode = "select"
    st.session_state.selected_customer = None
mode = st.session_state.mode

st.title("☕ Machine Hunter Service Logger")

# -----------------------------------------------------------------------------
# 8) SELECT or ADD CUSTOMER
# -----------------------------------------------------------------------------
if mode == "select":
    c1, c2 = st.columns([1,3])
    with c1:
        if st.button("➕ Add new customer"):
            st.session_state.mode = "add"
    with c2:
        st.markdown("**Or click a red dot to choose a customer**")

    m = folium.Map(location=[43.7, -79.4], zoom_start=10, tiles="CartoDB positron")
    fg = folium.FeatureGroup()
    for cid,(lat,lon) in st.session_state.coords.items():
        if lat and lon:
            name = customers.loc[customers["ID"]==cid,"Company Name"].iat[0]
            folium.CircleMarker([lat,lon], radius=6, color="red",
                                fill=True, fill_color="red", tooltip=name).add_to(fg)
    fg.add_to(m)
    Search(layer=fg, search_label="tooltip", collapsed=False).add_to(m)
    LocateControl(auto_start=False).add_to(m)

    md = st_folium(m, width=700, height=400)
    click = md.get("last_clicked")
    if click:
        best,bd=None,float("inf")
        for cid,(clat,clon) in st.session_state.coords.items():
            if clat and clon:
                d=(clat-click["lat"])**2+(clon-click["lng"])**2
                if d<bd:
                    best,bd=cid,d
        if best and bd<0.0005:
            st.session_state.selected_customer = customers.loc[
                customers["ID"]==best,"Company Name"
            ].iat[0]
            st.session_state.mode = "existing"
    st.stop()

# -----------------------------------------------------------------------------
# 9) ADD NEW CUSTOMER form
# -----------------------------------------------------------------------------
if mode == "add":
    st.header("➕ Add New Customer")
    with st.form("add_cust"):
        cname   = st.text_input("Company Name*")
        contact = st.text_input("Contact Name*")
        addr    = st.text_input("Address*")
        phone   = st.text_input("Phone* (000-000-0000)")
        email   = st.text_input("Email*")
        submit  = st.form_submit_button("Save Customer")

        if submit:
            errs = []
            if not cname.strip(): errs.append("Company Name required.")
            if not contact.strip(): errs.append("Contact Name required.")
            if not re.match(r'.+\d+.+',addr) or len(addr.split())<3:
                errs.append("Valid address required.")
            if not re.match(r'^\d{3}-\d{3}-\d{4}$',phone):
                errs.append("Phone must be 000-000-0000.")
            if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$',email):
                errs.append("Valid email required.")

            if errs:
                st.error("\n".join(errs))
            else:
                cid = str(uuid.uuid4())
                new_row = {
                    "ID": cid,
                    "Company Name": cname.strip(),
                    "Contact Name": contact.strip(),
                    "Address": addr.strip(),
                    "Phone": phone.strip(),
                    "Email": email.strip()
                }
                customers = load_df(CUSTOMERS_FILE, CUSTOMERS_COLUMNS)
                customers = pd.concat([customers, pd.DataFrame([new_row])], ignore_index=True)
                customers.to_csv(CUSTOMERS_FILE, index=False)

                push_to_github([CUSTOMERS_FILE], f"Add customer {cname.strip()}")

                try:
                    loc = locator.geocode(addr, timeout=10)
                    st.session_state.coords[cid] = (loc.latitude,loc.longitude) if loc else (None,None)
                except:
                    st.session_state.coords[cid] = (None,None)

                st.session_state.mode = "select"
                st.session_state.selected_customer = None
                st.rerun()
        else:
            valid = all([cname,contact,addr,phone,email])
            if valid:
                st.markdown(f"[Preview on Google Maps]"
                            f"(https://www.google.com/maps/search/{addr.replace(' ','+')})")
    st.stop()

# -----------------------------------------------------------------------------
# 10) EXISTING CUSTOMER & Machine flow
# -----------------------------------------------------------------------------
sel_name = st.session_state.selected_customer
if not sel_name or sel_name not in customers["Company Name"].tolist():
    st.session_state.mode = "select"
    st.warning("Customer not found—please select again.")
    st.stop()

cust = customers.loc[customers["Company Name"]==sel_name].iloc[0]
st.subheader("👤 Customer Information")
st.text_input("Company Name", cust["Company Name"], disabled=True)
st.text_input("Contact Name", cust["Contact Name"], disabled=True)
st.text_input("Address",      cust["Address"],      disabled=True)
st.text_input("Phone",        cust["Phone"],        disabled=True)
st.text_input("Email",        cust["Email"],        disabled=True)

customer_id = cust["ID"]
own = machines[machines["Customer ID"]==customer_id]
labels = [f"{r.Brand} ({r.Model})" for _,r in own.iterrows()]
mids   = own["ID"].tolist()
sel_m  = st.selectbox("Select machine", ["Add new..."] + labels, key="machine")

# --- ADD NEW MACHINE ---
if sel_m=="Add new...":
    st.markdown("### ➕ Add New Machine")
    for k in ("b_sel","prev_b","m_sel","prev_m"):
        st.session_state.setdefault(k,"")

    brand = st.selectbox("Brand*", [""]+brands, key="b_sel")
    custom_brand = st.text_input("New brand*", key="prev_b") if brand=="Other" else ""

    model_opts = coffee_brands.get(brand,[])
    model = st.selectbox("Model*", [""]+model_opts, key="m_sel")
    custom_model = st.text_input("New model*", key="prev_m") if model=="Other" else ""

    with st.form("add_machine"):
        year   = st.selectbox("Year*", [""]+[str(y) for y in years], key="yr")
        serial = st.text_input("Serial Number (optional)")
        obs    = st.text_area("Observations (optional)")
        photo  = st.file_uploader("Machine photo*", type=["jpg","png"])
        errs   = []

        fb = (custom_brand.strip() if brand=="Other" else brand).strip()
        fm = (custom_model.strip() if model=="Other" else model).strip()

        if not fb:    errs.append("Brand required.")
        if not fm:    errs.append("Model required.")
        if not st.session_state.yr: errs.append("Year required.")
        if not photo: errs.append("Photo required.")

        if st.form_submit_button("Save Machine"):
            if errs:
                st.error("\n".join(errs))
            else:
                mid    = str(uuid.uuid4())
                folder = os.path.join(MEDIA_ROOT, customer_id, "machines", mid)
                os.makedirs(folder, exist_ok=True)
                photo_path = os.path.join(folder, photo.name)
                Image.open(photo).save(photo_path)

                new = pd.DataFrame([{
                    "ID": mid,
                    "Customer ID": customer_id,
                    "Brand": fb,
                    "Model": fm,
                    "Year": st.session_state.yr,
                    "Serial Number": serial,
                    "Photo Path": photo_path,
                    "Observations": obs
                }])
                machines = pd.concat([machines, new], ignore_index=True)
                machines.to_csv(MACHINES_FILE, index=False)

                push_to_github([MACHINES_FILE, photo_path],
                               f"Add machine {fm} for {sel_name}")

                st.success("Machine added!")
                st.rerun()

# --- VIEW & LOG JOB for existing machine ---
else:
    idx  = labels.index(sel_m)
    mrow = own.iloc[idx]
    st.subheader("☕ Machine Information")
    st.text_input("Brand",         mrow["Brand"], disabled=True)
    st.text_input("Model",         mrow["Model"], disabled=True)
    st.text_input("Year",          mrow["Year"],  disabled=True)
    st.text_input("Serial Number", mrow.get("Serial Number",""), disabled=True)
    st.text_area("Observations",   mrow.get("Observations",""),  disabled=True)
    if os.path.exists(mrow["Photo Path"]):
        st.image(mrow["Photo Path"], caption="Machine Photo", width=200)

    st.subheader("📝 Log a Job")
    with st.form("log_job"):
        tech   = st.selectbox("Technician*", ["Adonai Garcia","Miki Horvath"])
        jdate  = st.date_input("Date*", datetime.now())
        travel = st.number_input("Travel Time (min)*", 0, step=1)
        tin    = st.time_input("Time In*")
        tout   = st.time_input("Time Out*")
        desc   = st.text_area("Job Description*")
        parts  = st.text_area("Parts Used (optional)")
        comm   = st.text_area("Additional Comments (optional)")

        found_files = st.file_uploader(
            "Machine as Found* (jpg/png/mp4)",
            type=["jpg","png","mp4"],
            accept_multiple_files=True
        )
        left_files = st.file_uploader(
            "Machine as Left* (jpg/png/mp4)",
            type=["jpg","png","mp4"],
            accept_multiple_files=True
        )

        emp    = st.text_input("Employee Full Name*")
        sigimg = st_canvas(
            fill_color="rgba(255,255,255,1)",
            stroke_width=2, stroke_color="#000",
            background_color="#fff", height=100, width=300,
            drawing_mode="freedraw", key="sig"
        )
        st.markdown(
            "**By submitting this form, I acknowledge that I have reviewed and verified the accuracy of all information provided above.**"
        )

        if st.form_submit_button("Submit Job"):
            ok = all([tech, desc.strip(), emp.strip(),
                      found_files, left_files, sigimg.image_data is not None])
            if not ok:
                st.error("Complete all required fields & uploads.")
            else:
                jid = str(uuid.uuid4())
                # prepare folders
                job_folder       = os.path.join(MEDIA_ROOT, customer_id, "jobs", jid)
                found_folder     = os.path.join(job_folder, "found")
                left_folder      = os.path.join(job_folder, "left")
                signature_folder = os.path.join(job_folder, "signature")
                for d in (found_folder, left_folder, signature_folder):
                    os.makedirs(d, exist_ok=True)

                # save found media
                found_paths = []
                for f in found_files:
                    p = os.path.join(found_folder, f.name)
                    with open(p, "wb") as out: out.write(f.read())
                    found_paths.append(p)

                # save left media
                left_paths = []
                for f in left_files:
                    p = os.path.join(left_folder, f.name)
                    with open(p, "wb") as out: out.write(f.read())
                    left_paths.append(p)

                # save signature
                sig_path = os.path.join(signature_folder, f"{jid}_sig.png")
                Image.fromarray(sigimg.image_data).save(sig_path)

                # update jobs.csv
                newj = pd.DataFrame([{
                    "Job ID":               jid,
                    "Customer ID":          customer_id,
                    "Machine ID":           mids[idx],
                    "Employee Name":        emp,
                    "Technician":           tech,
                    "Date":                 str(jdate),
                    "Travel Time (min)":    int(travel),
                    "Time In":              str(tin),
                    "Time Out":             str(tout),
                    "Job Description":      desc,
                    "Parts Used":           parts,
                    "Additional Comments":  comm,
                    "Machine as Found Paths": ";".join(found_paths),
                    "Machine as Left Paths":  ";".join(left_paths),
                    "Signature Path":        sig_path
                }])
                jobs = pd.concat([jobs, newj], ignore_index=True)
                jobs.to_csv(JOBS_FILE, index=False)

                # commit CSV + all media
                all_files = [JOBS_FILE] + found_paths + left_paths + [sig_path]
                push_to_github(all_files, f"Log job {jid} for {sel_name}")

                st.success("Job logged successfully!")

                # prepare raw link base for GitHub
                raw_base = f"https://raw.githubusercontent.com/{st.secrets['github']['repo']}/{st.secrets['github']['branch']}"

                # build HTML for customer email
                customer_links_html = "".join(
                    f'<li><a href="{raw_base}/{p.replace(os.sep,"/")}">{os.path.basename(p)}</a></li>'
                    for p in left_paths
                )
                html_customer = f"""
<p>Dear {cust['Contact Name']},</p>
<p>Thank you for choosing Machine Hunter for your service needs. Below are your job details:</p>
<ul>
  <li><strong>Job ID:</strong> {jid}</li>
  <li><strong>Customer:</strong> {sel_name}</li>
  <li><strong>Machine:</strong> {sel_m}</li>
  <li><strong>Employee:</strong> {emp}</li>
  <li><strong>Technician:</strong> {tech}</li>
  <li><strong>Date:</strong> {jdate}</li>
  <li><strong>Description:</strong> {desc}</li>
  {f"<li><strong>Additional Comments:</strong> {comm}</li>" if comm else ""}
</ul>
<p><strong>Signature:</strong> attached.</p>
<p><strong>Machine as it was left:</strong></p>
<ul>
  {customer_links_html}
</ul>
<p>Please find attached your employee's signature and the multimedia of the machine as it was left by our technician.</p>
<p>We appreciate your business and look forward to serving you again.<p>
<p>Sincerely,<br/>Machine Hunter Service Team</p>
"""

                # send customer email
                send_email(
                    recipients=[cust["Email"]],
                    subject=f"Service Job Confirmation – {jid}",
                    html_body=html_customer,
                    sig_path=sig_path
                )

                # build HTML for internal email
                internal_links_html = customer_links_html
                html_internal = f"""
<p>New service job logged:</p>
<ul>
  <li><strong>Job ID:</strong> {jid}</li>
  <li><strong>Customer:</strong> {sel_name}</li>
  <li><strong>Machine:</strong> {sel_m}</li>
  <li><strong>Employee:</strong> {emp}</li>
  <li><strong>Technician:</strong> {tech}</li>
  <li><strong>Date:</strong> {jdate}</li>
  <li><strong>Travel Time:</strong> {travel} minutes</li>
  <li><strong>Time In:</strong> {tin}</li>
  <li><strong>Time Out:</strong> {tout}</li>
  <li><strong>Description:</strong> {desc}</li>
  {f"<li><strong>Additional Comments:</strong> {comm}</li>" if comm else ""}
</ul>
<p><strong>Signature:</strong> attached.</p>
<p><strong>Machine as it was left:</strong></p>
<ul>
  {internal_links_html}
</ul>
"""

                # send internal email to the address in secrets
                send_email(
                    recipients=[st.secrets["email"]["user"]],
                    subject=f"Service Job Logged – {jid}",
                    html_body=html_internal,
                    sig_path=sig_path
                )

                # In‑app preview
                st.markdown("### Preview")
                st.image(sig_path, caption="Technician’s Signature", width=150)
                st.markdown("**Machine as Found:**")
                for p in found_paths:
                    if p.lower().endswith(".mp4"):
                        st.video(p)
                    else:
                        st.image(p, caption=os.path.basename(p), width=150)
                st.markdown("**Machine as Left:**")
                for p in left_paths:
                    if p.lower().endswith(".mp4"):
                        st.video(p)
                    else:
                        st.image(p, caption=os.path.basename(p), width=150)

# -----------------------------------------------------------------------------
# 11) ADMIN TABS: show full tables
# -----------------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs(['All Jobs','All Customers','All Machines'])
with tab1:
    st.header('All Job Logs')
    st.dataframe(jobs)
with tab2:
    st.header('All Customers')
    st.dataframe(customers)
with tab3:
    st.header('All Machines')
    st.dataframe(machines)
