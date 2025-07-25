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

def load_df(fn,cols):
    return pd.read_csv(fn) if os.path.exists(fn) else pd.DataFrame(columns=cols)

customers = load_df(CUSTOMERS_FILE, CUSTOMERS_COLUMNS)
machines  = load_df(MACHINES_FILE,  MACHINES_COLUMNS)
jobs      = load_df(JOBS_FILE,      JOBS_COLUMNS)

st.title("Coffee Machine Service Logger")

# --- Brands & Models Data ---
coffee_brands = {
    "Bezzera": ["BZ10","DUO","Magica","Matrix","Mitica"],
    "Breville": ["Barista Express","Barista Pro","Duo Temp","Infuser","Oracle Touch"],
    # ... (other brands omitted for brevity; include full list as before) ...
    "WMF": ["1100 S","1500 S+","5000 S+","9000 S+","Espresso"],
    "Other": ["Other"]
}

# Prepare ordered brand list (alphabetical, then Other)
brands_no_other = sorted([b for b in coffee_brands if b!="Other"])
brand_order = brands_no_other + ["Other"]
# Sort each model list
for b in coffee_brands:
    ms = sorted([m for m in coffee_brands[b] if m!="Other"])
    if "Other" in coffee_brands[b]:
        ms.append("Other")
    coffee_brands[b] = ms

# Year options
current_year = datetime.now().year
years = list(range(1970, current_year+1))[::-1]

# -------------------- CUSTOMER FORM --------------------
cust_opts = customers["Company Name"].tolist()
sel_cust = st.selectbox("Select customer", ["Add new..."]+cust_opts)

if sel_cust=="Add new...":
    with st.form("new_cust"):
        cname   = st.text_input("Company Name*")
        contact = st.text_input("Contact Name*")
        addr    = st.text_input("Address* (e.g. 123 Main St, City)")
        phone   = st.text_input("Phone* (000-000-0000)")
        email   = st.text_input("Email* (you@example.com)")

        errs=[]
        if not cname.strip():   errs.append("Company Name required.")
        if not contact.strip(): errs.append("Contact Name required.")
        if not re.match(r'.+\d+.+', addr) or len(addr.split())<3:
            errs.append("Enter a real address.")
        if not re.match(r'^\d{3}-\d{3}-\d{4}$', phone):
            errs.append("Phone must be 000-000-0000.")
        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
            errs.append("Enter a valid email.")

        if not errs:
            murl=f"https://www.google.com/maps/search/{addr.replace(' ','+')}"
            st.markdown(f"[Preview on Google Maps]({murl})")

        sub=st.form_submit_button("Save Customer")
        if sub:
            if errs:
                st.error("\n".join(errs))
            else:
                cid=str(uuid.uuid4())
                new=pd.DataFrame([{
                  "ID":cid,"Company Name":cname,"Contact Name":contact,
                  "Address":addr,"Phone":phone,"Email":email
                }])
                customers=pd.concat([customers,new],ignore_index=True)
                customers.to_csv(CUSTOMERS_FILE,index=False)
                st.success("Customer saved! Reload to select.")
                st.stop()
else:
    # -------------------- MACHINE FORM --------------------
    cid = customers.loc[customers["Company Name"]==sel_cust,"ID"].iat[0]

    # Show existing machines
    exist = machines[machines["Customer ID"]==cid]
    labels = [f"{r.Brand} ({r.Model})" for _,r in exist.iterrows()]
    ids    = exist["ID"].tolist()
    sel_lbl= st.selectbox("Select machine", ["Add new..."]+labels)

    if sel_lbl=="Add new...":
        # Initialize session state
        for k in ("brand","prev_brand","model","custom_brand","custom_model"):
            if k not in st.session_state: st.session_state[k]=""

        # --- Brand (outside form) ---
        brand = st.selectbox(
            "Brand*", [""]+brand_order,
            index=brand_order.index(st.session_state.brand)+1 if st.session_state.brand in brand_order else 0,
            key="brand"
        )
        # Reset model/custom inputs on brand change
        if brand!=st.session_state.prev_brand:
            st.session_state.prev_brand = brand
            st.session_state.model = ""
            st.session_state.custom_model = ""
            st.session_state.custom_brand = ""

        custom_brand=""
        if brand=="Other":
            custom_brand = st.text_input("Enter new brand*", key="custom_brand")

        # Determine model options
        if brand in coffee_brands:
            opts = coffee_brands[brand]
        elif brand=="Other":
            opts = ["Other"]
        else:
            opts = []

        model = st.selectbox(
            "Model*", [""]+opts,
            index=opts.index(st.session_state.model)+1 if st.session_state.model in opts else 0,
            key="model"
        )
        custom_model=""
        if model=="Other":
            custom_model = st.text_input("Enter new model*", key="custom_model")

        # --- Form for the rest ---
        with st.form("new_machine"):
            year   = st.selectbox("Year*",[""]+[str(y) for y in years], key="year")
            serial= st.text_input("Serial Number (optional)", key="serial")
            obs   = st.text_area("Observations (optional)", key="obs")
            photo = st.file_uploader("Upload machine photo*", type=["jpg","png"], key="photo")

            errs=[]
            # Validate brand/custom_brand
            final_brand=brand
            if not brand:
                errs.append("Brand required.")
            elif brand=="Other":
                if not custom_brand.strip(): errs.append("Enter new brand.")
                else: final_brand=custom_brand.strip()

            # Validate model/custom_model
            final_model=model
            if not model:
                errs.append("Model required.")
            elif model=="Other":
                if not custom_model.strip(): errs.append("Enter new model.")
                else: final_model=custom_model.strip()

            if not st.session_state.year:
                errs.append("Year required.")
            if not photo:
                errs.append("Photo required.")

            sub2 = st.form_submit_button("Save Machine")
            if sub2:
                if errs:
                    st.error("\n".join(errs))
                else:
                    mid = str(uuid.uuid4())
                    pth = f"{mid}_machine.png"
                    Image.open(photo).save(pth)
                    newm=pd.DataFrame([{
                      "ID":mid,"Customer ID":cid,
                      "Brand":final_brand,"Model":final_model,
                      "Year":st.session_state.year,
                      "Serial Number":serial,
                      "Photo Path":pth,"Observations":obs
                    }])
                    machines=pd.concat([machines,newm],ignore_index=True)
                    machines.to_csv(MACHINES_FILE,index=False)
                    st.success("Machine saved! Reload to select.")
                    st.stop()

    else:
        idx = labels.index(sel_lbl)
        mid = ids[idx]

        # -------------------- JOB FORM --------------------
        st.subheader("Log a Job")
        with st.form("log_job"):
            employee   = st.text_input("Employee Name")
            technician = st.selectbox("Technician",["Adonai Garcia","Miki Horvath"])
            job_date   = st.date_input("Date", datetime.now())
            travel     = st.number_input("Travel Time (min)",0, step=1)
            t_in       = st.time_input("Time In")
            t_out      = st.time_input("Time Out")
            desc       = st.text_area("Job Description")
            parts      = st.text_area("Parts Used (optional)")
            comments   = st.text_area("Additional Comments (optional)")
            found      = st.file_uploader("Machine as Found",type=["jpg","png","mp4"])
            left       = st.file_uploader("Machine as Left",type=["jpg","png","mp4"])
            st.write("Draw signature:")
            sigimg     = st_canvas(
                            fill_color="rgba(255,255,255,1)",stroke_width=2,
                            stroke_color="#000",background_color="#fff",
                            height=100,width=300,drawing_mode="freedraw",key="sig"
                        )

            sub3 = st.form_submit_button("Submit Job")
            req = all([employee,technician,job_date,travel,t_in,t_out,desc])
            if sub3 and req:
                jid=str(uuid.uuid4())
                # signature
                sigpth=""
                if sigimg.image_data is not None:
                    im=Image.fromarray(sigimg.image_data)
                    sigpth=f"{jid}_signature.png"; im.save(sigpth)
                # found
                fpth=""
                if found:
                    ext=found.name.split(".")[-1]; fpth=f"{jid}_found.{ext}"
                    open(fpth,"wb").write(found.read())
                # left
                lpth=""
                if left:
                    ext=left.name.split(".")[-1]; lpth=f"{jid}_left.{ext}"
                    open(lpth,"wb").write(left.read())
                newj=pd.DataFrame([{
                  "Job ID":jid,"Customer ID":cid,"Machine ID":mid,
                  "Employee Name":employee,"Technician":technician,
                  "Date":str(job_date),"Travel Time (min)":int(travel),
                  "Time In":str(t_in),"Time Out":str(t_out),
                  "Job Description":desc,"Parts Used":parts,
                  "Additional Comments":comments,
                  "Machine as Found Path":fpth,
                  "Machine as Left Path":lpth,
                  "Signature Path":sigpth
                }])
                jobs=pd.concat([jobs,newj],ignore_index=True)
                jobs.to_csv(JOBS_FILE,index=False)
                st.success("Job logged successfully!")
                st.markdown("### Preview")
                st.write(f"Customer: {sel_cust}")
                st.write(f"Machine: {sel_lbl}")
                st.write(f"Employee: {employee}")
                st.write(f"Technician: {technician}")
                st.write(f"Date: {job_date}")
                st.write(f"Travel Time: {travel} min")
                st.write(f"Time In: {t_in}  Time Out: {t_out}")
                st.write(f"Job Description: {desc}")
                if parts: st.write(f"Parts Used: {parts}")
                if comments: st.write(f"Additional Comments: {comments}")
                if sigpth: st.image(sigpth,caption="Signature",width=150)
                if fpth and os.path.exists(fpth):
                    if fpth.endswith(".mp4"): st.video(fpth)
                    else: st.image(fpth,caption="Machine as Found",width=150)
                if lpth and os.path.exists(lpth):
                    if lpth.endswith(".mp4"): st.video(lpth)
                    else: st.image(lpth,caption="Machine as Left",width=150)

# --- Admin Tabs ---
t1,t2,t3 = st.tabs(["All Jobs","All Customers","All Machines"])
with t1: st.header("All Job Logs");     st.dataframe(jobs)
with t2: st.header("All Customers");    st.dataframe(customers)
with t3: st.header("All Machines");     st.dataframe(machines)
