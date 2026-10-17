import os
import hmac
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, session, url_for
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
INSTANCE_DIR = BASE_DIR / "instance"
DEFAULT_DATABASE = INSTANCE_DIR / "mes.db"
NAV_ITEMS = [
    ("dashboard", "대시보드", "bi-speedometer2"),
    ("plans", "생산계획", "bi-calendar3"),
    ("orders", "작업지시", "bi-clipboard-check"),
    ("production", "생산실적", "bi-graph-up-arrow"),
    ("defects", "불량관리", "bi-exclamation-triangle"),
    ("equipment", "설비현황", "bi-cpu"),
    ("products", "기준정보", "bi-box-seam"),
]
KST = timezone(timedelta(hours=9))


def today_kst():
    return datetime.now(KST).date()


def connect_db(path):
    db = sqlite3.connect(path, factory=ClosingConnection)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    return db


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def init_db(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with connect_db(path) as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS products(product_code TEXT PRIMARY KEY, product_name TEXT NOT NULL, unit TEXT NOT NULL DEFAULT '개', active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS production_records(id INTEGER PRIMARY KEY AUTOINCREMENT, work_date TEXT NOT NULL, product_code TEXT NOT NULL, product_name TEXT NOT NULL, plan_qty INTEGER NOT NULL CHECK(plan_qty>=0), produced_qty INTEGER NOT NULL CHECK(produced_qty>=0), defect_qty INTEGER NOT NULL CHECK(defect_qty>=0), created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE INDEX IF NOT EXISTS idx_production_date ON production_records(work_date);
        CREATE TABLE IF NOT EXISTS equipment(equipment_code TEXT PRIMARY KEY, equipment_name TEXT NOT NULL, status TEXT NOT NULL DEFAULT '정지' CHECK(status IN ('가동','정지','점검','이상')));
        CREATE TABLE IF NOT EXISTS production_plans(id INTEGER PRIMARY KEY AUTOINCREMENT, plan_date TEXT NOT NULL, product_code TEXT NOT NULL REFERENCES products(product_code), product_name TEXT NOT NULL, plan_qty INTEGER NOT NULL CHECK(plan_qty>=0), due_date TEXT NOT NULL, status TEXT NOT NULL DEFAULT '계획' CHECK(status IN ('계획','확정','완료')), created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS work_orders(id INTEGER PRIMARY KEY AUTOINCREMENT, order_no TEXT NOT NULL UNIQUE, plan_id INTEGER REFERENCES production_plans(id) ON DELETE SET NULL, work_date TEXT NOT NULL, product_code TEXT NOT NULL REFERENCES products(product_code), product_name TEXT NOT NULL, order_qty INTEGER NOT NULL CHECK(order_qty>=0), equipment_code TEXT NOT NULL REFERENCES equipment(equipment_code), status TEXT NOT NULL DEFAULT '대기' CHECK(status IN ('대기','작업중','완료')), created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS production_entries(id INTEGER PRIMARY KEY AUTOINCREMENT, work_order_id INTEGER NOT NULL REFERENCES work_orders(id) ON DELETE CASCADE, work_date TEXT NOT NULL, produced_qty INTEGER NOT NULL CHECK(produced_qty>=0), defect_qty INTEGER NOT NULL CHECK(defect_qty>=0 AND defect_qty<=produced_qty), created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS defects(id INTEGER PRIMARY KEY AUTOINCREMENT, production_id INTEGER REFERENCES production_entries(id) ON DELETE SET NULL, work_order_id INTEGER NOT NULL REFERENCES work_orders(id) ON DELETE CASCADE, work_date TEXT NOT NULL, product_code TEXT NOT NULL REFERENCES products(product_code), product_name TEXT NOT NULL, defect_type TEXT NOT NULL, defect_qty INTEGER NOT NULL CHECK(defect_qty>=0), cause TEXT NOT NULL DEFAULT '', action TEXT NOT NULL DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE INDEX IF NOT EXISTS idx_plans_date ON production_plans(plan_date);
        CREATE INDEX IF NOT EXISTS idx_orders_date ON work_orders(work_date);
        CREATE INDEX IF NOT EXISTS idx_entries_date ON production_entries(work_date);
        """)
        if not db.execute("SELECT 1 FROM products LIMIT 1").fetchone():
            db.executemany("INSERT INTO products(product_code,product_name) VALUES (?,?)", [("P001", "기어 A"), ("P002", "기어 B"), ("P003", "스프링 A")])
        equipment = [("CNC-01", "CNC-01", "가동"), ("CNC-02", "CNC-02", "정지"), ("PRESS-01", "PRESS-01", "점검"), ("ASSY-01", "ASSY-01", "가동")]
        db.executemany("INSERT OR IGNORE INTO equipment(equipment_code,equipment_name,status) VALUES (?,?,?)", equipment)
        # Legacy desktop rows remain available; do not add demo records if the DB already contains data.
        if not db.execute("SELECT 1 FROM production_records LIMIT 1").fetchone():
            source = BASE_DIR / "mes.db"
            if Path(path).resolve() != source.resolve() and source.exists():
                try:
                    old = connect_db(source)
                    legacy = old.execute("SELECT work_date,product_code,product_name,plan_qty,produced_qty,defect_qty FROM production_records").fetchall()
                    db.executemany("INSERT INTO production_records(work_date,product_code,product_name,plan_qty,produced_qty,defect_qty) VALUES (?,?,?,?,?,?)", [tuple(r) for r in legacy])
                    old.close()
                except sqlite3.Error:
                    pass


def create_app(test_config=None):
    app = Flask(__name__, instance_path=str(INSTANCE_DIR))
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY") or os.urandom(32),
        DATABASE=os.environ.get("MES_DATABASE", str(DEFAULT_DATABASE)),
        MES_USERNAME=os.environ.get("MES_USERNAME", ""),
        MES_PASSWORD=os.environ.get("MES_PASSWORD", ""),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("MES_SECURE_COOKIE", "") == "1",
    )
    if test_config:
        app.config.update(test_config)
    db_path = Path(app.config["DATABASE"])
    if not db_path.is_absolute():
        db_path = BASE_DIR / db_path
        app.config["DATABASE"] = str(db_path)
    # Local installs get a one-time copy of the desktop DB. Hosted deployments use an explicit persistent path.
    local_default = db_path.resolve() == DEFAULT_DATABASE.resolve()
    should_copy_local_data = local_default or "MES_DATABASE" not in os.environ
    if not db_path.exists() and not app.config.get("TESTING") and should_copy_local_data and (BASE_DIR / "mes.db").exists() and db_path.resolve() != (BASE_DIR / "mes.db").resolve():
        db_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(BASE_DIR / "mes.db", db_path)
    init_db(db_path)

    @app.before_request
    def require_login():
        # Local demo remains frictionless unless credentials are explicitly configured.
        if app.config["MES_USERNAME"] and app.config["MES_PASSWORD"] and request.endpoint not in ("login", "static") and session.get("mes_user") != app.config["MES_USERNAME"]:
            return redirect(url_for("login"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if not app.config["MES_USERNAME"] or not app.config["MES_PASSWORD"]:
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            user = request.form.get("username", "")
            password = request.form.get("password", "")
            if hmac.compare_digest(user, app.config["MES_USERNAME"]) and hmac.compare_digest(password, app.config["MES_PASSWORD"]):
                session.clear()
                session["mes_user"] = user
                return redirect(url_for("dashboard"))
            flash("사용자 이름 또는 비밀번호가 올바르지 않습니다.", "danger")
        return render_template("login.html")

    @app.get("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.context_processor
    def common_context():
        return {"nav_items": NAV_ITEMS, "today": today_kst().isoformat()}

    def db_query(sql, params=()):
        with connect_db(app.config["DATABASE"]) as db:
            return db.execute(sql, params).fetchall()

    def all_plans():
        return db_query("SELECT id,plan_date,product_code,product_name,plan_qty,due_date,status FROM production_plans ORDER BY plan_date DESC,id DESC")

    def all_orders():
        return db_query("SELECT w.id,w.order_no,w.plan_id,w.work_date,w.product_code,w.product_name,w.order_qty,w.equipment_code,w.status FROM work_orders w ORDER BY w.work_date DESC,w.id DESC")

    def all_entries():
        return db_query("SELECT e.id,e.work_order_id,w.order_no,e.work_date,w.product_code,w.product_name,w.order_qty,e.produced_qty,e.defect_qty,e.produced_qty-e.defect_qty AS good_qty,CASE WHEN w.order_qty>0 THEN ROUND(e.produced_qty*100.0/w.order_qty,1) ELSE 0 END AS attainment FROM production_entries e JOIN work_orders w ON w.id=e.work_order_id ORDER BY e.work_date DESC,e.id DESC")

    @app.get("/")
    def dashboard():
        day = today_kst().isoformat()
        with connect_db(app.config["DATABASE"]) as db:
            plan_qty = db.execute("SELECT COALESCE(SUM(plan_qty),0) FROM production_plans WHERE plan_date=?", (day,)).fetchone()[0]
            order_qty = db.execute("SELECT COALESCE(SUM(order_qty),0) FROM work_orders WHERE work_date=?", (day,)).fetchone()[0]
            produced, defects = db.execute("SELECT COALESCE(SUM(produced_qty),0),COALESCE(SUM(defect_qty),0) FROM production_entries WHERE work_date=?", (day,)).fetchone()
            if not plan_qty:
                plan_qty = db.execute("SELECT COALESCE(SUM(plan_qty),0) FROM production_records WHERE work_date=?", (day,)).fetchone()[0]
            if not produced and not defects:
                produced, defects = db.execute("SELECT COALESCE(SUM(produced_qty),0),COALESCE(SUM(defect_qty),0) FROM production_records WHERE work_date=?", (day,)).fetchone()
            running = db.execute("SELECT COUNT(*) FROM equipment WHERE status='가동'").fetchone()[0]
            recent = db.execute("SELECT order_no,work_date,product_name,order_qty,equipment_code,status FROM work_orders ORDER BY id DESC LIMIT 10").fetchall()
        kpis = [
            ("금일 계획수량", plan_qty, "개", "primary"), ("금일 지시수량", order_qty, "개", "purple"),
            ("금일 생산수량", produced, "개", "green"), ("금일 양품수량", produced-defects, "개", "teal"),
            ("금일 불량수량", defects, "개", "red"), ("생산달성률", f"{produced/order_qty*100:.1f}" if order_qty else "0.0", "%", "purple"),
            ("불량률", f"{defects/produced*100:.2f}" if produced else "0.00", "%", "orange"), ("가동 설비수", running, "대", "green"),
        ]
        return render_template("dashboard.html", kpis=kpis, recent=recent)

    def render_crud(title, endpoint, fields, headers, rows, editing=None, empty_text="등록된 데이터가 없습니다."):
        return render_template("crud.html", title=title, endpoint=endpoint, fields=fields, headers=headers, rows=rows, editing=editing, empty_text=empty_text)

    @app.route("/plans", methods=["GET", "POST"])
    def plans():
        fields = [("plan_date", "계획일자", "date"), ("product_code", "제품", "product"), ("plan_qty", "계획수량", "number"), ("due_date", "납기일", "date"), ("status", "상태", ["계획", "확정", "완료"])]
        return plan_crud(fields, render_crud, all_plans)

    def plan_crud(fields, renderer, loader):
        return basic_crud("생산계획", "plans", fields, ["ID", "계획일자", "제품코드", "제품명", "계획수량", "납기일", "상태"], loader, renderer, "production_plans")

    @app.route("/orders", methods=["GET", "POST"])
    def orders():
        fields = [("plan_id", "생산계획", "plan"), ("work_date", "작업일자", "date"), ("order_qty", "지시수량", "number"), ("equipment_code", "설비", "equipment"), ("status", "작업상태", ["대기", "작업중", "완료"])]
        return basic_crud("작업지시", "orders", fields, ["ID", "작업지시번호", "계획ID", "작업일자", "제품코드", "제품명", "지시수량", "설비", "작업상태"], all_orders, render_crud, "work_orders")

    @app.route("/production", methods=["GET", "POST"])
    def production():
        fields = [("work_order_id", "작업지시", "order"), ("work_date", "작업일자", "date"), ("produced_qty", "생산수량", "number"), ("defect_qty", "불량수량", "number")]
        rows = all_entries()
        return basic_crud("생산실적", "production", fields, ["ID", "작업지시ID", "작업지시번호", "작업일자", "제품코드", "제품명", "지시수량", "생산수량", "불량수량", "양품수량", "달성률 %"], all_entries, render_crud, "production_entries", rows_override=rows)

    @app.route("/defects", methods=["GET", "POST"])
    def defects():
        fields = [("production_id", "연결 생산실적", "entry"), ("defect_type", "불량유형", ["치수불량", "외관불량", "가공불량", "조립불량", "기타"]), ("defect_qty", "불량수량", "number"), ("cause", "불량원인", "text"), ("action", "조치내용", "text")]
        return basic_crud("불량관리", "defects", fields, ["ID", "작업일자", "작업지시번호", "제품코드", "제품명", "불량유형", "불량수량", "불량원인", "조치내용"], lambda: db_query("SELECT d.id,d.work_date,w.order_no,d.product_code,d.product_name,d.defect_type,d.defect_qty,d.cause,d.action FROM defects d LEFT JOIN work_orders w ON w.id=d.work_order_id ORDER BY d.work_date DESC,d.id DESC"), render_crud, "defects")

    @app.route("/equipment", methods=["GET", "POST"])
    def equipment():
        if request.method == "POST":
            code, status = request.form.get("equipment_code", ""), request.form.get("status", "")
            if status not in ("가동", "정지", "점검", "이상"):
                flash("설비 상태 값이 올바르지 않습니다.", "danger")
            else:
                with connect_db(app.config["DATABASE"]) as db:
                    db.execute("UPDATE equipment SET status=? WHERE equipment_code=?", (status, code))
                flash("설비 상태를 변경했습니다.", "success")
            return redirect(url_for("equipment"))
        return render_template("equipment.html", equipment=db_query("SELECT equipment_code,equipment_name,status FROM equipment ORDER BY equipment_code"))

    @app.route("/products", methods=["GET", "POST"])
    def products():
        fields = [("product_code", "제품코드", "text"), ("product_name", "제품명", "text"), ("unit", "단위", "text")]
        return basic_crud("기준정보", "products", fields, ["제품코드", "제품명", "단위", "사용상태"], lambda: db_query("SELECT product_code,product_name,unit,active FROM products ORDER BY product_code"), render_crud, "products", identity="product_code")

    def field_options(kind):
        if kind == "product":
            return [(r[0], f"{r[0]} · {r[1]}") for r in db_query("SELECT product_code,product_name FROM products WHERE active=1 ORDER BY product_code")]
        if kind == "plan":
            return [(r[0], f"{r[1]} · {r[2]} {r[3]} · 계획 {r[4]}") for r in db_query("SELECT id,plan_date,product_code,product_name,plan_qty FROM production_plans ORDER BY plan_date DESC,id DESC")]
        if kind == "equipment":
            return [(r[0], r[0]) for r in db_query("SELECT equipment_code FROM equipment ORDER BY equipment_code")]
        if kind == "order":
            return [(r[0], f"{r[1]} · {r[2]} · 지시 {r[3]}") for r in db_query("SELECT id,order_no,product_name,order_qty FROM work_orders ORDER BY work_date DESC,id DESC")]
        if kind == "entry":
            return [(r[0], f"{r[1]} · {r[2]} · {r[3]} 생산 {r[4]}, 불량 {r[5]}") for r in db_query("SELECT e.id,w.order_no,w.product_code,w.product_name,e.produced_qty,e.defect_qty FROM production_entries e JOIN work_orders w ON w.id=e.work_order_id ORDER BY e.id DESC")]
        return []

    def basic_crud(title, endpoint, fields, headers, loader, renderer, table, identity="id", rows_override=None):
        edit_id = request.args.get("edit")
        editing = None
        if edit_id:
            editing_row = db_query(f"SELECT * FROM {table} WHERE {identity}=?", (edit_id,))
            editing = dict(editing_row[0]) if editing_row else None
        if request.method == "POST":
            action = request.form.get("action", "save")
            row_id = request.form.get("id", "")
            if action == "delete":
                try:
                    with connect_db(app.config["DATABASE"]) as db:
                        db.execute(f"DELETE FROM {table} WHERE {identity}=?", (row_id,))
                    flash("선택한 항목을 삭제했습니다.", "success")
                except sqlite3.IntegrityError as exc:
                    flash(f"연결된 데이터가 있어 삭제할 수 없습니다: {exc}", "danger")
                return redirect(url_for(endpoint))
            try:
                values = {key: request.form.get(key, "").strip() for key, _, _ in fields}
                row_id = request.form.get("id", "").strip()
                if table == "production_plans":
                    product = db_query("SELECT product_name FROM products WHERE product_code=? AND active=1", (values["product_code"],))
                    if not product: raise ValueError("제품 기준정보에서 제품을 선택하세요.")
                    values["product_name"] = product[0][0]
                    validate_date(values["plan_date"]); validate_date(values["due_date"]); values["plan_qty"] = valid_qty(values["plan_qty"], "계획수량")
                    with connect_db(app.config["DATABASE"]) as db:
                        args=(values["plan_date"],values["product_code"],values["product_name"],values["plan_qty"],values["due_date"],values["status"])
                        if row_id: db.execute("UPDATE production_plans SET plan_date=?,product_code=?,product_name=?,plan_qty=?,due_date=?,status=? WHERE id=?",args+(row_id,))
                        else: db.execute("INSERT INTO production_plans(plan_date,product_code,product_name,plan_qty,due_date,status) VALUES (?,?,?,?,?,?)",args)
                    flash("생산계획을 저장했습니다.", "success")
                    return redirect(url_for(endpoint))
                elif table == "work_orders":
                    plan = db_query("SELECT * FROM production_plans WHERE id=?", (values["plan_id"],))
                    if not plan: raise ValueError("생산계획을 선택하세요.")
                    values.update({"plan": plan[0], "product_code": plan[0]["product_code"], "product_name": plan[0]["product_name"]})
                    values["order_qty"] = valid_qty(values["order_qty"], "지시수량")
                    validate_date(values["work_date"])
                    with connect_db(app.config["DATABASE"]) as db:
                        if row_id:
                            db.execute("UPDATE work_orders SET plan_id=?,work_date=?,product_code=?,product_name=?,order_qty=?,equipment_code=?,status=? WHERE id=?", (values["plan_id"], values["work_date"], values["product_code"], values["product_name"], values["order_qty"], values["equipment_code"], values["status"], row_id))
                        else:
                            day = values["work_date"].replace("-", "")
                            prefix = f"WO-{day}-"
                            last = db.execute("SELECT MAX(CAST(substr(order_no,?) AS INTEGER)) FROM work_orders WHERE order_no LIKE ?", (len(prefix)+1, prefix+"%")).fetchone()[0] or 0
                            number = f"{prefix}{last+1:03d}"
                            db.execute("INSERT INTO work_orders(order_no,plan_id,work_date,product_code,product_name,order_qty,equipment_code,status) VALUES (?,?,?,?,?,?,?,?)", (number, values["plan_id"], values["work_date"], values["product_code"], values["product_name"], values["order_qty"], values["equipment_code"], values["status"]))
                    flash("작업지시를 저장했습니다.", "success")
                    return redirect(url_for(endpoint))
                elif table == "production_entries":
                    order = db_query("SELECT * FROM work_orders WHERE id=?", (values["work_order_id"],))
                    if not order: raise ValueError("작업지시를 선택하세요.")
                    validate_date(values["work_date"]); produced=valid_qty(values["produced_qty"],"생산수량"); defect=valid_qty(values["defect_qty"],"불량수량")
                    if defect > produced: raise ValueError("불량수량은 생산수량을 초과할 수 없습니다.")
                    with connect_db(app.config["DATABASE"]) as db:
                        if row_id: db.execute("UPDATE production_entries SET work_order_id=?,work_date=?,produced_qty=?,defect_qty=? WHERE id=?", (values["work_order_id"], values["work_date"], produced, defect, row_id))
                        else: db.execute("INSERT INTO production_entries(work_order_id,work_date,produced_qty,defect_qty) VALUES (?,?,?,?)", (values["work_order_id"], values["work_date"], produced, defect))
                        total=db.execute("SELECT SUM(produced_qty) FROM production_entries WHERE work_order_id=?",(values["work_order_id"],)).fetchone()[0] or 0
                        status="완료" if total>=order[0]["order_qty"] else "작업중"
                        db.execute("UPDATE work_orders SET status=? WHERE id=?",(status,values["work_order_id"]))
                    flash("생산실적을 저장했습니다.", "success"); return redirect(url_for(endpoint))
                elif table == "defects":
                    entry = db_query("SELECT e.id,e.work_order_id,e.work_date,e.defect_qty,w.product_code,w.product_name FROM production_entries e JOIN work_orders w ON w.id=e.work_order_id WHERE e.id=?",(values["production_id"],))
                    if not entry: raise ValueError("연결할 생산실적을 선택하세요.")
                    values["defect_qty"]=valid_qty(values["defect_qty"],"불량수량")
                    with connect_db(app.config["DATABASE"]) as db:
                        args=(values["production_id"],entry[0]["work_order_id"],entry[0]["work_date"],entry[0]["product_code"],entry[0]["product_name"],values["defect_type"],values["defect_qty"],values["cause"],values["action"])
                        if row_id: db.execute("UPDATE defects SET production_id=?,work_order_id=?,work_date=?,product_code=?,product_name=?,defect_type=?,defect_qty=?,cause=?,action=? WHERE id=?",args+(row_id,))
                        else: db.execute("INSERT INTO defects(production_id,work_order_id,work_date,product_code,product_name,defect_type,defect_qty,cause,action) VALUES (?,?,?,?,?,?,?,?,?)",args)
                    flash("불량 정보를 저장했습니다.", "success"); return redirect(url_for(endpoint))
                elif table == "products":
                    if not values["product_code"] or not values["product_name"]: raise ValueError("제품코드와 제품명을 입력하세요.")
                    if row_id:
                        with connect_db(app.config["DATABASE"]) as db: db.execute("UPDATE products SET product_name=?,unit=? WHERE product_code=?",(values["product_name"],values["unit"] or "개",row_id))
                    else:
                        with connect_db(app.config["DATABASE"]) as db: db.execute("INSERT INTO products(product_code,product_name,unit) VALUES (?,?,?)",(values["product_code"],values["product_name"],values["unit"] or "개"))
                    flash("제품 기준정보를 저장했습니다.", "success"); return redirect(url_for(endpoint))
                else:
                    db_fields = [f[0] for f in fields]
                    if row_id:
                        assignments=",".join(f"{key}=?" for key in db_fields)
                        with connect_db(app.config["DATABASE"]) as db: db.execute(f"UPDATE {table} SET {assignments} WHERE {identity}=?",tuple(values[k] for k in db_fields)+(row_id,))
                    else:
                        cols=",".join(db_fields); marks=",".join("?" for _ in db_fields)
                        with connect_db(app.config["DATABASE"]) as db: db.execute(f"INSERT INTO {table}({cols}) VALUES ({marks})",tuple(values[k] for k in db_fields))
                flash(f"{title} 정보를 저장했습니다.", "success")
                return redirect(url_for(endpoint))
            except (ValueError, sqlite3.IntegrityError) as exc:
                flash(str(exc), "danger")
                editing = request.form.to_dict()
        options = {key: field_options(kind) for key, _, kind in fields if isinstance(kind, str) and kind in ("product", "plan", "equipment", "order", "entry")}
        normalized_fields = [(key, label, kind, options.get(key, [(choice, choice) for choice in kind] if isinstance(kind, list) else [])) for key, label, kind in fields]
        values = rows_override if rows_override is not None else loader()
        normalized_rows = [dict(row) for row in values]
        for row in normalized_rows:
            if table == "products": row["active"] = "사용" if row.get("active") else "중지"
        return renderer(title, endpoint, normalized_fields, headers, normalized_rows, editing)

    def validate_date(value):
        try: datetime.strptime(value, "%Y-%m-%d")
        except (ValueError, TypeError): raise ValueError("날짜는 YYYY-MM-DD 형식으로 입력하세요.")

    def valid_qty(value, label):
        try: quantity=int(value)
        except (ValueError, TypeError): raise ValueError(f"{label}은 0 이상의 정수로 입력하세요.")
        if quantity < 0: raise ValueError(f"{label}은 0 이상의 정수로 입력하세요.")
        return quantity

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=os.environ.get("FLASK_DEBUG") == "1")
