import os
import streamlit as st
import requests
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="مدارس التكنولوجيا التطبيقية",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# Configuration
# ==========================================
try:
    # Production (Streamlit Cloud)
    API_BASE_URL = st.secrets["API_BASE_URL"]
    SYSTEM_API_KEY = st.secrets["API_KEY"]
except Exception:
    # Local Development
    API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
    SYSTEM_API_KEY = os.getenv("API_KEY")

# تصميم واجهة المستخدم بالـ CSS لتحسين المظهر العربي والاتجاهات
st.markdown("""
    <style>
    /* تطبيق RTL على الحاوية الرئيسية فقط */
    .main .block-container {
        direction: rtl;
        text-align: right;
    }
    /* ضمان محاذاة العناوين والنصوص داخل المحتوى الأساسي */
    .main h1, .main h2, .main h3, .main h4, .main p, .main span, .main div {
        direction: rtl;
        text-align: right;
    }
    </style>
    """, unsafe_allowed_unsafe_html=True)

headers = {"X-API-Key": SYSTEM_API_KEY} if SYSTEM_API_KEY else {}

# ==========================================
# Navigation Sidebar
# ==========================================
st.sidebar.title("📌 لوحة التحكم")

# إدارة حالة تسجيل الدخول للمشرف
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False

with st.sidebar.expander("🔐 بوابة المسؤولين (Admin Mode)"):
    if not st.session_state.is_admin:
        admin_key = st.text_input("أدخل مفتاح المسؤول (API Key):", type="password")
        if st.button("تسجيل الدخول كمسؤول"):
            if admin_key == SYSTEM_API_KEY:
                st.session_state.is_admin = True
                st.success("تم تفعيل صلاحيات المسؤول بنجاح!")
                st.rerun()
            else:
                st.error("المفتاح غير صحيح!")
    else:
        st.write("🟢 أنت تعمل الآن بصلاحيات المسؤول.")
        if st.button("تسجيل الخروج من نظام المسؤول"):
            st.session_state.is_admin = False
            st.rerun()

is_admin = st.session_state.is_admin

# الخيارات المتاحة في القائمة الجانبية
menu_options = ["🏠 الرئيسية واستعراض المدارس", "💬 اسأل الذكاء الاصطناعي عن المدارس (RAG)"]
if is_admin:
    menu_options.extend([
        "➕ إضافة مدرسة يدوياً", 
        "🔍اضافة مدرسة باستخدام نص - بوست فيسبوك, اعلان, ...الخ",
        "📂 رفع دليل مدرسة جديد (RAG Ingest)"
    ])

menu = st.sidebar.radio("انتقل إلى:", menu_options)

# ==========================================
# 1. الشاشة الرئيسية واستعراض المدارس
# ==========================================
if menu == "🏠 الرئيسية واستعراض المدارس":
    st.title("🎓 نظام إدارة واستعلام مدارس التكنولوجيا التطبيقية")
    st.write("مرحباً بك في المنصة الذكية الرسمية لاستعراض ومتابعة تفاصيل مدارس التكنولوجيا التطبيقية بمصر.")

    st.subheader("📊 المدارس المسجلة حالياً")
    with st.spinner("جاري جلب البيانات من السيرفر..."):
        try:
            res = requests.get(f"{API_BASE_URL}/schools")
            if res.status_code == 200:
                schools = res.json()
                if not schools:
                    st.info("لا توجد مدارس مسجلة في النظام حالياً.")
                else:
                    for school in schools:
                        with st.expander(f"🏫 {school['arabic_name']} ({school['location']}) - الحد الأدنى: {school['minimum_score']} درجة"):
                            col1, col2 = st.columns(2)
                            with col1:
                                st.write(f"**الاسم الإنجليزي:** {school['english_name'] or 'غير مسجل'}")
                                st.write(f"**سنة التأسيس:** {school['established_year']}")
                                st.write(f"**التخصص الأساسي:** {school['specialization']}")
                                st.write(f"**الشريك الصناعي:** {school['industrial_partner'] or 'غير مسجل'}")
                            with col2:
                                st.write(f"**المحافظات المقبولة:** {school['accepted_governorates']}")
                                st.write(f"**سنوات الدراسة:** {school['study_duration']} سنوات")
                                st.write(f"**الموقع الإلكتروني:** {school['official_website'] or 'لا يوجد'}")
                            
                            st.write(f"**وصف عام:** {school['description'] or 'لا يوجد وصف حالي لهذه المدرسة.'}")
                            
                            if is_admin:
                                if st.button(f"🗑️ حذف {school['arabic_name']}", key=f"del_{school['id']}"):
                                    del_res = requests.delete(f"{API_BASE_URL}/schools/{school['id']}", headers=headers)
                                    if del_res.status_code == 204:
                                        st.success("تم حذف المدرسة بنجاح!")
                                        st.rerun()
                                    else:
                                        st.error("فشل حذف المدرسة.")
            else:
                st.error("فشل جلب قائمة المدارس من السيرفر.")
        except Exception as e:
            st.error(f"خطأ في الاتصال بالـ Backend: {e}")

# ==========================================
# 2. شاشة محادثة الذكاء الاصطناعي (RAG Query) - محدثة بالكامل ديناميكياً
# ==========================================
elif menu == "💬 اسأل الذكاء الاصطناعي عن المدارس (RAG)":
    st.header("💬 اسأل الذكاء الاصطناعي عن المدارس (RAG)")
    st.write("اختر مدرسة واسأل المساعد الذكي عن شروطها، اختباراتها أو تفاصيلها من واقع ملفاتها الرسمية المعتمدة.")

    with st.spinner("جاري تهيئة قاعدة المعرفة الذكية..."):
        try:
            schools_res = requests.get(f"{API_BASE_URL}/schools")
            if schools_res.status_code == 200 and schools_res.json():
                schools_list = schools_res.json()
                # بناء قاموس يربط بين الاسم العربي والـ id الفريد في قاعدة البيانات
                school_options = {s["arabic_name"]: s["id"] for s in schools_list}
                
                selected_school_name = st.selectbox("اختر المدرسة المستهدفة بالبحث والاستعلام:", list(school_options.keys()))
                selected_school_id = school_options[selected_school_name]

                user_question = st.text_input("أدخل سؤالك هنا (مثال: ما هي الأوراق المطلوبة وشروط الكشف الطبي؟):")
                
                if st.button("إرسال السؤال"):
                    if user_question.strip():
                        with st.spinner("جاري قراءة مستندات المدرسة بدقة وتوليد الإجابة الحتمية..."):
                            try:
                                payload = {
                                    "question": user_question,
                                    "school_id": selected_school_id,  # تمرير الـ id الحقيقي ديناميكياً
                                    "k": 6
                                }
                                response = requests.post(f"{API_BASE_URL}/rag/query", json=payload, headers=headers)
                                
                                if response.status_code == 200:
                                    data = response.json()
                                    st.subheader("🤖 الإجابة المعتمدة:")
                                    st.write(data["answer"])
                                    
                                    with st.expander("🔍 المصادر والمستندات المستند إليها في التوليد:"):
                                        for src in data["sources"]:
                                            st.write(f"- المستند: `{src['source']}` (قطعة رقم {src['chunk_index']}) - المسافة الدلالية: {src['distance']}")
                                else:
                                    st.error("عذراً، حدث خطأ في معالجة طلبك من السيرفر أو لم يتم رفع أدلة لهذه المدرسة بعد.")
                            except Exception as e:
                                st.error(f"فشل الاتصال بـ API: {e}")
                    else:
                        st.warning("يرجى كتابة سؤال أولاً قبل الضغط على إرسال.")
            else:
                st.warning("⚠️ لا توجد مدارس مسجلة بالنظام حالياً. يرجى تسجيل المدارس أولاً لتتمكن من استخدام نظام الـ RAG.")
        except Exception as e:
            st.error(f"خطأ أثناء الاتصال بالخادم: {e}")

# ==========================================
# 3. شاشة إضافة مدرسة يدوياً (Admin)
# ==========================================
elif menu == "➕ إضافة مدرسة يدوياً" and is_admin:
    st.header("➕ إضافة مدرسة جديدة يدوياً (صلاحيات الإدارة)")
    
    with st.form("add_school_form"):
        arabic_name = st.text_input("اسم المدرسة باللغة العربية (إجباري):")
        english_name = st.text_input("اسم المدرسة باللغة الإنجليزية:")
        established_year = st.number_input("سنة التأسيس:", min_value=2015, max_value=2030, value=2023)
        specialization = st.text_input("التخصص:")
        location = st.text_input("الموقع الجغرافي / المحافظة:")
        accepted_governorates = st.text_input("المحافظات المقبولة (مثال: القاهرة، الجيزة):", value="All")
        minimum_score = st.number_input("الحد الأدنى للقبول (التنسيق):", min_value=140, max_value=280, value=220)
        industrial_partner = st.text_input("الشريك الصناعي:")
        study_duration = st.number_input("سنوات الدراسة:", min_value=3, max_value=5, value=3)
        description = st.text_area("وصف عام للمدرسة ومميزاتها:")
        official_website = st.text_input("رابط الموقع الرسمي للمدرسة:")
        
        submitted = st.form_submit_button("حفظ المدرسة في قاعدة البيانات")
        if submitted:
            if not arabic_name or not specialization or not location:
                st.error("يرجى ملء الحقول الأساسية (الاسم العربي، التخصص، الموقع).")
            else:
                payload = {
                    "arabic_name": arabic_name,
                    "english_name": english_name if english_name else None,
                    "established_year": int(established_year),
                    "specialization": specialization,
                    "location": location,
                    "accepted_governorates": accepted_governorates,
                    "minimum_score": int(minimum_score),
                    "industrial_partner": industrial_partner if industrial_partner else None,
                    "study_duration": int(study_duration),
                    "description": description if description else None,
                    "official_website": official_website if official_website else None
                }
                with st.spinner("جاري حفظ البيانات..."):
                    try:
                        res = requests.post(f"{API_BASE_URL}/schools", json=payload, headers=headers)
                        if res.status_code == 201:
                            st.success(f"🎉 تم إضافة مدرسة {arabic_name} بنجاح!")
                        else:
                            st.error(f"فشل الإضافة: {res.text}")
                    except Exception as e:
                        st.error(f"خطأ أثناء الاتصال بالـ Backend: {e}")

# ==========================================
# 4. شاشة استخراج وحفظ مدرسة بنص (Admin)
# ==========================================
elif menu == "🔍اضافة مدرسة باستخدام نص - بوست فيسبوك, اعلان, ...الخ" and is_admin:
    st.header("🔍 اضافة مدرسة باستخدام نص عشوائي (صلاحيات الإدارة)")
    st.write("ضع نصاً يتحدث عن مدرسة تكنولوجيا تطبيقية وسيقوم الذكاء الاصطناعي باستخراج حقولها وحفظها مباشرة.")
    
    school_text = st.text_area("أدخل النص التعريفي بالمدرسة:", height=150, placeholder="اكتب هنا النص العربي الشامل عن المدرسة...")
    provider = st.selectbox("مزود خدمة الذكاء الاصطناعي (Provider):", ["groq", "hf"])
    
    if st.button("استخراج وحفظ البيانات"):
        if len(school_text) >= 10:
            with st.spinner("جاري التحليل واستخراج البيانات وحفظها..."):
                try:
                    payload = {"text": school_text, "provider": provider}
                    response = requests.post(f"{API_BASE_URL}/llm/extract-school", json=payload, headers=headers)
                    
                    if response.status_code == 200:
                        school_data = response.json()
                        st.success("🎉 تم استخراج البيانات وحفظ المدرسة بنجاح في قاعدة البيانات!")
                        st.json(school_data)
                    else:
                        st.error(f"فشل الاستخراج. (تأكد من اكتمال البيانات بالنص الممرر أو صحة مفاتيح الـ APIKey)")
                except Exception as e:
                    st.error(f"حدث خطأ أثناء الاتصال بالـ Backend: {e}")
        else:
            st.warning("يرجى إدخال نص كافي يحتوي على تفاصيل المدرسة.")

# ==========================================
# 5. شاشة رفع الدليل الجديد (RAG Ingest) - محدثة بالكامل ديناميكياً للبروداكشن
# ==========================================
elif menu == "📂 رفع دليل مدرسة جديد (RAG Ingest)" and is_admin:
    st.header("📂 رفع دليل مدرسة جديد (صلاحيات الإدارة)")
    st.write("ارفع دليل المدرسة الرسمي بصيغة PDF وسيتم حفظه معزولاً ومربوطاً برقم المدرسة تلقائياً.")
    
    with st.spinner("جاري جلب قائمة المدارس النشطة..."):
        try:
            schools_res = requests.get(f"{API_BASE_URL}/schools")
            if schools_res.status_code == 200 and schools_res.json():
                schools_list = schools_res.json()
                school_options = {s["arabic_name"]: s["id"] for s in schools_list}
                
                selected_school_name = st.selectbox("اختر المدرسة التي تود رفع هذا الدليل والملف لها كمرجع دائم:", list(school_options.keys()))
                selected_school_id = school_options[selected_school_name]

                uploaded_file = st.file_uploader("اختر ملف الدليل (PDF فقط):", type=["pdf"])
                
                if st.button("ابدأ المعالجة وتكشيف المتجهات"):
                    if uploaded_file is not None:
                        with st.spinner("جاري فك تشفير الـ PDF وتوليد مصفوفات الـ Embeddings وحفظها في نطاق المدرسة..."):
                            try:
                                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                                # تمرير الـ school_id كـ Query parameter ديناميكي في مسار السيرفر
                                res = requests.post(f"{API_BASE_URL}/rag/ingest?school_id={selected_school_id}", files=files, headers=headers)
                                
                                if res.status_code == 200:
                                    st.success(f"🎉 تم تكشيف ورفع دليل مدرسة ({selected_school_name}) بنجاح وعزل متجهاتها بالكامل!")
                                    st.json(res.json())
                                else:
                                    st.error(f"فشل رفع وحفظ المستند: {res.text}")
                            except Exception as e:
                                st.error(f"خطأ أثناء معالجة الرفع: {e}")
                    else:
                        st.warning("يرجى اختيار ملف PDF أولاً.")
            else:
                st.warning("⚠️ لا توجد مدارس مسجلة. قم بتسجيل المدرسة أولاً لتتمكن من ربط أدلة الـ RAG بها.")
        except Exception as e:
            st.error(f"فشل تحميل بيانات المدارس: {e}")