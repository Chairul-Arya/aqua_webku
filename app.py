from flask import Flask, render_template, request, redirect, url_for, session, flash
import pymysql
import matplotlib.pyplot as plt
import seaborn as sns
import io
import base64

app = Flask(__name__)
app.secret_key = 'secret_key'

# Konfigurasi koneksi ke database
db_connection = pymysql.connect(
    host="localhost",
    user="root",          
    password="",          
    database="aqua_web"   
)
db_cursor = db_connection.cursor()

# Login Route
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        try:
            # Query 
            query = "SELECT * FROM users WHERE email = %s AND password = %s"
            db_cursor.execute(query, (email, password))
            user = db_cursor.fetchone()

            if user:
                session['user_id'] = user[0]
                session['username'] = user[1]
                flash("Login berhasil!", "success")
                return redirect(url_for("index"))
            else:
                flash("Email atau password salah.", "danger")
        except pymysql.MySQLError as e:
            flash(f"Database error: {str(e)}", "danger")

    return render_template("login.html")

#Register buat akun
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")

        try:
            # Periksa apakah email sudah terdaftar
            query = "SELECT * FROM users WHERE email = %s"
            db_cursor.execute(query, (email,))
            existing_user = db_cursor.fetchone()

            if existing_user:
                flash("Email sudah terdaftar. Silakan gunakan email lain.", "danger")
            else:
                # Tambahkan pengguna baru ke database
                query = "INSERT INTO users (name, email, password) VALUES (%s, %s, %s)"
                db_cursor.execute(query, (name, email, password))
                db_connection.commit()
                flash("Akun berhasil dibuat. Silakan login.", "success")
                return redirect(url_for("login"))
        except pymysql.MySQLError as e:
            flash(f"Database error: {str(e)}", "danger")

    return render_template("register.html")

#halaman utama 
@app.route("/index")
def index():
    if 'user_id' not in session:
        flash("Silakan login terlebih dahulu.", "warning")
        return redirect(url_for("login"))

    return render_template("index.html", username=session['username'])

#logout
@app.route("/logout")
def logout():
    # Hapus data sesi
    session.clear()
    flash("Anda telah berhasil logout.", "success")
    return redirect(url_for("login"))

# Standar kualitas air menurut WHO
standards = {
    'ph': (6.5, 8.5),        # WHO: pH ideal 6.5 - 8.5
    'Amonia': 5,          # WHO: Turbidity ideal < 5 
    'Biological Oxygen Demand': (15, 25), # WHO: Temperature ideal 15°C - 25
    'Total Dissolved Solids': (300, 1000)        # WHO: EC ideal 300 - 1000 
}

#rute Home
@app.route("/Home")
def home():
    return render_template("index.html")  # Halaman utama

#rute water testing
@app.route("/water-testing", methods=["GET", "POST"])
def water_testing():
    wilayah = None
    kecamatan = None
    sungai = None
    hasil = {}
    img_base64 = None  # Variabel untuk menyimpan grafik
    perbandingan = {}
    sesuai = 0
    tidak_sesuai = 0
    show_results = False  # Variabel untuk menentukan apakah hasil ditampilkan
    
    if request.method == "POST":
        wilayah = request.form.get("wilayah")
        kecamatan = request.form.get("kecamatan")
        sungai = request.form.get("sungai")

        # Periksa jika ada kolom yang belum diisi
        if not wilayah or not kecamatan or not sungai:
            flash("Harap isi semua kolom sebelum melakukan pengujian.", "warning")
        else:
            # Query untuk mengambil data kualitas air berdasarkan wilayah, kecamatan, atau sungai
            query = """
                SELECT ph, Amonia, `BOD(Biological_Oxygen_Demand)`, `TDS(Total_Dissolved_Solids)`
                FROM water_tests
                WHERE wilayah = %s AND kecamatan = %s AND sungai = %s
            """
            db_cursor.execute(query, (wilayah, kecamatan, sungai))
            result = db_cursor.fetchone()
        
            if result:
                # Memasukkan hasil dari database ke dictionary hasil
                hasil = {
                    'ph': result[0],
                    'Amonia': result[1],
                    'Biological Oxygen Demand': result[2],
                    'Total Dissolved Solids': result[3]
                }

                # Membandingkan hasil pengujian dengan standar WHO
                for parameter, value in hasil.items():
                    if parameter in ['ph', 'Biological Oxygen Demand']:
                        if standards[parameter][0] <= value <= standards[parameter][1]:
                            perbandingan[parameter] = 'Sesuai standar WHO'
                            sesuai += 1
                        else:
                            perbandingan[parameter] = 'Tidak sesuai standar WHO'
                            tidak_sesuai += 1
                    elif parameter == 'Amonia':
                        if value < standards['Amonia']:
                            perbandingan[parameter] = 'Sesuai standar WHO'
                            sesuai += 1
                        else:
                            perbandingan[parameter] = 'Tidak sesuai standar WHO'
                            tidak_sesuai += 1
                    elif parameter == 'Total Dissolved Solids':
                        if standards[parameter][0] <= value <= standards[parameter][1]:
                            perbandingan[parameter] = 'Sesuai standar WHO'
                            sesuai += 1
                        else:
                            perbandingan[parameter] = 'Tidak sesuai standar WHO'
                            tidak_sesuai += 1

                # Membuat grafik perbandingan
                sns.set_style("whitegrid")
                sns.set_palette("coolwarm")

                # Data untuk grafik
                parameters = list(hasil.keys())
                test_results = list(hasil.values())
                who_standards = [sum(standards[param]) / 2 if isinstance(standards[param], tuple) else standards[param] for param in parameters]

                x = range(len(parameters))
                bar_width = 0.35

                fig, ax = plt.subplots(figsize=(10, 6))
                bars_test = ax.bar([i - bar_width / 2 for i in x], test_results, bar_width, label="Hasil Pengujian", color="blue")
                bars_who = ax.bar([i + bar_width / 2 for i in x], who_standards, bar_width, label="Standar WHO", color="green")

                ax.set_xticks(x)
                ax.set_xticklabels(parameters)
                ax.set_title("Perbandingan Hasil Pengujian vs Standar WHO", fontsize=16, fontweight="bold")
                ax.set_xlabel("Parameter", fontsize=14)
                ax.set_ylabel("Nilai", fontsize=14)
                ax.legend()

                # Simpan grafik sebagai base64
                img = io.BytesIO()
                plt.tight_layout()
                fig.savefig(img, format="png", dpi=100)
                img.seek(0)
                img_base64 = base64.b64encode(img.getvalue()).decode()
                plt.close(fig)

                # Tampilkan hasil
                show_results = True
            else:
                flash("Data tidak ditemukan untuk wilayah, kecamatan, atau sungai yang dipilih.", "warning")
                show_results = False

    return render_template("water_testing.html", wilayah=wilayah, kecamatan=kecamatan, sungai=sungai, hasil=hasil, perbandingan=perbandingan, img_base64=img_base64, sesuai=sesuai, tidak_sesuai=tidak_sesuai, show_results=show_results)

#rute input test
@app.route("/input-test", methods=["GET", "POST"])
def input_test():
    if request.method == "POST":
        # Mendapatkan data dari form
        wilayah = request.form.get("wilayah")
        kecamatan = request.form.get("kecamatan")
        sungai = request.form.get("sungai")
        ph = request.form.get("ph")
        Amonia = request.form.get("Amonia")
        Biological_Oxygen_Demand = request.form.get("Biological Oxygen Demand")
        Total_Dissolved_Solids = request.form.get("Total Dissolved Solids")

        # Validasi: Periksa apakah semua kolom diisi
        if not all([wilayah, kecamatan, sungai, ph, Amonia, Biological_Oxygen_Demand, Total_Dissolved_Solids]):
            flash("Harap isi semua kolom sebelum menyimpan data.", "warning")
        else:
            try:
                # Konversi nilai numerik untuk parameter air
                ph = float(ph)
                Amonia = float(Amonia)
                Biological_Oxygen_Demand = float(Biological_Oxygen_Demand)
                Total_Dissolved_Solids = float(Total_Dissolved_Solids)

                # Query menyimpan data ke database
                query = """
                    INSERT INTO water_tests (user_id, wilayah, kecamatan, sungai, ph, Amonia, `BOD(Biological_Oxygen_Demand)`, `TDS(Total_Dissolved_Solids)`)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
                values = (session['user_id'], wilayah, kecamatan, sungai, ph, Amonia, Biological_Oxygen_Demand, Total_Dissolved_Solids)

                # Menjalankan query untuk memasukkan data
                db_cursor.execute(query, values)
                db_connection.commit()  # Pastikan untuk commit agar perubahan disimpan
                flash("Data berhasil disimpan!", "success")
                
                # Redirect ke halaman 'thank_you'
                return redirect(url_for('thank_you'))
                
            except ValueError:
                flash("Harap masukkan nilai numerik yang valid untuk parameter kualitas air.", "danger")
            except pymysql.MySQLError as e:
                flash(f"Database error: {str(e)}", "danger")

    return render_template("input_test.html")

#rute thanks
@app.route("/thank-you")
def thank_you():
    return render_template("thank_you.html")

    
if __name__ == "__main__":
    app.run(debug=True)
