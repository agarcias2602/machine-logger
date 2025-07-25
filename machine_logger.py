import re
import streamlit as st
import pandas as pd
import uuid
from PIL import Image
from streamlit_drawable_canvas import st_canvas
import os
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

# --- Brands & Models Data ---
coffee_brands = {
    "Bezzera": ["BZ10","DUO","Magica","Matrix","Mitica"],
    "Breville": ["Barista Express","Barista Pro","Duo Temp","Infuser","Oracle Touch"],
    # ... include other brands ...
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

current_year = datetime.now().year
years = list(range(1970, current_year+1))[::-1]

# -------------------- CUSTOMER FORM --------------------
cust_names = list(customers["Company Name"])
sel_cust   = st.selectbox("Select customer", ["Add new..."] + cust_names)

if sel_cust=="Add new...":
    with st.form("new_customer"):
        cname   = st.text_input("Company Name*")
        contact = st.text_input("Contact Name*")
        addr    = st.text_input("Address*")
        phone   = st.text_input("Phone* (000-000-0000)")
        email   = st.text_input("Email*")
        errs=[]
        if not cname: errs.append("Name required")
        if not contact: errs.append("Contact required")
        if not re.match(r'\d{3}-\d{3}-\d{4}', phone): errs.append("Phone format")
        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email): errs.append("Email invalid")
        sub = st.form_submit_button("Save Customer")
        if sub:
            if errs:
                st.error("\n".join(errs))
            else:
                cid=str(uuid.uuid4())
                row=pd.DataFrame([{
                  "ID":cid,"Company Name":cname,"Contact Name":contact,
                  "Address":addr,"Phone":phone,"Email":email
                }])
                customers=pd.concat([customers,row],ignore_index=True)
                customers.to_csv(CUSTOMERS_FILE,index=False)
                st.success("Customer saved! Reload to select.")
                st.stop()

else:
    # -------------------- MACHINE SELECTION & VIEW --------------------
    cid = customers.loc[customers["Company Name"]==sel_cust,"ID"].iat[0]
    cust_machs = machines[machines["Customer ID"]==cid]
    labels = [f"{r.Brand} ({r.Model})" for _,r in cust_machs.iterrows()]
    ids    = cust_machs["ID"].tolist()

    sel_machine = st.selectbox("Select machine", ["Add new..."]+labels)

    if sel_machine=="Add new...":
        with st.form("new_machine"):
            brand = st.selectbox("Brand*", [""]+brand_order)
            custom_b = st.text_input("New brand*") if brand=="Other" else ""
            opts = coffee_brands.get(brand,["Other"] if brand=="Other" else [])
            model = st.selectbox("Model*", [""]+opts)
            custom_m = st.text_input("New model*") if model=="Other" else ""
            year   = st.selectbox("Year*", [""]+[str(y) for y in years])
            serial = st.text_input("Serial Number (opt)")
            obs    = st.text_area("Observations (opt)")
            photo  = st.file_uploader("Machine photo*", type=["jpg","png"])
            errs=[]
            fb = custom_b.strip() if brand=="Other" else brand
            fm = custom_m.strip() if model=="Other" else model
            if not fb: errs.append("Brand req")
            if not fm: errs.append("Model req")
            if not year: errs.append("Year req")
            if not photo: errs.append("Photo req")
            sub2=st.form_submit_button("Save Machine")
            if sub2:
                if errs: st.error("\n".join(errs))
                else:
                    mid=str(uuid.uuid4()); path=f"{mid}_machine.png"; Image.open(photo).save(path)
                    row=pd.DataFrame([{
                      "ID":mid,"Customer ID":cid,
                      "Brand":fb,"Model":fm,"Year":year,
                      "Serial Number":serial,"Photo Path":path,"Observations":obs
                    }])
                    machines=pd.concat([machines,row],ignore_index=True)
                    machines.to_csv(MACHINES_FILE,index=False)
                    st.success("Machine saved! Reload.")
                    st.stop()
    else:
        # VIEW selected machine
        idx=labels.index(sel_machine)
        mrow=cust_machs.iloc[idx]
        st.text_input("Brand",         value=mrow["Brand"], disabled=True)
        st.text_input("Model",         value=mrow["Model"], disabled=True)
        st.text_input("Year",          value=mrow["Year"],  disabled=True)
        st.text_input("Serial Number", value=mrow["Serial Number"], disabled=True)
        st.text_area("Observations",   value=mrow["Observations"],   disabled=True)
        pp=mrow["Photo Path"]
        if pp and os.path.exists(pp):
            st.image(pp,caption="Photo",width=200)

        # -------------------- JOB FORM --------------------
        st.subheader("Log a Job")
        with st.form("log_job"):
            employee = st.text_input("Employee Name")
            technician = st.selectbox("Technician",["Adonai Garcia","Miki Horvath"])
            job_date = st.date_input("Date",datetime.now())
            travel   = st.number_input("Travel Time (min)",0)
            tin      = st.time_input("Time In")
            tout     = st.time_input("Time Out")
            desc     = st.text_area("Job Description")
            parts    = st.text_area("Parts Used (opt)")
            comm     = st.text_area("Additional Comments (opt)")
            found    = st.file_uploader("Machine as Found", type=["jpg","png","mp4"])
            left     = st.file_uploader("Machine as Left",  type=["jpg","png","mp4"])
            sig      = st_canvas(
                          fill_color="rgba(255,255,255,1)", stroke_width=2,
                          stroke_color="#000", background_color="#fff",
                          height=100, width=300, drawing_mode="freedraw", key="sig"
                       )
            sub3=st.form_submit_button("Submit Job")
            if sub3 and all([employee,technician,job_date,travel,tin,tout,desc]):
                jid=str(uuid.uuid4())
                sigpth=""
                if sig.image_data is not None:
                    im=Image.fromarray(sig.image_data)
                    sigpth=f"{jid}_sig.png"; im.save(sigpth)
                fpth=""; lpth=""
                if found:
                    ext=found.name.split(".")[-1]; fpth=f"{jid}_found.{ext}"
                    open(fpth,"wb").write(found.read())
                if left:
                    ext=left.name.split(".")[-1]; lpth=f"{jid}_left.{ext}"
                    open(lpth,"wb").write(left.read())
                newj=pd.DataFrame([{
                  "Job ID":jid,"Customer ID":cid,"Machine ID":ids[idx],
                  "Employee Name":employee,"Technician":technician,
                  "Date":str(job_date),"Travel Time (min)":int(travel),
                  "Time In":str(tin),"Time Out":str(tout),
                  "Job Description":desc,"Parts Used":parts,
                  "Additional Comments":comm,
                  "Machine as Found Path":fpth,
                  "Machine as Left Path":lpth,
                  "Signature Path":sigpth
                }])
                jobs=pd.concat([jobs,newj],ignore_index=True)
                jobs.to_csv(JOBS_FILE,index=False)
                st.success("Job logged!")
                st.markdown("### Preview")
                st.write(f"Customer: {sel_cust}")
                st.write(f"Machine: {sel_machine}")
                st.write(f"Employee: {employee}")
                st.write(f"Technician: {technician}")
                st.write(f"Date: {job_date}")
                st.write(f"Travel Time: {travel} min")
                st.write(f"Time In: {tin}  Time Out: {tout}")
                st.write(f"Description: {desc}")
                if parts:   st.write(f"Parts Used: {parts}")
                if comm:    st.write(f"Comments: {comm}")
                if sigpth:  st.image(sigpth,caption="Signature",width=150)
                if fpth and os.path.exists(fpth):
                    if fpth.endswith(".mp4"): st.video(fpth)
                    else: st.image(fpth,caption="Found",width=150)
                if lpth and os.path.exists(lpth):
                    if lpth.endswith(".mp4"): st.video(lpth)
                    else: st.image(lpth,caption="Left",width=150)

# --- Admin Tabs ---
tab1,tab2,tab3 = st.tabs(["All Jobs","All Customers","All Machines"])
with tab1:
    st.header("All Job Logs");     st.dataframe(jobs)
with tab2:
    st.header("All Customers");    st.dataframe(customers)
with tab3:
    st.header("All Machines");     st.dataframe(machines)
