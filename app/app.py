import os
from datetime import datetime, timezone

from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_sqlalchemy import SQLAlchemy

basedir = os.path.abspath(os.path.dirname(__file__))
os.makedirs(os.path.join(basedir, "instance"), exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "dev-key-change-in-production",
)
app.config["SQLALCHEMY_DATABASE_URI"] = (
    "sqlite:///" + os.path.join(basedir, "instance", "factory.db")
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

STATUS_CHOICES = ["running", "idle", "maintenance", "stopped"]
STATION_CHOICES = [
    "Stamping",
    "Body Shop",
    "Paint",
    "Assembly",
    "Powertrain",
    "Final Inspection",
]


class Part(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(32), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(80), default="General")
    supplier = db.Column(db.String(120), default="")
    quantity = db.Column(db.Integer, default=0, nullable=False)
    reorder_level = db.Column(db.Integer, default=10, nullable=False)
    unit_cost = db.Column(db.Float, default=0.0)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
    )

    @property
    def is_low(self):
        return self.quantity <= self.reorder_level

    @property
    def stock_value(self):
        return round(self.quantity * self.unit_cost, 2)


class ProductionLine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    station = db.Column(db.String(80), default="Assembly")
    status = db.Column(db.String(20), default="idle", nullable=False)
    target_output = db.Column(db.Integer, default=0)
    current_output = db.Column(db.Integer, default=0)
    shift = db.Column(db.String(40), default="Day Shift")
    note = db.Column(db.String(200), default="")
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
    )

    @property
    def completion_pct(self):
        if not self.target_output:
            return 0
        return min(100, round(100 * self.current_output / self.target_output))


@app.route("/")
def dashboard():
    lines = ProductionLine.query.order_by(
        ProductionLine.station,
        ProductionLine.name,
    ).all()
    low_parts = Part.query.filter(
        Part.quantity <= Part.reorder_level
    ).order_by(Part.quantity).all()
    total_parts = Part.query.count()
    running = sum(1 for line in lines if line.status == "running")
    stopped = sum(
        1 for line in lines if line.status in ("stopped", "maintenance")
    )
    inventory_value = sum(part.stock_value for part in Part.query.all())

    return render_template(
        "dashboard.html",
        lines=lines,
        low_parts=low_parts,
        total_parts=total_parts,
        running=running,
        stopped=stopped,
        inventory_value=inventory_value,
    )


@app.route("/parts")
def parts_list():
    query_text = request.args.get("q", "").strip()
    query = Part.query

    if query_text:
        like = f"%{query_text}%"
        query = query.filter(
            db.or_(
                Part.name.ilike(like),
                Part.sku.ilike(like),
                Part.category.ilike(like),
            )
        )

    parts = query.order_by(Part.name).all()
    return render_template("parts.html", parts=parts, q=query_text)


@app.route("/parts/new", methods=["GET", "POST"])
def part_new():
    if request.method == "POST":
        part = Part(
            sku=request.form["sku"].strip().upper(),
            name=request.form["name"].strip(),
            category=request.form.get("category", "General").strip()
            or "General",
            supplier=request.form.get("supplier", "").strip(),
            quantity=int(request.form.get("quantity") or 0),
            reorder_level=int(request.form.get("reorder_level") or 10),
            unit_cost=float(request.form.get("unit_cost") or 0),
        )
        db.session.add(part)

        try:
            db.session.commit()
            flash(f"Part {part.sku} added to inventory.", "success")
            return redirect(url_for("parts_list"))
        except Exception:
            db.session.rollback()
            flash(
                "Could not save part. Check that the SKU is unique.",
                "error",
            )

    return render_template("part_form.html", part=None)


@app.route("/parts/<int:part_id>/edit", methods=["GET", "POST"])
def part_edit(part_id):
    part = Part.query.get_or_404(part_id)

    if request.method == "POST":
        part.sku = request.form["sku"].strip().upper()
        part.name = request.form["name"].strip()
        part.category = request.form.get("category", "General").strip()
        part.category = part.category or "General"
        part.supplier = request.form.get("supplier", "").strip()
        part.quantity = int(request.form.get("quantity") or 0)
        part.reorder_level = int(request.form.get("reorder_level") or 10)
        part.unit_cost = float(request.form.get("unit_cost") or 0)
        part.updated_at = datetime.now(timezone.utc)

        db.session.commit()
        flash(f"Part {part.sku} updated.", "success")
        return redirect(url_for("parts_list"))

    return render_template("part_form.html", part=part)


@app.route("/parts/<int:part_id>/delete", methods=["POST"])
def part_delete(part_id):
    part = Part.query.get_or_404(part_id)
    db.session.delete(part)
    db.session.commit()
    flash(f"Part {part.sku} removed from inventory.", "success")
    return redirect(url_for("parts_list"))


@app.route("/parts/<int:part_id>/adjust", methods=["POST"])
def part_adjust(part_id):
    part = Part.query.get_or_404(part_id)
    delta = int(request.form.get("delta", 0))
    part.quantity = max(0, part.quantity + delta)
    part.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return redirect(url_for("parts_list", q=request.args.get("q", "")))


@app.route("/lines")
def lines_list():
    lines = ProductionLine.query.order_by(
        ProductionLine.station,
        ProductionLine.name,
    ).all()
    return render_template(
        "lines.html",
        lines=lines,
        station_choices=STATION_CHOICES,
    )


@app.route("/lines/new", methods=["GET", "POST"])
def line_new():
    if request.method == "POST":
        line = ProductionLine(
            name=request.form["name"].strip(),
            station=request.form.get("station", "Assembly"),
            status=request.form.get("status", "idle"),
            target_output=int(request.form.get("target_output") or 0),
            current_output=int(request.form.get("current_output") or 0),
            shift=request.form.get("shift", "Day Shift").strip()
            or "Day Shift",
            note=request.form.get("note", "").strip(),
        )
        db.session.add(line)
        db.session.commit()
        flash(f"Line '{line.name}' added.", "success")
        return redirect(url_for("lines_list"))

    return render_template(
        "line_form.html",
        line=None,
        station_choices=STATION_CHOICES,
        status_choices=STATUS_CHOICES,
    )


@app.route("/lines/<int:line_id>/edit", methods=["GET", "POST"])
def line_edit(line_id):
    line = ProductionLine.query.get_or_404(line_id)

    if request.method == "POST":
        line.name = request.form["name"].strip()
        line.station = request.form.get("station", "Assembly")
        line.status = request.form.get("status", "idle")
        line.target_output = int(request.form.get("target_output") or 0)
        line.current_output = int(request.form.get("current_output") or 0)
        line.shift = request.form.get("shift", "Day Shift").strip()
        line.shift = line.shift or "Day Shift"
        line.note = request.form.get("note", "").strip()
        line.updated_at = datetime.now(timezone.utc)

        db.session.commit()
        flash(f"Line '{line.name}' updated.", "success")
        return redirect(url_for("lines_list"))

    return render_template(
        "line_form.html",
        line=line,
        station_choices=STATION_CHOICES,
        status_choices=STATUS_CHOICES,
    )


@app.route("/lines/<int:line_id>/delete", methods=["POST"])
def line_delete(line_id):
    line = ProductionLine.query.get_or_404(line_id)
    db.session.delete(line)
    db.session.commit()
    flash(f"Line '{line.name}' removed.", "success")
    return redirect(url_for("lines_list"))


@app.route("/lines/<int:line_id>/status", methods=["POST"])
def line_status(line_id):
    line = ProductionLine.query.get_or_404(line_id)
    new_status = request.form.get("status")

    if new_status in STATUS_CHOICES:
        line.status = new_status
        line.updated_at = datetime.now(timezone.utc)
        db.session.commit()

    return redirect(request.referrer or url_for("dashboard"))


@app.route("/api/status")
def api_status():
    lines = ProductionLine.query.all()
    parts = Part.query.all()

    return jsonify(
        {
            "lines": [
                {
                    "id": line.id,
                    "name": line.name,
                    "station": line.station,
                    "status": line.status,
                    "current_output": line.current_output,
                    "target_output": line.target_output,
                    "completion_pct": line.completion_pct,
                }
                for line in lines
            ],
            "low_stock_parts": [
                {
                    "sku": part.sku,
                    "name": part.name,
                    "quantity": part.quantity,
                    "reorder_level": part.reorder_level,
                }
                for part in parts
                if part.is_low
            ],
        }
    )


def seed_demo_data():
    if ProductionLine.query.count() == 0:
        db.session.add_all(
            [
                ProductionLine(
                    name="Line A",
                    station="Stamping",
                    status="running",
                    target_output=800,
                    current_output=612,
                    shift="Day Shift",
                ),
                ProductionLine(
                    name="Line B",
                    station="Body Shop",
                    status="running",
                    target_output=600,
                    current_output=598,
                    shift="Day Shift",
                ),
                ProductionLine(
                    name="Line C",
                    station="Paint",
                    status="maintenance",
                    target_output=600,
                    current_output=140,
                    shift="Day Shift",
                    note="Booth 2 filter change",
                ),
                ProductionLine(
                    name="Line D",
                    station="Assembly",
                    status="running",
                    target_output=500,
                    current_output=310,
                    shift="Day Shift",
                ),
                ProductionLine(
                    name="Line E",
                    station="Powertrain",
                    status="stopped",
                    target_output=400,
                    current_output=0,
                    shift="Day Shift",
                    note="Awaiting torque wrench calibration",
                ),
                ProductionLine(
                    name="Line F",
                    station="Final Inspection",
                    status="idle",
                    target_output=500,
                    current_output=0,
                    shift="Night Shift",
                ),
            ]
        )

    if Part.query.count() == 0:
        db.session.add_all(
            [
                Part(
                    sku="ENG-4521",
                    name="Engine Block V6",
                    category="Powertrain",
                    supplier="Meridian Castings",
                    quantity=42,
                    reorder_level=20,
                    unit_cost=1250.00,
                ),
                Part(
                    sku="BRK-1190",
                    name="Brake Caliper Front",
                    category="Braking",
                    supplier="Halden Brakes",
                    quantity=8,
                    reorder_level=25,
                    unit_cost=64.50,
                ),
                Part(
                    sku="WIN-3002",
                    name="Windshield Laminated",
                    category="Glass",
                    supplier="Clarity Glassworks",
                    quantity=15,
                    reorder_level=15,
                    unit_cost=180.00,
                ),
                Part(
                    sku="SEA-0087",
                    name="Front Seat Assembly",
                    category="Interior",
                    supplier="Comfort Trim Co.",
                    quantity=120,
                    reorder_level=40,
                    unit_cost=310.00,
                ),
                Part(
                    sku="TIR-2244",
                    name="All-Season Tire 18in",
                    category="Wheels",
                    supplier="Rolling Rubber Ltd",
                    quantity=6,
                    reorder_level=50,
                    unit_cost=95.00,
                ),
                Part(
                    sku="BAT-7710",
                    name="EV Battery Module",
                    category="Powertrain",
                    supplier="VoltCell Energy",
                    quantity=30,
                    reorder_level=12,
                    unit_cost=2100.00,
                ),
                Part(
                    sku="DOR-1455",
                    name="Door Panel Left Front",
                    category="Body",
                    supplier="Meridian Castings",
                    quantity=55,
                    reorder_level=20,
                    unit_cost=88.00,
                ),
            ]
        )

    db.session.commit()


def create_app():
    return app


with app.app_context():
    db.create_all()
    seed_demo_data()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
