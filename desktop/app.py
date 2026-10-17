import sqlite3
import tkinter as tk
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from tkinter import messagebox, ttk

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "mes.db"
NAV_ITEMS = ["대시보드", "생산계획", "작업지시", "생산실적", "불량관리", "설비현황", "기준정보"]
BG, NAVY, BLUE, TEXT, MUTED = "#f3f6fa", "#14243a", "#2764e7", "#243247", "#718096"


class MESApp:
    def __init__(self, root):
        self.root = root
        root.title("스마트팩토리 MES 생산관리 시스템")
        root.geometry("1450x900")
        root.minsize(1050, 700)
        root.configure(bg=BG)
        self.page = "대시보드"
        self.selected_id = None
        self.init_db()
        self.configure_style()
        self.build_shell()
        self.show_page(self.page)
        self.update_clock()

    @contextmanager
    def connect(self):
        db = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def init_db(self):
        with self.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS products(product_code TEXT PRIMARY KEY, product_name TEXT NOT NULL, unit TEXT NOT NULL DEFAULT '개', active INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS production_records(id INTEGER PRIMARY KEY AUTOINCREMENT, work_date TEXT NOT NULL, product_code TEXT NOT NULL, product_name TEXT NOT NULL, plan_qty INTEGER NOT NULL CHECK(plan_qty>=0), produced_qty INTEGER NOT NULL CHECK(produced_qty>=0), defect_qty INTEGER NOT NULL CHECK(defect_qty>=0), created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            CREATE INDEX IF NOT EXISTS idx_production_date ON production_records(work_date);
            CREATE TABLE IF NOT EXISTS production_plans(id INTEGER PRIMARY KEY AUTOINCREMENT, plan_date TEXT NOT NULL, product_code TEXT NOT NULL REFERENCES products(product_code), product_name TEXT NOT NULL, plan_qty INTEGER NOT NULL CHECK(plan_qty>=0), due_date TEXT NOT NULL, status TEXT NOT NULL DEFAULT '계획' CHECK(status IN ('계획','확정','완료')), created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS work_orders(id INTEGER PRIMARY KEY AUTOINCREMENT, order_no TEXT NOT NULL UNIQUE, plan_id INTEGER REFERENCES production_plans(id) ON DELETE SET NULL, work_date TEXT NOT NULL, product_code TEXT NOT NULL REFERENCES products(product_code), product_name TEXT NOT NULL, order_qty INTEGER NOT NULL CHECK(order_qty>=0), equipment_code TEXT NOT NULL REFERENCES equipment(equipment_code), status TEXT NOT NULL DEFAULT '대기' CHECK(status IN ('대기','작업중','완료')), created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS production_entries(id INTEGER PRIMARY KEY AUTOINCREMENT, work_order_id INTEGER NOT NULL REFERENCES work_orders(id) ON DELETE CASCADE, work_date TEXT NOT NULL, produced_qty INTEGER NOT NULL CHECK(produced_qty>=0), defect_qty INTEGER NOT NULL CHECK(defect_qty>=0 AND defect_qty<=produced_qty), created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS defects(id INTEGER PRIMARY KEY AUTOINCREMENT, production_id INTEGER REFERENCES production_entries(id) ON DELETE SET NULL, work_order_id INTEGER NOT NULL REFERENCES work_orders(id) ON DELETE CASCADE, work_date TEXT NOT NULL, product_code TEXT NOT NULL REFERENCES products(product_code), product_name TEXT NOT NULL, defect_type TEXT NOT NULL, defect_qty INTEGER NOT NULL CHECK(defect_qty>=0), cause TEXT NOT NULL DEFAULT '', action TEXT NOT NULL DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS equipment(equipment_code TEXT PRIMARY KEY, equipment_name TEXT NOT NULL, status TEXT NOT NULL DEFAULT '정지' CHECK(status IN ('가동','정지','점검','이상')));
            CREATE INDEX IF NOT EXISTS idx_plans_date ON production_plans(plan_date);
            CREATE INDEX IF NOT EXISTS idx_orders_date ON work_orders(work_date);
            CREATE INDEX IF NOT EXISTS idx_entries_date ON production_entries(work_date);
            """)
            if not db.execute("SELECT 1 FROM products LIMIT 1").fetchone():
                db.executemany("INSERT INTO products(product_code,product_name) VALUES (?,?)", [("P001","기어 A"),("P002","기어 B"),("P003","스프링 A")])
            if not db.execute("SELECT 1 FROM production_records LIMIT 1").fetchone():
                today = date.today().isoformat()
                db.executemany("INSERT INTO production_records(work_date,product_code,product_name,plan_qty,produced_qty,defect_qty) VALUES (?,?,?,?,?,?)", [(today,"P001","기어 A",500,462,8),(today,"P002","기어 B",350,331,5),(today,"P003","스프링 A",240,224,4),(today,"P001","기어 A",180,175,2),(today,"P002","기어 B",120,116,1)])
            for code in ("CNC-01","CNC-02","PRESS-01","ASSY-01"):
                db.execute("INSERT OR IGNORE INTO equipment(equipment_code,equipment_name,status) VALUES (?,?,?)", (code, code, "가동" if code in ("CNC-01","ASSY-01") else "정지"))

    def configure_style(self):
        style = ttk.Style(); style.theme_use("clam")
        style.configure("Treeview", rowheight=30, font=("Malgun Gothic",9), background="white", fieldbackground="white", foreground=TEXT)
        style.configure("Treeview.Heading", font=("Malgun Gothic",9,"bold"), background="#eaf0f7", foreground=NAVY, padding=7)
        style.map("Treeview", background=[("selected","#dbeafe")], foreground=[("selected",NAVY)])
        style.configure("TEntry", padding=6, font=("Malgun Gothic",9)); style.configure("TCombobox", padding=5, font=("Malgun Gothic",9))
        style.configure("Primary.TButton", font=("Malgun Gothic",9,"bold"), padding=(12,7), background=BLUE, foreground="white")
        style.configure("Action.TButton", font=("Malgun Gothic",9), padding=(10,6))

    def build_shell(self):
        side=tk.Frame(self.root,bg=NAVY,width=220); side.pack(side="left",fill="y"); side.pack_propagate(False)
        tk.Label(side,text="MES",bg=NAVY,fg="white",font=("Malgun Gothic",25,"bold")).pack(anchor="w",padx=22,pady=(24,0))
        tk.Label(side,text="스마트팩토리 생산관리",bg=NAVY,fg="#a9bbd2",font=("Malgun Gothic",9)).pack(anchor="w",padx=24,pady=(0,25))
        self.nav_buttons={}
        for item in NAV_ITEMS:
            b=tk.Button(side,text="  "+item,anchor="w",bd=0,bg=NAVY,fg="#d7e0ec",activebackground="#263c59",activeforeground="white",font=("Malgun Gothic",10),padx=16,pady=12,command=lambda n=item:self.show_page(n)); b.pack(fill="x",padx=10,pady=2); self.nav_buttons[item]=b
        tk.Label(side,text="LOCAL DATABASE · SQLite",bg=NAVY,fg="#8296b1",font=("Malgun Gothic",8)).pack(side="bottom",anchor="w",padx=18,pady=18)
        main=tk.Frame(self.root,bg=BG); main.pack(side="left",fill="both",expand=True)
        header=tk.Frame(main,bg="white",height=62); header.pack(fill="x"); header.pack_propagate(False)
        self.page_title=tk.Label(header,text="",bg="white",fg=NAVY,font=("Malgun Gothic",15,"bold")); self.page_title.pack(side="left",padx=25)
        self.clock_label=tk.Label(header,text="",bg="white",fg=MUTED,font=("Malgun Gothic",9)); self.clock_label.pack(side="right",padx=25)
        self.content=tk.Frame(main,bg=BG); self.content.pack(fill="both",expand=True,padx=22,pady=18)
        self.status=tk.Label(main,text=f"데이터베이스: {DB_PATH.name}",anchor="w",bg="white",fg=MUTED,padx=18,pady=7,font=("Malgun Gothic",8)); self.status.pack(fill="x",side="bottom")

    def update_clock(self):
        self.clock_label.config(text=datetime.now().strftime("%Y-%m-%d %H:%M:%S")); self.root.after(1000,self.update_clock)

    def clear_content(self):
        for w in self.content.winfo_children(): w.destroy()

    def show_page(self,page):
        self.page=page; self.clear_content(); self.page_title.config(text=page)
        for n,b in self.nav_buttons.items(): b.configure(bg="#263c59" if n==page else NAVY,fg="white" if n==page else "#d7e0ec")
        {"대시보드":self.show_dashboard,"생산계획":self.show_plans,"작업지시":self.show_orders,"생산실적":self.show_production,"불량관리":self.show_defects,"설비현황":self.show_equipment,"기준정보":self.show_master}[page]()

    def section(self,parent,title,subtitle=""):
        f=tk.Frame(parent,bg="white",highlightthickness=1,highlightbackground="#e7ecf2",padx=14,pady=12)
        bar=tk.Frame(f,bg="white"); bar.pack(fill="x",pady=(0,9)); tk.Label(bar,text=title,bg="white",fg=NAVY,font=("Malgun Gothic",11,"bold")).pack(side="left")
        if subtitle: tk.Label(bar,text=subtitle,bg="white",fg=MUTED,font=("Malgun Gothic",8)).pack(side="right")
        return f

    def tree(self,parent,cols,labels,height=11):
        wrap=tk.Frame(parent,bg="white"); wrap.pack(fill="both",expand=True)
        tr=ttk.Treeview(wrap,columns=cols,show="headings",height=height)
        for c,l in zip(cols,labels): tr.heading(c,text=l); tr.column(c,width=110,anchor="center",stretch=True)
        y=ttk.Scrollbar(wrap,orient="vertical",command=tr.yview); tr.configure(yscrollcommand=y.set); tr.pack(side="left",fill="both",expand=True); y.pack(side="right",fill="y")
        return tr

    def show_dashboard(self):
        with self.connect() as db:
            t=date.today().isoformat()
            plan=db.execute("SELECT COALESCE(SUM(plan_qty),0) FROM production_plans WHERE plan_date=?",(t,)).fetchone()[0]
            order=db.execute("SELECT COALESCE(SUM(order_qty),0) FROM work_orders WHERE work_date=?",(t,)).fetchone()[0]
            prod,defect=db.execute("SELECT COALESCE(SUM(produced_qty),0),COALESCE(SUM(defect_qty),0) FROM production_entries WHERE work_date=?",(t,)).fetchone()
            running=db.execute("SELECT COUNT(*) FROM equipment WHERE status='가동'").fetchone()[0]
            records=db.execute("SELECT COALESCE(SUM(produced_qty),0),COALESCE(SUM(defect_qty),0) FROM production_records WHERE work_date=?",(t,)).fetchone()
            # 레거시 실적은 새 작업지시 실적이 없는 날짜에만 기존 대시보드 수치에 반영
            if not prod and not defect: prod,defect=records
        good=prod-defect; achieve=prod/order*100 if order else 0; defect_rate=defect/prod*100 if prod else 0
        tk.Label(self.content,text="오늘의 생산 현황",bg=BG,fg=NAVY,font=("Malgun Gothic",17,"bold")).pack(anchor="w",pady=(0,12))
        data=[("금일 계획수량",plan,"개",BLUE),("금일 지시수량",order,"개","#8156d9"),("금일 생산수량",prod,"개","#0f9f83"),("금일 양품수량",good,"개","#07877e"),("금일 불량수량",defect,"개","#e35b5b"),("생산달성률",f"{achieve:.1f}","%","#8156d9"),("불량률",f"{defect_rate:.2f}","%","#dd8b25"),("가동 설비수",running,"대","#0f9f83")]
        grid=tk.Frame(self.content,bg=BG); grid.pack(fill="x")
        for c in range(4): grid.columnconfigure(c,weight=1,uniform="k")
        for i,(label,value,unit,color) in enumerate(data):
            card=tk.Frame(grid,bg="white",highlightthickness=1,highlightbackground="#e7ecf2",padx=14,pady=12); card.grid(row=i//4,column=i%4,sticky="nsew",padx=(0 if i%4==0 else 7,7 if i%4<3 else 0),pady=(0,10))
            tk.Label(card,text=label,bg="white",fg=MUTED,font=("Malgun Gothic",9)).pack(anchor="w"); tk.Label(card,text=f"{value:,} {unit}" if isinstance(value,int) else f"{value} {unit}",bg="white",fg=color,font=("Malgun Gothic",20,"bold")).pack(anchor="w",pady=(6,0))
        box=self.section(self.content,"최근 작업지시","최근 10건"); box.pack(fill="both",expand=True,pady=(3,0))
        tr=self.tree(box,("no","date","product","qty","equipment","status"),("작업지시번호","작업일자","제품명","지시수량","설비","상태"),8)
        with self.connect() as db: rows=db.execute("SELECT order_no,work_date,product_name,order_qty,equipment_code,status FROM work_orders ORDER BY id DESC LIMIT 10").fetchall()
        for r in rows: tr.insert("","end",values=tuple(r))

    def products(self):
        with self.connect() as db: return db.execute("SELECT product_code,product_name FROM products WHERE active=1 ORDER BY product_code").fetchall()
    def plans(self):
        with self.connect() as db: return db.execute("SELECT id,plan_date,product_code,product_name,plan_qty,due_date,status FROM production_plans ORDER BY plan_date DESC,id DESC").fetchall()
    def orders(self):
        with self.connect() as db: return db.execute("SELECT w.id,w.order_no,w.plan_id,w.work_date,w.product_code,w.product_name,w.order_qty,w.equipment_code,w.status FROM work_orders w ORDER BY w.work_date DESC,w.id DESC").fetchall()
    def equipment_rows(self):
        with self.connect() as db: return db.execute("SELECT equipment_code,equipment_name,status FROM equipment ORDER BY equipment_code").fetchall()

    def form_page(self,title,fields,table,columns,labels,loader,save,delete,select_callback=None):
        self.selected_id=None; self.form_vars={k:tk.StringVar() for k,_,_ in fields}; self.form_widgets={}
        panel=self.section(self.content,title,"필수 항목을 입력한 뒤 저장하세요"); panel.pack(fill="x",pady=(0,12))
        for i,(key,label,choices) in enumerate(fields):
            panel.columnconfigure(i,weight=1); cell=tk.Frame(panel,bg="white"); cell.grid(row=1,column=i,sticky="ew",padx=(0,8),pady=(0,8)); tk.Label(cell,text=label,bg="white",fg=MUTED,font=("Malgun Gothic",8)).pack(anchor="w",pady=(0,4))
            if choices is not None: w=ttk.Combobox(cell,textvariable=self.form_vars[key],values=choices,state="readonly")
            else: w=ttk.Entry(cell,textvariable=self.form_vars[key])
            w.pack(fill="x"); self.form_widgets[key]=w
        actions=tk.Frame(panel,bg="white"); actions.grid(row=2,column=0,columnspan=max(1,len(fields)),sticky="w",pady=(2,0))
        ttk.Button(actions,text="신규",command=lambda:self.reset_form(fields),style="Action.TButton").pack(side="left",padx=(0,6))
        ttk.Button(actions,text="저장",command=lambda:self.save_form(fields,save,loader),style="Primary.TButton").pack(side="left",padx=6)
        ttk.Button(actions,text="삭제",command=lambda:self.delete_form(delete,loader),style="Action.TButton").pack(side="left",padx=6)
        ttk.Button(actions,text="조회/새로고침",command=loader,style="Action.TButton").pack(side="left",padx=6)
        box=self.section(self.content,title+" 목록"); box.pack(fill="both",expand=True)
        self.current_tree=self.tree(box,columns,labels,12); self.current_tree.bind("<<TreeviewSelect>>",lambda e:self.select_form(fields,table,select_callback))
        self.refresh_form_tree(loader)
        self.reset_form(fields)

    def reset_form(self,fields):
        self.selected_id=None
        for key,_,_ in fields:
            default=date.today().isoformat() if key in ("plan_date","work_date","due_date") else "0" if key in ("plan_qty","order_qty","produced_qty","defect_qty") else "계획" if key=="status" and self.page=="생산계획" else "대기" if key=="status" and self.page=="작업지시" else ""
            self.form_vars[key].set(default)
        if self.current_tree.selection(): self.current_tree.selection_remove(self.current_tree.selection())
    def refresh_form_tree(self,loader):
        self.current_tree.delete(*self.current_tree.get_children())
        for r in loader(): self.current_tree.insert("","end",iid=str(r[0]),values=tuple(r[1:]))
    def select_form(self,fields,table,callback=None):
        sel=self.current_tree.selection()
        if not sel:return
        self.selected_id=int(sel[0])
        with self.connect() as db: row=db.execute(f"SELECT * FROM {table} WHERE id=?",(self.selected_id,)).fetchone()
        if row:
            for key,_,_ in fields:
                if key in row.keys(): self.form_vars[key].set(str(row[key]))
            if callback: callback(row)
    def save_form(self,fields,save,loader):
        try:
            vals={k:v.get().strip() for k,v in self.form_vars.items()}; save(vals,self.selected_id)
            self.status.config(text="저장했습니다."); self.refresh_form_tree(loader); self.reset_form(fields)
        except (ValueError,sqlite3.Error) as e: messagebox.showerror("저장 오류",str(e),parent=self.root)
    def delete_form(self,delete,loader):
        if not self.selected_id: messagebox.showwarning("선택 필요","목록에서 삭제할 행을 선택하세요.",parent=self.root); return
        if messagebox.askyesno("삭제 확인","선택한 항목을 삭제하시겠습니까?",parent=self.root):
            try: delete(self.selected_id); self.refresh_form_tree(loader); self.reset_form([]); self.status.config(text="삭제했습니다.")
            except sqlite3.Error as e: messagebox.showerror("삭제 오류",str(e),parent=self.root)

    def valid_date(self,v):
        try: datetime.strptime(v,"%Y-%m-%d")
        except ValueError: raise ValueError("날짜는 YYYY-MM-DD 형식으로 입력하세요.")
    def positive(self,v,label):
        if not v.isdigit(): raise ValueError(f"{label}은 0 이상의 정수로 입력하세요.")
        return int(v)
    def product_fields(self): return [("product_code","제품코드",[p[0] for p in self.products()]),("product_name","제품명",None)]
    def show_plans(self):
        fields=[("plan_date","계획일자",None),("product_code","제품코드",[p[0] for p in self.products()]),("product_name","제품명",None),("plan_qty","계획수량",None),("due_date","납기일",None),("status","상태",["계획","확정","완료"])]
        self.form_page("생산계획",fields,"production_plans",("id","plan_date","product_code","product_name","plan_qty","due_date","status"),("ID","계획일자","제품코드","제품명","계획수량","납기일","상태"),self.plans,self.save_plan,lambda i:self.delete_row("production_plans",i))
        self.form_widgets["product_code"].bind("<<ComboboxSelected>>",lambda e:self.fill_product_name())
    def fill_product_name(self):
        p={r[0]:r[1] for r in self.products()}; code=self.form_vars["product_code"].get(); self.form_vars["product_name"].set(p.get(code,""))
    def save_plan(self,v,i):
        self.valid_date(v["plan_date"]); self.valid_date(v["due_date"]); q=self.positive(v["plan_qty"],"계획수량"); self.fill_product_name(); v["product_name"]=self.form_vars["product_name"].get()
        if not v["product_code"] or not v["product_name"]: raise ValueError("제품을 선택하세요.")
        with self.connect() as db:
            sql="UPDATE production_plans SET plan_date=?,product_code=?,product_name=?,plan_qty=?,due_date=?,status=? WHERE id=?" if i else "INSERT INTO production_plans(plan_date,product_code,product_name,plan_qty,due_date,status) VALUES (?,?,?,?,?,?)"
            args=(v["plan_date"],v["product_code"],v["product_name"],q,v["due_date"],v["status"])+( (i,) if i else () ); db.execute(sql,args)
    def show_orders(self):
        plans=self.plans(); choices=[f"{r['id']} | {r['plan_date']} | {r['product_code']} {r['product_name']} | {r['plan_qty']}" for r in plans]
        equipments=[r[0] for r in self.equipment_rows()]
        fields=[("plan_display","생산계획 선택",choices),("work_date","작업일자",None),("product_code","제품코드",None),("product_name","제품명",None),("order_qty","지시수량",None),("equipment_code","설비",equipments),("status","작업상태",["대기","작업중","완료"])]
        self.plan_choice_map=dict(zip(choices,plans))
        def loader(): return self.orders()
        def save(v,i):
            self.valid_date(v["work_date"]); q=self.positive(v["order_qty"],"지시수량")
            plan=self.plan_choice_map.get(v["plan_display"])
            code,name=v["product_code"],v["product_name"]
            if plan:
                code,name=plan["product_code"],plan["product_name"]
                if not q: q=plan["plan_qty"]
            if not code or not name or not v["equipment_code"]: raise ValueError("생산계획과 설비를 선택하세요.")
            with self.connect() as db:
                if i: db.execute("UPDATE work_orders SET plan_id=?,work_date=?,product_code=?,product_name=?,order_qty=?,equipment_code=?,status=? WHERE id=?",(plan["id"] if plan else None,v["work_date"],code,name,q,v["equipment_code"],v["status"],i))
                else:
                    day=v["work_date"].replace("-",""); prefix=f"WO-{day}-"; seq=db.execute("SELECT COUNT(*)+1 FROM work_orders WHERE order_no LIKE ?",(prefix+"%",)).fetchone()[0]; no=f"{prefix}{seq:03d}"
                    db.execute("INSERT INTO work_orders(order_no,plan_id,work_date,product_code,product_name,order_qty,equipment_code,status) VALUES (?,?,?,?,?,?,?,?)",(no,plan["id"] if plan else None,v["work_date"],code,name,q,v["equipment_code"],v["status"]))
        self.form_page("작업지시",fields,"work_orders",("id","order_no","plan_id","work_date","product_code","product_name","order_qty","equipment_code","status"),("ID","작업지시번호","계획ID","작업일자","제품코드","제품명","지시수량","설비","상태"),loader,save,lambda i:self.delete_row("work_orders",i),lambda row:self.load_order_plan(row,choices,plans))
        self.form_widgets["plan_display"].bind("<<ComboboxSelected>>",lambda e:self.order_plan_selected())
    def load_order_plan(self,row,choices,plans):
        if row["plan_id"]:
            for s,p in zip(choices,plans):
                if p["id"]==row["plan_id"]: self.form_vars["plan_display"].set(s); break
    def order_plan_selected(self):
        p=self.plan_choice_map.get(self.form_vars["plan_display"].get())
        if p:
            self.form_vars["product_code"].set(p["product_code"]); self.form_vars["product_name"].set(p["product_name"]); self.form_vars["order_qty"].set(str(p["plan_qty"]))
    def delete_row(self,table,i):
        with self.connect() as db: db.execute(f"DELETE FROM {table} WHERE id=?",(i,))

    def entries(self):
        with self.connect() as db: return db.execute("SELECT e.id,e.work_order_id,w.order_no,e.work_date,w.product_code,w.product_name,w.order_qty,e.produced_qty,e.defect_qty,e.produced_qty-e.defect_qty good_qty,CASE WHEN w.order_qty>0 THEN ROUND(e.produced_qty*100.0/w.order_qty,1) ELSE 0 END attainment FROM production_entries e JOIN work_orders w ON w.id=e.work_order_id ORDER BY e.work_date DESC,e.id DESC").fetchall()
    def show_production(self):
        orders=self.orders(); choices=[f"{r['id']} | {r['order_no']} | {r['product_name']} | 지시 {r['order_qty']}" for r in orders]; self.order_choice_map=dict(zip(choices,orders))
        fields=[("order_display","작업지시 선택",choices),("work_date","작업일자",None),("product_code","제품코드",None),("product_name","제품명",None),("order_qty","계획/지시수량",None),("produced_qty","생산수량",None),("defect_qty","불량수량",None)]
        def save(v,i):
            o=self.order_choice_map.get(v["order_display"]); self.valid_date(v["work_date"])
            if not o: raise ValueError("작업지시를 선택하세요.")
            produced=self.positive(v["produced_qty"],"생산수량"); defect=self.positive(v["defect_qty"],"불량수량")
            if defect>produced: raise ValueError("불량수량은 생산수량을 초과할 수 없습니다.")
            with self.connect() as db:
                if i: db.execute("UPDATE production_entries SET work_order_id=?,work_date=?,produced_qty=?,defect_qty=? WHERE id=?",(o["id"],v["work_date"],produced,defect,i))
                else: db.execute("INSERT INTO production_entries(work_order_id,work_date,produced_qty,defect_qty) VALUES (?,?,?,?)",(o["id"],v["work_date"],produced,defect))
                totals=db.execute("SELECT COALESCE(SUM(produced_qty),0),order_qty FROM production_entries JOIN work_orders ON work_orders.id=work_order_id WHERE work_order_id=?",(o["id"],)).fetchone()
                db.execute("UPDATE work_orders SET status=? WHERE id=?",("완료" if totals[0]>=totals[1] else "작업중",o["id"]))
        self.form_page("생산실적",fields,"production_entries",("id","work_order_id","order_no","work_date","product_code","product_name","order_qty","produced_qty","defect_qty","good_qty","attainment"),("ID","작업지시ID","작업지시번호","작업일자","제품코드","제품명","지시수량","생산수량","불량수량","양품수량","달성률 %"),self.entries,save,lambda i:self.delete_row("production_entries",i),lambda row:self.load_entry_order(row,choices,orders))
        self.form_widgets["order_display"].bind("<<ComboboxSelected>>",lambda e:self.entry_order_selected())
    def load_entry_order(self,row,choices,orders):
        for s,o in zip(choices,orders):
            if o["id"]==row["work_order_id"]: self.form_vars["order_display"].set(s); break
        self.form_vars["produced_qty"].set(str(row["produced_qty"])); self.form_vars["defect_qty"].set(str(row["defect_qty"]))
    def entry_order_selected(self):
        o=self.order_choice_map.get(self.form_vars["order_display"].get())
        if o:
            for k,v in (("work_date",o["work_date"]),("product_code",o["product_code"]),("product_name",o["product_name"]),("order_qty",o["order_qty"])): self.form_vars[k].set(str(v))
    def defects_rows(self):
        with self.connect() as db: return db.execute("SELECT d.id,d.work_date,w.order_no,d.product_code,d.product_name,d.defect_type,d.defect_qty,d.cause,d.action FROM defects d JOIN work_orders w ON w.id=d.work_order_id ORDER BY d.work_date DESC,d.id DESC").fetchall()
    def show_defects(self):
        entries=self.entries(); choices=[f"{r['work_order_id']} | {r['order_no']} | {r['product_name']}" for r in entries]; self.defect_choice_map={}
        for choice,r in zip(choices,entries): self.defect_choice_map[choice]=r
        fields=[("entry_display","생산실적/작업지시",choices),("work_date","작업일자",None),("product_code","제품코드",None),("product_name","제품명",None),("defect_type","불량유형",["치수불량","외관불량","가공불량","조립불량","기타"]),("defect_qty","불량수량",None),("cause","불량원인",None),("action","조치내용",None)]
        def save(v,i):
            r=self.defect_choice_map.get(v["entry_display"])
            if not r: raise ValueError("연결할 생산실적을 선택하세요.")
            q=self.positive(v["defect_qty"],"불량수량"); self.valid_date(v["work_date"])
            with self.connect() as db:
                order_id=r["work_order_id"]
                if i: db.execute("UPDATE defects SET production_id=?,work_order_id=?,work_date=?,product_code=?,product_name=?,defect_type=?,defect_qty=?,cause=?,action=? WHERE id=?",(r["id"],order_id,v["work_date"],r["product_code"],r["product_name"],v["defect_type"],q,v["cause"],v["action"],i))
                else: db.execute("INSERT INTO defects(production_id,work_order_id,work_date,product_code,product_name,defect_type,defect_qty,cause,action) VALUES (?,?,?,?,?,?,?,?,?)",(r["id"],order_id,v["work_date"],r["product_code"],r["product_name"],v["defect_type"],q,v["cause"],v["action"]))
        self.form_page("불량관리",fields,"defects",("id","work_date","order_no","product_code","product_name","defect_type","defect_qty","cause","action"),("ID","작업일자","작업지시번호","제품코드","제품명","불량유형","불량수량","불량원인","조치내용"),self.defects_rows,save,lambda i:self.delete_row("defects",i),lambda row:self.load_defect(row,choices,entries))
        self.form_widgets["entry_display"].bind("<<ComboboxSelected>>",lambda e:self.defect_selected())
    def load_defect(self,row,choices,entries):
        for s,r in zip(choices,entries):
            if r["id"]==row["production_id"]: self.form_vars["entry_display"].set(s); break
        for k in ("defect_type","defect_qty","cause","action"): self.form_vars[k].set(str(row[k]))
    def defect_selected(self):
        r=self.defect_choice_map.get(self.form_vars["entry_display"].get())
        if r:
            for k in ("work_date","product_code","product_name"): self.form_vars[k].set(str(r[k]))
            self.form_vars["defect_qty"].set(str(r["defect_qty"]))

    def show_equipment(self):
        box=self.section(self.content,"설비 현황","상태를 선택하고 변경 버튼을 누르세요"); box.pack(fill="both",expand=True)
        tr=self.tree(box,("code","name","status"),("설비코드","설비명","상태"),12)
        for r in self.equipment_rows(): tr.insert("","end",iid=r[0],values=tuple(r))
        actions=tk.Frame(box,bg="white"); actions.pack(fill="x",pady=(10,0)); tk.Label(actions,text="선택 설비 상태",bg="white").pack(side="left")
        state=tk.StringVar(value="가동"); ttk.Combobox(actions,textvariable=state,values=["가동","정지","점검","이상"],state="readonly",width=12).pack(side="left",padx=8)
        def update():
            sel=tr.selection()
            if not sel: messagebox.showwarning("선택 필요","설비 행을 선택하세요.",parent=self.root); return
            with self.connect() as db: db.execute("UPDATE equipment SET status=? WHERE equipment_code=?",(state.get(),sel[0]))
            tr.set(sel[0],"status",state.get()); self.status.config(text=f"{sel[0]} 상태를 {state.get()}으로 변경했습니다.")
        ttk.Button(actions,text="상태 변경",command=update,style="Primary.TButton").pack(side="left")
        cards=tk.Frame(self.content,bg=BG); cards.pack(fill="x",pady=12)
        for r in self.equipment_rows():
            c=tk.Frame(cards,bg="white",highlightthickness=1,highlightbackground="#e7ecf2",padx=14,pady=12); c.pack(side="left",fill="x",expand=True,padx=4)
            tk.Label(c,text=r[0],bg="white",fg=NAVY,font=("Malgun Gothic",11,"bold")).pack(anchor="w"); tk.Label(c,text=r[2],bg="white",fg="#0f9f83" if r[2]=="가동" else "#dd8b25",font=("Malgun Gothic",10)).pack(anchor="w",pady=(6,0))

    def show_master(self):
        fields=[("product_code","제품코드",None),("product_name","제품명",None),("unit","단위",None)]
        def loader():
            with self.connect() as db:return db.execute("SELECT product_code,product_name,unit FROM products ORDER BY product_code").fetchall()
        def save(v,i):
            if not v["product_code"] or not v["product_name"]: raise ValueError("제품코드와 제품명을 입력하세요.")
            with self.connect() as db:
                if i:
                    old=db.execute("SELECT product_code FROM products WHERE rowid=?",(i,)).fetchone()
                    if old and old[0]!=v["product_code"]: raise ValueError("등록된 제품코드는 변경할 수 없습니다.")
                    db.execute("UPDATE products SET product_name=?,unit=? WHERE product_code=?",(v["product_name"],v["unit"] or "개",v["product_code"]))
                else: db.execute("INSERT INTO products(product_code,product_name,unit) VALUES (?,?,?)",(v["product_code"],v["product_name"],v["unit"] or "개"))
        # master uses product_code as identity instead of integer id, so expose a specialized CRUD screen
        self.selected_product=None; self.form_vars={k:tk.StringVar() for k,_,_ in fields}
        panel=self.section(self.content,"제품 기준정보","제품을 등록하거나 선택해 수정/삭제하세요"); panel.pack(fill="x",pady=(0,12))
        for i,(key,label,_) in enumerate(fields):
            panel.columnconfigure(i,weight=1); cell=tk.Frame(panel,bg="white"); cell.grid(row=1,column=i,sticky="ew",padx=6); tk.Label(cell,text=label,bg="white",fg=MUTED).pack(anchor="w"); ttk.Entry(cell,textvariable=self.form_vars[key]).pack(fill="x")
        box=self.section(self.content,"제품 목록"); box.pack(fill="both",expand=True); tr=self.tree(box,("code","name","unit"),("제품코드","제품명","단위"),12); self.current_tree=tr
        def refresh():
            tr.delete(*tr.get_children())
            for r in loader():tr.insert("","end",iid=r[0],values=tuple(r))
        def select(_=None):
            s=tr.selection()
            if s:
                self.selected_product=s[0]
                for k,val in zip(("product_code","product_name","unit"),tr.item(s[0],"values")):self.form_vars[k].set(val)
        tr.bind("<<TreeviewSelect>>",select)
        def persist():
            try:save({k:v.get().strip() for k,v in self.form_vars.items()},self.selected_product); refresh(); self.selected_product=None
            except (ValueError,sqlite3.Error) as e:messagebox.showerror("저장 오류",str(e),parent=self.root)
        def delete():
            if not self.selected_product:return
            if messagebox.askyesno("삭제 확인","선택한 제품을 삭제하시겠습니까?",parent=self.root):
                try:
                    with self.connect() as db:db.execute("DELETE FROM products WHERE product_code=?",(self.selected_product,))
                    refresh();self.selected_product=None
                except sqlite3.Error as e:messagebox.showerror("삭제 오류",f"연결된 계획/실적이 있어 삭제할 수 없습니다.\n{e}",parent=self.root)
        actions=tk.Frame(panel,bg="white");actions.grid(row=2,column=0,columnspan=3,sticky="w",pady=8)
        ttk.Button(actions,text="신규",command=lambda:(setattr(self,"selected_product",None),[v.set("") for v in self.form_vars.values()])).pack(side="left",padx=4);ttk.Button(actions,text="저장",command=persist,style="Primary.TButton").pack(side="left",padx=4);ttk.Button(actions,text="삭제",command=delete).pack(side="left",padx=4);refresh()


if __name__ == "__main__":
    root=tk.Tk(); MESApp(root); root.mainloop()
