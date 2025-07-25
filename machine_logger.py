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

# ——— Helper: send email ———
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
    text = re.sub(r"<.*?>","", html_body).replace("<br>","\n")
    alt.attach(MIMEText(text, "plain"))
    alt.attach(MIMEText(html_body, "html"))
    msg.attach(alt)

    def _attach(path, name):
        ctype, _ = mimetypes.guess_type(path)
        maintype, subtype = ctype.split("/",1)
        part = MIMEBase(maintype, subtype)
        with open(path,"rb") as f: part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{name}"')
        msg.attach(part)

    if sig_path and os.path.exists(sig_path):
        _attach(sig_path, "signature.png")
    if left_path and os.path.exists(left_path):
        _attach(left_path, os.path.basename(left_path))

    with smtplib.SMTP_SSL(smtp_server, smtp_port) as srv:
        srv.login(sender, password)
        srv.sendmail(sender, recipients, msg.as_string())

# ——— Brands & Models ———
coffee_brands = {
    "Bezzera": ["BZ10","DUO","Magica","Matrix","Mitica"],
    "Breville": ["Barista Express","Barista Pro","Duo Temp","Infuser","Oracle Touch"],
    "Carimali": ["Armonia Ultra","BlueDot","CA1000","Optima","SolarTouch"],
    # … include the rest, then:
    "WMF": ["1100 S","1500 S+","5000 S+","9000 S+","Espresso"],
    "Other": ["Other"]
}
brands = sorted(b for b in coffee_brands if b!="Other") + ["Other"]
for b in coffee_brands:
    ms = sorted(m for m in coffee_brands[b] if m!="Other")
    if "Other" in coffee_brands[b]: ms.append("Other")
    coffee_brands[b] = ms

# Years list
current_year = datetime.now().year
years = list(range(1970, current_year+1))[::-1]

# ——— Geocode addresses once ———
if "coords" not in st.session_state:
    locator = Nominatim(user_agent="machine_logger")
    coords = {}
    for _, r in customers.iterrows():
        addr = r["Address"]
        try:
            loc = locator.geocode(addr, timeout=10)
            coords[r["ID"]] = (loc.latitude, loc.longitude) if loc else (None,None)
        except:
            coords[r["ID"]] = (None,None)
    st.session_state.coords = coords

# ——— Mode/state ———
if "mode" not in st.session_state:
    # modes: "select", "add", "existing"
    st.session_state.mode = "select"
    st.session_state.selected_customer = None

mode = st.session_state.mode

# ——— 1) SELECT or ADD NEW ———
if mode == "select":
    col1, col2 = st.columns([1,1])
    with col1:
        if st.button("➕ Add new customer"):
            st.session_state.mode = "add"
            st.experimental_rerun()
    with col2:
        st.markdown("**Or click a marker on the map to choose**")

    # Map
    m = folium.Map(location=[43.7, -79.4], zoom_start=10, tiles="CartoDB positron")
    fg = folium.FeatureGroup()
    for cid,(lat,lon) in st.session_state.coords.items():
        if lat and lon:
            cname = customers.loc[customers["ID"]==cid,"Company Name"].iat[0]
            folium.CircleMarker(
                [lat,lon],
                radius=6, color="red", fill=True, fill_color="red",
                tooltip=cname
            ).add_to(fg)
    fg.add_to(m)
    Search(layer=fg, search_label="tooltip", placeholder="Search…", collapsed=False).add_to(m)
    LocateControl(auto_start=False).add_to(m)

    data = st_folium(m, width=700, height=400)
    click = data.get("last_clicked")
    if click:
        # pick nearest marker
        best,bd = None,1e9
        for cid,(clat,clon) in st.session_state.coords.items():
            if clat and clon:
                d = (clat-click["lat"])**2 + (clon-click["lng"])**2
                if d<bd:
                    best,bd = cid,d
        if best and bd<0.0005:
            cname = customers.loc[customers["ID"]==best,"Company Name"].iat[0]
            st.session_state.selected_customer = cname
            st.session_state.mode = "existing"
            st.experimental_rerun()

    st.stop()

# ——— 2) ADD NEW CUSTOMER ———
if mode == "add":
    st.header("➕ Add New Customer")
    with st.form("new_customer"):
        cname   = st.text_input("Company Name*")
        contact = st.text_input("Contact Name*")
        addr    = st.text_input("Address* (e.g. 123 Main St, City)")
        phone   = st.text_input("Phone* (000-000-0000)")
        email   = st.text_input("Email*")
        errs=[]
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
            st.markdown(f"[Preview on Google Maps]({map_url})")
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

# ——— 3) EXISTING CUSTOMER FLOW ———
# at this point mode=="existing"
sel = st.session_state.selected_customer
cust = customers[customers["Company Name"]==sel].iloc[0]

st.subheader("👤 Customer Information")
st.text_input("Company Name",   value=cust["Company Name"], disabled=True)
st.text_input("Contact Name",   value=cust["Contact Name"], disabled=True)
st.text_input("Address",        value=cust["Address"],      disabled=True)
st.text_input("Phone",          value=cust["Phone"],        disabled=True)
st.text_input("Email",          value=cust["Email"],        disabled=True)

# --- MACHINE selection / add / view ---
st.subheader("☕ Machines")
customer_id = cust["ID"]
own = machines[machines["Customer ID"]==customer_id]
labels = [f"{r.Brand} ({r.Model})" for _,r in own.iterrows()]
mids   = own["ID"].tolist()
sel_m  = st.selectbox("Select machine", ["Add new..."]+labels, key="machine")

if sel_m=="Add new...":
    # add machine form
    st.markdown("### Add New Machine")
    for k in ("b_sel","p_brand","m_sel","p_model"): st.session_state.setdefault(k,"")
    brand = st.selectbox("Brand*", [""]+brands, key="b_sel")
    if brand != st.session_state.p_brand:
        st.session_state.p_brand = brand
        st.session_state.m_sel    = ""
        st.session_state.p_model  = ""
    custom_brand = st.text_input("New brand*", key="p_brand") if brand=="Other" else ""
    opts = coffee_brands.get(brand, ["Other"] if brand=="Other" else [])
    model = st.selectbox("Model*", [""]+opts, key="m_sel")
    custom_model = st.text_input("New model*", key="p_model") if model=="Other" else ""
    with st.form("new_machine"):
        year   = st.selectbox("Year*", [""]+[str(y) for y in years], key="year")
        serial = st.text_input("Serial Number (optional)", key="ser")
        obs    = st.text_area("Observations (optional)", key="obs")
        photo  = st.file_uploader("Machine photo*", type=["jpg","png"], key="photo")
        errs=[]
        fb = custom_brand.strip() if brand=="Other" else brand
        fm = custom_model.strip() if model=="Other" else model
        if not fb: errs.append("Brand required.")
        if not fm: errs.append("Model required.")
        if not st.session_state.year: errs.append("Year required.")
        if not photo: errs.append("Photo required.")
        if st.form_submit_button("Save Machine"):
            if errs:
                st.error("\n".join(errs))
            else:
                mid = str(uuid.uuid4()); p=f"{mid}_machine.png"
                Image.open(photo).save(p)
                new = pd.DataFrame([{
                    "ID":mid,"Customer ID":customer_id,
                    "Brand":fb,"Model":fm,"Year":st.session_state.year,
                    "Serial Number":serial,"Photo Path":p,"Observations":obs
                }])
                machines = pd.concat([machines,new],ignore_index=True)
                machines.to_csv(MACHINES_FILE,index=False)
                st.success("Machine added—please reload.")
                st.stop()

else:
    # view and then job form
    idx = labels.index(sel_m)
    mrow = own.iloc[idx]
    st.markdown("### Machine Information")
    st.text_input("Brand",          mrow["Brand"], disabled=True)
    st.text_input("Model",          mrow["Model"], disabled=True)
    st.text_input("Year",           mrow["Year"],  disabled=True)
    st.text_input("Serial Number",  mrow.get("Serial Number",""), disabled=True)
    st.text_area("Observations",    mrow.get("Observations",""),  disabled=True)
    pp = mrow.get("Photo Path","")
    if pp and os.path.exists(pp):
        st.image(pp, caption="Photo", width=200)

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
        found  = st.file_uploader("Machine as Found* (jpg/png/mp4)")
        left   = st.file_uploader("Machine as Left*  (jpg/png/mp4)")
        emp    = st.text_input("Employee Full Name*")
        sigimg = st_canvas(
            fill_color="rgba(255,255,255,1)",
            stroke_width=2, stroke_color="#000",
            background_color="#fff", height=100, width=300,
            drawing_mode="freedraw", key="sig"
        )
        st.markdown(
            "**By submitting, I acknowledge I’ve reviewed and verified all information provided above.**"
        )
        if st.form_submit_button("Submit Job"):
            ok = all([tech, desc.strip(), emp.strip(),
                      found, left, sigimg.image_data is not None])
            if not ok:
                st.error("Complete all required fields & uploads.")
            else:
                jid = str(uuid.uuid4())
                # save signature & media
                sp = f"{jid}_sig.png"
                Image.fromarray(sigimg.image_data).save(sp)
                fp = f"{jid}_found.{found.name.rsplit('.',1)[-1]}"
                open(fp,"wb").write(found.read())
                lp = f"{jid}_left.{left.name.rsplit('.',1)[-1]}"
                open(lp,"wb").write(left.read())
                # record
                newj = pd.DataFrame([{
                    "Job ID":jid,
                    "Customer ID":customer_id,
                    "Machine ID":mids[idx],
                    "Employee Name":emp,
                    "Technician":tech,
                    "Date":str(jdate),
                    "Travel Time (min)":int(travel),
                    "Time In":str(tin),
                    "Time Out":str(tout),
                    "Job Description":desc,
                    "Parts Used":parts,
                    "Additional Comments":comm,
                    "Machine as Found Path":fp,
                    "Machine as Left Path":lp,
                    "Signature Path":sp
                }])
                jobs = pd.concat([jobs,newj],ignore_index=True)
                jobs.to_csv(JOBS_FILE,index=False)
                st.success("Job logged successfully!")

                # build email
                html = f"""
<p>Dear Customer,</p>
<p>Thank you for choosing <strong>Machine Hunter</strong> for your service needs. Below are your job details:</p>
<p><strong>Job ID:</strong> {jid}</p>
<p><strong>Customer:</strong> {sel}</p>
<p><strong>Machine:</strong> {sel_m}</p>
<p><strong>Employee:</strong> {emp}</p>
<p><strong>Technician:</strong> {tech}</p>
<p><strong>Date:</strong> {jdate}</p>
<p><strong>Travel Time:</strong> {travel} minutes</p>
<p><strong>Time In:</strong> {tin}</p>
<p><strong>Time Out:</strong> {tout}</p>
<p><strong>Description:</strong> {desc}</p>
{f"<p><strong>Parts Used:</strong> {parts}</p>" if parts else ""}
{f"<p><strong>Additional Comments:</strong> {comm}</p>" if comm else ""}
<p>Please find attached the technician’s signature and a snapshot of the machine as it was left.</p>
<p>We appreciate your business and look forward to serving you again.</p>
<p>Sincerely,<br/>Machine Hunter Service Team</p>
"""
                cust_email = cust["Email"]
                send_job_email(jid, cust_email, html, sp, lp)

                # preview
                st.markdown("### Preview")
                st.write(f"Customer: {sel}")
                st.write(f"Machine: {sel_m}")
                st.write(f"Employee: {emp}")
                st.write(f"Technician: {tech}")
                st.write(f"Date: {jdate}")
                st.write(f"Travel Time: {travel} minutes")
                st.write(f"Time In: {tin}   Time Out: {tout}")
                st.write(f"Description: {desc}")
                if parts:    st.write(f"Parts Used: {parts}")
                if comm:     st.write(f"Additional Comments: {comm}")
                st.image(sp, caption="Signature", width=150)
                if os.path.exists(fp):
                    if fp.endswith(".mp4"): st.video(fp)
                    else:                   st.image(fp, caption="Found", width=150)
                if os.path.exists(lp):
                    if lp.endswith(".mp4"): st.video(lp)
                    else:                   st.image(lp, caption="Left", width=150)

# ——— Admin Tabs ———
tab1,tab2,tab3 = st.tabs(["All Jobs","All Customers","All Machines"])
with tab1: st.header("All Job Logs");     st.dataframe(jobs)
with tab2: st.header("All Customers");    st.dataframe(customers)
with tab3: st.header("All Machines");     st.dataframe(machines)
