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

# جلب إعدادات الاتصال
try:
    API_BASE_URL = st.secrets["API_BASE_URL"]
    SYSTEM_API_KEY = st.secrets["API_KEY"]
except Exception:
    API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
    SYSTEM_API_KEY = os.getenv("API_KEY")

# التنسيقات الخاصة بالواجهة العربية
st.markdown("""
    <style>
    .main .block-container {
        direction: rtl;
        text-align: right;
    }
    .main h1, .main h2, .main h3, .main h4, .main p, .main span, .main div {
        direction: rtl;
        text-align: right;
        line-height: 1.6;
    }
    .school-card {
        background-color: #f8f9fa;
        border-right: 6px solid #28a745;
        padding: 22px;
        border-radius: 8px;
        margin-bottom: 20px;
        box-shadow: 0 3px 6px rgba(0,0,0,0.05);
    }
    .metric-box {
        background-color: #e9ecef;
        padding: 12px;
        border-radius: 6px;
        text-align: center;
        font-weight: bold;
        font-size: 16px;
        color: #495057;
        border: 1px solid #ced4da;
    }
    .answer-box {
        background-color: #e8f4fd;
        border-right: 6px solid #007bff;
        padding: 20px;
        border-radius: 8px;
        font-size: 16px;
        color: #1d2124;
        white-space: pre-line;
    }
    </style>
    """, unsafe_allow_html=True)

headers = {"X-API-Key": SYSTEM_API_KEY} if SYSTEM_API_KEY else {}

st.sidebar.title("🎓 القائمة الرئيسية")

# إدارة جلسة المسؤول (Admin)
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False

with st.sidebar.expander("🔐 لوحة تحكم الإدارة"):
    if not st.session_state.is_admin:
        admin_key = st.text_input("أدخل كلمة مرور المسؤول:", type="password")
        if st.button("تسجيل الدخول"):
            if admin_key == SYSTEM_API_KEY:
                st.session_state.is_admin = True
                st.success("تم تفعيل صلاحيات الإدارة!")
                st.rerun()
            else:
                st.error("الكلمة غير صحيحة!")
    else:
        st.write("🟢 أنت تعمل الآن بصلاحيات المشرف.")
        if st.button("تسجيل الخروج"):
            st.session_state.is_admin = False
            st.rerun()

is_admin = st.session_state.is_admin

menu_options = ["🏠 دليل واستعراض المدارس", "🤖 المستشار الذكي (AI Agent)"]
if is_admin:
    menu_options.extend([
        "➕ إضافة مدرسة جديدة", 
        "📝 تعديل بيانات مدرسة",
        "🔍 استخراج بيانات مدرسة من نص",
        "📂 رفع ملفات وأدلة المدارس"
    ])

menu = st.sidebar.radio("اختر الوجهة:", menu_options)

# --- إحصائيات الآدمن لمراقبة ملفات الـ RAG ---
if is_admin:
    st.sidebar.markdown("---")
    st.sidebar.subheader("📊 مراقبة ملفات الـ RAG")
    if st.sidebar.button("📋 عرض الملفات المرفوعة بعدد القطع"):
        try:
            stats_res = requests.get(f"{API_BASE_URL}/rag/sources", headers=headers)
            if stats_res.status_code == 200:
                sources_data = stats_res.json()
                if sources_data:
                    st.sidebar.success(f"إجمالي الملفات الفريدة: {len(sources_data)}")
                    for src in sources_data:
                        st.sidebar.info(f"📄 {src['source']}\n📦 القطع (Chunks): {src['chunk_count']}")
                else:
                    st.sidebar.warning("لا توجد ملفات مرفوعة حالياً.")
            else:
                st.sidebar.error("فشل في جلب إحصائيات الملفات من السيرفر.")
        except Exception as e:
            st.sidebar.error(f"خطأ في الاتصال: {e}")

# 1. دليل واستعراض المدارس
if menu == "🏠 دليل واستعراض المدارس":
    st.title("🏫 دليل مدارس التكنولوجيا التطبيقية بمصر")
    with st.spinner("جاري تحديث قائمة المدارس..."):
        try:
            res = requests.get(f"{API_BASE_URL}/schools")
            if res.status_code == 200:
                schools = res.json()
                if not schools:
                    st.info("لا توجد مدارس مسجلة في الدليل حتى الآن.")
                else:
                    for school in schools:
                        st.markdown(f"""
                        <div class="school-card">
                            <h2 style='margin-top:0; color:#1e7e34;'>🏫 {school['arabic_name']}</h2>
                            <p style='font-size:16px; color:#495057;'>{school['description'] or 'لا يوجد وصف تفصيلي متوفر حالياً.'}</p>
                        </div>
                        """, unsafe_allow_html=True)
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.markdown(f"🎯 **التخصص:** {school['specialization']}")
                            st.markdown(f"🤝 **الشريك الصناعي:** {school['industrial_partner'] or 'غير محدد'}")
                        with col2:
                            st.markdown(f"📍 **الموقع:** {school['location']}")
                            st.markdown(f"🌍 **المحافظات:** {school['accepted_governorates']}")
                        with col3:
                            st.markdown(f"⏱️ **سنوات الدراسة:** {school['study_duration']}")
                            st.markdown(f"📅 **التأسيس:** {school['established_year']}")
                        st.markdown("<br>", unsafe_allow_html=True)
                        col_btn1, col_btn2 = st.columns([1, 2])
                        with col_btn1:
                            st.markdown(f"<div class='metric-box'>📊 التنسيق: {school['minimum_score']} درجة</div>", unsafe_allow_html=True)
                        with col_btn2:
                            if school['official_website']:
                                st.link_button("🌐 الموقع الرسمي للمدرسة", school['official_website'])
                        if is_admin:
                            if st.button(f"🗑️ حذف مدرسة {school['arabic_name']}", key=f"del_{school['id']}"):
                                del_res = requests.delete(f"{API_BASE_URL}/schools/{school['id']}", headers=headers)
                                if del_res.status_code == 204:
                                    st.success("تم حذف المدرسة بنجاح!")
                                    st.rerun()
                        st.markdown("<br><hr><br>", unsafe_allow_html=True)
        except Exception as e:
            st.error(f"خطأ في الاتصال: {e}")

# 2. المستشار الذكي المتصل بالـ AI Agent 🤖
elif menu == "🤖 المستشار الذكي (AI Agent)":
    st.title("🤖 المستشار الذكي لمدارس التكنولوجيا التطبيقية")
    st.caption("مساعد الذكاء الاصطناعي يمكنه البحث في قواعد البيانات وأدلة المدارس المرفوعة ومقارنة المدارس بذكاء.")

    user_question = st.text_area("اكتب سؤالك هنا بوضوح (مثال: قارن بين مدارس الذكاء الاصطناعي، أو ما هي المدارس المتاحة في الجيزة؟):", height=100)
    
    if st.button("🚀 إرسال السؤال إلى المستشار الذكي"):
        if user_question.strip():
            with st.status("🧠 المساعد الذكي يفكر ويحدد الأدوات المناسبة للرد...", expanded=True) as status:
                try:
                    payload = {"question": user_question}
                    response = requests.post(f"{API_BASE_URL}/agent", json=payload, headers=headers)
                    
                    if response.status_code == 200:
                        data = response.json()
                        status.update(label="✅ تم الوصول إلى الإجابة المناسبة!", state="complete", expanded=False)
                        
                        # عرض خطوات التفكير والأدوات المستخدمة إن وجدت
                        steps = data.get("steps", [])
                        if steps:
                            with st.expander("🔍 تفاصيل البحث والعمليات المنجزة بواسطة المساعد الذكي"):
                                for idx, step in enumerate(steps, 1):
                                    st.write(f"**الخطوة {idx}:** استخدام أداة `{step['tool']}`")
                                    st.json(step['args'])
                        
                        st.markdown("### 🤖 إجابة المستشار الذكي:")
                        st.markdown(f'<div class="answer-box">{data["answer"]}</div>', unsafe_allow_html=True)
                        
                    else:
                        status.update(label="❌ حدث خطأ أثناء معالجة الطلب.", state="error")
                        st.error(f"خطأ من السيرفر: {response.text}")
                except Exception as e:
                    status.update(label="❌ فشل الاتصال بالخادم.", state="error")
                    st.error(f"خطأ في الاتصال: {e}")
        else:
            st.warning("يرجى كتابة سؤال أولاً.")

# 3. إضافة مدرسة جديدة (Admin)
elif menu == "➕ إضافة مدرسة جديدة" and is_admin:
    st.header("➕ تسجيل مدرسة جديدة")
    with st.form("add_school_form"):
        arabic_name = st.text_input("اسم المدرسة باللغة العربية (مطلوب):")
        english_name = st.text_input("اسم المدرسة باللغة الإنجليزية (اختياري):")
        established_year = st.number_input("سنة التأسيس:", min_value=2015, max_value=2030, value=2023)
        specialization = st.text_input("التخصص الدراسي:")
        location = st.text_input("الموقع الجغرافي:")
        accepted_governorates = st.text_input("المحافظات المقبولة:", value="جميع المحافظات")
        minimum_score = st.number_input("الحد الأدنى للمجموع:", min_value=140, max_value=280, value=220)
        industrial_partner = st.text_input("الشريك الصناعي:")
        study_duration = st.number_input("سنوات الدراسة:", min_value=3, max_value=5, value=3)
        description = st.text_area("وصف المدرسة ومميزاتها:")
        official_website = st.text_input("رابط الموقع الرسمي:")
        
        if st.form_submit_button("حفظ المدرسة"):
            if not arabic_name or not specialization or not location:
                st.error("يرجى تعبئة الحقول الأساسية.")
            else:
                payload = {
                    "arabic_name": arabic_name, "english_name": english_name or None, "established_year": int(established_year),
                    "specialization": specialization, "location": location, "accepted_governorates": accepted_governorates,
                    "minimum_score": int(minimum_score), "industrial_partner": industrial_partner or None,
                    "study_duration": int(study_duration), "description": description or None, "official_website": official_website or None
                }
                res = requests.post(f"{API_BASE_URL}/schools", json=payload, headers=headers)
                if res.status_code == 201:
                    st.success(f"🎉 تم تسجيل مدرسة '{arabic_name}' بنجاح!")

# 4. تعديل بيانات مدرسة (Admin) - مع إصلاح PATCH
elif menu == "📝 تعديل بيانات مدرسة" and is_admin:
    st.header("📝 تعديل وتحديث بيانات مدرسة مسجلة")
    try:
        schools_res = requests.get(f"{API_BASE_URL}/schools")
        if schools_res.status_code == 200 and schools_res.json():
            schools_list = schools_res.json()
            school_map = {s["arabic_name"]: s for s in schools_list}
            selected_name = st.selectbox("اختر المدرسة المراد تعديل بياناتها:", list(school_map.keys()))
            s_data = school_map[selected_name]
            
            with st.form("edit_form"):
                up_arabic = st.text_input("اسم المدرسة بالعربية:", value=s_data["arabic_name"])
                up_english = st.text_input("اسم المدرسة بالإنجليزية:", value=s_data["english_name"] or "")
                up_year = st.number_input("سنة التأسيس:", min_value=2015, max_value=2030, value=int(s_data["established_year"]))
                up_spec = st.text_input("التخصص الدراسي الحالي:", value=s_data["specialization"])
                up_loc = st.text_input("الموقع الجغرافي:", value=s_data["location"])
                up_gov = st.text_input("المحافظات المقبولة:", value=s_data["accepted_governorates"])
                up_score = st.number_input("الحد الأدنى للقبول:", min_value=140, max_value=280, value=int(s_data["minimum_score"]))
                up_partner = st.text_input("الشريك الصناعي:", value=s_data["industrial_partner"] or "")
                up_dur = st.number_input("سنوات الدراسة:", min_value=3, max_value=5, value=int(s_data["study_duration"]))
                up_desc = st.text_area("وصف ومميزات المدرسة:", value=s_data["description"] or "")
                up_web = st.text_input("رابط الموقع الرسمي:", value=s_data["official_website"] or "")
                
                if st.form_submit_button("حفظ التغييرات"):
                    up_payload = {
                        "arabic_name": up_arabic, "english_name": up_english or None, "established_year": int(up_year),
                        "specialization": up_spec, "location": up_loc, "accepted_governorates": up_gov,
                        "minimum_score": int(up_score), "industrial_partner": up_partner or None,
                        "study_duration": int(up_dur), "description": up_desc or None, "official_website": up_web or None
                    }
                    # التعديل الصارم: استخدام patch بدلاً من put ليتوافق مع main.py
                    patch_res = requests.patch(f"{API_BASE_URL}/schools/{s_data['id']}", json=up_payload, headers=headers)
                    if patch_res.status_code == 200:
                        st.success("🎉 تم تحديث بيانات المدرسة بنجاح!")
                        st.rerun()
                    else:
                        st.error(f"فشل التعديل: {patch_res.text}")
    except Exception as e:
        st.error(f"خطأ أثناء جلب قائمة المدارس: {e}")

# 5. استخراج مدرسة من نص (Admin)
elif menu == "🔍 استخراج بيانات مدرسة من نص" and is_admin:
    st.header("🔍 استخراج وتعبئة بيانات المدارس تلقائياً")
    school_text = st.text_area("الصق النص هنا:", height=150)
    provider = st.selectbox("محرك التحليل الذكي المفضل:", ["groq", "hf"])
    if st.button("تحليل النص وحفظ المدرسة"):
        if len(school_text) >= 10:
            payload = {"text": school_text, "provider": provider}
            response = requests.post(f"{API_BASE_URL}/llm/extract-school", json=payload, headers=headers)
            if response.status_code == 200:
                st.success("🎉 نجح التحليل وحفظ المدرسة بالكامل!")
                st.json(response.json())
        else:
            st.warning("يرجى كتابة نص يحتوي على 10 أحرف على الأقل.")

# 6. رفع ملف المعرفة (RAG Ingest)
elif menu == "📂 رفع ملفات وأدلة المدارس" and is_admin:
    st.header("📂 إدارة ورفع ملفات المعرفة للمدارس")
    try:
        schools_res = requests.get(f"{API_BASE_URL}/schools")
        if schools_res.status_code == 200 and schools_res.json():
            schools_list = schools_res.json()
            school_options = {s["arabic_name"]: s["id"] for s in schools_list}
            selected_school_name = st.selectbox("اختر المدرسة المستهدفة برفع هذا الملف:", list(school_options.keys()))
            selected_school_id = school_options[selected_school_name]

            uploaded_file = st.file_uploader("اختر ملف الدليل الرسمي (PDF فقط):", type=["pdf"])
            if st.button("بدأ معالجة وحفظ الملف"):
                if uploaded_file is not None:
                    with st.spinner("جاري تفكيك وحفظ الملف..."):
                        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                        res = requests.post(f"{API_BASE_URL}/rag/ingest?school_id={selected_school_id}", files=files, headers=headers)
                        if res.status_code == 200:
                            st.success(f"🎉 تم تفكيك وتكشيف ملف مدرسة ({selected_school_name}) بنجاح!")
                            st.json(res.json())
                        else:
                            st.error(f"فشل الرفع: {res.text}")
        else:
            st.warning("⚠️ لا توجد مدارس مسجلة.")
    except Exception as e:
        st.error(f"فشل جلب قائمة المدارس: {e}")