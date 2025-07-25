import re, os, uuid, smtplib, mimetypes
import streamlit as st
import pandas as pd
import folium
from PIL import Image
from datetime import datetime
from geopy.geocoders import Nominatim
from streamlit_folium import st_folium
from folium.plugins import Search, LocateControl
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

st.title("☕ Coffee Machine Service Logger")

# ——— EMAIL SENDER ———
def send_job_email(job_id, cust_email, html_body, sig_path, left_path):
    sender      = st.secrets["email"]["user"]
    password    = st.secrets["email"]["password"]
    smtp_server = st.secrets["email"]["smtp_server"]
    smtp_port   = st.secrets["email"]["smtp_port"]
    to_addrs    = ["mhunter4coffee@gmail.com"]
    if cust_email:
        to_addrs.append(cust_email)

    msg = MIMEMultipart("mixed")
    msg["Subject"] = f"Service Job Confirmation – {job_id}"
    msg["From"]    = sender
    msg["To"]      = ", ".join(to_addrs)

    alt = MIMEMultipart("alternative")
    text = re.sub(r"<br\s*/?>","\n", re.sub(r"<.*?>","", html_body))
    alt.attach(MIMEText(text, "plain"))
    alt.attach(MIMEText(html_body, "html"))
    msg.attach(alt)

    def _attach(path, filename):
        ctype, _ = mimetypes.guess_type(path)
        maintype, subtype = ctype.split("/",1)
        part = MIMEBase(maintype, subtype)
        with open(path,"rb") as f: part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
        msg.attach(part)

    if sig_path and os.path.exists(sig_path):
        _attach(sig_path, "signature.png")
    if left_path and os.path.exists(left_path):
        _attach(left_path, os.path.basename(left_path))

    with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
        server.login(sender, password)
        server.sendmail(sender, to_addrs, msg.as_string())

# ——— BRANDS & MODELS ———
coffee_brands = {
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
    "WMF":      ["1100 S","1500 S+","5000 S+","9000 S+","Espresso"],
    "Other":    ["Other"]
}
brands = sorted(b for b in coffee_brands if b!="Other") + ["Other"]
for b in coffee_brands:
    ms = sorted(m for m in coffee_brands[b] if m!="Other")
    if "Other" in coffee_brands[b]:
        ms.append("Other")
    coffee_brands[b] = ms

current_year = datetime.now().year
years = list(range(1970, current_year+1))[::-1]

# ——— GEOCODE ADDRESSES ———
if "coords" not in st.session_state:
    geolocator = Nominatim(user_agent="machine_logger")
    coords = {}
    for _, r in customers.iterrows():
        addr = r["Address"]
        try:
            loc = geolocator.geocode(addr, timeout=10)
            coords[r["ID"]] = (loc.latitude, loc.longitude) if loc else (None,None)
        except:
            coords[r["ID"]] = (None,None)
    st.session_state.coords = coords

# ——— SELECTED CUSTOMER STATE ———
if "sel_dropdown" not in st.session_state:
    st.session_state.sel_dropdown = "Add new..."
# dropdown with “Add new…” first
cust_list = customers["Company Name"].tolist()
options   = ["Add new..."] + cust_list
sel = st.selectbox("Select customer", options, key="sel_dropdown")

# ——— MAP (GTA, greyscale, locate control) ———
st.markdown("## Or pick on the map")
m = folium.Map(
    location=[43.7, -79.4],
    zoom_start=10,
    tiles="CartoDB positron"  # light greyscale
)
fg = folium.FeatureGroup()
for cid,(lat,lon) in st.session_state.coords.items():
    if lat and lon:
        cname = customers.loc[customers["ID"]==cid,"Company Name"].iat[0]
        folium.CircleMarker(
            [lat,lon],
            radius=6,
            color="red",
            fill=True,
            fill_color="red",
            tooltip=cname
        ).add_to(fg)
fg.add_to(m)
Search(layer=fg, search_label="tooltip", placeholder="Search…", collapsed=False).add_to(m)
LocateControl(auto_start=False).add_to(m)
st_data = st_folium(m, width=700, height=400)

# if map click, pick nearest customer
click = st_data.get("last_clicked")
if click:
    lat,lon = click["lat"], click["lng"]
    # find closest
    best,bdiff = None,1e9
    for cid,(clat,clon) in st.session_state.coords.items():
        if clat and clon:
            diff = (clat-lat)**2 + (clon-lon)**2
            if diff < bdiff:
                best,bdiff = cid,diff
    if best and bdiff < 0.0005:  # ~<0.02° ≈2km
        cname = customers.loc[customers["ID"]==best,"Company Name"].iat[0]
        if cname != st.session_state.sel_dropdown:
            st.session_state.sel_dropdown = cname
            st.experimental_rerun()

# ——— NOW EITHER “Add new…” OR EXISTING ———
if sel == "Add new...":
    # new customer form
    with st.form("new_customer"):
        cname   = st.text_input("Company Name*")
        contact = st.text_input("Contact Name*")
        addr    = st.text_input("Address* (e.g. 123 Main St, City)")
        phone   = st.text_input("Phone* (000-000-0000)")
        email   = st.text_input("Email*")
        errs = []
        if not cname.strip(): errs.append("Company Name required.")
        if not contact.strip(): errs.append("Contact Name required.")
        if not re.match(r'.+\d+.+', addr) or len(addr.split())<3:
            errs.append("Valid address required.")
        if not re.match(r'^\d{3}-\d{3}-\d{4}$', phone):
            errs.append("Phone must be 000-000-0000.")
        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
            errs.append("Valid email required.")
        if not errs:
            map_url = f"https://www.google.com/maps/search/{addr.replace(' ','+')}"
            st.markdown(f"[Preview address on Google Maps]({map_url})")
        if st.form_submit_button("Save Customer") and not errs:
            cid = str(uuid.uuid4())
            new = pd.DataFrame([{
                "ID":cid,
                "Company Name":cname,
                "Contact Name":contact,
                "Address":addr,
                "Phone":phone,
                "Email":email
            }])
            customers=pd.concat([customers,new],ignore_index=True)
            customers.to_csv(CUSTOMERS_FILE,index=False)
            st.success("Customer added—please reload.")
            st.stop()

else:
    # view existing
    cust = customers[customers["Company Name"]==sel].iloc[0]
    st.subheader("Customer Information")
    st.text_input("Company Name", value=cust["Company Name"], disabled=True)
    st.text_input("Contact Name", value=cust["Contact Name"], disabled=True)
    st.text_input("Address",      value=cust["Address"],      disabled=True)
    st.text_input("Phone",        value=cust["Phone"],        disabled=True)
    st.text_input("Email",        value=cust["Email"],        disabled=True)

    # ——— MACHINE FLOW ——
    customer_id = cust["ID"]
    own = machines[machines["Customer ID"]==customer_id]
    labels = [f"{r.Brand} ({r.Model})" for _,r in own.iterrows()]
    mids   = own["ID"].tolist()
    sel_m  = st.selectbox("Select machine", ["Add new..."]+labels)

    if sel_m=="Add new...":
        # same “add machine” form as before…
        # (copy your machine‐form code here)
        pass
    else:
        idx = labels.index(sel_m)
        mrow=own.iloc[idx]
        st.subheader("Machine Information")
        st.text_input("Brand", value=mrow["Brand"], disabled=True)
        st.text_input("Model", value=mrow["Model"], disabled=True)
        st.text_input("Year",  value=mrow["Year"],  disabled=True)
        st.text_input("Serial Number", value=mrow.get("Serial Number",""), disabled=True)
        st.text_area("Observations", value=mrow.get("Observations",""), disabled=True)

        pp = mrow.get("Photo Path","")
        if pp and os.path.exists(pp):
            st.image(pp, caption="Machine Photo", width=200)

        # — LOG A JOB —
        st.subheader("Log a Job")
        with st.form("log_job"):
            technician = st.selectbox("Technician*", ["Adonai Garcia","Miki Horvath"])
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
                fill_color="rgba(255,255,255,1)",
                stroke_width=2, stroke_color="#000",
                background_color="#fff",
                height=100, width=300,
                drawing_mode="freedraw", key="sig"
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
                    st.error("Complete all required fields & uploads.")
                else:
                    jid = str(uuid.uuid4())
                    # save signature
                    sig_path = f"{jid}_signature.png"
                    Image.fromarray(sigimg.image_data).save(sig_path)
                    # save media
                    fpath = f"{jid}_found.{found.name.rsplit('.',1)[-1]}"
                    open(fpath,"wb").write(found.read())
                    lpath = f"{jid}_left.{left.name.rsplit('.',1)[-1]}"
                    open(lpath,"wb").write(left.read())
                    # record job
                    newj = pd.DataFrame([{
                        "Job ID":jid,
                        "Customer ID":customer_id,
                        "Machine ID":mids[idx],
                        "Employee Name":employee,
                        "Technician":technician,
                        "Date":str(job_date),
                        "Travel Time (min)":int(travel),
                        "Time In":str(time_in),
                        "Time Out":str(time_out),
                        "Job Description":desc,
                        "Parts Used":parts,
                        "Additional Comments":comments,
                        "Machine as Found Path":fpath,
                        "Machine as Left Path":lpath,
                        "Signature Path":sig_path
                    }])
                    jobs=pd.concat([jobs,newj],ignore_index=True)
                    jobs.to_csv(JOBS_FILE,index=False)
                    st.success("Job logged!")

                    # professional email
                    html = f"""
<p>Dear Customer,</p>
<p>Thank you for choosing <strong>Machine Hunter</strong> for your service needs. Below are your job details:</p>
<p><strong>Job ID:</strong> {jid}</p>
<p><strong>Customer:</strong> {sel}</p>
<p><strong>Machine:</strong> {sel_m}</p>
<p><strong>Employee:</strong> {employee}</p>
<p><strong>Technician:</strong> {technician}</p>
<p><strong>Date:</strong> {job_date}</p>
<p><strong>Travel Time:</strong> {travel} min</p>
<p><strong>Time In:</strong> {time_in}</p>
<p><strong>Time Out:</strong> {time_out}</p>
<p><strong>Description:</strong> {desc}</p>
{f"<p><strong>Parts Used:</strong> {parts}</p>" if parts else ""}
{f"<p><strong>Additional Comments:</strong> {comments}</p>" if comments else ""}
<p>Please find attached the technician’s signature and a snapshot of the machine as it was left.</p>
<p>We appreciate your business and look forward to serving you again.</p>
<p>Sincerely,<br/>Machine Hunter Service Team</p>
"""
                    cust_email = cust["Email"]
                    send_job_email(jid, cust_email, html, sig_path, lpath)

                    # preview
                    st.markdown("### Preview")
                    st.write(f"Customer: {sel}")
                    st.write(f"Machine: {sel_m}")
                    st.write(f"Employee: {employee}")
                    st.write(f"Technician: {technician}")
                    st.write(f"Date: {job_date}")
                    st.write(f"Travel Time: {travel} min")
                    st.write(f"Time In: {time_in}   Time Out: {time_out}")
                    st.write(f"Description: {desc}")
                    if parts:    st.write(f"Parts Used: {parts}")
                    if comments: st.write(f"Additional Comments: {comments}")
                    st.image(sig_path, caption="Signature", width=150)
                    if os.path.exists(fpath):
                        if fpath.endswith(".mp4"): st.video(fpath)
                        else:                      st.image(fpath, caption="As Found", width=150)
                    if os.path.exists(lpath):
                        if lpath.endswith(".mp4"): st.video(lpath)
                        else:                      st.image(lpath, caption="As Left", width=150)

# ——— Admin Tabs ———
tab1,tab2,tab3 = st.tabs(["All Jobs","All Customers","All Machines"])
with tab1: st.header("All Job Logs");   st.dataframe(jobs)
with tab2: st.header("All Customers");  st.dataframe(customers)
with tab3: st.header("All Machines");   st.dataframe(machines)
